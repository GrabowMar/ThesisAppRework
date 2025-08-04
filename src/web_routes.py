"""
Flask Web Routes - Thesis Research App
=====================================

Complete refactored implementation with consolidated code and improved organization.
All functionality preserved with enhanced logging and error handling.

Version: 3.0.0
"""

import json
import logging
import io
import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import (
    Blueprint, current_app, flash, jsonify, make_response, redirect,
    render_template, request, send_file, url_for, Response, g
)
from sqlalchemy import func

try:
    from extensions import db
    from models import (
        ModelCapability, GeneratedApplication, PortConfiguration,
        SecurityAnalysis, JobStatus, TaskStatus
    )
    from core_services import get_container_names
    from batch_testing_service import get_batch_testing_service
except ImportError:
    # Fallback for direct script execution
    from .extensions import db
    from .models import (
        ModelCapability, GeneratedApplication, PortConfiguration,
        SecurityAnalysis
    )
    from .core_services import get_container_names
    from .batch_testing_service import get_batch_testing_service

# Initialize logger
logger = logging.getLogger(__name__)

# ===========================
# PERFORMANCE LOGGING DECORATOR
# ===========================

def log_performance(operation_name: str = None):
    """Decorator to log performance metrics for routes and functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.time()
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            request_id = getattr(g, 'request_id', 'unknown')
            
            logger.info(f"Starting {op_name} [{request_id}]")
            
            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start_time) * 1000
                logger.info(f"Completed {op_name} [{request_id}] in {duration:.2f}ms")
                return result
                
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                logger.error(f"Failed {op_name} [{request_id}] after {duration:.2f}ms: {e}")
                raise
                
        return wrapper
    return decorator

# ===========================
# UTILITY CLASSES
# ===========================

class ResponseHandler:
    """Centralized response handling for HTMX and JSON responses with enhanced logging."""
    
    @staticmethod
    def is_htmx_request() -> bool:
        """Check if the request is from HTMX."""
        return request.headers.get('HX-Request') == 'true'
    
    @staticmethod
    def render_response(template_name: str, **context) -> Union[str, Response]:
        """Render appropriate response based on request type with timing."""
        start_time = time.time()
        
        try:
            if ResponseHandler.is_htmx_request():
                # For HTMX requests, check if partial is requested
                partial_type = request.args.get('partial')
                if partial_type:
                    # Use specific partial template
                    template_base = template_name.replace('.html', '')
                    result = render_template(f"partials/{template_base}_{partial_type}.html", **context)
                else:
                    # Use corresponding partial template
                    template_base = template_name.replace('.html', '')
                    result = render_template(f"partials/{template_base}.html", **context)
            else:
                result = render_template(f"pages/{template_name}", **context)
            
            # Log template rendering performance
            duration = (time.time() - start_time) * 1000
            logger.debug(f"Template {template_name} rendered in {duration:.2f}ms")
            
            return result
            
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            logger.error(f"Template rendering failed for {template_name} after {duration:.2f}ms: {e}")
            raise
    
    @staticmethod
    def error_response(error_msg: str, code: int = 500) -> Union[str, Response]:
        """Return error response for HTMX or JSON with enhanced logging."""
        request_id = getattr(g, 'request_id', 'unknown')
        logger.error(f"Error response [{request_id}]: {error_msg} (code: {code})")
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/error_message.html", error=error_msg), code
        return jsonify({
            'success': False, 
            'error': error_msg, 
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id
        }), code
    
    @staticmethod
    def success_response(data: Any = None, message: Optional[str] = None) -> Response:
        """Return success JSON response with request tracking."""
        request_id = getattr(g, 'request_id', 'unknown')
        if message:
            logger.info(f"Success response [{request_id}]: {message}")
            
        return jsonify({
            'success': True,
            'data': data,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id
        })
    
    @staticmethod
    def api_response(success: bool, data: Any = None, error: Optional[str] = None,
                    message: Optional[str] = None, code: int = 200) -> Tuple[Response, int]:
        """Create standardized API response with comprehensive logging."""
        request_id = getattr(g, 'request_id', 'unknown')
        
        if not success:
            logger.warning(f"API error response [{request_id}]: {error}")
        elif message:
            logger.info(f"API success response [{request_id}]: {message}")
            
        response_data = {
            'success': success,
            'data': data,
            'error': error,
            'message': message,
            'timestamp': datetime.now().isoformat(),
            'request_id': request_id
        }
        
        # Add retry information for error codes
        if not success and code in [429, 500, 502, 503, 504]:
            response_data['retryable'] = True
            retry_delays = {429: 60, 500: 30, 502: 60, 503: 60, 504: 120}
            response_data['retry_after'] = retry_delays.get(code, 30)
        
        response = jsonify(response_data)
        if 'retry_after' in response_data:
            response.headers['Retry-After'] = str(response_data['retry_after'])
            
        return response, code


class ServiceLocator:
    """Centralized service access."""
    
    @staticmethod
    def get_service(service_name: str):
        """Get service from app context or service manager."""
        # Direct app context check
        service = getattr(current_app, service_name, None)
        if service:
            return service
            
        # Service manager check
        service_manager = current_app.config.get('service_manager')
        if service_manager:
            return service_manager.get_service(service_name)
        return None
    
    @staticmethod
    def get_model_service():
        return ServiceLocator.get_service('model_service')
    
    @staticmethod
    def get_docker_manager():
        return ServiceLocator.get_service('docker_manager')
    
    @staticmethod
    def get_scan_manager():
        return ServiceLocator.get_service('scan_manager')
    
    @staticmethod
    def get_batch_service():
        return ServiceLocator.get_service('batch_service')


class DockerCache:
    """Thread-safe Docker container cache with automatic refresh."""
    
    def __init__(self, cache_duration: int = 10):  # 10 seconds cache
        self._cache = {}
        self._cache_timestamp = {}
        self._cache_duration = cache_duration
        self._lock = threading.RLock()
    
    def get_all_containers_cached(self, docker_manager) -> List[Any]:
        """Get all containers with caching."""
        with self._lock:
            now = datetime.now().timestamp()
            
            # Check if cache is still valid
            if ('all_containers' in self._cache and 
                'all_containers' in self._cache_timestamp and
                now - self._cache_timestamp['all_containers'] < self._cache_duration):
                return self._cache['all_containers']
            
            # Refresh cache
            try:
                if docker_manager and docker_manager.client:
                    containers = docker_manager.client.containers.list(all=True)
                    self._cache['all_containers'] = containers
                    self._cache_timestamp['all_containers'] = now
                    logger.info(f"Docker cache refreshed: {len(containers)} containers found")
                    return containers
                else:
                    return []
            except Exception as e:
                logger.warning(f"Failed to refresh Docker cache: {e}")
                # Return stale cache if available
                return self._cache.get('all_containers', [])
    
    def get_container_status_cached(self, docker_manager, container_name: str) -> str:
        """Get container status with caching."""
        with self._lock:
            now = datetime.now().timestamp()
            
            # Check if this specific container status is cached
            cache_key = f"status_{container_name}"
            if (cache_key in self._cache and 
                cache_key in self._cache_timestamp and
                now - self._cache_timestamp[cache_key] < self._cache_duration):
                return self._cache[cache_key]
            
            # Get status from all containers cache to avoid individual lookups
            all_containers = self.get_all_containers_cached(docker_manager)
            
            # Find container in cached list
            status = 'stopped'
            for container in all_containers:
                if container.name == container_name:
                    status = container.status
                    break
            
            # Cache the result
            self._cache[cache_key] = status
            self._cache_timestamp[cache_key] = now
            return status
    
    def bulk_get_container_statuses(self, docker_manager, container_names: List[str]) -> Dict[str, str]:
        """Get multiple container statuses efficiently."""
        with self._lock:
            # Get all containers once
            all_containers = self.get_all_containers_cached(docker_manager)
            
            # Create name to status mapping
            container_map = {container.name: container.status for container in all_containers}
            
            # Return statuses for requested containers
            result = {}
            for name in container_names:
                result[name] = container_map.get(name, 'stopped')
            
            # Update individual caches
            now = datetime.now().timestamp()
            for name, status in result.items():
                cache_key = f"status_{name}"
                self._cache[cache_key] = status
                self._cache_timestamp[cache_key] = now
            
            return result
    
    def invalidate(self):
        """Invalidate all cached data."""
        with self._lock:
            self._cache.clear()
            self._cache_timestamp.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for debugging."""
        with self._lock:
            now = datetime.now().timestamp()
            valid_entries = sum(1 for key, timestamp in self._cache_timestamp.items() 
                              if now - timestamp < self._cache_duration)
            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'cache_duration': self._cache_duration,
                'last_refresh': max(self._cache_timestamp.values()) if self._cache_timestamp else None
            }

# Global Docker cache instance
_docker_cache = DockerCache()


class AppDataProvider:
    """Centralized app data access and utilities."""
    
    # App type mapping
    APP_TYPES = {
        1: "Login System", 2: "Chat Application", 3: "Feedback System", 4: "Blog Platform",
        5: "E-commerce Cart", 6: "Note Taking", 7: "File Upload", 8: "Forum", 9: "CRUD Manager",
        10: "Microblog", 11: "Polling System", 12: "Reservation System", 13: "Photo Gallery",
        14: "Cloud Storage", 15: "Kanban Board", 16: "IoT Dashboard", 17: "Fitness Tracker",
        18: "Wiki", 19: "Crypto Wallet", 20: "Mapping App", 21: "Recipe Manager",
        22: "Learning Platform", 23: "Finance Tracker", 24: "Networking Tool", 25: "Health Monitor",
        26: "Environment Tracker", 27: "Team Management", 28: "Art Portfolio", 29: "Event Planner",
        30: "Research Collaboration"
    }
    
    @staticmethod
    def get_app_info(model: str, app_num: int) -> Dict[str, Any]:
        """Get comprehensive app information."""
        try:
            app = GeneratedApplication.query.filter_by(
                model_slug=model.replace('-', '_'),
                app_number=app_num
            ).first()
            
            if app:
                return {
                    'model': model,
                    'app_num': app_num,
                    'status': app.container_status or 'unknown',
                    'app_type': app.app_type or AppDataProvider.APP_TYPES.get(app_num, 'unknown'),
                    'provider': app.provider or 'unknown',
                    'has_backend': app.has_backend,
                    'has_frontend': app.has_frontend,
                    'metadata': app.get_metadata()
                }
        except Exception as e:
            logger.warning(f"Could not get app info: {e}")
        
        # Default response
        return {
            'model': model,
            'app_num': app_num,
            'status': 'unknown',
            'app_type': AppDataProvider.APP_TYPES.get(app_num, 'unknown'),
            'provider': 'unknown',
            'has_backend': True,
            'has_frontend': True,
            'metadata': {}
        }
    
    @staticmethod
    def get_port_config(model: str, app_num: int) -> Dict[str, int]:
        """Get port configuration for an app - DIRECT DB QUERY."""
        try:
            # Database format: anthropic_claude-3.7-sonnet (underscore between provider and model name)
            # URL format: anthropic-claude-3.7-sonnet (hyphens throughout)
            
            # Try direct database query first with the exact model slug
            config = PortConfiguration.query.filter_by(
                model=model,
                app_num=app_num
            ).first()
            
            if config:
                logger.debug(f"Found port config in DB for {model}/app{app_num}: frontend={config.frontend_port}, backend={config.backend_port}")
                return {
                    'backend_port': config.backend_port,
                    'frontend_port': config.frontend_port
                }
            
            # Transform URL format to database format
            # Convert slash to underscore (anthropic/claude-3.7-sonnet -> anthropic_claude-3.7-sonnet)
            db_format = model.replace('/', '_') if '/' in model else model
            
            config = PortConfiguration.query.filter_by(
                model=db_format,
                app_num=app_num
            ).first()
            
            if config:
                logger.debug(f"Found port config in DB for {db_format}/app{app_num} (original: {model}): frontend={config.frontend_port}, backend={config.backend_port}")
                return {
                    'backend_port': config.backend_port,
                    'frontend_port': config.frontend_port
                }
            
            # Try additional format variations for backward compatibility
            model_variations = [
                model.replace('/', '_'),  # Convert slashes to underscores  
                model.replace('-', '_'),  # Convert all hyphens to underscores
                model.replace('_', '-'),  # Convert all underscores to hyphens
            ]
            
            # Include sanitization function result
            try:
                from core_services import DockerUtils
                sanitized_model = DockerUtils.sanitize_project_name(model)
                model_variations.append(sanitized_model)
            except ImportError:
                pass
            
            for model_variant in model_variations:
                config = PortConfiguration.query.filter_by(
                    model=model_variant,
                    app_num=app_num
                ).first()
                
                if config:
                    logger.debug(f"Found port config in DB for {model_variant}/app{app_num} (original: {model}): frontend={config.frontend_port}, backend={config.backend_port}")
                    return {
                        'backend_port': config.backend_port,
                        'frontend_port': config.frontend_port
                    }
                
        except Exception as e:
            logger.warning(f"Error querying port config from DB for {model}/app{app_num}: {e}")
        
        # Default calculation fallback
        logger.debug(f"Using calculated port config for {model}/app{app_num}")
        return {
            'backend_port': 6000 + (app_num * 10),
            'frontend_port': 9000 + (app_num * 10)
        }
    
    @staticmethod
    def get_container_statuses(model: str, app_num: int) -> Dict[str, str]:
        """Get container statuses for an app using optimized caching."""
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return {'backend': 'unknown', 'frontend': 'unknown'}
        
        try:
            # First try the proper container naming function from core_services
            container_names = get_container_names(model, app_num)
            if container_names:
                backend_name = container_names['backend']
                frontend_name = container_names['frontend']
            else:
                # Fallback: Convert model slug to Docker container naming format
                container_model_name = model.replace('-', '_').replace('.', '_')
                
                # Use cache to find containers by pattern
                all_containers = _docker_cache.get_all_containers_cached(docker_manager)
                backend_name = None
                frontend_name = None
                
                pattern_prefix = f"{container_model_name}_app{app_num}_"
                for container in all_containers:
                    if container.name.startswith(pattern_prefix):
                        if '_backend_' in container.name:
                            backend_name = container.name
                        elif '_frontend_' in container.name:
                            frontend_name = container.name
                
                # Fallback names if not found
                if not backend_name:
                    backend_name = f"{container_model_name}_app{app_num}_backend"
                if not frontend_name:
                    frontend_name = f"{container_model_name}_app{app_num}_frontend"
            
            # Use bulk status lookup for better performance
            container_names_list = [backend_name, frontend_name]
            statuses = _docker_cache.bulk_get_container_statuses(docker_manager, container_names_list)
            
            return {
                'backend': statuses.get(backend_name, 'stopped'),
                'frontend': statuses.get(frontend_name, 'stopped')
            }
        except Exception as e:
            logger.error(f"Error getting container statuses for {model}/app{app_num}: {e}")
            return {'backend': 'error', 'frontend': 'error'}
    
    @staticmethod
    def get_all_apps() -> List[Dict[str, Any]]:
        """Get all applications with their status."""
        try:
            apps = []
            db_apps = GeneratedApplication.query.all()
            
            for app in db_apps:
                apps.append({
                    'model': app.model_slug.replace('_', '-'),
                    'app_num': app.app_number,
                    'status': app.container_status or 'unknown',
                    'app_type': app.app_type or AppDataProvider.APP_TYPES.get(app.app_number, 'unknown'),
                    'provider': app.provider or 'unknown'
                })
            
            return apps
        except Exception as e:
            logger.warning(f"Could not get apps from database: {e}")
            return []
    
    @staticmethod
    def get_app_for_dashboard(model_slug: str, app_num: int) -> Dict[str, Any]:
        """Get complete app data for dashboard display."""
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Get container status
        status = 'stopped'
        frontend_status = 'stopped'
        backend_status = 'stopped'
        
        if docker_manager:
            try:
                statuses = AppDataProvider.get_container_statuses(model_slug, app_num)
                backend_status = statuses.get('backend', 'stopped')
                frontend_status = statuses.get('frontend', 'stopped')
                
                if backend_status == 'running' and frontend_status == 'running':
                    status = 'running'
                elif backend_status in ['exited', 'dead'] or frontend_status in ['exited', 'dead']:
                    status = 'error'
                else:
                    status = 'stopped'
            except Exception:
                status = 'stopped'
        
        port_config = AppDataProvider.get_port_config(model_slug, app_num)
        
        return {
            'app_number': app_num,
            'app_name': f"App {app_num}",
            'app_type': AppDataProvider.APP_TYPES.get(app_num, 'Unknown'),
            'description': f"{AppDataProvider.APP_TYPES.get(app_num, 'Unknown')} - Generated by {model_slug}",
            'status': status,
            'frontend_port': port_config.get('frontend_port'),
            'backend_port': port_config.get('backend_port'),
            'containers': {
                'frontend_status': frontend_status,
                'backend_status': backend_status,
                'database_status': 'unknown'
            }
        }


class DockerOperations:
    """Centralized Docker operations."""
    
    @staticmethod
    def execute_action(action: str, model: str, app_num: int) -> Dict[str, Any]:
        """Execute a Docker action on an app."""
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return {'success': False, 'error': 'Docker manager not available'}
        
        try:
            # Get compose file path
            project_root = Path(__file__).parent.parent
            compose_path = project_root / "misc" / "models" / model / f"app{app_num}" / "docker-compose.yml"
            
            if not compose_path.exists():
                return {'success': False, 'error': f'Docker compose file not found'}
            
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
            
            return {'success': False, 'error': error_msg}
    
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
    def bulk_action(action: str, apps: List[Tuple[str, int]], max_workers: int = 2) -> Dict[str, Any]:
        """Execute bulk Docker action."""
        results = []
        successful = 0
        
        for model, app_num in apps:
            try:
                result = DockerOperations.execute_action(action, model, app_num)
                if result['success']:
                    successful += 1
                results.append({
                    'model': model,
                    'app_num': app_num,
                    'success': result['success'],
                    'message': result.get('message', result.get('error', 'Unknown result'))
                })
            except Exception as e:
                results.append({
                    'model': model,
                    'app_num': app_num,
                    'success': False,
                    'message': str(e)
                })
        
        return {
            'results': results,
            'total': len(results),
            'successful': successful,
            'failed': len(results) - successful
        }


class FileOperations:
    """File handling utilities."""
    
    @staticmethod
    def get_file_icon(extension: str) -> str:
        """Get appropriate icon for file extension."""
        icon_map = {
            '.py': 'fab fa-python',
            '.js': 'fab fa-js-square',
            '.ts': 'fab fa-js-square',
            '.jsx': 'fab fa-react',
            '.tsx': 'fab fa-react',
            '.html': 'fab fa-html5',
            '.css': 'fab fa-css3-alt',
            '.scss': 'fab fa-sass',
            '.json': 'fas fa-code',
            '.yml': 'fas fa-file-code',
            '.yaml': 'fas fa-file-code',
            '.md': 'fab fa-markdown',
            '.txt': 'fas fa-file-alt',
            '.dockerfile': 'fab fa-docker',
            '.gitignore': 'fab fa-git-alt',
            '.env': 'fas fa-cog'
        }
        return icon_map.get(extension.lower(), 'fas fa-file')
    
    @staticmethod
    def get_language_from_extension(extension: str) -> str:
        """Get language identifier for syntax highlighting."""
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.yml': 'yaml',
            '.yaml': 'yaml',
            '.md': 'markdown',
            '.dockerfile': 'dockerfile',
            '.sh': 'bash',
            '.sql': 'sql'
        }
        return language_map.get(extension.lower(), 'text')


# ===========================
# BLUEPRINT DEFINITIONS
# ===========================

main_bp = Blueprint("main", __name__)
api_bp = Blueprint("api", __name__, url_prefix="/api")
statistics_bp = Blueprint("statistics", __name__, url_prefix="/statistics")
batch_bp = Blueprint("batch", __name__, url_prefix="/batch")
docker_bp = Blueprint("docker", __name__, url_prefix="/docker")
batch_testing_bp = Blueprint("batch_testing", __name__, url_prefix="/batch-testing")

# ===========================
# MAIN ROUTES
# ===========================

@main_bp.route("/", endpoint='dashboard')
@log_performance("dashboard_load")
def dashboard():
    """Modern dashboard with expandable model tabs."""
    try:
        logger.info("Loading dashboard with model statistics")
        models = ModelCapability.query.all()
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Calculate statistics
        stats = {
            'total_models': len(models),
            'total_apps': len(models) * 30,
            'running_containers': 0,
            'error_containers': 0,
            'total_providers': len(set(m.provider for m in models)),
            'analyzed_apps': 0,
            'performance_tested': 0,
            'docker_health': 'Healthy' if docker_manager else 'Unavailable'
        }
        
        # Sample container status check for efficiency
        if docker_manager and models:
            logger.debug(f"Checking container status for {len(models)} models")
            sample_models = models[:3]
            checked_containers = 0
            
            for model in sample_models:
                for app_num in range(1, 6):
                    try:
                        statuses = AppDataProvider.get_container_statuses(model.canonical_slug, app_num)
                        checked_containers += 1
                        
                        if statuses.get('backend') == 'running' and statuses.get('frontend') == 'running':
                            stats['running_containers'] += 1
                        elif statuses.get('backend') in ['exited', 'dead'] or statuses.get('frontend') in ['exited', 'dead']:
                            stats['error_containers'] += 1
                    except Exception as e:
                        logger.debug(f"Container status check failed for {model.canonical_slug}/app{app_num}: {e}")
                        pass
            
            # Scale up estimates
            if len(sample_models) > 0:
                scale_factor = len(models) / len(sample_models) * 6
                stats['running_containers'] = int(stats['running_containers'] * scale_factor)
                stats['error_containers'] = int(stats['error_containers'] * scale_factor)
                logger.debug(f"Checked {checked_containers} containers, scaled estimates: running={stats['running_containers']}, errors={stats['error_containers']}")
        else:
            logger.warning("Docker manager unavailable or no models found for dashboard")
        
        logger.info(f"Dashboard loaded successfully with {stats['total_models']} models")
        return render_template('pages/dashboard.html', summary_stats=stats)
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        from datetime import datetime
        return render_template("pages/error.html", 
                             error=str(e), 
                             timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             error_code=500)


@main_bp.route("/batch-testing")
def batch_testing():
    """Redirect to batch testing dashboard."""
    return redirect("/batch-testing/")


@main_bp.route("/dashboard", endpoint='dashboard_redirect')
def dashboard_redirect():
    """Dashboard page - serve dashboard content directly."""
    # Call the dashboard function directly to avoid redirect
    return dashboard()


@main_bp.route("/docker")
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


@main_bp.route("/app/<model>/<int:app_num>")
def app_details(model: str, app_num: int):
    """Application details page - redirects to overview sub-page."""
    try:
        # Decode URL-encoded model name
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        # Redirect to overview sub-page by default
        return redirect(url_for("main.app_overview", model=decoded_model, app_num=app_num))
        
    except Exception as e:
        logger.error(f"Error redirecting to app overview: {e}")
        return ResponseHandler.error_response(f"Failed to redirect to app overview: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/overview")
def app_overview(model: str, app_num: int):
    """Application overview sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        # Get app info
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        # Get container statuses
        container_statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        container_status = container_statuses.get('overall_status', 'unknown')
        
        # Get port information from database
        port_config = PortConfiguration.query.filter_by(
            model=decoded_model, 
            app_num=app_num
        ).first()
        
        if port_config:
            port_info = {
                'frontend': port_config.frontend_port,
                'backend': port_config.backend_port
            }
        else:
            port_info = {
                'frontend': None,
                'backend': None
            }
        
        # Get generated application info
        generated_app = GeneratedApplication.query.filter_by(
            model_slug=decoded_model,
            app_number=app_num
        ).first()
        
        # Prepare context with all required variables
        context = {
            'app_info': app_info,
            'container_statuses': container_statuses,
            'container_status': container_status,
            'port_info': port_info,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'overview',
            # Additional context for template
            'security_stats': {'total_issues': 0},  # Placeholder
            'performance_stats': {'score': 'N/A'},   # Placeholder  
            'file_stats': {'total_files': 0}         # Placeholder
        }
        
        # Add generated app info if available
        if generated_app:
            context['generated_app'] = generated_app
            context['app_info'].update({
                'app_type': generated_app.app_type,
                'provider': generated_app.provider,
                'has_backend': generated_app.has_backend,
                'has_frontend': generated_app.has_frontend,
                'backend_framework': generated_app.backend_framework,
                'frontend_framework': generated_app.frontend_framework,
                'created_date': generated_app.created_at.strftime('%Y-%m-%d') if generated_app.created_at else None,
                'last_modified': generated_app.updated_at.strftime('%Y-%m-%d') if generated_app.updated_at else None
            })
        
        return render_template("pages/app_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app overview: {e}")
        return ResponseHandler.error_response(f"Failed to load app overview: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/docker")
def app_docker(model: str, app_num: int):
    """Application Docker containers sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        container_statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        
        context = {
            'app_info': app_info,
            'container_statuses': container_statuses,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'docker'
        }
        
        return render_template("pages/app_docker.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app docker page: {e}")
        return ResponseHandler.error_response(f"Failed to load app docker page: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/analysis")
def app_analysis(model: str, app_num: int):
    """Application security analysis sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        container_statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        
        context = {
            'app_info': app_info,
            'container_statuses': container_statuses,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'analysis'
        }
        
        return render_template("pages/app_analysis.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app analysis page: {e}")
        return ResponseHandler.error_response(f"Failed to load app analysis page: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/performance")
def app_performance(model: str, app_num: int):
    """Application performance testing sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        container_statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        
        # Add performance-specific data
        context = {
            'app_info': app_info,
            'container_statuses': container_statuses,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'performance'
        }
        
        try:
            # Performance service is now containerized
            context['performance_available'] = False  # Will be enabled when containers are available
            context['existing_results'] = None
            context['has_results'] = False
        except Exception:
            context['performance_available'] = False
            context['existing_results'] = None
            context['has_results'] = False
        
        return render_template("pages/app_performance.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app performance page: {e}")
        return ResponseHandler.error_response(f"Failed to load app performance page: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/files")
def app_files(model: str, app_num: int):
    """Application files browser sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        context = {
            'app_info': app_info,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'files'
        }
        
        return render_template("pages/app_files.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app files page: {e}")
        return ResponseHandler.error_response(f"Failed to load app files page: {str(e)}")


@main_bp.route("/app/<model>/<int:app_num>/tests")
def app_tests(model: str, app_num: int):
    """Application tests runner sub-page."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        app_info = AppDataProvider.get_app_info(decoded_model, app_num)
        if not app_info:
            flash(f"Application {decoded_model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        container_statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        
        context = {
            'app_info': app_info,
            'container_statuses': container_statuses,
            'model': decoded_model,
            'app_num': app_num,
            'current_page': 'tests'
        }
        
        return render_template("pages/app_tests.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app tests page: {e}")
        return ResponseHandler.error_response(f"Failed to load app tests page: {str(e)}")


@main_bp.route("/models")
def models_overview():
    """Models overview page with comprehensive filtering."""
    try:
        # Get query parameters
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '').strip()
        sort_by = request.args.get('sort', 'model_name')
        
        # Build query
        query = ModelCapability.query
        
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                ModelCapability.model_name.ilike(pattern) |
                ModelCapability.model_id.ilike(pattern) |
                ModelCapability.provider.ilike(pattern)
            )
        
        if provider:
            query = query.filter_by(provider=provider)
        
        # Apply sorting
        sort_map = {
            'provider': ModelCapability.provider,
            'context_window': ModelCapability.context_window.desc(),
            'input_price': ModelCapability.input_price_per_token.asc(),
            'output_price': ModelCapability.output_price_per_token.asc(),
            'safety_score': ModelCapability.safety_score.desc(),
            'cost_efficiency': ModelCapability.cost_efficiency.desc()
        }
        query = query.order_by(sort_map.get(sort_by, ModelCapability.model_name))
        
        models = query.all()
        
        # Get unique providers
        providers = db.session.query(ModelCapability.provider).distinct().order_by(ModelCapability.provider).all()
        providers = [p.provider for p in providers]
        
        # Get app statistics
        app_stats = db.session.query(
            GeneratedApplication.model_slug,
            func.count(GeneratedApplication.id).label('total_apps'),
            func.count(func.nullif(GeneratedApplication.generation_status, 'pending')).label('generated_apps'),
            func.count(func.nullif(GeneratedApplication.container_status, 'stopped')).label('running_containers')
        ).group_by(GeneratedApplication.model_slug).all()
        
        app_stats_dict = {stat.model_slug: stat for stat in app_stats}
        
        # Enhance models with statistics
        enhanced_models = []
        for model in models:
            model_data = model.to_dict()
            
            # Add app statistics
            if model.canonical_slug in app_stats_dict:
                stat = app_stats_dict[model.canonical_slug]
                model_data.update({
                    'total_apps': stat.total_apps,
                    'generated_apps': stat.generated_apps,
                    'running_containers': stat.running_containers
                })
            else:
                model_data.update({
                    'total_apps': 0,
                    'generated_apps': 0,
                    'running_containers': 0
                })
            
            enhanced_models.append(model_data)
        
        # Calculate summary statistics
        summary_stats = {
            'total_models': len(enhanced_models),
            'total_providers': len(providers),
            'total_apps': sum(m.get('total_apps', 0) for m in enhanced_models),
            'total_running': sum(m.get('running_containers', 0) for m in enhanced_models),
            'vision_models': sum(1 for m in enhanced_models if m.get('supports_vision')),
            'function_calling_models': sum(1 for m in enhanced_models if m.get('supports_function_calling')),
            'free_models': sum(1 for m in enhanced_models if m.get('is_free')),
            'avg_context_window': sum(m.get('context_window', 0) for m in enhanced_models) // max(1, len(enhanced_models))
        }
        
        context = {
            'models': enhanced_models,
            'providers': providers,
            'summary_stats': summary_stats,
            'search_query': search,
            'provider_filter': provider,
            'sort_by': sort_by
        }
        
        return ResponseHandler.render_response("models_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading models: {e}", exc_info=True)
        return ResponseHandler.error_response(str(e))


# ===========================
# API ROUTES - Dashboard
# ===========================

@api_bp.route("/dashboard/models")
def api_dashboard_models():
    """Get models data for dashboard grid."""
    try:
        models = ModelCapability.query.all()
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Enhance model objects with container statistics
        for model in models:
            # Get container statistics
            running_containers = 0
            stopped_containers = 0
            error_containers = 0
            
            if docker_manager:
                # Sample first 5 apps for performance
                for app_num in range(1, 6):
                    try:
                        statuses = AppDataProvider.get_container_statuses(model.canonical_slug, app_num)
                        backend = statuses.get('backend', 'stopped')
                        frontend = statuses.get('frontend', 'stopped')
                        
                        if backend == 'running' and frontend == 'running':
                            running_containers += 1
                        elif backend in ['exited', 'dead'] or frontend in ['exited', 'dead']:
                            error_containers += 1
                        else:
                            stopped_containers += 1
                    except Exception:
                        stopped_containers += 1
                
                # Scale up estimates
                running_containers = running_containers * 6
                stopped_containers = stopped_containers * 6
                error_containers = error_containers * 6
            else:
                stopped_containers = 30
            
            # Add container statistics as attributes for template access
            model.total_apps = 30
            model.running_containers = running_containers
            model.stopped_containers = stopped_containers
            model.error_containers = error_containers
        
        return render_template('partials/dashboard_models_grid.html', models=models)
        
    except Exception as e:
        logger.error(f"Error fetching dashboard models: {e}")
        return f"<div class='error-state'>Error loading models: {str(e)}</div>", 500


@api_bp.route("/model/<model_slug>/apps")
def api_model_apps(model_slug: str):
    """Get applications for a specific model."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        # Import and use the sanitization function from core_services
        try:
            from core_services import DockerUtils
            sanitized_model = DockerUtils.sanitize_project_name(decoded_model_slug)
        except ImportError:
            # Fallback sanitization
            import re
            sanitized_model = decoded_model_slug.lower()
            sanitized_model = re.sub(r'[^a-z0-9_-]', '_', sanitized_model)
            sanitized_model = re.sub(r'[_-]+', '_', sanitized_model).strip('_-')
        
        # Try to find model by canonical slug using sanitized slug first
        model = ModelCapability.query.filter_by(canonical_slug=sanitized_model).first()
        
        if not model:
            # Try variations for backward compatibility  
            model_variations = [
                decoded_model_slug,  # Original decoded slug
                decoded_model_slug.replace('-', '_'),  # Convert hyphens to underscores
                decoded_model_slug.replace('_', '-'),  # Convert underscores to hyphens
                decoded_model_slug.replace('/', '_'),  # Convert slashes to underscores
            ]
            
            for variant in model_variations:
                model = ModelCapability.query.filter_by(canonical_slug=variant).first()
                if model:
                    logger.debug(f"Found model using variant: {variant} (original: {decoded_model_slug})")
                    break
            
        if not model:
            logger.warning(f"Model not found for slug: {decoded_model_slug} (sanitized: {sanitized_model})")
            return ResponseHandler.error_response('Model not found', 404)
        
        # Use the actual canonical slug from the database for consistency
        model_slug_for_lookup = model.canonical_slug
        
        apps_data = []
        for app_num in range(1, 31):
            app_data = AppDataProvider.get_app_for_dashboard(model_slug_for_lookup, app_num)
            apps_data.append(app_data)
        
        return render_template('partials/model_apps_table.html', 
                             apps=apps_data, 
                             model_slug=model_slug_for_lookup)
        
    except Exception as e:
        logger.error(f"Error loading apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/stats")
def api_model_stats(model_slug: str):
    """Get container statistics for a specific model with optimized Docker lookups."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        model = ModelCapability.query.filter_by(canonical_slug=decoded_model_slug).first()
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Initialize counters
        running_count = 0
        stopped_count = 0
        error_count = 0
        
        # Optimized container status checking using bulk operations
        if docker_manager:
            try:
                # Get all containers once via cache
                all_containers = _docker_cache.get_all_containers_cached(docker_manager)
                
                # Create a mapping of container names to their statuses
                container_map = {container.name: container.status for container in all_containers}
                
                # Convert model slug to Docker container naming format
                container_model_name = model_slug.replace('-', '_').replace('.', '_')
                
                # Check all 30 apps efficiently
                for app_num in range(1, 31):
                    try:
                        # Generate expected container names
                        pattern_prefix = f"{container_model_name}_app{app_num}_"
                        
                        # Find actual container names from pattern
                        backend_name = None
                        frontend_name = None
                        
                        for container_name in container_map.keys():
                            if container_name.startswith(pattern_prefix):
                                if '_backend_' in container_name:
                                    backend_name = container_name
                                elif '_frontend_' in container_name:
                                    frontend_name = container_name
                        
                        # Use fallback naming if not found
                        if not backend_name:
                            backend_name = f"{container_model_name}_app{app_num}_backend"
                        if not frontend_name:
                            frontend_name = f"{container_model_name}_app{app_num}_frontend"
                        
                        # Get statuses from cached mapping
                        backend_status = container_map.get(backend_name, 'stopped')
                        frontend_status = container_map.get(frontend_name, 'stopped')
                        
                        # Count containers by status
                        for status in [backend_status, frontend_status]:
                            if status == 'running':
                                running_count += 1
                            elif status in ['exited', 'stopped']:
                                stopped_count += 1
                            elif status in ['error', 'unhealthy']:
                                error_count += 1
                            else:
                                # Unknown status, count as stopped
                                stopped_count += 1
                                
                    except Exception as app_error:
                        logger.debug(f"Error checking app {app_num} for model {model_slug}: {app_error}")
                        # Count as error if we can't determine status
                        error_count += 2  # Both frontend and backend
                        
            except Exception as docker_error:
                logger.error(f"Docker error for model {model_slug}: {docker_error}")
                # Docker not available, count all as stopped
                stopped_count = 30 * 2  # 30 apps * 2 containers each
        else:
            # Docker not available, count all as stopped
            stopped_count = 30 * 2  # 30 apps * 2 containers each
        
        stats = {
            'running': running_count,
            'stopped': stopped_count,
            'error': error_count,
            'total': 60  # 30 apps * 2 containers each
        }
        
        logger.debug(f"Model {model_slug} stats: {stats}")
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting stats for model {model_slug}: {e}")
        return jsonify({
            'running': 0,
            'stopped': 0,
            'error': 0,
            'total': 60
        }), 500


@api_bp.route("/docker/cache/refresh", methods=["POST"])
def api_refresh_docker_cache():
    """Manually refresh the Docker cache."""
    try:
        _docker_cache.invalidate()
        return jsonify({
            'success': True,
            'message': 'Docker cache refreshed',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error refreshing Docker cache: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/docker/cache/stats")
def api_docker_cache_stats():
    """Get Docker cache statistics."""
    try:
        cache_stats = _docker_cache.get_cache_stats()
        return jsonify({
            'success': True,
            'cache_stats': cache_stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/containers/stats")
def containers_stats():
    """Get container statistics for the batch testing dashboard."""
    try:
        from batch_testing_service import get_batch_testing_service
        service = get_batch_testing_service()
        
        stats = service.get_container_stats()
        return jsonify({
            'success': True,
            'stats': stats,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting container stats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/containers/overview")
def containers_overview():
    """Get container overview for the batch testing dashboard."""
    try:
        from batch_testing_service import get_batch_testing_service
        service = get_batch_testing_service()
        
        # Get available models and their container status
        models = service.get_available_models()
        
        overview = {
            'total_models': len(models),
            'models': models,
            'container_ecosystem': service.get_container_stats()
        }
        
        return jsonify({
            'success': True,
            'overview': overview,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting container overview: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@api_bp.route("/dashboard/stats")
def dashboard_stats():
    """Get dashboard statistics."""
    try:
        models = ModelCapability.query.all()
        docker_manager = ServiceLocator.get_docker_manager()
        
        stats = {
            'total_models': len(models),
            'total_apps': len(models) * 30,
            'running_containers': 0,
            'error_containers': 0,
            'total_providers': len(set(m.provider for m in models)),
            'docker_health': 'Healthy' if docker_manager else 'Unavailable'
        }
        
        return ResponseHandler.success_response(data=stats)
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/details")
@api_bp.route("/models/<model_slug>/details")
def api_model_details(model_slug: str):
    """Get detailed information about a model."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        model = ModelCapability.query.filter_by(canonical_slug=decoded_model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        # Get model capabilities and statistics
        capabilities = model.get_capabilities() if hasattr(model, 'get_capabilities') else {}
        metadata = model.get_metadata() if hasattr(model, 'get_metadata') else {}
        
        # Extract detailed information from capabilities
        pricing = capabilities.get('pricing', {})
        performance = capabilities.get('performance', {})
        architecture = capabilities.get('architecture', {})
        features = capabilities.get('features', {})
        
        details = {
            'model_name': model.model_name,
            'display_name': model.model_name,
            'provider': model.provider,
            'canonical_slug': model.canonical_slug,
            'is_free': model.is_free,
            'context_window': model.context_window,
            'max_output_tokens': model.max_output_tokens,
            'supports_function_calling': model.supports_function_calling,
            'supports_vision': model.supports_vision,
            'supports_streaming': model.supports_streaming,
            'supports_json_mode': model.supports_json_mode,
            'input_price_per_token': model.input_price_per_token,
            'output_price_per_token': model.output_price_per_token,
            'cost_efficiency': model.cost_efficiency,
            'safety_score': model.safety_score,
            'capabilities': capabilities,
            'metadata': metadata,
            'pricing': pricing,
            'performance': performance,
            'architecture': architecture,
            'features': features,
            'total_apps': 30,
            'created_at': model.created_at.isoformat() if model.created_at else None,
            'updated_at': model.updated_at.isoformat() if model.updated_at else None
        }
        
        if ResponseHandler.is_htmx_request():
            # Get container statistics for this model
            running_count = 0
            stopped_count = 0
            error_count = 0
            
            docker_manager = ServiceLocator.get_docker_manager()
            if docker_manager:
                try:
                    # Sample first 5 apps to get status estimates
                    for app_num in range(1, 6):
                        try:
                            statuses = AppDataProvider.get_container_statuses(decoded_model_slug, app_num)
                            backend = statuses.get('backend', 'stopped')
                            frontend = statuses.get('frontend', 'stopped')
                            
                            if backend == 'running' and frontend == 'running':
                                running_count += 1
                            elif backend in ['exited', 'dead'] or frontend in ['exited', 'dead']:
                                error_count += 1
                            else:
                                stopped_count += 1
                        except Exception:
                            stopped_count += 1
                    
                    # Scale up estimates for all 30 apps
                    running_count = running_count * 6
                    stopped_count = stopped_count * 6
                    error_count = error_count * 6
                except Exception as e:
                    logger.warning(f"Failed to get container stats for {decoded_model_slug}: {e}")
                    stopped_count = 30
            else:
                stopped_count = 30
            
            return render_template('partials/model_details_content.html', 
                                 model=model, 
                                 details=details,
                                 running_count=running_count,
                                 stopped_count=stopped_count,
                                 error_count=error_count)
        
        return ResponseHandler.success_response(data=details)
        
    except Exception as e:
        logger.error(f"Error getting model details for {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/start-all", methods=["POST"])
def api_model_start_all(model_slug: str):
    """Start all containers for a model."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        model = ModelCapability.query.filter_by(canonical_slug=decoded_model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Start all 30 apps for this model
        apps_to_start = [(decoded_model_slug, app_num) for app_num in range(1, 31)]
        result = DockerOperations.bulk_action('start', apps_to_start, max_workers=3)
        
        if ResponseHandler.is_htmx_request():
            # Return updated model card
            return api_dashboard_models()
        
        return ResponseHandler.success_response(data=result, 
                                               message=f"Started all apps for {model.model_name}")
        
    except Exception as e:
        logger.error(f"Error starting all apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/stop-all", methods=["POST"])
def api_model_stop_all(model_slug: str):
    """Stop all containers for a model."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        model = ModelCapability.query.filter_by(canonical_slug=decoded_model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Stop all 30 apps for this model
        apps_to_stop = [(decoded_model_slug, app_num) for app_num in range(1, 31)]
        result = DockerOperations.bulk_action('stop', apps_to_stop, max_workers=3)
        
        if ResponseHandler.is_htmx_request():
            # Return updated model card
            return api_dashboard_models()
        
        return ResponseHandler.success_response(data=result, 
                                               message=f"Stopped all apps for {model.model_name}")
        
    except Exception as e:
        logger.error(f"Error stopping all apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/restart-all", methods=["POST"])
def api_model_restart_all(model_slug: str):
    """Restart all containers for a model."""
    try:
        # Decode URL-encoded model slug
        import urllib.parse
        decoded_model_slug = urllib.parse.unquote(model_slug)
        
        model = ModelCapability.query.filter_by(canonical_slug=decoded_model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Restart all 30 apps for this model
        apps_to_restart = [(decoded_model_slug, app_num) for app_num in range(1, 31)]
        result = DockerOperations.bulk_action('restart', apps_to_restart, max_workers=3)
        
        if ResponseHandler.is_htmx_request():
            # Return updated model card
            return api_dashboard_models()
        
        return ResponseHandler.success_response(data=result, 
                                               message=f"Restarted all apps for {model.model_name}")
        
    except Exception as e:
        logger.error(f"Error restarting all apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/analyze-all", methods=["POST"])
def api_model_analyze_all(model_slug: str):
    """Run security analysis on all apps for a model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        scan_manager = ServiceLocator.get_scan_manager()
        if not scan_manager:
            return ResponseHandler.error_response('Scan manager not available')
        
        # Queue analysis for all 30 apps
        analysis_jobs = []
        for app_num in range(1, 31):
            try:
                job_id = scan_manager.queue_analysis(model_slug, app_num, 'backend_security')
                if job_id:
                    analysis_jobs.append(job_id)
            except Exception as job_error:
                logger.warning(f"Failed to queue analysis for {model_slug} app {app_num}: {job_error}")
        
        if ResponseHandler.is_htmx_request():
            # Return updated model card
            return api_dashboard_models()
        
        return ResponseHandler.success_response(
            data={'queued_jobs': len(analysis_jobs), 'job_ids': analysis_jobs},
            message=f"Queued {len(analysis_jobs)} analysis jobs for {model.model_name}"
        )
        
    except Exception as e:
        logger.error(f"Error analyzing all apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# API ROUTES - Sidebar & System
# ===========================

@api_bp.route("/sidebar/stats")
def sidebar_stats():
    """Get sidebar statistics."""
    try:
        model_count = ModelCapability.query.count()
        app_count = model_count * 30
        running_count = 0  # Calculate based on Docker status
        active_scans = 0  # Calculate based on active analyses
        
        if ResponseHandler.is_htmx_request():
            return render_template('partials/sidebar_stats.html',
                                 model_count=model_count,
                                 app_count=app_count,
                                 running_count=running_count,
                                 active_scans=active_scans)
        
        stats = {
            'total_models': model_count,
            'total_apps': app_count,
            'running_containers': running_count,
            'active_scans': active_scans
        }
        return ResponseHandler.success_response(data=stats)
    except Exception as e:
        logger.error(f"Sidebar stats error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/sidebar/activity")
def sidebar_activity():
    """Get recent activity."""
    try:
        # Mock activity data - replace with actual activity tracking
        activities = [
            {
                "content": "Container started: anthropic/app1",
                "time": "2 min ago",
                "icon": "fas fa-play text-success"
            },
            {
                "content": "Analysis completed: openai/app5",
                "time": "5 min ago",
                "icon": "fas fa-check text-success"
            }
        ]
        
        if ResponseHandler.is_htmx_request():
            return render_template('partials/sidebar_activity.html', activities=activities)
        
        return ResponseHandler.success_response(data=activities)
    except Exception as e:
        logger.error(f"Sidebar activity error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/sidebar/system-status")
def sidebar_system_status():
    """Get system status."""
    try:
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Create status list for template
        statuses = [
            {
                "label": "Database",
                "status": "success"  # Map to CSS class: status-success
            },
            {
                "label": "Docker", 
                "status": "success" if docker_manager else "warning"
            },
            {
                "label": "Services",
                "status": "success"
            }
        ]
        
        if ResponseHandler.is_htmx_request():
            return render_template('partials/sidebar_system_status.html', statuses=statuses)
        
        # Return legacy format for JSON API
        status = {
            'docker': 'healthy' if docker_manager else 'unavailable',
            'database': 'healthy',
            'services': 'healthy'
        }
        return ResponseHandler.success_response(data=status)
    except Exception as e:
        logger.error(f"System status error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/settings")
def get_settings():
    """Get application settings."""
    try:
        settings = {
            'theme': 'light',
            'auto_refresh': True,
            'notifications': True
        }
        return ResponseHandler.success_response(data=settings)
    except Exception as e:
        logger.error(f"Settings error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/notifications/count")
def notifications_count():
    """Get notification count."""
    try:
        # Mock notification count - replace with actual notification system
        count = 3
        return ResponseHandler.success_response(data={'count': count})
    except Exception as e:
        logger.error(f"Notifications count error: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# API ROUTES - Container Operations
# ===========================

@api_bp.route("/containers/<model>/<int:app_num>/<action>", methods=["POST"])
def container_action(model: str, app_num: int, action: str):
    """Execute container action."""
    try:
        # Decode URL-encoded model name
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        valid_actions = ['start', 'stop', 'restart', 'build']
        if action not in valid_actions:
            return ResponseHandler.error_response(f"Invalid action: {action}", 400)
        
        result = DockerOperations.execute_action(action, decoded_model, app_num)
        
        if result['success']:
            # For HTMX requests, return updated UI component
            if ResponseHandler.is_htmx_request():
                # Check the request context to determine response type
                referrer = request.referrer or ''
                
                if 'dashboard' in referrer:
                    # Return updated dashboard row
                    app_data = AppDataProvider.get_app_for_dashboard(decoded_model, app_num)
                    return render_template("partials/app_table_row.html", 
                                         app=app_data, model_slug=decoded_model, show_error=False)
                else:
                    # Return updated status badge for app list
                    statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
                    return render_template("partials/app_status_badge.html",
                                         statuses=statuses, model=decoded_model, app_num=app_num)
            
            # JSON response
            return ResponseHandler.success_response(
                data={'statuses': AppDataProvider.get_container_statuses(decoded_model, app_num)},
                message=result.get('message', f'{action} successful')
            )
        else:
            # Handle errors
            if ResponseHandler.is_htmx_request():
                referrer = request.referrer or ''
                
                if 'dashboard' in referrer:
                    # Return error row for dashboard
                    app_data = AppDataProvider.get_app_for_dashboard(decoded_model, app_num)
                    app_data['status'] = 'ERROR'
                    app_data['error_message'] = result.get('error')
                    return render_template('partials/app_table_row_error.html',
                                         app=app_data, model_slug=decoded_model, show_error=True)
                else:
                    # Return error status badge for app list
                    return render_template("partials/app_status_badge.html",
                                         statuses={'backend': 'error', 'frontend': 'error'}, 
                                         model=decoded_model, app_num=app_num, 
                                         error_message=result.get('error'))
            
            return ResponseHandler.error_response(result.get('error', f'{action} failed'))
            
    except Exception as e:
        logger.error(f"Container action error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/status/<model>/<int:app_num>")
def get_app_status(model: str, app_num: int):
    """Get container status."""
    try:
        # Decode URL-encoded model name
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        statuses = AppDataProvider.get_container_statuses(decoded_model, app_num)
        
        if ResponseHandler.is_htmx_request():
            # Check if this is a simple status badge request (from app list)
            # or a full status page request (from app details)
            referrer = request.referrer or ''
            if 'dashboard' in referrer or 'app_details' in referrer:
                # Full status page
                return render_template("partials/container_status.html",
                                     statuses=statuses, model=decoded_model, app_num=app_num)
            else:
                # Simple status badge (for app list)
                return render_template("partials/app_status_badge.html",
                                     statuses=statuses, model=decoded_model, app_num=app_num)
        
        return ResponseHandler.success_response(data=statuses)
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/logs/<model>/<int:app_num>/<container_type>")
def get_container_logs(model: str, app_num: int, container_type: str):
    """Get container logs."""
    try:
        # Decode URL-encoded model name
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        if container_type not in ['backend', 'frontend']:
            return ResponseHandler.error_response("Invalid container type", 400)
        
        logs = DockerOperations.get_logs(decoded_model, app_num, container_type)
        
        context = {
            'logs': logs,
            'model': decoded_model,
            'app_num': app_num,
            'container_type': container_type
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/container_logs.html", **context)
        
        return ResponseHandler.success_response(data=context)
        
    except Exception as e:
        logger.error(f"Logs error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/containers/<model>/<int:app_num>/logs")
def get_container_logs_api(model: str, app_num: int):
    """Get container logs for both frontend and backend."""
    try:
        # Decode URL-encoded model name
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        # Get logs for both frontend and backend
        backend_logs = DockerOperations.get_logs(decoded_model, app_num, 'backend')
        frontend_logs = DockerOperations.get_logs(decoded_model, app_num, 'frontend')
        
        context = {
            'backend_logs': backend_logs,
            'frontend_logs': frontend_logs,
            'model': decoded_model,
            'app_num': app_num
        }
        
        return render_template("partials/container_logs.html", **context)
        
    except Exception as e:
        logger.error(f"Error getting container logs: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# API ROUTES - Files
# ===========================

@api_bp.route("/app/<model>/<int:app_num>/files")
def get_app_files(model: str, app_num: int):
    """Get file tree for application."""
    try:
        project_root = Path(__file__).parent.parent
        app_dir = project_root / "misc" / "models" / model / f"app{app_num}"
        
        if not app_dir.exists():
            return ResponseHandler.error_response('Application directory not found', 404)
        
        files = []
        total_files = 0
        
        def scan_directory(directory: Path, level: int = 0) -> List[Dict]:
            nonlocal total_files
            items = []
            
            try:
                for item in sorted(directory.iterdir()):
                    if item.name.startswith('.'):
                        continue
                        
                    if item.is_file():
                        total_files += 1
                        items.append({
                            'name': item.name,
                            'path': str(item.relative_to(app_dir)),
                            'type': 'file',
                            'size': item.stat().st_size,
                            'level': level,
                            'icon': FileOperations.get_file_icon(item.suffix)
                        })
                    elif item.is_dir():
                        items.append({
                            'name': item.name,
                            'path': str(item.relative_to(app_dir)),
                            'type': 'directory',
                            'level': level,
                            'icon': 'fas fa-folder',
                            'children': scan_directory(item, level + 1)
                        })
            except PermissionError:
                pass
                
            return items
        
        files = scan_directory(app_dir)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/file_tree.html",
                                 files=files, total_files=total_files,
                                 model=model, app_num=app_num)
        
        return ResponseHandler.success_response(data={'files': files, 'total_files': total_files})
        
    except Exception as e:
        logger.error(f"File tree error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/app/<model>/<int:app_num>/file-content")
def get_file_content(model: str, app_num: int):
    """Get content of a specific file."""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return ResponseHandler.error_response('File path required', 400)
        
        project_root = Path(__file__).parent.parent
        app_dir = project_root / "misc" / "models" / model / f"app{app_num}"
        full_path = app_dir / file_path
        
        # Security check
        if not str(full_path.resolve()).startswith(str(app_dir.resolve())):
            return ResponseHandler.error_response('Access denied', 403)
        
        if not full_path.exists() or not full_path.is_file():
            return ResponseHandler.error_response('File not found', 404)
        
        # Read file content
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            try:
                content = full_path.read_text(encoding='latin-1')
            except:
                content = "Binary file - cannot display content"
        
        language = FileOperations.get_language_from_extension(full_path.suffix)
        
        context = {
            'content': content,
            'language': language,
            'filename': full_path.name,
            'size': len(content)
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/file_content.html", **context)
        
        return ResponseHandler.success_response(data=context)
        
    except Exception as e:
        logger.error(f"File content error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/app/<model>/<int:app_num>/download-file")
def download_app_file(model: str, app_num: int):
    """Download a specific file."""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return "File path required", 400
        
        project_root = Path(__file__).parent.parent
        app_dir = project_root / "misc" / "models" / model / f"app{app_num}"
        full_path = app_dir / file_path
        
        # Security check
        if not str(full_path.resolve()).startswith(str(app_dir.resolve())):
            return "Access denied", 403
        
        if not full_path.exists() or not full_path.is_file():
            return "File not found", 404
        
        return send_file(full_path, as_attachment=True)
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return "Download failed", 500


# ===========================
# API ROUTES - Models
# ===========================

@api_bp.route("/models")
def get_models():
    """Get all models data for API requests."""
    try:
        models = ModelCapability.query.all()
        models_data = []
        
        for model in models:
            model_data = {
                'id': model.id,
                'model_id': model.model_id,
                'model_name': model.model_name,
                'provider': model.provider,
                'context_window': model.context_window,
                'max_output_tokens': model.max_output_tokens,
                'input_price_per_token': model.input_price_per_token,
                'output_price_per_token': model.output_price_per_token,
                'created_at': model.created_at.isoformat() if model.created_at else None
            }
            models_data.append(model_data)
        
        return ResponseHandler.success_response({
            'models': models_data,
            'total': len(models_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting models: {e}", exc_info=True)
        return ResponseHandler.error_response(f"Failed to get models: {str(e)}")


@api_bp.route("/app/<model>/<int:app_num>")
def get_app_info(model: str, app_num: int):
    """Get application information for a specific model and app number."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        # Check if the model exists
        model_capability = ModelCapability.query.filter_by(model_id=decoded_model).first()
        if not model_capability:
            return ResponseHandler.error_response("Model not found", 404)
        
        # Get port configuration
        port_config = PortConfiguration.query.filter_by(
            model=decoded_model, 
            app_num=app_num
        ).first()
        
        if not port_config:
            return ResponseHandler.error_response("App configuration not found", 404)
        
        app_data = {
            'model': decoded_model,
            'app_num': app_num,
            'backend_port': port_config.backend_port,
            'frontend_port': port_config.frontend_port,
            'model_name': model_capability.model_name,
            'provider': model_capability.provider
        }
        
        return ResponseHandler.success_response(app_data)
        
    except Exception as e:
        logger.error(f"Error getting app info: {e}", exc_info=True)
        return ResponseHandler.error_response(f"Failed to get app info: {str(e)}")


@api_bp.route("/app/<model>/<int:app_num>/start", methods=["POST"])
def api_start_app(model: str, app_num: int):
    """Start a specific app container."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        result = DockerOperations.execute_action('start', decoded_model, app_num)
        
        if result['success']:
            return ResponseHandler.success_response({
                'message': f'Successfully started {decoded_model} app {app_num}',
                'model': decoded_model,
                'app_num': app_num,
                'action': 'start'
            })
        else:
            return ResponseHandler.error_response(f"Failed to start app: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error starting app {model}/{app_num}: {e}", exc_info=True)
        return ResponseHandler.error_response(f"Failed to start app: {str(e)}")


@api_bp.route("/app/<model>/<int:app_num>/stop", methods=["POST"])
def api_stop_app(model: str, app_num: int):
    """Stop a specific app container."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        result = DockerOperations.execute_action('stop', decoded_model, app_num)
        
        if result['success']:
            return ResponseHandler.success_response({
                'message': f'Successfully stopped {decoded_model} app {app_num}',
                'model': decoded_model,
                'app_num': app_num,
                'action': 'stop'
            })
        else:
            return ResponseHandler.error_response(f"Failed to stop app: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error stopping app {model}/{app_num}: {e}", exc_info=True)
        return ResponseHandler.error_response(f"Failed to stop app: {str(e)}")


@api_bp.route("/app/<model>/<int:app_num>/restart", methods=["POST"])
def api_restart_app(model: str, app_num: int):
    """Restart a specific app container."""
    try:
        import urllib.parse
        decoded_model = urllib.parse.unquote(model)
        
        result = DockerOperations.execute_action('restart', decoded_model, app_num)
        
        if result['success']:
            return ResponseHandler.success_response({
                'message': f'Successfully restarted {decoded_model} app {app_num}',
                'model': decoded_model,
                'app_num': app_num,
                'action': 'restart'
            })
        else:
            return ResponseHandler.error_response(f"Failed to restart app: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error restarting app {model}/{app_num}: {e}", exc_info=True)
        return ResponseHandler.error_response(f"Failed to restart app: {str(e)}")


@api_bp.route("/models/export")
def export_models_data():
    """Export models data in various formats."""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        # Get filtered models
        query = ModelCapability.query
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '').strip()
        
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                ModelCapability.model_name.ilike(pattern) |
                ModelCapability.model_id.ilike(pattern)
            )
        
        if provider:
            query = query.filter_by(provider=provider)
        
        models = query.all()
        
        # Prepare export data
        export_data = []
        for model in models:
            model_data = model.to_dict()
            # Add calculated fields
            capabilities = model.get_capabilities()
            metadata = model.get_metadata()
            
            model_data.update({
                'supports_reasoning': capabilities.get('reasoning', False),
                'supports_coding': capabilities.get('coding', False),
                'supports_math': capabilities.get('math', False),
                'quality_score': metadata.get('quality_metrics', {}).get('overall', 0)
            })
            
            export_data.append(model_data)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if format_type == 'csv':
            # CSV Export
            output = io.StringIO()
            if export_data:
                csv_fields = [
                    'model_id', 'model_name', 'canonical_slug', 'provider',
                    'is_free', 'context_window', 'max_output_tokens',
                    'supports_function_calling', 'supports_vision',
                    'input_price_per_token', 'output_price_per_token',
                    'cost_efficiency', 'safety_score'
                ]
                
                writer = csv.DictWriter(output, fieldnames=csv_fields, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(export_data)
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=models_export_{timestamp}.csv'
            return response
        else:
            # JSON format
            export_result = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'total_models': len(export_data),
                    'filters_applied': {
                        'search': search,
                        'provider': provider
                    }
                },
                'models': export_data
            }
            
            response = make_response(json.dumps(export_result, indent=2, default=str))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=models_export_{timestamp}.json'
            return response
            
    except Exception as e:
        logger.error(f"Export error: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# LEGACY ROUTES - REDIRECT TO STATISTICS
# ===========================

@main_bp.route("/analysis")
@main_bp.route("/analysis/")
def analysis_redirect():
    """Redirect analysis routes to statistics page."""
    return redirect(url_for('statistics.statistics_overview'))

@main_bp.route("/analysis/<path:subpath>")
def analysis_subpath_redirect(subpath):
    """Redirect all analysis subpaths to statistics."""
    return redirect(url_for('statistics.statistics_overview'))

@main_bp.route("/performance")
@main_bp.route("/performance/")
def performance_redirect():
    """Redirect performance routes to statistics page."""
    return redirect(url_for('statistics.statistics_overview'))

@main_bp.route("/performance/<path:subpath>")
def performance_subpath_redirect(subpath):
    """Redirect all performance subpaths to statistics."""
    return redirect(url_for('statistics.statistics_overview'))

@main_bp.route("/batch-analysis")
def batch_analysis_redirect():
    """Redirect to batch job creation page."""
    return redirect(url_for('batch.create_batch_job'))


# ===========================
# STATISTICS ROUTES
# ===========================

@statistics_bp.route("/")
def statistics_overview():
    """Statistics and generation data overview."""
    try:
        # Load generation statistics from generateOutputs.py data
        stats = load_generation_statistics()
        recent_generations = load_recent_generations()
        top_models = load_top_performing_models()
        daily_stats = load_daily_statistics()
        
        context = {
            'stats': stats,
            'recent_generations': recent_generations,
            'top_models': top_models,
            'daily_stats': daily_stats
        }
        
        return ResponseHandler.render_response("statistics_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Statistics overview error: {e}")
        return ResponseHandler.error_response(str(e))


@statistics_bp.route("/api/refresh", methods=["POST"])
def refresh_statistics():
    """Refresh statistics data."""
    try:
        # Clear any cached data and reload
        return ResponseHandler.success_response({"message": "Statistics refreshed"})
    except Exception as e:
        return ResponseHandler.error_response(str(e))


@statistics_bp.route("/api/export")
def export_statistics():
    """Export statistics data."""
    try:
        # Generate export file with statistics
        return ResponseHandler.success_response({"message": "Export not implemented yet"})
    except Exception as e:
        return ResponseHandler.error_response(str(e))
        
        # Placeholder for successful statistics loading
        return ResponseHandler.success_response({"message": "Statistics page loaded"})


# Helper functions for loading generation data
def load_generation_statistics():
    """Load generation statistics from generateOutputs.py data."""
    try:
        import json
        
        # Load from API data directory
        api_data_dir = Path("api_data/generation_stats")
        
        stats = {
            'total_models': 0,
            'total_applications': 0,
            'total_calls': 0,
            'successful_calls': 0,
            'avg_generation_time': 'N/A',
            'success_rate': 0.0
        }
        
        if api_data_dir.exists():
            # Find latest date directory
            date_dirs = [d for d in api_data_dir.iterdir() if d.is_dir()]
            if date_dirs:
                latest_date = max(date_dirs, key=lambda x: x.name).name
                date_dir = api_data_dir / latest_date
                
                # Load daily summary if it exists
                daily_summary_file = date_dir / f"daily_summary_{latest_date}.json"
                if daily_summary_file.exists():
                    with open(daily_summary_file, 'r') as f:
                        daily_data = json.load(f)
                    
                    models = set()
                    apps = set()
                    total_calls = len(daily_data)
                    successful_calls = sum(1 for call in daily_data if call.get('success', False))
                    total_duration = 0
                    duration_count = 0
                    
                    for call in daily_data:
                        models.add(call.get('model', ''))
                        apps.add(call.get('app_name', ''))
                        if call.get('total_duration'):
                            total_duration += call.get('total_duration', 0)
                            duration_count += 1
                    
                    stats['total_models'] = len(models)
                    stats['total_applications'] = len(apps) 
                    stats['total_calls'] = total_calls
                    stats['successful_calls'] = successful_calls
                    stats['success_rate'] = (successful_calls / total_calls * 100) if total_calls > 0 else 0
                    
                    if duration_count > 0:
                        avg_time = total_duration / duration_count
                        stats['avg_generation_time'] = f"{avg_time:.1f}s"
                else:
                    # Fallback: count model subdirectories
                    model_subdirs = [d for d in date_dir.iterdir() if d.is_dir() and not d.name.startswith('daily_')]
                    stats['total_models'] = len(model_subdirs)
        
        return stats
        
    except Exception as e:
        logger.error(f"Error loading generation statistics: {e}")
        return {
            'total_models': 0,
            'total_applications': 0,
            'total_calls': 0,
            'successful_calls': 0,
            'avg_generation_time': 'N/A',
            'success_rate': 0.0
        }


def load_recent_generations():
    """Load recent generation activity."""
    try:
        import json
        from datetime import datetime
        
        # Load from API data directory
        api_data_dir = Path("api_data/generation_stats")
        recent = []
        
        if api_data_dir.exists():
            # Find latest date directory
            date_dirs = [d for d in api_data_dir.iterdir() if d.is_dir()]
            if date_dirs:
                latest_date = max(date_dirs, key=lambda x: x.name).name
                date_dir = api_data_dir / latest_date
                
                # Load daily summary if it exists
                daily_summary_file = date_dir / f"daily_summary_{latest_date}.json"
                if daily_summary_file.exists():
                    with open(daily_summary_file, 'r') as f:
                        daily_data = json.load(f)
                    
                    # Sort by timestamp, most recent first
                    daily_data.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
                    
                    for call in daily_data[:15]:  # Get last 15 calls
                        model_display = call.get('model', '').split('/')[-1].replace(':free', '')
                        if len(model_display) > 20:
                            model_display = model_display[:17] + "..."
                            
                        status = 'success' if call.get('success', False) else 'failed'
                        duration = f"{call.get('total_duration', 0):.1f}s"
                        
                        # Parse timestamp for display
                        timestamp_str = call.get('timestamp', '')
                        try:
                            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            time_display = dt.strftime('%H:%M:%S')
                        except Exception:
                            time_display = 'Unknown'
                        
                        recent.append({
                            'model_name': model_display,
                            'app_type': call.get('app_name', 'Unknown'),
                            'call_type': call.get('call_type', 'N/A'),
                            'status': status,
                            'duration': duration,
                            'date': time_display,
                            'content_length': call.get('content_length', 0)
                        })
        
        return recent
        
    except Exception as e:
        logger.error(f"Error loading recent generations: {e}")
        return []


def load_top_performing_models():
    """Load top performing models."""
    try:
        import json
        from collections import defaultdict
        
        # Load from API data directory
        api_data_dir = Path("api_data/generation_stats")
        model_stats = defaultdict(lambda: {'total': 0, 'successful': 0, 'apps': set()})
        
        if api_data_dir.exists():
            # Find latest date directory
            date_dirs = [d for d in api_data_dir.iterdir() if d.is_dir()]
            if date_dirs:
                latest_date = max(date_dirs, key=lambda x: x.name).name
                date_dir = api_data_dir / latest_date
                
                # Load daily summary if it exists
                daily_summary_file = date_dir / f"daily_summary_{latest_date}.json"
                if daily_summary_file.exists():
                    with open(daily_summary_file, 'r') as f:
                        daily_data = json.load(f)
                    
                    for call in daily_data:
                        model = call.get('model', 'Unknown')
                        model_display = model.split('/')[-1].replace(':free', '')
                        if len(model_display) > 25:
                            model_display = model_display[:22] + "..."
                        
                        model_stats[model_display]['total'] += 1
                        if call.get('success', False):
                            model_stats[model_display]['successful'] += 1
                        model_stats[model_display]['apps'].add(call.get('app_name', ''))
                    
                    # Calculate success rates and sort
                    top_models = []
                    for model, stats in model_stats.items():
                        success_rate = (stats['successful'] / stats['total'] * 100) if stats['total'] > 0 else 0
                        top_models.append({
                            'name': model,
                            'success_rate': success_rate,
                            'apps_generated': len(stats['apps']),
                            'total_calls': stats['total'],
                            'successful_calls': stats['successful']
                        })
                    
                    # Sort by success rate, then by total calls
                    top_models.sort(key=lambda x: (x['success_rate'], x['total_calls']), reverse=True)
                    return top_models[:8]  # Return top 8
        
        return []
        
    except Exception as e:
        logger.error(f"Error loading top models: {e}")
        return []


def load_daily_statistics():
    """Load daily generation statistics."""
    try:
        # This would load daily statistics for charts
        return None  # Placeholder
    except Exception as e:
        logger.error(f"Error loading daily statistics: {e}")
        return None


# ===========================
# BATCH ROUTES - Enhanced with Coordinator Integration
# ===========================

# Import batch coordinator and models
try:
    from models import BatchJob, BatchTask, JobStatus, TaskStatus, AnalysisType
except ImportError:
    # Fallback for environments where batch system is not available
    BatchAnalysisCoordinator = None
    logger.warning("Batch coordinator not available")

# Global coordinator instance
_batch_coordinator = None

def get_batch_coordinator():
    """Get or create batch service instance."""
    global _batch_coordinator
    if _batch_coordinator is None:
        try:
            # Import the new Container Batch Service
            from batch_testing_service import get_batch_testing_service
            
            # Create service instance
            _batch_coordinator = get_batch_testing_service()
            logger.info("Container batch service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize batch service: {e}")
    return _batch_coordinator

@batch_bp.route("/")
def batch_overview():
    """Enhanced batch processing overview - Jobs management dashboard."""
    try:
        batch_service = get_batch_coordinator()
        
        context = {
            'jobs': [],
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'pending_jobs': 0,
            'cancelled_jobs': 0,
            'stats': {
                'total': 0,
                'pending': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0,
                'archived': 0
            },
            'page_title': 'Batch Analysis Jobs',
            'system_stats': None
        }
        
        if batch_service:
            # Get all jobs using BatchService
            jobs = batch_service.get_jobs(limit=50)
            
            context['jobs'] = jobs
            context['total_jobs'] = len(jobs)
            
            # Calculate stats
            for job in jobs:
                # Handle both dict and object responses
                job_status = job.get('status') if isinstance(job, dict) else job.status
                if job_status == JobStatus.RUNNING or job_status == 'running':
                    context['running_jobs'] += 1
                elif job_status == JobStatus.COMPLETED or job_status == 'completed':
                    context['completed_jobs'] += 1
                elif job_status == JobStatus.FAILED or job_status == 'failed':
                    context['failed_jobs'] += 1
                elif job_status == JobStatus.PENDING or job_status == 'pending':
                    context['pending_jobs'] += 1
                elif job_status == JobStatus.CANCELLED or job_status == 'cancelled':
                    context['cancelled_jobs'] += 1
            
            # Update stats dict
            context['stats'] = {
                'total': context['total_jobs'],
                'pending': context['pending_jobs'],
                'running': context['running_jobs'],
                'completed': context['completed_jobs'],
                'failed': context['failed_jobs'],
                'cancelled': context['cancelled_jobs'],
                'archived': 0
            }
            
            # Get system statistics if available
            try:
                context['system_stats'] = batch_service.get_stats()
            except Exception as e:
                logger.warning(f"Could not get system stats: {e}")
        
        # Redirect to the new container-centric batch testing interface
        return redirect(url_for('batch_testing.batch_testing_dashboard'))
        
    except Exception as e:
        logger.error(f"Batch overview error: {e}")
        context = {
            'jobs': [],
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'pending_jobs': 0,
            'cancelled_jobs': 0,
            'stats': {'total': 0, 'pending': 0, 'running': 0, 'completed': 0, 'failed': 0, 'cancelled': 0, 'archived': 0},
            'error_message': f"Service temporarily unavailable: {str(e)}",
            'page_title': 'Batch Analysis Jobs'
        }
        # Redirect to the new container-centric batch testing interface
        return redirect(url_for('batch_testing.batch_testing_dashboard'))


@batch_bp.route("/create", methods=["GET", "POST"])
def create_batch_job():
    """Enhanced batch job creation with comprehensive tool configuration."""
    if request.method == "GET":
        # Show enhanced create job page
        try:
            models = ModelCapability.query.all()
            
            context = {
                'available_models': [{'slug': m.canonical_slug, 'name': m.model_name, 'apps_count': 30} for m in models],
                'analysis_types': [
                    {'value': 'security_combined', 'name': 'Security Comprehensive', 'description': 'Full security analysis (Backend + Frontend)'},
                    {'value': 'security_backend', 'name': 'Security Backend', 'description': 'Bandit, Safety, Semgrep'},
                    {'value': 'security_frontend', 'name': 'Security Frontend', 'description': 'ESLint Security, Retire.js'},
                    {'value': 'performance', 'name': 'Performance Load Testing', 'description': 'Locust load testing'}
                ],
                'page_title': 'Create New Batch Analysis Job'
            }
            
            return render_template("pages/create_batch_job_enhanced.html", **context)
            
        except Exception as e:
            logger.error(f"Create job page error: {e}")
            flash(f"Error loading create job page: {str(e)}", "error")
            return redirect(url_for('batch.batch_overview'))
    
    else:  # POST - Enhanced form processing
        try:
            coordinator = get_batch_coordinator()
            if not coordinator:
                return ResponseHandler.error_response("Batch coordinator not available")
            
            # Extract basic job information
            job_data = {
                'name': request.form.get('name', '').strip(),
                'description': request.form.get('description', '').strip(),
                'priority': request.form.get('priority', 'NORMAL'),
                'execution_mode': request.form.get('execution_mode', 'IMMEDIATE'),
                'timeout_minutes': int(request.form.get('timeout_minutes', 60)),
                'max_concurrent_tasks': int(request.form.get('max_concurrent_tasks', 4)),
                'parallel_execution': bool(request.form.get('parallel_execution')),
                'retry_failed_tasks': bool(request.form.get('retry_failed_tasks')),
                'max_retries': int(request.form.get('max_retries', 2))
            }
            
            # Extract analysis types
            analysis_types = request.form.getlist('analysis_types')
            if not analysis_types:
                return ResponseHandler.error_response("At least one analysis type must be selected")
            
            job_data['analysis_types'] = analysis_types
            
            # Extract target models and apps
            target_models = request.form.getlist('target_models')
            if not target_models:
                return ResponseHandler.error_response("At least one target model must be selected")
            
            job_data['target_models'] = target_models
            
            # Process target apps
            target_apps = request.form.get('target_apps', '').strip()
            if not target_apps:
                target_apps = '1-30'  # Default to all apps
            
            job_data['target_apps'] = _parse_app_specification(target_apps)
            
            # Extract tool configurations
            job_data['security_config'] = _extract_tool_config(request.form, 'security_config')
            job_data['frontend_config'] = _extract_tool_config(request.form, 'frontend_config')
            job_data['performance_config'] = _extract_tool_config(request.form, 'performance_config')
            
            # Handle scheduling
            if job_data['execution_mode'] == 'SCHEDULED':
                scheduled_for = request.form.get('scheduled_for')
                if scheduled_for:
                    from datetime import datetime
                    job_data['scheduled_for'] = datetime.fromisoformat(scheduled_for)
                
                recurrence = request.form.get('recurrence_pattern')
                if recurrence:
                    job_data['recurrence_pattern'] = recurrence
            
            # Validate required fields
            if not job_data['name']:
                return ResponseHandler.error_response("Job name is required")
            
            # Create job using coordinator
            job = coordinator.create_job(**job_data)
            
            # Start job if immediate execution
            if job_data['execution_mode'] == 'IMMEDIATE':
                coordinator.start_job(job.id)
            
            if ResponseHandler.is_htmx_request():
                return render_template("partials/batch_job_create_success.html", job=job)
            
            flash(f'Batch job "{job.name}" created successfully ({job.total_tasks} tasks)', "success")
            return redirect(url_for('batch.view_job', job_id=job.id))
            
        except Exception as e:
            logger.error(f"Create job error: {e}")
            error_msg = f"Error creating job: {str(e)}"
            return ResponseHandler.error_response(error_msg)

def _parse_app_specification(app_spec: str) -> List[Union[int, str]]:
    """Parse app specification into list of app numbers or ranges."""
    apps = []
    
    # Handle comma-separated values
    for part in app_spec.split(','):
        part = part.strip()
        if '-' in part:
            # Range specification
            try:
                start, end = map(int, part.split('-'))
                apps.append(f"{start}-{end}")
            except ValueError:
                # Invalid range, treat as single value
                try:
                    apps.append(int(part))
                except ValueError:
                    continue
        else:
            # Single value
            try:
                apps.append(int(part))
            except ValueError:
                continue
    
    return apps

def _extract_tool_config(form_data, config_prefix: str) -> Dict[str, Any]:
    """Extract tool configuration from form data."""
    config = {}
    
    # Find all form fields with the config prefix
    for key, value in form_data.items():
        if key.startswith(f"{config_prefix}."):
            # Parse nested configuration structure
            parts = key.split('.')
            current = config
            
            # Navigate to the correct nested location
            for part in parts[1:-1]:  # Skip config_prefix and last part
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value
            field_name = parts[-1]
            
            # Handle different value types
            if isinstance(value, list):
                # Multiple values (checkboxes)
                current[field_name] = value
            elif value.lower() in ['true', 'false']:
                # Boolean values
                current[field_name] = value.lower() == 'true'
            elif value.isdigit():
                # Integer values
                current[field_name] = int(value)
            elif '\n' in value:
                # Multi-line text (convert to list)
                current[field_name] = [line.strip() for line in value.split('\n') if line.strip()]
            else:
                # String values
                current[field_name] = value
    
    return config


@batch_bp.route("/job/<job_id>")
def view_job(job_id: str):
    """Enhanced batch job details view."""
    try:
        coordinator = get_batch_coordinator()
        if not coordinator:
            return ResponseHandler.error_response("Batch coordinator not available")
        
        job_status = coordinator.get_job_status(job_id)
        if not job_status:
            return ResponseHandler.error_response("Job not found", 404)
        
        job_data = job_status['job']
        tasks = job_status['tasks']
        is_running = job_status['is_running']
        
        # Calculate task statistics
        task_stats = {
            'total': len(tasks),
            'pending': sum(1 for t in tasks if t['status'] == 'PENDING'),
            'running': sum(1 for t in tasks if t['status'] == 'RUNNING'),
            'completed': sum(1 for t in tasks if t['status'] == 'COMPLETED'),
            'failed': sum(1 for t in tasks if t['status'] == 'FAILED'),
            'cancelled': sum(1 for t in tasks if t['status'] == 'CANCELLED')
        }
        
        # Calculate progress percentage
        progress_percentage = 0
        if task_stats['total'] > 0:
            completed_tasks = task_stats['completed'] + task_stats['failed']
            progress_percentage = (completed_tasks / task_stats['total']) * 100
        
        context = {
            'job': job_data,
            'tasks': tasks,
            'task_stats': task_stats,
            'progress_percentage': round(progress_percentage, 1),
            'is_running': is_running,
            'page_title': f'Job: {job_data["name"]}'
        }
        
        return render_template("pages/view_job_enhanced.html", **context)
        
    except Exception as e:
        logger.error(f"View job error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/job/<job_id>/start", methods=["POST"])
def start_job(job_id: str):
    """Start a batch job."""
    try:
        coordinator = get_batch_coordinator()
        if not coordinator:
            return ResponseHandler.error_response("Batch coordinator not available")
        
        success = coordinator.start_job(job_id)
        if success:
            return ResponseHandler.success_response(message="Job started successfully")
        else:
            return ResponseHandler.error_response("Failed to start job")
            
    except Exception as e:
        logger.error(f"Start job error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/job/<job_id>/cancel", methods=["POST"])
def cancel_job(job_id: str):
    """Cancel a running batch job."""
    try:
        batch_service = get_batch_coordinator()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        # Use stop_job instead of cancel_job
        success = batch_service.stop_job(job_id)
        if success:
            return ResponseHandler.success_response(message="Job cancelled successfully")
        else:
            return ResponseHandler.error_response("Failed to cancel job")
            
    except Exception as e:
        logger.error(f"Cancel job error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/api/jobs", methods=["GET"])
def api_jobs_list():
    """API endpoint for jobs list (HTMX compatible) - REMOVED - USE BATCH ROUTES INSTEAD."""
    return jsonify({
        'error': 'This endpoint has been moved. Use /api/batch/jobs instead.',
        'redirect': '/api/batch/jobs'
    }), 301


@batch_bp.route("/api/job/<job_id>/status", methods=["GET"])
def api_job_status(job_id: str):
    """API endpoint for job status updates."""
    try:
        batch_service = get_batch_coordinator()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        # Use get_job with string ID as expected
        job = batch_service.get_job(job_id)
        if not job:
            return ResponseHandler.error_response("Job not found", 404)
        
        job_status = {
            "id": job.id,
            "status": job.status.value if job.status else "unknown",
            "progress": job.get_progress_percentage(),  # Use the method instead
            "error_message": job.error_message or "",
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            "completed_tasks": job.completed_tasks,
            "total_tasks": job.total_tasks
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/job_status.html", **job_status)
        
        return ResponseHandler.success_response(job_status)
        
    except Exception as e:
        logger.error(f"API job status error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/api/statistics", methods=["GET"])
def api_statistics():
    """API endpoint for batch processing statistics."""
    try:
        batch_service = get_batch_coordinator()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        # Use get_stats instead of get_statistics
        stats = batch_service.get_stats()
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_statistics.html", stats=stats)
        
        return ResponseHandler.success_response(stats)
        
    except Exception as e:
        logger.error(f"API statistics error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/templates", methods=["GET"])
def job_templates():
    """Manage batch job templates."""
    try:
        batch_service = get_batch_coordinator()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        # Since BatchService doesn't have template support yet, return empty list
        context = {
            'templates': [],
            'page_title': 'Batch Job Templates'
        }
        
        return render_template("pages/batch_templates.html", **context)
        
    except Exception as e:
        logger.error(f"Job templates error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/reports", methods=["GET"])
def batch_reports():
    """View batch analysis reports."""
    try:
        batch_service = get_batch_coordinator()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        # Since BatchService doesn't have reports support yet, return empty list
        context = {
            'reports': [],
            'page_title': 'Batch Analysis Reports'
        }
        
        return render_template("pages/batch_reports.html", **context)
        
    except Exception as e:
        logger.error(f"Batch reports error: {e}")
        return ResponseHandler.error_response(str(e))

@batch_bp.route("/api/models", methods=["GET"])
def api_models():
    """API endpoint for available models."""
    try:
        models = ModelCapability.query.all()
        models_data = [
            {
                'slug': model.canonical_slug,
                'name': model.model_name,
                'apps_count': 30,  # Assuming 30 apps per model
                'capabilities': model.capabilities if hasattr(model, 'capabilities') else {}
            }
            for model in models
        ]
        
        return ResponseHandler.success_response({'models': models_data})
        
    except Exception as e:
        logger.error(f"API models error: {e}")
        return ResponseHandler.error_response(str(e))


@batch_bp.route("/job/<job_id>/cancel", methods=["POST"])
def cancel_batch_job(job_id: str):
    """Cancel a batch job."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        success = batch_service.cancel_job(job_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.success_response("Job cancelled successfully")
            flash("Job cancelled successfully", "success")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.error_response("Failed to cancel job")
            flash("Failed to cancel job", "error")
        
        return redirect(url_for('batch.batch_overview'))
        
    except Exception as e:
        logger.error(f"Cancel job error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ResponseHandler.error_response(f"Error cancelling job: {str(e)}")
        flash(f"Error cancelling job: {str(e)}", "error")
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>/pause", methods=["POST"])
def pause_job(job_id: str):
    """Pause a batch job."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        success = batch_service.pause_job(job_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.success_response("Job paused successfully")
            flash("Job paused successfully", "success")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.error_response("Failed to pause job")
            flash("Failed to pause job", "error")
        
        return redirect(url_for('batch.batch_overview'))
        
    except Exception as e:
        logger.error(f"Pause job error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ResponseHandler.error_response(f"Error pausing job: {str(e)}")
        flash(f"Error pausing job: {str(e)}", "error")
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>/resume", methods=["POST"])
def resume_job(job_id: str):
    """Resume a paused batch job."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        success = batch_service.resume_job(job_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.success_response("Job resumed successfully")
            flash("Job resumed successfully", "success")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.error_response("Failed to resume job")
            flash("Failed to resume job", "error")
        
        return redirect(url_for('batch.batch_overview'))
        
    except Exception as e:
        logger.error(f"Resume job error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ResponseHandler.error_response(f"Error resuming job: {str(e)}")
        flash(f"Error resuming job: {str(e)}", "error")
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>/start", methods=["POST"])
def start_batch_job(job_id: str):
    """Start a pending batch job."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        success = batch_service.start_job(job_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.success_response("Job started successfully")
            flash("Job started successfully", "success")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.error_response("Failed to start job")
            flash("Failed to start job", "error")
        
        return redirect(url_for('batch.batch_overview'))
        
    except Exception as e:
        logger.error(f"Start job error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ResponseHandler.error_response(f"Error starting job: {str(e)}")
        flash(f"Error starting job: {str(e)}", "error")
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    """Delete a batch job."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        success = batch_service.delete_job(job_id)
        if success:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.success_response("Job deleted successfully")
            flash("Job deleted successfully", "success")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return ResponseHandler.error_response("Failed to delete job")
            flash("Failed to delete job", "error")
        
        return redirect(url_for('batch.batch_overview'))
        
    except Exception as e:
        logger.error(f"Delete job error: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ResponseHandler.error_response(f"Error deleting job: {str(e)}")
        flash(f"Error deleting job: {str(e)}", "error")
        return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>/export")
def export_job(job_id: str):
    """Export job results."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        job = batch_service.get_job(job_id)
        if not job:
            return ResponseHandler.error_response("Job not found", 404)
        
        tasks = batch_service.get_job_tasks(job_id)
        
        export_data = {
            'job': job.to_dict(),
            'tasks': [task.to_dict() for task in tasks],
            'exported_at': datetime.now().isoformat(),
            'export_version': '1.0'
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        logger.error(f"Export job error: {e}")
        return ResponseHandler.error_response(f"Error exporting job: {str(e)}")


@batch_bp.route("/export-all")
def export_all_jobs():
    """Export all jobs data."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        jobs = batch_service.get_all_jobs()
        stats = batch_service.get_job_stats()
        
        export_data = {
            'jobs': [job.to_dict() for job in jobs],
            'statistics': stats,
            'exported_at': datetime.now().isoformat(),
            'export_version': '1.0',
            'total_jobs': len(jobs)
        }
        
        return jsonify(export_data)
        
    except Exception as e:
        logger.error(f"Export all jobs error: {e}")
        return ResponseHandler.error_response(f"Error exporting jobs: {str(e)}")


@batch_bp.route("/api/status")
def api_status():
    """Get batch system status."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        stats = batch_service.get_detailed_statistics()
        
        return ResponseHandler.success_response(stats, "Status retrieved")
        
    except Exception as e:
        logger.error(f"API status error: {e}")
        return ResponseHandler.error_response(f"Error getting status: {str(e)}")


# ===========================
# DOCKER ROUTES
# ===========================

@docker_bp.route("/")
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


@docker_bp.route("/<action>/<model>/<int:app_num>", methods=["POST"])
def docker_action(action: str, model: str, app_num: int):
    """Handle Docker action."""
    return container_action(model, app_num, action)  # Reuse API handler


@docker_bp.route("/bulk-action", methods=["POST"])
def bulk_docker_action():
    """Handle bulk Docker actions."""
    try:
        action = request.form.get('action')
        if not action:
            return ResponseHandler.error_response("No action specified", 400)
        
        valid_actions = ['start', 'stop', 'restart', 'cleanup']
        if action not in valid_actions:
            return ResponseHandler.error_response(f"Invalid action: {action}", 400)
        
        # Parse filters
        model_filter = request.form.get('model_filter', '').strip()
        app_range = request.form.get('app_range', '1-30').strip()
        
        # Parse app range
        if '-' in app_range:
            start, end = map(int, app_range.split('-'))
            app_numbers = list(range(start, end + 1))
        else:
            app_numbers = [int(app_range)]
        
        # Get matching apps
        apps = []
        for model in ModelCapability.query.all():
            if model_filter and model_filter not in model.canonical_slug:
                continue
            for app_num in app_numbers:
                apps.append((model.canonical_slug, app_num))
        
        # Execute bulk action
        result = DockerOperations.bulk_action(action, apps[:20])  # Limit for safety
        
        context = {
            'action': action,
            'results': result['results'],
            'total_attempted': result['total'],
            'successful': result['successful'],
            'failed': result['failed']
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/bulk_action_results.html", **context)
        
        return ResponseHandler.success_response(data=context)
        
    except Exception as e:
        logger.error(f"Bulk action error: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# ERROR HANDLERS
# ===========================

@main_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    return ResponseHandler.error_response("Page not found", 404)


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal error: {error}")
    
    # Avoid template rendering for specific errors that might cause template issues
    error_str = str(error)
    if 'strftime' in error_str or 'template' in error_str.lower():
        if request.headers.get('HX-Request') == 'true':
            return f'<div class="alert alert-danger">Server Error: {error_str}</div>', 500
        else:
            return jsonify({'success': False, 'error': error_str}), 500
    
    return ResponseHandler.error_response("Internal server error", 500)


# ===========================
# TEMPLATE HELPERS
# ===========================

def register_template_helpers(app):
    """Register Jinja2 template helpers."""
    
    @app.template_filter('format_datetime')
    def format_datetime(value):
        """Format datetime for display."""
        try:
            if not value:
                return ''
            
            # If it's already a string, just return it (might be pre-formatted)
            if isinstance(value, str):
                # Try to parse it, but if it fails, just return the string
                try:
                    if 'T' in value:
                        parsed_dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        return parsed_dt.strftime('%Y-%m-%d %H:%M:%S')
                    else:
                        # Assume it's already formatted
                        return value
                except (ValueError, TypeError):
                    # If parsing fails, return the original string
                    return str(value)
            
            # If it's a datetime object, format it
            if hasattr(value, 'strftime'):
                return value.strftime('%Y-%m-%d %H:%M:%S')
            
            # Fallback - convert to string
            return str(value)
            
        except Exception as e:
            # Ultimate fallback
            return str(value) if value else ''
    
    @app.template_filter('format_duration')
    def format_duration(seconds):
        """Format duration in seconds to human readable."""
        if not seconds:
            return '0s'
        
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        parts = []
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        if secs or not parts:
            parts.append(f"{secs}s")
        
        return ' '.join(parts)
    
    @app.template_filter('to_datetime')
    def to_datetime(value):
        """Convert string to datetime object."""
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return value
    
    @app.template_filter('url_encode_model')
    def url_encode_model(model_name):
        """Encode model name for safe use in URLs."""
        if not model_name:
            return ''
        # For Flask routes, we need to ensure special characters are URL-encoded
        import urllib.parse
        return urllib.parse.quote(model_name, safe='')
    
    @app.template_filter('model_display_name')
    def model_display_name(model_slug):
        """Convert model slug to display name."""
        if not model_slug:
            return ''
        
        # Try to get the actual model from database for more accurate display name
        try:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if model and model.model_name:
                # Use the model_name from database and improve it
                display_name = model.model_name
                
                # Common transformations for better display names
                display_name = display_name.replace('-', ' ').replace('_', ' ')
                
                # Handle specific patterns
                if 'claude' in display_name.lower():
                    # Claude models: claude-3.7-sonnet -> Claude 3.7 Sonnet
                    if 'claude' in display_name and not display_name.startswith('Claude'):
                        display_name = display_name.replace('claude', 'Claude')
                
                # Handle version patterns like gpt-4.1 -> GPT-4.1
                if 'gpt' in display_name.lower():
                    display_name = display_name.upper().replace('GPT', 'GPT-')
                    if 'GPT--' in display_name:
                        display_name = display_name.replace('GPT--', 'GPT-')
                
                # Handle other common patterns
                display_name = display_name.replace('gemini', 'Gemini')
                display_name = display_name.replace('qwen', 'Qwen')
                display_name = display_name.replace('deepseek', 'DeepSeek')
                display_name = display_name.replace('mistral', 'Mistral')
                
                # Title case each word but preserve version numbers
                words = display_name.split()
                result_words = []
                for word in words:
                    if any(char.isdigit() for char in word) and ('.' in word or '-' in word):
                        # Keep version numbers as-is
                        result_words.append(word)
                    else:
                        # Title case regular words
                        result_words.append(word.capitalize())
                
                return ' '.join(result_words)
        except Exception:
            # Fall back to simple transformation if database lookup fails
            pass
        
        # Fallback: Simple transformation of the slug
        # Convert underscores to spaces, handle hyphens carefully
        display_name = model_slug.replace('_', ' ')
        
        # Split on spaces and improve each part
        parts = display_name.split(' ')
        result_parts = []
        
        for part in parts:
            if 'claude' in part.lower():
                part = part.replace('claude', 'Claude').replace('-', ' ')
            elif 'gpt' in part.lower():
                part = part.upper().replace('-', ' ')
            elif 'gemini' in part.lower():
                part = part.replace('gemini', 'Gemini').replace('-', ' ')
            elif 'qwen' in part.lower():
                part = part.replace('qwen', 'Qwen').replace('-', ' ')
            elif 'deepseek' in part.lower():
                part = part.replace('deepseek', 'DeepSeek').replace('-', ' ')
            else:
                part = part.title().replace('-', ' ')
            
            result_parts.append(part)
        
        return ' '.join(result_parts)
    
    @app.template_filter('safe_css_id')
    def safe_css_id(value):
        """Convert any string to a safe CSS ID by replacing problematic characters."""
        if not value:
            return ''
        # Replace dots, hyphens, and other problematic characters with underscores
        import re
        # Replace any non-alphanumeric character (except underscore) with underscore
        safe_id = re.sub(r'[^a-zA-Z0-9_]', '_', str(value))
        # Ensure it starts with a letter or underscore (CSS requirement)
        if safe_id and not safe_id[0].isalpha() and safe_id[0] != '_':
            safe_id = 'id_' + safe_id
        return safe_id
    
    @app.template_global()
    def url_decode_model(encoded_model):
        """Decode URL-encoded model name."""
        if not encoded_model:
            return ''
        import urllib.parse
        return urllib.parse.unquote(encoded_model)
    
    @app.template_global()
    def is_htmx():
        """Check if current request is from HTMX."""
        return ResponseHandler.is_htmx_request()
    
    @app.template_global()
    def get_app_url(model, app_num):
        """Generate app URL."""
        try:
            port_config = AppDataProvider.get_port_config(model, app_num)
            return f"http://localhost:{port_config['frontend_port']}"
        except Exception:
            return None


# ===========================
# PERFORMANCE & SECURITY ANALYSIS ROUTES
# ===========================

@api_bp.route("/performance/<model>/<int:app_num>/run", methods=["POST"])
def run_performance_test(model, app_num):
    """Run performance test on specified app."""
    try:
        logger.info(f"Starting performance test for {model} app {app_num}")
        
        # Get form data
        duration = int(request.form.get('duration', 60))
        users = int(request.form.get('users', 10))
        spawn_rate = float(request.form.get('spawn_rate', 1.0))
        
        # Get performance service
        performance_service = ServiceLocator.get_service('performance_service')
        if not performance_service:
            return jsonify({'error': 'Performance service not available'}), 503
        
        # Run the test
        results = performance_service.run_performance_test(
            model=model,
            app_num=app_num,
            duration=duration,
            users=users,
            spawn_rate=spawn_rate
        )
        
        if results['success']:
            return render_template("partials/performance_test_success.html", 
                                 results=results.get('data', {}))
        else:
            return render_template("partials/performance_test_failed.html", 
                                 error=results.get('error', 'Unknown error'))
            
    except Exception as e:
        logger.error(f"Performance test error: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/analysis/<model>/<int:app_num>/security", methods=["POST"])
def run_security_analysis(model, app_num):
    """Run CLI security analysis on specified app with containerized service support."""
    try:
        logger.info(f"Starting security analysis for {model} app {app_num}")
        
        # Check if containerized services should be used
        use_containerized = request.form.get('use_containerized') == 'on'
        
        if use_containerized:
            return _run_containerized_security_analysis(model, app_num)
        else:
            return _run_legacy_security_analysis(model, app_num)
        
    except Exception as e:
        logger.error(f"Security analysis error: {e}")
        return jsonify({'error': str(e)}), 500


def _run_containerized_security_analysis(model, app_num):
    """Run security analysis via containerized services."""
    try:
        # Get enabled tools from form
        tools = []
        if request.form.get('bandit') == 'on':
            tools.append('bandit')
        if request.form.get('safety') == 'on':
            tools.append('safety')
        if request.form.get('pylint') == 'on':
            tools.append('pylint')
        if request.form.get('eslint') == 'on':
            tools.append('eslint')
        if request.form.get('retire') == 'on':
            tools.append('retire')
        if request.form.get('npm_audit') == 'on':
            tools.append('npm-audit')
        
        # Default tools if none selected
        if not tools:
            tools = ['bandit', 'safety', 'eslint']
        
        # Get scan manager and submit to containerized service
        scan_manager = ServiceLocator.get_service('scan_manager')
        if not scan_manager or not hasattr(scan_manager, 'testing_client'):
            return jsonify({'error': 'Containerized testing service not available'}), 503
        
        # Submit analysis
        test_id = scan_manager.testing_client.submit_security_analysis(model, app_num, tools)
        
        return render_template("partials/security_analysis_submitted.html", 
                             test_id=test_id, tools=tools, model=model, app_num=app_num)
        
    except Exception as e:
        logger.error(f"Containerized security analysis failed: {e}")
        return render_template("partials/security_analysis_warning.html", 
                             error=str(e)) + _run_legacy_security_analysis(model, app_num)


def _run_legacy_security_analysis(model, app_num):
    """Legacy security analysis is no longer available - use containerized services."""
    return jsonify({
        'success': False,
        'error': 'Legacy security analysis service has been removed. Please use containerized testing services.',
        'recommendation': 'Deploy containerized services with: python testing-infrastructure/manage.py start'
    }), 503
    """Run CLI security analysis on specified app."""
    try:
        logger.info(f"Starting CLI security analysis for {model} app {app_num}")
        
        # Check for "use all tools" option
        use_all_tools = request.form.get('use_all_tools') == 'on'
        include_quality = request.form.get('include_quality') == 'on'
        
        # Get individual tool selections
        enabled_tools = {}
        if not use_all_tools:
            # Backend security tools
            enabled_tools['bandit'] = request.form.get('bandit') == 'on'
            enabled_tools['safety'] = request.form.get('safety') == 'on'
            enabled_tools['pylint'] = request.form.get('pylint') == 'on'
            enabled_tools['vulture'] = request.form.get('vulture') == 'on'
            
            # Frontend security tools
            enabled_tools['eslint'] = request.form.get('eslint') == 'on'
            enabled_tools['retire'] = request.form.get('retire') == 'on'
            enabled_tools['snyk'] = request.form.get('snyk') == 'on'
            enabled_tools['jshint'] = request.form.get('jshint') == 'on'
        
        # Get CLI analyzer service
        scan_service = ServiceLocator.get_scan_manager()
        if not scan_service:
            return jsonify({'error': 'CLI Analysis service not available'}), 503
        
        # Get the CLI analyzer
        from pathlib import Path
        
        # Initialize with base path (misc/models directory)
        base_path = Path(current_app.root_path).parent / "misc" / "models"
        cli_analyzer = UnifiedCLIAnalyzer(base_path)
        
        # Get application info
        app_info = AppDataProvider.get_app_info(model, app_num)
        
        # Check if application directory exists
        app_dir = base_path / model / f"app{app_num}"
        if not app_dir.exists():
            return render_template("partials/application_not_found.html", 
                                 model=model, app_num=app_num)
        
        # Run comprehensive CLI analysis
        if use_all_tools:
            analysis_results = cli_analyzer.run_full_analysis(
                model=model,
                app_num=app_num,
                use_all_tools=True,
                save_to_db=True
            )
        else:
            # Run selective analysis
            categories = [ToolCategory.BACKEND_SECURITY, ToolCategory.FRONTEND_SECURITY]
            if include_quality:
                categories.extend([ToolCategory.BACKEND_QUALITY, ToolCategory.FRONTEND_QUALITY])
            
            analysis_results = cli_analyzer.run_analysis(
                model=model,
                app_num=app_num,
                categories=categories,
                use_all_tools=False
            )
        
        # Check if analysis completed successfully
        if analysis_results and not any('error' in result for result in analysis_results.values() if isinstance(result, dict)):
            # Extract results from the analysis
            categories = {k: v for k, v in analysis_results.items() if k != 'metadata'}
            total_issues = sum(len(cat.get('issues', [])) for cat in categories.values() if isinstance(cat, dict))
            
            # Generate detailed results HTML
            results_html = []
            
            for category, data in categories.items():
                if isinstance(data, dict) and data.get('issues'):
                    category_name = category.replace('_', ' ').title()
                    results_html.append(f"""
                    <div class="analysis-category mb-3">
                        <h6 class="text-primary">
                            <i class="fas fa-{'server' if 'backend' in category else 'desktop' if 'frontend' in category else 'code'} mr-1"></i>
                            {category_name} ({len(data['issues'])} issues)
                        </h6>
                        <div class="issues-list">
                    """)
                    
                    for issue in data['issues'][:10]:  # Show first 10 issues
                        # Issue is a dictionary, so access its properties correctly
                        severity = issue.get('severity', 'LOW')
                        severity_class = {
                            'HIGH': 'severity-high',
                            'MEDIUM': 'severity-medium', 
                            'LOW': 'severity-low'
                        }.get(severity, 'severity-low')
                        
                        issue_text = issue.get('issue_text', 'Unknown issue')
                        filename = issue.get('filename', 'unknown')
                        line_number = issue.get('line_number', 0)
                        tool = issue.get('tool', 'unknown')
                        
                        results_html.append(f"""
                        <div class="analysis-result-item {severity_class} mb-2">
                            <div class="d-flex justify-content-between align-items-start">
                                <div>
                                    <strong>{tool}</strong>: {issue_text[:100]}{'...' if len(issue_text) > 100 else ''}
                                    <br><small class="text-muted">{filename}:{line_number}</small>
                                </div>
                                <span class="badge badge-{'danger' if severity == 'HIGH' else 'warning' if severity == 'MEDIUM' else 'info'}">{severity}</span>
                            </div>
                        </div>
                        """)
                    
                    if len(data['issues']) > 10:
                        results_html.append(f"""
                        <div class="text-muted text-center py-2">
                            <small>... and {len(data['issues']) - 10} more issues</small>
                        </div>
                        """)
                    
                    results_html.append("</div></div>")
            
            if not results_html:
                results_html.append("""
                <div class="alert alert-success text-center">
                    <i class="fas fa-check-circle fa-2x mb-2"></i>
                    <h6>No Issues Found</h6>
                    <p>All enabled tools completed successfully with no security or quality issues detected.</p>
                </div>
                """)
            
            return render_template("partials/security_analysis_completed.html", 
                                 total_issues=total_issues,
                                 results_html=''.join(results_html),
                                 timestamp=datetime.now().strftime('%H:%M:%S'),
                                 vulnerability_count=sum(1 for cat in categories.values() 
                                                        if isinstance(cat, dict) and cat.get('issues')
                                                        for issue in cat['issues'] 
                                                        if issue.get('severity') in ['HIGH', 'MEDIUM']))
        else:
            return render_template("partials/security_analysis_failed.html", 
                                 error=analysis_results.get('error', 'Unknown error'),
                                 details=analysis_results.get('details', 'No additional details available'))
            
    except Exception as e:
        logger.error(f"Security analysis error: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/analysis/<model>/<int:app_num>/results", methods=["GET"])
def get_analysis_results(model, app_num):
    """Get stored analysis results for an application."""
    try:
        # Get the most recent SecurityAnalysis record
        analysis = db.session.query(SecurityAnalysis)\
            .join(GeneratedApplication)\
            .filter(GeneratedApplication.model_slug == model,
                   GeneratedApplication.app_number == app_num)\
            .order_by(SecurityAnalysis.created_at.desc())\
            .first()
        
        if not analysis:
            return render_template("partials/no_analysis_results.html")
        
        # Parse the stored results
        results_data = analysis.get_results()
        if not results_data:
            return render_template("partials/analysis_results_unavailable.html")
        
        # Generate HTML for the results
        results_html = []
        total_issues = 0
        
        for category, data in results_data.items():
            if isinstance(data, dict) and 'issues' in data and data['issues']:
                category_name = category.replace('_', ' ').title()
                issue_count = len(data['issues'])
                total_issues += issue_count
                
                results_html.append(f"""
                <div class="analysis-category mb-3">
                    <h6 class="text-primary">
                        <i class="fas fa-{'server' if 'backend' in category else 'desktop' if 'frontend' in category else 'code'} mr-1"></i>
                        {category_name} ({issue_count} issues)
                    </h6>
                    <div class="issues-list">
                """)
                
                for issue in data['issues'][:10]:
                    severity_class = {
                        'HIGH': 'severity-high',
                        'MEDIUM': 'severity-medium', 
                        'LOW': 'severity-low'
                    }.get(issue.get('severity', 'LOW'), 'severity-low')
                    
                    results_html.append(f"""
                    <div class="analysis-result-item {severity_class} mb-2">
                        <div class="d-flex justify-content-between align-items-start">
                            <div>
                                <strong>{issue.get('tool', 'Unknown')}</strong>: {issue.get('issue_text', '')[:100]}{'...' if len(issue.get('issue_text', '')) > 100 else ''}
                                <br><small class="text-muted">{issue.get('filename', '')}:{issue.get('line_number', 0)}</small>
                            </div>
                            <span class="badge badge-{'danger' if issue.get('severity') == 'HIGH' else 'warning' if issue.get('severity') == 'MEDIUM' else 'info'}">{issue.get('severity', 'LOW')}</span>
                        </div>
                    </div>
                    """)
                
                if issue_count > 10:
                    results_html.append(f"""
                    <div class="text-muted text-center py-2">
                        <small>... and {issue_count - 10} more issues</small>
                    </div>
                    """)
                
                results_html.append("</div></div>")
        
        if not results_html:
            results_html.append("""
            <div class="alert alert-success text-center">
                <i class="fas fa-check-circle fa-2x mb-2"></i>
                <h6>No Issues Found</h6>
                <p>All analysis tools completed successfully with no issues detected.</p>
            </div>
            """)
        
        return render_template("partials/analysis_results_display.html", 
                             total_issues=total_issues,
                             results_html=''.join(results_html),
                             last_updated=analysis.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                             last_scan_time=analysis.created_at.strftime('%H:%M:%S'))
        
    except Exception as e:
        logger.error(f"Error loading analysis results: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/analysis/<model>/<int:app_num>/export", methods=["GET"])
def export_analysis_results(model, app_num):
    """Export analysis results as JSON."""
    try:
        # Get the most recent SecurityAnalysis record
        analysis = db.session.query(SecurityAnalysis)\
            .join(GeneratedApplication)\
            .filter(GeneratedApplication.model_slug == model,
                   GeneratedApplication.app_number == app_num)\
            .order_by(SecurityAnalysis.created_at.desc())\
            .first()
        
        if not analysis:
            return jsonify({'error': 'No analysis results found'}), 404
        
        # Prepare export data
        export_data = {
            'model': model,
            'app_number': app_num,
            'analysis_id': analysis.id,
            'created_at': analysis.created_at.isoformat(),
            'status': analysis.status,
            'total_issues': analysis.total_issues,
            'severity_counts': {
                'critical': analysis.critical_severity_count,
                'high': analysis.high_severity_count,
                'medium': analysis.medium_severity_count,
                'low': analysis.low_severity_count
            },
            'enabled_tools': analysis.get_enabled_tools(),
            'results': analysis.get_results()
        }
        
        # Create response with JSON download
        response = make_response(jsonify(export_data))
        response.headers['Content-Disposition'] = f'attachment; filename=analysis_{model}_app{app_num}_{analysis.created_at.strftime("%Y%m%d_%H%M%S")}.json'
        response.headers['Content-Type'] = 'application/json'
        return response
        
    except Exception as e:
        logger.error(f"Error exporting analysis results: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/analysis/<model>/<int:app_num>/zap", methods=["POST"])
def run_zap_scan(model, app_num):
    """Run ZAP security scan on specified app."""
    try:
        logger.info(f"Starting ZAP scan for {model} app {app_num}")
        
        # Get scan type
        scan_type = request.form.get('scan_type', 'spider')
        
        # Get ZAP service
        zap_service = ServiceLocator.get_service('zap_service')
        if not zap_service:
            return jsonify({'error': 'ZAP service not available'}), 503
        
        # Run the scan
        results = zap_service.run_zap_scan(
            model=model,
            app_num=app_num,
            scan_type=scan_type
        )
        
        if results['success']:
            vulnerabilities = results.get('data', {}).get('vulnerabilities', [])
            return render_template("partials/zap_scan_completed.html", 
                                 vulnerabilities=vulnerabilities)
        else:
            return render_template("partials/zap_scan_failed.html", 
                                 error=results.get('error', 'Unknown error'))
            
    except Exception as e:
        logger.error(f"ZAP scan error: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/analysis/<model>/<int:app_num>/status/<test_id>")
def get_analysis_status(model, app_num, test_id):
    """Get status of containerized analysis test."""
    try:
        # Get testing client from scan manager
        scan_manager = ServiceLocator.get_service('scan_manager')
        if not scan_manager or not hasattr(scan_manager, 'testing_client'):
            return jsonify({'error': 'Testing client not available'}), 503
        
        # Check test status
        status = scan_manager.testing_client.get_test_status(test_id, 'security')
        
        if status in ['completed', 'failed']:
            # Get results
            result = scan_manager.testing_client.get_test_result(test_id, 'security')
            
            if result and status == 'completed':
                issues = result.get('issues', [])
                return render_template("partials/security_analysis_complete.html", 
                                     total_issues=result.get('total_issues', 0),
                                     test_id=test_id,
                                     issues=issues)
            elif status == 'failed':
                return render_template("partials/security_analysis_test_failed.html", 
                                     test_id=test_id,
                                     error=result.get('error_message', 'Unknown error') if result else 'No error details available')
        else:
            # Still running
            return render_template('partials/security_analysis_running.html',
                                 status=status,
                                 test_id=test_id,
                                 model=model,
                                 app_num=app_num)
        
    except Exception as e:
        logger.error(f"Failed to get analysis status: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route("/status/<model>/<int:app_num>")
def get_app_status_api(model, app_num):
    """Get app status for HTMX updates."""
    try:
        # Get container status
        docker_service = ServiceLocator.get_docker_manager()
        if not docker_service:
            return render_template('partials/docker_service_unavailable.html')
        
        # Get port configuration
        app_info = AppDataProvider.get_app_info(model, app_num)
        if not app_info:
            return render_template('partials/app_info_not_found.html')
        
        # Check container status
        frontend_status = docker_service.get_container_status(
            model, app_num, 'frontend', app_info['frontend_port']
        )
        backend_status = docker_service.get_container_status(
            model, app_num, 'backend', app_info['backend_port']
        )
        
        return render_template('partials/container_status_display.html',
                             frontend_status=frontend_status, backend_status=backend_status)
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        return render_template('partials/status_check_failed.html')


# ===========================
# BATCH API ENDPOINTS (For HTMX compatibility)
# ===========================

@api_bp.route("/batch/jobs")
def api_batch_jobs():
    """Get list of batch jobs (HTMX compatible endpoint) - REMOVED - USE BATCH ROUTES INSTEAD."""
    return jsonify({
        'error': 'This endpoint has been moved. Use /api/batch/jobs instead.',
        'redirect': '/api/batch/jobs'
    }), 301


# Rate limiting cache for batch stats endpoint - per client
_batch_stats_clients = {}

@api_bp.route("/batch/stats")
def api_batch_stats():
    """Get batch statistics (HTMX compatible endpoint)."""
    try:
        # Add per-client rate limiting to prevent infinite loops
        import time
        global _batch_stats_clients
        
        client_ip = request.remote_addr
        current_time = time.time()
        
        # Minimal rate limiting: only prevent true rapid-fire requests (100+ req/sec)
        if client_ip in _batch_stats_clients:
            if current_time - _batch_stats_clients[client_ip] < 0.001:  # 1ms cooldown - only stops 1000+ req/sec
                logger.debug(f"Extreme rate limit hit for batch/stats endpoint from {client_ip}")
                return ResponseHandler.error_response("Rate limit exceeded", 429)
            
        _batch_stats_clients[client_ip] = current_time
        
        # Cleanup old entries (older than 5 minutes) to prevent memory leaks
        cutoff_time = current_time - 300  # 5 minutes
        # Use items() and update in place to avoid reassigning the global dict
        expired_ips = [ip for ip, timestamp in _batch_stats_clients.items() if timestamp <= cutoff_time]
        for ip in expired_ips:
            del _batch_stats_clients[ip]
        
        from models import BatchJob, JobStatus
        
        # Get basic statistics
        total_jobs = BatchJob.query.count()
        running_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.RUNNING).count()
        completed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.COMPLETED).count()
        failed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.FAILED).count()
        pending_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.PENDING).count()
        
        # Basic worker stats - simplified for now
        stats = {
            'total_jobs': total_jobs,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'pending_jobs': pending_jobs,
            'active_workers': 0,  # TODO: Implement worker tracking
            'total_workers': 0,   # TODO: Implement worker tracking
            'queue_size': pending_jobs  # Use pending jobs as queue size approximation
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_stats.html", stats=stats)
        
        return ResponseHandler.success_response(data=stats)
        
    except Exception as e:
        logger.error(f"Error getting batch stats: {e}")
        return ResponseHandler.error_response(str(e))


@batch_bp.route("/api/create", methods=["POST"])
def api_create_batch_job():
    """Redirect to the new endpoint."""
    return ResponseHandler.api_response(
        success=False,
        error="This endpoint has been moved. Use /api/batch/jobs instead.",
        message="Please use the new batch job creation endpoint"
    )


@api_bp.route("/batch/jobs/<job_id>/start", methods=["POST"])
def api_start_batch_job(job_id: str):
    """Start a batch job (HTMX compatible endpoint)."""
    try:
        from models import BatchJob, JobStatus
        from extensions import db
        
        job = BatchJob.query.get_or_404(job_id)
        
        if job.status != JobStatus.PENDING:
            return ResponseHandler.error_response(f"Job {job_id} is not in pending status")
        
        # Update job status
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        db.session.commit()
        
        # TODO: Start actual job processing with BatchAnalysisService
        
        return ResponseHandler.success_response(
            message=f"Job {job_id} started successfully"
        )
        
    except Exception as e:
        logger.error(f"Error starting batch job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/batch/jobs/<job_id>/stop", methods=["POST"])
def api_stop_batch_job(job_id: str):
    """Stop a batch job (HTMX compatible endpoint)."""
    try:
        from models import BatchJob, JobStatus
        from extensions import db
        
        job = BatchJob.query.get_or_404(job_id)
        
        if job.status != JobStatus.RUNNING:
            return ResponseHandler.error_response(f"Job {job_id} is not running")
        
        # Update job status
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        db.session.commit()
        
        # TODO: Stop actual job processing
        
        return ResponseHandler.success_response(
            message=f"Job {job_id} stopped successfully"
        )
        
    except Exception as e:
        logger.error(f"Error stopping batch job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/batch/jobs/<job_id>", methods=["DELETE"])
def api_delete_batch_job(job_id: str):
    """Delete a batch job (HTMX compatible endpoint)."""
    try:
        from models import BatchJob
        from extensions import db
        
        job = BatchJob.query.get_or_404(job_id)
        
        # Delete associated tasks first (cascade should handle this, but be explicit)
        for task in job.tasks:
            db.session.delete(task)
        
        db.session.delete(job)
        db.session.commit()
        
        return ResponseHandler.success_response(
            message=f"Job {job_id} deleted successfully"
        )
        
    except Exception as e:
        logger.error(f"Error deleting batch job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# BATCH TESTING ROUTES
# ===========================

@batch_testing_bp.route("/")
def batch_testing_dashboard():
    """Batch testing dashboard page."""
    try:
        service = get_batch_testing_service()
        
        # Get basic stats for dashboard
        all_jobs = service.get_all_jobs()
        stats = {
            'total_jobs': len(all_jobs),
            'running_jobs': len([j for j in all_jobs if j['status'] == 'running']),
            'completed_jobs': len([j for j in all_jobs if j['status'] == 'completed']),
            'total_issues': sum(j.get('total_issues', 0) for j in all_jobs if j['status'] == 'completed')
        }
        
        return ResponseHandler.render_response("batch_testing.html", stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading batch testing dashboard: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/jobs")
def api_get_batch_jobs():
    """Get list of batch testing jobs with optional filtering."""
    try:
        service = get_batch_testing_service()
        
        status_filter = request.args.get('status')
        test_type_filter = request.args.get('test_type')
        
        jobs = service.get_all_jobs(status_filter, test_type_filter)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_jobs_list.html", jobs=jobs)
        
        return ResponseHandler.success_response(data=jobs)
        
    except Exception as e:
        logger.error(f"Error getting batch jobs: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/create", methods=["POST"])
def api_create_batch_testing_job():
    """Create a new batch testing job."""
    try:
        service = get_batch_testing_service()
        
        # Get form data and map to container operation format
        job_config = {
            'operation_type': request.form.get('operation_type'),  # Fixed: use operation_type instead of test_type
            'job_name': request.form.get('job_name'),
            'description': request.form.get('description', ''),
            'tools': request.form.getlist('tools'),
            'target_selection': request.form.get('target_selection', 'models'),  # Fixed: use target_selection
            'concurrency': int(request.form.get('concurrency', 3)),
            'timeout': int(request.form.get('timeout', 300)),
            'fail_fast': request.form.get('fail_fast') == 'true',
            'container_options': {
                'wait_healthy': request.form.get('wait_healthy') == 'true',
                'pull_images': request.form.get('pull_images') == 'true',
                'force_recreate': request.form.get('force_recreate') == 'true',
                'remove_orphans': request.form.get('remove_orphans') == 'true'
            }
        }
        
        # Handle model/app selection based on target_selection method
        target_selection = job_config['target_selection']
        if target_selection == 'models':
            job_config['selected_models'] = request.form.getlist('selected_models')
        elif target_selection == 'running_containers':
            # For running containers, we'll let the service determine which containers are running
            pass
        elif target_selection == 'custom':
            job_config['custom_models'] = request.form.get('custom_models', '')
            job_config['selected_apps'] = request.form.get('selected_apps', '1-30')
        
        result = service.create_batch_job(job_config)
        
        if result['success']:
            return ResponseHandler.success_response(
                data={'job_id': result['job_id']},
                message=result['message']
            )
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error creating batch job: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/job/<job_id>/details")
def api_get_job_details(job_id: str):
    """Get detailed information about a batch job."""
    try:
        service = get_batch_testing_service()
        job = service.get_job_details(job_id)
        
        if not job:
            return ResponseHandler.error_response("Job not found", 404)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_job_details.html", job=job)
        
        return ResponseHandler.success_response(data=job)
        
    except Exception as e:
        logger.error(f"Error getting job details for {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/job/<job_id>/results")
def api_get_job_results(job_id: str):
    """Get comprehensive results for a completed job."""
    try:
        service = get_batch_testing_service()
        results = service.get_job_results(job_id)
        
        if not results:
            return ResponseHandler.error_response("Job not found or not completed", 404)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_job_results.html", results=results)
        
        return ResponseHandler.success_response(data=results)
        
    except Exception as e:
        logger.error(f"Error getting job results for {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/job/<job_id>/start", methods=["POST"])
def api_start_job(job_id: str):
    """Start execution of a batch job."""
    try:
        service = get_batch_testing_service()
        result = service.start_job(job_id)
        
        if result['success']:
            return ResponseHandler.success_response(message=result['message'])
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error starting job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/job/<job_id>/cancel", methods=["POST"])
def api_cancel_job(job_id: str):
    """Cancel a running batch job."""
    try:
        service = get_batch_testing_service()
        result = service.cancel_job(job_id)
        
        if result['success']:
            return ResponseHandler.success_response(message=result['message'])
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/job/<job_id>/delete", methods=["DELETE"])
def api_delete_job(job_id: str):
    """Delete a batch job."""
    try:
        service = get_batch_testing_service()
        result = service.delete_job(job_id)
        
        if result['success']:
            return ResponseHandler.success_response(message=result['message'])
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {e}")
        return ResponseHandler.error_response(str(e))


@batch_testing_bp.route("/api/models")
def api_get_available_models():
    """Get list of available models for batch testing."""
    try:
        service = get_batch_testing_service()
        models = service.get_available_models()
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_model_selection.html", models=models)
        
        return ResponseHandler.success_response(data=models)
        
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# TESTING INFRASTRUCTURE ROUTES
# ===========================

testing_bp = Blueprint("testing", __name__, url_prefix="/testing")

@testing_bp.route("/")
def testing_dashboard():
    """Security testing dashboard page."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        # Get basic stats for dashboard
        all_jobs = service.get_all_jobs()
        stats = {
            'total_jobs': len(all_jobs),
            'running_jobs': len([j for j in all_jobs if j['status'] == 'running']),
            'completed_jobs': len([j for j in all_jobs if j['status'] == 'completed']),
            'total_issues': sum(j.get('total_issues', 0) for j in all_jobs if j['status'] == 'completed'),
            'analyzed_apps': len(set((j.get('model'), j.get('app_num')) for j in all_jobs if j['status'] == 'completed'))
        }
        
        return ResponseHandler.render_response("batch_testing.html", stats=stats)
        
    except Exception as e:
        logger.error(f"Error loading testing dashboard: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/health")
def api_get_infrastructure_health():
    """Get testing infrastructure health status."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        health_data = service.get_service_health()
        return ResponseHandler.success_response(data=health_data)
        
    except Exception as e:
        logger.error(f"Error getting infrastructure health: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/tools")
def api_get_available_tools():
    """Get information about available security testing tools."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        tools_data = service.get_available_tools()
        return ResponseHandler.success_response(data=tools_data)
        
    except Exception as e:
        logger.error(f"Error getting available tools: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/jobs")
def api_get_testing_jobs():
    """Get list of testing jobs with optional filtering."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        status_filter = request.args.get('status')
        test_type_filter = request.args.get('test_type')
        model_filter = request.args.get('model')
        
        jobs = service.get_all_jobs(status_filter)
        
        # Apply additional filters
        if test_type_filter:
            jobs = [j for j in jobs if j.get('test_type') == test_type_filter]
        if model_filter:
            jobs = [j for j in jobs if j.get('model') == model_filter]
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/security_testing_jobs_list.html", jobs=jobs)
        
        return ResponseHandler.success_response(data=jobs)
        
    except Exception as e:
        logger.error(f"Error getting testing jobs: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/create", methods=["POST"])
def api_create_testing_job():
    """Create a new security testing job."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        test_type = request.form.get('test_type')
        
        if test_type == 'security_analysis':
            result = service.create_security_analysis_job({
                'model': request.form.get('model'),
                'app_num': request.form.get('app_num'),
                'tools': request.form.getlist('tools'),
                'scan_depth': request.form.get('scan_depth', 'standard'),
                'include_dependencies': request.form.get('include_dependencies') == 'on',
                'tool_options': {
                    'bandit': {
                        'severity': request.form.get('bandit_severity', 'MEDIUM'),
                        'confidence': request.form.get('bandit_confidence', 'MEDIUM'),
                        'skip': request.form.get('bandit_skip', '')
                    },
                    'safety': {
                        'apply_fixes': request.form.get('safety_apply_fixes') == 'on',
                        'detailed': request.form.get('safety_detailed') == 'on',
                        'ignore': request.form.get('safety_ignore', '')
                    },
                    'pylint': {
                        'types': request.form.getlist('pylint_types'),
                        'disable': request.form.get('pylint_disable', '')
                    },
                    'semgrep': {
                        'config': request.form.get('semgrep_config', 'auto'),
                        'max_memory': request.form.get('semgrep_max_memory', '2000'),
                        'timeout': request.form.get('semgrep_timeout', '30')
                    },
                    'eslint': {
                        'config': request.form.get('eslint_config', 'recommended'),
                        'fix': request.form.get('eslint_fix') == 'on',
                        'max_warnings': request.form.get('eslint_max_warnings', '50')
                    },
                    'retire': {
                        'severity': request.form.get('retire_severity', 'medium'),
                        'include_dev': request.form.get('retire_include_dev') == 'on'
                    },
                    'npm_audit': {
                        'level': request.form.get('npm_audit_level', 'moderate'),
                        'production': request.form.get('npm_production') == 'on',
                        'fix': request.form.get('npm_fix') == 'on'
                    }
                }
            })
            
        elif test_type == 'zap_scan':
            zap_options = {
                'scan_type': request.form.get('zap_scan_type', 'spider')
            }
            
            # Add scan-specific options
            scan_type = request.form.get('zap_scan_type', 'spider')
            if scan_type == 'spider':
                zap_options.update({
                    'max_depth': request.form.get('zap_max_depth', '5'),
                    'max_children': request.form.get('zap_max_children', '100'),
                    'recurse': request.form.get('zap_recurse') == 'on'
                })
            elif scan_type == 'active':
                zap_options.update({
                    'strength': request.form.get('zap_strength', 'Medium'),
                    'max_rule_duration': request.form.get('zap_max_rule_duration', '5'),
                    'in_scope_only': request.form.get('zap_in_scope_only') == 'on'
                })
            elif scan_type == 'baseline':
                zap_options.update({
                    'duration': request.form.get('zap_duration', '10'),
                    'level': request.form.get('zap_level', 'Warn')
                })
            elif scan_type == 'passive':
                zap_options.update({
                    'max_alerts': request.form.get('zap_max_alerts', '1000'),
                    'context_name': request.form.get('zap_context_name', '')
                })
            
            result = service.create_zap_scan_job({
                'model': request.form.get('model'),
                'app_num': request.form.get('app_num'),
                'target_url': request.form.get('target_url'),
                'scan_type': scan_type,
                'scan_options': zap_options
            })
            
        elif test_type == 'performance_test':
            result = service.create_performance_test_job({
                'model': request.form.get('model'),
                'app_num': request.form.get('app_num'),
                'target_url': request.form.get('performance_target_url'),
                'users': request.form.get('performance_users', '10'),
                'spawn_rate': request.form.get('performance_spawn_rate', '2'),
                'duration': request.form.get('performance_duration', '60')
            })
            
        else:
            return ResponseHandler.error_response("Invalid test type")
        
        if result['success']:
            return ResponseHandler.success_response(
                data={'job_id': result['job_id']},
                message=result['message']
            )
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error creating testing job: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/test/<test_id>/details")
def api_get_test_details(test_id: str):
    """Get detailed information about a test."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        result = service.get_job_status(test_id)
        
        if not result['success']:
            return ResponseHandler.error_response(result['error'], 404)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/security_test_details.html", test=result['job'])
        
        return ResponseHandler.success_response(data=result['job'])
        
    except Exception as e:
        logger.error(f"Error getting test details for {test_id}: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/test/<test_id>/results")
def api_get_test_results(test_id: str):
    """Get comprehensive results for a completed test."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        result = service.get_job_result(test_id)
        
        if not result['success']:
            return ResponseHandler.error_response(result['error'], 404)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/security_test_results.html", results=result['result'])
        
        return ResponseHandler.success_response(data=result['result'])
        
    except Exception as e:
        logger.error(f"Error getting test results for {test_id}: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/test/<test_id>/cancel", methods=["POST"])
def api_cancel_test(test_id: str):
    """Cancel a running test."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        result = service.cancel_job(test_id)
        
        if result['success']:
            return ResponseHandler.success_response(message=result['message'])
        else:
            return ResponseHandler.error_response(result['error'])
        
    except Exception as e:
        logger.error(f"Error cancelling test {test_id}: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/infrastructure-status")
def api_get_infrastructure_status():
    """Get detailed infrastructure status for modal display."""
    try:
        from testing_infrastructure_service import get_testing_infrastructure_service
        service = get_testing_infrastructure_service()
        
        health_data = service.get_service_health()
        tools_data = service.get_available_tools()
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/infrastructure_status_details.html", 
                                 health=health_data, tools=tools_data)
        
        return ResponseHandler.success_response(data={'health': health_data, 'tools': tools_data})
        
    except Exception as e:
        logger.error(f"Error getting infrastructure status: {e}")
        return ResponseHandler.error_response(str(e))


@testing_bp.route("/api/models")
def api_get_models():
    """Get list of available AI models from database."""
    try:
        from models import ModelCapability
        
        # Get all models from database
        models = ModelCapability.query.all()
        
        models_data = []
        for model in models:
            models_data.append({
                'id': model.canonical_slug,
                'name': model.model_name,
                'provider': model.provider,
                'display_name': f"{model.provider} - {model.model_name}",
                'slug': model.canonical_slug
            })
        
        # Sort by provider then by name
        models_data.sort(key=lambda x: (x['provider'], x['name']))
        
        return ResponseHandler.success_response(data=models_data)
        
    except Exception as e:
        logger.error(f"Error getting models from database: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# BLUEPRINT REGISTRATION
# ===========================

def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(statistics_bp)
    
    # Register legacy batch blueprint for compatibility
    app.register_blueprint(batch_bp)
    
    # Register batch testing blueprint
    app.register_blueprint(batch_testing_bp)
    
    # Register testing infrastructure blueprint
    app.register_blueprint(testing_bp)
    
    app.register_blueprint(docker_bp)
    
    # Register template helpers
    register_template_helpers(app)
    
    logger.info("All blueprints registered successfully")


# Export blueprints for use in app factory
__all__ = [
    'main_bp', 'api_bp', 'statistics_bp', 'batch_bp', 'docker_bp', 'batch_testing_bp', 'testing_bp',
    'register_blueprints'
]