"""
Models routes for the Flask application
======================================="""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, request, Response
from werkzeug.exceptions import HTTPException
from app.utils.template_paths import render_template_compat as render_template
from app.extensions import db
from app.models import (
    ModelCapability,
    GeneratedApplication,
    SecurityAnalysis,
    PerformanceTest,
    PortConfiguration,
    ExternalModelInfoCache,
)
from app.utils.helpers import get_app_directory, deep_merge_dicts, dicts_to_csv
from app.utils.port_resolution import resolve_ports
from app.routes.shared_utils import _project_root
from sqlalchemy import or_
from app.routes.jinja.detail_context import (
    build_application_detail_context,
    build_model_detail_context,
)

# Blueprint for models routes
models_bp = Blueprint('models', __name__, url_prefix='/models')

# Require authentication
@models_bp.before_request
def require_authentication():
    """Require authentication for all model endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access model features.', 'info')
        return redirect(url_for('auth.login', next=request.url))


class SimplePagination:
    """Lightweight pagination helper compatible with templates."""

    def __init__(self, page: int, per_page: int, total: int, items: list[Any]):
        self.page = page
        self.per_page = per_page
        self.total = total
        self.items = items

    @property
    def pages(self) -> int:
        if self.per_page <= 0:
            return 1
        return max(1, (self.total + self.per_page - 1) // self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def prev_num(self) -> int:
        return max(1, self.page - 1)

    @property
    def next_num(self) -> int:
        return min(self.pages, self.page + 1)

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 2,
        right_edge: int = 2,
    ):
        """Yield page numbers for pagination controls with ellipses as None.

        Mirrors Flask-SqlAlchemy Pagination.iter_pages signature so templates
        like `for page_num in pagination.iter_pages()` work unchanged.
        """
        last = 0
        total_pages = self.pages
        for num in range(1, total_pages + 1):
            if (
                num <= left_edge
                or (num >= self.page - left_current and num <= self.page + right_current)
                or num > total_pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


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

    # Prepare Docker status map (status only)
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
    except Exception:
        docker_mgr = None  # type: ignore

    STOPPED_STATES = {'exited', 'dead', 'created', 'removing', 'stopped'}

    def _resolve_status(model_slug: str, app_number: int, db_status_raw: str | None) -> tuple[str, dict[str, Any]]:
        """Determine application status using Docker when possible."""
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
        # Determine live status with Docker check fallback
        raw_db_status = r.container_status
        if not raw_db_status and getattr(r, 'generation_status', None):
            try:
                raw_db_status = r.generation_status.value  # type: ignore[attr-defined]
            except Exception:
                raw_db_status = str(r.generation_status)

        status, status_details = _resolve_status(r.model_slug, r.app_number, raw_db_status)
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

def _enrich_model(m: ModelCapability) -> dict:
    """Minimal model enrichment used by CSV export and models filter/comparison.

    Avoids network calls; derives fields from stored capabilities/metadata.
    """
    try:
        caps_raw = m.get_capabilities() or {}
    except Exception:
        caps_raw = {}
    try:
        meta = m.get_metadata() or {}
    except Exception:
        meta = {}

    # Normalize capabilities to a simple dict/list when possible
    caps: Any = {}
    if isinstance(caps_raw, dict):
        caps = caps_raw.get('capabilities') if 'capabilities' in caps_raw else caps_raw
    else:
        # Best-effort: if it's a sequence, map to a flag dict; otherwise keep empty
        try:
            caps_iter = list(caps_raw)  # type: ignore[arg-type]
            caps = {str(k): True for k in caps_iter}
        except Exception:
            caps = {}

    # Map a small set of openrouter- style fields from metadata when present
    data = {
        'provider': m.provider,
        'name': m.model_name,
        'capabilities': caps if isinstance(caps, (dict, list)) else {},
        'openrouter_context_length': meta.get('openrouter_context_length') or meta.get('context_length') or m.context_window,
        'openrouter_prompt_price': meta.get('openrouter_prompt_price') or meta.get('input_price_per_1k'),
        'openrouter_completion_price': meta.get('openrouter_completion_price') or meta.get('output_price_per_1k'),
        'openrouter_pricing_request': meta.get('openrouter_pricing_request'),
        'openrouter_pricing_image': meta.get('openrouter_pricing_image'),
        'openrouter_pricing_web_search': meta.get('openrouter_pricing_web_search'),
        'openrouter_pricing_internal_reasoning': meta.get('openrouter_pricing_internal_reasoning'),
        'openrouter_pricing_input_cache_read': meta.get('openrouter_pricing_input_cache_read'),
        'openrouter_pricing_input_cache_write': meta.get('openrouter_pricing_input_cache_write'),
        'architecture_modality': meta.get('architecture_modality'),
        'architecture_input_modalities': meta.get('architecture_input_modalities'),
        'architecture_output_modalities': meta.get('architecture_output_modalities'),
        'architecture_tokenizer': meta.get('architecture_tokenizer'),
        'architecture_instruct_type': meta.get('architecture_instruct_type'),
        'performance_score': meta.get('performance_score') or m.cost_efficiency,
    }
    return data

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

@models_bp.route('/')
def models_index():
    """Legacy models index → redirect to main models overview page."""
    from flask import redirect, url_for
    return redirect(url_for('main.models_overview'))

@models_bp.route('/models_overview')
def models_overview():
    """Compatibility endpoint name used by some templates; delegate to main."""
    from flask import redirect, url_for
    return redirect(url_for('main.models_overview'))


@models_bp.route('/application/<model_slug>/<int:app_number>')
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

@models_bp.route('/applications/generate', methods=['POST'])
def generate_application():
    """HTMX endpoint: Generate a new application record."""
    try:
        from app.services import application_service as app_service
        from flask import Response

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

        detail_url = f"{request.url_root.rstrip('/')}/models/application/{model_slug}/{app_number}"
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

@models_bp.route('/application/<model_slug>/<int:app_number>/section/overview')
def application_section_overview(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'overview')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/prompts')
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

@models_bp.route('/application/<model_slug>/<int:app_number>/section/files')
def application_section_files(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'files')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/ports')
def application_section_ports(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'ports')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/container')
def application_section_container(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'container')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/analyses')
def application_section_analyses(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'analyses')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/metadata')
def application_section_metadata(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'metadata')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/artifacts')
def application_section_artifacts(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'artifacts')

@models_bp.route('/application/<model_slug>/<int:app_number>/section/logs')
def application_section_logs(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'logs')

@models_bp.route('/application/<model_slug>/<int:app_number>/generation-metadata')
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

@models_bp.route('/application/<model_slug>/<int:app_number>/file')
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

@models_bp.route('/application/<model_slug>/<int:app_number>/logs/modal')
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

@models_bp.route('/model_actions/<model_slug>')
@models_bp.route('/model_actions')
def model_actions(model_slug=None):
    """HTMX endpoint for model actions modal content."""
    try:
        if model_slug:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

            app_count = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
            security_count = db.session.query(SecurityAnalysis).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()
            performance_count = db.session.query(PerformanceTest).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()

            return render_template(
                'pages/models/partials/model_actions.html',
                model=model,
                stats={
                    'applications': app_count,
                    'security_tests': security_count,
                    'performance_tests': performance_count
                }
            )
        else:
            # Bulk operations modal (legacy path expected 'partials/bulk_operations.html')
            # Updated to new canonical location under pages/applications/partials
            return render_template('pages/applications/partials/bulk_operations.html')

    except Exception as e:
        current_app.logger.error(f"Error loading model actions for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error loading model actions: {str(e)}</div>'

@models_bp.route('/application/<model_slug>/<int:app_number>/diagnostics/ports')
def application_ports_diagnostics(model_slug, app_number):
    """Lightweight preformatted diagnostics for port resolution attempts."""
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

@models_bp.route('/model_apps/<model_slug>')
def model_apps(model_slug):
    """View applications for a specific model."""
    try:
        # Route now serves as a compatibility alias. Redirect to Applications page
        # with model filter applied so the UI reflects the requested model.
        _ = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        from flask import redirect, url_for
        return redirect(url_for('main.applications_index', model=model_slug))
    except Exception as e:
        current_app.logger.error(f"Error loading model apps for {model_slug}: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Model Applications Error',
            error_message=str(e),
            python_version='3.11'
        )

@models_bp.route('/import')
def models_import_page():
    """Render a simple import page to upload JSON and call the API."""
    try:
        return render_template('pages/models/import.html')
    except Exception as e:
        current_app.logger.error(f"Error rendering models import page: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Import Page Error',
            error_message=str(e)
        ), 500

@models_bp.route('/export/models.csv')
def export_models_csv():
    """Export models overview to CSV with selected fields."""
    try:
        models = ModelCapability.query.order_by(
            ModelCapability.provider, ModelCapability.model_name
        ).all()
        rows = []
        for m in models:
            data = _enrich_model(m)
            cached = ExternalModelInfoCache.query.filter_by(model_slug=m.canonical_slug).first()
            if cached:
                try:
                    data = deep_merge_dicts(data, cached.get_data())
                except Exception:  # pragma: no cover
                    pass
            rows.append({
                'provider': m.provider,
                'model_name': m.model_name,
                'slug': m.canonical_slug,
                'context_window': data.get('openrouter_context_length') or m.context_window,
                'prompt_price': data.get('openrouter_prompt_price'),
                'completion_price': data.get('openrouter_completion_price'),
                'pricing_request': data.get('openrouter_pricing_request'),
                'pricing_image': data.get('openrouter_pricing_image'),
                'pricing_web_search': data.get('openrouter_pricing_web_search'),
                'pricing_internal_reasoning': data.get('openrouter_pricing_internal_reasoning'),
                'pricing_input_cache_read': data.get('openrouter_pricing_input_cache_read'),
                'pricing_input_cache_write': data.get('openrouter_pricing_input_cache_write'),
                'modality': data.get('architecture_modality'),
                'input_modalities': '|'.join(data.get('architecture_input_modalities') or []) if isinstance(data.get('architecture_input_modalities'), list) else data.get('architecture_input_modalities'),
                'output_modalities': '|'.join(data.get('architecture_output_modalities') or []) if isinstance(data.get('architecture_output_modalities'), list) else data.get('architecture_output_modalities'),
                'tokenizer': data.get('architecture_tokenizer'),
                'instruct_type': data.get('architecture_instruct_type'),
                'supported_parameters': '|'.join(data.get('openrouter_supported_parameters') or []) if isinstance(data.get('openrouter_supported_parameters'), list) else data.get('openrouter_supported_parameters'),
                'is_free': m.is_free,
            })

        csv_content = dicts_to_csv(rows)
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=models_export.csv'}
        )
    except Exception as e:  # pragma: no cover - export failures rare
        current_app.logger.error(f"Error exporting models CSV: {e}")
        return Response('provider,model_name,slug\n', mimetype='text/csv')

@models_bp.route('/filter')
def models_filter():
    """HTMX endpoint: Return filtered models grid for dynamic updates."""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '').strip()
        capabilities = request.args.get('capabilities', '').strip()
        pricing = request.args.get('pricing', '').strip()
        sort = request.args.get('sort', 'name')

        # Base query
        query = ModelCapability.query

        # Apply filters
        if provider:
            query = query.filter(ModelCapability.provider.ilike(f'%{provider}%'))

        if search:
            query = query.filter(
                or_(
                    ModelCapability.model_name.ilike(f'%{search}%'),
                    ModelCapability.provider.ilike(f'%{search}%'),
                    ModelCapability.canonical_slug.ilike(f'%{search}%')
                )
            )

        if pricing:
            if pricing == 'free':
                query = query.filter(ModelCapability.is_free)
            elif pricing == 'paid':
                query = query.filter(~ModelCapability.is_free)

        # Apply sorting
        if sort == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort == 'cost':
            # Sort by pricing (this is approximate since pricing comes from OpenRouter)
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        else:  # name
            query = query.order_by(ModelCapability.model_name)

        models = query.all()

        # Enrich models with OpenRouter data and filter by capabilities
        enriched_models = []
        for model in models:
            enriched_data = _enrich_model(model)
            app_count = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).count()
            enriched_data['apps_count'] = app_count

            # Filter by capabilities if specified
            if capabilities:
                model_caps = enriched_data.get('capabilities', {})
                cap_supported = False

                if capabilities == 'text' and model_caps.get('text'):
                    cap_supported = True
                elif capabilities == 'vision' and (model_caps.get('vision') or model_caps.get('images')):
                    cap_supported = True
                elif capabilities == 'multimodal' and model_caps.get('multimodal'):
                    cap_supported = True
                elif capabilities == 'function_calling' and model_caps.get('function_calling'):
                    cap_supported = True
                elif capabilities == 'streaming' and model_caps.get('streaming'):
                    cap_supported = True

                if not cap_supported:
                    continue

            enriched_models.append(enriched_data)

        # Return just the models grid
        return render_template('pages/models/partials/models-grid.html', models=enriched_models)

    except Exception as e:
        current_app.logger.error(f"Error filtering models: {e}")
        return f'<div class="alert alert-danger">Error filtering models: {str(e)}</div>', 500

@models_bp.route('/comparison')
def models_comparison():
    """Render comparison page with optional selected models list."""
    try:
        raw = request.args.get('models', '')
        slugs = [s.strip() for s in raw.split(',') if s.strip()][:6]  # limit to 6 for layout
        selected_models = []
        comparison_rows = []
        capability_union: set[str] = set()
        pricing = []
        if slugs:
            for slug in slugs:
                m = ModelCapability.query.filter_by(canonical_slug=slug).first()
                if not m:
                    continue
                data = _enrich_model(m)
                caps = data.get('capabilities') or {}
                # normalize capability keys
                if isinstance(caps, dict):
                    for k, v in caps.items():
                        if v:
                            capability_union.add(k)
                # Normalize price fields to float (original sources may be strings like '0.0012')
                def _to_float(v):
                    try:
                        if v is None or v == '':
                            return 0.0
                        return float(v)
                    except Exception:
                        return 0.0
                selected_models.append({
                    'slug': slug,
                    'name': data.get('name') or m.model_name,
                    'provider': data.get('provider') or m.provider,
                    'context_length': data.get('openrouter_context_length') or m.context_window,
                    'input_price': _to_float(data.get('openrouter_prompt_price') or data.get('input_price_per_1k')),
                    'output_price': _to_float(data.get('openrouter_completion_price') or data.get('output_price_per_1k')),
                    'performance_score': data.get('performance_score'),
                    'capabilities': caps,
                })
            # Pricing delta baseline (first model)
            if selected_models:
                base = selected_models[0]
                b_in = float(base.get('input_price') or 0) or 0.0
                b_out = float(base.get('output_price') or 0) or 0.0
                for sm in selected_models:
                    in_p = float(sm.get('input_price') or 0) or 0.0
                    out_p = float(sm.get('output_price') or 0) or 0.0
                    pricing.append({
                        'slug': sm['slug'],
                        'name': sm['name'],
                        'input_price': in_p,
                        'output_price': out_p,
                        'input_delta': (in_p - b_in) if b_in else None,
                        'output_delta': (out_p - b_out) if b_out else None,
                    })
            # Capability matrix
            capability_list = sorted(capability_union)
            for cap in capability_list:
                row = {'capability': cap, 'support': []}
                for sm in selected_models:
                    caps = sm.get('capabilities') or {}
                    val = False
                    if isinstance(caps, dict):
                        val = bool(caps.get(cap))
                    elif isinstance(caps, list):
                        val = cap in caps
                    row['support'].append(val)
                comparison_rows.append(row)
        return render_template(
            'pages/models/comparison.html',
            models=selected_models,
            pricing=pricing,
            capability_rows=comparison_rows,
            selected_models=slugs,
        )
    except Exception as e:
        current_app.logger.error(f"Error building comparison page: {e}")
        flash('Error building comparison', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Comparison Error',
            error_message=str(e)
        ), 500

# Model details routes (placed at end to avoid conflicts with static routes)
@models_bp.route('/<model_slug>')
def model_details(model_slug):
    """Detailed view of a specific model."""
    try:
        context = build_model_detail_context(model_slug, enrich_model=_enrich_model)
        return render_template('pages/models/model_details.html', **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error loading model details for %s: %s", model_slug, exc)
        flash(f"Error loading model details: {exc}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=404,
            error_title='Model Not Found',
            error_message=f"Model '{model_slug}' not found"
        )

@models_bp.route('/detail/<model_slug>/section/<section>')
def model_section(model_slug, section):
    """Render specific sections of model details page (HTMX)."""
    try:
        context = build_model_detail_context(model_slug, enrich_model=_enrich_model)
        section_cfg = context.get('sections_map', {}).get(section)
        if not section_cfg:
            return f'<div class="alert alert-warning">Unknown section: {section}</div>', 404
        return render_template(section_cfg['template'], **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error rendering model section %s for %s: %s", section, model_slug, exc)
        return f'<div class="alert alert-danger">Failed to load {section}: {exc}</div>', 500