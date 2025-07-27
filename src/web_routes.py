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

def get_core_services():
    """Get core services module to avoid circular imports."""
    import core_services
    return core_services

def get_model_service():
    """Get model service."""
    return get_core_services().get_model_service()

def get_scan_manager():
    """Get scan manager."""
    return get_core_services().get_scan_manager()

def get_docker_manager():
    """Get docker manager."""
    return get_core_services().get_docker_manager()

def get_all_apps():
    """Get all apps."""
    return get_core_services().get_all_apps()

def get_app_info(model: str, app_num: int):
    """Get app information."""
    return get_core_services().get_app_info(model, app_num)

def get_ai_models():
    """Get AI models."""
    return get_core_services().get_ai_models()

def get_port_config():
    """Get port configuration."""
    return get_core_services().get_port_config()

def get_app_container_statuses(model: str, app_num: int, docker_manager):
    """Get app container statuses."""
    return get_core_services().get_app_container_statuses(model, app_num, docker_manager)

def handle_docker_action(action: str, model: str, app_num: int):
    """Handle docker action."""
    return get_core_services().handle_docker_action(action, model, app_num)

def verify_container_health(docker_manager, model: str, app_num: int, max_retries: int = 15, retry_delay: int = 5):
    """Verify container health."""
    return get_core_services().verify_container_health(docker_manager, model, app_num, max_retries, retry_delay)

def load_json_results_for_template(model: str, app_num: int, analysis_type: Optional[str] = None):
    """Load JSON results for template."""
    return get_core_services().load_json_results_for_template(model, app_num, analysis_type)

def get_available_analysis_results(model: str, app_num: int):
    """Get available analysis results."""
    return get_core_services().get_available_analysis_results(model, app_num)

def get_latest_analysis_timestamp(model: str, app_num: int):
    """Get latest analysis timestamp."""
    return get_core_services().get_latest_analysis_timestamp(model, app_num)

def get_dashboard_data_optimized(docker_manager):
    """Get dashboard data optimized."""
    return get_core_services().get_dashboard_data_optimized(docker_manager)

def create_api_response(success: bool = True, data: Any = None, error: Optional[str] = None, message: Optional[str] = None, code: int = 200):
    """Create API response."""
    return get_core_services().create_api_response(success, data, error, message, code)

def filter_apps(apps, search=None, model=None, status=None):
    """Filter apps."""
    return get_core_services().filter_apps(apps, search, model, status)

def get_cache_stats():
    """Get cache statistics."""
    return get_core_services().get_cache_stats()

def clear_container_cache(model: Optional[str] = None, app_num: Optional[int] = None):
    """Clear container cache."""
    return get_core_services().clear_container_cache(model, app_num)

def create_logger_for_component(component_name: str):
    """Create logger for component."""
    return get_core_services().create_logger_for_component(component_name)

# Batch analysis helper functions
def _create_safe_job_dict(job):
    """Create safe job dict."""
    return get_core_services()._create_safe_job_dict(job)

def _create_safe_task_dict(task):
    """Create safe task dict."""
    return get_core_services()._create_safe_task_dict(task)

def _calculate_progress_stats(tasks):
    """Calculate progress stats."""
    return get_core_services()._calculate_progress_stats(tasks)

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
                return render_template("partials/apps_list.html", **context)
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
            model_name = config['model']
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
        
        return render_template("partials/apps_list.html", **context)
        
    except Exception as e:
        logger.error(f"Error searching apps: {e}")
        return render_template("partials/error_message.html", 
                             error="Search failed")


@api_bp.route("/cache/stats")
def cache_stats():
    """Get cache statistics for monitoring."""
    try:
        stats = get_cache_stats()
        if is_htmx_request():
            return render_template("partials/cache_stats.html", stats=stats)
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return create_api_response(False, error=str(e))


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


# ===========================
# DOCKER MANAGEMENT ROUTES
# ===========================

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
