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
    """Primary Applications page - delegate to models blueprint."""
    try:
        # Quick sync if no apps found
        if GeneratedApplication.query.count() == 0:
            from app.services.model_sync_service import sync_models_from_filesystem
            sync_models_from_filesystem()
    except Exception:
        current_app.logger.warning("Auto filesystem sync failed", exc_info=True)
    
    # Delegate to models blueprint
    from app.routes.jinja.models import _render_applications_page
    return _render_applications_page()

@main_bp.route('/applications/generate', methods=['POST'])
def applications_generate():
    """Delegate application generation to models blueprint."""
    from app.routes.jinja.models import generate_application
    return generate_application()

@main_bp.route('/applications/table')
def applications_table():
    """HTMX partial: Applications table - delegate to models blueprint."""
    # Simple redirect to the existing applications page functionality
    return redirect(url_for('models.model_apps'))

@main_bp.route('/applications/stats')
def applications_stats():
    """HTMX partial: Applications stats - delegate to models blueprint."""
    return redirect(url_for('models.model_apps'))

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

# ---------------------------------------------------------------------------
# Advanced features (consolidated from advanced.py)
# ---------------------------------------------------------------------------

@main_bp.route('/advanced/apps')
def advanced_apps_grid():
    """Advanced apps grid page."""
    return render_template(
        'views/applications/index.html',
        page_title='Applications Grid'
    )

@main_bp.route('/advanced/models')
def advanced_models_overview():
    """Advanced models overview page."""
    return render_template(
        'pages/models/overview.html',
        page_title='Models Overview'
    )

@main_bp.route('/tasks')
def tasks_overview_redirect():
    """Deprecated tasks route - redirect to main dashboard live tasks section."""
    return redirect(url_for('main.dashboard') + '#live-tasks')