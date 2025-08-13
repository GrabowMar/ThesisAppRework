"""
Models API Routes
================

API endpoints for AI model management and information.
"""

import logging
from flask import jsonify

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


@api_bp.route('/app/<model_slug>/<int:app_num>/logs')
def app_logs(model_slug, app_num):
    """Get logs for specific application."""
    try:
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_num
        ).first()
        
        if not app:
            return jsonify({'error': 'Application not found'}), 404
        
        # For now, return placeholder logs
        # In production, this would interface with docker/container logging
        logs = {
            'backend_logs': f"Backend logs for {model_slug} app {app_num}...",
            'frontend_logs': f"Frontend logs for {model_slug} app {app_num}...",
            'docker_logs': f"Docker logs for {model_slug} app {app_num}...",
            'last_updated': app.updated_at.isoformat() if app.updated_at else None
        }
        
        return jsonify(logs)
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
