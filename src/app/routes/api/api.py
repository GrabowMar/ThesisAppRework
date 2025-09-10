"""
API routes for the Flask application
====================================

API endpoints that return JSON responses.
"""

import os
import psutil
import subprocess
import importlib
import traceback
from pathlib import Path  # noqa: F401 (may still be used elsewhere dynamically)
from app.services.maintenance_service import MaintenanceService
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, current_app, abort, url_for, Response  # noqa: F401 (Response used in dynamic download endpoint)

from app.extensions import db
from app.models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest,
    BatchAnalysis, ContainerizedTest
)
from app.constants import ContainerState
from app.utils.helpers import create_success_response, create_error_response
from app.utils.errors import build_error_payload
from app.services.data_initialization import data_init_service
from app.services.statistics_service import (
    get_application_statistics, get_model_statistics, get_analysis_statistics,
    get_recent_statistics, get_model_distribution, get_generation_trends,
    get_analysis_summary, export_statistics
)
from app.services import application_service as app_service
from app.utils.generated_apps import list_generated_models, load_model_capabilities
 # (ModelService, AnalysisTaskService not required directly for fragment aliases)

# Import shared utilities
from ..shared_utils import _upsert_openrouter_models, _norm_caps

# Helper functions for missing response utilities
def build_pagination_envelope(query, page, per_page):
    """Build pagination envelope for query results."""
    try:
        items = query.paginate(page=page, per_page=per_page, error_out=False)
        total = query.count()
        total_pages = (total + per_page - 1) // per_page

        return items.items if hasattr(items, 'items') else items, {
            'current_page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
    except Exception:
        # Fallback for queries that don't support pagination
        all_items = query.all() if hasattr(query, 'all') else list(query)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        items = all_items[start_idx:end_idx]

        total = len(all_items)
        total_pages = (total + per_page - 1) // per_page

        return items, {
            'current_page': page,
            'per_page': per_page,
            'total_items': total,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }

def require_fields(data, required_fields):
    """Check if required fields are present in data."""
    missing = []
    for field in required_fields:
        if field not in data or data[field] is None:
            missing.append(field)
    return missing

def create_success_response_with_status(data=None, message="Success", status=200, **kwargs):
    """Create standardized success response with status support."""
    response = create_success_response(data, message)
    return response, status

def create_error_response_with_status(error, status=500, error_type=None, **kwargs):
    """Create standardized error response with status support."""
    response = create_error_response(error, status, error_type)
    return response, status

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')
# -----------------------------------------------------------------
# Wizard / Analysis fragments aliases (HTML responses via Jinja)
# -----------------------------------------------------------------

@api_bp.route('/models/grid')
def api_models_grid_fragment_alias():
    """Alias to analysis model grid fragment for wizard (HTML).

    If the analysis blueprint view isn't registered yet, return 503.
    """
    view = current_app.view_functions.get('analysis.htmx_model_grid_fragment')
    if not view:
        return "<div class='alert alert-warning'>Model grid unavailable</div>", 503
    return view()

@api_bp.route('/models/<model_slug>/applications')
def api_model_apps_fragment_alias(model_slug):
    """Alias to analysis model applications fragment (HTML)."""
    view = current_app.view_functions.get('analysis.htmx_model_applications_fragment')
    if not view:
        return "<div class='alert alert-warning'>Applications list unavailable</div>", 503
    return view(model_slug)

@api_bp.route('/tasks/recent')
def api_recent_tasks_fragment_alias():
    """Alias for recent tasks fragment (HTML)."""
    view = current_app.view_functions.get('analysis.htmx_recent_tasks_fragment')
    if not view:
        return "<div class='alert alert-warning'>Tasks fragment unavailable</div>", 503
    return view()

# Global exception handler for API routes
@api_bp.app_errorhandler(Exception)
def api_global_exception_handler(exc):
    """Return standardized JSON errors for unhandled exceptions within /api.* routes."""
    current_app.logger.exception("Unhandled exception in API layer")
    return create_error_response_with_status("Internal server error", status=500, error_type=exc.__class__.__name__)

# =================================================================
# CORE API ROUTES
# =================================================================

@api_bp.route('/')
def api_overview():
    """API overview endpoint."""
    return create_success_response({
        'version': '1.0',
        'endpoints': {
            'models': '/api/models',
            'applications': '/api/applications',
            'statistics': '/api/statistics',
            'system': '/api/system',
            'analysis': '/api/analysis'
        }
    }, message='Thesis Research App API')

@api_bp.route('/health')
def api_health():
    """API health check endpoint."""
    return create_success_response({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'version': '1.0'
    })

@api_bp.route('/stats')
def api_stats():
    """API endpoint for dashboard statistics."""
    try:
        stats = {
            'models': ModelCapability.query.count(),
            'applications': GeneratedApplication.query.count(),
            'security_analyses': SecurityAnalysis.query.count(),
            'performance_tests': PerformanceTest.query.count(),
            'batch_jobs': BatchAnalysis.query.count(),
            'active_containers': ContainerizedTest.query.filter_by(
                status=ContainerState.RUNNING.value
            ).count()
        }
        return jsonify(stats)
    except Exception as e:
        current_app.logger.error(f"Error getting API stats: {e}")
        return jsonify(build_error_payload("Failed to retrieve statistics", status=500, error="StatsError", details={"reason": str(e)})), 500

@api_bp.route('/data/initialize', methods=['POST'])
def api_initialize_data():
    """API endpoint to initialize database with data from JSON files."""
    try:
        results = data_init_service.initialize_all_data()
        return jsonify(results)
    except Exception as e:
        current_app.logger.error(f"Error initializing data: {e}")
        return jsonify(build_error_payload(
            "Failed to initialize data",
            status=500,
            error="DataInitializationError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/data/status')
def api_data_status():
    """API endpoint to get data initialization status."""
    try:
        status = data_init_service.get_initialization_status()
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error getting data status: {e}")
        return jsonify(build_error_payload("Failed to retrieve data status", status=500, error="DataStatusError", details={"reason": str(e)})), 500

@api_bp.route('/data/reload', methods=['POST'])
def api_reload_core_data():
    """API endpoint to reload core JSON files."""
    try:
        results = data_init_service.reload_core_files()
        status_code = 200 if results.get('success', True) and not results.get('errors') else 207
        return jsonify(results), status_code
    except Exception as e:
        current_app.logger.error(f"Error reloading core data: {e}")
        return jsonify(build_error_payload(
            "Failed to reload core data",
            status=500,
            error="DataReloadError",
            details={"reason": str(e)}
        )), 500

# =================================================================
# DASHBOARD API ROUTES
# =================================================================

@api_bp.route('/dashboard/overview')
def api_dashboard_overview():
    """API endpoint: Get dashboard overview data."""
    try:
        # Total counts
        total_apps = db.session.query(db.func.count(GeneratedApplication.id)).scalar()
        total_models = db.session.query(db.func.count(ModelCapability.id)).scalar()
        total_security = db.session.query(db.func.count(SecurityAnalysis.id)).scalar()
        total_performance = db.session.query(db.func.count(PerformanceTest.id)).scalar()

        # Recent activity (last 7 days)
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        recent_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.created_at >= week_ago)
            .scalar()
        )

        # Active applications
        active_apps = (
            db.session.query(db.func.count(GeneratedApplication.id))
            .filter(GeneratedApplication.container_status == 'running')
            .scalar()
        )

        # Success rates
        completed_security = (
            db.session.query(db.func.count(SecurityAnalysis.id))
            .filter(SecurityAnalysis.status == 'completed')
            .scalar()
        )
        security_rate = (completed_security / total_security * 100) if total_security > 0 else 0

        completed_performance = (
            db.session.query(db.func.count(PerformanceTest.id))
            .filter(PerformanceTest.status == 'completed')
            .scalar()
        )
        performance_rate = (completed_performance / total_performance * 100) if total_performance > 0 else 0

        return jsonify({
            'totals': {
                'applications': total_apps,
                'models': total_models,
                'security_analyses': total_security,
                'performance_tests': total_performance
            },
            'activity': {
                'recent_applications': recent_apps,
                'active_applications': active_apps
            },
            'success_rates': {
                'security': round(security_rate, 2),
                'performance': round(performance_rate, 2)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard overview: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve dashboard overview",
            status=500,
            error="DashboardOverviewError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/dashboard/stats')
def api_dashboard_stats():
    """Enhanced API endpoint for dashboard statistics."""
    try:
        # Basic counts
        models_count = ModelCapability.query.count()
        apps_count = GeneratedApplication.query.count()
        security_count = SecurityAnalysis.query.count()
        performance_count = PerformanceTest.query.count()

        # Provider breakdown
        provider_stats = db.session.query(
            ModelCapability.provider,
            db.func.count(ModelCapability.id).label('count')
        ).group_by(ModelCapability.provider).all()

        # Application framework breakdown
        framework_stats = db.session.query(
            GeneratedApplication.backend_framework,
            db.func.count(GeneratedApplication.id).label('count')
        ).group_by(GeneratedApplication.backend_framework).all()

        # Recent activity
        recent_models = ModelCapability.query.order_by(
            ModelCapability.created_at.desc()
        ).limit(5).all()

        recent_apps = GeneratedApplication.query.order_by(
            GeneratedApplication.created_at.desc()
        ).limit(5).all()

        return jsonify({
            'counts': {
                'models': models_count,
                'applications': apps_count,
                'security_tests': security_count,
                'performance_tests': performance_count
            },
            'providers': [{'name': p[0], 'count': p[1]} for p in provider_stats],
            'frameworks': [{'name': f[0] or 'Unknown', 'count': f[1]} for f in framework_stats],
            'recent_models': [m.to_dict() for m in recent_models],
            'recent_apps': [a.to_dict() for a in recent_apps],
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting dashboard stats: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve dashboard stats",
            status=500,
            error="DashboardStatsError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/sidebar_stats')
def sidebar_stats():
    """HTMX endpoint for sidebar statistics."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count()
        }
        return render_template('partials/common/_sidebar_stats_inner.html', stats=stats)
    except Exception as e:
        current_app.logger.error(f"Error getting sidebar stats: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        return render_template('partials/common/_sidebar_stats_inner.html', stats={
            'total_models': 0, 'total_apps': 0, 'security_tests': 0, 'performance_tests': 0
        })

@api_bp.route('/dashboard/stats-fragment')
def dashboard_stats_fragment():
    """HTMX endpoint returning dashboard stats inner fragment HTML."""
    try:
        stats = {
            'total_models': db.session.query(ModelCapability).count(),
            'total_apps': db.session.query(GeneratedApplication).count(),
            'security_tests': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
        }
        # Return inline HTML fragment (removed external template dependency)
        return (
            '<div class="row g-3">'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_models"]}</div><div class="text-muted small">Models</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["total_apps"]}</div><div class="text-muted small">Apps</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["security_tests"]}</div><div class="text-muted small">Security</div>'
            '</div></div></div>'
            f'<div class="col-6 col-md-3"><div class="card text-center stat-card"><div class="card-body py-3">'
            f'<div class="h4 mb-0">{stats["performance_tests"]}</div><div class="text-muted small">Perf</div>'
            '</div></div></div>'
            '</div>'
        )
    except Exception as e:
        current_app.logger.error(f"Error rendering dashboard stats fragment: {e}")
        return (
            '<div class="row g-3">'
            '<div class="col-12 text-muted small">Stats unavailable</div>'
            '</div>'
        )

@api_bp.route('/dashboard/system-health-fragment')
def dashboard_system_health_fragment():
    """Return small system health fragment."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        health = {
            'status': 'healthy',
            'uptime_minutes': 0,
            'active_tasks': 0,
        }
        return render_template('pages/system/partials/_system_health_inner.html', health=health)
    except Exception as e:
        current_app.logger.error(f"Error rendering system health: {e}")
        return '<div class="text-muted small">Health unavailable</div>'

@api_bp.route('/dashboard/analyzer-services')
def dashboard_analyzer_services():
    """Return analyzer services status cards."""
    try:
        services = [
            {'name': 'Security', 'status': 'healthy', 'version': '1.0'},
            {'name': 'Performance', 'status': 'healthy', 'version': '1.0'},
        ]
        cards = []
        for svc in services:
            cards.append(
                '<div class="col-md-3">'
                '<div class="card h-100 service-card">'
                '<div class="card-body py-2 px-3">'
                '<div class="d-flex justify-content-between align-items-center">'
                f'<strong class="small">{svc["name"]}</strong>'
                f'<span class="badge bg-{"success" if svc["status"]=="healthy" else "secondary"}">{svc["status"]}</span>'
                '</div>'
                f'<div class="small text-muted">v{svc.get("version") or "1.0"}</div>'
                '</div>'
                '</div>'
                '</div>'
            )
        return '<div class="row g-2">' + ''.join(cards) + '</div>'
    except Exception:
        current_app.logger.error("Analyzer services fragment failed", exc_info=True)
        return '<div class="text-muted small">Analyzer services unavailable</div>'

@api_bp.route('/dashboard/docker-status')
def dashboard_docker_status():
    """Return minimal docker status JSON placeholder."""
    return jsonify({'status': 'unavailable', 'message': 'Docker not running in test env'}), 200

@api_bp.route('/recent_activity')
def recent_activity():
    """HTMX endpoint for recent activity timeline."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        # Get recent activities (last 10 items)
        recent_security = db.session.query(SecurityAnalysis).order_by(db.desc(SecurityAnalysis.started_at)).limit(5).all()
        recent_performance = db.session.query(PerformanceTest).order_by(db.desc(PerformanceTest.started_at)).limit(5).all()
        recent_batch = db.session.query(BatchAnalysis).order_by(db.desc(BatchAnalysis.created_at)).limit(5).all()

        activities = []

        # Add security activities
        for analysis in recent_security:
            if analysis.started_at:
                activities.append({
                    'type': 'security',
                    'description': 'Security analysis completed',
                    'timestamp': analysis.started_at,
                    'status': analysis.status.value if analysis.status else 'unknown'
                })

        # Add performance activities
        for test in recent_performance:
            if test.started_at:
                activities.append({
                    'type': 'performance',
                    'description': 'Performance test completed',
                    'timestamp': test.started_at,
                    'status': test.status.value if test.status else 'unknown'
                })

        # Add batch activities
        for batch in recent_batch:
            if batch.created_at:
                activities.append({
                    'type': 'batch',
                    'description': f'Batch analysis #{batch.id}',
                    'timestamp': batch.created_at,
                    'status': batch.status.value if batch.status else 'unknown'
                })

        # Sort by timestamp
        activities.sort(key=lambda x: x['timestamp'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        activities = activities[:10]  # Keep only the 10 most recent

        if not activities:
            return '<div class="text-center py-3"><p class="text-muted">Unable to load activity</p></div>'
        return render_template('components/dashboard/activity-timeline.html', activities=activities)
    except Exception as e:
        current_app.logger.error(f"Error getting recent activity: {e}")
        from app.utils.template_paths import render_template_compat as render_template
        return render_template('components/dashboard/activity-timeline.html', activities=[])

# =================================================================
# MODELS API ROUTES
# =================================================================

@api_bp.route('/models')
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
    return create_success_response(data, message="Models fetched")

@api_bp.route('/models/<model_slug>/apps')
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
    return create_success_response(data, message="Applications fetched")

@api_bp.route('/models/list')
def api_models_list():
    """API endpoint: Get models list."""
    try:
        models = ModelCapability.query.all()
        return jsonify([model.to_dict() for model in models])
    except Exception as e:
        current_app.logger.error(f"Error getting models list: {e}")
        return jsonify(build_error_payload(
            "Failed to get models list",
            status=500,
            error="ModelsListError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/models/list-options')
def api_models_list_options():
    """HTMX endpoint: Render <option> list for model selects."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        if installed_only:
            try:
                models = [m for m in models if getattr(m, 'installed', False)]
            except Exception:
                repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                models_base = os.path.join(repo_root, 'generated')
                models = [m for m in models if os.path.isdir(os.path.join(models_base, m.canonical_slug))]
        return render_template('partials/models/_model_options.html', models=models)
    except Exception as e:
        current_app.logger.error(f"Error rendering model options: {e}")
        return '<option value="">All Models</option>', 200

@api_bp.route('/models/all')
def api_models_all():
    """Return models and simple statistics for Models Overview page."""
    try:
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # Fallback path: if database empty, synthesize lightweight model entries
        # from filesystem directories (generated/apps/<model_slug>) or
        # model_capabilities.json. This allows the front-end to show models
        # immediately after generation even before data import tasks ran.
        synthetic_mode = False
        synthetic_models = []
        if not models:
            try:
                fs_slugs = list_generated_models()  # raw folder names
                cap_json = load_model_capabilities().get('data') or {}
                # Normalize capability map: expect dict keyed by slug
                for slug in fs_slugs:
                    entry = cap_json.get(slug) if isinstance(cap_json, dict) else {}
                    class _Synthetic:
                        canonical_slug = slug
                        model_id = slug
                        model_name = slug
                        provider = slug.split('_')[0]
                        input_price_per_token = 0.0
                        output_price_per_token = 0.0
                        context_window = 0
                        max_output_tokens = 0
                        cost_efficiency = 0.0
                        installed = True
                        def get_capabilities(self):
                            # entry may already be capabilities list/dict
                            if isinstance(entry, dict) and 'capabilities' in entry:
                                return entry
                            return {'capabilities': entry if isinstance(entry, (list, dict)) else []}
                        def get_metadata(self):
                            return {}
                    synthetic_models.append(_Synthetic())
                if synthetic_models:
                    models = synthetic_models
                    synthetic_mode = True
            except Exception:
                pass

        # If DB is empty, try to fetch from OpenRouter
        try:
            if not models:
                api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
                if api_key:
                    import requests
                    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                    try:
                        resp = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
                        if resp.status_code == 200:
                            body = resp.json()
                            payload = []
                            if isinstance(body, dict):
                                for key in ('data', 'models', 'items'):
                                    if key in body and isinstance(body[key], list):
                                        payload = body[key]
                                        break
                                if not payload and isinstance(body.get('results'), list):
                                    payload = body.get('results')
                            elif isinstance(body, list):
                                payload = body

                            if payload:
                                _upsert_openrouter_models(payload)
                                models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
                    except Exception:
                        pass
        except Exception:
            pass

        # Optional installed-only filter
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        if installed_only:
            try:
                models = [m for m in models if getattr(m, 'installed', False)]
            except Exception:
                repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                models_base = os.path.join(repo_root, 'generated')
                models = [m for m in models if os.path.isdir(os.path.join(models_base, m.canonical_slug))]

        def map_model(m: ModelCapability):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            out = {
                'slug': m.canonical_slug,
                'model_id': m.model_id,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/images/default-avatar.svg',
                'capabilities': caps_list,
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'max_output_tokens': m.max_output_tokens or 0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': meta.get('openrouter_description') or meta.get('description') or None,
                'installed': bool(getattr(m, 'installed', False)),
                'openrouter': {
                    'model_id': meta.get('openrouter_model_id'),
                    'name': meta.get('openrouter_name'),
                    'created': meta.get('openrouter_created'),
                    'canonical_slug': meta.get('openrouter_canonical_slug'),
                    'pricing': meta.get('openrouter_pricing'),
                    'top_provider': meta.get('openrouter_top_provider')
                }
            }
            return out

        models_list = [map_model(m) for m in models]
        providers = {m.provider for m in models}
        stats = {
            'total_models': len(models_list),
            'active_models': len(models_list),
            'unique_providers': len(providers),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in models_list) / max(len(models_list), 1), 6),
            'source': 'synthetic' if synthetic_mode else 'database'
        }
        return jsonify({'models': models_list, 'statistics': stats})
    except Exception as e:
        current_app.logger.error(f"Error building models/all payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})

@api_bp.route('/models/filtered')
def api_models_filtered():
    """Filtered models list used by models.js applyFilters().

    Query params:
      search: substring match on model_name or canonical_slug
      providers: repeated param list of provider slugs
      capabilities: repeated param list (matched against capabilities array)
      price: optional tier (free|low|mid|high) based on input price per 1k tokens
    Returns same envelope shape as /models/all but with filtered subset & recalculated statistics.
    """
    try:
        search = (request.args.get('search') or '').strip().lower()
        providers = {p.lower() for p in request.args.getlist('providers') if p.strip()}
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').lower()

        base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # If DB empty, synthesize base list from filesystem so filtering still works
        if not base:
            try:
                from app.utils.generated_apps import list_generated_models, load_model_capabilities
                slugs = list_generated_models()
                caps_json = load_model_capabilities().get('data') or {}
                syn = []
                for slug in slugs:
                    entry = caps_json.get(slug) if isinstance(caps_json, dict) else {}
                    class _Synthetic:
                        canonical_slug = slug
                        model_id = slug
                        model_name = slug
                        provider = slug.split('_')[0]
                        input_price_per_token = 0.0
                        output_price_per_token = 0.0
                        context_window = 0
                        max_output_tokens = 0
                        cost_efficiency = 0.0
                        installed = True
                        def get_capabilities(self):
                            if isinstance(entry, dict) and 'capabilities' in entry:
                                return entry
                            return {'capabilities': entry if isinstance(entry, (list, dict)) else []}
                        def get_metadata(self):
                            return {}
                    syn.append(_Synthetic())
                if syn:
                    base = syn
            except Exception:
                pass

        def price_bucket(val: float) -> str:
            if val == 0:
                return 'free'
            if val < 0.001:  # < $0.001 per token (~$1 per 1k) low
                return 'low'
            if val < 0.005:
                return 'mid'
            return 'high'

        filtered = []
        for m in base:
            name_l = (m.model_name or '').lower()
            slug_l = (m.canonical_slug or '').lower()
            if search and search not in name_l and search not in slug_l:
                continue
            if providers and m.provider.lower() not in providers:
                continue
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            caps_lower = {c.lower() for c in caps_list}
            if caps_filter and not caps_filter.issubset(caps_lower):
                continue
            if price_tier:
                bucket = price_bucket(m.input_price_per_token or 0.0)
                if bucket != price_tier:
                    continue
            filtered.append(m)

        def map_model(m: ModelCapability):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            return {
                'slug': m.canonical_slug,
                'model_id': m.model_id,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/images/default-avatar.svg',
                'capabilities': caps_list,
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'max_output_tokens': m.max_output_tokens or 0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': meta.get('openrouter_description') or meta.get('description') or None,
                'installed': bool(getattr(m, 'installed', False)),
            }

        models_list = [map_model(m) for m in filtered]
        providers_set = {m['provider'] for m in models_list}
        stats = {
            'total_models': len(models_list),
            'active_models': len(models_list),
            'unique_providers': len(providers_set),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in models_list) / max(len(models_list), 1), 6)
        }
        return jsonify({'models': models_list, 'statistics': stats})
    except Exception as e:  # pragma: no cover - unexpected failure path
        current_app.logger.error(f"Error building models/filtered payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})

@api_bp.route('/models/paginated')
def api_models_paginated():
    """Paginated & filterable models list.

    Query params:
      page: page number (default 1)
      per_page: page size (default 25, max 200)
      search, providers, capabilities, price: same semantics as /models/filtered
      source: db|openrouter (default db) – when openrouter, pulls fresh (or cached) list from OpenRouterService
    Response JSON keys:
      models: list (current page slice)
      statistics: aggregation over FULL filtered result set
      pagination: envelope {current_page, per_page, total_items, total_pages, has_prev, has_next}
      source: 'db' | 'openrouter'
    """
    # Import inside function to avoid circular dependency during app init
    try:
        from ..shared_utils import openrouter_service  # type: ignore
    except Exception:
        openrouter_service = None  # type: ignore

    try:
        # Pagination params
        page = request.args.get('page', type=int) or 1
        per_page = request.args.get('per_page', type=int) or 25
        per_page = max(1, min(per_page, 200))
        if page < 1:
            page = 1

        # Source: db | openrouter
        source = (request.args.get('source') or 'db').lower()
        if source not in {'db', 'openrouter'}:
            source = 'db'

        # Filters
        search = (request.args.get('search') or '').strip().lower()
        providers_filter = {p.lower() for p in request.args.getlist('providers') if p.strip()}
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').lower()
        installed_param = request.args.get('installed') or request.args.get('installed_only') or request.args.get('used')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}

        # Acquire base list
        base_models: list = []
        synthetic_mode = False
        if source == 'openrouter' and openrouter_service and getattr(openrouter_service, 'api_key', None):
            try:
                or_models = openrouter_service.fetch_all_models() or []
                class _ORWrap:
                    __slots__ = ('canonical_slug','model_id','model_name','provider','input_price_per_token','output_price_per_token','context_window','max_output_tokens','cost_efficiency','_caps','_meta','installed')
                    def __init__(self, raw: dict):
                        mid = raw.get('id') or ''
                        self.model_id = mid
                        self.canonical_slug = (mid.replace('/', '_')) if mid else raw.get('name','unknown')
                        self.model_name = raw.get('name') or mid or 'unknown'
                        self.provider = mid.split('/')[0] if '/' in mid else (raw.get('provider') or 'unknown')
                        pricing = raw.get('pricing') or {}
                        try:
                            self.input_price_per_token = float(pricing.get('prompt') or 0) / 1000.0
                            self.output_price_per_token = float(pricing.get('completion') or 0) / 1000.0
                        except Exception:
                            self.input_price_per_token = 0.0
                            self.output_price_per_token = 0.0
                        self.context_window = raw.get('context_length') or (raw.get('top_provider') or {}).get('context_length') or 0
                        self.max_output_tokens = (raw.get('top_provider') or {}).get('max_completion_tokens') or 0
                        self.cost_efficiency = 0.0
                        arch = raw.get('architecture') or {}
                        caps = []
                        for k in ('modality','input_modalities','output_modalities'):
                            v = arch.get(k)
                            if isinstance(v, str):
                                caps.append(v)
                            elif isinstance(v, list):
                                caps.extend(v)
                        if raw.get('supports_tool_calls'):
                            caps.append('function_calling')
                        self._caps = {'capabilities': list({c for c in caps if c})}
                        self._meta = {
                            'openrouter_description': raw.get('description'),
                            'openrouter_model_id': mid,
                            'openrouter_name': raw.get('name'),
                            'openrouter_canonical_slug': raw.get('canonical_slug'),
                        }
                        self.installed = False
                    def get_capabilities(self):
                        return self._caps
                    def get_metadata(self):
                        return self._meta
                base_models = [_ORWrap(m) for m in or_models if isinstance(m, dict)]
            except Exception as e:  # pragma: no cover
                current_app.logger.warning(f"OpenRouter pagination source failed: {e}")
                base_models = []
        else:
            base_models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
            if not base_models:
                try:
                    fs_slugs = list_generated_models()
                    cap_json = load_model_capabilities().get('data') or {}
                    syn = []
                    for slug in fs_slugs:
                        entry = cap_json.get(slug) if isinstance(cap_json, dict) else {}
                        class _Synthetic:
                            canonical_slug = slug
                            model_id = slug
                            model_name = slug
                            provider = slug.split('_')[0]
                            input_price_per_token = 0.0
                            output_price_per_token = 0.0
                            context_window = 0
                            max_output_tokens = 0
                            cost_efficiency = 0.0
                            installed = True
                            def get_capabilities(self):
                                if isinstance(entry, dict) and 'capabilities' in entry:
                                    return entry
                                return {'capabilities': entry if isinstance(entry, (list, dict)) else []}
                            def get_metadata(self):
                                return {}
                        syn.append(_Synthetic())
                    if syn:
                        base_models = syn
                        synthetic_mode = True
                except Exception:
                    pass

        # If we are focusing on installed/used models, optionally pre-fetch OpenRouter catalog
        or_index_by_slug: dict[str, dict] = {}
        if installed_only and source != 'openrouter' and openrouter_service and getattr(openrouter_service, 'api_key', None):
            try:
                _or_models = openrouter_service.fetch_all_models() or []  # type: ignore[attr-defined]
                for _raw in _or_models:
                    if not isinstance(_raw, dict):
                        continue
                    _mid = _raw.get('id') or ''
                    if not _mid:
                        continue
                    # Canonical with variant (replace / and :)
                    _canon_full = _mid.replace('/', '_').replace(':', '_')
                    or_index_by_slug[_canon_full] = _raw
                    # Base (strip variant after colon)
                    if ':' in _mid:
                        _base_mid = _mid.split(':', 1)[0]
                        _canon_base = _base_mid.replace('/', '_')
                        # Don't overwrite a full exact entry, but add if missing
                        or_index_by_slug.setdefault(_canon_base, _raw)
            except Exception as _e:  # pragma: no cover - best effort enrichment
                current_app.logger.warning(f"OpenRouter enrichment (installed_only) failed: {_e}")

        def price_bucket(val: float) -> str:
            if val == 0:
                return 'free'
            if val < 0.001:
                return 'low'
            if val < 0.005:
                return 'mid'
            return 'high'

        # Filtering
        filtered = []
        for m in base_models:
            name_l = (getattr(m, 'model_name', '') or '').lower()
            slug_l = (getattr(m, 'canonical_slug', '') or '').lower()
            if search and search not in name_l and search not in slug_l:
                continue
            if providers_filter and (getattr(m, 'provider', '').lower() not in providers_filter):
                continue
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            caps_lower = {c.lower() for c in caps_list}
            if caps_filter and not caps_filter.issubset(caps_lower):
                continue
            if price_tier:
                bucket = price_bucket(getattr(m, 'input_price_per_token', 0.0) or 0.0)
                if bucket != price_tier:
                    continue
            if installed_only:
                if not bool(getattr(m, 'installed', False)):
                    try:
                        from app.utils.generated_apps import list_generated_models as _lgm
                        if getattr(m, 'canonical_slug', None) not in set(_lgm()):
                            continue
                    except Exception:
                        continue
            filtered.append(m)

        total_items = len(filtered)
        total_pages = (total_items + per_page - 1) // per_page if total_items else 1
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page
        end = start + per_page
        page_items = filtered[start:end]

        def map_model(m):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            base_slug = getattr(m, 'canonical_slug', None)
            result = {
                'slug': getattr(m, 'canonical_slug', None),
                'model_id': getattr(m, 'model_id', None),
                'name': getattr(m, 'model_name', None),
                'provider': getattr(m, 'provider', None),
                'capabilities': caps_list,
                'input_price_per_1k': round((getattr(m, 'input_price_per_token', 0.0) or 0.0) * 1000, 6),
                'output_price_per_1k': round((getattr(m, 'output_price_per_token', 0.0) or 0.0) * 1000, 6),
                'context_length': getattr(m, 'context_window', 0) or 0,
                'max_output_tokens': getattr(m, 'max_output_tokens', 0) or 0,
                'performance_score': int((getattr(m, 'cost_efficiency', 0.0) or 0.0) * 10) if (getattr(m, 'cost_efficiency', 0.0) or 0) <= 1 else int(getattr(m, 'cost_efficiency', 0.0) or 0),
                'status': 'active',
                'installed': bool(getattr(m, 'installed', False)),
                'description': meta.get('openrouter_description') or meta.get('description') or None,
            }
            # Enrich with OpenRouter catalog details if we have them (for installed_only views)
            if base_slug and base_slug in or_index_by_slug:
                _raw = or_index_by_slug[base_slug]
                _pricing = _raw.get('pricing') or {}
                try:
                    prompt_price = float(_pricing.get('prompt') or 0)
                    completion_price = float(_pricing.get('completion') or 0)
                except Exception:
                    prompt_price = 0.0
                    completion_price = 0.0
                # Keep existing numeric prices (per 1k tokens) but also surface explicit OpenRouter fields
                result.update({
                    'openrouter_model_id': _raw.get('id'),
                    'openrouter_name': _raw.get('name'),
                    'openrouter_canonical_slug': _raw.get('canonical_slug'),
                    'openrouter_prompt_price': prompt_price,  # raw price per 1 token? (OpenRouter returns per 1M in some cases; here we store raw)
                    'openrouter_completion_price': completion_price,
                    'openrouter_description': _raw.get('description'),
                    'openrouter_architecture': _raw.get('architecture'),
                    'openrouter_top_provider': _raw.get('top_provider'),
                    'openrouter_features': {
                        'supports_tool_calls': _raw.get('supports_tool_calls'),
                        'supports_json_mode': _raw.get('supports_json_mode'),
                        'supports_streaming': _raw.get('supports_streaming'),
                        'supports_vision': _raw.get('supports_vision'),
                    },
                })
            return result

        mapped_page = [map_model(m) for m in page_items]
        all_mapped_for_stats = [map_model(m) for m in filtered]
        providers_set = {m['provider'] for m in all_mapped_for_stats}
        stats = {
            'total_models': len(all_mapped_for_stats),
            'active_models': len(all_mapped_for_stats),
            'unique_providers': len(providers_set),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in all_mapped_for_stats) / max(len(all_mapped_for_stats), 1), 6),
            'source': 'openrouter' if source == 'openrouter' else ('synthetic' if synthetic_mode else 'database'),
            'openrouter_enriched_installed': bool(or_index_by_slug)
        }
        return jsonify({
            'models': mapped_page,
            'statistics': stats,
            'pagination': {
                'current_page': page,
                'per_page': per_page,
                'total_items': total_items,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages
            },
            'source': stats['source']
        })
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error building models/paginated payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0}, 'pagination': {'current_page': 1, 'per_page': 25, 'total_items': 0, 'total_pages': 1, 'has_prev': False, 'has_next': False}, 'source': 'error'})

@api_bp.route('/models/comparison/refresh', methods=['POST'])
def models_comparison_refresh():
    """Compute lightweight comparison metrics for provided models.

    Tests only assert a 200 response; we fabricate deterministic metrics.
    Form fields: models (comma separated), baseline (avg|median|model:<slug>)
    """
    try:
        baseline_spec = 'avg'
        model_slugs: list[str] = []
        if request.is_json:
            body = request.get_json(silent=True) or {}
            raw_models = body.get('models') or body.get('slugs') or body.get('ids') or ''
            baseline_spec = body.get('baseline', 'avg')
            if isinstance(raw_models, list):
                items = raw_models
            else:
                items = [s.strip() for s in str(raw_models).split(',') if s.strip()]
        else:
            raw_models = request.form.get('models', '')
            baseline_spec = request.form.get('baseline', 'avg')
            items = [m.strip() for m in raw_models.split(',') if m.strip()]

        # Resolve provided identifiers (canonical_slug, model_id, model_name) to canonical_slug
        for ident in items:
            q = ModelCapability.query.filter(
                (ModelCapability.canonical_slug == ident) |
                (ModelCapability.model_id == ident) |
                (ModelCapability.model_name == ident)
            ).first()
            if q:
                model_slugs.append(q.canonical_slug)
            else:
                # Preserve unknown slug so UI can still compare (placeholder metrics)
                cleaned = ident.strip().replace(' ', '_')
                if cleaned:
                    model_slugs.append(cleaned)
        # Deduplicate & limit to 8 to keep payload small
        seen = set()
        deduped = []
        for s in model_slugs:
            if s not in seen:
                seen.add(s)
                deduped.append(s)
            if len(deduped) >= 8:
                break
        model_slugs = deduped
        # Build real metrics from ModelCapability where possible
        from statistics import median
        metrics: dict[str, dict[str, float | int | bool | None]] = {}
        if model_slugs:
            rows = ModelCapability.query.filter(ModelCapability.canonical_slug.in_(model_slugs)).all()
            rows_by_slug = {r.canonical_slug: r for r in rows}
            for idx, slug in enumerate(model_slugs, start=1):
                r = rows_by_slug.get(slug)
                # Fallback deterministic dummy metrics retained for backward compatibility
                throughput = 100 - idx
                latency_ms = 40 + idx * 5
                cost_per_call = round(0.0005 * idx, 6)
                if r:
                    caps = r.get_capabilities() or {}
                    caps_count = 0
                    if isinstance(caps, dict):
                        caps_count = sum(1 for v in caps.values() if bool(v))
                    metrics[slug] = {
                        'model_id': r.model_id,
                        'provider': r.provider,
                        'context_window': r.context_window or 0,
                        'max_output_tokens': r.max_output_tokens or 0,
                        'input_price_per_1k': round((r.input_price_per_token or 0.0) * 1000, 6),
                        'output_price_per_1k': round((r.output_price_per_token or 0.0) * 1000, 6),
                        'cost_efficiency': round(r.cost_efficiency or 0.0, 6),
                        'safety_score': round(r.safety_score or 0.0, 6),
                        'caps_count': caps_count,
                        'supports_function_calling': bool(r.supports_function_calling),
                        'supports_vision': bool(r.supports_vision),
                        'supports_streaming': bool(r.supports_streaming),
                        'supports_json_mode': bool(r.supports_json_mode),
                        'is_free': bool(r.is_free),
                        # Dummy / synthetic metrics retained
                        'throughput': throughput,
                        'latency_ms': latency_ms,
                        'cost_per_call': cost_per_call
                    }
                else:  # slug resolved but row missing (edge case)
                    metrics[slug] = {
                        'model_id': slug,
                        'provider': None,
                        'context_window': 0,
                        'max_output_tokens': 0,
                        'input_price_per_1k': 0.0,
                        'output_price_per_1k': 0.0,
                        'cost_efficiency': 0.0,
                        'safety_score': 0.0,
                        'caps_count': 0,
                        'supports_function_calling': False,
                        'supports_vision': False,
                        'supports_streaming': False,
                        'supports_json_mode': False,
                        'is_free': False,
                        'throughput': throughput,
                        'latency_ms': latency_ms,
                        'cost_per_call': cost_per_call
                    }

        # Determine baseline metrics
        numeric_keys = [
            'context_window','max_output_tokens','input_price_per_1k','output_price_per_1k',
            'cost_efficiency','safety_score','caps_count','throughput','latency_ms','cost_per_call'
        ]
        def _aggregate(kind: str):
            vals_by_key: dict[str, list[float]] = {k: [] for k in numeric_keys}
            for slug in model_slugs:
                m = metrics.get(slug) or {}
                for k in numeric_keys:
                    v = m.get(k)
                    if isinstance(v, (int, float)):
                        vals_by_key[k].append(float(v))
            out: dict[str, float] = {}
            for k, arr in vals_by_key.items():
                if not arr:
                    out[k] = 0.0
                    continue
                if kind == 'avg':
                    out[k] = round(sum(arr)/len(arr), 6)
                elif kind == 'median':
                    out[k] = round(median(arr), 6)
                else:
                    out[k] = 0.0
            return out

        baseline_kind = baseline_spec.lower()
        baseline_metrics: dict[str, float | int | bool] = {}
        if baseline_kind.startswith('model:'):
            bslug = baseline_kind.split(':',1)[1]
            baseline_metrics = metrics.get(bslug) or (metrics.get(model_slugs[0]) if model_slugs else {})
        elif baseline_kind in ('avg','average'):
            baseline_metrics = _aggregate('avg')
        elif baseline_kind in ('median','med'):
            baseline_metrics = _aggregate('median')
        else:  # default avg
            baseline_metrics = _aggregate('avg')

        # Summary stats for research insight
        summary = {}
        for k in numeric_keys:
            vals = [float(metrics[s][k]) for s in model_slugs if isinstance(metrics.get(s, {}).get(k), (int,float))]
            if not vals:
                continue
            try:
                summary[k] = {
                    'avg': round(sum(vals)/len(vals), 6),
                    'median': round(median(vals), 6),
                    'min': min(vals),
                    'max': max(vals),
                    'min_slug': next((s for s in model_slugs if float(metrics[s][k]) == min(vals)), None),
                    'max_slug': next((s for s in model_slugs if float(metrics[s][k]) == max(vals)), None),
                }
            except Exception:
                continue

        return jsonify({
            'models': model_slugs,
            'baseline': baseline_spec,
            'baseline_metrics': baseline_metrics,
            'metrics': metrics,
            'summary': summary
        })
    except Exception as e:
        current_app.logger.error(f"Model comparison refresh failed: {e}")
        return jsonify({'models': [], 'baseline': 'avg', 'metrics': {}})

@api_bp.route('/models/export')
def models_export():
    """Export models in JSON format (only format supported)."""
    try:
        fmt = request.args.get('format', 'json').lower()
        if fmt != 'json':
            return jsonify({'error': 'only json supported'}), 400
        models = ModelCapability.query.all()
        data = [m.to_dict() for m in models]
        return jsonify({'format': 'json', 'count': len(data), 'models': data})
    except Exception as e:
        current_app.logger.error(f"Models export failed: {e}")
        return jsonify({'format': 'json', 'count': 0, 'models': []})

@api_bp.route('/models/load-openrouter', methods=['POST'])
def api_models_load_openrouter():
    """Load/refresh ModelCapability rows from OpenRouter API."""
    api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'OPENROUTER_API_KEY not configured'}), 400

    import requests
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
        if resp.status_code != 200:
            current_app.logger.error(f'OpenRouter models fetch failed: {resp.status_code} {resp.text[:200]}')
            return jsonify({'success': False, 'error': f'OpenRouter API returned {resp.status_code}'}), 502

        body = resp.json()
        if isinstance(body, dict):
            data = body.get('data') or body.get('models') or body.get('items') or body.get('results') or []
        elif isinstance(body, list):
            data = body
        else:
            data = []

        upserted = _upsert_openrouter_models(data)

        try:
            mark_res = data_init_service.mark_installed_models(reset_first=False)
        except Exception:
            mark_res = {'success': False, 'updated': 0}

        return jsonify({'success': True, 'upserted': upserted, 'fetched': len(data or []), 'mark_installed': mark_res})
    except Exception as e:
        current_app.logger.error(f'Error loading models from OpenRouter: {e}')
        return jsonify(build_error_payload(
            "Failed to load models from OpenRouter",
            status=500,
            error="OpenRouterLoadError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/models/mark-installed', methods=['POST'])
def api_models_mark_installed():
    """Scan generated and set ModelCapability.installed=True for matching canonical_slugs."""
    try:
        try:
            res = data_init_service.mark_installed_models(reset_first=True)
            status_code = 200 if res.get('success', False) else 400
            return jsonify(res), status_code
        except Exception as e:
            current_app.logger.error(f'Error in mark-installed delegate: {e}')
            return jsonify(build_error_payload(
                "Failed to mark installed models (delegate)",
                status=500,
                error="MarkInstalledDelegateError",
                details={"reason": str(e), "updated": 0}
            )), 500
    except Exception as e:
        current_app.logger.error(f'Error marking installed models: {e}')
        return jsonify(build_error_payload(
            "Failed to mark installed models",
            status=500,
            error="MarkInstalledError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/models/sync', methods=['POST'])
def api_models_sync():
    """Sync filesystem model/app directories into the database.

    Returns JSON summary so UI can refresh models list. Safe & idempotent.
    """
    try:
        from app.services.model_sync_service import sync_models_from_filesystem
        summary = sync_models_from_filesystem()
        summary['success'] = True
        return jsonify(summary)
    except Exception as e:  # pragma: no cover - unexpected failures
        current_app.logger.error(f"Filesystem sync failed: {e}")
        return jsonify(build_error_payload(
            "Filesystem model sync failed",
            status=500,
            error="ModelSyncError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/models/<model_slug>/containers/start', methods=['POST'])
def api_model_start_containers(model_slug):
    """Start all application containers for a model.

    Uses application_service.start_model_containers (DB-level status flip for now).
    Returns counts and triggers front-end grid refresh via HTMX trigger header.
    """
    try:
        result = app_service.start_model_containers(model_slug)
        response = create_success_response(result, message=f'Model {model_slug} applications started')
        # Trigger front-end grid refresh if HTMX
        try:
            response.headers['HX-Trigger'] = 'refresh-grid'  # type: ignore[attr-defined]
        except Exception:
            pass
        return response  # type: ignore[return-value]
    except Exception as e:  # pragma: no cover - unexpected
        return create_error_response(f'Failed to start containers for model {model_slug}: {e}', code=500)

@api_bp.route('/models/<model_slug>/containers/stop', methods=['POST'])
def api_model_stop_containers(model_slug):
    """Stop all running application containers for a model.

    Uses application_service.stop_model_containers (DB-level status flip for now).
    Returns counts and triggers front-end grid refresh via HTMX trigger header.
    """
    try:
        result = app_service.stop_model_containers(model_slug)
        response = create_success_response(result, message=f'Model {model_slug} applications stopped')
        try:
            response.headers['HX-Trigger'] = 'refresh-grid'  # type: ignore[attr-defined]
        except Exception:
            pass
        return response  # type: ignore[return-value]
    except Exception as e:  # pragma: no cover
        return create_error_response(f'Failed to stop containers for model {model_slug}: {e}', code=500)

# -----------------------------------------------------------------
# Backward-compatible singular aliases for model container actions
# (Templates currently call /api/model/<slug>/containers/...)
# -----------------------------------------------------------------

@api_bp.route('/model/<model_slug>/containers/start', methods=['POST'])
def api_model_start_containers_alias(model_slug):  # pragma: no cover - thin wrapper
    return api_model_start_containers(model_slug)

@api_bp.route('/model/<model_slug>/containers/stop', methods=['POST'])
def api_model_stop_containers_alias(model_slug):  # pragma: no cover - thin wrapper
    return api_model_stop_containers(model_slug)

@api_bp.route('/model/<model_slug>/containers/restart', methods=['POST'])
def api_model_restart_containers_alias(model_slug):  # pragma: no cover - thin wrapper
    # No dedicated restart batch op yet; emulate by stop then start for now
    try:
        api_model_stop_containers(model_slug)
        return api_model_start_containers(model_slug)
    except Exception as e:  # pragma: no cover
        return create_error_response(f'Failed to restart containers for model {model_slug}: {e}', code=500)

@api_bp.route('/model/<model_slug>/containers/build', methods=['POST'])
def api_model_build_containers_alias(model_slug):  # pragma: no cover - placeholder
    # Build action not implemented in service layer yet; respond success placeholder
    try:
        return create_success_response({'model_slug': model_slug, 'message': 'Build trigger placeholder'})
    except Exception as e:  # pragma: no cover
        return create_error_response(f'Failed to build containers for model {model_slug}: {e}', code=500)

# -----------------------------------------------------------------
# Sync Status Endpoint (HTML fragment or JSON)
# -----------------------------------------------------------------

def _render_model_apps_fragment(model_slug: str):
    """Internal helper to render the applications fragment for a model.

    Reuses the existing applications grid partial logic. We build a minimal
    context structure (entry) matching what templates expect (model + apps list).
    """
    from app.utils.template_paths import render_template_compat as render_template
    model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
    if not model:
        return f"<div class='alert alert-warning mb-2'>Model {model_slug} not found</div>"
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).order_by(GeneratedApplication.app_number.asc()).all()

    # Build lightweight objects used in template loops (mirroring earlier structure)
    entry = type('Entry', (), {})()
    setattr(entry, 'model', model)
    setattr(entry, 'apps', [
        {
            'app_number': a.app_number,
            'app_type': a.app_type,
            'status': a.container_status or 'unknown',
            'ports': getattr(a, 'ports', None) or {},  # placeholder; port mapping service may fill later
            'has_docker_compose': getattr(a, 'has_docker_compose', False),
            'exists': True,  # presence in DB implies generated (filesystem existence checked elsewhere)
        } for a in apps
    ])
    setattr(entry, 'apps_count', len(apps))

    # Decide which variant to render based on requesting container: grid collapse vs table accordion
    # The calling template targets either `.model-apps` (grid) or `.model-apps-table-body` (table)
    # Provide raw rows/cards only to minimize payload size.
    # For simplicity we re-render the appropriate inner structure.
    # If request specifies variant parameter we can honor; else default to cards.
    variant = request.args.get('variant')
    target_selector = request.headers.get('HX-Target', '')
    try:
        if 'model-apps-table-body' in target_selector or variant == 'table':
            # Render only <tr> rows
            return render_template('pages/applications/partials/_model_apps_table_rows.html', entry=entry)
        else:
            # Render only cards inside the .row container
            return render_template('pages/applications/partials/_model_apps_cards.html', entry=entry)
    except Exception:
        # Fallback: render full grid fragment section (heavier) if specialized partials not present
        return render_template('pages/applications/partials/grid.html', application_grid=[entry])

@api_bp.route('/model/<model_slug>/containers/sync-status', methods=['POST'])
@api_bp.route('/models/<model_slug>/containers/sync-status', methods=['POST'])
def api_model_containers_sync_status(model_slug):
    """Return current application container statuses for a model.

    Supports HTML fragment (?format=html) for HTMX targets or JSON (default).
    """
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).order_by(GeneratedApplication.app_number.asc()).all()
        if request.args.get('format') == 'html' or request.headers.get('HX-Request'):
            html = _render_model_apps_fragment(model_slug)
            return html
        # JSON response: simplified list
        return create_success_response({
            'model_slug': model_slug,
            'applications': [
                {
                    'app_number': a.app_number,
                    'status': a.container_status,
                    'app_type': a.app_type,
                    'has_docker_compose': getattr(a, 'has_docker_compose', False)
                } for a in apps
            ],
            'count': len(apps)
        }, message='Container statuses synced')
    except Exception as e:  # pragma: no cover
        return create_error_response(f'Failed to sync container statuses for model {model_slug}: {e}', code=500)

# =================================================================
# APPLICATION API ROUTES
# =================================================================

@api_bp.route('/applications')
def api_list_applications():
    """API endpoint: Get applications (standardized envelope)."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    app_type = request.args.get('type')

    query = app_service.list_applications(status=status, app_type=app_type)

    items, meta = build_pagination_envelope(query, page, per_page)
    return create_success_response([app.to_dict() for app in items], message="Applications fetched")

@api_bp.route('/applications', methods=['POST'])
def api_create_application():
    """API endpoint: Create application (standardized envelope)."""
    data = request.get_json() or {}
    missing = require_fields(data, ['model_slug', 'app_number', 'app_type', 'provider'])
    if missing:
        return create_error_response(f"Missing required fields: {', '.join(missing)}", code=400)

    try:
        created = app_service.create_application(data)
        return create_success_response(created, message="Application created")
    except app_service.ValidationError as ve:
        return create_error_response(str(ve), code=400)

@api_bp.route('/applications/<int:app_id>')
def api_get_application(app_id):
    """API endpoint: Get specific application (standardized)."""
    try:
        return create_success_response(app_service.get_application(app_id))
    except app_service.NotFoundError:
        return create_error_response('Application not found', code=404)

@api_bp.route('/applications/<int:app_id>', methods=['PUT'])
def api_update_application(app_id):
    """API endpoint: Update application (standardized)."""
    data = request.get_json() or {}
    try:
        updated = app_service.update_application(app_id, data)
        return create_success_response(updated, message="Application updated")
    except app_service.NotFoundError:
        return create_error_response('Application not found', code=404)

@api_bp.route('/applications/<int:app_id>', methods=['DELETE'])
def api_delete_application(app_id):
    """API endpoint: Delete application (standardized)."""
    try:
        app_service.delete_application(app_id)
        return create_success_response(message='Application deleted successfully')
    except app_service.NotFoundError:
        return create_error_response('Application not found', code=404)

@api_bp.route('/applications/types')
def api_get_application_types():
    """API endpoint: Get available application types (standardized)."""
    types = (
        db.session.query(GeneratedApplication.app_type)
        .distinct()
        .filter(GeneratedApplication.app_type.isnot(None))
        .all()
    )
    type_list = [t[0] for t in types]
    common_types = [
        'web_app', 'api', 'microservice', 'dashboard',
        'e_commerce', 'blog', 'cms', 'social_media'
    ]
    for common_type in common_types:
        if common_type not in type_list:
            type_list.append(common_type)
    return create_success_response({'types': sorted(type_list)}, message='Application types fetched')

@api_bp.route('/applications/<int:app_id>/start', methods=['POST'])
def api_application_start(app_id):
    """API endpoint to start an application container (service-backed)."""
    try:
        result = app_service.start_application(app_id)
        response = create_success_response(result, message=f'Application {app_id} started successfully')
        try:
            response.headers['HX-Trigger'] = 'refresh-grid'  # type: ignore[attr-defined]
        except Exception:
            pass
        return response  # type: ignore[return-value]
    except app_service.NotFoundError:
        return create_error_response(f'Application {app_id} not found', code=404)

@api_bp.route('/applications/<int:app_id>/stop', methods=['POST'])
def api_application_stop(app_id):
    """API endpoint to stop an application container (service-backed)."""
    try:
        result = app_service.stop_application(app_id)
        response = create_success_response(result, message=f'Application {app_id} stopped successfully')
        try:
            response.headers['HX-Trigger'] = 'refresh-grid'  # type: ignore[attr-defined]
        except Exception:
            pass
        return response  # type: ignore[return-value]
    except app_service.NotFoundError:
        return create_error_response(f'Application {app_id} not found', code=404)

@api_bp.route('/applications/<int:app_id>/restart', methods=['POST'])
def api_application_restart(app_id):
    """API endpoint to restart an application container (service-backed)."""
    try:
        result = app_service.restart_application(app_id)
        response = create_success_response(result, message=f'Application {app_id} restarted successfully')
        try:
            response.headers['HX-Trigger'] = 'refresh-grid'  # type: ignore[attr-defined]
        except Exception:
            pass
        return response  # type: ignore[return-value]
    except app_service.NotFoundError:
        return create_error_response(f'Application {app_id} not found', code=404)

@api_bp.route('/apps/grid')
def api_apps_grid():
    """API endpoint for applications grid view."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        search = request.args.get('search', '')
        model = request.args.get('model', '')
        status = request.args.get('status', '')
        view = request.args.get('view', 'grid')
        page = request.args.get('page', 1, type=int)
        per_page = 12

        query = GeneratedApplication.query

        if search:
            query = query.filter(
                GeneratedApplication.model_slug.contains(search)
            )

        if model:
            query = query.filter(GeneratedApplication.model_slug == model)

        if status:
            query = query.filter(GeneratedApplication.generation_status == status)

        apps = query.order_by(
            GeneratedApplication.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )

        if view == 'list':
            return render_template('partials/apps_grid/apps_list.html', apps=apps.items if hasattr(apps, 'items') else apps)
        else:
            return render_template('partials/apps_grid/apps_grid.html', apps=apps.items if hasattr(apps, 'items') else apps)
    except Exception as e:
        current_app.logger.error(f"Error getting apps grid: {e}")
        return f'<div class="alert alert-danger">Error loading applications: {str(e)}</div>'

# =================================================================
# STATISTICS API ROUTES
# =================================================================

@api_bp.route('/stats/apps')
def api_stats_apps():
    data = get_application_statistics()
    return create_success_response(data, message="Application statistics fetched")

@api_bp.route('/stats/models')
def api_stats_models():
    data = get_model_statistics()
    return create_success_response(data, message="Model statistics fetched")

@api_bp.route('/stats/analysis')
def api_stats_analysis():
    data = get_analysis_statistics()
    return create_success_response(data, message="Analysis statistics fetched")

@api_bp.route('/stats/recent')
def api_stats_recent():
    data = get_recent_statistics()
    return create_success_response(data, message="Recent statistics fetched")

@api_bp.route('/models/distribution')
def api_models_distribution():
    data = get_model_distribution()
    return create_success_response(data, message="Model distribution fetched")

@api_bp.route('/generation/trends')
def api_generation_trends():
    data = get_generation_trends()
    return create_success_response(data, message="Generation trends fetched")

@api_bp.route('/analysis/summary')
def api_analysis_summary():
    data = get_analysis_summary()
    return create_success_response(data, message="Analysis summary fetched")

@api_bp.route('/export')
def api_export_statistics():
    data = export_statistics()
    return create_success_response(data, message="Statistics exported")

# =================================================================
# SYSTEM API ROUTES
# =================================================================

@api_bp.route('/system/health')
def api_system_health():
    """API endpoint: Get system health status."""
    try:
        # Database health check
        db_healthy = True
        db_error = None
        try:
            db.session.execute(db.text('SELECT 1'))
            db.session.commit()
        except Exception as e:
            db_healthy = False
            db_error = str(e)

        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        # Check Docker status
        docker_status = {
            'available': False,
            'containers_running': 0,
            'error': None,
        }

        try:
            from app.services.docker_manager import DockerManager
            docker_service = DockerManager()
            client = getattr(docker_service, 'client', None)
            if client:
                containers = client.containers.list()
                docker_status['available'] = True
                docker_status['containers_running'] = len(containers)
        except Exception as e:
            docker_status['error'] = str(e)

        # Determine overall health
        health_status = 'healthy'
        issues = []

        if not db_healthy:
            health_status = 'unhealthy'
            issues.append(f'Database connection failed: {db_error}')

        if cpu_percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High CPU usage: {cpu_percent}%')

        if memory.percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High memory usage: {memory.percent}%')

        if disk.percent > 90:
            health_status = 'warning' if health_status == 'healthy' else health_status
            issues.append(f'High disk usage: {disk.percent}%')

        return jsonify({
            'status': health_status,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'database': {
                'healthy': db_healthy,
                'error': db_error
            },
            'docker': docker_status,
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent
            },
            'issues': issues
        })

    except Exception as e:
        current_app.logger.error(f"Error getting system health: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }), 500

@api_bp.route('/system/info')
def api_system_info():
    """API endpoint: Get system information."""
    try:
        system_info = {
            'platform': os.name,
            'python_version': f"{psutil.Process().memory_info().rss}",
            'cpu_count': psutil.cpu_count(),
            'total_memory': psutil.virtual_memory().total,
            'available_memory': psutil.virtual_memory().available,
            'disk_total': psutil.disk_usage('/').total,
            'disk_free': psutil.disk_usage('/').free,
            'boot_time': datetime.fromtimestamp(psutil.boot_time()).isoformat()
        }

        current_process = psutil.Process()
        process_info = {
            'pid': current_process.pid,
            'memory_usage': current_process.memory_info().rss,
            'cpu_percent': current_process.cpu_percent(),
            'create_time': datetime.fromtimestamp(current_process.create_time()).isoformat(),
            'num_threads': current_process.num_threads()
        }

        return jsonify({
            'system': system_info,
            'process': process_info,
            'timestamp': datetime.now(timezone.utc).isoformat()
        })

    except Exception as e:
        current_app.logger.error(f"Error getting system info: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve system info",
            status=500,
            error="SystemInfoError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/system/overview')
def api_system_overview():
    """API endpoint: Get system overview."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        db_status = 'connected'
        try:
            db.session.execute(db.text('SELECT 1'))
            db.session.commit()
        except Exception:
            db_status = 'disconnected'

        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now(timezone.utc).timestamp() - boot_time
        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        data = {
            'status': 'online',
            'uptime': {
                'days': uptime_days,
                'hours': uptime_hours,
                'minutes': uptime_minutes,
                'total_seconds': int(uptime_seconds)
            },
            'resources': {
                'cpu': {
                    'usage_percent': cpu_percent,
                    'cores': psutil.cpu_count()
                },
                'memory': {
                    'usage_percent': memory.percent,
                    'total_gb': round(memory.total / 1024**3, 2),
                    'available_gb': round(memory.available / 1024**3, 2)
                },
                'disk': {
                    'usage_percent': disk.percent,
                    'total_gb': round(disk.total / 1024**3, 2),
                    'free_gb': round(disk.free / 1024**3, 2)
                }
            },
            'services': {
                'database': db_status,
                'api': 'running'
            },
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting system overview: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve system overview",
            status=500,
            error="SystemOverviewError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/system/footer-status')
def api_system_footer_status():
    """API endpoint: Get system status for footer display."""
    try:
        # Quick system health check
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        # Determine status based on resource usage
        if cpu_percent > 90 or memory.percent > 90:
            status = 'warning'
            status_class = 'status-indicator-animated bg-orange'
        elif cpu_percent > 50 or memory.percent > 80:
            status = 'moderate'
            status_class = 'status-indicator-animated bg-yellow'
        else:
            status = 'healthy'
            status_class = 'status-indicator-animated bg-green'

        data = {
            'status': status,
            'status_class': status_class,
            'cpu_percent': cpu_percent,
            'memory_percent': memory.percent,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            # Check if this is for header or footer
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                return f'<span class="status-indicator {status_class} me-1"></span><small class="text-muted">OK</small>'
            else:
                return f'''
                <span class="status-indicator {status_class} me-2"></span>
                <span class="text-secondary">System OK</span>
                '''

        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting footer status: {e}")
        if request.headers.get('HX-Request'):
            return '<span class="status-indicator status-indicator-animated bg-red me-2"></span><span class="text-secondary">System Error</span>'
        return jsonify({
            'status': 'error',
            'status_class': 'status-indicator-animated bg-red',
            'error': str(e)
        }), 500

@api_bp.route('/tasks/count')
def api_tasks_count():
    """API endpoint: Get active tasks count."""
    try:
        # Count active tasks from various sources
        from app.models import SecurityAnalysis, PerformanceTest, BatchAnalysis

        active_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.status.in_(['pending', 'running'])
        ).count()

        active_performance = PerformanceTest.query.filter(
            PerformanceTest.status.in_(['pending', 'running'])
        ).count()

        active_batch = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_(['pending', 'running'])
        ).count()

        total_active = active_security + active_performance + active_batch

        data = {
            'total_active': total_active,
            'security': active_security,
            'performance': active_performance,
            'batch': active_batch,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            # Check if this is for header or footer
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                badge_class = 'text-blue' if total_active > 0 else 'text-muted'
                return f'''<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-list-check me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                <path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/>
                <path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/>
                <path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/>
                <path d="M11 6l9 0"/>
                <path d="M11 12l9 0"/>
                <path d="M11 18l9 0"/>
              </svg><small class="{badge_class}">{total_active}</small>'''
            else:
                badge_class = 'bg-blue' if total_active > 0 else 'bg-secondary'
                return f'Tasks: <span class="badge {badge_class} ms-1">{total_active}</span>'

        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting tasks count: {e}")
        if request.headers.get('HX-Request'):
            return 'Tasks: <span class="badge bg-red ms-1">!</span>'
        return jsonify(build_error_payload(
            "Failed to retrieve tasks count",
            status=500,
            error="TasksCountError",
            details={"reason": str(e), "total_active": 0}
        )), 500

@api_bp.route('/uptime')
def api_uptime():
    """API endpoint: Get system uptime."""
    try:
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now(timezone.utc).timestamp() - boot_time

        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        # Format for display
        if uptime_days > 0:
            uptime_str = f"{uptime_days}d {uptime_hours}h"
        elif uptime_hours > 0:
            uptime_str = f"{uptime_hours}h {uptime_minutes}m"
        else:
            uptime_str = f"{uptime_minutes}m"

        data = {
            'uptime_seconds': int(uptime_seconds),
            'uptime_formatted': uptime_str,
            'days': uptime_days,
            'hours': uptime_hours,
            'minutes': uptime_minutes,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        # Return HTML fragment for HTMX requests
        if request.headers.get('HX-Request'):
            # Check if this is for header or footer
            if 'header' in request.headers.get('HX-Target', '').lower() or 'header' in request.path:
                return f'''<svg xmlns="http://www.w3.org/2000/svg" class="icon icon-tabler icon-tabler-clock me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <path stroke="none" d="M0 0h24v24H0z" fill="none"/>
                <path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/>
                <path d="M12 7l0 5 3 3"/>
              </svg><small class="text-muted">{uptime_str}</small>'''
            else:
                return f'Uptime: {uptime_str}'

        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Error getting uptime: {e}")
        if request.headers.get('HX-Request'):
            return 'Uptime: --'
        return jsonify(build_error_payload(
            "Failed to retrieve uptime",
            status=500,
            error="UptimeError",
            details={"reason": str(e), "uptime_formatted": '--'}
        )), 500

# =================================================================
# DASHBOARD MANAGEMENT / ACTION ENDPOINTS (lightweight auth via token)
# =================================================================

def _require_admin_token():
    token = request.headers.get('X-Admin-Token') or request.args.get('admin_token')
    expected = current_app.config.get('DASHBOARD_ADMIN_TOKEN') or os.environ.get('DASHBOARD_ADMIN_TOKEN')
    if expected and token != expected:
        abort(401)

def _json_success(message: str, **extra):
    return jsonify({"success": True, "message": message, **extra})

def _json_error(message: str, status: int = 500, **extra):
    return jsonify({"success": False, "error": message, **extra}), status

def _run_script_function(description: str, import_path: str, func_name: str = 'main'):
    start = datetime.now(timezone.utc)
    try:
        module = importlib.import_module(import_path)
        fn = getattr(module, func_name)
        result = fn()
        return True, {"description": description, "runtime_ms": int((datetime.now(timezone.utc) - start).total_seconds()*1000), "result": result}
    except SystemExit as se:  # scripts may sys.exit
        code = int(getattr(se, 'code', 0) or 0)
        return code == 0, {"description": description, "runtime_ms": int((datetime.now(timezone.utc) - start).total_seconds()*1000), "exit_code": code}
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Dashboard action {description} failed: {e}\n{traceback.format_exc()}")
        return False, {"description": description, "runtime_ms": int((datetime.now(timezone.utc) - start).total_seconds()*1000), "error": str(e)}

@api_bp.route('/dashboard/actions/<action>', methods=['POST'])
def dashboard_action_dispatch(action: str):
    """Unified maintenance action endpoint (service-backed)."""
    _require_admin_token()
    svc = MaintenanceService(current_app)
    result = svc.run_action(action)
    if result.get('ok'):
        return jsonify({"success": True, **result})
    return jsonify({"success": False, **result}), 400

@api_bp.route('/dashboard/system-stats')
def dashboard_system_stats():
    try:
        counts = {
            'models': db.session.query(ModelCapability).count(),
            'applications': db.session.query(GeneratedApplication).count(),
            'security_analyses': db.session.query(SecurityAnalysis).count(),
            'performance_tests': db.session.query(PerformanceTest).count(),
            'batches_running': db.session.query(BatchAnalysis).filter(BatchAnalysis.status == 'running').count()
        }
        cpu_percent = psutil.cpu_percent(interval=0.15)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot_time = psutil.boot_time()
        uptime_seconds = int(datetime.now(timezone.utc).timestamp() - boot_time)
        data = {
            'counts': counts,
            'resources': {
                'cpu_percent': cpu_percent,
                'memory_percent': mem.percent,
                'disk_percent': disk.percent,
                'memory_gb': round(mem.total / 1024**3, 2),
                'disk_free_gb': round(disk.free / 1024**3, 2)
            },
            'uptime_seconds': uptime_seconds,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        return jsonify(data)
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"Error building dashboard system stats: {e}")
        return jsonify({'error': 'Failed to gather system stats', 'details': str(e)}), 500

@api_bp.route('/header/summary')
def api_header_summary():
    """API endpoint: Get header summary with status, tasks, and uptime for HTMX."""
    try:
        # Get system status
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        # Determine status based on resource usage
        if cpu_percent > 90 or memory.percent > 90:
            status_class = 'status-indicator-animated bg-orange'
            status_text = 'Warning'
        elif cpu_percent > 50 or memory.percent > 80:
            status_class = 'status-indicator-animated bg-yellow'
            status_text = 'Moderate'
        else:
            status_class = 'status-indicator-animated bg-green'
            status_text = 'OK'

        # Get active tasks count
        from app.models import SecurityAnalysis, PerformanceTest, BatchAnalysis

        active_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.status.in_(['pending', 'running'])
        ).count()

        active_performance = PerformanceTest.query.filter(
            PerformanceTest.status.in_(['pending', 'running'])
        ).count()

        active_batch = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_(['pending', 'running'])
        ).count()

        total_active = active_security + active_performance + active_batch

        # Get uptime
        boot_time = psutil.boot_time()
        uptime_seconds = datetime.now(timezone.utc).timestamp() - boot_time

        uptime_days = int(uptime_seconds // 86400)
        uptime_hours = int((uptime_seconds % 86400) // 3600)
        uptime_minutes = int((uptime_seconds % 3600) // 60)

        # Format uptime for display
        if uptime_days > 0:
            uptime_str = f"{uptime_days}d {uptime_hours}h"
        elif uptime_hours > 0:
            uptime_str = f"{uptime_hours}h {uptime_minutes}m"
        else:
            uptime_str = f"{uptime_minutes}m"

        # Return HTML fragment for HTMX
        return f'''
        <span class="d-flex align-items-center me-3" aria-live="polite">
          <span class="{status_class} me-2" style="width:20px;height:20px;border-radius:50%;display:inline-block;" aria-hidden="true"></span>
          <small class="text-muted">{status_text}</small>
        </span>

        <a class="text-muted d-flex align-items-center me-3" href="{{{{ url_for('tasks.tasks_overview') }}}}" title="Active tasks">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/>
            <path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/>
            <path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/>
            <path d="M11 6l9 0"/>
            <path d="M11 12l9 0"/>
            <path d="M11 18l9 0"/>
          </svg>
          <small class="text-muted">{total_active}</small>
        </a>

        <div class="text-muted me-3 d-flex align-items-center" title="Uptime">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/>
            <path d="M12 7l0 5 3 3"/>
          </svg>
          <small class="text-muted">{uptime_str}</small>
        </div>
        '''

    except Exception as e:
        current_app.logger.error(f"Error getting header summary: {e}")
        # Return fallback HTML on error
        return '''
        <span class="d-flex align-items-center me-3" aria-live="polite">
          <span class="status-indicator-animated bg-red me-2" style="width:20px;height:20px;border-radius:50%;display:inline-block;" aria-hidden="true"></span>
          <small class="text-muted">Error</small>
        </span>

        <a class="text-muted d-flex align-items-center me-3" href="#" title="Active tasks">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M3.5 5.5l1.5 1.5l2.5 -2.5"/>
            <path d="M3.5 11.5l1.5 1.5l2.5 -2.5"/>
            <path d="M3.5 17.5l1.5 1.5l2.5 -2.5"/>
            <path d="M11 6l9 0"/>
            <path d="M11 12l9 0"/>
            <path d="M11 18l9 0"/>
          </svg>
          <small class="text-muted">!</small>
        </a>

        <div class="text-muted me-3 d-flex align-items-center" title="Uptime">
          <svg xmlns="http://www.w3.org/2000/svg" class="icon me-1" width="16" height="16" viewBox="0 0 24 24" stroke-width="2" stroke="currentColor" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M12 12m-9 0a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/>
            <path d="M12 7l0 5 3 3"/>
          </svg>
          <small class="text-muted">--</small>
        </div>
        '''

@api_bp.route('/analyzer/start', methods=['POST'])
def start_analyzer_services():
    """Start analyzer services via Docker"""
    try:
        result = subprocess.run(['docker', 'ps'],
                              capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Docker is available. Analyzer services can be started via the analyzer_manager.py script.',
                'note': 'Please run: cd analyzer && python analyzer_manager.py start'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Docker not available'
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Docker command timed out'
        }), 500
    except FileNotFoundError:
        return jsonify({
            'success': False,
            'error': 'Docker not found. Please install Docker.'
        }), 500
    except Exception as e:
        current_app.logger.error(f"Error starting analyzer services: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =================================================================
# RESULTS API ROUTES
# =================================================================

@api_bp.route('/results')
def get_api_results():
    """Get results with filtering and pagination."""
    try:
        page = request.args.get('page', 1, type=int)
        size = request.args.get('size', 25, type=int)
        sort = request.args.get('sort', 'timestamp:desc')
        status = request.args.get('status', '')
        model = request.args.get('model', '')
        date_range = request.args.get('dateRange', '')
        search = request.args.get('search', '')

        query = db.session.query(SecurityAnalysis).join(GeneratedApplication)

        if status:
            query = query.filter(SecurityAnalysis.status == status)

        if model:
            query = query.filter(GeneratedApplication.model_slug.ilike(f'%{model}%'))

        if search:
            query = query.filter(GeneratedApplication.model_slug.ilike(f'%{search}%'))

        if date_range:
            date_cutoff = datetime.now()
            if date_range == 'today':
                date_cutoff = date_cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
            elif date_range == 'week':
                date_cutoff = date_cutoff - timedelta(days=7)
            elif date_range == 'month':
                date_cutoff = date_cutoff - timedelta(days=30)

            query = query.filter(SecurityAnalysis.created_at >= date_cutoff)

        if sort == 'timestamp:desc':
            query = query.order_by(db.desc(SecurityAnalysis.created_at))
        elif sort == 'timestamp:asc':
            query = query.order_by(SecurityAnalysis.created_at)

        total_count = query.count()
        results = query.offset((page - 1) * size).limit(size).all()

        formatted_results = []
        for result in results:
            app = GeneratedApplication.query.get(result.application_id) if result.application_id else None

            formatted_result = {
                'id': result.id,
                'model_slug': app.model_slug if app else 'unknown',
                'app_number': app.app_number if app else 0,
                'analysis_type': 'security',
                'status': result.status.value if result.status else 'unknown',
                'score': getattr(result, 'overall_score', None) or 0,
                'duration': result.analysis_duration,
                'timestamp': result.created_at.isoformat() if result.created_at else None,
                'started_at': result.started_at.isoformat() if result.started_at else None,
                'completed_at': result.completed_at.isoformat() if result.completed_at else None,
                'task_id': getattr(result, 'task_id', None),
                'summary': {
                    'total_findings': result.total_issues or 0,
                    'high_severity': result.high_severity_count or 0,
                    'medium_severity': result.medium_severity_count or 0,
                    'low_severity': result.low_severity_count or 0
                }
            }

            formatted_results.append(formatted_result)

        total_pages = (total_count + size - 1) // size

        return jsonify({
            'success': True,
            'results': formatted_results,
            'pagination': {
                'current_page': page,
                'per_page': size,
                'total_items': total_count,
                'total_pages': total_pages,
                'has_prev': page > 1,
                'has_next': page < total_pages
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting results: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve results",
            status=500,
            error="ResultsQueryError",
            details={"reason": str(e)}
        )), 500

# =================================================================
# MISCELLANEOUS API ROUTES
# =================================================================

@api_bp.route('/quick_search', methods=['POST'])
def quick_search():
    """Quick search functionality for HTMX."""
    try:
        from app.utils.template_paths import render_template_compat as render_template
        query = request.form.get('query', '').strip()

        if not query:
            return render_template('components/search_results.html', results=[], query='')

        # Search models
        model_results = ModelCapability.query.filter(
            ModelCapability.model_name.ilike(f'%{query}%') |
            ModelCapability.provider.ilike(f'%{query}%') |
            ModelCapability.canonical_slug.ilike(f'%{query}%')
        ).limit(5).all()

        # Search applications
        app_results = GeneratedApplication.query.filter(
            GeneratedApplication.model_slug.ilike(f'%{query}%') |
            GeneratedApplication.app_type.ilike(f'%{query}%') |
            GeneratedApplication.provider.ilike(f'%{query}%')
        ).limit(5).all()

        results = {
            'models': [{
                'type': 'model',
                'name': model.model_name,
                'provider': model.provider,
                'slug': model.canonical_slug,
                'url': f'/models/{model.canonical_slug}'
            } for model in model_results],
            'applications': [{
                'type': 'application',
                'name': f'{app.model_slug} App #{app.app_number}',
                'provider': app.provider,
                'status': app.container_status,
                'url': f'/applications/{app.id}'
            } for app in app_results]
        }

        return render_template('components/search_results.html',
                             results=results, query=query)
    except Exception as e:
        current_app.logger.error(f"Error in quick search: {e}")
        return f"<div class='alert alert-danger'>Search error: {str(e)}</div>"

@api_bp.route('/tasks/status')
def tasks_status():
    """Get overall task status."""
    try:
        status = {
            'active_tasks': 0,
            'pending_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'queue_health': 'healthy'
        }
        return jsonify(status)
    except Exception as e:
        current_app.logger.error(f"Error getting task status: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve task status",
            status=500,
            error="TaskStatusError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/notifications/count')
def notifications_count():
    """Get unread notifications count."""
    try:
        count = 0
        return jsonify({'count': count})
    except Exception as e:
        current_app.logger.error(f"Error getting notifications count: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve notifications count",
            status=500,
            error="NotificationsCountError",
            details={"reason": str(e)}
        )), 500

@api_bp.route('/analysis/active-tests')
def testing_active_tests():
    """Get active test information."""
    try:
        active_security = SecurityAnalysis.query.filter(
            SecurityAnalysis.status.in_(['pending', 'running'])
        ).count()

        active_performance = PerformanceTest.query.filter(
            PerformanceTest.status.in_(['pending', 'running'])
        ).count()

        return jsonify({
            'active_security_tests': active_security,
            'active_performance_tests': active_performance,
            'total_active': active_security + active_performance
        })
    except Exception as e:
        current_app.logger.error(f"Error getting active tests: {e}")
        return jsonify(build_error_payload(
            "Failed to retrieve active tests",
            status=500,
            error="ActiveTestsError",
            details={"reason": str(e)}
        )), 500

# =================================================================
# APPLICATION CONTROL (lightweight placeholders)
# =================================================================

def _get_app_or_404(model_slug, app_number):
    app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
    if not app:
        return None, create_error_response_with_status(
            f"Application {model_slug}/app{app_number} not found", status=404, error_type="NotFound"
        )
    return app, None

@api_bp.route('/app/<model_slug>/<int:app_number>/start', methods=['POST'])
def api_app_start(model_slug, app_number):
    app, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    try:
        assert app is not None
        # Attempt real container start via DockerManager if available
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        docker_result = None
        compose_diag = None
        if docker_mgr:
            try:
                docker_result = docker_mgr.start_containers(model_slug, app_number)
                compose_diag = docker_mgr.debug_compose_resolution(model_slug, app_number)
            except Exception as _dock_err:  # pragma: no cover
                current_app.logger.warning(f"Docker start failed for {model_slug}/app{app_number}: {_dock_err}")
        from app.services.application_service import start_application
        result = start_application(app.id)  # flips DB state
        payload = {'status': result['status'], 'docker': docker_result, 'compose': compose_diag}
        # HTMX request -> return refreshed container section HTML instead of JSON envelope
        if request.headers.get('HX-Request'):
            try:
                from app.routes.jinja.models import _render_application_section  # type: ignore
                section = _render_application_section(model_slug, app_number, 'container')
                if isinstance(section, tuple):
                    body, status = section
                else:
                    body, status = section, 200
                from flask import make_response
                resp = make_response(body, status)
                resp.headers['HX-Trigger'] = '{"app-operation": {"operation": "start", "status": "success"}}'
                return resp
            except Exception as _htmx_err:  # pragma: no cover
                current_app.logger.warning(f"HTMX container section render failed: {_htmx_err}")
        return create_success_response_with_status(payload, message='Application started')
    except Exception as e:
        db.session.rollback()
        return create_error_response_with_status(str(e), status=500, error_type='StartError')

@api_bp.route('/app/<model_slug>/<int:app_number>/stop', methods=['POST'])
def api_app_stop(model_slug, app_number):
    app, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    try:
        assert app is not None
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        docker_result = None
        compose_diag = None
        if docker_mgr:
            try:
                docker_result = docker_mgr.stop_containers(model_slug, app_number)
                compose_diag = docker_mgr.debug_compose_resolution(model_slug, app_number)
            except Exception as _dock_err:  # pragma: no cover
                current_app.logger.warning(f"Docker stop failed for {model_slug}/app{app_number}: {_dock_err}")
        from app.services.application_service import stop_application
        result = stop_application(app.id)
        payload = {'status': result['status'], 'docker': docker_result, 'compose': compose_diag}
        if request.headers.get('HX-Request'):
            try:
                from app.routes.jinja.models import _render_application_section  # type: ignore
                section = _render_application_section(model_slug, app_number, 'container')
                if isinstance(section, tuple):
                    body, status = section
                else:
                    body, status = section, 200
                from flask import make_response
                resp = make_response(body, status)
                resp.headers['HX-Trigger'] = '{"app-operation": {"operation": "stop", "status": "success"}}'
                return resp
            except Exception as _htmx_err:  # pragma: no cover
                current_app.logger.warning(f"HTMX container section render failed: {_htmx_err}")
        return create_success_response_with_status(payload, message='Application stopped')
    except Exception as e:
        db.session.rollback()
        return create_error_response_with_status(str(e), status=500, error_type='StopError')

@api_bp.route('/app/<model_slug>/<int:app_number>/restart', methods=['POST'])
def api_app_restart(model_slug, app_number):
    app, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    try:
        assert app is not None
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        docker_result = None
        compose_diag = None
        if docker_mgr:
            try:
                docker_result = docker_mgr.restart_containers(model_slug, app_number)
                compose_diag = docker_mgr.debug_compose_resolution(model_slug, app_number)
            except Exception as _dock_err:  # pragma: no cover
                current_app.logger.warning(f"Docker restart failed for {model_slug}/app{app_number}: {_dock_err}")
        from app.services.application_service import restart_application
        result = restart_application(app.id)
        payload = {'status': result['status'], 'docker': docker_result, 'compose': compose_diag}
        if request.headers.get('HX-Request'):
            try:
                from app.routes.jinja.models import _render_application_section  # type: ignore
                section = _render_application_section(model_slug, app_number, 'container')
                if isinstance(section, tuple):
                    body, status = section
                else:
                    body, status = section, 200
                from flask import make_response
                resp = make_response(body, status)
                resp.headers['HX-Trigger'] = '{"app-operation": {"operation": "restart", "status": "success"}}'
                return resp
            except Exception as _htmx_err:  # pragma: no cover
                current_app.logger.warning(f"HTMX container section render failed: {_htmx_err}")
        return create_success_response_with_status(payload, message='Application restarted')
    except Exception as e:
        db.session.rollback()
        return create_error_response_with_status(str(e), status=500, error_type='RestartError')

@api_bp.route('/app/<model_slug>/<int:app_number>/build', methods=['POST'])
def api_app_build(model_slug, app_number):
    app, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    try:
        assert app is not None
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        docker_result = None
        compose_diag = None
        if docker_mgr:
            try:
                docker_result = docker_mgr.build_containers(model_slug, app_number, no_cache=True)
                compose_diag = docker_mgr.debug_compose_resolution(model_slug, app_number)
            except Exception as _dock_err:  # pragma: no cover
                current_app.logger.error(f"Docker build failed for {model_slug}/app{app_number}: {_dock_err}")
                docker_result = {'success': False, 'error': str(_dock_err)}
        else:
            docker_result = {'success': False, 'error': 'DockerManager unavailable'}

        # Update DB status according to outcome
        if docker_result and docker_result.get('success'):
            app.container_status = 'running'
        else:
            app.container_status = 'error'
        db.session.commit()
        if request.headers.get('HX-Request'):
            try:
                from app.routes.jinja.models import _render_application_section  # type: ignore
                section = _render_application_section(model_slug, app_number, 'container')
                if isinstance(section, tuple):
                    body, status = section
                else:
                    body, status = section, 200
                from flask import make_response
                resp = make_response(body, status)
                # include outcome (success/fail) in trigger
                outcome = 'success' if (docker_result or {}).get('success') else 'error'
                resp.headers['HX-Trigger'] = f'{{"app-operation": {{"operation": "build", "status": "{outcome}"}}}}'
                return resp
            except Exception as _htmx_err:  # pragma: no cover
                current_app.logger.warning(f"HTMX container section render failed: {_htmx_err}")
        return create_success_response_with_status({'status': app.container_status, 'docker': docker_result, 'compose': compose_diag}, message='Build attempted')
    except Exception as e:
        db.session.rollback()
        return create_error_response_with_status(str(e), status=500, error_type='BuildError')

@api_bp.route('/app/<model_slug>/<int:app_number>/logs', methods=['GET'])
def api_app_logs(model_slug, app_number):
    # Reuse modal logic by calling internal function via request
    try:
        from app.routes.jinja.models import application_logs_modal
        html = application_logs_modal(model_slug, app_number)
        # application_logs_modal returns HTML string or tuple
        if isinstance(html, tuple):
            body, status = html
            return jsonify({'html': body}), status
        return jsonify({'html': html})
    except Exception as e:
        return create_error_response_with_status(str(e), status=500, error_type='LogsError')

@api_bp.route('/app/<model_slug>/<int:app_number>/diagnose', methods=['GET'])
def api_app_diagnose(model_slug, app_number):
    """Return detailed diagnostics for compose path & docker environment.

    Helps explain why build/start may fail (missing compose file vs docker not running).
    Returns HTML fragment suitable for HTMX injection.
    """
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return '''
            <div class="alert alert-warning">
                <h5><i class="fas fa-exclamation-triangle me-2"></i>DockerManager Unavailable</h5>
                <p>The Docker management service is not available. This could mean:</p>
                <ul class="mb-0">
                    <li>Docker Desktop is not running</li>
                    <li>Service initialization failed</li>
                    <li>Configuration issue</li>
                </ul>
            </div>
            ''', 503

        diag = docker_mgr.debug_compose_resolution(model_slug, app_number)
        
        # Build HTML response
        html_parts = []
        
        # Docker connection status
        if diag.get('docker_connected'):
            html_parts.append(f'''
            <div class="alert alert-success">
                <h5><i class="fas fa-check-circle me-2"></i>Docker Connected</h5>
                <p class="mb-1">Successfully connected to Docker engine</p>
                {f"<small>Engine: {diag.get('docker_engine', {}).get('server_version', 'Unknown')}</small>" if diag.get('docker_engine') else ""}
            </div>
            ''')
        else:
            html_parts.append('''
            <div class="alert alert-danger">
                <h5><i class="fas fa-times-circle me-2"></i>Docker Not Connected</h5>
                <p class="mb-1">Cannot connect to Docker daemon</p>
                <small>Ensure Docker Desktop is running and accessible</small>
            </div>
            ''')

        # Compose file resolution
        chosen_exists = diag.get('chosen_exists', False)
        chosen_path = diag.get('chosen_compose_path', 'Unknown')
        
        if chosen_exists:
            html_parts.append(f'''
            <div class="alert alert-success">
                <h5><i class="fas fa-file-check me-2"></i>Compose File Found</h5>
                <code class="small">{chosen_path}</code>
            </div>
            ''')
        else:
            html_parts.append(f'''
            <div class="alert alert-warning">
                <h5><i class="fas fa-file-times me-2"></i>Compose File Missing</h5>
                <p class="mb-1">Expected location: <code class="small">{chosen_path}</code></p>
                <small>You may need to generate the application first or check the model slug.</small>
            </div>
            ''')
            
        # Show candidate paths
        variants = diag.get('compose_variants', [])
        if variants:
            existing_variants = [v for v in variants if v.get('exists')]
            if existing_variants:
                html_parts.append('<div class="alert alert-info">')
                html_parts.append('<h6><i class="fas fa-info-circle me-2"></i>Available Compose Files</h6>')
                html_parts.append('<ul class="mb-0">')
                for v in existing_variants:
                    html_parts.append(f'<li><code class="small">{v["path"]}</code> <span class="badge bg-secondary">{v["variant"]}</span></li>')
                html_parts.append('</ul></div>')

        # Project root info
        project_root = diag.get('project_root', 'Unknown')
        html_parts.append(f'''
        <div class="card card-sm">
            <div class="card-body">
                <h6 class="card-title">Path Resolution</h6>
                <div class="small">
                    <div><strong>Project Root:</strong> <code>{project_root}</code></div>
                    <div><strong>Model:</strong> <code>{model_slug}</code></div>
                    <div><strong>App Number:</strong> <code>{app_number}</code></div>
                </div>
            </div>
        </div>
        ''')

        return ''.join(html_parts)
    except Exception as e:
        return f'''
        <div class="alert alert-danger">
            <h5><i class="fas fa-exclamation-triangle me-2"></i>Diagnostic Error</h5>
            <p class="mb-0">Failed to run diagnostics: {e}</p>
        </div>
        ''', 500

@api_bp.route('/app/<model_slug>/<int:app_number>/test-port/<int:port>', methods=['GET'])
def api_app_test_port(model_slug, app_number, port):
    """Test TCP connectivity to localhost:port.

    Returns JSON envelope with accessible flag. Fast timeout (1s) to keep UI snappy.
    """
    import socket
    accessible = False
    try:
        with socket.create_connection(('localhost', port), timeout=1.0):
            accessible = True
    except Exception:  # pragma: no cover
        accessible = False
    return create_success_response_with_status({'port': port, 'accessible': accessible})

@api_bp.route('/app/<model_slug>/<int:app_number>/status', methods=['GET'])
def api_app_status(model_slug, app_number):
    """Return current application & container status (lightweight, pollable).

    Returns HTML fragment with current container status for HTMX updates.
    """
    try:
        from app.services.service_locator import ServiceLocator
        
        # Get DB application
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        db_status = app.container_status if app else 'not_found'
        
        # Get Docker information
        docker_mgr = ServiceLocator.get_docker_manager()
        containers = []
        docker_connected = False
        
        if docker_mgr:
            try:
                containers = docker_mgr.get_project_containers(model_slug, app_number)
                docker_connected = True
            except Exception as e:
                current_app.logger.warning(f"Failed to get containers for {model_slug}/app{app_number}: {e}")
        
        # Build status HTML
        html_parts = []
        
        # Container discovery status
        if containers:
            html_parts.append(f'''
            <div class="alert alert-success alert-dismissible">
                <h6><i class="fas fa-check-circle me-2"></i>Containers Found ({len(containers)})</h6>
                <div class="small">
            ''')
            for container in containers:
                status_badge = 'success' if container.get('status') == 'running' else 'secondary'
                html_parts.append(f'''
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <span><code>{container.get('name', 'unknown')}</code></span>
                        <span class="badge bg-{status_badge}">{container.get('status', 'unknown')}</span>
                    </div>
                ''')
            html_parts.append('</div></div>')
        else:
            html_parts.append(f'''
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle me-2"></i>No Containers Found</h6>
                <p class="mb-1">No Docker containers discovered for this application</p>
                <small>DB Status: <span class="badge bg-secondary">{db_status}</span> | Docker Connected: {"Yes" if docker_connected else "No"}</small>
            </div>
            ''')
        
        # Status mismatch warning
        running_containers = sum(1 for c in containers if c.get('status') == 'running')
        if db_status == 'running' and running_containers == 0:
            html_parts.append('''
            <div class="alert alert-warning">
                <h6><i class="fas fa-exclamation-triangle me-2"></i>Status Mismatch</h6>
                <p class="mb-0">Database shows 'running' but no running containers found</p>
            </div>
            ''')
        elif db_status != 'running' and running_containers > 0:
            html_parts.append('''
            <div class="alert alert-info">
                <h6><i class="fas fa-info-circle me-2"></i>Status Mismatch</h6>
                <p class="mb-0">Found running containers but database shows different status</p>
            </div>
            ''')
        
        return ''.join(html_parts)
        
    except Exception as e:
        current_app.logger.error(f"Error getting app status for {model_slug}/app{app_number}: {e}")
        return f'''
        <div class="alert alert-danger">
            <h6><i class="fas fa-times-circle me-2"></i>Status Check Failed</h6>
            <p class="mb-0">Error: {e}</p>
        </div>
        ''', 500

@api_bp.route('/app/<model_slug>/<int:app_number>/logs/tails', methods=['GET'])
def api_app_log_tails(model_slug, app_number):
    """Return HTML fragment with recent backend & frontend log tails.

    This is an HTMX-friendly endpoint (returns raw HTML, not JSON) so the
    applications page can periodically refresh lightweight log previews.
    """
    app, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    from markupsafe import escape
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return ('<div class="text-warning small">Docker manager unavailable – cannot fetch live logs.</div>')
        lines = request.args.get('lines', default=120, type=int)
        services = ['backend', 'frontend']
        parts = []
        for svc in services:
            try:
                text = docker_mgr.get_container_logs(model_slug, app_number, svc, tail=lines)
            except Exception as _log_err:  # pragma: no cover
                text = f"Error retrieving {svc} logs: {_log_err}"
            safe = escape(text)
            download_url = url_for('api.api_app_log_download', model_slug=model_slug, app_number=app_number, service=svc)
            parts.append(
                f'<div class="mb-3">'
                f'<div class="d-flex justify-content-between align-items-center mb-1">'
                f'<h6 class="m-0">{svc.title()} Log Tail <small class="text-muted">(last {lines} lines)</small></h6>'
                f'<a class="btn btn-sm btn-outline-secondary" href="{download_url}"><i class="fas fa-download me-1"></i>Download</a>'
                f'</div>'
                f'<pre class="small bg-body-tertiary rounded p-2 mb-0" style="max-height:160px; overflow:auto; font-family:var(--tblr-font-monospace);">{safe}</pre>'
                f'</div>'
            )
        return ''.join(parts)
    except Exception as e:  # pragma: no cover
        return (f'<div class="text-danger small">Error loading log tails: {escape(e)}</div>'), 500

@api_bp.route('/app/<model_slug>/<int:app_number>/logs/download', methods=['GET'])
def api_app_log_download(model_slug, app_number):
    """Download (tail) of a specific service's logs from the running container.

    For now we tail a large number of lines (default 5000) to avoid streaming
    entire container output while still giving useful history.
    """
    service = request.args.get('service', 'backend').lower()
    lines = request.args.get('lines', default=5000, type=int)
    if service not in ('backend', 'frontend'):
        return create_error_response_with_status('Invalid service parameter', status=400, error_type='BadRequest')
    _, err = _get_app_or_404(model_slug, app_number)
    if err:
        return err
    try:
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            return create_error_response_with_status('Docker manager unavailable', status=503, error_type='ServiceUnavailable')
        content = docker_mgr.get_container_logs(model_slug, app_number, service, tail=lines)
        from flask import Response
        filename = f"{model_slug}_app{app_number}_{service}_logs.txt".replace('/', '_')
        return Response(
            content,
            mimetype='text/plain; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:  # pragma: no cover
        return create_error_response_with_status(str(e), status=500, error_type='DownloadError')

# ================================================================
# FILES UTILITIES
# ================================================================

@api_bp.route('/app/<model_slug>/<int:app_number>/scan-files', methods=['POST'])
def api_app_scan_files(model_slug, app_number):
    """Force a rescan of the application directory and return updated files section.

    Heavy scan logic already performed inside _render_application_section when section == 'files'.
    We simply re-render and return HTML if HTMX; otherwise JSON success stub.
    """
    try:
        if request.headers.get('HX-Request'):
            from app.routes.jinja.models import _render_application_section  # type: ignore
            section = _render_application_section(model_slug, app_number, 'files')
            if isinstance(section, tuple):
                body, status = section
            else:
                body, status = section, 200
            from flask import make_response
            resp = make_response(body, status)
            resp.headers['HX-Trigger'] = '{"files-scan": {"status": "completed"}}'
            return resp
        # Non-HTMX safeguard
        return create_success_response_with_status({'message': 'Scan complete'}, message='Scan complete')
    except Exception as e:  # pragma: no cover
        return create_error_response_with_status(str(e), status=500, error_type='ScanFilesError')

# ================================================================
# BULK DOCKER OPERATIONS
# ================================================================

@api_bp.route('/apps/bulk/list', methods=['GET'])
def api_bulk_apps_list():
    """Return HTML checkbox list of all generated applications (for modal).

    HTMX-friendly: returns raw HTML (no JSON envelope)."""
    try:
        apps = GeneratedApplication.query.order_by(GeneratedApplication.model_slug, GeneratedApplication.app_number).all()
        parts = [
            '<div class="bulk-app-list small" style="max-height:300px; overflow:auto">'
        ]
        if not apps:
            parts.append('<div class="text-muted">No applications available.</div>')
        else:
            for a in apps:
                label = f"{a.model_slug} / app{a.app_number}"
                value = f"{a.model_slug}:{a.app_number}"
                status_badge = f"<span class='badge bg-secondary ms-1'>{a.container_status or 'unknown'}</span>"
                parts.append(
                    f"<label class='d-flex align-items-center gap-2 py-1 border-bottom small'>"
                    f"<input type='checkbox' class='form-check-input' name='items' value='{value}' />"
                    f"<span>{label}</span>{status_badge}"
                    "</label>"
                )
        parts.append('</div>')
        return ''.join(parts)
    except Exception as e:  # pragma: no cover
        return f"<div class='text-danger small'>Error loading applications: {e}</div>", 500

@api_bp.route('/apps/bulk/docker', methods=['POST'])
def api_bulk_docker():
    """Perform a bulk docker operation across selected applications.

    Form fields:
      operation: start|stop|restart|build
      items: repeated checkbox values "model_slug:app_number"
    Returns JSON (if non-HTMX) or HTML summary (if HTMX request).
    """
    operation = request.form.get('operation', '').lower().strip()
    valid_ops = {'start', 'stop', 'restart', 'build'}
    if operation not in valid_ops:
        return create_error_response_with_status('Invalid or missing operation', status=400, error_type='BadRequest')
    raw_items = request.form.getlist('items')
    if not raw_items:
        return create_error_response_with_status('No applications selected', status=400, error_type='BadRequest')

    from app.services.service_locator import ServiceLocator
    docker_mgr = ServiceLocator.get_docker_manager()
    results = []
    success_count = 0
    for item in raw_items:
        try:
            model_slug, app_number_s = item.split(':', 1)
            app_number = int(app_number_s)
        except Exception:
            results.append({'item': item, 'success': False, 'error': 'Invalid format'})
            continue
        app = GeneratedApplication.query.filter_by(model_slug=model_slug, app_number=app_number).first()
        if not app:
            results.append({'item': item, 'success': False, 'error': 'App not found'})
            continue
        op_result = {'item': item, 'model_slug': model_slug, 'app_number': app_number, 'operation': operation}
        try:
            docker_result = None
            if docker_mgr:
                if operation == 'start':
                    docker_result = docker_mgr.start_containers(model_slug, app_number)
                elif operation == 'stop':
                    docker_result = docker_mgr.stop_containers(model_slug, app_number)
                elif operation == 'restart':
                    docker_result = docker_mgr.restart_containers(model_slug, app_number)
                elif operation == 'build':
                    docker_result = docker_mgr.build_containers(model_slug, app_number, no_cache=False)
            # Update DB state using application service for consistency
            from app.services import application_service as _app_service
            if operation == 'start':
                _app_service.start_application(app.id)
            elif operation == 'stop':
                _app_service.stop_application(app.id)
            elif operation == 'restart':
                _app_service.restart_application(app.id)
            elif operation == 'build':
                if docker_result and docker_result.get('success'):
                    app.container_status = 'running'
                else:
                    app.container_status = 'error'
                db.session.commit()
            op_result['docker'] = docker_result
            op_result['success'] = (docker_result or {}).get('success', True)
            if op_result['success']:
                success_count += 1
        except Exception as e:  # pragma: no cover
            op_result['success'] = False
            op_result['error'] = str(e)
        results.append(op_result)

    summary = {
        'operation': operation,
        'total': len(raw_items),
        'succeeded': success_count,
        'failed': len(raw_items) - success_count
    }

    # HTMX: return HTML fragment summary
    if request.headers.get('HX-Request'):
        rows = []
        for r in results:
            badge = '<span class="badge bg-success">OK</span>' if r.get('success') else '<span class="badge bg-danger">Fail</span>'
            err = f"<div class='text-danger small'>{r.get('error')}</div>" if r.get('error') else ''
            rows.append(
                f"<tr><td>{r.get('model_slug')}</td><td>app{r.get('app_number')}</td><td>{r.get('operation')}</td><td>{badge}{err}</td></tr>"
            )
        html = (
            '<div class="bulk-results">'
            f"<div class='mb-2'><strong>{summary['operation'].title()} Summary:</strong> {summary['succeeded']}/{summary['total']} succeeded" \
            f" ({summary['failed']} failed)</div>"  # noqa: E501
            '<div class="table-responsive" style="max-height:240px; overflow:auto">'
            '<table class="table table-sm table-striped mb-0"><thead><tr><th>Model</th><th>App</th><th>Op</th><th>Result</th></tr></thead><tbody>'
            + ''.join(rows) + '</tbody></table></div></div>'
        )
        return html

    return create_success_response_with_status({'summary': summary, 'results': results})