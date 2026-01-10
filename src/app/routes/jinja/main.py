"""
Main routes for the Flask application
=====================================

Dashboard and core web routes that render Jinja templates.
"""

from flask import Blueprint, flash, current_app, redirect, url_for, request, jsonify
from flask_login import login_required, current_user
from app.models import ModelCapability, GeneratedApplication
from app.utils.template_paths import render_template_compat as render_template
from app.routes.shared_utils import _norm_caps

# Create blueprint
main_bp = Blueprint('main', __name__)

# Require authentication for ALL routes
@main_bp.before_request
def require_authentication():
    """Require authentication for all main blueprint endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access this page.', 'info')
        return redirect(url_for('auth.login', next=request.url))

@main_bp.route('/')
@login_required
def dashboard():
    """Main dashboard page."""
    try:
        return render_template(
            'pages/index/index_main.html',
            page_title='Operations Dashboard',
            active_page='dashboard'
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


@main_bp.route('/system-status')
def system_status():
    """Deprecated: redirect to dashboard where system stats now live."""
    from flask import redirect, url_for
    return redirect(url_for('main.dashboard'))

@main_bp.route('/api-access')
@login_required
def api_access():
    """API Access and token management page."""
    return render_template(
        'pages/api_access/api_access_main.html',
        page_title='API Access',
        active_page='api-access'
    )

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
    """Models overview page (render directly to avoid redirect loops)."""
    try:
        models = ModelCapability.query.all()
        provider_options = sorted({(getattr(m, 'provider', '') or '').strip() for m in models if (getattr(m, 'provider', '') or '').strip()})
        capability_options = set()
        for model in models:
            try:
                caps_payload = model.get_capabilities() if hasattr(model, 'get_capabilities') else None
            except Exception:
                caps_payload = None
            if isinstance(caps_payload, dict) and 'capabilities' in caps_payload:
                caps_payload = caps_payload.get('capabilities')
            for cap in _norm_caps(caps_payload):
                if cap:
                    capability_options.add(cap)

        total_models = len(models)
        avg_cost_sum = 0.0
        for model in models:
            try:
                price_token = float(getattr(model, 'input_price_per_token', 0.0) or 0.0)
            except Exception:
                price_token = 0.0
            avg_cost_sum += price_token * 1000.0
        avg_cost = (avg_cost_sum / total_models) if total_models else 0.0
        models_stats = {
            'total_models': total_models,
            'active_models': total_models,
            'unique_providers': len(provider_options),
            'avg_cost_per_1k': round(avg_cost, 6),
        }
        return render_template(
            'pages/models/models_main.html',
            page_title='Models Overview',
            provider_options=provider_options,
            capability_options=sorted(capability_options),
            models_stats=models_stats
        )
    except Exception as e:
        current_app.logger.error(f"Error loading models overview: {e}")
        flash('Error loading models overview', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error=str(e),
            page_title='Models Overview Error'
        ), 500

@main_bp.route('/applications')
def applications_index():
    """Primary Applications page - delegate to models blueprint."""
    try:
        # Quick sync if no apps found
        if GeneratedApplication.query.count() == 0:
            from app.services.model_sync_service import sync_models_from_filesystem
            sync_models_from_filesystem()
    except Exception:
        current_app.logger.warning("Auto filesystem sync failed", exc_info=True)
    
    # Delegate to applications blueprint
    from app.routes.jinja.applications import _render_applications_page
    return _render_applications_page()

@main_bp.route('/applications/generate', methods=['POST'])
def applications_generate():
    """Delegate application generation to applications blueprint."""
    from app.routes.jinja.applications import generate_application
    return generate_application()

@main_bp.route('/applications/table')
def applications_table():
    """HTMX partial: Applications table content."""
    try:
        # Build the same context as the full applications page
        from app.routes.jinja.applications import build_applications_context  # type: ignore
        context = build_applications_context()
        # Return only the table block so HX swap can replace the section
        html = render_template('pages/applications/partials/_table_block.html', **context)
        # Add an identifying header so we can confirm in Network panel this is the partial
        from flask import make_response
        resp = make_response(html)
        resp.headers['X-Partial'] = 'applications-table'
        return resp
    except Exception as e:
        current_app.logger.error(f"Error rendering applications table: {e}")
        return ('<div class="alert alert-danger">Failed to load applications table.</div>', 500)

@main_bp.route('/applications/stats')
def applications_stats():
    """HTMX partial: Applications stats numbers snippet."""
    try:
        from app.routes.jinja.applications import build_applications_context  # type: ignore
        ctx = build_applications_context()
        stats = ctx.get('applications_stats') or ctx.get('stats') or {}
        html = render_template(
            'pages/applications/partials/_stats_numbers.html',
            total_applications=stats.get('total_applications', 0),
            running_applications=stats.get('running_applications', 0),
            analyzed_applications=stats.get('analyzed_applications', 0),
            unique_models=stats.get('unique_models', 0)
        )
        from flask import make_response
        resp = make_response(html)
        resp.headers['X-Partial'] = 'applications-stats'
        return resp
    except Exception as e:
        current_app.logger.error(f"Error rendering applications stats: {e}")
        return ('<ul class="list-unstyled small"><li class="text-danger">Failed to load stats</li></ul>', 500)

@main_bp.route('/applications/<model_slug>/<int:app_number>')
def applications_detail_alias(model_slug, app_number):
    """Alias route matching new applications URL scheme that delegates to applications blueprint detail renderer."""
    try:
        from app.routes.jinja.applications import application_detail  # type: ignore
        return application_detail(model_slug, app_number)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading application detail alias: {e}")
        return ('<div class="alert alert-danger">Failed to load application detail.</div>', 500)

@main_bp.route('/applications/<model_slug>/<int:app_number>/section/<section>')
def applications_detail_section_alias(model_slug, app_number, section):
    """Alias for HTMX section endpoints using /applications path instead of /models/application."""
    try:
        from app.routes.jinja.applications import _render_application_section  # type: ignore
        return _render_application_section(model_slug, app_number, section)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading application section alias: {e}")
        return f'<div class="alert alert-danger">Failed to load section: {section}</div>', 500

@main_bp.route('/applications/<model_slug>/<int:app_number>/prompts/modal')
def applications_prompts_modal_alias(model_slug, app_number):
    """Alias for prompts modal endpoint using /applications path."""
    try:
        from app.routes.jinja.applications import application_section_prompts  # type: ignore
        return application_section_prompts(model_slug, app_number)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading prompts modal alias: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/applications/<model_slug>/<int:app_number>/file')
def applications_file_alias(model_slug, app_number):
    """Alias for file preview endpoint using /applications path."""
    try:
        from app.routes.jinja.applications import application_file_preview  # type: ignore
        return application_file_preview(model_slug, app_number)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading application file alias: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/applications/<model_slug>/<int:app_number>/generation-metadata')
def applications_generation_metadata_alias(model_slug, app_number):
    """Alias for generation metadata endpoint using /applications path."""
    try:
        from app.routes.jinja.applications import application_generation_metadata  # type: ignore
        return application_generation_metadata(model_slug, app_number)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error loading generation metadata alias: {e}")
        from flask import jsonify
        return jsonify({'error': str(e)}), 500

# ---------------------------------------------------------------------------
# Advanced features (consolidated from advanced.py)
# ---------------------------------------------------------------------------

@main_bp.route('/advanced/apps')
def advanced_apps_grid():
    """Advanced apps grid page."""
    return render_template(
        'pages/applications/applications_main.html',
        page_title='Applications Grid'
    )

@main_bp.route('/advanced/models')
def advanced_models_overview():
    """Advanced models overview page."""
    return render_template(
        'pages/models/models_main.html',
        page_title='Models Overview'
    )

@main_bp.route('/tasks')
def tasks_overview_redirect():
    """Deprecated tasks route - redirect to main dashboard live tasks section."""
    return redirect(url_for('main.dashboard') + '#live-tasks')