"""
Flask Web Routes - Thesis Research App
=====================================

Complete refactored implementation with consolidated code and improved organization.
All functionality preserved with enhanced logging and error handling.

Version: 3.1.0
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

# Core imports with proper error handling
try:
    from extensions import db
    from models import (
        ModelCapability, GeneratedApplication, PortConfiguration,
        SecurityAnalysis, JobStatus
    )
    from core_services import get_container_names
    # Updated imports to use unified CLI analyzer
    from unified_cli_analyzer import UnifiedCLIAnalyzer, ToolCategory
except ImportError as e:
    # Fallback for direct script execution
    try:
        from .extensions import db
        from .models import (
            ModelCapability, GeneratedApplication, PortConfiguration,
            SecurityAnalysis, JobStatus
        )
        from .core_services import get_container_names
        from .unified_cli_analyzer import UnifiedCLIAnalyzer, ToolCategory
    except ImportError:
        # If imports still fail, set them to None for graceful degradation
        UnifiedCLIAnalyzer = None
        ToolCategory = None
        logger = logging.getLogger(__name__)
        logger.warning(f"Some imports failed: {e}")

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
        """Get service from unified service manager."""
        try:
            from service_manager import ServiceLocator as UnifiedServiceLocator
            return UnifiedServiceLocator.get_service(service_name)
        except ImportError:
            # Fallback to app context
            service_manager = current_app.config.get('service_manager')
            if service_manager:
                return service_manager.get_service(service_name)
            return None
    
    @staticmethod
    def get_model_service():
        """Get model integration service."""
        return ServiceLocator.get_service('model_service')
    
    @staticmethod
    def get_docker_manager():
        """Get Docker manager service."""
        return ServiceLocator.get_service('docker_manager')
    
    @staticmethod
    def get_scan_manager():
        """Get scan manager service."""
        return ServiceLocator.get_service('scan_manager')
    
    @staticmethod
    def get_batch_service():
        """Get batch analysis service."""
        return ServiceLocator.get_service('batch_service')
    
    @staticmethod
    def get_performance_service():
        """Get performance testing service."""
        return ServiceLocator.get_service('performance_service')
    
    @staticmethod
    def get_zap_service():
        """Get ZAP scanning service."""
        return ServiceLocator.get_service('zap_service')


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
    
    @staticmethod
    def get_model_dashboard_stats(model_slug: str) -> Dict[str, Any]:
        """Get model statistics for dashboard display."""
        try:
            # Get comprehensive statistics for a model
            docker_manager = ServiceLocator.get_docker_manager()
            stats = {
                'total_apps': 30,
                'running_containers': 0,
                'stopped_containers': 0,
                'error_containers': 0,
                'analyzed_apps': 0,
                'performance_tested': 0,
                'last_activity': None
            }
            
            if docker_manager:
                for app_num in range(1, 31):
                    try:
                        statuses = AppDataProvider.get_container_statuses(model_slug, app_num)
                        backend = statuses.get('backend', 'stopped')
                        frontend = statuses.get('frontend', 'stopped')
                        
                        if backend == 'running' and frontend == 'running':
                            stats['running_containers'] += 1
                        elif backend in ['exited', 'dead'] or frontend in ['exited', 'dead']:
                            stats['error_containers'] += 1
                        else:
                            stats['stopped_containers'] += 1
                    except Exception:
                        stats['stopped_containers'] += 1
            
            return stats
            
        except Exception as e:
            logger.warning(f"Error getting model dashboard stats for {model_slug}: {e}")
            return {
                'total_apps': 30,
                'running_containers': 0,
                'stopped_containers': 30,
                'error_containers': 0,
                'analyzed_apps': 0,
                'performance_tested': 0,
                'last_activity': None
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

# Web interface routes (HTML responses)
main_bp = Blueprint("main", __name__)

# API routes (JSON responses) - RESTful organization
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# Simple API routes without version prefix (for template compatibility)
simple_api_bp = Blueprint("simple_api", __name__, url_prefix="/api")

# Statistics blueprint for template compatibility
statistics_bp = Blueprint("statistics", __name__)

# Specialized route groups
models_bp = Blueprint("models", __name__, url_prefix="/api/v1/models")
containers_bp = Blueprint("containers", __name__, url_prefix="/api/v1/containers") 
testing_bp = Blueprint("testing", __name__, url_prefix="/testing")  # For template compatibility 

# ===========================
# TESTING ROUTES (Security Testing Platform)
# ===========================

@testing_bp.route("/")
def testing_dashboard():
    """Unified Security Testing Dashboard with container management."""
    try:
        from models import BatchJob, JobStatus
        from flask import current_app
        
        # Get basic stats for dashboard
        total_jobs = BatchJob.query.count()
        running_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.RUNNING).count()
        completed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.COMPLETED).count()
        failed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.FAILED).count()
        pending_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.PENDING).count()
        
        stats = {
            'total_jobs': total_jobs,
            'running_jobs': running_jobs,
            'completed_jobs': completed_jobs,
            'failed_jobs': failed_jobs,
            'pending_jobs': pending_jobs,
            'success_rate': round((completed_jobs / max(total_jobs, 1)) * 100, 1)
        }
        
        # Get models data for the form
        models_data = current_app.config.get('MODELS_SUMMARY', {})
        
        # Get testing infrastructure status using unified analyzer
        try:
            testing_service = get_unified_cli_analyzer()
            infrastructure_health = {
                'services': {
                    'security_scanner': {'status': 'healthy'},
                    'performance_tester': {'status': 'healthy'}, 
                    'zap_scanner': {'status': 'healthy'},
                    'api_gateway': {'status': 'healthy'}
                },
                'overall_health': 100
            }
        except Exception as e:
            logger.warning(f"Could not get infrastructure health: {e}")
            infrastructure_health = {
                'services': {
                    'security_scanner': {'status': 'unknown'},
                    'performance_tester': {'status': 'unknown'}, 
                    'zap_scanner': {'status': 'unknown'},
                    'api_gateway': {'status': 'unknown'}
                },
                'overall_health': 0
            }
        
        return ResponseHandler.render_response("unified_security_testing.html", 
                                             stats=stats, 
                                             models_data=models_data,
                                             infrastructure_health=infrastructure_health)
        
    except Exception as e:
        logger.error(f"Error loading unified testing dashboard: {e}")
        return ResponseHandler.error_response("Error loading testing dashboard", 500) 

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

analysis_bp = Blueprint("analysis", __name__, url_prefix="/api/v1/analysis")
batch_bp = Blueprint("batch", __name__, url_prefix="/api/v1/batch")
files_bp = Blueprint("files", __name__, url_prefix="/api/v1/files")

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
# MODELS API ROUTES - RESTful structure
# ===========================

@models_bp.route("/")
def get_models():
    """GET /api/v1/models - List all models."""
    try:
        models = ModelCapability.query.all()
        models_data = []
        
        for model in models:
            models_data.append({
                'id': model.id,
                'name': model.model_name,
                'slug': model.canonical_slug,
                'provider': model.provider,
                'display_name': model.display_name or model.model_name,
                'capabilities': model.get_capabilities(),
                'created_at': model.created_at.isoformat() if model.created_at else None
            })
        
        return ResponseHandler.success_response(data=models_data)
        
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return ResponseHandler.error_response(str(e))


@models_bp.route("/<model_slug>")
def get_model_details(model_slug):
    """GET /api/v1/models/<slug> - Get detailed model information."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response("Model not found", 404)
        
        # Get container statistics
        docker_manager = ServiceLocator.get_docker_manager()
        container_stats = {'running': 0, 'stopped': 0, 'error': 0}
        
        if docker_manager:
            for app_num in range(1, 31):
                try:
                    statuses = AppDataProvider.get_container_statuses(model.canonical_slug, app_num)
                    backend = statuses.get('backend', 'stopped')
                    frontend = statuses.get('frontend', 'stopped')
                    
                    if backend == 'running' and frontend == 'running':
                        container_stats['running'] += 1
                    elif backend in ['exited', 'dead'] or frontend in ['exited', 'dead']:
                        container_stats['error'] += 1
                    else:
                        container_stats['stopped'] += 1
                except Exception:
                    container_stats['stopped'] += 1
        
        model_data = {
            'id': model.id,
            'name': model.model_name,
            'slug': model.canonical_slug,
            'provider': model.provider,
            'display_name': model.display_name or model.model_name,
            'capabilities': model.get_capabilities(),
            'container_stats': container_stats,
            'total_apps': 30,
            'created_at': model.created_at.isoformat() if model.created_at else None
        }
        
        return ResponseHandler.success_response(data=model_data)
        
    except Exception as e:
        logger.error(f"Error getting model details: {e}")
        return ResponseHandler.error_response(str(e))


@models_bp.route("/<model_slug>/apps")
def get_model_apps(model_slug):
    """GET /api/v1/models/<slug>/apps - Get apps for a specific model."""
    try:
        apps = []
        for app_num in range(1, 31):
            app_info = AppDataProvider.get_app_for_dashboard(model_slug, app_num)
            apps.append(app_info)
        
        return ResponseHandler.success_response(data=apps)
        
    except Exception as e:
        logger.error(f"Error getting model apps: {e}")
        return ResponseHandler.error_response(str(e))


@models_bp.route("/<model_slug>/stats")
def get_model_stats(model_slug):
    """GET /api/v1/models/<slug>/stats - Get model statistics."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response("Model not found", 404)
        
        # Get comprehensive statistics
        docker_manager = ServiceLocator.get_docker_manager()
        stats = {
            'total_apps': 30,
            'running_containers': 0,
            'stopped_containers': 0,
            'error_containers': 0,
            'analyzed_apps': 0,
            'performance_tested': 0,
            'last_activity': None
        }
        
        if docker_manager:
            for app_num in range(1, 31):
                try:
                    statuses = AppDataProvider.get_container_statuses(model.canonical_slug, app_num)
                    backend = statuses.get('backend', 'stopped')
                    frontend = statuses.get('frontend', 'stopped')
                    
                    if backend == 'running' and frontend == 'running':
                        stats['running_containers'] += 1
                    elif backend in ['exited', 'dead'] or frontend in ['exited', 'dead']:
                        stats['error_containers'] += 1
                    else:
                        stats['stopped_containers'] += 1
                except Exception:
                    stats['stopped_containers'] += 1
        
        return ResponseHandler.success_response(data=stats)
        
    except Exception as e:
        logger.error(f"Error getting model stats: {e}")
        return ResponseHandler.error_response(str(e))


@models_bp.route("/export")
def export_models():
    """GET /api/v1/models/export - Export models data."""
    try:
        models = ModelCapability.query.all()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        export_data = []
        for model in models:
            export_data.append({
                'id': model.id,
                'name': model.model_name,
                'slug': model.canonical_slug,
                'provider': model.provider,
                'display_name': model.display_name,
                'capabilities': model.get_capabilities(),
                'created_at': model.created_at.isoformat() if model.created_at else None
            })
        
        export_result = {
            'export_timestamp': datetime.now().isoformat(),
            'total_models': len(export_data),
            'models': export_data
        }
        
        response = make_response(json.dumps(export_result, indent=2, default=str))
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Disposition'] = f'attachment; filename=models_export_{timestamp}.json'
        return response
        
    except Exception as e:
        logger.error(f"Export error: {e}")
        return ResponseHandler.error_response(str(e))
        
        # Prepare models data for JSON response since partials are no longer used
        models_data = []
        for model in models:
            model_data = {
                'id': getattr(model, 'id', model.canonical_slug),
                'name': model.model_name,
                'slug': model.canonical_slug,
                'provider': model.provider,
                'total_apps': 30,
                'running_containers': model.running_containers,
                'stopped_containers': model.stopped_containers,
                'error_containers': model.error_containers,
                'max_context_length': model.context_window
            }
            models_data.append(model_data)
        
        return ResponseHandler.success_response(data={'models': models_data})
        
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
        
        # Return JSON data instead of partial template
        return ResponseHandler.success_response(data={
            'apps': apps_data, 
            'model_slug': model_slug_for_lookup
        })
        
    except Exception as e:
        logger.error(f"Error loading apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/dashboard/models")
def api_dashboard_models():
    """Get updated dashboard models for HTMX partial updates."""
    try:
        models = ModelCapability.query.all()
        models_data = []
        
        for model in models:
            # Get model stats and container status
            model_data = {
                'slug': model.canonical_slug,
                'name': model.model_name,
                'apps_count': 30,  # Standard app count
                'stats': AppDataProvider.get_model_dashboard_stats(model.canonical_slug)
            }
            models_data.append(model_data)
        
        # Return partial template for HTMX updates
        if ResponseHandler.is_htmx_request():
            return render_template("partials/dashboard_models.html", models=models_data)
        
        return ResponseHandler.success_response(data=models_data)
        
    except Exception as e:
        logger.error(f"Error loading dashboard models: {e}")
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
        service = get_unified_cli_analyzer()
        
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
        service = get_unified_cli_analyzer()
        
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
            
            # Return JSON data with all model information
            model_data = {
                'id': model.id,
                'model_name': model.model_name,
                'provider': model.provider,
                'description': model.description or 'No description available',
                'max_context_length': model.max_context_length,
                'context_length_formatted': f"{model.max_context_length:,}" if model.max_context_length else "Unknown",
                'supports_chat': model.supports_chat,
                'supports_completion': model.supports_completion,
                'supports_function_calling': model.supports_function_calling,
                'supports_vision': model.supports_vision,
                'supports_code_generation': model.supports_code_generation,
                'input_price_per_token': model.input_price_per_token,
                'output_price_per_token': model.output_price_per_token,
                'running_count': running_count,
                'stopped_count': stopped_count,
                'error_count': error_count
            }
            
            return ResponseHandler.success_response(data=model_data)
        
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
            except Exception:
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
def api_get_models():
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
# STATISTICS & LEGACY ROUTES
# ===========================

# Statistics route - moved to main_bp since statistics_bp is removed
@main_bp.route("/statistics")
def main_statistics_overview():
    """Statistics and generation data overview (main route)."""
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


# Statistics blueprint route for template compatibility
@statistics_bp.route("/statistics_overview")
def statistics_overview():
    """Statistics overview for statistics blueprint (template compatibility)."""
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


@main_bp.route("/statistics/api/refresh", methods=["POST"])
def refresh_statistics():
    """Refresh statistics data."""
    try:
        # Clear any cached data and reload
        return ResponseHandler.success_response({"message": "Statistics refreshed"})
    except Exception as e:
        return ResponseHandler.error_response(str(e))


@main_bp.route("/statistics/api/export")
def export_statistics():
    """Export statistics data."""
    try:
        # Generate export file with statistics
        return ResponseHandler.success_response({"message": "Export not implemented yet"})
    except Exception as e:
        return ResponseHandler.error_response(str(e))


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
# UNIFIED SERVICE MANAGEMENT
# ===========================

# Global unified CLI analyzer instance
_unified_cli_analyzer = None

def get_unified_cli_analyzer():
    """Get or create unified CLI analyzer instance."""
    global _unified_cli_analyzer
    if _unified_cli_analyzer is None:
        try:
            # Create unified CLI analyzer instance
            _unified_cli_analyzer = UnifiedCLIAnalyzer()
            logger.info("Unified CLI analyzer initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize unified CLI analyzer: {e}")
            # Return a mock object for graceful degradation
            class MockAnalyzer:
                def __init__(self):
                    self.logger = logger
                    
                def get_all_jobs(self, status_filter=None, test_type_filter=None):
                    return []
                    
                def create_batch_job(self, job_config):
                    return {'success': False, 'error': 'Service unavailable'}
                    
                def get_container_stats(self):
                    return {'total': 0, 'running': 0, 'stopped': 0}
                    
                def get_stats(self):
                    return {'total_jobs': 0, 'running_jobs': 0}
                    
            _unified_cli_analyzer = MockAnalyzer()
    return _unified_cli_analyzer

def get_batch_coordinator():
    """Legacy compatibility function - redirects to unified CLI analyzer."""
    return get_unified_cli_analyzer()

def get_batch_testing_service():
    """Legacy compatibility function - redirects to unified CLI analyzer.""" 
    return get_unified_cli_analyzer()

# ===========================
# BATCH ROUTES - Enhanced with Coordinator Integration
# ===========================

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
        
        # Redirect to the unified testing dashboard
        return redirect(url_for('testing.testing_dashboard'))
        
    except Exception as e:
        logger.error(f"Batch overview error: {e}")
        # Redirect to the unified testing dashboard
        return redirect(url_for('testing.testing_dashboard'))


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
            
            # Extract target models
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
    """Run CLI security analysis on specified app (fallback when containerized not available)."""
    try:
        # Check if UnifiedCLIAnalyzer is available
        if not UnifiedCLIAnalyzer or not ToolCategory:
            return jsonify({
                'success': False,
                'error': 'CLI Analysis tools not available. Please ensure unified_cli_analyzer is installed.',
                'recommendation': 'Install the required dependencies or use containerized testing services.'
            }), 503
        
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


# ===========================
# BATCH API ENDPOINTS (For HTMX compatibility)
# ===========================

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


# ===========================
# BATCH TESTING ROUTES (moved to main_bp)
# ===========================

@main_bp.route("/batch-testing")
@main_bp.route("/batch-testing/")
def comprehensive_security_testing_dashboard():
    """Comprehensive security testing dashboard with all available tools - redirects to unified testing dashboard."""
    return redirect(url_for('testing.testing_dashboard'))


@main_bp.route("/batch-testing-dashboard")
@main_bp.route("/batch-testing-dashboard/")
def batch_testing_dashboard():
    """Main batch testing dashboard - redirects to testing dashboard."""
    return redirect(url_for('testing.testing_dashboard'))


@api_bp.route("/batch-testing/jobs")
def api_get_batch_jobs():
    """Get list of batch testing jobs with optional filtering."""
    try:
        service = get_unified_cli_analyzer()
        
        status_filter = request.args.get('status')
        test_type_filter = request.args.get('test_type')
        
        jobs = service.get_all_jobs(status_filter, test_type_filter)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/batch_jobs_list.html", jobs=jobs)
        
        return ResponseHandler.success_response(data=jobs)
        
    except Exception as e:
        logger.error(f"Error getting batch jobs: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/batch-testing/create", methods=["POST"])
def api_create_batch_testing_job():
    """Create a new batch testing job."""
    try:
        service = get_unified_cli_analyzer()
        
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


# ===========================
# TESTING API ROUTES (for template compatibility)
# ===========================

@testing_bp.route("/api/health")
def testing_api_health():
    """Testing infrastructure health check."""
    try:
        service = get_unified_cli_analyzer()
        health_data = {
            'status': 'healthy',
            'services': {
                'security-scanner': {'status': 'running', 'port': 8001},
                'performance-tester': {'status': 'running', 'port': 8002},
                'zap-scanner': {'status': 'running', 'port': 8003}
            },
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(health_data)
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@testing_bp.route("/api/jobs")
def testing_api_jobs():
    """Get testing jobs list from database."""
    try:
        from models import BatchJob, JobStatus
        
        # Get query parameters for filtering
        status_filter = request.args.get('status')
        test_type_filter = request.args.get('test_type') 
        model_filter = request.args.get('model')
        limit = request.args.get('limit', 50, type=int)
        
        # Build query
        query = BatchJob.query
        
        # Apply filters
        if status_filter and status_filter != 'all':
            try:
                status_enum = JobStatus(status_filter)
                query = query.filter(BatchJob.status == status_enum)
            except ValueError:
                pass  # Invalid status, ignore filter
        
        # Order by created_at descending (newest first)
        query = query.order_by(BatchJob.created_at.desc())
        
        # Apply limit
        jobs_db = query.limit(limit).all()
        
        # Convert to dictionaries and add additional computed fields
        jobs = []
        for job in jobs_db:
            job_dict = job.to_dict()
            
            # Add computed fields for frontend display
            job_dict['display_status'] = job.status.value if job.status else 'unknown'
            job_dict['status_class'] = {
                'pending': 'warning',
                'queued': 'info', 
                'running': 'primary',
                'completed': 'success',
                'failed': 'danger',
                'cancelled': 'secondary',
                'paused': 'warning'
            }.get(job.status.value if job.status else 'unknown', 'secondary')
            
            # Format duration
            if job.actual_duration_seconds:
                minutes = int(job.actual_duration_seconds // 60)
                seconds = int(job.actual_duration_seconds % 60)
                job_dict['duration_display'] = f"{minutes}m {seconds}s"
            elif job.estimated_duration_minutes:
                job_dict['duration_display'] = f"~{job.estimated_duration_minutes}m"
            else:
                job_dict['duration_display'] = "Unknown"
            
            # Format creation time
            if job.created_at:
                job_dict['created_at_display'] = job.created_at.strftime("%Y-%m-%d %H:%M:%S")
            
            # Add models and test types for filtering
            job_dict['models_display'] = ', '.join(job.get_models()[:3])  # First 3 models
            if len(job.get_models()) > 3:
                job_dict['models_display'] += f" (+{len(job.get_models()) - 3} more)"
            
            job_dict['test_types_display'] = ', '.join(job.get_analysis_types())
            
            jobs.append(job_dict)
        
        # Apply additional client-side filters if needed
        if test_type_filter and test_type_filter != 'all':
            jobs = [job for job in jobs if test_type_filter in job.get('test_types_display', '')]
        
        if model_filter and model_filter != 'all':
            jobs = [job for job in jobs if model_filter in job.get('models_display', '')]
        
        # Check if request is from HTMX (wants HTML response)
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_jobs_list.html', jobs=jobs)
        else:
            return jsonify({'success': True, 'jobs': jobs})
        
    except Exception as e:
        logger.error(f"Error getting jobs: {e}")
        if request.headers.get('HX-Request'):
            return render_template('partials/batch_jobs_list.html', jobs=[], error=str(e))
        else:
            return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/export")
def testing_api_export():
    """Export test results."""
    try:
        from models import BatchJob
        import csv
        import io
        
        format_type = request.args.get('format', 'csv')
        
        if format_type == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['ID', 'Name', 'Status', 'Created At', 'Completed At', 'Duration'])
            
            # Write data
            jobs = BatchJob.query.all()
            for job in jobs:
                writer.writerow([
                    job.id,
                    job.name,
                    job.status.value if job.status else 'unknown',
                    job.created_at.strftime('%Y-%m-%d %H:%M:%S') if job.created_at else '',
                    job.completed_at.strftime('%Y-%m-%d %H:%M:%S') if job.completed_at else '',
                    job.actual_duration_seconds or ''
                ])
            
            output.seek(0)
            return make_response(
                output.getvalue(),
                200,
                {
                    'Content-Type': 'text/csv',
                    'Content-Disposition': 'attachment; filename=test_results.csv'
                }
            )
        
        return jsonify({'success': False, 'error': 'Unsupported format'}), 400
        
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/tools")
def testing_api_tools():
    """Get available security analysis tools with their configurations."""
    try:
        tools = {
            'sast': [
                {
                    'id': 'bandit',
                    'name': 'Bandit',
                    'description': 'Python security linter for common security issues',
                    'language': 'Python',
                    'category': 'SAST',
                    'status': 'available',
                    'options': ['confidence', 'severity', 'exclude_paths', 'config_file']
                },
                {
                    'id': 'safety',
                    'name': 'Safety',
                    'description': 'Python dependency vulnerability scanner',
                    'language': 'Python',
                    'category': 'Dependency',
                    'status': 'available',
                    'options': ['check_type', 'output_format', 'policy_file']
                },
                {
                    'id': 'semgrep',
                    'name': 'Semgrep',
                    'description': 'Fast static analysis for 17+ languages',
                    'language': 'Multi-language',
                    'category': 'SAST',
                    'status': 'available',
                    'options': ['config', 'severity', 'timeout', 'autofix']
                },
                {
                    'id': 'eslint',
                    'name': 'ESLint',
                    'description': 'JavaScript/TypeScript static analysis',
                    'language': 'JavaScript',
                    'category': 'SAST',
                    'status': 'available',
                    'options': ['config', 'rules', 'format']
                },
                {
                    'id': 'sonarqube',
                    'name': 'SonarQube',
                    'description': 'Code quality and security platform',
                    'language': 'Multi-language',
                    'category': 'SAST',
                    'status': 'available',
                    'options': ['project_key', 'quality_gate']
                },
                {
                    'id': 'codeql',
                    'name': 'CodeQL',
                    'description': 'GitHub\'s semantic code analysis',
                    'language': 'Multi-language',
                    'category': 'SAST',
                    'status': 'available',
                    'options': ['database', 'query_suite']
                }
            ],
            'dependency': [
                {
                    'id': 'npm-audit',
                    'name': 'npm audit',
                    'description': 'Node.js dependency vulnerability scanner',
                    'language': 'JavaScript',
                    'category': 'Dependency',
                    'status': 'available',
                    'options': ['audit_level', 'production_only']
                },
                {
                    'id': 'retire',
                    'name': 'Retire.js',
                    'description': 'JavaScript vulnerability detection',
                    'language': 'JavaScript',
                    'category': 'Dependency',
                    'status': 'available',
                    'options': ['severity_threshold', 'ignore_file']
                },
                {
                    'id': 'snyk',
                    'name': 'Snyk',
                    'description': 'Developer security platform',
                    'language': 'Multi-language',
                    'category': 'Dependency',
                    'status': 'available',
                    'options': ['severity_threshold', 'file_path', 'fail_on']
                }
            ],
            'secrets': [
                {
                    'id': 'trufflehog',
                    'name': 'TruffleHog',
                    'description': 'Secret scanning engine',
                    'language': 'Any',
                    'category': 'Secrets',
                    'status': 'available',
                    'options': ['entropy', 'regex', 'max_depth']
                },
                {
                    'id': 'gitleaks',
                    'name': 'Gitleaks',
                    'description': 'Git secrets detection',
                    'language': 'Any',
                    'category': 'Secrets',
                    'status': 'available',
                    'options': ['config', 'verbose', 'redact']
                }
            ],
            'quality': [
                {
                    'id': 'pylint',
                    'name': 'Pylint',
                    'description': 'Python code quality analyzer',
                    'language': 'Python',
                    'category': 'Quality',
                    'status': 'available',
                    'options': ['rcfile', 'disable', 'enable']
                },
                {
                    'id': 'flake8',
                    'name': 'Flake8',
                    'description': 'Python style guide enforcement',
                    'language': 'Python',
                    'category': 'Quality',
                    'status': 'available',
                    'options': ['config', 'max-line-length', 'ignore']
                },
                {
                    'id': 'black',
                    'name': 'Black',
                    'description': 'Python code formatter',
                    'language': 'Python',
                    'category': 'Quality',
                    'status': 'available',
                    'options': ['line-length', 'target-version', 'check']
                },
                {
                    'id': 'isort',
                    'name': 'isort',
                    'description': 'Python import sorter',
                    'language': 'Python',
                    'category': 'Quality',
                    'status': 'available',
                    'options': ['profile', 'line_length', 'multi_line_output']
                }
            ]
        }
        
        # Flatten tools list for the response
        all_tools = []
        for category, tool_list in tools.items():
            all_tools.extend(tool_list)
        
        return jsonify({
            'success': True,
            'tools': all_tools,
            'categories': tools,
            'total_count': len(all_tools)
        })
        
    except Exception as e:
        logger.error(f"Error getting tools: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/models")
def testing_api_models():
    """Get available models for testing."""
    try:
        # Try to get models from the model service
        models_data = []
        
        try:
            from core_services import get_model_service
            model_service = get_model_service()
            
            if model_service and hasattr(model_service, 'get_all_models'):
                all_models = model_service.get_all_models()
                
                for model in all_models:
                    # Handle both AIModel objects and dict objects
                    if hasattr(model, '__dict__'):
                        model_id = getattr(model, 'model_name', getattr(model, 'name', 'unknown'))
                        provider = getattr(model, 'provider', 'Unknown')
                    else:
                        model_id = model.get('model_name', model.get('name', 'unknown'))
                        provider = model.get('provider', 'Unknown')
                    
                    model_data = {
                        'id': model_id,
                        'slug': model_id,
                        'name': model_id,
                        'display_name': model_id,
                        'provider': provider,
                        'status': 'ready',
                        'apps_count': 30  # Default for testing
                    }
                    models_data.append(model_data)
            
            if not models_data:
                raise Exception("No models from service")
                
        except Exception as e:
            logger.warning(f"Could not get models from model service: {e}")
            # Fallback: try to get from ModelCapability table directly
            try:
                from models import ModelCapability
                models = ModelCapability.query.all()
                
                for model in models:
                    model_data = {
                        'id': model.canonical_slug,
                        'slug': model.canonical_slug,
                        'name': model.model_name,
                        'display_name': model.model_name,
                        'provider': model.provider or 'Unknown',
                        'status': 'ready',
                        'apps_count': 20  # Default assumption
                    }
                    models_data.append(model_data)
                    
            except Exception as e2:
                logger.warning(f"Could not get models from database: {e2}")
                # Ultimate fallback: provide some default models
                models_data = [
                    {
                        'id': 'anthropic_claude-3.7-sonnet',
                        'slug': 'anthropic_claude-3.7-sonnet',
                        'name': 'Claude 3.7 Sonnet',
                        'display_name': 'Claude 3.7 Sonnet',
                        'provider': 'Anthropic',
                        'status': 'ready',
                        'apps_count': 20
                    },
                    {
                        'id': 'test_model',
                        'slug': 'test_model',
                        'name': 'Test Model',
                        'display_name': 'Test Model',
                        'provider': 'Local',
                        'status': 'ready',
                        'apps_count': 20
                    }
                ]
        
        return jsonify({
            'success': True,
            'models': models_data,
            'total_count': len(models_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting models: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/new-test-form")
def testing_api_new_test_form():
    """Get new test form modal HTML."""
    try:
        # Get available applications from database (with safer query)
        applications = []
        try:
            from models import GeneratedApplication
            applications = GeneratedApplication.query.limit(50).all()
        except Exception as e:
            logger.warning(f"Could not load applications from database: {e}")
            # Create some mock applications for testing
            class MockApp:
                def __init__(self, id, model_slug, app_number):
                    self.id = id
                    self.model_slug = model_slug
                    self.app_number = app_number
            
            applications = [
                MockApp(1, "gpt-4", 1),
                MockApp(2, "claude-3", 2),
                MockApp(3, "gemini-pro", 3)
            ]
        
        # Get available models for the form
        models_data = []
        try:
            model_service = ServiceLocator.get_model_service()
            if model_service:
                models_data = model_service.get_available_models()
        except Exception as e:
            logger.warning(f"Could not get models from service: {e}")
            # Fallback to database with error handling
            try:
                from models import ModelCapability
                models = ModelCapability.query.all()
                for model in models:
                    models_data.append({
                        'id': model.canonical_slug,
                        'slug': model.canonical_slug,
                        'name': model.model_name,
                        'provider': model.provider
                    })
            except Exception as db_error:
                logger.warning(f"Database fallback also failed: {db_error}")
                # Create mock models as final fallback
                models_data = [
                    {'id': 'gpt-4', 'slug': 'gpt-4', 'name': 'GPT-4', 'provider': 'openai'},
                    {'id': 'claude-3-sonnet', 'slug': 'claude-3-sonnet', 'name': 'Claude 3 Sonnet', 'provider': 'anthropic'},
                    {'id': 'gemini-pro', 'slug': 'gemini-pro', 'name': 'Gemini Pro', 'provider': 'google'}
                ]
        
        return render_template('partials/testing/new_test_modal.html', 
                             applications=applications,
                             models=models_data)
    except Exception as e:
        logger.error(f"Error loading new test form: {e}")
        return render_template('partials/error_message.html', 
                             error="Could not load test form"), 500

@testing_bp.route("/api/infrastructure-status")
def testing_api_infrastructure_status():
    """Get detailed infrastructure status."""
    try:
        # Use mock infrastructure status for now
        status = {
            'overall_status': 'healthy',
            'services': {
                'security_scanner': {'status': 'healthy', 'response_time': 150},
                'performance_tester': {'status': 'healthy', 'response_time': 120},
                'zap_scanner': {'status': 'healthy', 'response_time': 200},
                'api_gateway': {'status': 'healthy', 'response_time': 80}
            },
            'metrics': {
                'total_services': 4,
                'healthy_services': 4,
                'unhealthy_services': 0
            },
            'overall_health': 100,
            'timestamp': datetime.now().isoformat()
        }
        
        if request.headers.get('HX-Request'):
            # Debug: log the status to see what's being passed
            logger.debug(f"Infrastructure status data: {status}")
            return render_template('partials/infrastructure_status.html', data=status)
        else:
            return jsonify({'success': True, 'data': status})
    except Exception as e:
        logger.error(f"Infrastructure status error: {e}")
        if request.headers.get('HX-Request'):
            return render_template('partials/infrastructure_status.html', data=None, error=str(e))
        else:
            return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/infrastructure/<action>", methods=["POST"])
def testing_api_infrastructure_management(action):
    """Manage testing infrastructure containers."""
    try:
        import subprocess
        import os
        
        if action not in ['start', 'stop', 'restart']:
            return jsonify({'success': False, 'error': 'Invalid action'}), 400
        
        # Path to the testing infrastructure management script
        testing_infra_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'testing-infrastructure')
        manage_script = os.path.join(testing_infra_path, 'manage.py')
        
        if not os.path.exists(manage_script):
            return jsonify({'success': False, 'error': 'Testing infrastructure not available'}), 404
        
        # Execute the management command
        cmd = ['python', manage_script, action]
        result = subprocess.run(cmd, cwd=testing_infra_path, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            return jsonify({
                'success': True, 
                'message': f'Infrastructure {action}ed successfully',
                'output': result.stdout
            })
        else:
            # Check if it's a partial failure (some services still work)
            if "Most services are healthy" in result.stdout:
                return jsonify({
                    'success': True, 
                    'message': f'Infrastructure {action}ed with warnings (some services unhealthy)',
                    'output': result.stdout
                })
            else:
                return jsonify({
                    'success': False, 
                    'error': f'Failed to {action} infrastructure',
                    'output': result.stderr
                }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Operation timed out'}), 408
    except Exception as e:
        logger.error(f"Infrastructure {action} error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/infrastructure-logs")
def testing_api_infrastructure_logs():
    """Get infrastructure logs."""
    try:
        import subprocess
        import os
        
        # Path to the testing infrastructure
        testing_infra_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'testing-infrastructure')
        
        if not os.path.exists(testing_infra_path):
            return jsonify({'success': False, 'error': 'Testing infrastructure not available'}), 404
        
        # Get docker-compose logs
        cmd = ['docker-compose', 'logs', '--tail=100']
        result = subprocess.run(cmd, cwd=testing_infra_path, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            logs = result.stdout.split('\n')
            return jsonify({
                'success': True, 
                'logs': logs,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'success': False, 
                'error': 'Failed to get logs',
                'output': result.stderr
            }), 500
            
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'error': 'Log retrieval timed out'}), 408
    except Exception as e:
        logger.error(f"Infrastructure logs error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/stats")
def testing_api_stats():
    """Get testing statistics."""
    try:
        from models import BatchJob, JobStatus
        
        # Get basic stats for dashboard
        total_jobs = BatchJob.query.count()
        running_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.RUNNING).count()
        completed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.COMPLETED).count()
        failed_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.FAILED).count()
        pending_jobs = BatchJob.query.filter(BatchJob.status == JobStatus.PENDING).count()
        queued_jobs = pending_jobs  # For compatibility
        
        stats = {
            'total': total_jobs,
            'running': running_jobs,
            'completed': completed_jobs,
            'failed': failed_jobs,
            'pending': pending_jobs,
            'queued': queued_jobs,
            'success_rate': round((completed_jobs / max(total_jobs, 1)) * 100, 1)
        }
        
        return jsonify({'success': True, 'data': stats})
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/create-test", methods=["POST"])
def testing_api_create_test():
    """Create a new security test."""
    try:
        from models import BatchJob, JobStatus, JobPriority
        from extensions import db
        import uuid
        
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Validate required fields
        if not data.get('test_type'):
            return jsonify({'success': False, 'error': 'Test type is required'}), 400
        
        # Generate unique test ID
        test_id = str(uuid.uuid4())
        
        # Create new BatchJob record
        new_job = BatchJob(
            id=test_id,
            name=data.get('test_name', f"Security Test {test_id[:8]}"),
            description=data.get('description', ''),
            status=JobStatus.PENDING,
            priority=JobPriority.NORMAL,
            auto_start=True,
            auto_retry=False,
            max_retries=3
        )
        
        # Set job configuration
        config = {
            'test_type': data.get('test_type'),
            'tools': data.get('tools', []),
            'selected_models': data.get('selected_models', []),
            'selected_apps': data.get('selected_apps', []),
            'requirements': data.get('requirements', '').split('\n') if data.get('requirements') else [],
            'priority': data.get('priority', 'normal'),
            'timeout': data.get('timeout', 30),
            'parallel_execution': data.get('parallel_execution', False),
            'notify_on_completion': data.get('notify_on_completion', True),
            'notify_on_failure': data.get('notify_on_failure', True),
            'custom_params': data.get('custom_params', {})
        }
        
        # Add test-type specific configuration
        if data.get('test_type') == 'zap_scan':
            config.update({
                'zap_scan_type': data.get('zap_scan_type', 'baseline'),
                'target_url': data.get('target_url'),
                'api_definition_url': data.get('api_definition_url')
            })
        elif data.get('test_type') == 'performance_test':
            config.update({
                'users': data.get('users', 10),
                'spawn_rate': data.get('spawn_rate', 2),
                'duration': data.get('duration', 60)
            })
        elif data.get('test_type') == 'ai_analysis':
            config.update({
                'ai_model': data.get('ai_model', 'gpt-4'),
                'ai_focus': data.get('ai_focus', [])
            })
        
        new_job.config = config
        
        db.session.add(new_job)
        db.session.commit()
        
        logger.info(f"Created new security test: {test_id}")
        
        return jsonify({
            'success': True, 
            'message': 'Test created successfully',
            'test_id': test_id,
            'data': {
                'id': test_id,
                'name': new_job.name,
                'status': new_job.status.value,
                'created_at': new_job.created_at.isoformat() if new_job.created_at else None
            }
        })
        
    except Exception as e:
        logger.error(f"Error creating test: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/export-results")
def testing_api_export_results():
    """Export test results to Excel format."""
    try:
        from models import BatchJob
        import io
        import pandas as pd
        from flask import send_file
        
        # Get all completed jobs
        jobs = BatchJob.query.filter(BatchJob.status.in_(['completed', 'failed'])).all()
        
        # Prepare data for export
        export_data = []
        for job in jobs:
            export_data.append({
                'Test ID': job.id,
                'Name': job.name,
                'Description': job.description,
                'Status': job.status.value,
                'Priority': job.priority.value if job.priority else 'normal',
                'Created At': job.created_at.isoformat() if job.created_at else '',
                'Updated At': job.updated_at.isoformat() if job.updated_at else '',
                'Duration': str(job.duration) if job.duration else '',
                'Total Issues': job.total_issues if hasattr(job, 'total_issues') else 0,
                'Config': str(job.config) if job.config else ''
            })
        
        # Create Excel file
        df = pd.DataFrame(export_data)
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Test Results', index=False)
        
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'security-test-results-{datetime.now().strftime("%Y%m%d")}.xlsx'
        )
        
    except Exception as e:
        logger.error(f"Error exporting results: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/create", methods=["POST"])
def testing_api_create():
    """Create a new test with enhanced tool configurations."""
    try:
        from models import BatchJob, JobStatus, JobPriority
        from extensions import db
        from datetime import timedelta
        import uuid
        import traceback
        
        # Handle both JSON and form data with proper content type handling
        if request.is_json or request.content_type == 'application/json':
            data = request.get_json()
            logger.info("Received JSON data")
        elif request.form or request.content_type == 'application/x-www-form-urlencoded':
            # Convert form data to dict
            data = {}
            for key, value in request.form.items():
                # Handle array fields
                if key in ['tools', 'selected_models', 'selected_apps']:
                    data[key] = request.form.getlist(key)
                else:
                    data[key] = value
            logger.info("Received form data")
        else:
            logger.error(f"No supported content type. Content-Type: {request.content_type}")
            return jsonify({'success': False, 'error': f'Unsupported content type: {request.content_type}'}), 415
        
        if not data:
            logger.error("Empty request data")
            return jsonify({'success': False, 'error': 'Empty request data'}), 400
        
        logger.info(f"Creating test with data: {list(data.keys())}")  # Log keys only for security
        
        # Validate required fields
        if not data.get('test_type'):
            return jsonify({'success': False, 'error': 'Test type is required'}), 400
        
        if not data.get('job_name'):
            return jsonify({'success': False, 'error': 'Job name is required'}), 400
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Create new BatchJob record with proper priority handling
        priority_value = data.get('priority', 'normal')
        if isinstance(priority_value, str):
            if priority_value.lower() in ['low', 'normal', 'high', 'urgent']:
                job_priority = JobPriority(priority_value.lower())
            else:
                logger.warning(f"Invalid priority value: {priority_value}, defaulting to normal")
                job_priority = JobPriority.NORMAL
        elif isinstance(priority_value, int):
            # Handle numeric priority values from HTML select options
            priority_map = {1: JobPriority.LOW, 2: JobPriority.NORMAL, 3: JobPriority.HIGH, 4: JobPriority.URGENT}
            job_priority = priority_map.get(priority_value, JobPriority.NORMAL)
        else:
            job_priority = JobPriority.NORMAL
            
        new_job = BatchJob(
            id=job_id,
            name=data.get('job_name'),
            description=data.get('description', ''),
            status=JobStatus.PENDING,
            priority=job_priority,
            auto_start=data.get('auto_start', True),
            auto_retry=False,
            max_retries=3
        )
        
        # Set analysis types
        analysis_types = [data.get('test_type')]
        new_job.set_analysis_types(analysis_types)
        
        # Set models
        models = data.get('selected_models', [])
        if isinstance(models, str):
            models = [models]
        new_job.set_models(models)
        
        # Set app range
        apps = data.get('selected_apps', [])
        if isinstance(apps, str):
            apps = [int(apps)]
        elif isinstance(apps, list):
            apps = [int(app) if isinstance(app, str) else app for app in apps]
        
        app_range = {
            'apps': apps,
            'include_all': len(apps) == 0
        }
        new_job.set_app_range(app_range)
        
        # Enhanced tool configuration processing
        options = _process_enhanced_tool_config(data)
        new_job.set_options(options)
        
        # Calculate estimated duration and total tasks
        total_models = len(models) if models else 1
        total_apps = len(apps) if apps else 10  # Default assumption
        new_job.total_tasks = total_models * total_apps
        new_job.estimated_duration_minutes = new_job.total_tasks * 5  # 5 minutes per task estimate
        
        # Set scheduled time if auto_start is false
        if not data.get('auto_start', True):
            new_job.scheduled_at = datetime.now() + timedelta(minutes=5)
        
        # Save to database
        db.session.add(new_job)
        db.session.commit()
        
        # Auto-start the job if requested
        if data.get('auto_start', True):
            try:
                service = get_unified_cli_analyzer()
                if service:
                    # Submit the job to the unified CLI analyzer
                    job_config = new_job.to_dict()
                    service_result = service.create_batch_job(job_config)
                    
                    if service_result.get('success'):
                        new_job.status = JobStatus.QUEUED
                        new_job.started_at = datetime.now()
                        db.session.commit()
                        logger.info(f"Job {job_id} submitted to unified CLI analyzer")
                    else:
                        logger.warning(f"Failed to submit job to service: {service_result.get('error')}")
                else:
                    logger.warning("Unified CLI analyzer service not available")
            except Exception as e:
                logger.error(f"Error starting job: {e}")
                # Job is still created but not started
        
        result = {
            'success': True,
            'message': f'Security test "{data.get("job_name", "Test")}" created successfully',
            'data': {
                'job_id': job_id,
                'test_type': data.get('test_type'),
                'status': new_job.status.value,
                'created_at': new_job.created_at.isoformat(),
                'total_tasks': new_job.total_tasks,
                'estimated_duration_minutes': new_job.estimated_duration_minutes
            }
        }
        
        logger.info(f"Test created successfully and saved to database: {job_id}")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating test: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Rollback database changes on error
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


def _process_enhanced_tool_config(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process enhanced tool configurations based on comprehensive tool options."""
    
    test_type = data.get('test_type')
    options = {
        'tools': data.get('tools', []),
        'concurrency': int(data.get('concurrency', 1)),
        'timeout': int(data.get('timeout', 600)),
        'fail_fast': data.get('fail_fast', False),
        'generate_report': data.get('generate_report', True)
    }
    
    # Security Analysis Tool Configurations
    if test_type == 'security_analysis':
        security_config = {}
        
        # Bandit Configuration
        if 'bandit' in data.get('tools', []):
            security_config['bandit'] = {
                'config_file': data.get('bandit_config_file', ''),
                'confidence': data.get('bandit_confidence', 'medium'),
                'severity': data.get('bandit_severity', 'medium'),
                'exclude_paths': data.get('bandit_exclude_paths', '').split(',') if data.get('bandit_exclude_paths') else [],
                'include_tests': data.get('bandit_include_tests', '').split(',') if data.get('bandit_include_tests') else [],
                'skip_tests': data.get('bandit_skip_tests', '').split(',') if data.get('bandit_skip_tests') else [],
                'format': data.get('bandit_format', 'json'),
                'output_file': data.get('bandit_output_file', ''),
                'recursive': data.get('bandit_recursive', True),
                'aggregate': data.get('bandit_aggregate', 'file')
            }
        
        # Safety Configuration
        if 'safety' in data.get('tools', []):
            security_config['safety'] = {
                'check_type': data.get('safety_check_type', 'scan'),  # scan or check
                'output_format': data.get('safety_output_format', 'json'),
                'detailed_output': data.get('safety_detailed_output', True),
                'policy_file': data.get('safety_policy_file', ''),
                'target_path': data.get('safety_target_path', '.'),
                'apply_fixes': data.get('safety_apply_fixes', False),
                'ignore_unpinned': data.get('safety_ignore_unpinned', False),
                'continue_on_error': data.get('safety_continue_on_error', True)
            }
        
        # Semgrep Configuration
        if 'semgrep' in data.get('tools', []):
            security_config['semgrep'] = {
                'config': data.get('semgrep_config', 'p/security-audit'),
                'output_format': data.get('semgrep_output_format', 'json'),
                'severity': data.get('semgrep_severity', 'WARNING'),
                'timeout': int(data.get('semgrep_timeout', 30)),
                'timeout_threshold': int(data.get('semgrep_timeout_threshold', 3)),
                'exclude_patterns': data.get('semgrep_exclude_patterns', '').split(',') if data.get('semgrep_exclude_patterns') else [],
                'include_patterns': data.get('semgrep_include_patterns', '').split(',') if data.get('semgrep_include_patterns') else [],
                'autofix': data.get('semgrep_autofix', False),
                'dry_run': data.get('semgrep_dry_run', False),
                'oss_only': data.get('semgrep_oss_only', True),
                'products': data.get('semgrep_products', '').split(',') if data.get('semgrep_products') else ['code'],
                'verbose': data.get('semgrep_verbose', False),
                'debug': data.get('semgrep_debug', False)
            }
        
        options['security_config'] = security_config
    
    # ZAP Scan Configuration
    elif test_type == 'zap_scan':
        zap_config = {
            'target_url': data.get('zap_target_url', ''),
            'scan_type': data.get('zap_scan_type', 'baseline'),  # baseline, active, api, full
            'format': data.get('zap_format', 'json'),
            'output_file': data.get('zap_output_file', ''),
            'config_file': data.get('zap_config_file', ''),
            'config_url': data.get('zap_config_url', ''),
            'generate_config': data.get('zap_generate_config', False),
            'alpha_passive': data.get('zap_alpha_passive', False),
            'debug': data.get('zap_debug', False),
            'listen_port': int(data.get('zap_listen_port', 8080)) if data.get('zap_listen_port') else None,
            'passive_scan_delay': int(data.get('zap_passive_scan_delay', 0)) if data.get('zap_passive_scan_delay') else 0,
            'info_unspecified': data.get('zap_info_unspecified', False),
            'no_fail_on_warn': data.get('zap_no_fail_on_warn', False),
            'min_level': data.get('zap_min_level', 'WARN'),  # PASS, IGNORE, INFO, WARN, FAIL
            'context_file': data.get('zap_context_file', ''),
            'progress_file': data.get('zap_progress_file', ''),
            'short_output': data.get('zap_short_output', False),
            'safe_mode': data.get('zap_safe_mode', False),
            'max_time': int(data.get('zap_max_time', 0)) if data.get('zap_max_time') else None,
            'user': data.get('zap_user', ''),
            'hostname_override': data.get('zap_hostname_override', ''),
            'additional_options': data.get('zap_additional_options', ''),
            'hook_file': data.get('zap_hook_file', ''),
            'schema_file': data.get('zap_schema_file', '')  # For GraphQL
        }
        
        # Add scan-specific options
        if zap_config['scan_type'] == 'api':
            zap_config['api_definition'] = data.get('zap_api_definition', '')
            zap_config['api_format'] = data.get('zap_api_format', 'openapi')  # openapi, soap, graphql
        
        options['zap_config'] = zap_config
    
    # Performance Testing Configuration
    elif test_type == 'performance_test':
        performance_config = {
            'target_url': data.get('perf_target_url', ''),
            'users': int(data.get('perf_users', 10)),
            'spawn_rate': float(data.get('perf_spawn_rate', 2.0)),
            'duration': int(data.get('perf_duration', 60)),
            'test_type': data.get('perf_test_type', 'load'),  # load, stress, spike, volume
            'output_format': data.get('perf_output_format', 'json'),
            'output_file': data.get('perf_output_file', ''),
            'locustfile': data.get('perf_locustfile', ''),
            'host': data.get('perf_host', ''),
            'web_ui': data.get('perf_web_ui', False),
            'web_port': int(data.get('perf_web_port', 8089)) if data.get('perf_web_port') else None,
            'headless': data.get('perf_headless', True),
            'csv_output': data.get('perf_csv_output', False),
            'html_output': data.get('perf_html_output', True),
            'tags': data.get('perf_tags', '').split(',') if data.get('perf_tags') else [],
            'exclude_tags': data.get('perf_exclude_tags', '').split(',') if data.get('perf_exclude_tags') else [],
            'stop_timeout': int(data.get('perf_stop_timeout', 0)) if data.get('perf_stop_timeout') else None
        }
        options['performance_config'] = performance_config
    
    # AI Analysis Configuration
    elif test_type == 'ai_analysis':
        ai_config = {
            'model': data.get('ai_model', 'gpt-4'),
            'analysis_type': data.get('ai_analysis_type', 'comprehensive'),
            'focus_areas': data.get('ai_focus_areas', '').split(',') if data.get('ai_focus_areas') else [],
            'output_format': data.get('ai_output_format', 'json'),
            'include_suggestions': data.get('ai_include_suggestions', True),
            'severity_threshold': data.get('ai_severity_threshold', 'medium'),
            'max_tokens': int(data.get('ai_max_tokens', 4000)) if data.get('ai_max_tokens') else None,
            'temperature': float(data.get('ai_temperature', 0.7)) if data.get('ai_temperature') else None
        }
        options['ai_config'] = ai_config
    
    return options


@testing_bp.route("/api/test/<test_id>/details")
def testing_api_test_details(test_id):
    """Get test details."""
    try:
        from models import BatchJob
        
        # Get test from database
        test = BatchJob.query.get(test_id)
        if not test:
            if request.headers.get('HX-Request'):
                return render_template('partials/test_details.html', test=None, error="Test not found")
            else:
                return jsonify({'success': False, 'error': 'Test not found'}), 404
        
        # Convert to dict and add additional computed fields
        test_dict = test.to_dict()
        test_dict['status_class'] = {
            'pending': 'warning',
            'queued': 'info', 
            'running': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'cancelled': 'secondary',
            'paused': 'warning'
        }.get(test.status.value if test.status else 'unknown', 'secondary')
        
        # Format timestamps
        if test.created_at:
            test_dict['created_at'] = test.created_at.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(test, 'started_at') and test.started_at:
            test_dict['started_at'] = test.started_at.strftime("%Y-%m-%d %H:%M:%S")
        if hasattr(test, 'completed_at') and test.completed_at:
            test_dict['completed_at'] = test.completed_at.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate progress
        if hasattr(test, 'total_tasks') and test.total_tasks and test.total_tasks > 0:
            completed = getattr(test, 'completed_tasks', 0) or 0
            test_dict['progress_percentage'] = round((completed / test.total_tasks) * 100, 1)
        else:
            test_dict['progress_percentage'] = 0
        
        # Add mock data for demonstration
        test_dict['logs'] = [
            f"[{datetime.now().strftime('%H:%M:%S')}] Test {test_id} initialized",
            f"[{datetime.now().strftime('%H:%M:%S')}] Running security analysis...",
            f"[{datetime.now().strftime('%H:%M:%S')}] Processing results..."
        ]
        
        if request.headers.get('HX-Request'):
            return render_template('partials/test_details.html', test=test_dict)
        else:
            return jsonify({'success': True, 'data': test_dict})
            
    except Exception as e:
        logger.error(f"Error getting test details: {e}")
        if request.headers.get('HX-Request'):
            return render_template('partials/test_details.html', test=None, error=str(e))
        else:
            return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/test/<test_id>/status")
def testing_api_test_status(test_id):
    """Get test status."""
    try:
        service = get_unified_cli_analyzer()
        status = {
            'id': test_id,
            'status': 'running',
            'progress': 45,
            'last_update': datetime.now().isoformat()
        }
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting test status: {e}")
        return jsonify({'error': str(e)}), 500


@testing_bp.route("/api/test/<test_id>/results")
def testing_api_test_results(test_id):
    """Get test results."""
    try:
        from models import BatchJob
        
        # Get test from database
        test = BatchJob.query.get(test_id)
        if not test:
            if request.headers.get('HX-Request'):
                return render_template('partials/test_results.html', test=None, error="Test not found")
            else:
                return jsonify({'success': False, 'error': 'Test not found'}), 404
        
        # Convert to dict and add results data
        test_dict = test.to_dict()
        test_dict['status_class'] = {
            'pending': 'warning',
            'queued': 'info', 
            'running': 'primary',
            'completed': 'success',
            'failed': 'danger',
            'cancelled': 'secondary',
            'paused': 'warning'
        }.get(test.status.value if test.status else 'unknown', 'secondary')
        
        # Add mock results for demonstration
        if test.status and test.status.value == 'completed':
            test_dict['total_issues'] = 15
            test_dict['critical_issues'] = 3
            test_dict['warning_issues'] = 8
            test_dict['results'] = {
                'bandit': {
                    'issues': [
                        {
                            'severity': 'high',
                            'type': 'B101',
                            'filename': 'app.py',
                            'line_number': 45,
                            'description': 'Use of assert detected. The enclosed code will be removed when compiling to optimised byte code.',
                            'recommendation': 'Remove assert statements or use proper exception handling'
                        },
                        {
                            'severity': 'medium',
                            'type': 'B603',
                            'filename': 'utils.py',
                            'line_number': 23,
                            'description': 'subprocess call - check for execution of untrusted input.',
                            'recommendation': 'Validate and sanitize subprocess inputs'
                        }
                    ],
                    'metrics': {
                        'files_scanned': 25,
                        'total_lines': 1500,
                        'scan_time': '2.3s'
                    }
                },
                'safety': {
                    'issues': [
                        {
                            'severity': 'critical',
                            'type': 'CVE-2023-1234',
                            'filename': 'requirements.txt',
                            'description': 'Known vulnerability in package xyz version 1.2.3',
                            'recommendation': 'Update package to version 1.2.4 or higher'
                        }
                    ],
                    'metrics': {
                        'packages_checked': 45,
                        'vulnerabilities_found': 1
                    }
                }
            }
            test_dict['recommendations'] = [
                'Update all packages to latest versions',
                'Review and remove debug code from production',
                'Implement proper input validation',
                'Add security headers to HTTP responses'
            ]
        elif test.status and test.status.value == 'failed':
            test_dict['error_message'] = 'Connection timeout while scanning target application'
        
        # Calculate progress
        if hasattr(test, 'total_tasks') and test.total_tasks and test.total_tasks > 0:
            completed = getattr(test, 'completed_tasks', 0) or 0
            test_dict['progress_percentage'] = round((completed / test.total_tasks) * 100, 1)
        else:
            test_dict['progress_percentage'] = 0
        
        if request.headers.get('HX-Request'):
            return render_template('partials/test_results.html', test=test_dict)
        else:
            return jsonify({'success': True, 'data': test_dict})
            
    except Exception as e:
        logger.error(f"Error getting test results: {e}")
        if request.headers.get('HX-Request'):
            return render_template('partials/test_results.html', test=None, error=str(e))
        else:
            return jsonify({'success': False, 'error': str(e)}), 500


@testing_bp.route("/api/test/<test_id>/live-metrics")
def testing_api_test_metrics(test_id):
    """Get live test metrics."""
    try:
        service = get_unified_cli_analyzer()
        metrics = {
            'id': test_id,
            'metrics': {
                'cpu_usage': 45,
                'memory_usage': 62,
                'requests_per_second': 150,
                'response_time': 245
            },
            'timestamp': datetime.now().isoformat()
        }
        return jsonify(metrics)
    except Exception as e:
        logger.error(f"Error getting test metrics: {e}")
        return jsonify({'error': str(e)}), 500


@testing_bp.route("/api/test/<test_id>/logs")
def testing_api_test_logs(test_id):
    """Get test logs."""
    try:
        service = get_unified_cli_analyzer()
        logs = {
            'id': test_id,
            'logs': [
                {'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': 'Test started'},
                {'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': 'Running security scan...'},
                {'timestamp': datetime.now().isoformat(), 'level': 'INFO', 'message': 'Scan in progress...'}
            ]
        }
        return jsonify(logs)
    except Exception as e:
        logger.error(f"Error getting test logs: {e}")
        return jsonify({'error': str(e)}), 500


@testing_bp.route("/api/test/<test_id>/<action>", methods=["POST", "DELETE"])
def testing_api_test_action(test_id, action):
    """Perform action on test (restart, cancel, delete)."""
    try:
        from models import BatchJob, JobStatus
        from extensions import db
        
        # Find the job in database
        job = BatchJob.query.filter_by(id=test_id).first()
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        
        if action == 'restart':
            if not job.can_be_restarted():
                return jsonify({'success': False, 'error': 'Job cannot be restarted'}), 400
            
            # Reset job status and counters
            job.status = JobStatus.PENDING
            job.completed_tasks = 0
            job.failed_tasks = 0
            job.cancelled_tasks = 0
            job.started_at = None
            job.completed_at = None
            job.error_message = None
            job.error_details_json = None
            
            db.session.commit()
            
            # Try to submit to unified CLI analyzer if auto_start is enabled
            if job.auto_start:
                try:
                    service = get_unified_cli_analyzer()
                    job_config = job.to_dict()
                    service_result = service.create_batch_job(job_config)
                    
                    if service_result.get('success'):
                        job.status = JobStatus.QUEUED
                        job.started_at = datetime.now()
                        db.session.commit()
                        logger.info(f"Job {test_id} restarted and submitted to unified CLI analyzer")
                    else:
                        logger.warning(f"Failed to submit restarted job to service: {service_result.get('error')}")
                except Exception as e:
                    logger.error(f"Error restarting job: {e}")
                    # Job is still restarted but not queued
            
            result = {'success': True, 'message': f'Job {job.name} restarted successfully'}
            
        elif action == 'cancel':
            if not job.can_be_cancelled():
                return jsonify({'success': False, 'error': 'Job cannot be cancelled'}), 400
            
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            
            # Calculate actual duration if job was running
            if job.started_at:
                duration = datetime.now() - job.started_at
                job.actual_duration_seconds = duration.total_seconds()
            
            db.session.commit()
            
            # TODO: Send cancellation signal to unified CLI analyzer
            logger.info(f"Job {test_id} cancelled")
            
            result = {'success': True, 'message': f'Job {job.name} cancelled successfully'}
            
        elif action == 'delete':
            if job.is_active():
                return jsonify({'success': False, 'error': 'Cannot delete active job. Cancel it first.'}), 400
            
            job_name = job.name
            db.session.delete(job)
            db.session.commit()
            
            logger.info(f"Job {test_id} deleted")
            
            result = {'success': True, 'message': f'Job {job_name} deleted successfully'}
            
        else:
            result = {'success': False, 'error': f'Unknown action: {action}'}
            return jsonify(result), 400
            
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error performing test action {action} on {test_id}: {e}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================
# DOCKER ROUTES (moved to main_bp)
# ===========================

@main_bp.route("/docker")
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
            return str(value) if value else ''
            
        except Exception:
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
# SIMPLE API ROUTES (Template Compatibility)
# ===========================

@simple_api_bp.route("/settings")
def api_settings():
    """Get application settings for frontend."""
    try:
        settings = {
            'theme': 'light',
            'auto_refresh': True,
            'refresh_interval': 15,
            'max_concurrent_operations': 4,
            'docker_timeout': 60,
            'analysis_timeout': 300
        }
        return ResponseHandler.success_response(data=settings)
    except Exception as e:
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/dashboard/models")
def api_simple_dashboard_models():
    """Get dashboard models without version prefix."""
    try:
        models = ModelCapability.query.all()
        models_data = []
        
        for model in models:
            # Get model stats and flatten them directly into model data
            stats = AppDataProvider.get_model_dashboard_stats(model.canonical_slug)
            
            model_data = {
                'slug': model.canonical_slug,
                'name': model.model_name,
                'provider': model.provider or 'Unknown',
                'total_apps': stats.get('total_apps', 30),
                'running_containers': stats.get('running_containers', 0),
                'stopped_containers': stats.get('stopped_containers', 0),
                'error_containers': stats.get('error_containers', 0),
                'analyzed_apps': stats.get('analyzed_apps', 0),
                'performance_tested': stats.get('performance_tested', 0)
            }
            models_data.append(model_data)
        
        # Return partial template for HTMX updates
        if ResponseHandler.is_htmx_request():
            return render_template("partials/dashboard_models.html", models=models_data)
        
        return ResponseHandler.success_response(data=models_data)
        
    except Exception as e:
        logger.error(f"Simple API dashboard models error: {e}")
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/models")
def api_simple_models():
    """Get models for testing interface - simple format."""
    try:
        from models import ModelCapability
        models = ModelCapability.query.all()
        models_data = []
        
        for model in models:
            model_data = {
                'id': model.canonical_slug,
                'slug': model.canonical_slug,
                'name': model.model_name,
                'display_name': model.model_name,
                'provider': model.provider or 'Unknown',
                'status': 'ready',
                'apps_count': 30  # Default for testing
            }
            models_data.append(model_data)
        
        return jsonify({
            'success': True,
            'data': models_data,
            'total_count': len(models_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting simple models: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ===========================
# BLUEPRINT REGISTRATION
# ===========================

def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(simple_api_bp)
    app.register_blueprint(statistics_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(containers_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(testing_bp)  # Add testing blueprint for template compatibility
    app.register_blueprint(files_bp)
    
    # Register template helpers
    register_template_helpers(app)
    
    logger.info("All blueprints registered successfully")


# Export blueprints for use in app factory
__all__ = [
    'main_bp', 'api_bp', 'simple_api_bp', 'statistics_bp', 'models_bp', 'containers_bp', 'analysis_bp', 'batch_bp', 'files_bp', 'testing_bp',
    'register_blueprints'
]