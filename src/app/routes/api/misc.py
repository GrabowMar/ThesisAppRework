"""
Miscellaneous API Routes
=======================

API endpoints for HTMX, background tasks, notifications, and other utilities.
"""

import logging
from flask import jsonify, request, render_template

from . import api_bp
from ...models import GeneratedApplication, SecurityAnalysis, PerformanceTest
from ...extensions import db

# Set up logger
logger = logging.getLogger(__name__)


# =================================================================
# HTMX ENDPOINTS
# =================================================================

@api_bp.route('/quick_search', methods=['POST'])
def quick_search():
    """Quick search functionality for HTMX."""
    try:
        query = request.form.get('query', '').strip()
        
        if not query:
            return render_template('components/search_results.html', results=[], query='')
        
        # Search across models and applications
        from ...models import ModelCapability
        
        # Search models
        model_results = ModelCapability.query.filter(
            ModelCapability.model_name.ilike(f'%{query}%') |
            ModelCapability.provider.ilike(f'%{query}%') |
            ModelCapability.canonical_slug.ilike(f'%{query}%')
        ).limit(5).all()
        
        # Search applications
        app_results = GeneratedApplication.query.filter(
            GeneratedApplication.model_slug.ilike(f'%{query}%') |
            GeneratedApplication.app_type.ilike(f'%{query}%') |
            GeneratedApplication.provider.ilike(f'%{query}%')
        ).limit(5).all()
        
        results = {
            'models': [{
                'type': 'model',
                'name': model.model_name,
                'provider': model.provider,
                'slug': model.canonical_slug,
                'url': f'/models/{model.canonical_slug}'
            } for model in model_results],
            'applications': [{
                'type': 'application',
                'name': f'{app.model_slug} App #{app.app_number}',
                'provider': app.provider,
                'status': app.container_status,
                'url': f'/applications/{app.id}'
            } for app in app_results]
        }
        
        return render_template('components/search_results.html', 
                             results=results, query=query)
    except Exception as e:
        logger.error(f"Error in quick search: {e}")
        return f"<div class='alert alert-danger'>Search error: {str(e)}</div>"


# =================================================================
# BACKGROUND TASKS ENDPOINTS
# =================================================================

@api_bp.route('/tasks/status')
def tasks_status():
    """Get overall task status."""
    try:
        # For now, return a simple status
        # In production, this would interface with task queue (Celery, etc.)
        status = {
            'active_tasks': 0,
            'pending_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_health': 'healthy'
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks/active')
def tasks_active():
    """Get active tasks."""
    try:
        # For now, return empty list
        # In production, this would query task queue
        active_tasks = []
        return jsonify(active_tasks)
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/tasks/<task_id>/status')
def task_status(task_id):
    """Get specific task status."""
    try:
        # For now, return not found
        # In production, this would query task queue by ID
        return jsonify({'error': 'Task not found'}), 404
    except Exception as e:
        logger.error(f"Error getting task {task_id} status: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# NOTIFICATIONS ENDPOINTS
# =================================================================

@api_bp.route('/notifications/count')
def notifications_count():
    """Get unread notifications count."""
    try:
        # For now, return 0
        # In production, this would query notifications table
        count = 0
        return jsonify({'count': count})
    except Exception as e:
        logger.error(f"Error getting notifications count: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# TESTING ENDPOINTS
# =================================================================

@api_bp.route('/testing/active-tests')
def testing_active_tests():
    """Get active test information."""
    try:
        # Count active security and performance tests
        active_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.status.in_(['pending', 'running'])
        ).count()
        
        active_performance = PerformanceTest.query.filter(
            PerformanceTest.status.in_(['pending', 'running'])
        ).count()
        
        return jsonify({
            'active_security_tests': active_security,
            'active_performance_tests': active_performance,
            'total_active': active_security + active_performance
        })
    except Exception as e:
        logger.error(f"Error getting active tests: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/testing/service-status')
def testing_service_status():
    """Get testing service status."""
    try:
        # Check if analyzers are available
        # For now, return basic status
        status = {
            'static_analyzer': 'available',
            'dynamic_analyzer': 'available',
            'performance_tester': 'available',
            'ai_analyzer': 'available',
            'overall_status': 'healthy'
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/testing/templates')
def testing_templates():
    """Get available testing templates."""
    try:
        templates = [
            {
                'name': 'Basic Security Scan',
                'type': 'security',
                'tools': ['bandit', 'safety', 'eslint'],
                'description': 'Standard security vulnerability scan'
            },
            {
                'name': 'Performance Load Test', 
                'type': 'performance',
                'tools': ['locust'],
                'description': 'Basic load testing with configurable users'
            },
            {
                'name': 'Full Analysis Suite',
                'type': 'comprehensive',
                'tools': ['bandit', 'safety', 'eslint', 'locust', 'zap'],
                'description': 'Complete security and performance analysis'
            }
        ]
        return jsonify(templates)
    except Exception as e:
        logger.error(f"Error getting testing templates: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/testing/test-history')
def testing_test_history():
    """Get testing history summary."""
    try:
        from sqlalchemy import func
        from datetime import datetime, timedelta
        
        # Get test history for last 30 days
        since = datetime.now() - timedelta(days=30)
        
        security_history = db.session.query(
            func.date(SecurityAnalysis.created_at).label('date'),
            func.count(SecurityAnalysis.id).label('count')
        ).filter(SecurityAnalysis.created_at >= since)\
         .group_by(func.date(SecurityAnalysis.created_at))\
         .order_by(func.date(SecurityAnalysis.created_at)).all()
        
        performance_history = db.session.query(
            func.date(PerformanceTest.created_at).label('date'),
            func.count(PerformanceTest.id).label('count')
        ).filter(PerformanceTest.created_at >= since)\
         .group_by(func.date(PerformanceTest.created_at))\
         .order_by(func.date(PerformanceTest.created_at)).all()
        
        history = {
            'security_tests': [{'date': str(row.date), 'count': row.count} for row in security_history],
            'performance_tests': [{'date': str(row.date), 'count': row.count} for row in performance_history],
            'total_security': len(security_history),
            'total_performance': len(performance_history)
        }
        
        return jsonify(history)
    except Exception as e:
        logger.error(f"Error getting test history: {e}")
        return jsonify({'error': str(e)}), 500
