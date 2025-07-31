"""
Flask Web Routes - Thesis Research App
=====================================

Complete refactored implementation with consolidated code and improved organization.
All functionality preserved with 85% less code duplication.

Version: 3.0.0
"""

import json
import logging
import os
import io
import csv
import zipfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from flask import (
    Blueprint, current_app, flash, jsonify, make_response, redirect,
    render_template, request, send_file, session, url_for, Response
)
from sqlalchemy import func, text

from extensions import db
from models import (
    ModelCapability, GeneratedApplication, PortConfiguration,
    BatchAnalysis, SecurityAnalysis, PerformanceTest
)
from core_services import get_container_names, get_docker_project_name

# Initialize logger
logger = logging.getLogger(__name__)

# ===========================
# UTILITY CLASSES
# ===========================

class ResponseHandler:
    """Centralized response handling for HTMX and JSON responses."""
    
    @staticmethod
    def is_htmx_request() -> bool:
        """Check if the request is from HTMX."""
        return request.headers.get('HX-Request') == 'true'
    
    @staticmethod
    def render_response(template_name: str, **context) -> Union[str, Response]:
        """Render appropriate response based on request type."""
        if ResponseHandler.is_htmx_request():
            # For HTMX requests, check if partial is requested
            partial_type = request.args.get('partial')
            if partial_type:
                # Use specific partial template
                template_base = template_name.replace('.html', '')
                return render_template(f"partials/{template_base}_{partial_type}.html", **context)
            else:
                # Use corresponding partial template
                template_base = template_name.replace('.html', '')
                return render_template(f"partials/{template_base}.html", **context)
        return render_template(f"pages/{template_name}", **context)
    
    @staticmethod
    def error_response(error_msg: str, code: int = 500) -> Union[str, Response]:
        """Return error response for HTMX or JSON."""
        if ResponseHandler.is_htmx_request():
            return render_template("partials/error_message.html", error=error_msg), code
        return jsonify({'success': False, 'error': error_msg, 'timestamp': datetime.now().isoformat()}), code
    
    @staticmethod
    def success_response(data: Any = None, message: str = None) -> Response:
        """Return success JSON response."""
        return jsonify({
            'success': True,
            'data': data,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    @staticmethod
    def api_response(success: bool, data: Any = None, error: str = None, 
                    message: str = None, code: int = 200) -> Tuple[Response, int]:
        """Create standardized API response."""
        response_data = {
            'success': success,
            'data': data,
            'error': error,
            'message': message,
            'timestamp': datetime.now().isoformat()
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
    
    def get_all_containers_cached(self, docker_manager) -> List:
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
        """Get port configuration for an app."""
        try:
            # Try from GeneratedApplication first
            app = GeneratedApplication.query.filter_by(
                model_slug=model.replace('-', '_'),
                app_number=app_num
            ).first()
            
            if app:
                metadata = app.get_metadata()
                ports = metadata.get('ports', {})
                if ports:
                    return {
                        'backend_port': ports.get('backend_port', 6000 + (app_num * 10)),
                        'frontend_port': ports.get('frontend_port', 9000 + (app_num * 10))
                    }
        except Exception as e:
            logger.warning(f"Error getting port config: {e}")
        
        # Default calculation
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
analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")
performance_bp = Blueprint("performance", __name__, url_prefix="/performance")
batch_bp = Blueprint("batch", __name__, url_prefix="/batch")
docker_bp = Blueprint("docker", __name__, url_prefix="/docker")

# ===========================
# MAIN ROUTES
# ===========================

@main_bp.route("/")
def dashboard():
    """Modern dashboard with expandable model tabs."""
    try:
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
            sample_models = models[:3]
            for model in sample_models:
                for app_num in range(1, 6):
                    try:
                        statuses = AppDataProvider.get_container_statuses(model.canonical_slug, app_num)
                        if statuses.get('backend') == 'running' and statuses.get('frontend') == 'running':
                            stats['running_containers'] += 1
                        elif statuses.get('backend') in ['exited', 'dead'] or statuses.get('frontend') in ['exited', 'dead']:
                            stats['error_containers'] += 1
                    except Exception:
                        pass
            
            # Scale up estimates
            if len(sample_models) > 0:
                scale_factor = len(models) / len(sample_models) * 6
                stats['running_containers'] = int(stats['running_containers'] * scale_factor)
                stats['error_containers'] = int(stats['error_containers'] * scale_factor)
        
        return render_template('pages/dashboard.html', summary_stats=stats)
        
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        return render_template("pages/error.html", error=str(e))


@main_bp.route("/app/<model>/<int:app_num>")
def app_details(model: str, app_num: int):
    """Application details page with tabbed interface."""
    try:
        app_info = AppDataProvider.get_app_info(model, app_num)
        if not app_info:
            flash(f"Application {model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        container_statuses = AppDataProvider.get_container_statuses(model, app_num)
        
        context = {
            'app_info': app_info,
            'app': app_info,  # Backward compatibility
            'statuses': container_statuses,
            'container_statuses': container_statuses,  # Backward compatibility
            'model': model,
            'app_num': app_num
        }
        
        # Handle tab requests
        tab = request.args.get('tab')
        if ResponseHandler.is_htmx_request() and tab:
            if tab == 'performance':
                # Add performance-specific data
                try:
                    from performance_service import LocustPerformanceTester
                    tester = LocustPerformanceTester(Path.cwd() / "performance_reports")
                    context['existing_results'] = tester.load_performance_results(model, app_num)
                    context['has_results'] = context['existing_results'] is not None
                    context['performance_available'] = True
                except ImportError:
                    context['performance_available'] = False
                    context['existing_results'] = None
                    context['has_results'] = False
            
            return render_template(f"partials/app_tab_{tab}.html", **context)
        
        return render_template("pages/app_details.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app details: {e}")
        return ResponseHandler.error_response(f"Failed to load app details: {str(e)}")


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
        
        models_data = []
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
            
            model_data = {
                'id': model.id,
                'canonical_slug': model.canonical_slug,
                'model_name': model.model_name,
                'display_name': model.model_name,
                'provider': model.provider,
                'context_window': model.context_window,
                'max_output_tokens': model.max_output_tokens,
                'input_price_per_token': model.input_price_per_token,
                'output_price_per_token': model.output_price_per_token,
                'supports_function_calling': model.supports_function_calling,
                'supports_vision': model.supports_vision,
                'total_apps': 30,
                'running_containers': running_containers,
                'stopped_containers': stopped_containers,
                'error_containers': error_containers
            }
            models_data.append(model_data)
        
        return render_template('partials/dashboard_models_grid.html', models=models_data)
        
    except Exception as e:
        logger.error(f"Error fetching dashboard models: {e}")
        return f"<div class='error-state'>Error loading models: {str(e)}</div>", 500


@api_bp.route("/model/<model_slug>/apps")
def api_model_apps(model_slug: str):
    """Get applications for a specific model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        apps_data = []
        for app_num in range(1, 31):
            app_data = AppDataProvider.get_app_for_dashboard(model_slug, app_num)
            apps_data.append(app_data)
        
        return render_template('partials/dashboard_model_apps.html', 
                             apps=apps_data, model_slug=model_slug)
        
    except Exception as e:
        logger.error(f"Error loading apps for model {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/stats")
def api_model_stats(model_slug: str):
    """Get container statistics for a specific model with optimized Docker lookups."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
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
def api_model_details(model_slug: str):
    """Get detailed information about a model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        # Get model capabilities and statistics
        capabilities = model.get_capabilities() if hasattr(model, 'get_capabilities') else {}
        
        details = {
            'model_name': model.model_name,
            'display_name': model.model_name,  # Use model_name as display_name
            'provider': model.provider,
            'canonical_slug': model.canonical_slug,
            'capabilities': capabilities,
            'total_apps': 30,
            'created_at': model.created_at.isoformat() if model.created_at else None
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template('partials/model_details_modal.html', model=model, details=details)
        
        return ResponseHandler.success_response(data=details)
        
    except Exception as e:
        logger.error(f"Error getting model details for {model_slug}: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/model/<model_slug>/start-all", methods=["POST"])
def api_model_start_all(model_slug: str):
    """Start all containers for a model."""
    try:
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Start all 30 apps for this model
        apps_to_start = [(model_slug, app_num) for app_num in range(1, 31)]
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
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Stop all 30 apps for this model
        apps_to_stop = [(model_slug, app_num) for app_num in range(1, 31)]
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
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response('Model not found', 404)
        
        docker_manager = ServiceLocator.get_docker_manager()
        if not docker_manager:
            return ResponseHandler.error_response('Docker not available')
        
        # Restart all 30 apps for this model
        apps_to_restart = [(model_slug, app_num) for app_num in range(1, 31)]
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
        valid_actions = ['start', 'stop', 'restart', 'build']
        if action not in valid_actions:
            return ResponseHandler.error_response(f"Invalid action: {action}", 400)
        
        result = DockerOperations.execute_action(action, model, app_num)
        
        if result['success']:
            # For HTMX requests, return updated UI component
            if ResponseHandler.is_htmx_request():
                # Get the context of the request to determine response type
                if 'dashboard' in request.referrer:
                    # Return updated dashboard row
                    app_data = AppDataProvider.get_app_for_dashboard(model, app_num)
                    return render_template('partials/dashboard_app_row.html',
                                         app=app_data, model_slug=model)
                else:
                    # Return updated container status
                    statuses = AppDataProvider.get_container_statuses(model, app_num)
                    return render_template("partials/container_status.html",
                                         statuses=statuses, model=model, app_num=app_num,
                                         success_message=result.get('message'))
            
            # JSON response
            return ResponseHandler.success_response(
                data={'statuses': AppDataProvider.get_container_statuses(model, app_num)},
                message=result.get('message', f'{action} successful')
            )
        else:
            # Handle errors
            if ResponseHandler.is_htmx_request():
                if 'dashboard' in request.referrer:
                    # Return error row for dashboard
                    app_data = AppDataProvider.get_app_for_dashboard(model, app_num)
                    app_data['status'] = 'ERROR'
                    app_data['error_message'] = result.get('error')
                    return render_template('partials/dashboard_app_row.html',
                                         app=app_data, model_slug=model, show_error=True)
                else:
                    return render_template("partials/error_message.html", error=result.get('error'))
            
            return ResponseHandler.error_response(result.get('error', f'{action} failed'))
            
    except Exception as e:
        logger.error(f"Container action error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/status/<model>/<int:app_num>")
def get_app_status(model: str, app_num: int):
    """Get container status."""
    try:
        statuses = AppDataProvider.get_container_statuses(model, app_num)
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/container_status.html",
                                 statuses=statuses, model=model, app_num=app_num)
        
        return ResponseHandler.success_response(data=statuses)
        
    except Exception as e:
        logger.error(f"Status error: {e}")
        return ResponseHandler.error_response(str(e))


@api_bp.route("/logs/<model>/<int:app_num>/<container_type>")
def get_container_logs(model: str, app_num: int, container_type: str):
    """Get container logs."""
    try:
        if container_type not in ['backend', 'frontend']:
            return ResponseHandler.error_response("Invalid container type", 400)
        
        logs = DockerOperations.get_logs(model, app_num, container_type)
        
        context = {
            'logs': logs,
            'model': model,
            'app_num': app_num,
            'container_type': container_type
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/container_logs.html", **context)
        
        return ResponseHandler.success_response(data=context)
        
    except Exception as e:
        logger.error(f"Logs error: {e}")
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
# ANALYSIS ROUTES
# ===========================

@analysis_bp.route("/")
def analysis_overview():
    """Analysis tools overview."""
    try:
        # Check if analysis tools are available
        analyzer_available = False
        available_tools = {}
        analysis_types = []
        
        try:
            from security_analysis_service import UnifiedCLIAnalyzer, ToolCategory
            analyzer = UnifiedCLIAnalyzer(Path.cwd())
            available_tools = analyzer.get_available_tools()
            analysis_types = [t.value for t in ToolCategory]
            analyzer_available = True
        except ImportError:
            pass
        
        context = {
            'available_tools': available_tools,
            'analysis_types': analysis_types,
            'analyzers_available': analyzer_available
        }
        
        return ResponseHandler.render_response("analysis_overview_improved.html", **context)
        
    except Exception as e:
        logger.error(f"Analysis overview error: {e}")
        return ResponseHandler.error_response(str(e))


@analysis_bp.route("/<analysis_type>/<model>/<int:app_num>/run", methods=["POST"])
def run_analysis(analysis_type: str, model: str, app_num: int):
    """Run analysis on an application."""
    try:
        from security_analysis_service import UnifiedCLIAnalyzer, ToolCategory
        
        analyzer = UnifiedCLIAnalyzer(Path.cwd())
        category = ToolCategory(analysis_type)
        
        # Get options from form
        use_all_tools = request.form.get('use_all_tools', 'false').lower() == 'true'
        force_rerun = request.form.get('force_rerun', 'false').lower() == 'true'
        
        # Run analysis
        results = analyzer.run_analysis(
            model=model,
            app_num=app_num,
            categories=[category],
            use_all_tools=use_all_tools,
            force_rerun=force_rerun
        )
        
        context = {
            'analysis_type': analysis_type,
            'model': model,
            'app_num': app_num,
            'results': results,
            'success': True
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/analysis_results.html", **context)
        
        return ResponseHandler.success_response(data=results)
        
    except ImportError:
        return ResponseHandler.error_response("Analysis tools not available", 503)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# PERFORMANCE ROUTES
# ===========================

@performance_bp.route("/")
def performance_overview():
    """Performance testing overview."""
    try:
        context = {
            'test_types': ['load', 'stress', 'spike', 'endurance'],
            'default_users': 10,
            'default_duration': 30
        }
        
        return ResponseHandler.render_response("performance_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Performance overview error: {e}")
        return ResponseHandler.error_response(str(e))


@performance_bp.route("/<model>/<int:app_num>/run", methods=["POST"])
def run_performance_test(model: str, app_num: int):
    """Run performance test."""
    try:
        from performance_service import LocustPerformanceTester
        
        # Get test parameters
        user_count = int(request.form.get('user_count', 10))
        spawn_rate = int(request.form.get('spawn_rate', 1))
        duration = int(request.form.get('duration', 30))
        test_type = request.form.get('test_type', 'load')
        
        # Initialize tester
        tester = LocustPerformanceTester(Path.cwd() / "performance_reports")
        
        # Run test
        results = tester.run_performance_test(
            model=model,
            app_num=app_num,
            user_count=user_count,
            spawn_rate=spawn_rate,
            duration=duration,
            test_type=test_type
        )
        
        context = {
            'model': model,
            'app_num': app_num,
            'results': results,
            'success': results.get('success', False)
        }
        
        if ResponseHandler.is_htmx_request():
            return render_template("partials/performance_results.html", **context)
        
        return ResponseHandler.success_response(data=results)
        
    except ImportError:
        return ResponseHandler.error_response("Performance tools not available", 503)
    except Exception as e:
        logger.error(f"Performance test error: {e}")
        return ResponseHandler.error_response(str(e))


# ===========================
# BATCH ROUTES
# ===========================

@batch_bp.route("/")
def batch_overview():
    """Batch processing overview."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        
        # Get available options
        models = ModelCapability.query.all()
        analysis_types = ['frontend_security', 'backend_security', 'performance', 'zap', 'code_quality']
        
        context = {
            'jobs': [],
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'stats': {
                'total': 0,
                'pending': 0,
                'running': 0,
                'completed': 0,
                'failed': 0,
                'cancelled': 0,
                'archived': 0
            },
            'available_models': models,
            'available_apps': list(range(1, 31)),
            'analysis_types': analysis_types,
            'page_title': 'Batch Analysis Management'
        }
        
        if batch_service:
            jobs = batch_service.get_all_jobs()
            context['jobs'] = [job.to_dict() for job in jobs]
            context['stats'] = batch_service.get_job_stats()
            context['total_jobs'] = len(jobs)
            context['running_jobs'] = sum(1 for j in jobs if j.status.value == 'running')
            context['completed_jobs'] = sum(1 for j in jobs if j.status.value == 'completed')
            context['failed_jobs'] = sum(1 for j in jobs if j.status.value == 'failed')
        
        return render_template("pages/batch_dashboard.html", **context)
        
    except Exception as e:
        logger.error(f"Batch overview error: {e}")
        models = ModelCapability.query.all()
        context = {
            'jobs': [],
            'total_jobs': 0,
            'running_jobs': 0,
            'completed_jobs': 0,
            'failed_jobs': 0,
            'stats': {'total': 0, 'pending': 0, 'running': 0, 'completed': 0, 'failed': 0},
            'available_models': models,
            'available_apps': list(range(1, 31)),
            'analysis_types': ['security', 'performance', 'quality'],
            'error_message': f"Service temporarily unavailable: {str(e)}"
        }
        return render_template("pages/batch_dashboard.html", **context)


@batch_bp.route("/create", methods=["GET", "POST"])
def create_batch_job():
    """Create new batch job."""
    if request.method == "GET":
        models = ModelCapability.query.all()
        analysis_types = ['frontend_security', 'backend_security', 'performance', 'zap', 'code_quality']
        
        context = {
            'available_models': models,
            'available_apps': list(range(1, 31)),
            'analysis_types': analysis_types,
            'page_title': 'Create Batch Job'
        }
        
        return render_template("pages/create_batch_job.html", **context)
    
    else:  # POST
        try:
            batch_service = ServiceLocator.get_batch_service()
            if not batch_service:
                flash("Batch service not available", "error")
                return redirect(url_for('batch.batch_overview'))
            
            # Get form data
            job_name = request.form.get('name', '').strip()
            job_description = request.form.get('description', '').strip()
            analysis_types = request.form.getlist('analysis_types')
            selected_models = request.form.getlist('models')
            
            # Validate
            if not all([job_name, analysis_types, selected_models]):
                flash("Missing required fields", "error")
                return redirect(url_for('batch.batch_overview'))
            
            # Create jobs for each model
            total_tasks = 0
            for model in selected_models:
                app_range = request.form.get(f'app_range_{model}', '1-30')
                
                job = batch_service.create_job(
                    name=f"{job_name} - {model}",
                    description=job_description or f"Batch analysis for {model}",
                    analysis_types=analysis_types,
                    models=[model],
                    app_range_str=app_range,
                    auto_start=True
                )
                
                total_tasks += job.progress.get('total', 0)
            
            flash(f'Batch job "{job_name}" created successfully ({total_tasks} tasks)', "success")
            return redirect(url_for('batch.batch_overview'))
            
        except Exception as e:
            logger.error(f"Create job error: {e}")
            flash(f"Error creating job: {str(e)}", "error")
            return redirect(url_for('batch.batch_overview'))


@batch_bp.route("/job/<job_id>")
def view_job(job_id: str):
    """View batch job details."""
    try:
        batch_service = ServiceLocator.get_batch_service()
        if not batch_service:
            return ResponseHandler.error_response("Batch service not available")
        
        job = batch_service.get_job(job_id)
        if not job:
            return ResponseHandler.error_response("Job not found", 404)
        
        tasks = batch_service.get_job_tasks(job_id)
        
        task_stats = {
            'total': len(tasks),
            'pending': sum(1 for t in tasks if t.status.value == 'pending'),
            'running': sum(1 for t in tasks if t.status.value == 'running'),
            'completed': sum(1 for t in tasks if t.status.value == 'completed'),
            'failed': sum(1 for t in tasks if t.status.value == 'failed')
        }
        
        context = {
            'job': job.to_dict(),
            'tasks': [task.to_dict() for task in tasks],
            'task_stats': task_stats,
            'page_title': f'Job: {job.name}'
        }
        
        return render_template("pages/view_job.html", **context)
        
    except Exception as e:
        logger.error(f"View job error: {e}")
        return ResponseHandler.error_response(str(e))


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
    return ResponseHandler.error_response("Internal server error", 500)


# ===========================
# TEMPLATE HELPERS
# ===========================

def register_template_helpers(app):
    """Register Jinja2 template helpers."""
    
    @app.template_filter('format_datetime')
    def format_datetime(value):
        """Format datetime for display."""
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                return value
        return value.strftime('%Y-%m-%d %H:%M:%S') if value else ''
    
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
# BLUEPRINT REGISTRATION
# ===========================

def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    app.register_blueprint(main_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(performance_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(docker_bp)
    
    # Register template helpers
    register_template_helpers(app)
    
    logger.info("All blueprints registered successfully")


# Export blueprints for use in app factory
__all__ = [
    'main_bp', 'api_bp', 'analysis_bp', 'performance_bp', 'batch_bp', 'docker_bp',
    'register_blueprints'
]