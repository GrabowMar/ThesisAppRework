"""
Main Routes
==========

Core application routes including dashboard and basic pages.
"""

import logging

from flask import Blueprint, render_template, flash, request

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
            'dashboard.html',
            stats=stats,
            recent_apps=recent_apps,
            recent_analyses=recent_analyses,
            running_batches=running_batches
        )
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        flash('Error loading dashboard', 'error')
        return render_template('error.html', error=str(e))


@main_bp.route('/health')
def health_check():
    """Health check endpoint for monitoring."""
    return {'status': 'healthy', 'version': '2.0.0'}, 200


@main_bp.route('/about')
def about():
    """About page with project information."""
    return render_template('pages/about.html')


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
        
        batch_stats = {
            'total': total_batches,
            'running': running_batches,
            'completed': completed_batches,
            'failed': failed_batches
        }
        
        batches = BatchAnalysis.query.order_by(
            BatchAnalysis.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template(
            'batch_overview.html',
            batches=batches,
            batch_stats=batch_stats
        )
    except Exception as e:
        logger.error(f"Error loading batch overview: {e}")
        flash('Error loading batch overview', 'error')
        return render_template('error.html', error=str(e))


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
