"""
Shared Route Utilities
=====================

This module contains shared utilities, classes, and helper functions
that are used across multiple route modules. Extracted from the original
web_routes.py to improve code organization and reduce duplication.
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

from flask import request, render_template, jsonify, g

# Core imports with proper error handling
try:
    from ..extensions import db
    from ..models import (
        ModelCapability, GeneratedApplication, PortConfiguration,
        SecurityAnalysis, JobStatus
    )
    from ..core_services import get_container_names
    from ..unified_cli_analyzer import UnifiedCLIAnalyzer, ToolCategory
except ImportError as e:
    # Fallback for direct script execution
    try:
        from extensions import db
        from models import (
            ModelCapability, GeneratedApplication, PortConfiguration,
            SecurityAnalysis, JobStatus
        )
        from core_services import get_container_names
        from unified_cli_analyzer import UnifiedCLIAnalyzer, ToolCategory
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
    def render_response(template_name: str, **context) -> Union[str, Any]:
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
    def error_response(error_msg: str, code: int = 500) -> Union[str, Any]:
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
    def success_response(data: Any = None, message: Optional[str] = None) -> Any:
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
                    message: Optional[str] = None, code: int = 200) -> Tuple[Any, int]:
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
            from ..service_manager import ServiceLocator as UnifiedServiceLocator
            return UnifiedServiceLocator.get_service(service_name)
        except ImportError:
            # Fallback to app context
            from flask import current_app
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
                from ..core_services import DockerUtils
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
            
            return {'success': False, 'error': error_msg}


def get_unified_cli_analyzer():
    """Get unified CLI analyzer service."""
    try:
        from ..unified_cli_analyzer import UnifiedCLIAnalyzer
        return UnifiedCLIAnalyzer()
    except Exception as e:
        logger.warning(f"Could not get unified CLI analyzer: {e}")
        return None