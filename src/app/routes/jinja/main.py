"""
Main routes for the Flask application
=====================================

Dashboard and core web routes that render Jinja templates.
"""

from flask import Blueprint, flash, current_app, redirect, url_for
from app.utils.generated_apps import generated_apps_stats

from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest,
    ContainerizedTest, BatchAnalysis
)
from app.constants import ContainerState
from app.utils.template_paths import render_template_compat as render_template

# Create blueprint
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def dashboard():
    """Main dashboard page."""
    try:
        # Get overview statistics
        stats = {
            'total_models': ModelCapability.query.count(),
            'total_applications': GeneratedApplication.query.count(),
            'total_security_analyses': SecurityAnalysis.query.count(),
            'total_performance_tests': PerformanceTest.query.count(),
            'active_containers': ContainerizedTest.query.filter_by(
                status=ContainerState.RUNNING.value
            ).count()
        }
        if stats['total_applications'] == 0:
            fs = generated_apps_stats()
            stats['total_applications_fs'] = fs.get('total_apps', 0)
            stats['total_models_fs'] = fs.get('total_models', 0)

        # Get recent activities
        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()

        recent_analyses = SecurityAnalysis.query.order_by(
            SecurityAnalysis.created_at.desc()
        ).limit(5).all()

        # Get running batch jobs
        running_batches = BatchAnalysis.query.filter_by(
            status='running'
        ).all()

        return render_template(
            'pages/index/index_main.html',
            stats=stats,
            recent_apps=recent_apps,
            recent_analyses=recent_analyses,
            running_batches=running_batches
        )
    except Exception as e:
        current_app.logger.error(f"Error loading dashboard: {e}")
        flash('Error loading dashboard', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e),
            page_title='Dashboard Error'
        ), 500

@main_bp.route('/about')
def about():
    """About page - redirects to docs since about content is now consolidated there."""
    return redirect(url_for('docs.docs_index'))

@main_bp.route('/spa/dashboard')
def spa_dashboard():
    """SPA: Dashboard inner content."""
    try:
        return render_template('spa/dashboard_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA dashboard: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500

@main_bp.route('/spa/analysis')
def spa_analysis():
    """SPA: Analysis hub inner content."""
    try:
        return render_template('spa/analysis_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA analysis: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500

@main_bp.route('/spa/models')
def spa_models():
    """SPA: Models overview inner content."""
    try:
        return render_template('spa/models_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA models: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500

@main_bp.route('/spa/applications')
def spa_applications():
    """SPA: Applications overview inner content."""
    try:
        return render_template('spa/applications_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA applications: {e}")
        return render_template('pages/errors/errors_main.html', error=str(e)), 500

@main_bp.route('/system-status')
def system_status():
    """Deprecated: redirect to dashboard where system stats now live."""
    from flask import redirect, url_for
    return redirect(url_for('main.dashboard'))

@main_bp.route('/test-platform')
def testing():
    """Legacy testing platform route -> redirect to Analysis Hub."""
    try:
        flash('Testing has moved to Analysis Hub.', 'info')
        return redirect(url_for('analysis.analysis_dashboard'))
    except Exception as e:
        current_app.logger.error(f"Error redirecting testing page: {e}")
        flash('Error loading testing page', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e),
            page_title='Testing Page Error'
        ), 500

@main_bp.route('/models_overview')
def models_overview():
    """Redirect to models overview page."""
    return redirect(url_for('models.models_overview'))

@main_bp.route('/applications')
def applications_index():
    """Primary Applications page (clean URL). Delegates to legacy models blueprint implementation."""
    try:
        # If no applications (and likely empty models/apps tables), perform a quick
        # idempotent filesystem sync so the grid can display existing folders.
        try:
            if GeneratedApplication.query.count() == 0:
                from app.services.model_sync_service import sync_models_from_filesystem  # type: ignore
                sync_models_from_filesystem()
        except Exception:  # pragma: no cover - non-fatal
            current_app.logger.warning("Auto filesystem sync on /applications failed", exc_info=True)
        # Import internal render helper directly
        from app.routes.jinja.models import _render_applications_page  # type: ignore
        return _render_applications_page()
    except Exception as e:  # pragma: no cover - defensive
        current_app.logger.error(f"Error loading applications page: {e}")
        flash('Error loading applications page', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e),
            page_title='Applications Error'
        ), 500

@main_bp.route('/applications/generate', methods=['POST'])
def applications_generate():
    """Delegate application generation to existing models blueprint route for cleaner URL."""
    try:
        from app.routes.jinja.models import generate_application  # type: ignore
        return generate_application()
    except Exception as e:  # pragma: no cover - defensive
        current_app.logger.error(f"Error generating application via /applications/generate: {e}")
        return (
            '<div class="alert alert-danger">Error generating application.</div>',
            500,
        )

@main_bp.route('/applications/table')
def applications_table():
    """HTMX partial: Applications table with current filters."""
    try:
        # Real (lightweight) pagination + filtering implementation for the applications table
        from flask import request
        from app.routes.jinja.models import db, GeneratedApplication, PortConfiguration, SimplePagination, ModelCapability  # type: ignore
        search = (request.args.get('search') or '').strip().lower()
        # Multi-select filters come in as comma-separated lists
        model_filter_raw = (request.args.get('model') or '').strip().lower()
        model_filters = [m for m in model_filter_raw.split(',') if m]
        provider_filter = (request.args.get('provider') or '').strip().lower()
        status_filter_raw = (request.args.get('status') or '').strip().lower()
        status_filters = [s for s in status_filter_raw.split(',') if s]
        page = max(1, int(request.args.get('page', 1) or 1))
        per_page = min(100, max(5, int(request.args.get('per_page', 25) or 25)))

        query = GeneratedApplication.query
        if model_filters:
            if len(model_filters) == 1:
                query = query.filter(GeneratedApplication.model_slug == model_filters[0])
            else:
                query = query.filter(GeneratedApplication.model_slug.in_(model_filters))
        if provider_filter:
            query = query.filter(GeneratedApplication.provider.ilike(f"%{provider_filter}%"))
        if status_filters:
            if len(status_filters) == 1:
                query = query.filter(GeneratedApplication.container_status == status_filters[0])
            else:
                query = query.filter(GeneratedApplication.container_status.in_(status_filters))
        if search:
            like = f"%{search}%"
            from sqlalchemy import or_
            query = query.filter(or_(
                GeneratedApplication.model_slug.ilike(like),
                GeneratedApplication.provider.ilike(like),
                GeneratedApplication.app_type.ilike(like)
            ))

        total = query.count()
        # Ordering: model then app number for determinism
        page_items = (query
                       .order_by(GeneratedApplication.model_slug.asc(), GeneratedApplication.app_number.asc())
                       .offset((page - 1) * per_page)
                       .limit(per_page)
                       .all())

        # Preload port configurations for the page set only
        app_keys = [(a.model_slug, a.app_number) for a in page_items]
        ports_map: dict[tuple[str,int], dict] = {}
        if app_keys:
            pcs = (db.session.query(PortConfiguration)
                   .filter(PortConfiguration.model.in_([k[0] for k in app_keys]))
                   .all())
            for pc in pcs:
                ports_map[(pc.model, pc.app_num)] = {
                    'backend': pc.backend_port,
                    'frontend': pc.frontend_port
                }

        # Fetch model metadata for provider/display name enrichment (single query)
        models_map = {}
        try:
            model_slugs = {a.model_slug for a in page_items}
            if model_slugs:
                rows = db.session.query(ModelCapability).filter(ModelCapability.canonical_slug.in_(model_slugs)).all()
                for m in rows:
                    models_map[m.canonical_slug] = m
        except Exception:
            pass

        applications_list = []
        for app in page_items:
            ports_cfg = ports_map.get((app.model_slug, app.app_number)) or {}
            # Represent ports as a list for template compatibility
            ports_list = []
            if ports_cfg.get('backend'):
                ports_list.append({'host_port': ports_cfg['backend'], 'role': 'backend'})
            if ports_cfg.get('frontend') and ports_cfg.get('frontend') != ports_cfg.get('backend'):
                ports_list.append({'host_port': ports_cfg['frontend'], 'role': 'frontend'})

            model_meta = models_map.get(app.model_slug)
            applications_list.append({
                'id': app.id,
                'model_slug': app.model_slug,
                'model_provider': getattr(app, 'provider', None) or getattr(model_meta, 'provider', 'local'),
                'model_display_name': getattr(model_meta, 'display_name', None) or app.model_slug,
                'app_number': app.app_number,
                'app_type': app.app_type or 'web_app',
                'status': app.container_status or 'unknown',
                'ports': ports_list,
                'container_size': None,  # Placeholder; could be populated by a metrics service
                'analysis_status': None  # Placeholder; real aggregation can be added later
            })

        pagination = SimplePagination(page, per_page, total, applications_list)

        # Always return wrapped section so HTMX swaps keep a stable target
        return render_template(
            'pages/applications/partials/table_block.html',
            applications=applications_list,
            total_applications=total,
            pagination=pagination
        )
    except Exception as e:  # pragma: no cover - defensive
        current_app.logger.error(f"Error loading applications table: {e}")
        return (
            '<div class="alert alert-danger">Error loading applications table.</div>',
            500,
        )

@main_bp.route('/applications/stats')
def applications_stats():
    """HTMX partial: refreshed mini stats numbers for Applications sidebar."""
    try:
        from app.routes.jinja.models import db, GeneratedApplication, SecurityAnalysis  # type: ignore
        total_apps = GeneratedApplication.query.count()
        running = GeneratedApplication.query.filter_by(container_status='running').count()
        try:
            analyzed = db.session.query(SecurityAnalysis).count()
        except Exception:
            analyzed = 0
        try:
            from sqlalchemy import func
            unique_models = db.session.query(func.count(func.distinct(GeneratedApplication.model_slug))).scalar() or 0
        except Exception:
            unique_models = 0
        return render_template('pages/applications/partials/_stats_numbers.html',
                               total_applications=total_apps,
                               running_applications=running,
                               analyzed_applications=analyzed,
                               unique_models=unique_models)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading applications stats: {e}")
        # Return safe fallback blank list
        return '<ul class="list-unstyled mb-0 d-flex flex-wrap gap-2 small"></ul>'

@main_bp.route('/applications/<model_slug>/<int:app_number>')
def applications_detail_alias(model_slug, app_number):
    """Alias route matching new applications URL scheme that delegates to legacy models blueprint detail renderer."""
    try:
        from app.routes.jinja.models import application_detail  # type: ignore
        return application_detail(model_slug, app_number)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading application detail alias: {e}")
        return ('<div class="alert alert-danger">Failed to load application detail.</div>', 500)

@main_bp.route('/applications/<model_slug>/<int:app_number>/section/<section>')
def applications_detail_section_alias(model_slug, app_number, section):
    """Alias for HTMX section endpoints using /applications path instead of /models/application."""
    try:
        from app.routes.jinja.models import _render_application_section  # type: ignore
        return _render_application_section(model_slug, app_number, section)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading application section alias: {e}")
        return f'<div class="alert alert-danger">Failed to load section: {section}</div>', 500