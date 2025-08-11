"""
Main Routes
==========

Core application routes including dashboard and basic pages.
"""

import logging

from flask import Blueprint, render_template, flash, request, current_app

from ..models import (
    ModelCapability, GeneratedApplication,
    SecurityAnalysis, PerformanceTest,
    BatchAnalysis, ContainerizedTest
)
from ..constants import JobStatus, ContainerState
from ..extensions import db

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
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Dashboard Error',
                             error_message=str(e),
                             error=str(e),
                             timestamp=datetime.now().isoformat(),
                             request_id='dashboard-error',
                             python_version=sys.version,
                             flask_version=getattr(flask, '__version__', 'unknown'),
                             debug_mode=current_app.debug,
                             environment=current_app.config.get('ENV', 'unknown'))


@main_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return {'status': 'healthy', 'version': '2.0.0'}, 200


@main_bp.route('/about')
def about():
    """About page with project information."""
    return render_template('pages/about.html')


@main_bp.route('/statistics')
def statistics():
    """Statistics overview page."""
    try:
        # Get statistical data
        stats = {
            'total_tests': SecurityAnalysis.query.count() + PerformanceTest.query.count(),
            'passed_tests': SecurityAnalysis.query.filter_by(status='completed').count(),
            'failed_tests': SecurityAnalysis.query.filter_by(status='failed').count(),
            'avg_duration': '4.2s',  # TODO: Calculate actual average
            'success_rate': '87.3%',  # TODO: Calculate actual rate
            'active_models': ModelCapability.query.count()
        }
        return render_template('pages/statistics_overview.html', stats=stats)
    except Exception as e:
        logger.error(f"Error loading statistics: {e}")
        flash('Error loading statistics', 'error')
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Statistics Error',
                             error_message=str(e))


@main_bp.route('/testing')
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
        
        return render_template('pages/testing.html', 
                             stats=stats, 
                             available_models=available_models,
                             active_sessions=active_sessions,
                             recent_results=recent_results)
    except Exception as e:
        logger.error(f"Error loading testing page: {e}")
        flash('Error loading testing page', 'error')
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Testing Page Error',
                             error_message=str(e))


@main_bp.route('/models_overview')
def models_overview():
    """Redirect to models overview page."""
    from flask import redirect, url_for
    return redirect(url_for('models.models_overview'))


@main_bp.route('/batch')
def batch_overview():
    """Batch analysis overview page."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Get batch statistics
        total_batches = BatchAnalysis.query.count()
        running_batches = BatchAnalysis.query.filter_by(status=JobStatus.RUNNING).count()
        completed_batches = BatchAnalysis.query.filter_by(status=JobStatus.COMPLETED).count()
        failed_batches = BatchAnalysis.query.filter_by(status=JobStatus.FAILED).count()
        
        stats = {
            'total_batches': total_batches,
            'running_batches': running_batches,
            'completed_batches': completed_batches,
            'failed_batches': failed_batches
        }
        
        # Get active and recent batches
        active_batches = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_([JobStatus.RUNNING, JobStatus.PENDING])
        ).order_by(BatchAnalysis.created_at.desc()).all()
        
        recent_batches = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_([JobStatus.COMPLETED, JobStatus.FAILED])
        ).order_by(BatchAnalysis.created_at.desc()).limit(10).all()
        
        # Get available models for new batch creation
        available_models = ModelCapability.query.all()
        
        return render_template(
            'pages/batch_overview.html',
            stats=stats,
            active_batches=active_batches,
            recent_batches=recent_batches,
            available_models=available_models
        )
    except Exception as e:
        logger.error(f"Error loading batch overview: {e}")
        flash('Error loading batch overview', 'error')
        return render_template('pages/error.html', 
                             error_code=500,
                             error_title='Batch Overview Error',
                             error_message=str(e))


@main_bp.route('/batch/list')
def batch_list():
    """HTMX endpoint for batch list."""
    try:
        status_filter = request.args.get('status')
        
        query = BatchAnalysis.query
        if status_filter:
            query = query.filter_by(status=status_filter)
        
        batches = query.order_by(
            BatchAnalysis.created_at.desc()
        ).limit(10).all()
        
        return render_template('partials/batch_list.html', batches=batches)
    except Exception as e:
        logger.error(f"Error loading batch list: {e}")
        return f'<div class="alert alert-danger">Error loading batch list: {str(e)}</div>'


@main_bp.route('/batch/form')
def batch_form():
    """HTMX endpoint for batch form."""
    try:
        models = ModelCapability.query.all()
        return render_template('partials/batch_form.html', models=models)
    except Exception as e:
        logger.error(f"Error loading batch form: {e}")
        return f'<div class="alert alert-danger">Error loading batch form: {str(e)}</div>'


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
