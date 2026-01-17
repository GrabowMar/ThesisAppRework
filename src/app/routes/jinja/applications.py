"""
Applications routes for the Flask application
=============================================="""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, request, Response, redirect, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from flask import render_template
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
    # Load template catalog for enriching apps with template metadata
    from app.services.service_locator import ServiceLocator
    try:
        gen_service = ServiceLocator.get_generation_service()
        template_catalog = gen_service.get_template_catalog() if gen_service else []
        template_map = {t['slug']: t for t in template_catalog}
    except Exception:
        template_catalog = []
        template_map = {}
    
    # Filter & table state parameters
    model_filter_raw = (request.args.get('model') or '').strip()
    # Accept comma-separated slugs
    model_filter_list = [m.strip() for m in model_filter_raw.split(',') if m.strip()]
    provider_filter = (request.args.get('provider') or '').strip()
    search_filter = (request.args.get('search') or '').strip()
    status_filter_raw = (request.args.get('status') or '').strip()  # comma-aware
    status_filters = [s.strip().lower() for s in status_filter_raw.split(',') if s.strip()]
    template_filter = (request.args.get('template') or '').strip()  # Changed from type_filter
    ports_filter = (request.args.get('ports') or '').strip()
    analysis_filter = (request.args.get('analysis') or '').strip()
    # Enhanced sorting: support column name + direction
    sort_column = request.args.get('sort', 'model_slug')
    sort_direction = request.args.get('dir', 'asc').lower()
    sort_field = request.args.get('sort', 'model')  # Legacy compatibility: model|provider|model_desc|provider_desc
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
    # Enhanced sorting at DB level
    # Map frontend column names to database fields
    column_map = {
        'model_slug': GeneratedApplication.model_slug,
        'provider': GeneratedApplication.provider,
        'app_number': GeneratedApplication.app_number,
        'template_slug': GeneratedApplication.template_slug,
        'container_status': GeneratedApplication.container_status,
        'created_at': GeneratedApplication.created_at
    }
    
    # Apply sorting if valid column specified
    if sort_column in column_map:
        sort_attr = column_map[sort_column]
        if sort_direction == 'desc':
            q = q.order_by(sort_attr.desc())
        else:
            q = q.order_by(sort_attr.asc())
    # Legacy sort_field support
    elif sort_field.startswith('provider'):
        q = q.order_by(GeneratedApplication.provider.asc(), GeneratedApplication.model_slug.asc(), GeneratedApplication.app_number.asc())
    else:
        q = q.order_by(GeneratedApplication.model_slug.asc(), GeneratedApplication.app_number.asc())

    # Fetch rows once; for typical sizes this is OK and enables status/ports filters
    rows = q.all()
    total_apps_overall = len(rows)

    # Skip expensive Docker checks by default for faster loading
    # Docker status will be fetched via HTMX/client-side if needed
    check_docker = request.args.get('check_docker', 'false').lower() == 'true'
    
    # Get Docker status cache for efficient lookups
    status_cache = None
    if check_docker:
        try:
            from app.services.service_locator import ServiceLocator
            status_cache = ServiceLocator.get_docker_status_cache()
        except Exception:
            status_cache = None

    def _resolve_status_fast(db_status_raw: str | None) -> str:
        """Fast status resolution using only database status."""
        db_status = (db_status_raw or '').strip().lower()
        if db_status in ('running', 'stopped', 'not_created', 'error', 'no_compose'):
            return db_status
        return db_status if db_status else 'unknown'

    def _project_name(model_slug: str, app_num: int) -> str:
        safe_model = (model_slug or '').replace('_', '-').replace('.', '-')
        return f"{safe_model}-app{app_num}"

    # Pre-fetch bulk status from cache if Docker checks are enabled
    bulk_status_map: dict[tuple[str, int], Any] = {}
    if check_docker and status_cache:
        try:
            apps_list = [(r.model_slug, r.app_number) for r in rows]
            bulk_status_map = status_cache.get_bulk_status(apps_list)
        except Exception as e:
            current_app.logger.warning(f"Failed to get bulk status from cache: {e}")

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
        
        # Determine status - use cache if Docker checks requested
        status_details = {}
        cache_key = (r.model_slug, r.app_number)
        
        if check_docker and cache_key in bulk_status_map:
            # Use cached Docker status
            cache_entry = bulk_status_map[cache_key]
            status = cache_entry.status
            status_details = cache_entry.to_dict() if hasattr(cache_entry, 'to_dict') else {}
        else:
            # Fast path: just use DB status (no Docker API calls)
            raw_db_status = r.container_status
            if not raw_db_status and getattr(r, 'generation_status', None):
                try:
                    raw_db_status = r.generation_status.value  # type: ignore[attr-defined]
                except Exception:
                    raw_db_status = str(r.generation_status)
            status = _resolve_status_fast(raw_db_status)
        
        if status == 'running':
            running_count += 1
        
        # Get template metadata from catalog
        template_info = template_map.get(r.template_slug, {})
        template_name = template_info.get('name', r.template_slug) if r.template_slug else None
        template_category = template_info.get('category', '') if r.template_slug else ''
        
        # Get failure tracking info
        is_generation_failed = getattr(r, 'is_generation_failed', False) or False
        failure_stage = getattr(r, 'failure_stage', None)
        error_message = getattr(r, 'error_message', None)
        
        # Override status to 'failed' if generation failed
        if is_generation_failed:
            status = 'generation_failed'
        
        # Get raw container status for template
        raw_container_status = getattr(r, 'container_status', None) or ''
        
        # Check for unhealthy containers:
        # 1. DB status is 'build_failed' (persisted when start/build fails)
        # 2. Or detected from Docker status_details
        is_container_unhealthy = False
        
        # Primary check: DB container_status field
        raw_status_lower = raw_container_status.lower() if raw_container_status else ''
        if raw_status_lower in ('build_failed', 'error', 'failed', 'unhealthy'):
            is_container_unhealthy = True
        
        # Secondary check: Docker status_details (when Docker checks are enabled)
        if not is_container_unhealthy and status_details:
            states = [s.lower() for s in status_details.get('states', []) if s]
            containers = status_details.get('containers', [])
            
            # Check if any container exited or is dead
            if any(s in ('exited', 'dead', 'error', 'failed') for s in states):
                is_container_unhealthy = True
            
            # Check for error in status_details
            if status_details.get('error'):
                is_container_unhealthy = True
            
            # Check containers for exit codes != 0 or unhealthy status
            for container in containers:
                c_status = (container.get('status') or '').lower()
                c_state = (container.get('State', {}) if isinstance(container.get('State'), dict) else {})
                exit_code = c_state.get('ExitCode', 0) if c_state else 0
                health = (container.get('health', '') or '').lower()
                
                if c_status in ('exited', 'dead', 'error'):
                    is_container_unhealthy = True
                if exit_code != 0:
                    is_container_unhealthy = True
                if health == 'unhealthy':
                    is_container_unhealthy = True
        
        # Also mark as unhealthy if status is 'stopped' but was never successfully running
        # (detected by having no live port bindings despite having port config)
        if status == 'stopped' and not is_container_unhealthy:
            # If there's status_details but status is stopped, containers likely crashed
            if status_details and status_details.get('compose_exists', False):
                states = [s.lower() for s in status_details.get('states', []) if s]
                if states and all(s != 'running' for s in states):
                    # All containers stopped - might be a failure
                    is_container_unhealthy = True
        
        applications_all.append({
            'model_slug': r.model_slug,
            'model_provider': model_provider,
            'model_display_name': display_name,
            'app_number': r.app_number,
            'status': status,
            'container_status': raw_container_status,
            'is_container_unhealthy': is_container_unhealthy,
            'id': r.id,
            'template_slug': r.template_slug,
            'template_name': template_name,
            'template_category': template_category,
            'generation_mode': r.generation_mode.value if r.generation_mode else 'guarded',
            'ports': derived_ports,
            'container_size': None,
            'analysis_status': 'none',
            'status_details': status_details,
            'created_at': r.created_at,
            # Generation failure tracking
            'is_generation_failed': is_generation_failed,
            'failure_stage': failure_stage,
            'error_message': error_message
        })

    # Apply in-memory filters that depend on enriched fields
    def _passes_status(a: dict) -> bool:
        if not status_filters:
            return True
        app_status = (a.get('status') or '').lower()
        # Special handling for build_failed filter
        if 'build_failed' in status_filters:
            if a.get('is_container_unhealthy') or a.get('container_status', '').lower() == 'build_failed':
                return True
        return app_status in status_filters
    def _passes_template(a: dict) -> bool:
        return (not template_filter) or (a.get('template_slug') == template_filter)
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

    filtered_apps = [a for a in applications_all if _passes_status(a) and _passes_template(a) and _passes_ports(a) and _passes_analysis(a)]

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
    
    # Get unique templates that have generated apps (for filter dropdown)
    available_templates = []
    used_template_slugs = sorted({r.template_slug for r in rows if r.template_slug})
    for slug in used_template_slugs:
        info = template_map.get(slug, {})
        available_templates.append({
            'slug': slug,
            'name': info.get('name', slug),
            'category': info.get('category', '')
        })

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
        'available_templates': available_templates,
        'stats': stats,
        'applications_stats': stats,
        'current_filters': {
            'model': model_filter_raw,
            'provider': provider_filter,
            'search': search_filter,
            'status': status_filter_raw,
            'template': template_filter,
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
        # Check if app is a failed generation - redirect to failure page
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        if app and app.is_generation_failed:
            return redirect(url_for('applications.application_failure', model_slug=model_slug, app_number=app_number))
        
        context = build_application_detail_context(model_slug, app_number, allow_synthetic=True)
        return render_template('pages/applications/applications_detail.html', **context)
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


@applications_bp.route('/<model_slug>/<int:app_number>/failure')
def application_failure(model_slug, app_number):
    """Failure detail view for a failed generation."""
    try:
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        
        if not app:
            flash(f"Application '{model_slug}/app{app_number}' not found.", "error")
            return redirect(url_for('applications.applications_index'))
        
        # If app is not actually failed, redirect to normal detail page
        if not app.is_generation_failed:
            return redirect(url_for('applications.application_detail', model_slug=model_slug, app_number=app_number))
        
        # Read error log file if it exists
        from pathlib import Path
        error_log_content = None
        app_dir = Path('generated') / 'apps' / model_slug / f'app{app_number}'
        error_log_path = app_dir / 'generation_error.txt'
        
        if error_log_path.exists():
            try:
                error_log_content = error_log_path.read_text(encoding='utf-8')
            except Exception as e:
                current_app.logger.warning(f"Failed to read error log: {e}")
                error_log_content = f"Error reading log file: {e}"
        
        # Get model info for display
        try:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            model_display_name = getattr(model, 'display_name', None) or getattr(model, 'model_name', None) or model_slug
            model_provider = getattr(model, 'provider', None) or app.provider or 'local'
        except Exception:
            model_display_name = model_slug
            model_provider = app.provider or 'local'
        
        context = {
            'app': app,
            'model_slug': model_slug,
            'app_number': app_number,
            'model_display_name': model_display_name,
            'model_provider': model_provider,
            'failure_stage': app.failure_stage,
            'error_message': app.error_message,
            'last_error_at': app.last_error_at,
            'generation_attempts': app.generation_attempts or 1,
            'error_log_content': error_log_content,
            'app_dir_exists': app_dir.exists(),
            'template_slug': app.template_slug,
            'created_at': app.created_at,
            'metadata': app.get_metadata() if hasattr(app, 'get_metadata') else {},
            'active_page': 'applications',
        }
        
        return render_template('pages/applications/applications_failure.html', **context)
        
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error loading failure details for %s/app%s: %s", model_slug, app_number, exc)
        flash(f"Error loading failure details: {exc}", "error")
        return redirect(url_for('applications.applications_index'))


@applications_bp.route('/generate', methods=['POST'])
def generate_application():
    """HTMX endpoint: Generate a new application with actual code generation.
    
    This endpoint now calls the full generation service which:
    1. Atomically reserves the next app number (prevents race conditions)
    2. Scaffolds Docker infrastructure
    3. Generates AI code for backend and frontend
    4. Creates the database record
    """
    try:
        from app.services.generation import get_generation_service
        from app.utils.async_utils import run_async_safely

        model_slug = (request.form.get('model_slug') or '').strip()
        # app_number is now OPTIONAL - service will auto-allocate atomically
        app_number_raw = request.form.get('app_number')
        template_slug = (request.form.get('template_slug') or 'crud_todo_list').strip()
        
        # Parse optional flags
        gen_frontend = request.form.get('generate_frontend', 'true').lower() != 'false'
        gen_backend = request.form.get('generate_backend', 'true').lower() != 'false'

        if not model_slug:
            return (
                '<div class="alert alert-danger">Model slug is required.</div>',
                400,
            )

        # Validate model exists
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return (
                f'<div class="alert alert-danger">Unknown model: {model_slug}</div>',
                404,
            )
        
        # Parse app_number if provided, otherwise let service auto-allocate
        app_number = None
        if app_number_raw:
            try:
                app_number = int(app_number_raw)
            except (ValueError, TypeError):
                # Invalid app_number provided - let service auto-allocate
                app_number = None

        # Generate unique batch ID
        import uuid
        from datetime import datetime
        batch_id = f"htmx_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        current_app.logger.info(
            f"HTMX generation request: {model_slug}/app{app_number or 'auto'}, template={template_slug}"
        )

        # Run actual generation (scaffolding + AI code generation)
        service = get_generation_service()
        result = run_async_safely(service.generate_full_app(
            model_slug=model_slug,
            app_num=app_number,  # None = auto-allocate atomically
            template_slug=template_slug,
            generate_frontend=gen_frontend,
            generate_backend=gen_backend,
            batch_id=batch_id,
            version=1
        ))

        if result.get('success'):
            allocated_app_num = result.get('app_number', app_number)
            detail_url = f"{request.url_root.rstrip('/')}/applications/{model_slug}/{allocated_app_num}"
            resp = Response(
                '<div class="alert alert-success">'
                f'Successfully generated application #{allocated_app_num} for <strong>{model_slug}</strong> '
                f'(<a href="{detail_url}" target="_blank">open details</a>).</div>'
            )
            resp.headers['HX-Trigger'] = 'refresh-grid'
            return resp
        else:
            errors = result.get('errors', ['Unknown error'])
            error_msg = '; '.join(errors) if errors else 'Generation failed'
            current_app.logger.error(f"Generation failed for {model_slug}: {error_msg}")
            return (
                f'<div class="alert alert-danger">Generation failed: {error_msg}</div>',
                500,
            )

    except Exception as e:
        msg = str(e)
        if 'already exists' in msg.lower() or ('unique' in msg.lower() and 'model' in msg.lower()):
            return (
                '<div class="alert alert-warning">An application with this configuration already exists.</div>',
                409,
            )
        current_app.logger.error(f"Error generating application: {e}", exc_info=True)
        return (
            f'<div class="alert alert-danger">Error generating application: {str(e)}</div>',
            500,
        )


@applications_bp.route('/<model_slug>/<int:app_number>/section/overview')
def application_section_overview(model_slug, app_number):
    return _render_application_section(model_slug, app_number, 'overview')


@applications_bp.route('/<model_slug>/<int:app_number>/section/prompts')
def application_section_prompts(model_slug, app_number):
    """Return the prompts section content for lazy loading via HTMX."""
    return _render_application_section(model_slug, app_number, 'prompts')


@applications_bp.route('/<model_slug>/<int:app_number>/prompts/modal')
def application_prompts_modal(model_slug, app_number):
    """Return the prompts modal for the legacy View Prompts button."""
    try:
        context = build_application_detail_context(model_slug, app_number, allow_synthetic=True)
        return render_template('pages/applications/partials/modals/_prompts_modal.html', **context)
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
        return f'''<div class="file-preview">
  <div class="file-preview-header"><span>{rel_path}</span></div>
  <pre>{escaped}</pre>
</div>'''
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


@applications_bp.route('/<model_slug>/<int:app_number>/logs/stream')
def application_logs_stream(model_slug, app_number):
    """Stream container logs for a specific container (backend/frontend)."""
    container = request.args.get('container', 'backend')
    lines = int(request.args.get('lines', 100))
    
    try:
        from app.services.docker_manager import DockerManager
        docker_mgr = DockerManager()
        logs = docker_mgr.get_container_logs(model_slug, app_number, container_type=container, tail=lines)
        return logs or f'No {container} logs available'
    except Exception as e:
        current_app.logger.error(f"Error streaming logs for {model_slug}/app{app_number}/{container}: {e}")
        return f'Error fetching logs: {e}'


@applications_bp.route('/<model_slug>/<int:app_number>/logs/filter')
def application_logs_filter(model_slug, app_number):
    """Filter container logs by level and search term."""
    container = request.args.get('container', 'backend')
    level = request.args.get('level', '').upper()
    search = request.args.get('search', '').lower()
    lines = int(request.args.get('lines', 100))
    
    try:
        from app.services.docker_manager import DockerManager
        docker_mgr = DockerManager()
        logs = docker_mgr.get_container_logs(model_slug, app_number, container_type=container, tail=lines)
        
        if not logs:
            return f'No {container} logs available'
        
        # Filter logs
        filtered_lines = []
        for line in logs.split('\n'):
            # Level filter
            if level and level not in line.upper():
                continue
            # Search filter  
            if search and search not in line.lower():
                continue
            filtered_lines.append(line)
        
        return '\n'.join(filtered_lines) if filtered_lines else 'No matching log entries'
    except Exception as e:
        current_app.logger.error(f"Error filtering logs for {model_slug}/app{app_number}/{container}: {e}")
        return f'Error filtering logs: {e}'


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
        return render_template('pages/applications/partials/_bulk_operations.html')
    except Exception as e:
        current_app.logger.error(f"Error loading bulk operations: {e}")
        return f'<div class="alert alert-danger">Error loading bulk operations: {str(e)}</div>'


# ==================== Developer Tools Section ====================

@applications_bp.route('/<model_slug>/<int:app_number>/section/tools')
def application_section_tools(model_slug, app_number):
    """Developer tools section with DB browser, env viewer, API tester, etc."""
    return _render_application_section(model_slug, app_number, 'tools')


def _collect_developer_tools_context(model_slug: str, app_number: int) -> dict:
    """Collect context data for developer tools section."""
    from pathlib import Path
    import json
    import sqlite3
    
    app_path = get_app_directory(model_slug, app_number)
    result = {
        'env_vars': {},
        'db_info': {'exists': False, 'path': None, 'tables': [], 'size_display': '0 B'},
        'backend_deps': [],
        'frontend_deps': [],
    }
    
    # Load .env file
    env_paths = [
        app_path / '.env',
        app_path / 'backend' / '.env',
    ]
    for env_path in env_paths:
        if env_path.exists():
            try:
                content = env_path.read_text(encoding='utf-8', errors='ignore')
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key:
                            result['env_vars'][key] = value
                break
            except Exception as e:
                current_app.logger.warning(f"Failed to read .env: {e}")
    
    # Find SQLite database
    db_paths = [
        app_path / 'backend' / 'app.db',
        app_path / 'backend' / 'data.db',
        app_path / 'backend' / 'database.db',
        app_path / 'backend' / 'instance' / 'app.db',
        app_path / 'backend' / 'instance' / 'data.db',
        app_path / 'app.db',
        app_path / 'data.db',
    ]
    for db_path in db_paths:
        if db_path.exists() and db_path.is_file():
            try:
                size = db_path.stat().st_size
                size_display = f"{size:,} B" if size < 1024 else f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"
                result['db_info'] = {
                    'exists': True,
                    'path': str(db_path.relative_to(app_path)),
                    'full_path': str(db_path),
                    'size': size,
                    'size_display': size_display,
                    'tables': [],
                }
                # Get table info
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
                tables = cursor.fetchall()
                for (table_name,) in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
                    row_count = cursor.fetchone()[0]
                    result['db_info']['tables'].append({
                        'name': table_name,
                        'row_count': row_count,
                    })
                conn.close()
                break
            except Exception as e:
                current_app.logger.warning(f"Failed to read database {db_path}: {e}")
    
    # Load backend dependencies (requirements.txt)
    req_paths = [
        app_path / 'backend' / 'requirements.txt',
        app_path / 'requirements.txt',
    ]
    for req_path in req_paths:
        if req_path.exists():
            try:
                content = req_path.read_text(encoding='utf-8', errors='ignore')
                for line in content.splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('-'):
                        # Parse package==version or package>=version etc.
                        for sep in ['==', '>=', '<=', '~=', '!=', '>',  '<']:
                            if sep in line:
                                name, version = line.split(sep, 1)
                                result['backend_deps'].append({'name': name.strip(), 'version': version.strip()})
                                break
                        else:
                            result['backend_deps'].append({'name': line, 'version': None})
                break
            except Exception as e:
                current_app.logger.warning(f"Failed to read requirements.txt: {e}")
    
    # Load frontend dependencies (package.json)
    pkg_paths = [
        app_path / 'frontend' / 'package.json',
        app_path / 'package.json',
    ]
    for pkg_path in pkg_paths:
        if pkg_path.exists():
            try:
                data = json.loads(pkg_path.read_text(encoding='utf-8'))
                deps = data.get('dependencies', {})
                for name, version in deps.items():
                    result['frontend_deps'].append({'name': name, 'version': version})
                break
            except Exception as e:
                current_app.logger.warning(f"Failed to read package.json: {e}")
    
    return result


@applications_bp.route('/<model_slug>/<int:app_number>/tools/env/edit')
def application_tools_env_edit(model_slug, app_number):
    """Return an editable form for .env variables."""
    from markupsafe import escape
    tools_ctx = _collect_developer_tools_context(model_slug, app_number)
    env_vars = tools_ctx.get('env_vars', {})
    
    if not env_vars:
        return '''
        <div class="alert alert-info small mb-2">
            <i class="fas fa-info-circle me-1"></i>No .env file exists yet
        </div>
        <form hx-post="/applications/{}/{}/tools/env/save" hx-target="#env-editor-container" hx-swap="innerHTML">
            <div class="mb-2">
                <textarea name="env_content" class="form-control form-control-sm font-monospace" rows="6" 
                    placeholder="KEY=value&#10;ANOTHER_KEY=another_value"></textarea>
            </div>
            <div class="d-flex gap-2">
                <button type="submit" class="btn btn-primary btn-sm">
                    <i class="fas fa-save me-1"></i>Save
                </button>
                <button type="button" class="btn btn-ghost-secondary btn-sm"
                        hx-get="/applications/{}/{}/section/tools"
                        hx-target="#section-tools"
                        hx-swap="innerHTML">
                    Cancel
                </button>
            </div>
        </form>
        '''.format(model_slug, app_number, model_slug, app_number)
    
    env_content = '\n'.join(f"{k}={v}" for k, v in env_vars.items())
    return f'''
    <form hx-post="/applications/{model_slug}/{app_number}/tools/env/save" hx-target="#env-editor-container" hx-swap="innerHTML">
        <div class="mb-2">
            <textarea name="env_content" class="form-control form-control-sm font-monospace" rows="6">{escape(env_content)}</textarea>
        </div>
        <div class="d-flex gap-2">
            <button type="submit" class="btn btn-primary btn-sm">
                <i class="fas fa-save me-1"></i>Save
            </button>
            <button type="button" class="btn btn-ghost-secondary btn-sm"
                    hx-get="/applications/{model_slug}/{app_number}/section/tools"
                    hx-target="#section-tools"
                    hx-swap="innerHTML">
                Cancel
            </button>
        </div>
    </form>
    '''


@applications_bp.route('/<model_slug>/<int:app_number>/tools/env/save', methods=['POST'])
def application_tools_env_save(model_slug, app_number):
    """Save .env file content."""
    from pathlib import Path
    app_path = get_app_directory(model_slug, app_number)
    env_content = request.form.get('env_content', '').strip()
    
    # Try to save to backend/.env first, then root .env
    env_paths = [
        app_path / 'backend' / '.env',
        app_path / '.env',
    ]
    
    saved = False
    for env_path in env_paths:
        if env_path.parent.exists():
            try:
                env_path.write_text(env_content, encoding='utf-8')
                saved = True
                break
            except Exception as e:
                current_app.logger.error(f"Failed to save .env to {env_path}: {e}")
    
    if saved:
        return '''
        <div class="alert alert-success small mb-2">
            <i class="fas fa-check me-1"></i>Environment variables saved successfully
        </div>
        <script>setTimeout(() => htmx.ajax('GET', '/applications/{}/{}/section/tools', {{target: '#section-tools', swap: 'innerHTML'}}), 1500);</script>
        '''.format(model_slug, app_number)
    else:
        return '<div class="alert alert-danger small">Failed to save .env file</div>', 500


@applications_bp.route('/<model_slug>/<int:app_number>/tools/env/create', methods=['POST'])
def application_tools_env_create(model_slug, app_number):
    """Create a new .env file."""
    return application_tools_env_edit(model_slug, app_number)


@applications_bp.route('/<model_slug>/<int:app_number>/tools/db/table')
def application_tools_db_table(model_slug, app_number):
    """Return table preview with data rows."""
    import sqlite3
    from markupsafe import escape
    
    table_name = request.args.get('db-table-select', '').strip()
    if not table_name:
        return '<div class="text-muted small">Select a table</div>'
    
    tools_ctx = _collect_developer_tools_context(model_slug, app_number)
    db_info = tools_ctx.get('db_info', {})
    
    if not db_info.get('exists') or not db_info.get('full_path'):
        return '<div class="alert alert-warning small">Database not found</div>'
    
    try:
        conn = sqlite3.connect(db_info['full_path'])
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get column names
        cursor.execute(f"PRAGMA table_info([{table_name}])")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Get first 20 rows
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT 20")
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return f'''
            <div class="text-center text-muted small py-2">
                <i class="fas fa-inbox me-1"></i>Table "{escape(table_name)}" is empty
            </div>
            <div class="small text-muted">Columns: {", ".join(escape(c) for c in columns)}</div>
            '''
        
        # Build HTML table
        html = ['<div class="table-responsive"><table class="table table-sm table-striped table-hover mb-0">']
        html.append('<thead><tr>')
        for col in columns[:8]:  # Limit columns shown
            html.append(f'<th class="small text-muted">{escape(col)}</th>')
        if len(columns) > 8:
            html.append('<th class="small text-muted">...</th>')
        html.append('</tr></thead><tbody>')
        
        for row in rows:
            html.append('<tr>')
            for i, col in enumerate(columns[:8]):
                value = row[i]
                if value is None:
                    display = '<span class="text-muted">NULL</span>'
                elif isinstance(value, (bytes,)):
                    display = '<span class="text-muted">[BLOB]</span>'
                else:
                    str_val = str(value)
                    display = escape(str_val[:50] + '...' if len(str_val) > 50 else str_val)
                html.append(f'<td class="small">{display}</td>')
            if len(columns) > 8:
                html.append('<td class="small text-muted">...</td>')
            html.append('</tr>')
        
        html.append('</tbody></table></div>')
        
        # Add row count info
        total_rows = next((t['row_count'] for t in db_info['tables'] if t['name'] == table_name), len(rows))
        html.append(f'<div class="small text-muted mt-1">Showing {len(rows)} of {total_rows} rows</div>')
        
        return ''.join(html)
        
    except Exception as e:
        current_app.logger.error(f"Error querying table {table_name}: {e}")
        return f'<div class="alert alert-danger small">Error: {escape(str(e))}</div>'


@applications_bp.route('/<model_slug>/<int:app_number>/tools/deps/backend')
def application_tools_deps_backend(model_slug, app_number):
    """Return backend dependencies list."""
    from markupsafe import escape
    tools_ctx = _collect_developer_tools_context(model_slug, app_number)
    deps = tools_ctx.get('backend_deps', [])
    
    if not deps:
        return '''
        <div class="text-center text-muted py-3">
            <i class="fas fa-box-open fa-2x mb-2 opacity-50"></i>
            <p class="mb-0 small">No requirements.txt found</p>
        </div>
        '''
    
    html = ['<table class="table table-sm table-vcenter mb-0"><thead><tr>']
    html.append('<th class="small text-muted">Package</th>')
    html.append('<th class="small text-muted text-end">Version</th>')
    html.append('</tr></thead><tbody>')
    
    for dep in deps:
        html.append(f'''<tr>
            <td><code class="small">{escape(dep["name"])}</code></td>
            <td class="text-end"><span class="badge bg-secondary-lt">{escape(dep["version"] or "latest")}</span></td>
        </tr>''')
    
    html.append('</tbody></table>')
    return ''.join(html)


@applications_bp.route('/<model_slug>/<int:app_number>/tools/deps/frontend')
def application_tools_deps_frontend(model_slug, app_number):
    """Return frontend dependencies list."""
    from markupsafe import escape
    tools_ctx = _collect_developer_tools_context(model_slug, app_number)
    deps = tools_ctx.get('frontend_deps', [])
    
    if not deps:
        return '''
        <div class="text-center text-muted py-3">
            <i class="fas fa-box-open fa-2x mb-2 opacity-50"></i>
            <p class="mb-0 small">No package.json found</p>
        </div>
        '''
    
    html = ['<table class="table table-sm table-vcenter mb-0"><thead><tr>']
    html.append('<th class="small text-muted">Package</th>')
    html.append('<th class="small text-muted text-end">Version</th>')
    html.append('</tr></thead><tbody>')
    
    for dep in deps:
        html.append(f'''<tr>
            <td><code class="small">{escape(dep["name"])}</code></td>
            <td class="text-end"><span class="badge bg-info-lt">{escape(dep["version"] or "latest")}</span></td>
        </tr>''')
    
    html.append('</tbody></table>')
    return ''.join(html)


@applications_bp.route('/<model_slug>/<int:app_number>/tools/api/test', methods=['POST'])
def application_tools_api_test(model_slug, app_number):
    """Test an API endpoint on the running application."""
    import requests
    import json
    from markupsafe import escape
    from app.utils.port_resolution import resolve_ports
    
    method = request.form.get('method', 'GET').upper()
    endpoint = request.form.get('endpoint', '/').strip()
    body = request.form.get('body', '').strip()
    
    # Resolve backend port
    ports = resolve_ports(model_slug, app_number)
    if not ports or not ports.get('backend'):
        return '<div class="alert alert-warning small"><i class="fas fa-exclamation-triangle me-1"></i>Could not resolve backend port</div>'
    
    backend_port = ports['backend']
    url = f"http://localhost:{backend_port}{endpoint}"
    
    try:
        # Parse body as JSON if provided
        json_body = None
        if body:
            try:
                json_body = json.loads(body)
            except json.JSONDecodeError:
                return '<div class="alert alert-danger small"><i class="fas fa-times me-1"></i>Invalid JSON body</div>'
        
        # Make request
        start_time = __import__('time').time()
        if method == 'GET':
            resp = requests.get(url, timeout=10)
        elif method == 'POST':
            resp = requests.post(url, json=json_body, timeout=10)
        elif method == 'PUT':
            resp = requests.put(url, json=json_body, timeout=10)
        elif method == 'DELETE':
            resp = requests.delete(url, timeout=10)
        elif method == 'PATCH':
            resp = requests.patch(url, json=json_body, timeout=10)
        else:
            return '<div class="alert alert-warning small">Unsupported method</div>'
        
        elapsed = (__import__('time').time() - start_time) * 1000
        
        # Format response
        status_class = 'success' if 200 <= resp.status_code < 300 else 'warning' if 300 <= resp.status_code < 400 else 'danger'
        
        try:
            resp_json = resp.json()
            resp_body = json.dumps(resp_json, indent=2)
        except Exception:
            resp_body = resp.text[:2000]
        
        return f'''
        <div class="mb-1">
            <span class="badge bg-{status_class}">{resp.status_code}</span>
            <span class="small text-muted ms-2">{elapsed:.0f}ms</span>
            <code class="small ms-2">{escape(url)}</code>
        </div>
        <pre class="bg-dark text-light rounded p-2 small mb-0" style="max-height: 150px; overflow: auto;">{escape(resp_body)}</pre>
        '''
        
    except requests.exceptions.ConnectionError:
        return '<div class="alert alert-danger small"><i class="fas fa-plug me-1"></i>Connection refused - is the container running?</div>'
    except requests.exceptions.Timeout:
        return '<div class="alert alert-warning small"><i class="fas fa-clock me-1"></i>Request timed out</div>'
    except Exception as e:
        return f'<div class="alert alert-danger small"><i class="fas fa-times me-1"></i>Error: {escape(str(e))}</div>'


@applications_bp.route('/<model_slug>/<int:app_number>/tools/cmd/<cmd>', methods=['POST'])
def application_tools_cmd(model_slug, app_number, cmd):
    """Execute a quick command in the container."""
    import subprocess
    from markupsafe import escape
    
    # Map command shortcuts to actual commands
    # Format: cmd -> (container_type, shell_cmd, fallback_cmd_or_None)
    cmd_map = {
        'pip-list': ('backend', 'pip list --format=columns', None),
        'npm-list': ('frontend', 
                     'npm list --depth=0 2>/dev/null || (cat /app/package.json 2>/dev/null | head -50) || echo "npm not available (production container)"',
                     None),
        'health': ('backend', 'curl -s http://localhost:5000/api/health || wget -qO- http://localhost:5000/api/health || echo "Health endpoint not responding"', None),
        'routes': ('backend', 'flask routes 2>/dev/null || python -c "from app import app; print(app.url_map)" 2>/dev/null || echo "Could not list routes"', None),
        'ps': ('backend', 'ps aux --sort=-%mem 2>/dev/null | head -10 || ps aux | head -10 || echo "ps command not available"', None),
        'env': ('backend', 'env | sort | head -30', None),
        'disk': ('backend', 'df -h 2>/dev/null || echo "df not available"', None),
    }
    
    if cmd not in cmd_map:
        return f'<span class="text-danger">Unknown command: {escape(cmd)}</span>'
    
    container_type, shell_cmd, _ = cmd_map[cmd]
    
    # Build container name - Docker Compose uses format: {project_name}_{service}
    # Project name: model slug with underscores/dots replaced by hyphens + -app{N}
    safe_model = model_slug.replace('_', '-').replace('.', '-')
    project_name = f"{safe_model}-app{app_number}"
    container_name = f"{project_name}_{container_type}"
    
    try:
        result = subprocess.run(
            ['docker', 'exec', container_name, 'sh', '-c', shell_cmd],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = result.stdout.strip() if result.stdout else ''
        stderr = result.stderr.strip() if result.stderr else ''
        
        if not output and not stderr:
            output = 'No output'
        elif not output and stderr:
            # Some commands output to stderr
            output = stderr
            stderr = ''
        
        # Format output
        cmd_display = shell_cmd.split('||')[0].strip()  # Show just the primary command
        if result.returncode != 0 and stderr and 'not found' in stderr.lower():
            return f'<span class="text-muted">$ {escape(cmd_display)}</span>\n<span class="text-warning">{escape(output or stderr)}</span>'
        elif result.returncode != 0 and stderr:
            return f'<span class="text-warning">$ {escape(cmd_display)}</span>\n{escape(output)}\n<span class="text-danger">{escape(stderr)}</span>'
        return f'<span class="text-success">$ {escape(cmd_display)}</span>\n{escape(output)}'
    except subprocess.TimeoutExpired:
        return '<span class="text-warning">Command timed out after 30s</span>'
    except FileNotFoundError:
        return '<span class="text-danger">Docker not found. Is Docker installed?</span>'
    except Exception as e:
        return f'<span class="text-danger">Error: {escape(str(e))}</span>'


@applications_bp.route('/<model_slug>/<int:app_number>/tools/structure')
def application_tools_structure(model_slug, app_number):
    """Return project directory structure as a tree."""
    from pathlib import Path
    from markupsafe import escape
    
    app_path = get_app_directory(model_slug, app_number)
    
    if not app_path.exists():
        return '<span class="text-warning">Application directory not found</span>'
    
    def build_tree(path: Path, prefix: str = '', max_depth: int = 3, current_depth: int = 0) -> list:
        if current_depth >= max_depth:
            return []
        
        lines = []
        try:
            items = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            items = [i for i in items if not i.name.startswith('.') and i.name not in ('node_modules', '__pycache__', '.git', 'venv', '.venv')]
            
            for i, item in enumerate(items[:30]):  # Limit items
                is_last = i == len(items) - 1 or i == 29
                connector = '└── ' if is_last else '├── '
                
                if item.is_dir():
                    lines.append(f'{prefix}{connector}<span class="text-info">{escape(item.name)}/</span>')
                    extension = '    ' if is_last else '│   '
                    lines.extend(build_tree(item, prefix + extension, max_depth, current_depth + 1))
                else:
                    size = item.stat().st_size
                    size_str = f'{size}B' if size < 1024 else f'{size//1024}K'
                    lines.append(f'{prefix}{connector}<span class="text-light">{escape(item.name)}</span> <span class="text-muted">({size_str})</span>')
            
            if len(items) > 30:
                lines.append(f'{prefix}... and {len(items) - 30} more items')
                
        except PermissionError:
            lines.append(f'{prefix}[Permission denied]')
        
        return lines
    
    tree_lines = [f'<span class="text-primary">{escape(app_path.name)}/</span>']
    tree_lines.extend(build_tree(app_path))
    
    return '\n'.join(tree_lines)
