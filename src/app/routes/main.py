"""
Main Routes
==========

Core application routes including dashboard and basic pages.
"""

import logging

from flask import Blueprint, render_template, flash, current_app

from ..models import (
    ModelCapability, GeneratedApplication,
    SecurityAnalysis, PerformanceTest,
    BatchAnalysis, ContainerizedTest
)
from ..constants import JobStatus, ContainerState

# Set up logger
logger = logging.getLogger(__name__)

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
            status=JobStatus.RUNNING
        ).all()
        
        # Use new page wrapper template (pages/dashboard.html)
        return render_template(
            'pages/dashboard.html',
            stats=stats,
            recent_apps=recent_apps,
            recent_analyses=recent_analyses,
            running_batches=running_batches
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash('Error loading dashboard', 'error')
        from datetime import datetime
        import sys
        import flask
        return render_template(
            'single_page.html',
            page_title='Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Dashboard Error',
            error_message=str(e),
            error=str(e),
            timestamp=datetime.now().isoformat(),
            request_id='dashboard-error',
            python_version=sys.version,
            flask_version=getattr(flask, '__version__', 'unknown'),
            debug_mode=current_app.debug,
            environment=current_app.config.get('ENV', 'unknown')
        )


@main_bp.route('/about')
def about():
    """About page with project information."""
    return render_template('pages/about.html')


@main_bp.route('/system-status')
def system_status():
    """System status / runtime health page (wrapper template)."""
    try:
        # Light-weight stats for status panel (reuse subset of dashboard)
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_scans': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count()
        }
        return render_template('pages/system_status.html', stats=stats)
    except Exception as e:
        logger.error(f"Error loading system status: {e}")
        flash('Error loading system status', 'error')
        return render_template(
            'single_page.html',
            page_title='System Status Error',
            main_partial='partials/common/error.html',
            error_message=str(e)
        )


@main_bp.route('/test-platform')
def testing():
    """Testing platform overview page."""
    try:
        # Get testing statistics
        stats = {
            'active_tests': SecurityAnalysis.query.filter_by(status=JobStatus.RUNNING).count() +
                           PerformanceTest.query.filter_by(status=JobStatus.RUNNING).count(),
            'completed_tests': SecurityAnalysis.query.filter_by(status=JobStatus.COMPLETED).count() +
                              PerformanceTest.query.filter_by(status=JobStatus.COMPLETED).count(),
            'failed_tests': SecurityAnalysis.query.filter_by(status=JobStatus.FAILED).count() +
                           PerformanceTest.query.filter_by(status=JobStatus.FAILED).count(),
            'queue_length': SecurityAnalysis.query.filter_by(status=JobStatus.PENDING).count() +
                           PerformanceTest.query.filter_by(status=JobStatus.PENDING).count()
        }
        
        # Get available models for testing
        available_models = ModelCapability.query.all()
        
        # Get active sessions (mock data for now)
        active_sessions = []
        
        # Get recent results
        recent_results = []
        
        return render_template(
            'single_page.html',
            page_title='Testing Platform',
            page_icon='fas fa-flask',
            page_subtitle='System testing and validation',
            main_partial='partials/testing/platform_overview.html',
            stats=stats,
            available_models=available_models,
            active_sessions=active_sessions,
            recent_results=recent_results
        )
    except Exception as e:
        logger.error(f"Error loading testing page: {e}")
        flash('Error loading testing page', 'error')
        return render_template(
            'single_page.html',
            page_title='Error',
            main_partial='partials/common/error.html',
            error_code=500,
            error_title='Testing Page Error',
            error_message=str(e)
        )


@main_bp.route('/models_overview')
def models_overview():
    """Redirect to models overview page."""
    from flask import redirect, url_for
    return redirect(url_for('models.models_overview'))


@main_bp.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics."""
    try:
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_analyses': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count(),
            'batch_jobs': BatchAnalysis.query.count(),
            'active_containers': ContainerizedTest.query.filter_by(
                status=ContainerState.RUNNING.value
            ).count()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting API stats: {e}")
        return {'error': str(e)}, 500
