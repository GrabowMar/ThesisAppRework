"""
Main Application Routes
======================

This module contains the primary application routes including:
- Dashboard and home page
- Model overview and management
- Application detail pages
- Error handling

Extracted and refactored from the original web_routes.py file.
"""

import logging
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, redirect, render_template, request, url_for, flash
from sqlalchemy import func

from .utils import (
    log_performance, ResponseHandler, ServiceLocator, AppDataProvider
)

try:
    from ..extensions import db
    from ..models import ModelCapability, GeneratedApplication, PortConfiguration
except ImportError:
    from extensions import db
    from models import ModelCapability, GeneratedApplication, PortConfiguration

# Initialize logger
logger = logging.getLogger(__name__)

# Create blueprint
main_bp = Blueprint("main", __name__)


# ===========================
# MAIN ROUTES
# ===========================

@main_bp.route("/", endpoint='dashboard')
@log_performance("dashboard_load")
def dashboard():
    """Modern dashboard with expandable model tabs."""
    try:
        logger.info("Loading dashboard with model statistics")
        
        # Safely get models with error handling for missing tables
        try:
            models = ModelCapability.query.all()
        except Exception as e:
            logger.warning(f"Could not query models: {e}")
            models = []
        
        docker_manager = ServiceLocator.get_docker_manager()
        
        # Calculate statistics
        stats = {
            'total_models': len(models),
            'total_apps': len(models) * 30 if models else 0,
            'running_containers': 0,
            'error_containers': 0,
            'total_providers': len(set(m.provider for m in models)) if models else 0,
            'analyzed_apps': 0,
            'performance_tested': 0,
            'docker_health': 'Healthy' if docker_manager else 'Unavailable'
        }
        
        # Sample container status check for efficiency (only if we have models)
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
        return render_template("pages/error.html", 
                             error=str(e), 
                             timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                             error_code=500)


@main_bp.route("/dashboard", endpoint='dashboard_redirect')
def dashboard_redirect():
    """Dashboard page - serve dashboard content directly."""
    # Call the dashboard function directly to avoid redirect
    return dashboard()


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
        
        # Get port information from database with error handling
        port_info = {'frontend': None, 'backend': None}
        try:
            port_config = PortConfiguration.query.filter_by(
                model=decoded_model, 
                app_num=app_num
            ).first()
            
            if port_config:
                port_info = {
                    'frontend': port_config.frontend_port,
                    'backend': port_config.backend_port
                }
        except Exception as e:
            logger.warning(f"Could not query port configuration: {e}")
            # Use fallback port calculation
            port_info = {
                'frontend': 9000 + (app_num * 10),
                'backend': 6000 + (app_num * 10)
            }
        
        # Get generated application info with error handling
        generated_app = None
        try:
            generated_app = GeneratedApplication.query.filter_by(
                model_slug=decoded_model,
                app_number=app_num
            ).first()
        except Exception as e:
            logger.warning(f"Could not query generated application: {e}")
        
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
            from flask import jsonify
            return jsonify({'success': False, 'error': error_str}), 500
    
    return ResponseHandler.error_response("Internal server error", 500)