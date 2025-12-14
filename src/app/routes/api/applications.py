"""
Applications API module for managing generated applications.
Handles application lifecycle, container operations, and monitoring.
"""

from flask import Blueprint, request, current_app
from typing import TYPE_CHECKING, cast
from app.routes.api.common import api_error, api_success

try:  # Pylance compatibility – docker stubs omit errors module
    from docker.errors import ImageNotFound  # type: ignore
except Exception:  # pragma: no cover - docker optional during tests
    ImageNotFound = Exception  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    from app.services.docker_manager import DockerManager

# Create applications blueprint
applications_bp = Blueprint('api_applications', __name__)

# NOTE: Generic /applications/* CRUD endpoints removed - they were unused stubs.
# All actual application operations use the /app/{model_slug}/{app_number}/* pattern below.
# If you need CRUD operations, use the model-specific endpoints or add them here.

@applications_bp.route('/applications/<int:app_id>/start', methods=['POST'])
def start_application(app_id):
    """Start an application container."""
    # TODO: Move implementation from api.py
    return api_error("Start application endpoint not yet migrated", 501)

@applications_bp.route('/applications/<int:app_id>/stop', methods=['POST'])
def stop_application(app_id):
    """Stop an application container."""
    # TODO: Move implementation from api.py
    return api_error("Stop application endpoint not yet migrated", 501)

@applications_bp.route('/applications/<int:app_id>/restart', methods=['POST'])
def restart_application(app_id):
    """Restart an application container."""
    # TODO: Move implementation from api.py
    return api_error("Restart application endpoint not yet migrated", 501)

@applications_bp.route('/apps/grid')
def get_apps_grid():
    """Get applications grid view data."""
    # TODO: Move implementation from api.py
    return api_error("Apps grid endpoint not yet migrated", 501)

@applications_bp.route('/stats/apps')
def get_apps_stats():
    """Get application statistics."""
    # TODO: Move implementation from api.py
    return api_error("Apps stats endpoint not yet migrated", 501)

# Container management routes for specific model/app combinations
@applications_bp.route('/app/<model_slug>/<int:app_number>/start', methods=['POST'])
def start_app_container(model_slug, app_number):
    """Start a specific app container."""
    try:
        from app.services.service_locator import ServiceLocator
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        
        # Check if images exist first
        project_name = docker_mgr._get_project_name(model_slug, app_number)
        images_exist = False
        missing_images = []
        
        if docker_mgr.client:
            try:
                # Check for backend and frontend images
                backend_image = f"{project_name}-backend"
                frontend_image = f"{project_name}-frontend"
                
                try:
                    docker_mgr.client.images.get(backend_image)
                except ImageNotFound:
                    missing_images.append('backend')
                
                try:
                    docker_mgr.client.images.get(frontend_image)
                except ImageNotFound:
                    missing_images.append('frontend')
                
                images_exist = len(missing_images) == 0
            except Exception:
                # If check fails, continue anyway (fallback to old behavior)
                pass
        
        # Helper to update container status in DB
        def _update_container_status(status: str):
            try:
                from app.models import GeneratedApplication
                from app.extensions import db
                app_record = GeneratedApplication.query.filter_by(
                    model_slug=model_slug, app_number=app_number
                ).first()
                if app_record:
                    app_record.container_status = status
                    db.session.commit()
            except Exception as e:
                current_app.logger.warning(f"Failed to update container status: {e}")
        
        # If images don't exist, auto-build first
        if not images_exist and missing_images:
            build_result = docker_mgr.build_containers(model_slug, app_number, no_cache=False, start_after=True)
            # Invalidate cache after container operation
            status_cache = ServiceLocator.get_docker_status_cache()
            if status_cache:
                status_cache.invalidate(model_slug, app_number)
            if build_result.get('success'):
                # Build and start succeeded - update DB status
                _update_container_status('running')
                build_result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
                return api_success(build_result, message=f'Built and started containers for {model_slug}/app{app_number}')
            else:
                # Build/start failed - mark as build_failed in DB
                _update_container_status('build_failed')
                return api_error(f'Failed to build containers: {build_result.get("error", "Unknown error")}', status=500, details=build_result)
        
        # Images exist, just start them
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.start_containers(model_slug, app_number)
        # Invalidate cache after container operation
        status_cache = ServiceLocator.get_docker_status_cache()
        if status_cache:
            status_cache.invalidate(model_slug, app_number)
        result['preflight'] = pre
        if result.get('success'):
            # Start succeeded - update DB status
            _update_container_status('running')
            result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
            return api_success(result, message=f'Started containers for {model_slug}/app{app_number}')
        # Start failed - mark as build_failed in DB
        _update_container_status('build_failed')
        return api_error(f'Failed to start containers: {result.get("error", "Unknown error")}', status=500, details=result)
    except Exception as e:
        return api_error(f'Error starting containers: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/stop', methods=['POST'])
def stop_app_container(model_slug, app_number):
    """Stop a specific app container."""
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.stop_containers(model_slug, app_number)
        # Invalidate cache after container operation
        status_cache = ServiceLocator.get_docker_status_cache()
        if status_cache:
            status_cache.invalidate(model_slug, app_number)
        result['preflight'] = pre
        if result.get('success'):
            result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
            return api_success(result, message=f'Stopped containers for {model_slug}/app{app_number}')
        return api_error(f'Failed to stop containers: {result.get("error", "Unknown error")}', status=500, details=result)
    except Exception as e:
        return api_error(f'Error stopping containers: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/restart', methods=['POST'])
def restart_app_container(model_slug, app_number):
    """Restart a specific app container."""
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.restart_containers(model_slug, app_number)
        # Invalidate cache after container operation
        status_cache = ServiceLocator.get_docker_status_cache()
        if status_cache:
            status_cache.invalidate(model_slug, app_number)
        result['preflight'] = pre
        if result.get('success'):
            result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
            return api_success(result, message=f'Restarted containers for {model_slug}/app{app_number}')
        return api_error(f'Failed to restart containers: {result.get("error", "Unknown error")}', status=500, details=result)
    except Exception as e:
        return api_error(f'Error restarting containers: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/build', methods=['POST'])
def build_app_container(model_slug, app_number):
    """Build a specific app container."""
    try:
        from app.services.service_locator import ServiceLocator
        from app.models import GeneratedApplication
        from app.extensions import db
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        body = request.get_json(silent=True) or {}
        no_cache = body.get('no_cache', True)
        start_after = body.get('start_after', True)
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.build_containers(model_slug, app_number, no_cache=no_cache, start_after=start_after)
        # Invalidate cache after container operation
        status_cache = ServiceLocator.get_docker_status_cache()
        if status_cache:
            status_cache.invalidate(model_slug, app_number)
        result['preflight'] = pre
        
        # Update container status in DB based on result
        try:
            app_record = GeneratedApplication.query.filter_by(
                model_slug=model_slug, app_number=app_number
            ).first()
            if app_record:
                if result.get('success'):
                    app_record.container_status = 'running' if start_after else 'stopped'
                else:
                    app_record.container_status = 'build_failed'
                db.session.commit()
        except Exception as e:
            current_app.logger.warning(f"Failed to update container status: {e}")
        
        if result.get('success'):
            result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
            return api_success(result, message=f'Built containers for {model_slug}/app{app_number}')
        return api_error(f'Failed to build containers: {result.get("error", "Unknown error")}', status=500, details=result)
    except Exception as e:
        return api_error(f'Error building containers: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/diagnostics', methods=['GET'])
def app_compose_diagnostics(model_slug, app_number):
    """Return docker compose preflight + container status diagnostics."""
    try:
        from app.services.service_locator import ServiceLocator
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        diag = docker_mgr.compose_preflight(model_slug, app_number)
        diag['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
        
        return api_success(diag, message='Diagnostics collected')
    except Exception as e:
        return api_error(f'Error collecting diagnostics: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/logs', methods=['GET'])
def get_app_logs(model_slug, app_number):
    """Get logs for a specific app container."""
    try:
        from app.services.service_locator import ServiceLocator
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        
        lines = request.args.get('lines', 100, type=int)
        
        # Get logs for backend and frontend
        backend_logs = docker_mgr.get_container_logs(model_slug, app_number, container_type='backend', tail=lines)
        frontend_logs = docker_mgr.get_container_logs(model_slug, app_number, container_type='frontend', tail=lines)
        
        # Return JSON for API calls
        return api_success({
            'backend_logs': backend_logs,
            'frontend_logs': frontend_logs,
            'model_slug': model_slug,
            'app_number': app_number,
            'lines': lines
        }, message='Logs retrieved')
    except Exception as e:
        return api_error(f'Error retrieving logs: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/diagnose', methods=['GET'])
def diagnose_app(model_slug, app_number):
    """Diagnose issues with a specific app."""
    # TODO: Move implementation from api.py
    return api_error("Diagnose app endpoint not yet migrated", 501)

@applications_bp.route('/app/<model_slug>/<int:app_number>/test-port/<int:port>', methods=['GET'])
def test_app_port(model_slug, app_number, port):
    """Test if a specific port is accessible for an app."""
    try:
        import socket
        
        # Try to connect to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # 2 second timeout
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        accessible = result == 0
        
        return api_success({
            'port': port,
            'accessible': accessible,
            'model_slug': model_slug,
            'app_number': app_number
        }, message=f'Port {port} is {"accessible" if accessible else "not accessible"}')
    except Exception as e:
        return api_error(f'Error testing port: {e}', status=500)

@applications_bp.route('/app/<model_slug>/<int:app_number>/status', methods=['GET'])
def get_app_status(model_slug, app_number):
    """Get live container/application status using the DockerStatusCache.

    The cache provides efficient status lookups with on-demand refresh.
    Status is refreshed from Docker only if the cached entry is stale.

    Query Parameters:
        force_refresh: bool - Force a fresh Docker lookup (default: false)

    Returns:
      success: bool
      data: {
        model_slug, app_number, compose_file_exists, project_name,
        containers: [...], states: [...], running: bool,
        docker_status: str, cached_status: str, last_check: datetime,
        status_age_minutes: float, status_is_fresh: bool
      }
    """
    from app.services.service_locator import ServiceLocator
    from app.models import GeneratedApplication
    from datetime import datetime, timezone

    # Get the status cache
    status_cache = ServiceLocator.get_docker_status_cache()
    if not status_cache:
        # Fallback to direct Docker lookup if cache unavailable
        return _get_app_status_fallback(model_slug, app_number)
    
    force_refresh = request.args.get('force_refresh', 'false').lower() == 'true'
    
    try:
        # Get status from cache (will refresh if stale)
        cache_entry = status_cache.get_status(model_slug, app_number, force_refresh=force_refresh)
        
        # Get application from database for additional info
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
        
        # Calculate status age
        status_age_minutes = None
        if cache_entry.updated_at:
            now = datetime.now(timezone.utc)
            age = now - cache_entry.updated_at
            status_age_minutes = age.total_seconds() / 60
        
        # Determine if running
        running = cache_entry.status == 'running'
        
        payload = {
            'model_slug': model_slug,
            'app_number': app_number,
            'project_name': cache_entry.project_name,
            'compose_file_exists': cache_entry.compose_exists,
            'docker_connected': cache_entry.docker_connected,
            'containers': cache_entry.containers,
            'states': cache_entry.states,
            'running': running,
            'docker_status': cache_entry.status,
            'cached_status': app.container_status if app else cache_entry.status,
            'last_check': cache_entry.updated_at.isoformat() if cache_entry.updated_at else None,
            'status_age_minutes': status_age_minutes,
            'status_is_fresh': not cache_entry.is_stale(),
            'cache_info': {
                'is_stale': cache_entry.is_stale(),
                'updated_at': cache_entry.updated_at.isoformat() if cache_entry.updated_at else None
            },
            'errors': [{'error': cache_entry.error}] if cache_entry.error else []
        }
        return api_success(payload, message='Status retrieved')

    except Exception as e:
        current_app.logger.exception(
            "Error retrieving status for %s/app%s: %s", model_slug, app_number, e
        )
        # Fallback payload to prevent frontend from breaking
        return api_success({
            'model_slug': model_slug,
            'app_number': app_number,
            'project_name': None,
            'compose_file_exists': False,
            'docker_connected': False,
            'containers': [],
            'states': [],
            'running': False,
            'docker_status': 'error',
            'cached_status': 'unknown',
            'last_check': None,
            'status_age_minutes': None,
            'status_is_fresh': False,
            'errors': [{'stage': 'cache', 'error': str(e)}]
        }, message='Status retrieved with errors', status=200)


def _get_app_status_fallback(model_slug: str, app_number: int):
    """Fallback status lookup when cache is unavailable."""
    from app.services.service_locator import ServiceLocator
    from app.models import GeneratedApplication
    
    docker_mgr = ServiceLocator.get_docker_manager()
    if not docker_mgr:
        return api_error("Docker manager unavailable", status=503)
    
    try:
        # Get application from database
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
        
        # Use existing compose_preflight and container_status_summary
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        summary = docker_mgr.container_status_summary(model_slug, app_number)
        
        states = summary.get('states', [])
        normalized_states = [str(s).lower().strip() for s in states if s]
        running = any(s == 'running' for s in normalized_states)
        
        if running:
            docker_status = 'running'
        elif normalized_states:
            docker_status = 'stopped'
        elif pre.get('compose_file_exists'):
            docker_status = 'not_created'
        else:
            docker_status = 'no_compose'
        
        return api_success({
            'model_slug': model_slug,
            'app_number': app_number,
            'project_name': pre.get('project_name'),
            'compose_file_exists': pre.get('compose_file_exists'),
            'docker_connected': pre.get('docker_connected'),
            'containers': summary.get('containers', []),
            'states': states,
            'running': running,
            'docker_status': docker_status,
            'cached_status': app.container_status if app else docker_status,
            'last_check': None,
            'status_age_minutes': None,
            'status_is_fresh': False,
            'errors': [{'stage': 'fallback', 'error': 'Using direct Docker lookup'}]
        }, message='Status retrieved (fallback)')
        
    except Exception as e:
        return api_success({
            'model_slug': model_slug,
            'app_number': app_number,
            'docker_status': 'error',
            'running': False,
            'errors': [{'error': str(e)}]
        }, message='Status error', status=200)

@applications_bp.route('/app/<model_slug>/<int:app_number>/logs/tails', methods=['GET'])
def get_app_log_tails(model_slug, app_number):
    """Get tail of logs for a specific app."""
    # TODO: Move implementation from api.py
    return api_error("Get app log tails endpoint not yet migrated", 501)

@applications_bp.route('/app/<model_slug>/<int:app_number>/logs/download', methods=['GET'])
def download_app_logs(model_slug, app_number):
    """Download logs for a specific app."""
    # TODO: Move implementation from api.py
    return api_error("Download app logs endpoint not yet migrated", 501)

@applications_bp.route('/app/<model_slug>/<int:app_number>/scan-files', methods=['POST'])
def scan_app_files(model_slug, app_number):
    """Scan files for a specific app."""
    # TODO: Move implementation from api.py
    return api_error("Scan app files endpoint not yet migrated", 501)

@applications_bp.route('/app/<model_slug>/<int:app_number>/analyze', methods=['POST'])
def analyze_application(model_slug, app_number):
    """
    Trigger analysis for a specific application.
    
    Endpoint: POST /api/app/{model_slug}/{app_number}/analyze
    
    Request body:
    {
        "analysis_type": "security",  # security, performance, dynamic, ai, unified
        "tools": ["bandit", "safety"],  # Optional: specific tools
        "priority": "normal"  # Optional: normal, high, low
    }
    
    Returns:
    {
        "success": true,
        "task_id": "abc123",
        "message": "Analysis started",
        "data": {...}
    }
    """
    try:
        # Verify application exists
        from app.models import GeneratedApplication
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if not app:
            return api_error(f"Application not found: {model_slug}/app{app_number}", 404)
        
        # Get request data
        data = request.get_json() or {}
        analysis_type = data.get('analysis_type', 'security')
        tools = data.get('tools', [])
        priority = data.get('priority', 'normal')
        
        # Import task service
        from app.services.task_service import AnalysisTaskService
        from app.engines.container_tool_registry import get_container_tool_registry
        
        # Get tool registry
        registry = get_container_tool_registry()
        all_tools = registry.get_all_tools()
        
        # Build tool configuration if tools specified
        if tools:
            tool_ids = []
            tools_by_service = {}
            tool_names = []
            
            # Build lookup
            name_to_idx = {tool_name.lower(): idx + 1 for idx, tool_name in enumerate(all_tools.keys())}
            
            for tool_name in tools:
                tool_name_lower = tool_name.lower()
                if tool_name_lower in name_to_idx:
                    tool_id = name_to_idx[tool_name_lower]
                    tool_ids.append(tool_id)
                    
                    # Find tool object
                    tool_obj = None
                    for t_name, t_obj in all_tools.items():
                        if t_name.lower() == tool_name_lower:
                            tool_obj = t_obj
                            break
                    
                    if tool_obj and tool_obj.available:
                        service = tool_obj.container.value
                        tools_by_service.setdefault(service, []).append(tool_id)
                        tool_names.append(tool_obj.name)
            
            if not tools_by_service:
                return api_error("No valid tools found", 400)
            
            # Multi-service or single-service
            multiple_services = len(tools_by_service) > 1
            
            if multiple_services:
                task = AnalysisTaskService.create_main_task_with_subtasks(
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tool_names,
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
                    tools=tool_names,
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
            # No tools specified - create simple task
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=[],
                priority=priority,
                custom_options={'source': 'api'}
            )
        
        return api_success({
            'task_id': task.task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': task.analysis_type,
            'status': task.status.value if hasattr(task.status, 'value') else str(task.status),
            'created_at': task.created_at.isoformat() if task.created_at else None,
            'tools_count': len(tools) if tools else 'default'
        }, message='Analysis started successfully')
        
    except Exception as e:
        from flask import current_app
        current_app.logger.exception(f"Error starting analysis: {e}")
        return api_error(f"Failed to start analysis: {e}", 500)

@applications_bp.route('/apps/bulk/list', methods=['GET'])
def list_bulk_apps():
    """List applications for bulk operations."""
    # TODO: Move implementation from api.py
    return api_error("List bulk apps endpoint not yet migrated", 501)

@applications_bp.route('/apps/bulk/docker', methods=['POST'])
def bulk_docker_operations():
    """Perform bulk Docker operations on applications."""
    # TODO: Move implementation from api.py
    return api_error("Bulk docker operations endpoint not yet migrated", 501)