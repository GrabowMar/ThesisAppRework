"""
Main routes for the Flask application
=====================================

Dashboard and core web routes that render Jinja templates.
"""

from flask import Blueprint, flash, current_app, redirect, url_for

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
            'partials/common/error.html',
            error=str(e),
            page_title='Dashboard Error'
        ), 500

@main_bp.route('/about')
def about():
    """About page with project information."""
    return render_template('pages/about/about_main.html')

@main_bp.route('/spa/dashboard')
def spa_dashboard():
    """SPA: Dashboard inner content."""
    try:
        return render_template('spa/dashboard_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA dashboard: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500

@main_bp.route('/spa/analysis')
def spa_analysis():
    """SPA: Analysis hub inner content."""
    try:
        return render_template('spa/analysis_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA analysis: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500

@main_bp.route('/spa/models')
def spa_models():
    """SPA: Models overview inner content."""
    try:
        return render_template('spa/models_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA models: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500

@main_bp.route('/spa/applications')
def spa_applications():
    """SPA: Applications overview inner content."""
    try:
        return render_template('spa/applications_content.html')
    except Exception as e:
        current_app.logger.error(f"Error loading SPA applications: {e}")
        return render_template('partials/common/error.html', error=str(e)), 500

@main_bp.route('/system-status')
def system_status():
    """System status / runtime health page."""
    try:
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_scans': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count()
        }
        return render_template('views/system/status.html', stats=stats)
    except Exception as e:
        current_app.logger.error(f"Error loading system status: {e}")
        flash('Error loading system status', 'error')
        return render_template(
            'partials/common/error.html',
            error=str(e),
            page_title='System Status Error'
        ), 500

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
            'partials/common/error.html',
            error=str(e),
            page_title='Testing Page Error'
        ), 500

@main_bp.route('/models_overview')
def models_overview():
    """Redirect to models overview page."""
    return redirect(url_for('models.models_overview'))