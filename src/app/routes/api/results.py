"""
Enhanced API routes for analysis results.
=========================================

New endpoints that use the ResultsManagementService to provide
structured data for the frontend tabs.
"""

from flask import Blueprint, jsonify, request
from flask_login import current_user
import logging
from ...services.results_management_service import ResultsManagementService
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


def get_results_service() -> ResultsManagementService:
    """Get the results management service instance."""
    # Try to get from service locator first
    service = ServiceLocator.get('results_management_service')
    if service and isinstance(service, ResultsManagementService):
        return service
    # Create a new instance if not registered
    return ResultsManagementService()


@results_api_bp.route('/tasks/<task_id>/results')
def get_task_results(task_id: str):
    """Get complete structured results for a task."""
    try:
        service = get_results_service()
        results = service.get_task_results(task_id)
        
        if not results:
            return jsonify({
                'error': 'Task results not found',
                'task_id': task_id
            }), 404
        
        # Convert to dict for JSON serialization
        return jsonify({
            'task_id': results.task_id,
            'status': results.status,
            'analysis_type': results.analysis_type,
            'model_slug': results.model_slug,
            'app_number': results.app_number,
            'timestamp': results.timestamp.isoformat(),
            'duration': results.duration,
            'total_findings': results.total_findings,
            'tools_executed': results.tools_executed,
            'tools_failed': results.tools_failed,
            'security': results.security,
            'performance': results.performance,
            'quality': results.quality,
            'requirements': results.requirements
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
        
        # Convert datetime to string for JSON
        if 'timestamp' in summary and summary['timestamp']:
            summary['timestamp'] = summary['timestamp'].isoformat()
        
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
        # Force refresh to ensure we get properly extracted performance data
        results = service.get_task_results(task_id, force_refresh=True)
        
        if results and results.performance:
            performance_data = results.performance
        else:
            performance_data = service._empty_performance_data()
        
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
        # Force refresh to ensure we get properly extracted requirements data
        results = service.get_task_results(task_id, force_refresh=True)
        
        if results and results.requirements:
            requirements_data = results.requirements
        else:
            requirements_data = service._empty_requirements_data()
        
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
        
        return jsonify(tools_data)
        
    except Exception as e:
        logger.error(f"Error getting tools data for task {task_id}: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@results_api_bp.route('/tasks/<task_id>/refresh', methods=['POST'])
def refresh_task_results(task_id: str):
    """Force refresh of task results from API."""
    try:
        service = get_results_service()
        results = service.get_task_results(task_id, force_refresh=True)
        
        if not results:
            return jsonify({
                'error': 'Task results not found',
                'task_id': task_id
            }), 404
        
        return jsonify({
            'message': 'Results refreshed successfully',
            'task_id': task_id,
            'timestamp': results.timestamp.isoformat()
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
    """Recreate task data from JSON file and reload all cached data."""
    try:
        from pathlib import Path
        import json
        from ...services.simple_tool_results_service import SimpleToolResultsService
        from ...services.results_api_service import ResultsAPIService
        
        # Enhanced debug logging
        print(f"DEBUG: Recreate endpoint called with task_id: {task_id}")
        logger.info(f"Recreating task data from JSON for task {task_id}")
        logger.info(f"Request method: {request.method}, Headers: {dict(request.headers)}")
        
        # Try to find the JSON file for this task
        # Check common patterns for result file locations
        possible_patterns = [
            f"results/**/analysis/*{task_id}*.json",
            f"results/**/*{task_id}*.json",
        ]
        
        json_file = None
        project_root = Path(__file__).parent.parent.parent.parent.parent
        
        for pattern in possible_patterns:
            files = list(project_root.glob(pattern))
            if files:
                # Use the most recent file if multiple exist
                json_file = max(files, key=lambda f: f.stat().st_mtime)
                break
        
        if not json_file or not json_file.exists():
            return jsonify({
                'success': False,
                'error': f'JSON results file not found for task {task_id}',
                'task_id': task_id
            }), 404
        
        logger.info(f"Found JSON file: {json_file}")
        
        # Load the JSON data
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Failed to load JSON file: {str(e)}',
                'task_id': task_id
            }), 400
        
        # Clear existing cached data
        service = get_results_service()
        service.invalidate_cache(task_id)
        service.invalidate_tools_cache(task_id)
        
        # Recreate from JSON using SimpleToolResultsService
        tool_service = SimpleToolResultsService()
        success = tool_service.store_tool_results_from_json(task_id, json_data)
        
        if not success:
            return jsonify({
                'success': False,
                'error': 'Failed to store tool results from JSON',
                'task_id': task_id
            }), 500
        
        # Apply status corrections based on findings and service data
        logger.info(f"Applying status corrections for task {task_id}")
        
        from ...models.simple_tool_results import ToolResult, ToolSummary
        from ...extensions import db
        
        # Get findings and service data to correct tool statuses
        results = json_data.get('results', {})
        findings = results.get('findings', [])
        services = results.get('services', {})
        
        # Tools that have findings should be marked as success
        tools_with_findings = {}
        for finding in findings:
            tool = finding.get('tool')
            if tool:
                tools_with_findings[tool] = tools_with_findings.get(tool, 0) + 1
        
        # Tools that were used by services should be marked as success
        tools_executed = set()
        
        # Check performance tools
        perf_service = services.get('performance-tester', {})
        perf_tools = perf_service.get('summary', {}).get('tools_used', [])
        tools_executed.update(perf_tools)
        
        # Check dynamic tools
        dynamic_service = services.get('dynamic-analyzer', {})
        dynamic_tools = dynamic_service.get('summary', {}).get('tools_used', [])
        tools_executed.update(dynamic_tools)
        
        # Check AI tools
        ai_service = services.get('ai-analyzer', {})
        if ai_service and ai_service.get('success', False):
            ai_tools = ai_service.get('tools_requested', [])
            tools_executed.update(ai_tools)
        
        # Apply corrections to database
        corrections_made = 0
        stored_results = ToolResult.query.filter_by(task_id=task_id).all()
        
        for result in stored_results:
            tool_name = result.tool_name
            needs_correction = False
            
            # If tool has findings, it should be success
            if tool_name in tools_with_findings:
                if result.status != 'success':
                    result.status = 'success'
                    result.executed = True
                    result.total_issues = tools_with_findings[tool_name]
                    needs_correction = True
            
            # If tool was executed by services, it should be success (even with 0 findings)
            elif tool_name in tools_executed:
                if result.status != 'success':
                    result.status = 'success'
                    result.executed = True
                    needs_correction = True
            
            if needs_correction:
                corrections_made += 1
        
        # Update summary counts
        if corrections_made > 0:
            total_tools = len(stored_results)
            executed_tools = sum(1 for t in stored_results if t.executed)
            successful_tools = sum(1 for t in stored_results if t.status == 'success')
            failed_tools = sum(1 for t in stored_results if t.status == 'error')
            not_available_tools = sum(1 for t in stored_results if t.status == 'not_available')
            total_issues = sum(t.total_issues or 0 for t in stored_results)
            
            summary = ToolSummary.query.filter_by(task_id=task_id).first()
            if summary:
                summary.total_tools = total_tools
                summary.executed_tools = executed_tools
                summary.successful_tools = successful_tools
                summary.failed_tools = failed_tools
                summary.not_available_tools = not_available_tools
                summary.total_issues_found = total_issues
        
        # Commit all changes
        db.session.commit()
        
        logger.info(f"Applied {corrections_made} status corrections for task {task_id}")
        
        # Also update the API cache with fresh data
        api_service = ResultsAPIService()
        try:
            # Force refresh the API data
            api_service._fetch_raw_results(task_id)
        except Exception as e:
            logger.warning(f"Failed to refresh API cache: {e}")
            # Don't fail the whole operation for this
        
        logger.info(f"Successfully recreated task data from JSON for task {task_id}")
        
        # Calculate comprehensive return data from the JSON
        findings = results.get('findings', [])
        tools_section = results.get('tools', {})
        summary = results.get('summary', {})
        
        # Count tools by status from JSON
        tools_successful_json = sum(1 for tool_data in tools_section.values() if tool_data.get('status') == 'success')
        tools_failed_json = sum(1 for tool_data in tools_section.values() if tool_data.get('status') == 'error')
        tools_not_available_json = sum(1 for tool_data in tools_section.values() if tool_data.get('status') == 'not_available')
        
        # Get AI analysis compliance if available
        ai_compliance = 0.0
        ai_service = services.get('ai-analyzer', {})
        if ai_service and ai_service.get('success'):
            ai_results = ai_service.get('raw_outputs', {}).get('analysis', {}).get('results', {})
            ai_summary = ai_results.get('summary', {})
            ai_compliance = ai_summary.get('compliance_percentage', 0.0)
        
        return jsonify({
            'success': True,
            'message': 'Task data successfully recreated from JSON',
            'task_id': task_id,
            'source_file': str(json_file.relative_to(project_root)),
            
            # Cache and update status
            'tools_updated': True,
            'cache_cleared': True,
            'status_corrections': corrections_made,
            
            # Comprehensive analysis summary from JSON
            'analysis_summary': {
                'total_findings': summary.get('total_findings', len(findings)),
                'tools_executed': summary.get('tools_executed', len(tools_section)),
                'services_executed': summary.get('services_executed', len(services)),
                'tools_successful': tools_successful_json,
                'tools_failed': tools_failed_json,
                'tools_not_available': tools_not_available_json,
                'ai_compliance_percentage': ai_compliance
            },
            
            # Processing details
            'processing_details': {
                'tools_with_findings': len(tools_with_findings),
                'tools_executed_by_services': len(tools_executed),
                'performance_data_available': bool(services.get('performance-tester')),
                'ai_analysis_available': bool(services.get('ai-analyzer')),
                'security_findings': len([f for f in findings if f.get('category') == 'security']),
                'quality_issues': len([f for f in findings if f.get('category') in ['quality', 'code_quality']])
            },
            
            # Severity breakdown if available
            'severity_breakdown': summary.get('severity_breakdown', {})
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
        count = service.clear_stale_cache(older_than_hours=hours)
        
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
            'service': 'results_api',
            'version': '2.0'
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

@results_api_bp.route('/test_recreate', methods=['GET', 'POST'])
def test_recreate():
    """Test endpoint to verify routing works."""
    return jsonify({
        'message': 'Test endpoint works!',
        'method': request.method,
        'path': request.path
    })