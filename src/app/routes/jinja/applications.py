"""
Applications routes for the Flask application
=============================================="""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, request, Response, redirect, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from app.utils.template_paths import render_template_compat as render_template
from app.extensions import db
from app.models import (
    ModelCapability,
    GeneratedApplication,
    SecurityAnalysis,
    PortConfiguration,
)
from app.utils.helpers import get_app_directory
from app.routes.shared_utils import _project_root
from app.routes.jinja.detail_context import build_application_detail_context
from app.routes.jinja.shared import SimplePagination

# Blueprint for applications routes
applications_bp = Blueprint('applications', __name__, url_prefix='/applications')


# Require authentication
@applications_bp.before_request
def require_authentication():
    """Require authentication for all application endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access application features.', 'info')
        return redirect(url_for('auth.login', next=request.url))


def build_applications_context():
    """Build context for Applications overview using application-centric filtering and pagination."""
    # Filter & table state parameters
    model_filter_raw = (request.args.get('model') or '').strip()
    # Accept comma-separated slugs
    model_filter_list = [m.strip() for m in model_filter_raw.split(',') if m.strip()]
    provider_filter = (request.args.get('provider') or '').strip()
    search_filter = (request.args.get('search') or '').strip()
    status_filter_raw = (request.args.get('status') or '').strip()  # comma-aware
    status_filters = [s.strip().lower() for s in status_filter_raw.split(',') if s.strip()]
    type_filter = (request.args.get('type') or '').strip()
    ports_filter = (request.args.get('ports') or '').strip()
    analysis_filter = (request.args.get('analysis') or '').strip()
    sort_field = request.args.get('sort', 'model')  # model|provider|model_desc|provider_desc
    page = max(1, int(request.args.get('page', 1) or 1))
    per_page = min(100, max(5, int(request.args.get('per_page', 25) or 25)))

    # Preload PortConfiguration map
    port_map: dict[tuple[str, int], dict] = {}
    try:
        for pc in db.session.query(PortConfiguration).all():
            port_map[(pc.model, pc.app_num)] = {'backend': pc.backend_port, 'frontend': pc.frontend_port}
    except Exception as e:
        current_app.logger.warning(f"Failed to load PortConfiguration from DB: {e}")

    # Base GeneratedApplication query (apps-level)
    q = GeneratedApplication.query
    if model_filter_list:
        try:
            q = q.filter(GeneratedApplication.model_slug.in_(model_filter_list))
        except Exception:
            pass
    if provider_filter:
        q = q.filter(GeneratedApplication.provider == provider_filter)
    if search_filter:
        # Match model slug, provider, app_type
        like = f"%{search_filter}%"
        try:
            from sqlalchemy import or_
            q = q.filter(or_(GeneratedApplication.model_slug.ilike(like),
                             GeneratedApplication.provider.ilike(like),
                             GeneratedApplication.app_type.ilike(like)))
        except Exception:
            q = q.filter(GeneratedApplication.model_slug.contains(search_filter))
    # Soft sort at DB level for determinism
    if sort_field.startswith('provider'):
        q = q.order_by(GeneratedApplication.provider.asc(), GeneratedApplication.model_slug.asc(), GeneratedApplication.app_number.asc())
    else:
        q = q.order_by(GeneratedApplication.model_slug.asc(), GeneratedApplication.app_number.asc())

    # Fetch rows once; for typical sizes this is OK and enables status/ports filters
    rows = q.all()
    total_apps_overall = len(rows)

    # Skip expensive Docker checks by default for faster loading
    # Docker status will be fetched via HTMX/client-side if needed
    check_docker = request.args.get('check_docker', 'false').lower() == 'true'
    
    # Prepare Docker status map (status only) - only if explicitly requested
    docker_mgr = None
    if check_docker:
        try:
            from app.services.service_locator import ServiceLocator
            docker_mgr = ServiceLocator.get_docker_manager()
        except Exception:
            docker_mgr = None  # type: ignore

    STOPPED_STATES = {'exited', 'dead', 'created', 'removing', 'stopped'}

    def _resolve_status_fast(db_status_raw: str | None) -> str:
        """Fast status resolution using only database status."""
        db_status = (db_status_raw or '').strip().lower()
        if db_status in ('running', 'stopped', 'not_created', 'error'):
            return db_status
        return db_status if db_status else 'unknown'

    def _resolve_status_docker(model_slug: str, app_number: int, db_status_raw: str | None) -> tuple[str, dict[str, Any]]:
        """Determine application status using Docker (slow but accurate)."""
        status_details: dict[str, Any] = {}
        db_status = (db_status_raw or '').strip().lower()
        status_guess = db_status if db_status else 'unknown'

        if not docker_mgr or not getattr(docker_mgr, 'client', None):
            return status_guess, status_details

        try:
            summary = docker_mgr.container_status_summary(model_slug, app_number)  # type: ignore[attr-defined]
            status_details = summary or {}
        except Exception:
            return status_guess, status_details

        states = [str(s or '').lower() for s in status_details.get('states', [])]
        containers_found = int(status_details.get('containers_found') or 0)

        if any(state == 'running' for state in states):
            return 'running', status_details
        if any(state in STOPPED_STATES for state in states):
            return 'stopped', status_details
        if containers_found:
            # Containers exist but status unknown -> treat as stopped to avoid "Unknown" badge
            return 'stopped', status_details

        # No containers found. If compose file exists, assume not created yet.
        compose_exists = False
        try:
            compose_path = docker_mgr._get_compose_path(model_slug, app_number)  # type: ignore[attr-defined]
            compose_exists = compose_path.exists()
            status_details['compose_path'] = str(compose_path)
            status_details['compose_file_exists'] = compose_exists
        except Exception:
            pass

        if compose_exists:
            return 'not_created', status_details

        if status_guess == 'running':
            # Docker shows nothing running, override stale DB state
            return 'stopped', status_details

        return status_guess or 'unknown', status_details

    def _project_name(model_slug: str, app_num: int) -> str:
        safe_model = (model_slug or '').replace('_', '-').replace('.', '-')
        return f"{safe_model}-app{app_num}"

    # Build application dicts
    applications_all: list[dict] = []
    running_count = 0
    for r in rows:
        ports = port_map.get((r.model_slug, r.app_number), {})
        derived_ports = []
        if isinstance(ports, dict):
            for key in ('backend', 'frontend'):
                val = ports.get(key)
                if isinstance(val, int):
                    derived_ports.append({'host_port': val})
        try:
            m = ModelCapability.query.filter_by(canonical_slug=r.model_slug).first()
            model_provider = getattr(m, 'provider', None) or r.provider or 'local'
            display_name = getattr(m, 'display_name', None) or getattr(m, 'model_name', None) or r.model_slug
        except Exception:
            model_provider = r.provider or 'local'
            display_name = r.model_slug
        # Determine live status - use fast path unless Docker checks requested
        raw_db_status = r.container_status
        if not raw_db_status and getattr(r, 'generation_status', None):
            try:
                raw_db_status = r.generation_status.value  # type: ignore[attr-defined]
            except Exception:
                raw_db_status = str(r.generation_status)

        # Fast path: just use DB status (no Docker API calls)
        if not check_docker:
            status = _resolve_status_fast(raw_db_status)
            status_details = {}
        else:
            # Slow path: check Docker for accurate status
            status, status_details = _resolve_status_docker(r.model_slug, r.app_number, raw_db_status)
        
        if status == 'running':
            running_count += 1
        applications_all.append({
            'model_slug': r.model_slug,
            'model_provider': model_provider,
            'model_display_name': display_name,
            'app_number': r.app_number,
            'status': status,
            'id': r.id,
            'app_type': r.app_type or 'web_app',
            'ports': derived_ports,
            'container_size': None,
            'analysis_status': 'none',
            'status_details': status_details
        })

    # Apply in-memory filters that depend on enriched fields
    def _passes_status(a: dict) -> bool:
        if not status_filters:
            return True
        return (a.get('status') or '').lower() in status_filters
    def _passes_type(a: dict) -> bool:
        return (not type_filter) or (a.get('app_type') == type_filter)
    def _passes_ports(a: dict) -> bool:
        if not ports_filter:
            return True
        has = bool(a.get('ports'))
        if ports_filter == 'has_ports':
            return has
        if ports_filter == 'no_ports':
            return not has
        # exposed/internal are placeholders; treat 'exposed' same as has_ports for now
        if ports_filter == 'exposed':
            return has
        if ports_filter == 'internal':
            return not has
        return True
    def _passes_analysis(a: dict) -> bool:
        if not analysis_filter:
            return True
        # With no analysis data wired yet, only allow 'not_analyzed'
        if analysis_filter == 'not_analyzed':
            return (a.get('analysis_status') in (None, '', 'none'))
        return True

    filtered_apps = [a for a in applications_all if _passes_status(a) and _passes_type(a) and _passes_ports(a) and _passes_analysis(a)]

    # Sort applications
    if sort_field in ('model', 'model_desc'):
        filtered_apps.sort(key=lambda a: (a['model_display_name'] or '', a['app_number']), reverse=sort_field.endswith('desc'))
    elif sort_field in ('provider', 'provider_desc'):
        filtered_apps.sort(key=lambda a: (a['model_provider'] or '', a['model_display_name'] or '', a['app_number']), reverse=sort_field.endswith('desc'))
    else:
        filtered_apps.sort(key=lambda a: (a['model_display_name'] or '', a['app_number']))

    # Pagination on filtered apps
    total_filtered = len(filtered_apps)
    page_count = max(1, (total_filtered + per_page - 1) // per_page)
    start = (page - 1) * per_page
    end = start + per_page
    applications_list = filtered_apps[start:end]
    pagination = SimplePagination(page, per_page, total_filtered, applications_list)

    # Providers and models for filter dropdowns (derived from rows)
    try:
        providers = sorted({(r.provider or 'local') for r in rows if getattr(r, 'provider', None)})
    except Exception:
        providers = []
    available_models = []
    try:
        slugs = sorted({r.model_slug for r in rows})
        # Fetch names when available
        name_map = {m.canonical_slug: (getattr(m, 'display_name', None) or m.model_name or m.canonical_slug)
                    for m in ModelCapability.query.filter(ModelCapability.canonical_slug.in_(slugs)).all()} if slugs else {}
        for s in slugs:
            available_models.append({'slug': s, 'display_name': name_map.get(s, s)})
    except Exception:
        available_models = [{'slug': s, 'display_name': s} for s in sorted({r.model_slug for r in rows})]

    # Stats
    try:
        analyzed_count = db.session.query(SecurityAnalysis).count()
    except Exception:
        analyzed_count = 0
    stats = {
        'total_applications': total_apps_overall,
        'running_applications': running_count,
        'analyzed_applications': analyzed_count,
        'unique_models': len({r.model_slug for r in rows}),
    }

    context = {
        'total_apps': total_apps_overall,
        'running_containers': running_count,
        'stopped_containers': max(0, total_apps_overall - running_count),
        'total_models': len({r.model_slug for r in rows}),
        'providers': providers,
        'applications': applications_list,
        'total_applications': total_apps_overall,
        'total_count': total_filtered,
        'available_models': available_models,
        'stats': stats,
        'applications_stats': stats,
        'current_filters': {
            'model': model_filter_raw,
            'provider': provider_filter,
            'search': search_filter,
            'status': status_filter_raw,
            'sort': sort_field,
            'page': page,
            'per_page': per_page,
            'page_count': page_count
        },
        'pagination': pagination,
        'active_page': 'applications',
        'has_right_sidebar': True
    }
    return context


def _render_applications_page():
    """Core implementation for applications overview (shared by legacy and new routes)."""
    try:
        context = build_applications_context()
        return render_template('pages/applications/applications_main.html', **context)
    except Exception as e:
        current_app.logger.error(f"Error loading applications: {e}")
        flash(f"Error loading applications: {e}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            application_grid=[], total_apps=0,
            running_containers=0, stopped_containers=0,
            current_filters={}, providers=[], error=str(e)
        )


@applications_bp.route('/')
def applications_index():
    """Applications overview page."""
    return _render_applications_page()


@applications_bp.route('/<model_slug>/<int:app_number>')
def application_detail(model_slug, app_number):
    """Detailed view for a specific application using the unified detail context."""
    try:
        context = build_application_detail_context(model_slug, app_number, allow_synthetic=True)
        return render_template('pages/applications/detail.html', **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error loading application details for %s/app%s: %s", model_slug, app_number, exc)
        flash(f"Error loading application details: {exc}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=404,
            error_title='Application Not Found',
            error_message=f"Application '{model_slug}/app{app_number}' not found"
        )


@applications_bp.route('/generate', methods=['POST'])
def generate_application():
    """HTMX endpoint: Generate a new application record."""
    try:
        from app.services import application_service as app_service

        model_slug = (request.form.get('model_slug') or '').strip()
        app_number_raw = request.form.get('app_number')
        app_type = (request.form.get('app_type') or 'web_app').strip() or 'web_app'
        auto_start = request.form.get('auto_start') == 'on'

        if not model_slug or not app_number_raw:
            return (
                '<div class="alert alert-danger">Model and app number are required.</div>',
                400,
            )
        try:
            app_number = int(app_number_raw)
        except Exception:
            return (
                '<div class="alert alert-danger">Invalid app number.</div>',
                400,
            )

        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return (
                f'<div class="alert alert-danger">Unknown model: {model_slug}</div>',
                404,
            )

        payload = {
            'model_slug': model_slug,
            'app_number': app_number,
            'app_type': app_type,
            'provider': model.provider,
        }

        created = app_service.create_application(payload)

        if auto_start and created.get('id'):
            try:
                app_service.start_application(created['id'])
            except Exception:  # pragma: no cover - non critical
                current_app.logger.warning("Failed to auto-start application", exc_info=True)

        detail_url = f"{request.url_root.rstrip('/')}/applications/{model_slug}/{app_number}"
        resp = Response(
            '<div class="alert alert-success">'
            f'Successfully created application for <strong>{model_slug}</strong> '
            f'(<a href="{detail_url}" target="_blank">open details</a>).</div>'
        )
        resp.headers['HX-Trigger'] = 'refresh-grid'
        return resp
    except Exception as e:
        msg = str(e)
        if 'unique' in msg.lower() and 'model' in msg.lower():
            return (
                '<div class="alert alert-warning">An application for this model and number already exists.</div>',
                409,
            )
        current_app.logger.error(f"Error generating application: {e}")
        return (
            f'<div class="alert alert-danger">Error generating application: {str(e)}</div>',
            500,
        )


@applications_bp.route('/<model_slug>/<int:app_number>/section/overview')
def application_section_overview(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'overview')


@applications_bp.route('/<model_slug>/<int:app_number>/section/prompts')
def application_section_prompts(model_slug, app_number):
    """Return the prompts modal so the UI can lazy load it via HTMX."""
    try:
        context = build_application_detail_context(model_slug, app_number, allow_synthetic=True)
        return render_template('pages/applications/partials/modals/prompts_modal.html', **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error rendering prompts modal for %s/app%s: %s", model_slug, app_number, exc)
        return ('<div class="modal fade" tabindex="-1" role="dialog">'
                '<div class="modal-dialog"><div class="modal-content">'
                '<div class="modal-header">'
                '<h5 class="modal-title">Prompts</h5>'
                '<button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>'
                '</div>'
                f'<div class="modal-body"><div class="alert alert-danger mb-0">Failed to load prompts: {exc}</div></div>'
                '</div></div></div>'), 500


@applications_bp.route('/<model_slug>/<int:app_number>/section/files')
def application_section_files(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'files')


@applications_bp.route('/<model_slug>/<int:app_number>/section/ports')
def application_section_ports(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'ports')


@applications_bp.route('/<model_slug>/<int:app_number>/section/container')
def application_section_container(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'container')


@applications_bp.route('/<model_slug>/<int:app_number>/section/analyses')
def application_section_analyses(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'analyses')


@applications_bp.route('/<model_slug>/<int:app_number>/section/metadata')
def application_section_metadata(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'metadata')


@applications_bp.route('/<model_slug>/<int:app_number>/section/artifacts')
def application_section_artifacts(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'artifacts')


@applications_bp.route('/<model_slug>/<int:app_number>/section/logs')
def application_section_logs(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'logs')


@applications_bp.route('/<model_slug>/<int:app_number>/generation-metadata')
def application_generation_metadata(model_slug, app_number):
    """View generation metadata JSON files for backend and frontend."""
    from pathlib import Path
    from flask import jsonify
    
    metadata_dir = Path('generated') / 'metadata' / 'indices' / 'runs' / model_slug / f'app{app_number}'
    
    if not metadata_dir.exists():
        return jsonify({
            'error': 'Metadata directory not found',
            'path': str(metadata_dir),
            'backend': None,
            'frontend': None
        }), 404
    
    result = {
        'model_slug': model_slug,
        'app_number': app_number,
        'metadata_dir': str(metadata_dir),
        'backend': None,
        'frontend': None
    }
    
    # Find backend metadata
    backend_files = list(metadata_dir.glob(f'{model_slug}_app{app_number}_backend_*_metadata.json'))
    if backend_files:
        try:
            import json
            with open(backend_files[0], 'r', encoding='utf-8') as f:
                result['backend'] = json.load(f)
                result['backend_file'] = backend_files[0].name
        except Exception as e:
            result['backend_error'] = str(e)
    
    # Find frontend metadata
    frontend_files = list(metadata_dir.glob(f'{model_slug}_app{app_number}_frontend_*_metadata.json'))
    if frontend_files:
        try:
            import json
            with open(frontend_files[0], 'r', encoding='utf-8') as f:
                result['frontend'] = json.load(f)
                result['frontend_file'] = frontend_files[0].name
        except Exception as e:
            result['frontend_error'] = str(e)
    
    return jsonify(result)


def _render_application_section(model_slug: str, app_number: int, section: str):
    """Shared loader for application detail sections (partials)."""
    try:
        context = build_application_detail_context(model_slug, app_number, allow_synthetic=True)
        section_cfg = context.get('sections_map', {}).get(section)
        if not section_cfg:
            return f'<div class="alert alert-warning">Unknown section: {section}</div>', 404
        return render_template(section_cfg['template'], **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error rendering section %s for %s/app%s: %s", section, model_slug, app_number, exc)
        return f'<div class="alert alert-danger">Failed to load {section}: {exc}</div>', 500


@applications_bp.route('/<model_slug>/<int:app_number>/file')
def application_file_preview(model_slug, app_number):
    """HTMX endpoint to preview a file inside an application directory."""
    rel_path = request.args.get('path', '').strip()
    if not rel_path:
        return '<div class="text-muted">No file specified.</div>'
    try:
        app_dir = get_app_directory(model_slug, app_number)
        if not app_dir.exists():
            return '<div class="text-danger">Application directory not found.</div>'
        # prevent path traversal
        candidate = (app_dir / rel_path).resolve()
        if not str(candidate).startswith(str(app_dir.resolve())):
            return '<div class="text-danger">Invalid path.</div>', 400
        if not candidate.exists() or not candidate.is_file():
            return '<div class="text-warning">File not found.</div>', 404
        try:
            content = candidate.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return '<div class="text-danger">Unable to read file.</div>', 500
        from markupsafe import escape
        escaped = escape(content)
        return f'<div class="file-preview"><h6 class="small text-muted mb-2">{rel_path}</h6><pre class="small bg-body-tertiary p-2 rounded" style="max-height:480px; overflow:auto; white-space: pre-wrap">{escaped}</pre></div>'
    except Exception as e:
        current_app.logger.error(f"Error previewing file {model_slug}/app{app_number}:{rel_path}: {e}")
        return f'<div class="text-danger">Error: {e}</div>', 500


@applications_bp.route('/<model_slug>/<int:app_number>/logs/modal')
def application_logs_modal(model_slug, app_number):
    """Return a modal containing recent log lines for the app (backend & frontend)."""
    try:
        logs_dir = _project_root() / 'generated' / 'apps' / '_logs'
        # fallback per model directory
        model_logs_dir = logs_dir / model_slug
        collected = []
        def _tail(path, limit=200):
            try:
                if path.exists():
                    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()[-limit:]
                    collected.append((path.name, lines))
            except Exception:
                pass
        # Try generic aggregated logs first
        _tail(logs_dir / f'{model_slug}_app{app_number}_backend.log')
        _tail(logs_dir / f'{model_slug}_app{app_number}_frontend.log')
        # Per-model subdir
        _tail(model_logs_dir / f'app{app_number}_backend.log')
        _tail(model_logs_dir / f'app{app_number}_frontend.log')
        if not collected:
            return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                    '<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">'
                    '<div class="modal-header"><h5 class="modal-title">Logs</h5>'
                    '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                    '<div class="modal-body"><div class="alert alert-warning mb-0">No logs found for this application.</div></div>'
                    '</div></div></div>')
        body_parts = []
        for name, lines in collected:
            escaped = '\n'.join(lines).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            body_parts.append(f'<h6 class="mt-3">{name}</h6><pre class="small bg-body-tertiary p-2 rounded" style="max-height:260px; overflow:auto">{escaped}</pre>')
        body_html = ''.join(body_parts)
        return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                '<div class="modal-dialog modal-lg modal-dialog-scrollable"><div class="modal-content">'
                f'<div class="modal-header"><h5 class="modal-title">Logs - {model_slug} app{app_number}</h5>'
                '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                f'<div class="modal-body">{body_html}</div>'
                '</div></div></div>')
    except Exception as e:
        current_app.logger.error(f"Error loading logs modal for {model_slug}/app{app_number}: {e}")
        return ('<div id="logsModal" class="modal fade" tabindex="-1">'
                '<div class="modal-dialog"><div class="modal-content">'
                '<div class="modal-header"><h5 class="modal-title">Logs</h5>'
                '<button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>'
                f'<div class="modal-body"><div class="alert alert-danger">Error loading logs: {e}</div></div>'
                '</div></div></div>'), 500


@applications_bp.route('/<model_slug>/<int:app_number>/diagnostics/ports')
def application_ports_diagnostics(model_slug, app_number):
    """Lightweight preformatted diagnostics for port resolution attempts."""
    from app.utils.port_resolution import resolve_ports
    try:
        result = resolve_ports(model_slug, app_number, include_attempts=True)
        if not result:
            return '<pre class="small">{\n  "found": false\n}</pre>'
        import html as _html
        backend = result.get('backend')
        frontend = result.get('frontend')
        source = _html.escape(str(result.get('source')))
        attempts = result.get('attempts', [])
        esc_attempts = ',\n    '.join([_html.escape(a) for a in attempts])
        body = (
            '{\n'
            f'  "found": true,\n'
            f'  "backend": {backend},\n'
            f'  "frontend": {frontend},\n'
            f'  "source": "{source}",\n'
            f'  "attempts": [\n    {esc_attempts}\n  ]\n'
            '}'
        )
        return f'<pre class="small">{body}</pre>'
    except Exception as e:
        return f'<div class="alert alert-danger small">Diagnostics error: {e}</div>', 500


@applications_bp.route('/bulk_operations')
def bulk_operations():
    """HTMX endpoint for bulk operations modal content."""
    try:
        return render_template('pages/applications/partials/bulk_operations.html')
    except Exception as e:
        current_app.logger.error(f"Error loading bulk operations: {e}")
        return f'<div class="alert alert-danger">Error loading bulk operations: {str(e)}</div>'
