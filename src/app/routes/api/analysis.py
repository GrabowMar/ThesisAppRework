"""
Analysis API module for managing code analysis operations.
Handles security analysis, performance testing, and analysis summaries.
All tool operations are now delegated to the container-based tool registry.
"""

from flask import Blueprint, jsonify, request
from app.routes.api.common import api_error
from app.engines.container_tool_registry import get_container_tool_registry
import logging

logger = logging.getLogger(__name__)

# Create analysis blueprint
analysis_bp = Blueprint('api_analysis', __name__)


def _resolve_tools_from_names(tool_names, all_tools):
    """Helper to resolve tool names to IDs and group by service.
    
    Returns:
        tuple: (tool_ids, tool_names, tools_by_service) or (None, None, None) if no valid tools
    """
    tool_ids = []
    valid_tool_names = []
    tools_by_service = {}
    
    # Build lookup: name (case-insensitive) -> tool object
    tools_lookup = {t.name.lower(): t for t in all_tools.values()}
    name_to_idx = {t.name.lower(): idx + 1 for idx, t in enumerate(all_tools.values())}
    
    for tool_name in tool_names:
        tool_name_lower = tool_name.lower()
        tool_obj = tools_lookup.get(tool_name_lower)
        
        if tool_obj and tool_obj.available:
            tool_id = name_to_idx.get(tool_name_lower)
            if tool_id:
                tool_ids.append(tool_id)
                valid_tool_names.append(tool_obj.name)
                service = tool_obj.container.value
                tools_by_service.setdefault(service, []).append(tool_id)
        else:
            logger.warning(f"Tool '{tool_name}' not found or unavailable")
    
    if not tools_by_service:
        return None, None, None
    
    return tool_ids, valid_tool_names, tools_by_service

@analysis_bp.route('/tool-registry/custom-analysis', methods=['POST'])
def create_custom_analysis():
    """Create a custom analysis request using container tools."""
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        required_fields = ['model_slug', 'app_number']
        for field in required_fields:
            if field not in data:
                return api_error(f"Missing required field: {field}", 400)
        
        # Create custom analysis configuration
        result = {
            'analysis_id': f"custom_{data['app_number']}_{data['model_slug']}",
            'app_number': data['app_number'],
            'model_slug': data['model_slug'],
            'tools': data.get('tools', []),
            'containers': data.get('containers', ['static-analyzer']),
            'created_at': __import__('time').time()
        }
        
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Custom analysis created successfully'
        })
    except Exception as e:
        logger.error(f"Error creating custom analysis: {str(e)}")
        return api_error(f"Failed to create custom analysis: {str(e)}", 500)

@analysis_bp.route('/tool-registry/execution-plan/<int:analysis_id>')
def get_execution_plan(analysis_id):
    """Get execution plan for a custom analysis."""
    try:
        # Basic execution plan based on container tools
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        plan = {
            'analysis_id': analysis_id,
            'steps': [],
            'estimated_duration': 0
        }
        
        # Create steps for each container
        for container in ['static-analyzer', 'dynamic-analyzer', 'performance-tester']:
            tools = [tool for tool in all_tools.values() if tool.container.value == container]
            if tools:
                plan['steps'].append({
                    'step': len(plan['steps']) + 1,
                    'container': container,
                    'tools': [tool.name for tool in tools if tool.available],
                    'estimated_duration': 60  # seconds
                })
                plan['estimated_duration'] += 60
        
        return jsonify({
            'success': True,
            'data': plan,
            'message': 'Execution plan retrieved successfully'
        })
    except Exception as e:
        logger.error(f"Error fetching execution plan: {str(e)}")
        return api_error(f"Failed to fetch execution plan: {str(e)}", 500)


@analysis_bp.route('/run', methods=['POST'])
def run_analysis():
    """
    Run analysis on an application.
    
    Endpoint: POST /api/analysis/run
    
    Request body:
    {
        "model_slug": "openai_codex-mini",
        "app_number": 1,
        "analysis_type": "security",  # security, performance, dynamic, ai, unified
        "tools": ["bandit", "safety"],  # Optional: specific tools to run
        "priority": "normal"  # Optional: normal, high, low
    }
    
    Returns:
    {
        "success": true,
        "task_id": "abc123...",
        "message": "Analysis task created",
        "data": {
            "task_id": "abc123...",
            "model_slug": "openai_codex-mini",
            "app_number": 1,
            "analysis_type": "security",
            "status": "pending",
            "created_at": "2025-10-27T10:00:00"
        }
    }
    """
    try:
        data = request.get_json() or {}
        
        # Validate required fields
        model_slug = data.get('model_slug', '').strip()
        app_number = data.get('app_number')
        analysis_type = data.get('analysis_type', 'security').strip()
        tools = data.get('tools', [])
        priority = data.get('priority', 'normal').strip()
        
        if not model_slug:
            return api_error("Missing required field: model_slug", 400)
        if not app_number:
            return api_error("Missing required field: app_number", 400)
        
        try:
            app_number = int(app_number)
        except (ValueError, TypeError):
            return api_error("app_number must be an integer", 400)
        
        # Verify application exists
        from app.models import GeneratedApplication
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not app:
            return api_error(f"Application not found: {model_slug}/app{app_number}", 404)
        
        # Import task service
        from app.services.task_service import AnalysisTaskService
        from app.engines.container_tool_registry import get_container_tool_registry
        
        # Get tool registry
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Determine which tools to run
        if not tools:
            # No tools specified - use analysis_type to determine tools
            if analysis_type in ['unified', 'comprehensive']:
                tools = [t.name for t in all_tools.values() if t.available]
            else:
                # Map analysis_type to default tools
                default_tools_map = {
                    'security': ['bandit', 'safety', 'eslint'],
                    'performance': ['locust'],
                    'dynamic': ['zap'],
                    'ai': ['ai-analyzer']
                }
                tools = default_tools_map.get(analysis_type, ['bandit', 'safety'])
        
        # Resolve tool names to IDs and group by service
        tool_ids, tool_names, tools_by_service = _resolve_tools_from_names(tools, all_tools)
        
        if not tools_by_service:
            return api_error("No valid tools found", 400)
        
        # Build custom options for task
        custom_options = {
            'selected_tools': tool_ids,
            'selected_tool_names': tool_names,
            'tools_by_service': tools_by_service,
            'source': 'api'
        }
        
        # Create task - use multi-service if multiple containers involved
        if len(tools_by_service) > 1:
            custom_options['unified_analysis'] = True
            task = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug=model_slug,
                app_number=app_number,
                tools=tool_names,
                priority=priority,
                custom_options=custom_options,
                task_name=f"api:{model_slug}:{app_number}"
            )
        else:
            custom_options['unified_analysis'] = False
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=tool_names,
                priority=priority,
                custom_options=custom_options
            )
        
        # Return task information
        return jsonify({
            'success': True,
            'task_id': task.task_id,
            'message': 'Analysis task created successfully',
            'data': {
                'task_id': task.task_id,
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': task.analysis_type,
                'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'tools_count': len(tools) if tools else 'all',
                'priority': priority
            }
        }), 201
        
    except Exception as e:
        logger.exception(f"Error running analysis: {str(e)}")
        return api_error(f"Failed to run analysis: {str(e)}", 500)

