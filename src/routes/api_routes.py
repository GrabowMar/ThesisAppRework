"""
RESTful API Routes
=================

This module contains RESTful API endpoints including:
- Model management API
- Application data API
- System status and settings
- Dashboard data endpoints

Extracted and refactored from the original web_routes.py file.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, request, render_template
from sqlalchemy import func

from .utils import (
    log_performance, ResponseHandler, ServiceLocator, AppDataProvider
)

try:
    from ..extensions import db
    from ..models import ModelCapability, GeneratedApplication
except ImportError:
    from extensions import db
    from models import ModelCapability, GeneratedApplication

# Initialize logger
logger = logging.getLogger(__name__)

# Create blueprints
api_bp = Blueprint("api", __name__, url_prefix="/api/v1")
simple_api_bp = Blueprint("simple_api", __name__, url_prefix="/api")
models_bp = Blueprint("models", __name__, url_prefix="/api/v1/models")


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
        # Check if model exists
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return ResponseHandler.error_response("Model not found", 404)
        
        # Get app info for this model
        apps = []
        for app_num in range(1, 31):
            app_info = AppDataProvider.get_app_for_dashboard(model_slug, app_num)
            apps.append(app_info)
        
        # Return partial template for HTMX or JSON
        if ResponseHandler.is_htmx_request():
            return render_template("partials/model_apps.html", apps=apps, model=model)
        
        return ResponseHandler.success_response(data=apps)
        
    except Exception as e:
        logger.error(f"Error getting model apps: {e}")
        return ResponseHandler.error_response(str(e))


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


@simple_api_bp.route("/dashboard/stats")
def api_dashboard_stats():
    """Get dashboard statistics."""
    try:
        # Get basic statistics with error handling
        try:
            total_models = ModelCapability.query.count()
            total_apps = GeneratedApplication.query.count()
        except Exception as e:
            logger.warning(f"Could not query database: {e}")
            total_models = 0
            total_apps = 0
        
        stats = {
            'total_models': total_models,
            'total_apps': total_apps,
            'running_containers': 0,  # Mock for now
            'error_containers': 0,    # Mock for now
            'total_analyses': 0,      # Mock for now
            'success_rate': 95.5      # Mock for now
        }
        
        return ResponseHandler.success_response(data=stats)
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/sidebar/stats")
def api_sidebar_stats():
    """Get sidebar statistics."""
    try:
        stats = {
            'active_jobs': 0,
            'pending_analyses': 0,
            'system_health': 'good',
            'docker_status': 'running'
        }
        return ResponseHandler.success_response(data=stats)
    except Exception as e:
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/sidebar/system-status")
def api_sidebar_system_status():
    """Get system status for sidebar."""
    try:
        status = {
            'database': 'connected',
            'docker': 'available',
            'services': 'running',
            'memory_usage': 45,
            'cpu_usage': 23
        }
        return ResponseHandler.success_response(data=status)
    except Exception as e:
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/status/<model>/<int:app_num>")
def api_app_status(model: str, app_num: int):
    """Get application status."""
    try:
        app_info = AppDataProvider.get_app_info(model, app_num)
        container_statuses = AppDataProvider.get_container_statuses(model, app_num)
        
        status = {
            'model': model,
            'app_num': app_num,
            'status': app_info.get('status', 'unknown'),
            'containers': container_statuses,
            'last_check': datetime.now().isoformat()
        }
        
        return ResponseHandler.success_response(data=status)
    except Exception as e:
        logger.error(f"App status error: {e}")
        return ResponseHandler.error_response(str(e))


@simple_api_bp.route("/models")
def api_simple_models():
    """Get models for testing interface - simple format."""
    try:
        try:
            models = ModelCapability.query.all()
        except Exception as e:
            logger.warning(f"Could not query models: {e}")
            models = []
        
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
        
        from flask import jsonify
        return jsonify({
            'success': True,
            'data': models_data,
            'total_count': len(models_data)
        })
        
    except Exception as e:
        logger.error(f"Error getting simple models: {e}")
        from flask import jsonify
        return jsonify({'success': False, 'error': str(e)}), 500


# Add the missing get_model_dashboard_stats method to AppDataProvider
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

# Monkey patch the method for compatibility
AppDataProvider.get_model_dashboard_stats = staticmethod(get_model_dashboard_stats)

# Add missing get_app_for_dashboard method
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

# Monkey patch this method too
AppDataProvider.get_app_for_dashboard = staticmethod(get_app_for_dashboard)

# Add missing get_all_apps method
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

# Monkey patch this method as well
AppDataProvider.get_all_apps = staticmethod(get_all_apps)