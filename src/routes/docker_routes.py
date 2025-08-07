"""
Docker Container Management Routes
=================================

This module contains routes for Docker container operations including:
- Container lifecycle management (start, stop, restart)
- Container status monitoring
- Docker system overview
- Bulk operations

Extracted and refactored from the original web_routes.py file.
"""

import logging
from typing import Any, Dict

from flask import Blueprint, request

from .utils import (
    log_performance, ResponseHandler, ServiceLocator, AppDataProvider,
    DockerOperations
)

# Initialize logger
logger = logging.getLogger(__name__)

# Create blueprints
containers_bp = Blueprint("containers", __name__, url_prefix="/api/v1/containers")
docker_main_bp = Blueprint("docker_main", __name__)  # For /docker route


# ===========================
# CONTAINER MANAGEMENT ROUTES
# ===========================

@containers_bp.route("/<model_slug>/<int:app_num>/start", methods=["POST"])
def container_start(model_slug: str, app_num: int):
    """Start containers for a specific model/app."""
    try:
        result = DockerOperations.execute_action('start', model_slug, app_num)
        if result['success']:
            return ResponseHandler.success_response(
                message=f"Started containers for {model_slug}/app{app_num}",
                data=result
            )
        else:
            return ResponseHandler.error_response(result.get('error', 'Start operation failed'))
    except Exception as e:
        logger.error(f"Container start error: {e}")
        return ResponseHandler.error_response(str(e))


@containers_bp.route("/<model_slug>/<int:app_num>/stop", methods=["POST"])
def container_stop(model_slug: str, app_num: int):
    """Stop containers for a specific model/app."""
    try:
        result = DockerOperations.execute_action('stop', model_slug, app_num)
        if result['success']:
            return ResponseHandler.success_response(
                message=f"Stopped containers for {model_slug}/app{app_num}",
                data=result
            )
        else:
            return ResponseHandler.error_response(result.get('error', 'Stop operation failed'))
    except Exception as e:
        logger.error(f"Container stop error: {e}")
        return ResponseHandler.error_response(str(e))


@containers_bp.route("/<model_slug>/<int:app_num>/restart", methods=["POST"])
def container_restart(model_slug: str, app_num: int):
    """Restart containers for a specific model/app."""
    try:
        result = DockerOperations.execute_action('restart', model_slug, app_num)
        if result['success']:
            return ResponseHandler.success_response(
                message=f"Restarted containers for {model_slug}/app{app_num}",
                data=result
            )
        else:
            return ResponseHandler.error_response(result.get('error', 'Restart operation failed'))
    except Exception as e:
        logger.error(f"Container restart error: {e}")
        return ResponseHandler.error_response(str(e))


@containers_bp.route("/<model_slug>/<int:app_num>/logs")
def container_logs(model_slug: str, app_num: int):
    """Get container logs for a specific model/app."""
    try:
        container_type = request.args.get('type', 'backend')
        tail = request.args.get('tail', 200, type=int)
        
        logs = DockerOperations.get_logs(model_slug, app_num, container_type, tail)
        
        # Return as HTML for direct display in modal
        logs_html = f"""
        <div class="log-content">
            <div class="log-header">
                <h6><i class="fas fa-terminal mr-2"></i>Logs for {model_slug}/app{app_num}/{container_type}</h6>
            </div>
            <pre class="log-text">{logs}</pre>
        </div>
        """
        
        return logs_html
        
    except Exception as e:
        logger.error(f"Container logs error: {e}")
        return f"<div class='alert alert-danger'>Error loading logs: {str(e)}</div>"


# ===========================
# DOCKER OVERVIEW ROUTES
# ===========================

@docker_main_bp.route("/docker")
def docker_redirect():
    """Docker management page - serve docker content directly."""
    # Call docker_overview function directly to serve content instead of redirecting
    try:
        docker_manager = ServiceLocator.get_docker_manager()
        
        context = {
            'title': 'Docker Management',
            'active_page': 'docker',
            'docker_status': 'available' if docker_manager else 'unavailable'
        }
        return ResponseHandler.render_response("docker_overview.html", **context)
    except Exception as e:
        logger.error(f"Docker overview error: {e}")
        return f"Error: Docker management unavailable - {str(e)}", 500


@docker_main_bp.route("/docker")
def docker_overview():
    """Docker management overview."""
    try:
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Get Docker info
        docker_available = False
        docker_info = {}
        docker_version = {}
        
        if docker_manager:
            try:
                docker_info = docker_manager.client.info()
                docker_version = docker_manager.client.version()
                docker_available = True
            except Exception:
                pass
        
        # Get container statistics
        all_apps = AppDataProvider.get_all_apps()
        container_stats = {
            'total_apps': len(all_apps),
            'running': sum(1 for app in all_apps if app.get('status') == 'running'),
            'stopped': sum(1 for app in all_apps if app.get('status') != 'running'),
            'models': len(set(app['model'] for app in all_apps))
        }
        
        context = {
            'docker_available': docker_available,
            'docker_info': docker_info,
            'docker_version': docker_version,
            'container_stats': container_stats,
            'recent_apps': all_apps[:10]
        }
        
        return ResponseHandler.render_response("docker_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Docker overview error: {e}")
        return ResponseHandler.error_response(str(e))


# Add the DockerOperations get_logs method if it doesn't exist
class DockerOperations:
    """Enhanced Docker operations."""
    
    @staticmethod
    def get_logs(model: str, app_num: int, container_type: str, tail: int = 200) -> str:
        """Get container logs."""
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return "Docker manager not available"
        
        try:
            # Convert model slug to Docker container naming format
            container_model_name = model.replace('-', '_').replace('.', '_')
            container_name = f"{container_model_name}_app{app_num}_{container_type}"
            return docker_manager.get_container_logs(container_name, tail=tail)
        except Exception as e:
            logger.error(f"Error getting logs: {e}")
            return f"Error getting logs: {str(e)}"
    
    @staticmethod
    def execute_action(action: str, model: str, app_num: int) -> Dict[str, Any]:
        """Execute a Docker action on an app."""
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return {'success': False, 'error': 'Docker manager not available'}
        
        try:
            # Get compose file path
            from pathlib import Path
            project_root = Path(__file__).parent.parent.parent
            compose_path = project_root / "misc" / "models" / model / f"app{app_num}" / "docker-compose.yml"
            
            if not compose_path.exists():
                return {'success': False, 'error': 'Docker compose file not found'}
            
            logger.info(f"Executing {action} for {model}/app{app_num}")
            
            # Execute action
            action_map = {
                'start': docker_manager.start_containers,
                'stop': docker_manager.stop_containers,
                'restart': docker_manager.restart_containers,
                'build': docker_manager.build_containers
            }
            
            if action not in action_map:
                return {'success': False, 'error': f'Unknown action: {action}'}
            
            return action_map[action](str(compose_path), model, app_num)
            
        except Exception as e:
            logger.error(f"Error executing {action} for {model}/app{app_num}: {e}")
            # Provide user-friendly error messages
            error_msg = str(e)
            if "Nie można odnaleźć określonego pliku" in error_msg or "dockerDesktopLinuxEngine" in error_msg:
                error_msg = "Docker Desktop is not running. Please start Docker Desktop and try again."
            elif "unable to get image" in error_msg:
                error_msg = "Docker images not built. Please build the containers first."
            
@docker_main_bp.route("/docker/start/<model>/<int:app_num>", methods=["POST"])
def docker_start_action(model: str, app_num: int):
    """Start containers for a specific model/app - legacy route format."""
    try:
        result = DockerOperations.execute_action('start', model, app_num)
        if result['success']:
            from flask import jsonify
            return jsonify({
                'success': True,
                'message': f"Started containers for {model}/app{app_num}",
                'data': result
            })
        else:
            from flask import jsonify
            return jsonify({'success': False, 'error': result.get('error', 'Start operation failed')}), 500
    except Exception as e:
        logger.error(f"Docker start error: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500


@docker_main_bp.route("/docker/stop/<model>/<int:app_num>", methods=["POST"])
def docker_stop_action(model: str, app_num: int):
    """Stop containers for a specific model/app - legacy route format."""
    try:
        result = DockerOperations.execute_action('stop', model, app_num)
        if result['success']:
            from flask import jsonify
            return jsonify({
                'success': True,
                'message': f"Stopped containers for {model}/app{app_num}",
                'data': result
            })
        else:
            from flask import jsonify
            return jsonify({'success': False, 'error': result.get('error', 'Stop operation failed')}), 500
    except Exception as e:
        logger.error(f"Docker stop error: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500


@docker_main_bp.route("/docker/restart/<model>/<int:app_num>", methods=["POST"])
def docker_restart_action(model: str, app_num: int):
    """Restart containers for a specific model/app - legacy route format."""
    try:
        result = DockerOperations.execute_action('restart', model, app_num)
        if result['success']:
            from flask import jsonify
            return jsonify({
                'success': True,
                'message': f"Restarted containers for {model}/app{app_num}",
                'data': result
            })
        else:
            from flask import jsonify
            return jsonify({'success': False, 'error': result.get('error', 'Restart operation failed')}), 500
    except Exception as e:
        logger.error(f"Docker restart error: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500