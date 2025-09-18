"""
API Routes Orchestrator

This module serves as the main API blueprint that orchestrates and consolidates
routes from the various specialized API modules. It maintains backward compatibility
with existing code and tests that expect a single 'api' blueprint.

The actual route implementations are distributed across focused modules:
- core.py: Basic health, status, and core endpoints
- models.py: Model management and metadata
- system.py: System monitoring and health
- dashboard.py: Dashboard stats and fragments
- applications.py: Application lifecycle management
- analysis.py: Analysis operations and statistics
"""

from flask import Blueprint

# Import all the specialized blueprints
from .core import core_bp
from .models import models_bp
from .system import system_bp
from .dashboard import dashboard_bp
from .applications import applications_bp
from .tool_registry import tool_registry_bp
from .analysis import analysis_bp

# Create the main API blueprint that will orchestrate all others
api_bp = Blueprint('api', __name__)

# Register all specialized blueprints as nested blueprints
# This allows them to share the same URL prefix while maintaining modularity
api_bp.register_blueprint(core_bp)
api_bp.register_blueprint(models_bp) 
api_bp.register_blueprint(system_bp)
# Mount dashboard routes under /api/dashboard to provide a stable prefix
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(applications_bp)
api_bp.register_blueprint(analysis_bp)
api_bp.register_blueprint(tool_registry_bp)

# ----------------------------------------------------------------------------
# Back-compat shims for pre-prefix dashboard endpoints
# These keep older callers (if any) working by delegating to the new routes
# ----------------------------------------------------------------------------

@api_bp.route('/overview')
def dashboard_overview_compat():
    from .dashboard import api_dashboard_overview
    return api_dashboard_overview()


@api_bp.route('/stats')
def dashboard_stats_compat():
    from .dashboard import api_dashboard_stats
    return api_dashboard_stats()


@api_bp.route('/system-stats')
def dashboard_system_stats_compat():
    from .dashboard import dashboard_system_stats
    return dashboard_system_stats()


@api_bp.route('/analyzer-services')
def dashboard_analyzer_services_compat():
    from .dashboard import dashboard_analyzer_services
    return dashboard_analyzer_services()


@api_bp.route('/recent_activity')
def dashboard_recent_activity_compat():
    from .dashboard import recent_activity
    return recent_activity()


@api_bp.route('/system-health-comprehensive')
def dashboard_system_health_comprehensive_compat():
    from .dashboard import comprehensive_system_health
    return comprehensive_system_health()


@api_bp.route('/tool-registry-summary')
def dashboard_tool_registry_summary_compat():
    from .dashboard import tool_registry_summary
    return tool_registry_summary()

# Add any missing critical routes that tests depend on
# These will be migrated to appropriate modules in future iterations

@api_bp.route('/models')
def models_endpoint():
    """
    Models endpoint (test compatibility).
    Delegates to the main models route.
    TODO: Update tests to use /api/ endpoint directly
    """
    from .models import api_models
    return api_models()

@api_bp.route('/applications')
def applications_endpoint():
    """
    Applications endpoint (test compatibility).
    Provides basic functionality until proper migration.
    TODO: Move implementation to applications.py module
    """
    from flask import jsonify
    from app.models import GeneratedApplication
    try:
        apps = GeneratedApplication.query.all()
        data = [{
            'id': app.id,
            'model_slug': app.model_slug,
            'app_number': app.app_number,
            'app_type': app.app_type,
            'container_status': app.container_status,
            'created_at': app.created_at.isoformat() if app.created_at else None
        } for app in apps]
        return jsonify({'success': True, 'data': data, 'message': 'Applications fetched'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@api_bp.route('/models/paginated')
def models_paginated():
    """
    Paginated models endpoint with filtering support.
    
    Query params:
      page: page number (default 1)
      per_page: page size (default 25, max 200)
      search, providers, capabilities, price: filter parameters
      source: db|openrouter for data source
      installed_only: filter to only installed models
    
    Returns:
      models: list (current page slice)
      statistics: aggregation over full filtered result set
      pagination: envelope {current_page, per_page, total_items, total_pages, has_prev, has_next}
      source: data source identifier
    """
    from flask import request, jsonify
    from app.models import ModelCapability, GeneratedApplication
    from app.extensions import db
    from .common import get_pagination_params
    from ..shared_utils import _norm_caps
    
    try:
        # Get pagination parameters
        page, per_page = get_pagination_params(default_per_page=25, max_per_page=200)
        
        # Get filter parameters
        search = (request.args.get('search') or '').strip().lower()
        providers_filter = {p.lower() for p in request.args.getlist('providers') if p.strip()}
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').lower()
        source = (request.args.get('source') or 'db').lower()
        installed_param = request.args.get('installed_only') or request.args.get('installed') or request.args.get('used')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        
        # Get base models and determine which ones have applications
        from app.models import GeneratedApplication
        base_models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        
        # Get set of model slugs that have applications (used models)
        used_model_slugs = set(
            slug[0] for slug in 
            db.session.query(GeneratedApplication.model_slug).distinct().all()
        )
        
        # If filtering for "used" models, filter to only those with applications
        if installed_only:
            base_models = [m for m in base_models if getattr(m, 'canonical_slug', None) in used_model_slugs]
        
        # Price tier filtering function
        def price_bucket(val: float) -> str:
            if val == 0:
                return 'free'
            if val < 0.001:
                return 'low'
            if val < 0.005:
                return 'mid'
            return 'high'
        
        # Apply filters
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
                    
            filtered.append(m)
        
        # Calculate pagination
        total_items = len(filtered)
        total_pages = (total_items + per_page - 1) // per_page if total_items else 1
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page
        end = start + per_page
        page_items = filtered[start:end]
        
        # Map models to response format
        def map_model(m):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            slug = getattr(m, 'canonical_slug', None)
            return {
                'slug': slug,
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
                'has_applications': slug in used_model_slugs if slug else False,
                'description': meta.get('openrouter_description') or meta.get('description') or None,
            }
        
        # Generate response
        models_list = [map_model(m) for m in page_items]
        all_mapped_for_stats = [map_model(m) for m in filtered]
        providers_set = {m['provider'] for m in all_mapped_for_stats}
        
        statistics = {
            'total_models': len(all_mapped_for_stats),
            'active_models': len(all_mapped_for_stats),
            'unique_providers': len(providers_set),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in all_mapped_for_stats) / max(len(all_mapped_for_stats), 1), 6),
            'source': source
        }
        
        pagination = {
            'current_page': page,
            'per_page': per_page,
            'total_items': total_items,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages
        }
        
        return jsonify({
            'models': models_list,
            'statistics': statistics,
            'pagination': pagination,
            'source': source
        })
        
    except Exception as e:
        return jsonify({
            'models': [],
            'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0},
            'pagination': {'current_page': 1, 'per_page': 25, 'total_items': 0, 'total_pages': 1, 'has_prev': False, 'has_next': False},
            'source': 'error',
            'error': str(e)
        }), 500

@api_bp.route('/model/<model_slug>/containers/sync-status', methods=['POST'])
@api_bp.route('/models/<model_slug>/containers/sync-status', methods=['POST'])
def model_containers_sync_status(model_slug):
    """
    Model containers sync status endpoint.
    Compatibility shim that delegates to models.py implementation.
    """
    # Import lazily to avoid circulars
    from .models import api_model_containers_sync_status
    return api_model_containers_sync_status(model_slug)
