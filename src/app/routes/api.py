"""
API Routes
=========

RESTful API endpoints for external integrations.
"""

import logging

from flask import Blueprint, jsonify, render_template

from ..models import ModelCapability, GeneratedApplication
from ..services.task_manager import TaskManager
from ..services.analyzer_integration import AnalyzerIntegration

# Set up logger
logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

# Initialize services
task_manager = TaskManager()
analyzer_integration = AnalyzerIntegration()


@api_bp.route('/models')
def api_models():
    """API endpoint: Get all models."""
    try:
        models = ModelCapability.query.all()
        return jsonify([{
            'model_slug': model.model_slug,
            'provider': model.provider,
            'model_name': model.model_name,
            'capabilities': model.capabilities
        } for model in models])
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/<model_slug>/apps')
def api_model_apps(model_slug):
    """API endpoint: Get applications for a model."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        return jsonify([{
            'app_id': app.id,
            'app_number': app.app_number,
            'model_slug': app.model_slug,
            'provider': app.provider,
            'created_at': app.created_at.isoformat() if app.created_at else None
        } for app in apps])
    except Exception as e:
        logger.error(f"Error getting apps for model {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/stats_total_models')
def stats_total_models():
    """API endpoint: Get total models count."""
    from ..models import ModelCapability
    from ..extensions import db
    
    try:
        count = db.session.query(ModelCapability).count()
        return {'count': count}
    except Exception as e:
        logger.error(f"Error getting total models: {e}")
        return {'count': 0}


@api_bp.route('/stats_models_trend')
def stats_models_trend():
    """API endpoint: Get models trend (for dashboard)."""
    try:
        # For now, return a simple trend indicator
        # In the future, this could calculate actual growth trends
        return '+3 this week'
    except Exception as e:
        logger.error(f"Error getting models trend: {e}")
        return '+0'


@api_bp.route('/quick_search', methods=['POST'])
def quick_search():
    """HTMX endpoint for quick search functionality."""
    # TODO: Implement quick search
    return render_template('partials/search_results.html', results=[])


@api_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    from ..models import ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest
    from ..extensions import db
    
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        return render_template('partials/sidebar_stats.html', stats=stats)
    except Exception as e:
        logger.error(f"Error getting sidebar stats: {e}")
        return render_template('partials/sidebar_stats.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })


@api_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
    from ..models import SecurityAnalysis, PerformanceTest, BatchAnalysis
    from ..extensions import db
    from sqlalchemy import desc
    from datetime import datetime, timezone
    
    try:
        # Get recent activities (last 10 items)
        recent_security = db.session.query(SecurityAnalysis).order_by(desc(SecurityAnalysis.started_at)).limit(5).all()
        recent_performance = db.session.query(PerformanceTest).order_by(desc(PerformanceTest.started_at)).limit(5).all()
        recent_batch = db.session.query(BatchAnalysis).order_by(desc(BatchAnalysis.created_at)).limit(5).all()
        
        activities = []
        
        # Add security activities
        for analysis in recent_security:
            if analysis.started_at:
                activities.append({
                    'type': 'security',
                    'description': 'Security analysis completed',
                    'timestamp': analysis.started_at,
                    'status': analysis.status.value if analysis.status else 'unknown'
                })
        
        # Add performance activities  
        for test in recent_performance:
            if test.started_at:
                activities.append({
                    'type': 'performance',
                    'description': 'Performance test completed',
                    'timestamp': test.started_at,
                    'status': test.status.value if test.status else 'unknown'
                })
        
        # Add batch activities
        for batch in recent_batch:
            if batch.created_at:
                activities.append({
                    'type': 'batch',
                    'description': f'Batch analysis #{batch.id}',
                    'timestamp': batch.created_at,
                    'status': batch.status.value if batch.status else 'unknown'
                })
        
        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        activities = activities[:10]  # Keep only the 10 most recent
        
        return render_template('partials/activity_timeline.html', activities=activities)
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        return render_template('partials/activity_timeline.html', activities=[])


@api_bp.route('/system_health')
def system_health():
    """HTMX endpoint for system health status."""
    from ..extensions import get_components
    from sqlalchemy import text
    from ..extensions import db
    
    try:
        # Check database status
        try:
            db.session.execute(text('SELECT 1'))
            db_status = {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            db_status = {'status': 'error', 'message': str(e)}
        
        # Check Celery status
        try:
            components = get_components()
            celery_instance = components.celery if components else None
            if celery_instance:
                celery_inspect = celery_instance.control.inspect()
                active_tasks = celery_inspect.active()
                celery_status = {'status': 'healthy', 'message': 'Running'} if active_tasks is not None else {'status': 'error', 'message': 'Not responding'}
            else:
                celery_status = {'status': 'warning', 'message': 'Not available'}
        except Exception as e:
            celery_status = {'status': 'error', 'message': str(e)}
        
        # Check analyzer status
        try:
            components = get_components()
            analyzer_integration = components.analyzer_integration if components else None
            if analyzer_integration and hasattr(analyzer_integration, 'health_check'):
                analyzer_health = analyzer_integration.health_check()
                analyzer_status = {'status': analyzer_health.get('status', 'unknown'), 'message': analyzer_health.get('message', 'Unknown status')}
            else:
                analyzer_status = {'status': 'warning', 'message': 'Not available'}
        except Exception as e:
            analyzer_status = {'status': 'error', 'message': str(e)}
        
        system_status = {
            'database': db_status,
            'celery': celery_status,
            'analyzer': analyzer_status
        }
        
        return render_template('partials/system_status.html', system_status=system_status)
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        return render_template('partials/system_status.html', system_status={
            'database': {'status': 'error', 'message': 'Health check failed'},
            'celery': {'status': 'error', 'message': 'Health check failed'},
            'analyzer': {'status': 'error', 'message': 'Health check failed'}
        })
