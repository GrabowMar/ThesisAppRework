"""
Applications API module for managing generated applications.
Handles application lifecycle, container operations, and monitoring.
"""

from flask import Blueprint, request
from typing import TYPE_CHECKING, cast
from app.routes.api.common import api_error, api_success

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
        import docker
        
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
                except docker.errors.ImageNotFound:
                    missing_images.append('backend')
                
                try:
                    docker_mgr.client.images.get(frontend_image)
                except docker.errors.ImageNotFound:
                    missing_images.append('frontend')
                
                images_exist = len(missing_images) == 0
            except Exception:
                # If check fails, continue anyway (fallback to old behavior)
                pass
        
        # If images don't exist, auto-build first
        if not images_exist and missing_images:
            build_result = docker_mgr.build_containers(model_slug, app_number, no_cache=False, start_after=True)
            if build_result.get('success'):
                # Build and start succeeded
                build_result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
                return api_success(build_result, message=f'Built and started containers for {model_slug}/app{app_number}')
            else:
                return api_error(f'Failed to build containers: {build_result.get("error", "Unknown error")}', status=500, details=build_result)
        
        # Images exist, just start them
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.start_containers(model_slug, app_number)
        result['preflight'] = pre
        if result.get('success'):
            result['status_summary'] = docker_mgr.container_status_summary(model_slug, app_number)
            return api_success(result, message=f'Started containers for {model_slug}/app{app_number}')
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
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        docker_mgr = cast('DockerManager', docker_mgr)
        body = request.get_json(silent=True) or {}
        no_cache = body.get('no_cache', True)
        start_after = body.get('start_after', True)
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        result = docker_mgr.build_containers(model_slug, app_number, no_cache=no_cache, start_after=start_after)
        result['preflight'] = pre
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
    """Get live container/application status.

    Returns:
      success: bool
      data: {
        model_slug, app_number, compose_file_exists, project_name,
        containers: [...], states: [...], running: bool,
        cached_status: str, last_check: datetime, status_age_minutes: float
      }
    """
    try:
        from app.services.service_locator import ServiceLocator
        from app.models import GeneratedApplication
        from app.extensions import db
        from datetime import datetime, timezone
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return api_error("Docker manager unavailable", status=503)
        from typing import cast
        from app.services.docker_manager import DockerManager  # type: ignore
        docker_mgr = cast(DockerManager, docker_mgr)
        
        # Get application from database
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
        
        # Check Docker status
        pre = docker_mgr.compose_preflight(model_slug, app_number)
        summary = docker_mgr.container_status_summary(model_slug, app_number)
        states = (summary.get('states') or [])
        running = any(s.lower() == 'running' for s in states)
        
        # Determine current Docker status
        if running:
            docker_status = 'running'
        elif states:
            docker_status = 'stopped'
        elif pre.get('compose_file_exists'):
            docker_status = 'not_created'
        else:
            docker_status = 'no_compose'
        
        # If we have the app in database, update its status
        if app:
            # Update database status if it differs from Docker
            if app.container_status != docker_status:
                app.update_container_status(docker_status)
                db.session.commit()
            elif not app.last_status_check:
                # Update timestamp even if status is the same
                app.last_status_check = datetime.now(timezone.utc)
                db.session.commit()
                
            status_age_minutes = None
            if app.last_status_check:
                # Ensure both datetimes are timezone-aware
                now = datetime.now(timezone.utc)
                last_check = app.last_status_check
                if last_check.tzinfo is None:
                    last_check = last_check.replace(tzinfo=timezone.utc)
                age = now - last_check
                status_age_minutes = age.total_seconds() / 60
        else:
            status_age_minutes = None
        
        payload = {
            'model_slug': model_slug,
            'app_number': app_number,
            'project_name': pre.get('project_name'),
            'compose_file_exists': pre.get('compose_file_exists'),
            'docker_connected': pre.get('docker_connected'),
            'containers': summary.get('containers'),
            'states': states,
            'running': running,
            'docker_status': docker_status,
            'cached_status': app.container_status if app else None,
            'last_check': app.last_status_check.isoformat() if app and app.last_status_check else None,
            'status_age_minutes': status_age_minutes,
            'status_is_fresh': app.is_status_fresh() if app else False
        }
        return api_success(payload, message='Status retrieved')
    except Exception as e:
        return api_error(f'Error retrieving status: {e}', status=500)

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