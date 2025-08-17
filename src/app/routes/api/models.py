"""
Models API Routes
================

API endpoints for AI model management and information.
"""

import logging
from flask import jsonify, render_template, request

from ..response_utils import json_success, handle_exceptions

from . import api_bp
from ...models import ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest
from ...extensions import db

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/models')
@handle_exceptions(logger_override=logger)
def api_models():
    """API endpoint: Get all models (standardized envelope)."""
    models = ModelCapability.query.all()
    data = [{
        'model_id': model.model_id,
        'canonical_slug': model.canonical_slug,
        'provider': model.provider,
        'model_name': model.model_name,
        'capabilities': model.get_capabilities()
    } for model in models]
    return json_success(data, message="Models fetched")


@api_bp.route('/models/<model_slug>/apps')
@handle_exceptions(logger_override=logger)
def api_model_apps(model_slug):
    """API endpoint: Get applications for a model (standardized envelope)."""
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
    data = [{
        'app_id': app.id,
        'app_number': app.app_number,
        'model_slug': app.model_slug,
        'provider': app.provider,
        'created_at': app.created_at.isoformat() if app.created_at else None
    } for app in apps]
    return json_success(data, message="Applications fetched")


@api_bp.route('/models/list')
def api_models_list():
    """API endpoint: Get models list."""
    try:
        models = ModelCapability.query.all()
        return jsonify([model.to_dict() for model in models])
    except Exception as e:
        logger.error(f"Error getting models list: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/list-options')
def api_models_list_options():
    """HTMX endpoint: Render <option> list for model selects.

    Returns HTML <option> tags for use in selects. Includes an "All Models" placeholder.
    """
    try:
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        return render_template('partials/models/_model_options.html', models=models)
    except Exception as e:
        logger.error(f"Error rendering model options: {e}")
        # Minimal safe fallback options
        return '<option value="">All Models</option>', 200


@api_bp.route('/models/stats/total')
def api_models_stats_total():
    """API endpoint: Get total models count."""
    try:
        count = ModelCapability.query.count()
        return jsonify({'total': count})
    except Exception as e:
        logger.error(f"Error getting models total: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/stats/providers')
def api_models_stats_providers():
    """API endpoint: Get provider statistics."""
    try:
        from ...extensions import db
        from sqlalchemy import func
        
        provider_stats = db.session.query(
            ModelCapability.provider,
            func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()
        
        return jsonify([{
            'provider': provider,
            'count': count
        } for provider, count in provider_stats])
    except Exception as e:
        logger.error(f"Error getting provider stats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/providers')
def api_models_providers():
    """API endpoint: Get unique providers."""
    try:
        from ...extensions import db
        providers = db.session.query(ModelCapability.provider.distinct()).all()
        return jsonify([p[0] for p in providers if p[0]])
    except Exception as e:
        logger.error(f"Error getting providers: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# MODELS VIEW SUPPORT ENDPOINTS EXPECTED BY TEMPLATES
# =================================================================

@api_bp.route('/models/all')
def api_models_all():
    """Return models and simple statistics for Models Overview page.

    This matches the JS expectations in templates/views/models/overview.html.
    """
    try:
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        # Map to the fields referenced by the page's JS
        def map_model(m: ModelCapability):
            caps = m.get_capabilities() or {}
            # Derive some fields with safe defaults
            return {
                'slug': m.canonical_slug,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/img/providers/default.png',
                'capabilities': caps.get('capabilities') or list(caps.keys()) or [],
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': (m.get_metadata() or {}).get('description')
            }

        models_list = [map_model(m) for m in models]
        providers = {m.provider for m in models}
        stats = {
            'total_models': len(models_list),
            'active_models': len(models_list),
            'unique_providers': len(providers),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in models_list) / max(len(models_list), 1), 6)
        }
        return jsonify({'models': models_list, 'statistics': stats})
    except Exception as e:
        logger.error(f"Error building models/all payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


@api_bp.route('/models/grid')
def api_models_grid_fragment():
    """Render the models grid fragment used by the Models Overview page."""
    try:
        # Simple fetch without filters for now; can be extended to read request.args
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # Transform for fragment expected fields
        items = []
        for m in models:
            caps = m.get_capabilities() or {}
            items.append({
                'slug': m.canonical_slug,
                'display_name': m.model_name,
                'name': m.model_name,
                'provider': m.provider,
                'status': 'active',
                'capabilities': caps.get('capabilities') or list(caps.keys()) or [],
                'context_length': m.context_window or 0,
                'max_tokens': m.max_output_tokens or 0,
                'pricing': {
                    'input_cost': (m.input_price_per_token or 0.0) * 1000,
                    'output_cost': (m.output_price_per_token or 0.0) * 1000,
                },
                'statistics': {
                    'total_analyses': db.session.query(SecurityAnalysis).join(GeneratedApplication, SecurityAnalysis.application_id == GeneratedApplication.id).filter(GeneratedApplication.model_slug == m.canonical_slug).count()
                }
            })

        context = {
            'models': items,
            'total_models': len(items),
            'filters_applied': False,
            'active_filters': {},
            'query_params': ''
        }
        return render_template('fragments/api/model-grid.html', **context)
    except Exception as e:
        logger.error(f"Error rendering models grid fragment: {e}")
        return render_template('fragments/api/model-grid.html', models=[], total_models=0, filters_applied=False, active_filters={}, query_params='')


@api_bp.route('/models/filtered')
def api_models_filtered():
    """Return filtered models list matching the structure used by /models/all.

    Supports query params: search, provider, capability, price, status, context, size, release, specialization
    """
    try:
        q = ModelCapability.query
        search = request.args.get('search')
        provider = request.args.get('provider')

        if provider:
            q = q.filter(ModelCapability.provider == provider)
        if search:
            like = f"%{search}%"
            q = q.filter((ModelCapability.model_name.ilike(like)) | (ModelCapability.provider.ilike(like)))

        models = q.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        def map_model(m: ModelCapability):
            caps = m.get_capabilities() or {}
            return {
                'slug': m.canonical_slug,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/img/providers/default.png',
                'capabilities': caps.get('capabilities') or list(caps.keys()) or [],
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': (m.get_metadata() or {}).get('description')
            }

        models_list = [map_model(m) for m in models]
        providers = {m.provider for m in models}
        stats = {
            'total_models': len(models_list),
            'active_models': len(models_list),
            'unique_providers': len(providers),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in models_list) / max(len(models_list), 1), 6)
        }
        return jsonify({'models': models_list, 'statistics': stats})
    except Exception as e:
        logger.error(f"Error building models/filtered payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})
# =================================================================
# MODEL CONTAINER AND STATUS ENDPOINTS
# =================================================================

@api_bp.route('/model/<model_slug>/container-status')
def model_container_status(model_slug):
    """Get container status for model applications."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        
        status_summary = {
            'total_apps': len(apps),
            'running': sum(1 for app in apps if app.container_status == 'running'),
            'stopped': sum(1 for app in apps if app.container_status == 'stopped'),
            'error': sum(1 for app in apps if app.container_status == 'error'),
            'unknown': sum(1 for app in apps if app.container_status == 'unknown'),
            'applications': [{
                'app_id': app.id,
                'app_number': app.app_number,
                'status': app.container_status,
                'has_backend': app.has_backend,
                'has_frontend': app.has_frontend
            } for app in apps]
        }
        
        return jsonify(status_summary)
    except Exception as e:
        logger.error(f"Error getting container status for model {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/model/<model_slug>/running-count')
def model_running_count(model_slug):
    """Get count of running containers for a model."""
    try:
        running_count = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            container_status='running'
        ).count()
        
        return jsonify({'running_count': running_count})
    except Exception as e:
        logger.error(f"Error getting running count for model {model_slug}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/app/<model_slug>/<int:app_num>/status')
def app_status(model_slug, app_num):
    """Get specific application status."""
    try:
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_num
        ).first()
        
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        return jsonify({
            'app_id': app.id,
            'model_slug': app.model_slug,
            'app_number': app.app_number,
            'status': app.container_status,
            'generation_status': app.generation_status.value if app.generation_status else None,
            'has_backend': app.has_backend,
            'has_frontend': app.has_frontend,
            'has_docker_compose': app.has_docker_compose,
            'backend_framework': app.backend_framework,
            'frontend_framework': app.frontend_framework,
            'created_at': app.created_at.isoformat() if app.created_at else None,
            'updated_at': app.updated_at.isoformat() if app.updated_at else None
        })
    except Exception as e:
        logger.error(f"Error getting status for app {model_slug}/{app_num}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/app/<model_slug>/<int:app_num>/logs.json')
def app_logs(model_slug, app_num):
    """Get logs for specific application (JSON variant).

    Note: The HTML modal for logs is served by
    /api/app/<model_slug>/<int:app_num>/logs in api/applications.py.
    This JSON endpoint avoids a route collision and can be used by API clients.
    """
    try:
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_num).first()
        if not app:
            return jsonify({'error': 'Application not found'}), 404

        # Fetch real logs via DockerManager if available
        backend_logs = None
        frontend_logs = None
        try:
            from ...services.service_locator import ServiceLocator
            docker = ServiceLocator.get_docker_manager()
            if docker is not None:  # type: ignore[truthy-bool]
                backend_logs = docker.get_container_logs(model_slug, app_num, 'backend', tail=200)  # type: ignore[attr-defined]
                frontend_logs = docker.get_container_logs(model_slug, app_num, 'frontend', tail=200)  # type: ignore[attr-defined]
        except Exception:
            pass

        return jsonify({
            'backend_logs': backend_logs or '',
            'frontend_logs': frontend_logs or '',
            'last_updated': app.updated_at.isoformat() if app.updated_at else None
        })
    except Exception as e:
        logger.error(f"Error getting logs for app {model_slug}/{app_num}: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# MODEL STATISTICS ENDPOINTS
# =================================================================

@api_bp.route('/models/stats/performance')
def models_stats_performance():
    """Get model performance statistics."""
    try:
        from sqlalchemy import func
        
        # Performance stats by model
        performance_stats = db.session.query(
            ModelCapability.model_name,
            ModelCapability.provider,
            func.count(SecurityAnalysis.id).label('security_tests'),
            func.count(PerformanceTest.id).label('performance_tests'),
            func.avg(PerformanceTest.requests_per_second).label('avg_rps'),
            func.avg(PerformanceTest.average_response_time).label('avg_response_time')
        ).outerjoin(GeneratedApplication, GeneratedApplication.model_slug == ModelCapability.canonical_slug)\
         .outerjoin(SecurityAnalysis, SecurityAnalysis.application_id == GeneratedApplication.id)\
         .outerjoin(PerformanceTest, PerformanceTest.application_id == GeneratedApplication.id)\
         .group_by(ModelCapability.id, ModelCapability.model_name, ModelCapability.provider)\
         .having(func.count(GeneratedApplication.id) > 0).all()
        
        return jsonify([{
            'model_name': stat.model_name,
            'provider': stat.provider,
            'security_tests': stat.security_tests or 0,
            'performance_tests': stat.performance_tests or 0,
            'avg_rps': float(stat.avg_rps) if stat.avg_rps else 0.0,
            'avg_response_time': float(stat.avg_response_time) if stat.avg_response_time else 0.0
        } for stat in performance_stats])
    except Exception as e:
        logger.error(f"Error getting model performance stats: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/models/stats/last-updated')
def models_stats_last_updated():
    """Get last updated timestamp for models."""
    try:
        from sqlalchemy import func
        
        last_updated = db.session.query(
            func.max(ModelCapability.updated_at)
        ).scalar()
        
        return jsonify({
            'last_updated': last_updated.isoformat() if last_updated else None
        })
    except Exception as e:
        logger.error(f"Error getting models last updated: {e}")
        return jsonify({'error': str(e)}), 500
