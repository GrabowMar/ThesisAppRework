"""
Analysis API module for managing code analysis operations.
Handles security analysis, performance testing, and analysis summaries.
All tool operations are now delegated to the container-based tool registry.
"""

from flask import Blueprint, jsonify, request
from app.routes.api.common import api_error
from app.engines.container_tool_registry import get_container_tool_registry
from app.utils.analysis_utils import extract_issues_from_sarif
from app.utils.tool_parsers import extract_tool_findings
import logging
from typing import Any, Dict, Optional, List

logger = logging.getLogger(__name__)

# Create analysis blueprint
analysis_bp = Blueprint('api_analysis', __name__)


def _derive_tool_issues_from_service(service_type: Optional[str], tool_name: str, analysis_block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Attempt to build issue arrays for tools that don't emit SARIF/issue payloads."""
    if not service_type or not isinstance(analysis_block, dict):
        return []

    return extract_tool_findings(service_type, tool_name, analysis_block)


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

# Mapping of tool names to their keys in the result JSON
TOOL_KEY_MAPPINGS = {
    'zap': 'zap_security_scan',
    'nmap': 'port_scan',
    'curl': 'connectivity',
    'connectivity': 'connectivity',
    'vulnscan': 'vulnerability_scan',
    'vulnerability_scan': 'vulnerability_scan'
}

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
        "priority": "normal",  # Optional: normal, high, low
        "container_management": {  # Optional: container lifecycle management
            "start_before_analysis": false,  # Start containers before analysis
            "build_if_missing": false,  # Build containers if not present
            "stop_after_analysis": false  # Stop containers after analysis completes
        }
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
        
        # Parse container management options (opt-in, disabled by default)
        container_opts = data.get('container_management', {})
        container_management = {
            'start_before_analysis': bool(container_opts.get('start_before_analysis', False)),
            'build_if_missing': bool(container_opts.get('build_if_missing', False)),
            'stop_after_analysis': bool(container_opts.get('stop_after_analysis', False))
        }
        
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
        
        if not tools_by_service or not tool_names:
            return api_error("No valid tools found", 400)
        
        # Build custom options for task
        custom_options = {
            'selected_tools': tool_ids,
            'selected_tool_names': tool_names,
            'tools_by_service': tools_by_service,
            'source': 'api',
            'container_management': container_management
        }
        
        # Always create main task with subtasks for consistent UI display
        # This ensures both single-service and multi-service analyses show subtasks
        custom_options['unified_analysis'] = True
        task = AnalysisTaskService.create_main_task_with_subtasks(
            model_slug=model_slug,
            app_number=app_number,
            tools=tool_names,
            priority=priority,
            custom_options=custom_options,
            task_name=f"api:{model_slug}:{app_number}"
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
                'priority': priority,
                'container_management': container_management
            }
        }), 201
        
    except Exception as e:
        logger.exception(f"Error running analysis: {str(e)}")
        return api_error(f"Failed to run analysis: {str(e)}", 500)


@analysis_bp.route('/task/<task_id>', methods=['GET'])
def get_task_status(task_id: str):
    """
    Get status and details of an analysis task.
    
    Endpoint: GET /api/analysis/task/<task_id>
    
    Returns:
    {
        "success": true,
        "data": {
            "task_id": "task_abc123",
            "status": "running",
            "progress_percentage": 45,
            "model_slug": "openai_gpt-4",
            "app_number": 1,
            "analysis_type": "security",
            "created_at": "2025-12-13T10:00:00",
            "started_at": "2025-12-13T10:00:05",
            "completed_at": null,
            "error_message": null,
            "subtasks": [...]
        }
    }
    """
    try:
        from app.services.task_service import AnalysisTaskService
        from app.models import AnalysisTask
        
        # Get task from database
        task = AnalysisTaskService.get_task(task_id)
        
        if not task:
            return api_error(f"Task not found: {task_id}", 404)
        
        # Build response data
        task_data = {
            'task_id': task.task_id,
            'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
            'progress_percentage': task.progress_percentage or 0,
            'model_slug': task.target_model,
            'app_number': task.target_app_number,
            'analysis_type': task.analysis_type,
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'error_message': task.error_message,
            'is_main_task': task.is_main_task,
            'service_name': task.service_name
        }
        
        # Include subtasks if this is a main task
        if task.is_main_task:
            subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
            task_data['subtasks'] = [
                {
                    'task_id': st.task_id,
                    'status': st.status.value if hasattr(st.status, 'value') else str(st.status),
                    'progress_percentage': st.progress_percentage or 0,
                    'service_name': st.service_name,
                    'error_message': st.error_message
                }
                for st in subtasks
            ]
        
        # Include result summary if completed
        if task.result_summary:
            task_data['result_summary'] = task.result_summary
        
        return jsonify({
            'success': True,
            'data': task_data
        })
        
    except Exception as e:
        logger.exception(f"Error getting task status: {str(e)}")
        return api_error(f"Failed to get task status: {str(e)}", 500)


@analysis_bp.route('/results/<result_id>/tools/<tool_name>', methods=['GET'])
def get_tool_details(result_id: str, tool_name: str):
    """
    Get detailed information for a specific tool from an analysis result.
    
    Endpoint: GET /api/analysis/results/<result_id>/tools/<tool_name>?service=<service_type>
    
    Query parameters:
        - service: Service type (static, dynamic, performance, ai) - optional
        - page: Page number for pagination (default: 1)
        - per_page: Items per page (default: 25)
        - severity: Filter by severity (CRITICAL, HIGH, MEDIUM, LOW, INFO)
    
    Returns:
    {
        "success": true,
        "data": {
            "tool_name": "bandit",
            "language": "python",
            "status": "success",
            "executed": true,
            "execution_time": 2.3,
            "total_issues": 5,
            "issues": [...],
            "sarif_file": "sarif/static_python_bandit.sarif.json",
            ...
        }
    }
    """
    try:
        from app.services.unified_result_service import UnifiedResultService
        
        # Get query parameters
        service_type = request.args.get('service', '').lower()
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 25))
        severity_filter = request.args.get('severity', '').upper()
        
        # Load result data
        result_service = UnifiedResultService()
        result = result_service.load_analysis_results(result_id)
        
        if not result:
            return api_error(f"Result not found: {result_id}", 404)
        
        result_data = result.raw_data
        
        # Extract tool data from result
        tool_data = None
        detected_service = None
        matched_analysis_block: Optional[Dict[str, Any]] = None
        
        # Try to find tool in services
        # Support both nested (results.services) and flat (services) structures
        services = result_data.get('results', {}).get('services', {})
        if not services:
            services = result_data.get('services', {})
        
        # Service name mappings: short name -> possible full names in data
        SERVICE_NAME_VARIANTS = {
            'static': ['static', 'static-analyzer'],
            'dynamic': ['dynamic', 'dynamic-analyzer'],
            'performance': ['performance', 'performance-tester'],
            'ai': ['ai', 'ai-analyzer']
        }
        
        # Search through all services if not specified
        search_services = [service_type] if service_type else ['static', 'dynamic', 'performance', 'ai']
        
        for svc in search_services:
            # Try all variants of the service name
            svc_variants = SERVICE_NAME_VARIANTS.get(svc, [svc])
            svc_data = None
            actual_svc_name = None
            for variant in svc_variants:
                if variant in services:
                    svc_data = services[variant]
                    actual_svc_name = variant
                    break
            
            if not svc_data:
                continue
            
            # Support both 'analysis' and 'payload' keys
            analysis = svc_data.get('analysis', {})
            if not analysis:
                analysis = svc_data.get('payload', {})
            
            # Check different result structures
            if svc == 'static':
                # Static has language-based grouping
                results = analysis.get('results', {})
                for lang, lang_tools in results.items():
                    if isinstance(lang_tools, dict) and tool_name.lower() in [k.lower() for k in lang_tools.keys()]:
                        # Find exact match (case-insensitive)
                        for k, v in lang_tools.items():
                            if k.lower() == tool_name.lower():
                                tool_data = v.copy()
                                tool_data['language'] = lang
                                detected_service = svc
                                matched_analysis_block = analysis
                                break
                    if tool_data:
                        break
            else:
                # Dynamic, performance, AI have flat tool_results
                # PRIORITIZE 'results' (full data) over 'tool_results' (metadata summary)
                full_results = analysis.get('results', {})
                tool_results = analysis.get('tool_results', {})
                
                # Determine the key to look for
                search_key = TOOL_KEY_MAPPINGS.get(tool_name.lower(), tool_name.lower())
                
                # Helper to search in a dictionary
                def find_tool_in_dict(source_dict, keys):
                    if not isinstance(source_dict, dict):
                        return None
                    
                    for key in keys:
                        for k, v in source_dict.items():
                            if k.lower() == key:
                                return v
                    return None

                # Try both mapped key and original tool name
                keys_to_try = [search_key, tool_name.lower()]
                # Remove duplicates
                keys_to_try = list(dict.fromkeys(keys_to_try))

                # 1. Try full results first (preferred source)
                found_data = find_tool_in_dict(full_results, keys_to_try)
                
                # 2. Fallback to tool_results (metadata summary)
                if found_data is None:
                    found_data = find_tool_in_dict(tool_results, keys_to_try)
                
                if found_data is not None:
                    if isinstance(found_data, list):
                        tool_data = {'items': found_data, 'status': 'success'}
                        # Try to extract status from first item if available
                        if found_data and isinstance(found_data[0], dict) and 'status' in found_data[0]:
                            tool_data['status'] = found_data[0]['status']
                    elif isinstance(found_data, dict):
                        tool_data = found_data.copy()
                    else:
                        tool_data = {'value': found_data}
                        
                    detected_service = svc
                    matched_analysis_block = analysis
                    break
            
            if tool_data:
                break
        
        if not tool_data:
            return api_error(f"Tool '{tool_name}' not found in result", 404)
        
        # Add tool name to response
        tool_data['tool_name'] = tool_name
        tool_data['service_type'] = detected_service

        if (not tool_data.get('issues')) and matched_analysis_block:
            derived_issues = _derive_tool_issues_from_service(
                detected_service,
                tool_name,
                matched_analysis_block
            )
            if derived_issues:
                tool_data['issues'] = derived_issues
                tool_data['total_issues'] = len(derived_issues)
        
        # If tool has SARIF data but empty issues array, derive issues from SARIF payload
        if (not tool_data.get('issues') or len(tool_data.get('issues', [])) == 0) and tool_data.get('sarif'):
            sarif_ref = tool_data.get('sarif')
            sarif_data = None
            sarif_file = None

            if isinstance(sarif_ref, dict):
                if sarif_ref.get('runs'):
                    sarif_data = sarif_ref
                else:
                    sarif_file = sarif_ref.get('sarif_file') or sarif_ref.get('path') or sarif_ref.get('file')
            elif isinstance(sarif_ref, str):
                sarif_file = sarif_ref

            if not sarif_data and sarif_file:
                try:
                    sarif_data = result_service.load_sarif_file(result_id, sarif_file)
                    if not sarif_data:
                        logger.warning(f"SARIF file missing for {tool_name}: {sarif_file}")
                except Exception as e:
                    logger.warning(f"Failed to load SARIF file for {tool_name}: {e}")

            if sarif_data:
                extracted_issues = extract_issues_from_sarif(sarif_data)
                tool_data['issues'] = extracted_issues
                tool_data['total_issues'] = len(extracted_issues)
                logger.info(f"Loaded {len(extracted_issues)} issues from SARIF data for {tool_name}")
        
        # Filter issues by severity if requested
        if severity_filter and 'issues' in tool_data and tool_data['issues']:
            original_issues = tool_data['issues']
            filtered_issues = [
                issue for issue in original_issues
                if (issue.get('issue_severity') or issue.get('severity', '')).upper() == severity_filter
            ]
            tool_data['issues'] = filtered_issues
            tool_data['filtered_count'] = len(filtered_issues)
            tool_data['original_count'] = len(original_issues)
        
        # Apply pagination to issues
        if 'issues' in tool_data and tool_data['issues']:
            total_issues = len(tool_data['issues'])
            start = (page - 1) * per_page
            end = start + per_page
            
            tool_data['pagination'] = {
                'page': page,
                'per_page': per_page,
                'total': total_issues,
                'pages': (total_issues + per_page - 1) // per_page,
                'has_prev': page > 1,
                'has_next': end < total_issues
            }
            
            # Slice issues for current page
            tool_data['issues'] = tool_data['issues'][start:end]
        
        return jsonify({
            'success': True,
            'data': tool_data
        })
        
    except Exception as e:
        logger.exception(f"Error fetching tool details: {str(e)}")
        return api_error(f"Failed to fetch tool details: {str(e)}", 500)


@analysis_bp.route('/results/<result_id>/sarif/<path:sarif_path>', methods=['GET'])
def get_sarif_file(result_id: str, sarif_path: str):
    """
    Get SARIF file content from an analysis result.
    
    Endpoint: GET /api/analysis/results/<result_id>/sarif/<sarif_path>
    
    Returns: SARIF JSON file or 404 if not found
    """
    try:
        from app.services.unified_result_service import UnifiedResultService
        result_service = UnifiedResultService()
        
        sarif_data = result_service.load_sarif_file(result_id, sarif_path)
        
        if not sarif_data:
            return api_error(f"SARIF file not found: {sarif_path}", 404)
        
        return jsonify(sarif_data)
        
    except Exception as e:
        logger.exception(f"Error fetching SARIF file: {str(e)}")
        return api_error(f"Failed to fetch SARIF file: {str(e)}", 500)

