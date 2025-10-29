"""
Enhanced API routes for analysis results.
=========================================

New endpoints that use the UnifiedResultService to provide
structured data for the frontend tabs.
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user
import logging
from ...services.unified_result_service import UnifiedResultService
from ...services.service_locator import ServiceLocator

logger = logging.getLogger(__name__)

# Create blueprint for enhanced results API
results_api_bp = Blueprint('results_api', __name__, url_prefix='/analysis/api')

# Require authentication for all results API routes
@results_api_bp.before_request
def require_authentication():
    """Require authentication for all results API endpoints."""
    if not current_user.is_authenticated:
        return jsonify({
            'error': 'Authentication required',
            'message': 'Please log in to access this endpoint',
            'login_url': '/auth/login'
        }), 401


def get_results_service() -> UnifiedResultService:
    """Get the unified result service instance."""
    # Try to get from service locator first
    service = ServiceLocator.get_unified_result_service()
    if service and isinstance(service, UnifiedResultService):
        return service
    # Create a new instance if not registered
    return UnifiedResultService()


@results_api_bp.route('/tasks/<task_id>/results')
def get_task_results(task_id: str):
    """Get complete structured results for a task."""
    try:
        service = get_results_service()
        results = service.load_analysis_results(task_id)
        
        if not results:
            return jsonify({
                'error': 'Task results not found',
                'task_id': task_id
            }), 404
        
        # Convert to dict for JSON serialization
        return jsonify({
            'task_id': results.task_id,
            'status': results.status,
            'summary': results.summary,
            'security': results.security,
            'performance': results.performance,
            'quality': results.quality,
            'requirements': results.requirements,
            'tools': results.tools
        })
        
    except Exception as e:
        logger.error(f"Error getting results for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/summary')
def get_task_summary(task_id: str):
    """Get task summary for the overview tab."""
    try:
        service = get_results_service()
        summary = service.get_task_summary(task_id)
        
        if not summary:
            return jsonify({'error': 'Summary not found'}), 404
        
        return jsonify(summary)
        
    except Exception as e:
        logger.error(f"Error getting summary for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/security')
def get_task_security(task_id: str):
    """Get security-specific data for a task."""
    try:
        service = get_results_service()
        security_data = service.get_security_data(task_id)
        
        if not security_data:
            return jsonify({'error': 'Security data not found'}), 404
        
        return jsonify(security_data)
        
    except Exception as e:
        logger.error(f"Error getting security data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/performance')
def get_task_performance(task_id: str):
    """Get performance-specific data for a task."""
    try:
        service = get_results_service()
        performance_data = service.get_performance_data(task_id)
        
        if not performance_data:
            return jsonify({'error': 'Performance data not found'}), 404
        
        return jsonify(performance_data)
        
    except Exception as e:
        logger.error(f"Error getting performance data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/quality')
def get_task_quality(task_id: str):
    """Get code quality-specific data for a task."""
    try:
        service = get_results_service()
        quality_data = service.get_quality_data(task_id)
        
        if not quality_data:
            return jsonify({'error': 'Quality data not found'}), 404
        
        return jsonify(quality_data)
        
    except Exception as e:
        logger.error(f"Error getting quality data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/requirements')
def get_task_requirements(task_id: str):
    """Get AI requirements-specific data for a task."""
    try:
        service = get_results_service()
        requirements_data = service.get_requirements_data(task_id)
        
        if not requirements_data:
            return jsonify({'error': 'Requirements data not found'}), 404
        
        return jsonify(requirements_data)
        
    except Exception as e:
        logger.error(f"Error getting requirements data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/tools')
def get_task_tools(task_id: str):
    """Get comprehensive tool execution data for a task."""
    try:
        service = get_results_service()
        tools_data = service.get_tools_data(task_id)
        
        if not tools_data:
            return jsonify({'error': 'Tools data not found'}), 404
        
        return jsonify(tools_data)
        
    except Exception as e:
        logger.error(f"Error getting tools data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/refresh', methods=['POST'])
def refresh_task_results(task_id: str):
    """Force refresh of task results from storage."""
    try:
        service = get_results_service()
        results = service.load_analysis_results(task_id, force_refresh=True)
        
        if not results:
            return jsonify({
                'error': 'Task results not found',
                'task_id': task_id
            }), 404
        
        return jsonify({
            'message': 'Results refreshed successfully',
            'task_id': task_id,
            'status': results.status
        })
        
    except Exception as e:
        logger.error(f"Error refreshing results for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/cache/invalidate', methods=['POST'])
def invalidate_task_cache(task_id: str):
    """Invalidate cached results for a task."""
    try:
        service = get_results_service()
        success = service.invalidate_cache(task_id)
        
        return jsonify({
            'message': 'Cache invalidated successfully' if success else 'Cache entry not found',
            'task_id': task_id,
            'invalidated': success
        })
        
    except Exception as e:
        logger.error(f"Error invalidating cache for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/recreate_from_json', methods=['POST'])
def recreate_from_json(task_id: str):
    """Recreate task data from JSON file."""
    try:
        service = get_results_service()
        success = service.rebuild_from_json(task_id)
        
        if not success:
            return jsonify({
                'success': False,
                'error': f'Failed to rebuild from JSON for task {task_id}',
                'task_id': task_id
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Task data successfully recreated from JSON',
            'task_id': task_id
        })
        
    except Exception as e:
        logger.error(f"Error recreating task data for {task_id}: {e}")
        return jsonify({
            'success': False,
            'error': f'Internal server error: {str(e)}',
            'task_id': task_id
        }), 500


@results_api_bp.route('/cache/cleanup', methods=['POST'])
def cleanup_cache():
    """Cleanup old cache entries."""
    try:
        hours = request.json.get('hours', 24) if request.json else 24
        
        service = get_results_service()
        count = service.cleanup_stale_cache(hours=hours)
        
        return jsonify({
            'message': f'Cleaned up {count} stale cache entries',
            'entries_cleaned': count,
            'older_than_hours': hours
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up cache: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/health')
def health_check():
    """Health check endpoint for the results API."""
    try:
        # Test basic service functionality
        get_results_service()
        
        return jsonify({
            'status': 'healthy',
            'service': 'unified_result_service',
            'version': '2.0'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503