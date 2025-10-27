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
        
        # Build tool configuration
        if tools:
            # User specified tools - convert names to IDs and group by service
            tool_ids = []
            tools_by_service = {}
            tool_names = []
            
            # Build lookup tables
            name_to_idx = {tool_name.lower(): idx + 1 for idx, tool_name in enumerate(all_tools.keys())}
            
            for tool_name in tools:
                tool_name_lower = tool_name.lower()
                if tool_name_lower in name_to_idx:
                    tool_id = name_to_idx[tool_name_lower]
                    tool_ids.append(tool_id)
                    
                    # Find tool object to get container
                    tool_obj = all_tools.get(tool_name)
                    if not tool_obj:
                        # Try case-insensitive lookup
                        for t_name, t_obj in all_tools.items():
                            if t_name.lower() == tool_name_lower:
                                tool_obj = t_obj
                                break
                    
                    if tool_obj and tool_obj.available:
                        service = tool_obj.container.value
                        tools_by_service.setdefault(service, []).append(tool_id)
                        tool_names.append(tool_obj.name)
                else:
                    logger.warning(f"Unknown tool: {tool_name}")
            
            if not tools_by_service:
                return api_error("No valid tools found", 400)
            
            # Decide if we need multi-service task or single-service
            multiple_services = len(tools_by_service) > 1
            
            if multiple_services:
                # Create main task with subtasks
                task = AnalysisTaskService.create_main_task_with_subtasks(
                    model_slug=model_slug,
                    app_number=app_number,
                    analysis_type='unified',
                    tools_by_service=tools_by_service,
                    priority=priority,
                    custom_options={
                        'selected_tools': tool_ids,
                        'selected_tool_names': tool_names,
                        'tools_by_service': tools_by_service,
                        'unified_analysis': True,
                        'source': 'api'
                    },
                    task_name=f"api:{model_slug}:{app_number}"
                )
            else:
                # Single service - create simple task
                service_to_engine = {
                    'static-analyzer': 'security',
                    'dynamic-analyzer': 'dynamic',
                    'performance-tester': 'performance',
                    'ai-analyzer': 'ai',
                }
                only_service = next(iter(tools_by_service.keys()))
                engine_name = service_to_engine.get(only_service, analysis_type)
                
                task = AnalysisTaskService.create_task(
                    model_slug=model_slug,
                    app_number=app_number,
                    analysis_type=engine_name,
                    priority=priority,
                    custom_options={
                        'selected_tools': tool_ids,
                        'selected_tool_names': tool_names,
                        'tools_by_service': tools_by_service,
                        'unified_analysis': False,
                        'source': 'api'
                    }
                )
        else:
            # No tools specified - run all tools for the analysis type
            if analysis_type in ['unified', 'comprehensive']:
                # Run all tools across all services
                all_tool_ids = list(range(1, len(all_tools) + 1))
                all_tool_names = list(all_tools.keys())
                
                tools_by_service = {}
                for idx, (tool_name, tool) in enumerate(all_tools.items()):
                    if tool.available:
                        service = tool.container.value
                        tool_id = idx + 1
                        tools_by_service.setdefault(service, []).append(tool_id)
                
                task = AnalysisTaskService.create_main_task_with_subtasks(
                    model_slug=model_slug,
                    app_number=app_number,
                    analysis_type=analysis_type,
                    tools_by_service=tools_by_service,
                    priority=priority,
                    custom_options={
                        'selected_tools': all_tool_ids,
                        'selected_tool_names': all_tool_names,
                        'tools_by_service': tools_by_service,
                        'unified_analysis': True,
                        'source': 'api'
                    },
                    task_name=f"api:{model_slug}:{app_number}"
                )
            else:
                # Run default tools for specified analysis type
                task = AnalysisTaskService.create_task(
                    model_slug=model_slug,
                    app_number=app_number,
                    analysis_type=analysis_type,
                    priority=priority,
                    custom_options={'source': 'api'}
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

