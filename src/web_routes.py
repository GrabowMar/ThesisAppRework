"""
Flask Routes and Blueprints - HTMX Edition
==========================================

Modern route definitions for the Thesis Research App using HTMX patterns.
Includes routes for dashboard, analysis, performance testing, ZAP scanning, and batch processing.

Key HTMX Patterns Used:
- hx-get/hx-post for AJAX requests
- hx-target for DOM updates  
- hx-swap for element replacement strategies
- hx-trigger for event handling
- Partial template rendering for component updates
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint, Response, current_app, flash, jsonify, make_response,
    redirect, render_template, request, session, url_for
)

# ===========================
# SERVICE ACCESS HELPERS
# ===========================

def get_model_service():
    """Get model service from Flask app context."""
    return getattr(current_app, 'model_service', None)

def get_scan_manager():
    """Get scan manager from Flask app context."""
    service_manager = current_app.config.get('service_manager')
    if service_manager:
        return service_manager.get_service('scan_manager')
    return None

def get_docker_manager():
    """Get docker manager from Flask app context."""
    service_manager = current_app.config.get('service_manager')
    if service_manager:
        return service_manager.get_service('docker_manager')
    return None

def get_all_apps():
    """Get all apps with minimal data."""
    # Return dummy data for now - would normally come from database
    return []

def get_app_info(model: str, app_num: int):
    """Get app information."""
    return {
        'model': model,
        'app_num': app_num,
        'status': 'unknown'
    }

def get_ai_models():
    """Get AI models."""
    # In real implementation, would query ModelCapability table
    return []

def get_port_config(model: str = None, app_num: int = None):
    """Get port configuration."""
    # Import here to avoid circular import
    try:
        from models import PortConfiguration
        if model and app_num:
            config = PortConfiguration.query.filter_by(
                model_slug=model.replace('-', '_'),
                app_number=app_num
            ).first()
            if config:
                return {
                    'backend_port': config.backend_port,
                    'frontend_port': config.frontend_port
                }
    except Exception:
        pass
    return {'backend_port': 6000, 'frontend_port': 9000}

def get_app_container_statuses(model: str, app_num: int, docker_manager):
    """Get app container statuses."""
    if docker_manager:
        try:
            backend_name = f"{model.replace('-', '_')}_app{app_num}_backend"
            frontend_name = f"{model.replace('-', '_')}_app{app_num}_frontend"
            
            backend_status = docker_manager.get_container_status(backend_name)
            frontend_status = docker_manager.get_container_status(frontend_name)
            
            return {
                'backend': backend_status,
                'frontend': frontend_status
            }
        except Exception:
            pass
    
    return {'backend': 'not_found', 'frontend': 'not_found'}

def handle_docker_action(action: str, model: str, app_num: int):
    """Handle docker action."""
    docker_manager = get_docker_manager()
    if not docker_manager:
        return {'success': False, 'error': 'Docker manager not available'}
    
    try:
        port_config = get_port_config(model, app_num)
        compose_path = f"misc/models/{model}/app{app_num}/docker-compose.yml"
        
        if action == 'start':
            return docker_manager.start_containers(compose_path)
        elif action == 'stop':
            return docker_manager.stop_containers(compose_path)
        elif action == 'restart':
            return docker_manager.restart_containers(compose_path)
        else:
            return {'success': False, 'error': f'Unknown action: {action}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def verify_container_health(docker_manager, model: str, app_num: int, max_retries: int = 15, retry_delay: int = 5):
    """Verify container health."""
    # Simplified implementation
    if docker_manager:
        statuses = get_app_container_statuses(model, app_num, docker_manager)
        return statuses.get('backend') == 'running' and statuses.get('frontend') == 'running'
    return False

def load_json_results_for_template(model: str, app_num: int, analysis_type: Optional[str] = None):
    """Load JSON results for template."""
    # Stub implementation - would load from files or database
    return {'results': []}

def get_available_analysis_results(model: str, app_num: int):
    """Get available analysis results."""
    # Stub implementation
    return []

def get_latest_analysis_timestamp(model: str, app_num: int):
    """Get latest analysis timestamp."""
    # Stub implementation
    return None

def get_dashboard_data_optimized(docker_manager):
    """Get dashboard data optimized."""
    try:
        from models import ModelCapability, PortConfiguration
        
        # Get models from database
        models = ModelCapability.query.all()
        apps = []
        
        for model in models:
            for app_num in range(1, 31):  # Apps 1-30
                port_config = PortConfiguration.query.filter_by(
                    model_slug=model.canonical_slug,
                    app_number=app_num
                ).first()
                
                if port_config:
                    apps.append({
                        'model': model.canonical_slug.replace('_', '-'),
                        'app_num': app_num,
                        'backend_port': port_config.backend_port,
                        'frontend_port': port_config.frontend_port,
                        'status': 'unknown'
                    })
        
        return {'apps': apps, 'cache_used': False}
    except Exception as e:
        return {'apps': [], 'cache_used': False}

def create_api_response(success: bool = True, data: Any = None, error: Optional[str] = None, message: Optional[str] = None, code: int = 200):
    """Create API response."""
    response = {
        'success': success,
        'data': data,
        'error': error,
        'message': message
    }
    return jsonify(response), code

def filter_apps(apps, search=None, model=None, status=None):
    """Filter apps."""
    filtered = apps
    
    if search:
        search = search.lower()
        filtered = [app for app in filtered 
                   if search in app.get('model', '').lower() 
                   or search in str(app.get('app_num', ''))]
    
    if model:
        filtered = [app for app in filtered if app.get('model') == model]
    
    if status:
        filtered = [app for app in filtered if app.get('status') == status]
    
    return filtered

def get_cache_stats():
    """Get cache statistics."""
    return {
        'cache_hits': 0,
        'cache_misses': 0,
        'cache_size': 0
    }

def clear_container_cache(model: Optional[str] = None, app_num: Optional[int] = None):
    """Clear container cache."""
    # Stub implementation
    return True

def create_logger_for_component(component_name: str):
    """Create logger for component."""
    return logging.getLogger(component_name)

# Batch analysis helper functions
def _create_safe_job_dict(job):
    """Create safe job dict."""
    # Stub implementation
    return {}

def _create_safe_task_dict(task):
    """Create safe task dict."""
    # Stub implementation
    return {}

def _calculate_progress_stats(tasks):
    """Calculate progress stats."""
    # Stub implementation
    return {
        'total': len(tasks) if tasks else 0,
        'completed': 0,
        'running': 0,
        'failed': 0
    }

# Enums and constants
class ScanState:
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    ERROR = "Error"
    STOPPED = "Stopped"

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"

class JobStatus:
    PENDING = "pending"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELLING = "cancelling"
    ARCHIVED = "archived"
    ERROR = "error"

class AnalysisType:
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_SECURITY = "backend_security"
    PERFORMANCE = "performance"
    ZAP = "zap"
    GPT4ALL = "gpt4all"
    CODE_QUALITY = "code_quality"

# Initialize logger
logger = create_logger_for_component('routes')

# Import analyzers with fallbacks
try:
    from security_analysis_service import UnifiedCLIAnalyzer, ToolCategory
except ImportError:
    logger.warning("CLI tools analysis not available")
    UnifiedCLIAnalyzer = None
    ToolCategory = None

try:
    from performance_service import LocustPerformanceTester
except ImportError:
    logger.warning("Performance analysis not available")
    LocustPerformanceTester = None

try:
    from zap_service import create_scanner
except ImportError:
    logger.warning("ZAP scanner not available")
    create_scanner = None

try:
    from openrouter_service import OpenRouterAnalyzer
except ImportError:
    logger.warning("OpenRouter analyzer not available")
    OpenRouterAnalyzer = None

# ===========================
# BLUEPRINT DEFINITIONS
# ===========================

# Main application routes
main_bp = Blueprint("main", __name__)

# API routes for HTMX interactions
api_bp = Blueprint("api", __name__, url_prefix="/api")

# Analysis routes (security and quality)
analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

# Performance testing routes
performance_bp = Blueprint("performance", __name__, url_prefix="/performance")

# ZAP security scanning routes
zap_bp = Blueprint("zap", __name__, url_prefix="/zap")

# GPT4All/OpenRouter analysis routes
openrouter_bp = Blueprint("openrouter", __name__, url_prefix="/openrouter")

# Batch processing routes
batch_bp = Blueprint("batch", __name__, url_prefix="/batch")

# Generation content routes
generation_bp = Blueprint("generation", __name__, url_prefix="/generation")

# Docker management routes
docker_bp = Blueprint("docker", __name__, url_prefix="/docker")


# ===========================
# UTILITY FUNCTIONS
# ===========================

def is_htmx_request() -> bool:
    """Check if the request is coming from HTMX."""
    return request.headers.get('HX-Request') == 'true'


def render_htmx_response(template_name: str, **context) -> str:
    """Render template for HTMX or full page response."""
    if is_htmx_request():
        # For HTMX requests, return just the component
        return render_template(f"partials/{template_name}", **context)
    else:
        # For regular requests, return full page
        return render_template(f"pages/{template_name}", **context)


def get_request_filters() -> Dict[str, Any]:
    """Extract common filter parameters from request."""
    return {
        'search': request.args.get('search', '').strip(),
        'model': request.args.get('model', '').strip(),
        'status': request.args.get('status', '').strip(),
        'page': int(request.args.get('page', 1)),
        'per_page': int(request.args.get('per_page', 20))
    }


# ===========================
# MAIN ROUTES
# ===========================

@main_bp.route("/")
def dashboard():
    """
    Main dashboard showing all applications with HTMX-powered filtering.
    
    HTMX Features:
    - Live search with hx-get and hx-target
    - Filter dropdowns with automatic updates
    - Auto-refresh capabilities
    - Infinite scroll pagination
    """
    logger.info("Loading dashboard")
    
    try:
        # Get services
        docker_manager = get_docker_manager()
        
        # Load dashboard data with caching
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        # Apply filters
        filters = get_request_filters()
        filtered_apps = filter_apps(
            all_apps, 
            search=filters['search'],
            model=filters['model'], 
            status=filters['status']
        )
        
        # Pagination
        start_idx = (filters['page'] - 1) * filters['per_page']
        end_idx = start_idx + filters['per_page']
        paginated_apps = filtered_apps[start_idx:end_idx]
        
        # Calculate statistics
        stats = {
            'total_apps': len(all_apps),
            'filtered_apps': len(filtered_apps),
            'running_apps': sum(1 for app in all_apps if app.get('status') == 'running'),
            'models_count': len(set(app['model'] for app in all_apps))
        }
        
        # Get unique models for filter dropdown
        unique_models = sorted(set(app['model'] for app in all_apps))
        
        context = {
            'apps': paginated_apps,
            'stats': stats,
            'unique_models': unique_models,
            'filters': filters,
            'has_more': end_idx < len(filtered_apps),
            'cache_used': dashboard_data.get('cache_used', False)
        }
        
        # Return appropriate response based on request type
        if is_htmx_request():
            if request.args.get('component') == 'apps-list':
                return render_template("partials/app_list.html", **context)
            elif request.args.get('component') == 'stats':
                return render_template("partials/dashboard_stats.html", **context)
        
        return render_template("pages/dashboard.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load dashboard data")
        return render_template("pages/error.html", error=str(e))


@main_bp.route("/app/<model>/<int:app_num>")
def app_details(model: str, app_num: int):
    """
    Application details page with HTMX-powered tabs and live updates.
    
    HTMX Features:
    - Tabbed interface with hx-get for content loading
    - Live container status updates
    - Analysis result loading on demand
    """
    try:
        # Get app information
        app_info = get_app_info(model, app_num)
        if not app_info:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error=f"Application {model}/app{app_num} not found")
            flash(f"Application {model}/app{app_num} not found", "error")
            return redirect(url_for("main.dashboard"))
        
        # Get container statuses
        docker_manager = get_docker_manager()
        container_statuses = get_app_container_statuses(model, app_num, docker_manager)
        
        # Load analysis results
        analysis_results = load_json_results_for_template(model, app_num)
        available_analyses = get_available_analysis_results(model, app_num)
        last_analysis = get_latest_analysis_timestamp(model, app_num)
        
        context = {
            'app': app_info,
            'container_statuses': container_statuses,
            'analysis_results': analysis_results,
            'available_analyses': available_analyses,
            'last_analysis': last_analysis,
            'model': model,
            'app_num': app_num
        }
        
        # Handle tab-specific requests
        tab = request.args.get('tab')
        if is_htmx_request() and tab:
            return render_template(f"partials/app_tab_{tab}.html", **context)
        
        return render_template("pages/app_details.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading app details for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"Failed to load app details: {str(e)}")
        flash(f"Error loading application details: {str(e)}", "error")
        return redirect(url_for("main.dashboard"))


@main_bp.route("/models")
def models_overview():
    """Models overview page with filtering and statistics."""
    try:
        models = get_ai_models()
        port_config = get_port_config()
        
        # Group apps by model
        model_stats = {}
        for config in port_config:
            model_name = config['model_name']
            if model_name not in model_stats:
                model_stats[model_name] = {
                    'name': model_name,
                    'app_count': 0,
                    'total_ports': 0
                }
            model_stats[model_name]['app_count'] += 1
            model_stats[model_name]['total_ports'] += 2  # backend + frontend
        
        context = {
            'models': models,
            'model_stats': list(model_stats.values()),
            'total_models': len(models)
        }
        
        return render_htmx_response("models_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading models overview: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load models data")
        return render_template("pages/error.html", error=str(e))


@main_bp.route("/debug/config/<model>/<int:app_num>")
def debug_config(model: str, app_num: int):
    """Debug route to check configuration for specific model/app."""
    try:
        from core_services import get_app_config_by_model_and_number, get_container_names
        
        app_config = get_app_config_by_model_and_number(model, app_num)
        
        try:
            container_names = get_container_names(model, app_num)
        except Exception as e:
            container_names = f"Error: {e}"
        
        debug_info = {
            'model': model,
            'app_num': app_num,
            'app_config': app_config,
            'container_names': container_names
        }
        
        return f"<pre>{json.dumps(debug_info, indent=2)}</pre>"
        
    except Exception as e:
        return f"<pre>Error: {e}</pre>"


# ===========================
# API ROUTES (HTMX ENDPOINTS)
# ===========================

@api_bp.route("/status/<model>/<int:app_num>")
def get_app_status(model: str, app_num: int):
    """
    Get live container status for HTMX updates.
    
    Returns JSON for programmatic access or HTML partial for HTMX.
    """
    try:
        docker_manager = get_docker_manager()
        statuses = get_app_container_statuses(model, app_num, docker_manager)
        
        if is_htmx_request():
            return render_template("partials/container_status.html", 
                                 statuses=statuses, model=model, app_num=app_num)
        else:
            return jsonify(statuses)
            
    except Exception as e:
        logger.error(f"Error getting status for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to get status")
        return create_api_response(False, error=str(e))


@api_bp.route("/search")
def search_apps():
    """
    HTMX-powered search endpoint.
    
    Returns filtered app list as HTML partial.
    """
    try:
        # Get all apps
        docker_manager = get_docker_manager()
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        # Apply search filter
        search_term = request.args.get('search', '').strip()
        filtered_apps = filter_apps(all_apps, search=search_term)
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_apps = filtered_apps[start_idx:end_idx]
        
        context = {
            'apps': paginated_apps,
            'has_more': end_idx < len(filtered_apps),
            'search_term': search_term
        }
        
        return render_template("partials/app_list.html", **context)
        
    except Exception as e:
        logger.error(f"Error searching apps: {e}")
        return render_template("partials/error_message.html", 
                             error="Search failed")


@api_bp.route("/advanced-search")
def advanced_search():
    """
    Advanced search endpoint with multiple filters.
    
    Returns filtered app list as HTML partial for HTMX.
    """
    try:
        # Get all apps
        docker_manager = get_docker_manager()
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        # Get search parameters
        search_term = request.args.get('q', '').strip()
        model_filter = request.args.get('model', '').strip()
        app_type_filter = request.args.get('app_type', '').strip()
        status_filter = request.args.get('status', '').strip()
        analysis_status = request.args.get('analysis_status', '').strip()
        analysis_types = request.args.getlist('analysis_types')
        
        # Apply filters
        filtered_apps = all_apps
        
        # Basic search filter
        if search_term:
            filtered_apps = filter_apps(filtered_apps, search=search_term)
        
        # Model filter
        if model_filter:
            filtered_apps = [app for app in filtered_apps 
                           if app.get('model', {}).get('slug') == model_filter]
        
        # App type filter
        if app_type_filter:
            filtered_apps = [app for app in filtered_apps 
                           if str(app.get('app_number', '')) == app_type_filter]
        
        # Status filter
        if status_filter:
            filtered_apps = [app for app in filtered_apps 
                           if app.get('status', '').lower() == status_filter.lower()]
                           
        # Analysis status filter
        if analysis_status:
            if analysis_status == 'analyzed':
                filtered_apps = [app for app in filtered_apps 
                               if app.get('has_analysis', False)]
            elif analysis_status == 'pending':
                filtered_apps = [app for app in filtered_apps 
                               if not app.get('has_analysis', False)]
            elif analysis_status == 'failed':
                filtered_apps = [app for app in filtered_apps 
                               if app.get('analysis_failed', False)]
        
        # Analysis types filter
        if analysis_types:
            # This would need to be implemented based on your analysis tracking
            pass
        
        # Pagination
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_apps = filtered_apps[start_idx:end_idx]
        
        context = {
            'apps': paginated_apps,
            'has_more': end_idx < len(filtered_apps),
            'total_results': len(filtered_apps),
            'search_params': {
                'q': search_term,
                'model': model_filter,
                'app_type': app_type_filter,
                'status': status_filter,
                'analysis_status': analysis_status,
                'analysis_types': analysis_types
            }
        }
        
        return render_template("partials/advanced_search_results.html", **context)
        
    except Exception as e:
        logger.error(f"Error in advanced search: {e}")
        return render_template("partials/error_message.html", 
                             error="Advanced search failed")


@api_bp.route("/cache/stats")
def cache_stats():
    """Get cache statistics for monitoring."""
    try:
        stats = get_cache_stats()
        if is_htmx_request():
            return render_template("partials/cache_info.html", stats=stats)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return create_api_response(False, error=str(e))


@api_bp.route("/header-stats")
def get_header_stats():
    """Get header statistics for the navbar."""
    try:
        docker_manager = get_docker_manager()
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        # Calculate stats
        total_apps = len(all_apps)
        running_containers = len([app for app in all_apps if app.get('status') == 'running'])
        
        stats = {
            'total_apps': total_apps,
            'running_containers': running_containers,
            'stopped_apps': total_apps - running_containers,
            'models_count': len(set(app['model'] for app in all_apps))
        }
        
        if is_htmx_request():
            return render_template("partials/header_stats.html", stats=stats)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting header stats: {e}")
        if is_htmx_request():
            return render_template("partials/header_stats.html", 
                                 stats={'total_apps': 0, 'running_containers': 0, 'stopped_apps': 0, 'models_count': 0})
        return jsonify({'total_apps': 0, 'running_containers': 0, 'stopped_apps': 0, 'models_count': 0})


@api_bp.route("/health-status")
def health_status():
    """Get system health status."""
    try:
        # Simple health check - check if Docker is accessible
        docker_manager = get_docker_manager()
        docker_healthy = True
        
        try:
            # Try to ping Docker
            docker_manager.client.ping()
        except Exception:
            docker_healthy = False
        
        health_data = {
            'status': 'healthy' if docker_healthy else 'degraded',
            'docker': docker_healthy,
            'timestamp': datetime.now().isoformat()
        }
        
        if is_htmx_request():
            return render_template("partials/health_indicator.html", **health_data)
        return jsonify(health_data)
        
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        health_data = {
            'status': 'error',
            'docker': False,
            'timestamp': datetime.now().isoformat()
        }
        if is_htmx_request():
            return render_template("partials/health_indicator.html", **health_data)
        return jsonify(health_data)


@api_bp.route("/notifications")
def get_notifications():
    """Get system notifications."""
    try:
        # For now, return empty notifications
        # In a real app, this would fetch from a notifications service
        notifications = []
        
        # You could add sample notifications here for testing:
        # notifications = [
        #     {
        #         'id': 1,
        #         'type': 'info',
        #         'title': 'System Status',
        #         'message': 'All services are running normally',
        #         'timestamp': datetime.now().isoformat(),
        #         'read': False
        #     }
        # ]
        
        if is_htmx_request():
            return render_template("partials/notifications_list.html", 
                                 notifications=notifications)
        return jsonify({'notifications': notifications})
        
    except Exception as e:
        logger.error(f"Error getting notifications: {e}")
        if is_htmx_request():
            return render_template("partials/notifications_list.html", 
                                 notifications=[])
        return jsonify({'notifications': []})


@api_bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """Clear application cache."""
    try:
        clear_container_cache()
        
        if is_htmx_request():
            return render_template("partials/success_message.html", 
                                 message="Cache cleared successfully")
        return create_api_response(True, message="Cache cleared")
        
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to clear cache")
        return create_api_response(False, error=str(e))


@api_bp.route("/dashboard-stats")
def dashboard_stats():
    """Get dashboard statistics."""
    try:
        docker_manager = get_docker_manager()
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        stats = {
            'total_apps': len(all_apps),
            'running_containers': len([app for app in all_apps if app.get('status') == 'running']),
            'models_count': len(set(app['model'] for app in all_apps)),
            'analyzed_apps': len([app for app in all_apps if app.get('has_analysis', False)]),
            'new_apps_today': 0,  # Would calculate from timestamps
            'success_rate': 85,   # Would calculate from analysis results
            'avg_response_time': 250  # Would calculate from performance data
        }
        
        if is_htmx_request():
            return render_template("partials/dashboard_stats.html", stats=stats)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        if is_htmx_request():
            return render_template("partials/dashboard_stats.html", 
                                 stats={'total_apps': 0, 'running_containers': 0, 'models_count': 0, 'analyzed_apps': 0, 'new_apps_today': 0, 'success_rate': 0, 'avg_response_time': 0})
        return jsonify({'total_apps': 0, 'running_containers': 0, 'models_count': 0, 'analyzed_apps': 0})


@api_bp.route("/recent-activity")
def recent_activity():
    """Get recent activity feed."""
    try:
        # For now, return empty activity
        # In a real app, this would fetch recent activities from logs or database
        activities = []
        
        if is_htmx_request():
            return render_template("partials/recent_activity.html", activities=activities)
        return jsonify({'activities': activities})
        
    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")
        if is_htmx_request():
            return render_template("partials/recent_activity.html", activities=[])
        return jsonify({'activities': []})


@api_bp.route("/sidebar-stats")
def sidebar_stats():
    """Get sidebar statistics."""
    try:
        docker_manager = get_docker_manager()
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        stats = {
            'active_scans': 0,  # Would get from scan service
            'queued_jobs': 0,   # Would get from batch service
            'alerts': 0,        # Would get from monitoring service
            'success_rate': 85  # Would calculate from analysis results
        }
        
        if is_htmx_request():
            return render_template("partials/sidebar_stats.html", stats=stats)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting sidebar stats: {e}")
        if is_htmx_request():
            return render_template("partials/sidebar_stats.html", 
                                 stats={'active_scans': 0, 'queued_jobs': 0, 'alerts': 0, 'success_rate': 85})
        return jsonify({'active_scans': 0, 'queued_jobs': 0, 'alerts': 0, 'success_rate': 85})


@api_bp.route("/system-health")
def system_health():
    """Get system health status."""
    try:
        # Check Docker health
        docker_manager = get_docker_manager()
        docker_healthy = True
        
        try:
            docker_manager.client.ping()
        except Exception:
            docker_healthy = False
        
        # Overall system health
        health_status = {
            'status': 'healthy' if docker_healthy else 'degraded',
            'docker': docker_healthy,
            'services': {
                'docker': docker_healthy,
                'database': True,  # Would check database connection
                'cache': True      # Would check cache service
            },
            'timestamp': datetime.now().isoformat()
        }
        
        if is_htmx_request():
            return render_template("partials/system_health.html", **health_status)
        return jsonify(health_status)
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        health_status = {
            'status': 'error',
            'docker': False,
            'services': {'docker': False, 'database': False, 'cache': False},
            'timestamp': datetime.now().isoformat()
        }
        if is_htmx_request():
            return render_template("partials/system_health.html", **health_status)
        return jsonify(health_status)


@api_bp.route("/settings")
def get_settings():
    """Get application settings for the settings modal."""
    try:
        # Sample settings - in a real app, these would come from a config service
        settings = {
            'auto_refresh_interval': 30,
            'items_per_page': 20,
            'enable_notifications': True,
            'enable_auto_start': False,
            'default_analysis_tools': ['bandit', 'safety'],
            'log_level': 'INFO',
            'theme': 'auto',
            'cache_enabled': True,
            'max_concurrent_analyses': 5
        }
        
        if is_htmx_request():
            return render_template("partials/settings_form.html", settings=settings)
        return jsonify(settings)
        
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load settings")
        return create_api_response(False, error=str(e))


@api_bp.route("/settings", methods=["POST"])
def save_settings():
    """Save application settings."""
    try:
        # Get form data
        settings = {
            'auto_refresh_interval': int(request.form.get('auto_refresh_interval', 30)),
            'items_per_page': int(request.form.get('items_per_page', 20)),
            'enable_notifications': request.form.get('enable_notifications') == 'on',
            'enable_auto_start': request.form.get('enable_auto_start') == 'on',
            'default_analysis_tools': request.form.getlist('default_analysis_tools'),
            'log_level': request.form.get('log_level', 'INFO'),
            'theme': request.form.get('theme', 'auto'),
            'cache_enabled': request.form.get('cache_enabled') == 'on',
            'max_concurrent_analyses': int(request.form.get('max_concurrent_analyses', 5))
        }
        
        # In a real app, you would save these to a config service or database
        logger.info(f"Settings saved: {settings}")
        
        if is_htmx_request():
            return render_template("partials/success_message.html", 
                                 message="Settings saved successfully")
        return create_api_response(True, message="Settings saved", data=settings)
        
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to save settings")
        return create_api_response(False, error=str(e))


# ===========================
# DOCKER MANAGEMENT ROUTES
# ===========================

@docker_bp.route("/")
def docker_overview():
    """Docker management overview page."""
    try:
        docker_manager = get_docker_manager()
        
        # Get Docker system information
        try:
            docker_info = docker_manager.client.info()
            docker_version = docker_manager.client.version()
            docker_available = True
        except Exception as e:
            logger.warning(f"Docker not available: {e}")
            docker_info = {}
            docker_version = {}
            docker_available = False
        
        # Get container statistics
        dashboard_data = get_dashboard_data_optimized(docker_manager)
        all_apps = dashboard_data.get('apps', [])
        
        container_stats = {
            'total_apps': len(all_apps),
            'running': len([app for app in all_apps if app.get('status') == 'running']),
            'stopped': len([app for app in all_apps if app.get('status') != 'running']),
            'models': len(set(app['model'] for app in all_apps))
        }
        
        context = {
            'docker_available': docker_available,
            'docker_info': docker_info,
            'docker_version': docker_version,
            'container_stats': container_stats,
            'recent_apps': all_apps[:10]  # Show recent 10 apps
        }
        
        return render_htmx_response("docker_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading Docker overview: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load Docker overview")
        return render_template("pages/error.html", error=str(e))


@docker_bp.route("/<action>/<model>/<int:app_num>", methods=["POST"])
def docker_action(action: str, model: str, app_num: int):
    """
    Handle Docker actions with HTMX response.
    
    Actions: start, stop, restart, logs
    """
    try:
        logger.info(f"Docker {action} requested for {model}/app{app_num}")
        
        # Validate action
        valid_actions = ['start', 'stop', 'restart']
        if action not in valid_actions:
            raise ValueError(f"Invalid action: {action}")
        
        # Perform Docker action
        success, message = handle_docker_action(action, model, app_num)
        
        if success:
            # Verify container health for start/restart actions
            if action in ['start', 'restart']:
                docker_manager = get_docker_manager()
                health_ok, health_msg = verify_container_health(
                    docker_manager, model, app_num
                )
                if not health_ok:
                    message += f" Warning: {health_msg}"
            
            if is_htmx_request():
                # Return updated status component
                docker_manager = get_docker_manager()
                statuses = get_app_container_statuses(model, app_num, docker_manager)
                return render_template("partials/container_status.html", 
                                     statuses=statuses, model=model, app_num=app_num,
                                     success_message=message)
            else:
                return create_api_response(True, message=message)
        else:
            if is_htmx_request():
                return render_template("partials/error_message.html", error=message)
            return create_api_response(False, error=message)
            
    except Exception as e:
        logger.error(f"Error performing {action} on {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"Docker {action} failed: {str(e)}")
        return create_api_response(False, error=str(e))


@docker_bp.route("/logs/<model>/<int:app_num>")
def view_logs(model: str, app_num: int):
    """View container logs with live updates."""
    try:
        container_type = request.args.get('type', 'backend')  # backend or frontend
        lines = int(request.args.get('lines', 100))
        
        docker_manager = get_docker_manager()
        logs = docker_manager.get_container_logs(model, app_num, container_type, lines)
        
        context = {
            'logs': logs,
            'model': model,
            'app_num': app_num,
            'container_type': container_type
        }
        
        if is_htmx_request():
            return render_template("partials/container_logs.html", **context)
        return render_template("pages/logs.html", **context)
        
    except Exception as e:
        logger.error(f"Error getting logs for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load logs")
        return render_template("pages/error.html", error=str(e))


# ===========================
# ANALYSIS ROUTES
# ===========================

@analysis_bp.route("/")
def analysis_overview():
    """Analysis overview page showing available analysis types."""
    try:
        # Get available analysis tools
        if UnifiedCLIAnalyzer:
            analyzer = UnifiedCLIAnalyzer(Path.cwd())
            available_tools = analyzer.get_available_tools()
        else:
            available_tools = {}
        
        context = {
            'available_tools': available_tools,
            'analysis_types': [t.value for t in ToolCategory] if ToolCategory else [],
            'analyzers_available': UnifiedCLIAnalyzer is not None
        }
        
        return render_htmx_response("analysis_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading analysis overview: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load analysis tools")
        return render_template("pages/error.html", error=str(e))


@analysis_bp.route("/<analysis_type>/<model>/<int:app_num>")
def analysis_details(analysis_type: str, model: str, app_num: int):
    """Show analysis results for a specific type and application."""
    try:
        # Load existing results
        results = load_json_results_for_template(model, app_num, analysis_type)
        
        context = {
            'analysis_type': analysis_type,
            'model': model,
            'app_num': app_num,
            'results': results,
            'has_results': bool(results)
        }
        
        return render_htmx_response("analysis_details.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading {analysis_type} analysis for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load analysis results")
        return render_template("pages/error.html", error=str(e))


@analysis_bp.route("/<analysis_type>/<model>/<int:app_num>/run", methods=["POST"])
def run_analysis(analysis_type: str, model: str, app_num: int):
    """
    Run analysis with HTMX progress updates.
    
    Uses HTMX polling to show progress and return results when complete.
    """
    try:
        # Check if analyzer is available
        if not UnifiedCLIAnalyzer or not ToolCategory:
            if is_htmx_request():
                return render_template("partials/analysis_error.html", 
                                     error="Analysis tools not available")
            return jsonify({'error': 'Analysis tools not available'}), 503
        
        # Validate analysis type
        valid_types = [t.value for t in ToolCategory]
        if analysis_type not in valid_types:
            raise ValueError(f"Invalid analysis type: {analysis_type}")
        
        # Check if analysis is already running
        # Implementation would check running tasks...
        
        # Start analysis in background
        analyzer = UnifiedCLIAnalyzer(Path.cwd())
        
        # Get analysis parameters from form and convert to boolean
        use_all_tools = str(request.form.get('use_all_tools', 'false')).lower() == 'true'
        force_rerun = str(request.form.get('force_rerun', 'false')).lower() == 'true'
        
        # Run analysis
        category = ToolCategory(analysis_type)
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
        
        if is_htmx_request():
            return render_template("partials/analysis_results.html", **context)
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error running {analysis_type} analysis for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"Analysis failed: {str(e)}")
        return create_api_response(False, error=str(e))


# ===========================
# PERFORMANCE TESTING ROUTES
# ===========================

@performance_bp.route("/")
def performance_overview():
    """Performance testing overview."""
    try:
        # Get available performance test configurations
        context = {
            'test_types': ['load', 'stress', 'spike', 'endurance'],
            'default_users': 10,
            'default_duration': 30
        }
        
        return render_htmx_response("performance_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading performance overview: {e}")
        return render_template("pages/error.html", error=str(e))


@performance_bp.route("/<model>/<int:app_num>")
def performance_test_page(model: str, app_num: int):
    """Performance test page for specific application."""
    try:
        app_info = get_app_info(model, app_num)
        if not app_info:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Application not found")
            return redirect(url_for("main.dashboard"))
        
        # Check if performance tester is available
        if not LocustPerformanceTester:
            context = {
                'app': app_info,
                'model': model,
                'app_num': app_num,
                'existing_results': None,
                'has_results': False,
                'performance_available': False,
                'error': 'Performance testing tools not available'
            }
        else:
            # Load existing performance results
            tester = LocustPerformanceTester(Path.cwd() / "performance_reports")
            existing_results = tester.load_performance_results(model, app_num)
            
            context = {
                'app': app_info,
                'model': model,
                'app_num': app_num,
                'existing_results': existing_results,
                'has_results': existing_results is not None,
                'performance_available': True
            }
        
        return render_htmx_response("performance_test.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading performance test page for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load performance test page")
        return redirect(url_for("main.dashboard"))


@performance_bp.route("/<model>/<int:app_num>/run", methods=["POST"])
def run_performance_test(model: str, app_num: int):
    """Run performance test with HTMX progress updates."""
    try:
        # Check if performance tester is available
        if not LocustPerformanceTester:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Performance testing tools not available")
            return jsonify({'error': 'Performance testing tools not available'}), 503
        
        # Get test parameters from form
        user_count = int(request.form.get('user_count', 10))
        spawn_rate = int(request.form.get('spawn_rate', 1))
        duration = int(request.form.get('duration', 30))
        test_type = request.form.get('test_type', 'load')
        
        # Initialize performance tester
        tester = LocustPerformanceTester(Path.cwd() / "performance_reports")
        
        # Run test
        results = tester.run_performance_test(model, app_num)
        
        context = {
            'model': model,
            'app_num': app_num,
            'results': results,
            'success': results.get('success', False)
        }
        
        if is_htmx_request():
            return render_template("partials/performance_results.html", **context)
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error running performance test for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"Performance test failed: {str(e)}")
        return create_api_response(False, error=str(e))


# ===========================
# ZAP SECURITY SCANNING ROUTES
# ===========================

@zap_bp.route("/")
def zap_overview():
    """ZAP scanning overview."""
    try:
        # Check if ZAP scanner is available
        if not create_scanner:
            context = {
                'zap_available': False,
                'scan_types': ['passive', 'active', 'full'],
                'error': 'ZAP scanning tools not available'
            }
        else:
            # Check ZAP availability
            zap_scanner = create_scanner(Path.cwd())
            
            context = {
                'zap_available': zap_scanner.is_available() if zap_scanner else False,
                'scan_types': ['passive', 'active', 'full']
            }
        
        return render_htmx_response("zap_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading ZAP overview: {e}")
        return render_template("pages/error.html", error=str(e))


@zap_bp.route("/<model>/<int:app_num>")
@zap_bp.route("/<model>/<int:app_num>")
def zap_scan_page(model: str, app_num: int):
    """ZAP scan page for specific application."""
    try:
        app_info = get_app_info(model, app_num)
        if not app_info:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Application not found")
            return redirect(url_for("main.dashboard"))
        
        # Check if ZAP scanner is available
        if not create_scanner:
            context = {
                'app': app_info,
                'model': model,
                'app_num': app_num,
                'scan_status': None,
                'zap_available': False,
                'error': 'ZAP scanning tools not available'
            }
        else:
            # Check scan status
            zap_scanner = create_scanner(Path.cwd())
            scan_status = zap_scanner.get_scan_status(model, app_num) if zap_scanner else None
            
            context = {
                'app': app_info,
                'model': model,
                'app_num': app_num,
                'scan_status': scan_status,
                'zap_available': zap_scanner.is_available() if zap_scanner else False
            }
        
        return render_htmx_response("zap_scan.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading ZAP scan page for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load ZAP scan page")
        return render_template("pages/error.html", error=str(e))


@zap_bp.route("/<model>/<int:app_num>/scan", methods=["POST"])
def start_zap_scan(model: str, app_num: int):
    """Start ZAP security scan."""
    try:
        scan_type = request.form.get('scan_type', 'passive')
        
        zap_scanner = create_scanner(Path.cwd())
        results = zap_scanner.scan_app(model, app_num)
        
        context = {
            'model': model,
            'app_num': app_num,
            'results': results,
            'success': results.get('success', False)
        }
        
        if is_htmx_request():
            return render_template("partials/zap_results.html", **context)
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error starting ZAP scan for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"ZAP scan failed: {str(e)}")
        return create_api_response(False, error=str(e))


@zap_bp.route("/<model>/<int:app_num>/status")
def zap_scan_status(model: str, app_num: int):
    """Get ZAP scan status for progress updates."""
    try:
        zap_scanner = create_scanner(Path.cwd())
        status = zap_scanner.get_scan_status(model, app_num)
        
        if is_htmx_request():
            return render_template("partials/zap_status.html", 
                                 status=status, model=model, app_num=app_num)
        return jsonify(status)
        
    except Exception as e:
        logger.error(f"Error getting ZAP scan status for {model}/app{app_num}: {e}")
        return create_api_response(False, error=str(e))


# ===========================
# OPENROUTER ANALYSIS ROUTES
# ===========================

@openrouter_bp.route("/")
def openrouter_overview():
    """OpenRouter analysis overview."""
    try:
        analyzer = OpenRouterAnalyzer()
        
        context = {
            'available_models': analyzer.get_available_models(),
            'api_available': analyzer.is_api_available()
        }
        
        return render_htmx_response("openrouter_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading OpenRouter overview: {e}")
        return render_template("pages/error.html", error=str(e))


@openrouter_bp.route("/<model>/<int:app_num>")
def openrouter_analysis_page(model: str, app_num: int):
    """OpenRouter analysis page for specific application."""
    try:
        app_info = get_app_info(model, app_num)
        if not app_info:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Application not found")
            return redirect(url_for("main.dashboard"))
        
        # Load existing results
        analyzer = OpenRouterAnalyzer()
        existing_results = analyzer.load_results(model, app_num)
        
        # Get requirements for this app
        requirements, app_type = analyzer.get_requirements_for_app(app_num)
        
        context = {
            'app': app_info,
            'model': model,
            'app_num': app_num,
            'requirements': requirements,
            'app_type': app_type,
            'existing_results': existing_results,
            'has_results': existing_results is not None,
            'available_models': analyzer.get_available_models()
        }
        
        return render_htmx_response("openrouter_analysis.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading OpenRouter analysis page for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load analysis page")
        return render_template("pages/error.html", error=str(e))


@openrouter_bp.route("/<model>/<int:app_num>/analyze", methods=["POST"])
def run_openrouter_analysis(model: str, app_num: int):
    """Run OpenRouter requirements analysis."""
    try:
        selected_model = request.form.get('selected_model')
        
        analyzer = OpenRouterAnalyzer()
        if selected_model:
            analyzer.set_preferred_model(selected_model)
        
        # Run analysis
        results = analyzer.analyze_app(model, app_num)
        
        context = {
            'model': model,
            'app_num': app_num,
            'results': results,
            'success': True
        }
        
        if is_htmx_request():
            return render_template("partials/openrouter_results.html", **context)
        return jsonify([result.__dict__ for result in results])
        
    except Exception as e:
        logger.error(f"Error running OpenRouter analysis for {model}/app{app_num}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error=f"Analysis failed: {str(e)}")
        return create_api_response(False, error=str(e))


# ===========================
# BATCH PROCESSING ROUTES
# ===========================

@batch_bp.route("/")
def batch_overview():
    """Batch processing overview and job management."""
    try:
        # Get batch service
        service = get_model_service()
        
        # Get active and recent jobs
        # Implementation would get job status from service
        
        context = {
            'active_jobs': [],  # service.get_active_jobs(),
            'recent_jobs': [],  # service.get_recent_jobs(),
            'available_operations': ['security_analysis', 'performance_test', 'zap_scan']
        }
        
        return render_htmx_response("batch_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading batch overview: {e}")
        return render_template("pages/error.html", error=str(e))


@batch_bp.route("/create", methods=["GET", "POST"])
def create_batch_job():
    """Create new batch job."""
    if request.method == "GET":
        try:
            # Get available models and apps for selection
            all_apps = get_all_apps()
            unique_models = sorted(set(app['model'] for app in all_apps))
            
            context = {
                'models': unique_models,
                'operation_types': ['security_analysis', 'performance_test', 'zap_scan']
            }
            
            return render_htmx_response("batch_create.html", **context)
            
        except Exception as e:
            logger.error(f"Error loading batch job creation form: {e}")
            return render_template("pages/error.html", error=str(e))
    
    else:  # POST
        try:
            # Get form data
            operation_type = request.form.get('operation_type')
            selected_models = request.form.getlist('models')
            app_range_start = int(request.form.get('app_range_start', 1))
            app_range_end = int(request.form.get('app_range_end', 30))
            
            # Create batch job
            # Implementation would create and queue batch job
            
            job_id = f"batch_{int(time.time())}"
            
            if is_htmx_request():
                return render_template("partials/success_message.html", 
                                     message=f"Batch job {job_id} created successfully")
            return create_api_response(True, data={'job_id': job_id})
            
        except Exception as e:
            logger.error(f"Error creating batch job: {e}")
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error=f"Failed to create batch job: {str(e)}")
            return create_api_response(False, error=str(e))


@batch_bp.route("/job/<job_id>")
def batch_job_status(job_id: str):
    """Get batch job status and results."""
    try:
        # Get job status from service
        # Implementation would get job details
        
        job_status = {
            'id': job_id,
            'status': 'running',
            'progress': 65,
            'total_tasks': 100,
            'completed_tasks': 65,
            'failed_tasks': 2,
            'start_time': datetime.now().isoformat()
        }
        
        context = {
            'job': job_status,
            'job_id': job_id
        }
        
        if is_htmx_request():
            return render_template("partials/batch_job_status.html", **context)
        return jsonify(job_status)
        
    except Exception as e:
        logger.error(f"Error getting batch job status for {job_id}: {e}")
        return create_api_response(False, error=str(e))


# ===========================
# GENERATION CONTENT ROUTES
# ===========================

@generation_bp.route("/")
def generation_overview():
    """Generation content overview."""
    try:
        # Get generation lookup service if available
        from core_services import generation_lookup_service
        if generation_lookup_service:
            runs = generation_lookup_service.list_runs()
            stats = generation_lookup_service.get_stats()
        else:
            runs = []
            stats = {}
        
        context = {
            'runs': runs,
            'stats': stats,
            'service_available': generation_lookup_service is not None
        }
        
        return render_htmx_response("generation_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading generation overview: {e}")
        return render_template("pages/error.html", error=str(e))


@generation_bp.route("/run/<timestamp>")
def generation_run_details(timestamp: str):
    """Generation run details."""
    try:
        from core_services import generation_lookup_service
        if not generation_lookup_service:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Generation service not available")
            return render_template("pages/error.html", 
                                 error="Generation service not available")
        
        run_data = generation_lookup_service.get_run(timestamp)
        if not run_data:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="Generation run not found")
            return redirect(url_for("generation.generation_overview"))
        
        context = {
            'run': run_data,
            'timestamp': timestamp
        }
        
        return render_htmx_response("generation_run_details.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading generation run {timestamp}: {e}")
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load generation run")
        return render_template("pages/error.html", error=str(e))


# ===========================
# ERROR HANDLERS
# ===========================

@main_bp.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors."""
    if is_htmx_request():
        return render_template("partials/error_message.html", 
                             error="Page not found"), 404
    return render_template("pages/error.html", 
                         error="Page not found"), 404


@main_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    logger.error(f"Internal server error: {error}")
    if is_htmx_request():
        return render_template("partials/error_message.html", 
                             error="Internal server error"), 500
    return render_template("pages/error.html", 
                         error="Internal server error"), 500


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
        """Format duration in seconds to human readable format."""
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
    
    @app.template_global()
    def is_htmx():
        """Check if current request is from HTMX."""
        return is_htmx_request()
    
    @app.template_global()
    def get_app_url(model, app_num):
        """Generate app URL."""
        try:
            app_info = get_app_info(model, app_num)
            if app_info and 'frontend_port' in app_info:
                return f"http://localhost:{app_info['frontend_port']}"
            return None
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
    app.register_blueprint(zap_bp)
    app.register_blueprint(openrouter_bp)
    app.register_blueprint(batch_bp)
    app.register_blueprint(generation_bp)
    app.register_blueprint(docker_bp)
    
    # Register template helpers
    register_template_helpers(app)
    
    logger.info("All blueprints registered successfully")


# Export blueprints for use in app factory
__all__ = [
    'main_bp', 'api_bp', 'analysis_bp', 'performance_bp', 'zap_bp',
    'openrouter_bp', 'batch_bp', 'generation_bp', 'docker_bp',
    'register_blueprints'
]
