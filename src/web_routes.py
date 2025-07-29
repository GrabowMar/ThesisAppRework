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
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint, Response, current_app, flash, jsonify, make_response,
    redirect, render_template, request, session, url_for
)

# Initialize logger
logger = logging.getLogger(__name__)

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
    try:
        # Try to get from database
        from models import GeneratedApplication
        apps = []
        db_apps = GeneratedApplication.query.all()
        
        for app in db_apps:
            apps.append({
                'model': app.model_slug.replace('_', '-'),
                'app_num': app.app_number,
                'status': app.container_status or 'unknown',
                'app_type': app.app_type or 'unknown',
                'provider': app.provider or 'unknown'
            })
        
        return apps
    except Exception as e:
        logger.warning(f"Could not get apps from database: {e}")
        # Return minimal test data
        return [
            {'model': 'test-model', 'app_num': 1, 'status': 'unknown', 'app_type': 'test', 'provider': 'test'}
        ]

def get_app_info(model: str, app_num: int):
    """Get app information."""
    try:
        from models import GeneratedApplication
        app = GeneratedApplication.query.filter_by(
            model_slug=model.replace('-', '_'),
            app_number=app_num
        ).first()
        
        if app:
            return {
                'model': model,
                'app_num': app_num,
                'status': app.container_status or 'unknown',
                'app_type': app.app_type or 'unknown',
                'provider': app.provider or 'unknown',
                'has_backend': app.has_backend,
                'has_frontend': app.has_frontend,
                'metadata': app.get_metadata()
            }
    except Exception as e:
        logger.warning(f"Could not get app info from database: {e}")
    
    # Return basic info if not found in database
    return {
        'model': model,
        'app_num': app_num,
        'status': 'unknown',
        'app_type': 'unknown',
        'provider': 'unknown',
        'has_backend': True,
        'has_frontend': True,
        'metadata': {}
    }

def get_ai_models():
    """Get AI models."""
    try:
        from models import ModelCapability
        models = []
        db_models = ModelCapability.query.all()
        
        for model in db_models:
            models.append({
                'id': model.model_id,
                'name': model.model_name,
                'provider': model.provider,
                'canonical_slug': model.canonical_slug,
                'context_window': model.context_window,
                'supports_function_calling': model.supports_function_calling,
                'supports_vision': model.supports_vision
            })
        
        return models
    except Exception as e:
        logger.warning(f"Could not get models from database: {e}")
        return []

def get_port_config(model: Optional[str] = None, app_num: Optional[int] = None):
    """Get port configuration."""
    # Import here to avoid circular import
    try:
        from models import PortConfiguration, GeneratedApplication
        if model and app_num:
            # First try to find by generated application
            app = GeneratedApplication.query.filter_by(
                model_slug=model.replace('-', '_'),
                app_number=app_num
            ).first()
            if app:
                metadata = app.get_metadata()
                ports = metadata.get('ports', {})
                if ports:
                    return {
                        'backend_port': ports.get('backend_port', 6000),
                        'frontend_port': ports.get('frontend_port', 9000)
                    }
            
            # Fallback to port configuration table
            config = PortConfiguration.query.filter_by(
                frontend_port=9051 + (app_num - 1) * 2
            ).first()
            if config:
                return {
                    'backend_port': config.backend_port,
                    'frontend_port': config.frontend_port
                }
    except Exception as e:
        logger.warning(f"Error getting port config: {e}")
    
    # Default ports
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
        is_healthy = statuses.get('backend') == 'running' and statuses.get('frontend') == 'running'
        message = "Containers are running" if is_healthy else "Some containers are not running"
        return is_healthy, message
    return False, "Docker manager not available"

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
        from models import ModelCapability, GeneratedApplication
        
        # Get apps from database
        apps = []
        db_apps = GeneratedApplication.query.all()
        
        for app in db_apps:
            # Get container statuses if docker manager is available
            container_status = 'unknown'
            if docker_manager:
                try:
                    statuses = get_app_container_statuses(
                        app.model_slug.replace('_', '-'),
                        app.app_number,
                        docker_manager
                    )
                    backend_running = statuses.get('backend') == 'running'
                    frontend_running = statuses.get('frontend') == 'running'
                    
                    if backend_running and frontend_running:
                        container_status = 'running'
                    elif backend_running or frontend_running:
                        container_status = 'partial'
                    else:
                        container_status = 'stopped'
                except Exception:
                    container_status = 'unknown'
            
            apps.append({
                'model': app.model_slug.replace('_', '-'),
                'app_num': app.app_number,
                'status': container_status,
                'app_type': app.app_type or 'unknown',
                'provider': app.provider or 'unknown',
                'has_backend': app.has_backend,
                'has_frontend': app.has_frontend,
                'backend_port': 6000 + app.app_number,  # Default calculation
                'frontend_port': 9000 + app.app_number
            })
        
        return {'apps': apps, 'cache_used': False}
    except Exception as e:
        logger.warning(f"Could not get dashboard data: {e}")
        return {'apps': [], 'cache_used': False}

def create_api_response(success: bool = True, data: Any = None, error: Optional[str] = None, 
                       message: Optional[str] = None, code: int = 200, retry_after: Optional[int] = None):
    """
    Create standardized API response with enhanced error handling.
    
    Args:
        success: Whether the operation was successful
        data: Response data
        error: Error message if applicable
        message: Success message if applicable
        code: HTTP status code
        retry_after: Seconds to wait before retrying (for 429, 503 errors)
    """
    response_data = {
        'success': success,
        'data': data,
        'error': error,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    
    # Add retry information for appropriate error codes
    if not success and code in [429, 500, 502, 503, 504]:
        response_data['retryable'] = True
        if retry_after:
            response_data['retry_after'] = retry_after
        else:
            # Default retry delays based on error type
            retry_delays = {429: 60, 500: 30, 502: 60, 503: 60, 504: 120}
            response_data['retry_after'] = retry_delays.get(code, 30)
    else:
        response_data['retryable'] = False
    
    response = jsonify(response_data)
    
    # Add appropriate headers
    if retry_after:
        response.headers['Retry-After'] = str(retry_after)
    
    return response, code

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

def safe_error_template(error_message: str, error_code: int = 500, retry_action: Optional[str] = None):
    """
    Helper function to ensure all error templates include proper error_code and retry functionality.
    
    Args:
        error_message: The error message to display
        error_code: HTTP status code
        retry_action: Optional URL or action for retry button
    """
    from datetime import datetime
    
    context = {
        'error': error_message,
        'error_code': error_code,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'retry_action': retry_action
    }
    
    return render_template("pages/error.html", **context)

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
    """New dashboard with expandable model tabs and Docker integration"""
    try:
        from models import ModelCapability
        from extensions import db
        
        # Get basic statistics for the dashboard
        models = db.session.query(ModelCapability).all()
        docker_manager = get_docker_manager()
        
        total_models = len(models)
        total_apps = total_models * 30  # 30 apps per model
        running_containers = 0
        error_containers = 0
        total_providers = len(set(model.provider for model in models))
        
        # Get Docker stats if available
        if docker_manager:
            for model in models:
                for app_num in range(1, 31):
                    try:
                        statuses = get_app_container_statuses(model.canonical_slug, app_num, docker_manager)
                        backend_status = statuses.get('backend', 'not_found')
                        frontend_status = statuses.get('frontend', 'not_found')
                        
                        if backend_status == 'running' and frontend_status == 'running':
                            running_containers += 1
                        elif backend_status in ['exited', 'dead'] or frontend_status in ['exited', 'dead']:
                            error_containers += 1
                    except Exception:
                        pass
        
        summary_stats = {
            'total_models': total_models,
            'total_apps': total_apps,
            'running_containers': running_containers,
            'error_containers': error_containers,
            'total_providers': total_providers,
            'analyzed_apps': 0,  # Placeholder for analysis data
            'performance_tested': 0,  # Placeholder for performance data
            'docker_health': 'Healthy' if docker_manager else 'Unavailable'
        }
        
        return render_template('pages/dashboard.html', summary_stats=summary_stats)
        
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}", exc_info=True)
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
            'app_info': app_info,  # Fix: template expects app_info not app
            'app': app_info,       # Keep both for backward compatibility
            'statuses': container_statuses,  # Fix: template expects statuses
            'container_statuses': container_statuses,  # Keep both for backward compatibility
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
    """Comprehensive models overview page with detailed model information table."""
    try:
        from models import ModelCapability, GeneratedApplication
        from extensions import db
        from sqlalchemy import func
        from core_services import get_port_config as get_port_config_from_db
        
        # Get search and filter parameters
        search_query = request.args.get('search', '').strip()
        provider_filter = request.args.get('provider', '').strip()
        sort_by = request.args.get('sort', 'model_name')
        
        # Build base query
        query = ModelCapability.query
        
        # Apply search filter
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                ModelCapability.model_name.ilike(search_pattern) |
                ModelCapability.model_id.ilike(search_pattern) |
                ModelCapability.provider.ilike(search_pattern)
            )
        
        # Apply provider filter
        if provider_filter:
            query = query.filter(ModelCapability.provider == provider_filter)
        
        # Apply sorting
        if sort_by == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort_by == 'context_window':
            query = query.order_by(ModelCapability.context_window.desc())
        elif sort_by == 'input_price':
            query = query.order_by(ModelCapability.input_price_per_token.asc())
        elif sort_by == 'output_price':
            query = query.order_by(ModelCapability.output_price_per_token.asc())
        elif sort_by == 'safety_score':
            query = query.order_by(ModelCapability.safety_score.desc())
        elif sort_by == 'cost_efficiency':
            query = query.order_by(ModelCapability.cost_efficiency.desc())
        else:  # default to model_name
            query = query.order_by(ModelCapability.model_name)
        
        models = query.all()
        
        # Get port configuration for app counts
        port_config = get_port_config_from_db()
        app_counts = {}
        for config in port_config:
            if isinstance(config, dict):
                model_name = config.get('model_name')
                if model_name:
                    app_counts[model_name] = app_counts.get(model_name, 0) + 1
        
        # Get generated applications data for additional metrics
        app_stats = db.session.query(
            GeneratedApplication.model_slug,
            func.count(GeneratedApplication.id).label('total_apps'),
            func.count(func.nullif(GeneratedApplication.generation_status, 'pending')).label('generated_apps'),
            func.count(func.nullif(GeneratedApplication.container_status, 'stopped')).label('running_containers')
        ).group_by(GeneratedApplication.model_slug).all()
        
        app_stats_dict = {stat.model_slug: stat for stat in app_stats}
        
        # Get unique providers for filter dropdown
        all_providers = db.session.query(ModelCapability.provider).distinct().order_by(ModelCapability.provider).all()
        providers = [p.provider for p in all_providers]
        
        # Enhance models with additional data
        enhanced_models = []
        for model in models:
            model_data = model.to_dict()
            
            # Add application statistics
            model_slug = model.canonical_slug
            if model_slug in app_stats_dict:
                stat = app_stats_dict[model_slug]
                model_data.update({
                    'total_apps': stat.total_apps,
                    'generated_apps': stat.generated_apps,
                    'running_containers': stat.running_containers
                })
            else:
                model_data.update({
                    'total_apps': app_counts.get(model.canonical_slug, 0),
                    'generated_apps': 0,
                    'running_containers': 0
                })
            
            # Parse capabilities and metadata for display
            capabilities = model.get_capabilities()
            metadata = model.get_metadata()
            
            # Extract quality metrics
            quality_metrics = metadata.get('quality_metrics', {})
            model_data['quality_metrics'] = quality_metrics
            
            # Extract performance metrics
            performance_metrics = metadata.get('performance_metrics', {})
            model_data['performance_metrics'] = performance_metrics
            
            # Extract architecture info
            architecture = metadata.get('architecture', {})
            model_data['architecture'] = architecture
            
            # Calculate capability flags
            model_data['capability_flags'] = {
                'reasoning': capabilities.get('reasoning', False),
                'coding': capabilities.get('coding', False),
                'math': capabilities.get('math', False),
                'creative_writing': capabilities.get('creative_writing', False),
                'analysis': capabilities.get('analysis', False),
                'multilingual': capabilities.get('multilingual', False),
                'long_context': capabilities.get('long_context', False)
            }
            
            enhanced_models.append(model_data)
        
        # Calculate summary statistics
        total_models = len(enhanced_models)
        total_providers = len(providers)
        total_apps = sum(m.get('total_apps', 0) for m in enhanced_models)
        total_running = sum(m.get('running_containers', 0) for m in enhanced_models)
        
        vision_models = sum(1 for m in enhanced_models if m.get('supports_vision'))
        function_calling_models = sum(1 for m in enhanced_models if m.get('supports_function_calling'))
        free_models = sum(1 for m in enhanced_models if m.get('is_free'))
        
        avg_context_window = sum(m.get('context_window', 0) for m in enhanced_models) // max(1, total_models)
        
        summary_stats = {
            'total_models': total_models,
            'total_providers': total_providers,
            'total_apps': total_apps,
            'total_running': total_running,
            'vision_models': vision_models,
            'function_calling_models': function_calling_models,
            'free_models': free_models,
            'avg_context_window': avg_context_window
        }
        
        context = {
            'models': enhanced_models,
            'providers': providers,
            'summary_stats': summary_stats,
            'search_query': search_query,
            'provider_filter': provider_filter,
            'sort_by': sort_by
        }
        
        # Return partial template for HTMX requests
        if is_htmx_request():
            # Check if this is for the models table only
            if request.args.get('partial') == 'table':
                return render_template("partials/models_table.html", **context)
            return render_template("partials/models_content.html", **context)
        
        return render_htmx_response("models_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading models overview: {e}", exc_info=True)
        if is_htmx_request():
            return render_template("partials/error_message.html", 
                                 error="Failed to load models data")
        return safe_error_template(str(e), 500)


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
# NEW DASHBOARD ROUTES
# ===========================

@main_bp.route('/api/dashboard/models')
def api_dashboard_models():
    """HTMX endpoint for models grid data"""
    try:
        from models import ModelCapability
        from extensions import db
        from datetime import datetime
        
        # Get all models with their capabilities
        models = db.session.query(ModelCapability).all()
        docker_manager = get_docker_manager()
        
        # Enhanced models data with Docker stats
        models_data = []
        
        for model in models:
            # Get container stats for this model
            running_containers = 0
            stopped_containers = 0
            error_containers = 0
            
            if docker_manager:
                for app_num in range(1, 31):  # 30 apps per model
                    try:
                        statuses = get_app_container_statuses(model.canonical_slug, app_num, docker_manager)
                        backend_status = statuses.get('backend', 'not_found')
                        frontend_status = statuses.get('frontend', 'not_found')
                        
                        if backend_status == 'running' and frontend_status == 'running':
                            running_containers += 1
                        elif backend_status in ['exited', 'dead'] or frontend_status in ['exited', 'dead']:
                            error_containers += 1
                        else:
                            stopped_containers += 1
                    except Exception:
                        stopped_containers += 1
            else:
                stopped_containers = 30  # All apps assumed stopped if no Docker
            
            model_data = {
                'id': model.id,
                'canonical_slug': model.canonical_slug,
                'model_name': model.model_name,  # Keep consistent with template
                'display_name': model.model_name,
                'provider': model.provider,  # Keep consistent with template  
                'provider_name': model.provider,
                'context_window': model.context_window,
                'max_output_tokens': model.max_output_tokens,
                'input_price_per_token': model.input_price_per_token,
                'output_price_per_token': model.output_price_per_token,
                'supports_function_calling': model.supports_function_calling,
                'supports_vision': model.supports_vision,
                'total_apps': 30,
                'running_containers': running_containers,
                'stopped_containers': stopped_containers,
                'error_containers': error_containers,
                'last_updated': datetime.now()
            }
            models_data.append(model_data)
        
        return render_template('partials/dashboard_models_grid.html', models=models_data)
    
    except Exception as e:
        logger.error(f"Error fetching dashboard models: {e}")
        return f"<div class='error-state'>Error loading models: {str(e)}</div>", 500


@main_bp.route('/api/dashboard/search')
def api_dashboard_search():
    """HTMX endpoint for dashboard search and filtering"""
    try:
        from models import ModelCapability
        from extensions import db
        from datetime import datetime
        
        # Get search parameters
        search_query = request.args.get('search', '').strip()
        provider_filter = request.args.get('filter-provider', '').strip()
        status_filter = request.args.get('filter-status', '').strip()
        
        # Build query
        query = db.session.query(ModelCapability)
        
        # Apply search filter
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                ModelCapability.model_name.ilike(search_pattern) |
                ModelCapability.canonical_slug.ilike(search_pattern) |
                ModelCapability.provider.ilike(search_pattern)
            )
        
        # Apply provider filter
        if provider_filter:
            query = query.filter(ModelCapability.provider.ilike(f"%{provider_filter}%"))
        
        models = query.all()
        
        # Process models data
        models_data = []
        total_apps = 0
        running_apps = 0
        error_apps = 0
        
        for model in models:
            # Count total apps for this model
            model_total_apps = 30
            total_apps += model_total_apps
            
            # Get running apps count (placeholder)
            model_running_apps = 0
            running_apps += model_running_apps
            
            # Apply status filter
            if status_filter:
                if status_filter == 'running' and model_running_apps == 0:
                    continue
                elif status_filter == 'stopped' and model_running_apps > 0:
                    continue
                elif status_filter == 'error':
                    continue  # Implement error detection logic
            
            model_data = {
                'id': model.id,
                'canonical_slug': model.canonical_slug,
                'display_name': model.model_name,
                'provider': model.provider,
                'context_window_size': model.context_window,
                'max_output_tokens': model.max_output_tokens,
                'input_cost_per_mtok': model.input_price_per_token,
                'output_cost_per_mtok': model.output_price_per_token,
                'supports_function_calling': model.supports_function_calling,
                'supports_vision': model.supports_vision,
                'generated_apps': [f'app{i}' for i in range(1, 31)],
                'running_apps_count': model_running_apps,
                'is_available': True,
                'last_analysis': None,
                'status': 'active' if model_running_apps > 0 else 'inactive'
            }
            models_data.append(model_data)
        
        context = {
            'models': models_data,
            'total_apps': total_apps,
            'running_apps': running_apps,
            'error_apps': error_apps,
            'current_time': datetime.now()
        }
        
        return render_template('partials/models_grid.html', **context)
    
    except Exception as e:
        current_app.logger.error(f"Error searching dashboard models: {e}")
        return f"<div class='error-state'>Error searching models: {str(e)}</div>", 500


@main_bp.route('/api/dashboard/refresh-all')
def api_dashboard_refresh_all():
    """HTMX endpoint to refresh all dashboard data"""
    try:
        # This is the same as the models endpoint but could include cache clearing
        return api_dashboard_models()
    except Exception as e:
        current_app.logger.error(f"Error refreshing dashboard: {e}")
        return f"<div class='error-state'>Error refreshing dashboard: {str(e)}</div>", 500


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


@api_bp.route("/models-stats")
def get_models_stats():
    """Get models statistics for the overview page."""
    try:
        # Import the core_services functions
        from core_services import get_ai_models as get_ai_models_from_db
        from core_services import get_port_config as get_port_config_from_db
        
        models = get_ai_models_from_db()
        port_config = get_port_config_from_db()
        
        # Group apps by model
        model_stats = {}
        for config in port_config:
            try:
                model_name = config.get('model_name')
                if not model_name:
                    continue
                    
                if model_name not in model_stats:
                    model_stats[model_name] = {
                        'name': model_name,
                        'app_count': 0,
                        'total_ports': 0
                    }
                model_stats[model_name]['app_count'] += 1
                model_stats[model_name]['total_ports'] += 2  # backend + frontend
            except Exception:
                continue
        
        stats = {
            'total_models': len(model_stats),
            'total_apps': len(port_config),
            'unique_providers': len(set(model.split('_')[0] for model in model_stats.keys())),
            'models_with_apps': len([m for m in model_stats.values() if m['app_count'] > 0])
        }
        
        if is_htmx_request():
            return render_template("partials/models_stats.html", stats=stats)
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Error getting models stats: {e}")
        if is_htmx_request():
            return render_template("partials/models_stats.html", 
                                 stats={'total_models': 0, 'total_apps': 0, 'unique_providers': 0, 'models_with_apps': 0})
        return jsonify({'total_models': 0, 'total_apps': 0, 'unique_providers': 0, 'models_with_apps': 0})


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
            if docker_manager and hasattr(docker_manager, 'client') and docker_manager.client:
                docker_manager.client.ping()
            else:
                docker_healthy = False
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
            if docker_manager and hasattr(docker_manager, 'client') and docker_manager.client:
                docker_manager.client.ping()
            else:
                docker_healthy = False
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
            if docker_manager and hasattr(docker_manager, 'client') and docker_manager.client:
                docker_info = docker_manager.client.info()
                docker_version = docker_manager.client.version()
                docker_available = True
            else:
                docker_info = {}
                docker_version = {}
                docker_available = False
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
        if docker_manager and hasattr(docker_manager, 'get_container_logs'):
            logs = docker_manager.get_container_logs(model, app_num, container_type, lines)
        else:
            logs = f"Docker manager not available or does not support log retrieval"
        
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


@api_bp.route("/models/export")
def export_models_data():
    """Export models data in various formats."""
    try:
        from models import ModelCapability, GeneratedApplication
        from extensions import db
        from sqlalchemy import func
        import csv
        import io
        
        # Get format parameter
        export_format = request.args.get('format', 'json').lower()
        
        # Get search and filter parameters (same as models overview)
        search_query = request.args.get('search', '').strip()
        provider_filter = request.args.get('provider', '').strip()
        sort_by = request.args.get('sort', 'model_name')
        
        # Build query (same logic as models overview)
        query = ModelCapability.query
        
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter(
                ModelCapability.model_name.ilike(search_pattern) |
                ModelCapability.model_id.ilike(search_pattern) |
                ModelCapability.provider.ilike(search_pattern)
            )
        
        if provider_filter:
            query = query.filter(ModelCapability.provider == provider_filter)
        
        # Apply sorting
        if sort_by == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort_by == 'context_window':
            query = query.order_by(ModelCapability.context_window.desc())
        elif sort_by == 'input_price':
            query = query.order_by(ModelCapability.input_price_per_token.asc())
        elif sort_by == 'output_price':
            query = query.order_by(ModelCapability.output_price_per_token.asc())
        elif sort_by == 'safety_score':
            query = query.order_by(ModelCapability.safety_score.desc())
        elif sort_by == 'cost_efficiency':
            query = query.order_by(ModelCapability.cost_efficiency.desc())
        else:  # default to model_name
            query = query.order_by(ModelCapability.model_name)
        
        models = query.all()
        
        # Get application statistics
        app_stats = db.session.query(
            GeneratedApplication.model_slug,
            func.count(GeneratedApplication.id).label('total_apps'),
            func.count(func.nullif(GeneratedApplication.generation_status, 'pending')).label('generated_apps'),
            func.count(func.nullif(GeneratedApplication.container_status, 'stopped')).label('running_containers')
        ).group_by(GeneratedApplication.model_slug).all()
        
        app_stats_dict = {stat.model_slug: stat for stat in app_stats}
        
        # Prepare export data
        export_data = []
        for model in models:
            model_data = model.to_dict()
            
            # Add application statistics
            model_slug = model.canonical_slug
            if model_slug in app_stats_dict:
                stat = app_stats_dict[model_slug]
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
            
            # Parse capabilities and metadata for flat export
            capabilities = model.get_capabilities()
            metadata = model.get_metadata()
            quality_metrics = metadata.get('quality_metrics', {})
            architecture = metadata.get('architecture', {})
            
            # Flatten for export
            model_data.update({
                'supports_reasoning': capabilities.get('reasoning', False),
                'supports_coding': capabilities.get('coding', False),
                'supports_math': capabilities.get('math', False),
                'supports_creative_writing': capabilities.get('creative_writing', False),
                'supports_analysis': capabilities.get('analysis', False),
                'supports_multilingual': capabilities.get('multilingual', False),
                'supports_long_context': capabilities.get('long_context', False),
                'quality_helpfulness': quality_metrics.get('helpfulness'),
                'quality_accuracy': quality_metrics.get('accuracy'),
                'quality_coherence': quality_metrics.get('coherence'),
                'quality_creativity': quality_metrics.get('creativity'),
                'quality_instruction_following': quality_metrics.get('instruction_following'),
                'quality_safety': quality_metrics.get('safety'),
                'architecture_tokenizer': architecture.get('tokenizer'),
                'architecture_parameter_count': architecture.get('parameter_count'),
                'architecture_training_cutoff': architecture.get('training_cutoff')
            })
            
            export_data.append(model_data)
        
        # Generate response based on format
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if export_format == 'csv':
            # CSV Export
            output = io.StringIO()
            if export_data:
                # Define CSV fields
                csv_fields = [
                    'model_id', 'model_name', 'canonical_slug', 'provider',
                    'is_free', 'context_window', 'max_output_tokens',
                    'supports_function_calling', 'supports_vision', 'supports_streaming', 'supports_json_mode',
                    'input_price_per_token', 'output_price_per_token',
                    'cost_efficiency', 'safety_score',
                    'total_apps', 'generated_apps', 'running_containers',
                    'supports_reasoning', 'supports_coding', 'supports_math',
                    'supports_creative_writing', 'supports_analysis', 'supports_multilingual', 'supports_long_context',
                    'quality_helpfulness', 'quality_accuracy', 'quality_coherence',
                    'quality_creativity', 'quality_instruction_following', 'quality_safety',
                    'architecture_tokenizer', 'architecture_parameter_count', 'architecture_training_cutoff',
                    'created_at', 'updated_at'
                ]
                
                writer = csv.DictWriter(output, fieldnames=csv_fields, extrasaction='ignore')
                writer.writeheader()
                for row in export_data:
                    writer.writerow(row)
            
            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=models_export_{timestamp}.csv'
            return response
            
        else:  # JSON format (default)
            export_result = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'total_models': len(export_data),
                    'filters_applied': {
                        'search': search_query,
                        'provider': provider_filter,
                        'sort_by': sort_by
                    }
                },
                'models': export_data
            }
            
            response = make_response(json.dumps(export_result, indent=2, default=str))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=models_export_{timestamp}.json'
            return response
            
    except Exception as e:
        logger.error(f"Error exporting models data: {e}")
        return jsonify({'error': str(e)}), 500


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
        
        if not create_scanner:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="ZAP scanner not available")
            return jsonify({'error': 'ZAP scanner not available'}), 503
        
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
        if not create_scanner:
            return jsonify({'error': 'ZAP scanner not available'}), 503
        
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
        if not OpenRouterAnalyzer:
            context = {
                'available_models': [],
                'api_available': False,
                'error': 'OpenRouter analyzer not available'
            }
        else:
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
        if not OpenRouterAnalyzer:
            existing_results = None
            requirements, app_type = [], "unknown"
            openrouter_available = False
            available_models = []
        else:
            analyzer = OpenRouterAnalyzer()
            existing_results = analyzer.load_results(model, app_num)
            
            # Get requirements for this app
            requirements, app_type = analyzer.get_requirements_for_app(app_num)
            openrouter_available = True
            available_models = analyzer.get_available_models()
        
        context = {
            'app': app_info,
            'model': model,
            'app_num': app_num,
            'requirements': requirements,
            'app_type': app_type,
            'existing_results': existing_results,
            'has_results': existing_results is not None,
            'openrouter_available': openrouter_available,
            'available_models': available_models
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
        
        if not OpenRouterAnalyzer:
            if is_htmx_request():
                return render_template("partials/error_message.html", 
                                     error="OpenRouter analyzer not available")
            return jsonify({'error': 'OpenRouter analyzer not available'}), 503
        
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
        # Get batch service from app
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            logger.warning("Batch service not available")
            return render_template("pages/error.html", error="Batch service not available")
        
        # Get all jobs and statistics
        jobs = batch_service.get_all_jobs()
        job_stats = batch_service.get_job_stats()
        
        # Convert jobs to dict format for template
        jobs_data = [job.to_dict() for job in jobs]
        
        context = {
            'jobs': jobs_data,
            'job_stats': job_stats,
            'page_title': 'Batch Analysis Management'
        }
        
        return render_template("pages/batch_overview.html", **context)
        
    except Exception as e:
        logger.error(f"Error loading batch overview: {e}")
        return render_template("pages/error.html", error=str(e))


@batch_bp.route("/create", methods=["GET", "POST"])
def create_batch_job():
    """Create new batch job."""
    if request.method == "GET":
        try:
            # Get available models from database
            from models import ModelCapability
            available_models = ModelCapability.query.all()
            
            context = {
                'available_models': available_models,
                'page_title': 'Create Batch Job'
            }
            
            if is_htmx_request():
                return render_template("partials/batch_create_form.html", **context)
            return render_template("pages/batch_create.html", **context)
            
        except Exception as e:
            logger.error(f"Error loading batch job creation form: {e}")
            return render_template("pages/error.html", error=str(e))
    
    else:  # POST
        try:
            # Get form data
            job_name = request.form.get('name', '').strip()
            job_description = request.form.get('description', '').strip()
            analysis_types = request.form.getlist('analysis_types')
            selected_models = request.form.getlist('models')
            app_range = request.form.get('app_range', '').strip()
            auto_start = bool(request.form.get('auto_start'))
            
            # Validate required fields
            if not job_name:
                return create_api_response(False, error="Job name is required")
            if not analysis_types:
                return create_api_response(False, error="At least one analysis type must be selected")
            if not selected_models:
                return create_api_response(False, error="At least one model must be selected")
            if not app_range:
                return create_api_response(False, error="Application range is required")
            
            # Get batch service
            batch_service = getattr(current_app, 'batch_service', None)
            if not batch_service:
                return create_api_response(False, error="Batch service not available")
            
            # Create batch job
            job = batch_service.create_job(
                name=job_name,
                description=job_description,
                analysis_types=analysis_types,
                models=selected_models,
                app_range_str=app_range,
                auto_start=auto_start
            )
            
            logger.info(f"Created batch job {job.id}: {job_name}")
            
            return create_api_response(True, data={
                'job_id': job.id,
                'message': f'Batch job "{job_name}" created successfully'
            })
            
        except Exception as e:
            logger.error(f"Error creating batch job: {e}")
            return create_api_response(False, error=str(e))


@batch_bp.route("/job/<job_id>")
def batch_job_detail(job_id: str):
    """View detailed batch job information."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return render_template("pages/error.html", error="Batch service not available")
        
        # Get job and tasks
        job = batch_service.get_job(job_id)
        if not job:
            return render_template("pages/error.html", error="Job not found"), 404
        
        tasks = batch_service.get_job_tasks(job_id)
        
        # Calculate task statistics
        task_stats = {
            'total': len(tasks),
            'pending': len([t for t in tasks if t.status.value == 'pending']),
            'running': len([t for t in tasks if t.status.value == 'running']),
            'completed': len([t for t in tasks if t.status.value == 'completed']),
            'failed': len([t for t in tasks if t.status.value == 'failed']),
            'cancelled': len([t for t in tasks if t.status.value == 'cancelled']),
        }
        
        context = {
            'job': job.to_dict(),
            'tasks': [task.to_dict() for task in tasks],
            'task_stats': task_stats,
            'page_title': f'Job: {job.name}'
        }
        
        return render_template("pages/batch_job_detail.html", **context)
        
    except Exception as e:
        logger.error(f"Error getting batch job details for {job_id}: {e}")
        return render_template("pages/error.html", error=str(e))


@batch_bp.route("/job/<job_id>/status")
def batch_job_status_api(job_id: str):
    """Get batch job status via API."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return create_api_response(False, error="Batch service not available")
        
        # Get job and tasks
        job = batch_service.get_job(job_id)
        if not job:
            return create_api_response(False, error="Job not found")
        
        tasks = batch_service.get_job_tasks(job_id)
        
        return create_api_response(True, data={
            'job': job.to_dict(),
            'tasks': [task.to_dict() for task in tasks]
        })
        
    except Exception as e:
        logger.error(f"Error getting batch job status for {job_id}: {e}")
        return create_api_response(False, error=str(e))


@batch_bp.route("/job/<job_id>/cancel", methods=["POST"])
def cancel_batch_job(job_id: str):
    """Cancel a running batch job."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return create_api_response(False, error="Batch service not available")
        
        # Cancel job
        success = batch_service.cancel_job(job_id)
        
        if success:
            logger.info(f"Cancelled batch job {job_id}")
            return create_api_response(True, message="Job cancelled successfully")
        else:
            return create_api_response(False, error="Failed to cancel job or job not found")
        
    except Exception as e:
        logger.error(f"Error cancelling batch job {job_id}: {e}")
        return create_api_response(False, error=str(e))


@batch_bp.route("/job/<job_id>/archive", methods=["POST"])
def archive_batch_job(job_id: str):
    """Archive a completed batch job."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return create_api_response(False, error="Batch service not available")
        
        # Archive job
        success = batch_service.archive_job(job_id)
        
        if success:
            logger.info(f"Archived batch job {job_id}")
            return create_api_response(True, message="Job archived successfully")
        else:
            return create_api_response(False, error="Failed to archive job or job not found")
        
    except Exception as e:
        logger.error(f"Error archiving batch job {job_id}: {e}")
        return create_api_response(False, error=str(e))


@batch_bp.route("/job/<job_id>/delete", methods=["DELETE"])
def delete_batch_job(job_id: str):
    """Delete an archived batch job."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return create_api_response(False, error="Batch service not available")
        
        # Delete job
        success = batch_service.delete_job(job_id)
        
        if success:
            logger.info(f"Deleted batch job {job_id}")
            return create_api_response(True, message="Job deleted successfully")
        else:
            return create_api_response(False, error="Failed to delete job or job not found")
        
    except Exception as e:
        logger.error(f"Error deleting batch job {job_id}: {e}")
        return create_api_response(False, error=str(e))


@batch_bp.route("/api/jobs")
def get_batch_jobs_api():
    """Get all batch jobs via API for real-time updates."""
    try:
        # Get batch service
        batch_service = getattr(current_app, 'batch_service', None)
        if not batch_service:
            return create_api_response(False, error="Batch service not available")
        
        # Get jobs and stats
        jobs = batch_service.get_all_jobs()
        job_stats = batch_service.get_job_stats()
        
        return create_api_response(True, data={
            'jobs': [job.to_dict() for job in jobs],
            'stats': job_stats
        })
        
    except Exception as e:
        logger.error(f"Error getting batch jobs via API: {e}")
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
# NEW DASHBOARD API ROUTES
# ===========================

@main_bp.route('/api/model/<model_slug>/apps')
def api_model_apps(model_slug):
    """Get applications for a specific model"""
    try:
        from models import ModelCapability
        from extensions import db
        
        # Get model
        model = db.session.query(ModelCapability).filter_by(canonical_slug=model_slug).first()
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        docker_manager = get_docker_manager()
        apps_data = []
        
        # Generate app data for 30 applications
        for app_num in range(1, 31):
            # Get container status
            status = 'stopped'
            frontend_status = 'stopped'
            backend_status = 'stopped'
            database_status = 'stopped'
            
            if docker_manager:
                try:
                    statuses = get_app_container_statuses(model_slug, app_num, docker_manager)
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
            
            # Get port configuration
            port_config = get_port_config(model_slug, app_num)
            
            # App type mapping
            app_types = {
                1: "Login System", 2: "Chat Application", 3: "Feedback System", 4: "Blog Platform",
                5: "E-commerce Cart", 6: "Note Taking", 7: "File Upload", 8: "Forum", 9: "CRUD Manager",
                10: "Microblog", 11: "Polling System", 12: "Reservation System", 13: "Photo Gallery",
                14: "Cloud Storage", 15: "Kanban Board", 16: "IoT Dashboard", 17: "Fitness Tracker",
                18: "Wiki", 19: "Crypto Wallet", 20: "Mapping App", 21: "Recipe Manager",
                22: "Learning Platform", 23: "Finance Tracker", 24: "Networking Tool", 25: "Health Monitor",
                26: "Environment Tracker", 27: "Team Management", 28: "Art Portfolio", 29: "Event Planner",
                30: "Research Collaboration"
            }
            
            app_data = {
                'app_number': app_num,
                'app_name': f"App {app_num}",
                'app_type': app_types.get(app_num, 'Unknown'),
                'description': f"{app_types.get(app_num, 'Unknown')} - Generated by {model.model_name}",
                'status': status,
                'frontend_port': port_config.get('frontend_port', 9050 + (app_num * 2)),
                'backend_port': port_config.get('backend_port', 6050 + (app_num * 2)),
                'containers': {
                    'frontend_status': frontend_status,
                    'backend_status': backend_status,
                    'database_status': database_status
                },
                'created_at': None,  # Could add actual creation dates
                'last_analyzed': None,  # Could add analysis data
                'analysis_summary': None,  # Could add analysis summaries
                'performance_summary': None  # Could add performance data
            }
            apps_data.append(app_data)
        
        return render_template('partials/dashboard_model_apps.html', 
                             apps=apps_data, 
                             model_slug=model_slug)
        
    except Exception as e:
        logger.error(f"Error loading apps for model {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/model/<model_slug>/details')
def api_model_details(model_slug):
    """Get detailed information about a model"""
    try:
        from models import ModelCapability
        from extensions import db
        
        model = db.session.query(ModelCapability).filter_by(canonical_slug=model_slug).first()
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        # Get container statistics
        docker_manager = get_docker_manager()
        running_count = 0
        stopped_count = 0
        error_count = 0
        
        if docker_manager:
            for app_num in range(1, 31):
                try:
                    statuses = get_app_container_statuses(model_slug, app_num, docker_manager)
                    backend_status = statuses.get('backend', 'not_found')
                    frontend_status = statuses.get('frontend', 'not_found')
                    
                    if backend_status == 'running' and frontend_status == 'running':
                        running_count += 1
                    elif backend_status in ['exited', 'dead'] or frontend_status in ['exited', 'dead']:
                        error_count += 1
                    else:
                        stopped_count += 1
                except Exception:
                    stopped_count += 1
        else:
            stopped_count = 30
        
        return render_template('partials/model_details_content.html', 
                             model=model,
                             running_count=running_count,
                             stopped_count=stopped_count,
                             error_count=error_count)
        
    except Exception as e:
        logger.error(f"Error loading model details for {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/model/<model_slug>/stats')
def api_model_stats(model_slug):
    """Get real-time statistics for a model"""
    try:
        docker_manager = get_docker_manager()
        running_count = 0
        stopped_count = 0
        error_count = 0
        
        if docker_manager:
            for app_num in range(1, 31):
                try:
                    statuses = get_app_container_statuses(model_slug, app_num, docker_manager)
                    backend_status = statuses.get('backend', 'not_found')
                    frontend_status = statuses.get('frontend', 'not_found')
                    
                    if backend_status == 'running' and frontend_status == 'running':
                        running_count += 1
                    elif backend_status in ['exited', 'dead'] or frontend_status in ['exited', 'dead']:
                        error_count += 1
                    else:
                        stopped_count += 1
                except Exception:
                    stopped_count += 1
        else:
            stopped_count = 30
        
        return jsonify({
            'running': running_count,
            'stopped': stopped_count,
            'error': error_count,
            'total': 30
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main_bp.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Get dashboard summary statistics"""
    try:
        from models import ModelCapability
        from extensions import db
        
        models = db.session.query(ModelCapability).all()
        docker_manager = get_docker_manager()
        
        total_models = len(models)
        total_apps = total_models * 30
        running_containers = 0
        error_containers = 0
        analyzed_apps = 0
        
        if docker_manager:
            for model in models:
                for app_num in range(1, 31):
                    try:
                        statuses = get_app_container_statuses(model.canonical_slug, app_num, docker_manager)
                        if statuses.get('backend') == 'running' and statuses.get('frontend') == 'running':
                            running_containers += 1
                        elif statuses.get('backend') in ['exited', 'dead'] or statuses.get('frontend') in ['exited', 'dead']:
                            error_containers += 1
                    except Exception:
                        pass
        
        stats = {
            'total_models': total_models,
            'total_apps': total_apps,
            'running_containers': running_containers,
            'error_containers': error_containers,
            'total_providers': len(set(model.provider for model in models)),
            'analyzed_apps': analyzed_apps,
            'performance_tested': 0,
            'docker_health': 'Healthy' if docker_manager else 'Unavailable'
        }
        
        return jsonify(stats)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Container control routes
@main_bp.route('/api/containers/<model_slug>/<int:app_num>/start', methods=['POST'])
def api_start_container(model_slug, app_num):
    """Start containers for a specific app"""
    try:
        result = handle_docker_action('start', model_slug, app_num)
        if result.get('success'):
            # Return updated single app card
            app_data = get_app_data(model_slug, app_num)
            return render_template('partials/single_app_card.html', 
                                 app=app_data, 
                                 model_slug=model_slug)
        else:
            return f'<div class="alert alert-danger">Error: {result.get("error", "Failed to start containers")}</div>', 500
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 500

@main_bp.route('/api/containers/<model_slug>/<int:app_num>/stop', methods=['POST'])
def api_stop_container(model_slug, app_num):
    """Stop containers for a specific app"""
    try:
        result = handle_docker_action('stop', model_slug, app_num)
        if result.get('success'):
            # Return updated single app card
            app_data = get_app_data(model_slug, app_num)
            return render_template('partials/single_app_card.html', 
                                 app=app_data, 
                                 model_slug=model_slug)
        else:
            return f'<div class="alert alert-danger">Error: {result.get("error", "Failed to stop containers")}</div>', 500
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 500

@main_bp.route('/api/containers/<model_slug>/<int:app_num>/restart', methods=['POST'])
def api_restart_container(model_slug, app_num):
    """Restart containers for a specific app"""
    try:
        result = handle_docker_action('restart', model_slug, app_num)
        if result.get('success'):
            # Return updated single app card
            app_data = get_app_data(model_slug, app_num)
            return render_template('partials/single_app_card.html', 
                                 app=app_data, 
                                 model_slug=model_slug)
        else:
            return f'<div class="alert alert-danger">Error: {result.get("error", "Failed to restart containers")}</div>', 500
    except Exception as e:
        return f'<div class="alert alert-danger">Error: {str(e)}</div>', 500

@main_bp.route('/api/containers/<model_slug>/<int:app_num>/logs')
def api_container_logs(model_slug, app_num):
    """Get container logs for a specific app"""
    try:
        docker_manager = get_docker_manager()
        if not docker_manager:
            return "Docker manager not available", 500
        
        # Get logs from both containers
        backend_name = f"{model_slug}_app{app_num}_backend"
        frontend_name = f"{model_slug}_app{app_num}_frontend"
        
        backend_logs = docker_manager.get_container_logs(backend_name) or "No backend logs available"
        frontend_logs = docker_manager.get_container_logs(frontend_name) or "No frontend logs available"
        
        logs_content = f"""
        <div class="logs-container">
            <div class="logs-section">
                <h4>Backend Logs ({backend_name})</h4>
                <pre class="logs-content">{backend_logs}</pre>
            </div>
            <div class="logs-section">
                <h4>Frontend Logs ({frontend_name})</h4>
                <pre class="logs-content">{frontend_logs}</pre>
            </div>
        </div>
        """
        
        return logs_content
        
    except Exception as e:
        return f"<div class='error'>Error fetching logs: {str(e)}</div>", 500

def get_app_data(model_slug, app_num):
    """Helper function to get complete app data for dashboard"""
    try:
        docker_manager = get_docker_manager()
        
        # Get container status
        status = 'stopped'
        frontend_status = 'stopped'
        backend_status = 'stopped'
        database_status = 'stopped'
        
        if docker_manager:
            try:
                statuses = get_app_container_statuses(model_slug, app_num, docker_manager)
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
        
        # Get port configuration
        port_config = get_port_config(model_slug, app_num)
        
        # App type mapping
        app_types = {
            1: "Login System", 2: "Chat Application", 3: "Feedback System", 4: "Blog Platform",
            5: "E-commerce Cart", 6: "Note Taking", 7: "File Upload", 8: "Forum", 9: "CRUD Manager",
            10: "Microblog", 11: "Polling System", 12: "Reservation System", 13: "Photo Gallery",
            14: "Cloud Storage", 15: "Kanban Board", 16: "IoT Dashboard", 17: "Fitness Tracker",
            18: "Wiki", 19: "Crypto Wallet", 20: "Mapping App", 21: "Recipe Manager",
            22: "Learning Platform", 23: "Finance Tracker", 24: "Networking Tool", 25: "Health Monitor",
            26: "Environment Tracker", 27: "Team Management", 28: "Art Portfolio", 29: "Event Planner",
            30: "Research Collaboration"
        }
        
        return {
            'app_number': app_num,
            'app_name': f"App {app_num}",
            'app_type': app_types.get(app_num, 'Unknown'),
            'description': f"{app_types.get(app_num, 'Unknown')} - Generated by {model_slug}",
            'status': status,
            'frontend_port': port_config.get('frontend_port', 9050 + (app_num * 2)),
            'backend_port': port_config.get('backend_port', 6050 + (app_num * 2)),
            'containers': {
                'frontend_status': frontend_status,
                'backend_status': backend_status,
                'database_status': database_status
            },
            'created_at': None,
            'last_analyzed': None,
            'analysis_summary': None,
            'performance_summary': None
        }
    except Exception as e:
        logger.error(f"Error getting app data for {model_slug}/app{app_num}: {e}")
        return {
            'app_number': app_num,
            'app_name': f"App {app_num}",
            'app_type': 'Unknown',
            'description': 'Error loading app data',
            'status': 'error',
            'frontend_port': 9050 + (app_num * 2),
            'backend_port': 6050 + (app_num * 2),
            'containers': {
                'frontend_status': 'error',
                'backend_status': 'error',
                'database_status': 'error'
            },
            'created_at': None,
            'last_analyzed': None,
            'analysis_summary': None,
            'performance_summary': None
        }


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
