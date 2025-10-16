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
from .container_tools import container_tools_bp

# Create the main API blueprint that will orchestrate all others
api_bp = Blueprint('api', __name__)

# Register all specialized blueprints as nested blueprints
# This allows them to share the same URL prefix while maintaining modularity
api_bp.register_blueprint(core_bp)
api_bp.register_blueprint(models_bp, url_prefix='/models') 
api_bp.register_blueprint(system_bp)
# Mount dashboard routes under /api/dashboard to provide a stable prefix
api_bp.register_blueprint(dashboard_bp, url_prefix='/dashboard')
api_bp.register_blueprint(applications_bp)
api_bp.register_blueprint(analysis_bp)
api_bp.register_blueprint(tool_registry_bp)
api_bp.register_blueprint(container_tools_bp)

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
        provider_filter = (request.args.get('provider') or '').strip().lower()
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').strip().lower()
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
        
        # Price tier filtering function (per token values)
        def price_bucket(val: float) -> str:
            if val == 0:
                return 'free'
            if val < 0.001:  # < $1 per 1M tokens
                return 'low'
            if val < 0.01:  # $1-$10 per 1M tokens
                return 'medium'
            return 'high'  # > $10 per 1M tokens
        
        # Get additional filter parameters
        context_filter = request.args.get('context', '').strip().lower()
        max_output_filter = request.args.get('max_output', '').strip().lower()
        tokenizer_filter = request.args.get('tokenizer', '').strip().lower()
        instruct_type_filter = request.args.get('instruct_type', '').strip().lower()
        cost_efficiency_filter = request.args.get('cost_efficiency', '').strip().lower()
        safety_score_filter = request.args.get('safety_score', '').strip().lower()
        has_apps = request.args.get('has_apps') == '1'
        free_models_only = request.args.get('free_models') == '1'
        
        # Feature support filters
        features_requested = request.args.getlist('features')
        features_set = {f.lower().replace('-', '_') for f in features_requested if f}
        
        # Modality filters
        modalities_requested = request.args.getlist('modalities')
        modalities_set = {m.lower() for m in modalities_requested if m}
        
        # Parameter support filters
        params_requested = request.args.getlist('parameters')
        params_set = {p.lower() for p in params_requested if p}
        
        # Helper for context window filtering
        def context_matches(ctx_val):
            if not context_filter:
                return True
            if not ctx_val:
                return False
            if context_filter == 'small':
                return ctx_val < 8000
            elif context_filter == 'medium':
                return 8000 <= ctx_val < 32000
            elif context_filter == 'large':
                return 32000 <= ctx_val < 128000
            elif context_filter == 'xlarge':
                return ctx_val >= 128000
            return True
        
        # Helper for max output filtering
        def max_output_matches(max_out):
            if not max_output_filter:
                return True
            if not max_out:
                return False
            if max_output_filter == 'small':
                return max_out < 4000
            elif max_output_filter == 'medium':
                return 4000 <= max_out < 16000
            elif max_output_filter == 'large':
                return max_out >= 16000
            return True
        
        # Apply filters
        filtered = []
        for m in base_models:
            name_l = (getattr(m, 'model_name', '') or '').lower()
            slug_l = (getattr(m, 'canonical_slug', '') or '').lower()
            meta = m.get_metadata() or {}
            
            # Text search (name, slug, or description)
            if search:
                desc = (meta.get('openrouter_description') or meta.get('description') or '').lower()
                if search not in name_l and search not in slug_l and search not in desc:
                    continue
            
            # Provider filter
            if provider_filter:
                model_provider = (getattr(m, 'provider', '') or '').lower()
                if provider_filter != model_provider:
                    continue
            
            # Capability filter (legacy)
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            caps_lower = {c.lower() for c in caps_list}
            if caps_filter and not caps_filter.issubset(caps_lower):
                continue
            
            # Price tier filter
            if price_tier:
                bucket = price_bucket(getattr(m, 'input_price_per_token', 0.0) or 0.0)
                if bucket != price_tier:
                    continue
            
            # Has applications filter
            if has_apps:
                if getattr(m, 'canonical_slug', None) not in used_model_slugs:
                    continue
            
            # Context window filter
            if context_filter:
                if not context_matches(getattr(m, 'context_window', 0)):
                    continue
            
            # Max output tokens filter
            if max_output_filter:
                if not max_output_matches(getattr(m, 'max_output_tokens', 0)):
                    continue
            
            # Feature support filters
            if features_set:
                # Try direct boolean fields first, fallback to capabilities_json
                caps_data = m.get_capabilities() or {}
                feature_map = {
                    'function_calling': (
                        getattr(m, 'supports_function_calling', False) or
                        caps_data.get('supports_tool_calling', False) or
                        caps_data.get('supports_function_calling', False)
                    ),
                    'vision': (
                        getattr(m, 'supports_vision', False) or
                        caps_data.get('supports_vision', False)
                    ),
                    'json_mode': (
                        getattr(m, 'supports_json_mode', False) or
                        caps_data.get('supports_json', False) or
                        caps_data.get('supports_json_mode', False)
                    ),
                    'streaming': (
                        getattr(m, 'supports_streaming', False) or
                        caps_data.get('supports_streaming', False)
                    ),
                }
                # Skip model if any required feature is missing
                model_has_all_features = all(feature_map.get(f, False) for f in features_set)
                if not model_has_all_features:
                    continue
            
            # Modality filters
            if modalities_set:
                # Get modality from capabilities_json architecture field
                caps_data = m.get_capabilities() or {}
                arch = caps_data.get('architecture', {})
                modality_str = arch.get('modality', '')
                
                if not modality_str:
                    continue  # Skip models without modality data
                
                # Parse modality string (format: "text+image->text" or "text->text")
                # Split by both '+' and '->' to get all modalities
                modality_parts = modality_str.replace('->', '+').split('+')
                parsed_modalities = {m.strip().lower() for m in modality_parts if m.strip()}
                
                # Check if all requested modalities are present
                if not modalities_set.issubset(parsed_modalities):
                    continue
            
            # Parameter support filters
            if params_set:
                # Get supported parameters from capabilities_json
                caps_data = m.get_capabilities() or {}
                supported_params = caps_data.get('supported_parameters', [])
                
                if not supported_params:
                    continue  # Skip models without parameter data
                
                # Convert to set safely
                supported_params_lower = {str(p).lower() for p in supported_params if p}
                
                # Check if all requested parameters are supported
                if not params_set.issubset(supported_params_lower):
                    continue
            
            # Tokenizer filter
            if tokenizer_filter:
                # Get tokenizer from capabilities_json architecture field
                caps_data = m.get_capabilities() or {}
                arch = caps_data.get('architecture', {})
                tokenizer = (arch.get('tokenizer') or '').lower()
                
                # Skip models without tokenizer info when filtering
                if not tokenizer:
                    continue
                
                if tokenizer_filter == 'gpt' and not any(x in tokenizer for x in ['gpt', 'claude', 'tiktoken']):
                    continue
                elif tokenizer_filter == 'llama' and 'llama' not in tokenizer:
                    continue
                elif tokenizer_filter == 'qwen' and 'qwen' not in tokenizer:
                    continue
                elif tokenizer_filter == 'mistral' and 'mistral' not in tokenizer:
                    continue
                elif tokenizer_filter == 'other':
                    if any(x in tokenizer for x in ['gpt', 'claude', 'tiktoken', 'llama', 'qwen', 'mistral']):
                        continue
            
            # Instruction type filter
            if instruct_type_filter:
                # Get instruction type from capabilities_json architecture field
                caps_data = m.get_capabilities() or {}
                arch = caps_data.get('architecture', {})
                instruct_type = (arch.get('instruct_type') or '').lower()
                
                # Normalize empty, None, or base/foundation to 'none'
                if not instruct_type or instruct_type in ['base', 'foundation', 'none']:
                    instruct_type = 'none'
                
                if instruct_type_filter != instruct_type:
                    continue
            
            # Free models filter
            if free_models_only:
                is_free = getattr(m, 'is_free', False)
                input_price = getattr(m, 'input_price_per_token', None) or 0.0
                output_price = getattr(m, 'output_price_per_token', None) or 0.0
                # Model is free if flag is set OR both prices are 0
                if not (is_free or (input_price == 0.0 and output_price == 0.0)):
                    continue
            
            # Cost efficiency filter
            if cost_efficiency_filter:
                cost_eff = getattr(m, 'cost_efficiency', None)
                if cost_eff is None:
                    continue  # Skip models without cost efficiency data
                cost_eff = float(cost_eff) if cost_eff else 0.0
                if cost_efficiency_filter == 'high' and cost_eff <= 0.7:
                    continue
                elif cost_efficiency_filter == 'medium' and (cost_eff < 0.3 or cost_eff > 0.7):
                    continue
                elif cost_efficiency_filter == 'low' and cost_eff >= 0.3:
                    continue
            
            # Safety score filter
            if safety_score_filter:
                safety = getattr(m, 'safety_score', None)
                if safety is None:
                    continue  # Skip models without safety score data
                safety = float(safety) if safety else 0.0
                if safety_score_filter == 'high' and safety <= 0.7:
                    continue
                elif safety_score_filter == 'medium' and (safety < 0.3 or safety > 0.7):
                    continue
                elif safety_score_filter == 'low' and safety >= 0.3:
                    continue
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
            
            # Get provider count from pricing.providers if available
            provider_count = 0
            pricing_data = caps_raw.get('pricing', {})
            if isinstance(pricing_data, dict) and 'providers' in pricing_data:
                providers = pricing_data.get('providers', [])
                if isinstance(providers, list):
                    provider_count = len(providers)
            
            # Count variants (models with same base_model_id)
            variant_count = 0
            base_id = getattr(m, 'base_model_id', None)
            if base_id:
                try:
                    variant_count = ModelCapability.query.filter_by(base_model_id=base_id).count()
                except Exception:
                    variant_count = 1
            
            return {
                'slug': slug,
                'model_id': getattr(m, 'model_id', None),
                'name': getattr(m, 'model_name', None),
                'provider': getattr(m, 'provider', None),
                'provider_count': provider_count,
                'variant_count': variant_count,
                'base_model_id': base_id,
                'is_free': bool(getattr(m, 'is_free', False)),
                'capabilities': caps_list,
                'capabilities_raw': caps_raw,  # Full capabilities for frontend parsing
                'input_price_per_1k': round((getattr(m, 'input_price_per_token', 0.0) or 0.0) * 1000, 6),
                'output_price_per_1k': round((getattr(m, 'output_price_per_token', 0.0) or 0.0) * 1000, 6),
                'context_length': getattr(m, 'context_window', 0) or 0,
                'max_output_tokens': getattr(m, 'max_output_tokens', 0) or 0,
                'cost_efficiency': float(getattr(m, 'cost_efficiency', 0.0) or 0.0),  # Add cost efficiency
                'performance_score': int((getattr(m, 'cost_efficiency', 0.0) or 0.0) * 10) if (getattr(m, 'cost_efficiency', 0.0) or 0) <= 1 else int(getattr(m, 'cost_efficiency', 0.0) or 0),
                'status': 'active',
                'installed': bool(getattr(m, 'installed', False)),
                'has_applications': slug in used_model_slugs if slug else False,
                'description': meta.get('openrouter_description') or meta.get('description') or None,
                # Feature support flags
                'supports_function_calling': bool(getattr(m, 'supports_function_calling', False)),
                'supports_vision': bool(getattr(m, 'supports_vision', False)),
                'supports_streaming': bool(getattr(m, 'supports_streaming', False)),
                'supports_json_mode': bool(getattr(m, 'supports_json_mode', False)),
            }
        
        # Generate response
        models_list = [map_model(m) for m in page_items]
        all_mapped_for_stats = [map_model(m) for m in filtered]
        providers_set = {m['provider'] for m in all_mapped_for_stats if m.get('provider')}
        capabilities_set = set()
        modalities_set = set()
        parameters_set = set()
        tokenizers_set = set()
        
        for mapped in all_mapped_for_stats:
            for cap in mapped.get('capabilities') or []:
                if cap:
                    capabilities_set.add(cap)
        
        # Collect available modalities, parameters, and tokenizers from all filtered models
        for m in filtered:
            meta = m.get_metadata() or {}
            
            # Collect input modalities
            arch_input_mods = meta.get('architecture_input_modalities') or []
            if isinstance(arch_input_mods, str):
                arch_input_mods = [arch_input_mods]
            for mod in arch_input_mods:
                if mod:
                    modalities_set.add(mod)
            
            # Collect supported parameters
            supported_params = meta.get('openrouter_supported_parameters') or []
            if isinstance(supported_params, str):
                supported_params = [supported_params]
            for param in supported_params:
                if param:
                    parameters_set.add(param)
            
            # Collect tokenizer types
            tokenizer = meta.get('architecture_tokenizer')
            if tokenizer:
                tokenizers_set.add(tokenizer)
        
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
            'source': source,
            'filters': {
                'providers': sorted(providers_set),
                'capabilities': sorted(capabilities_set),
                'modalities': sorted(modalities_set),
                'parameters': sorted(parameters_set),
                'tokenizers': sorted(tokenizers_set)
            }
        })
        
    except Exception as e:
        return jsonify({
            'models': [],
            'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0},
            'pagination': {'current_page': 1, 'per_page': 25, 'total_items': 0, 'total_pages': 1, 'has_prev': False, 'has_next': False},
            'source': 'error',
            'error': str(e)
        }), 500

@api_bp.route('/models/<model_slug>/providers', methods=['GET'])
def get_model_providers(model_slug):
    """
    Get provider list for a specific model from OpenRouter.
    """
    from flask import jsonify
    from app.models import ModelCapability
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Find model by canonical_slug or model_id
        model = ModelCapability.query.filter(
            (ModelCapability.canonical_slug == model_slug) |
            (ModelCapability.model_id == model_slug.replace('_', '/'))
        ).first()
        
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        # Get providers from capabilities_json pricing.providers
        caps = model.get_capabilities() or {}
        pricing_data = caps.get('pricing', {})
        
        if not isinstance(pricing_data, dict):
            return jsonify({'providers': [], 'count': 0})
        
        providers = pricing_data.get('providers', [])
        if not isinstance(providers, list):
            return jsonify({'providers': [], 'count': 0})
        
        # Format providers for response
        formatted_providers = []
        for provider in providers:
            if not isinstance(provider, dict):
                continue
            
            formatted_providers.append({
                'name': provider.get('name', 'Unknown'),
                'region': provider.get('region', 'US'),
                'latency': provider.get('latency'),
                'throughput': provider.get('throughput'),
                'uptime': provider.get('uptime'),
                'context_length': provider.get('context_length'),
                'max_completion_tokens': provider.get('max_completion_tokens'),
                'input_price': provider.get('input_price'),
                'output_price': provider.get('output_price'),
                'cache_read_price': provider.get('cache_read_price'),
                'cache_write_price': provider.get('cache_write_price'),
            })
        
        return jsonify({
            'model_slug': model_slug,
            'model_id': model.model_id,
            'model_name': model.model_name,
            'providers': formatted_providers,
            'count': len(formatted_providers)
        })
        
    except Exception as e:
        logger.error(f"Error fetching providers for model {model_slug}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@api_bp.route('/models/<model_slug>/variants', methods=['GET'])
def get_model_variants(model_slug):
    """
    Get all variants of a model (e.g., free vs paid versions).
    Returns all models that share the same base_model_id.
    """
    from flask import jsonify
    from app.models import ModelCapability
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Find the requested model
        model = ModelCapability.query.filter(
            (ModelCapability.canonical_slug == model_slug) |
            (ModelCapability.model_id == model_slug.replace('_', '/'))
        ).first()
        
        if not model:
            return jsonify({'error': 'Model not found'}), 404
        
        base_id = model.base_model_id
        if not base_id:
            # No base_model_id means no variants
            return jsonify({
                'model_slug': model_slug,
                'base_model_id': None,
                'variants': [],
                'count': 1
            })
        
        # Find all models with the same base_model_id
        variants = ModelCapability.query.filter_by(base_model_id=base_id).order_by(
            ModelCapability.is_free.desc(),  # Free variants first
            ModelCapability.input_price_per_token.asc()  # Then by price
        ).all()
        
        # Format variants for response
        formatted_variants = []
        for variant in variants:
            # Extract variant suffix (e.g., ":free" from "model:free")
            variant_suffix = ''
            if ':' in variant.model_id:
                variant_suffix = ':' + variant.model_id.split(':')[-1]
            
            formatted_variants.append({
                'slug': variant.canonical_slug,
                'model_id': variant.model_id,
                'name': variant.model_name,
                'variant_suffix': variant_suffix,
                'is_free': bool(variant.is_free),
                'input_price_per_token': float(variant.input_price_per_token or 0),
                'output_price_per_token': float(variant.output_price_per_token or 0),
                'input_price_per_1m': round((variant.input_price_per_token or 0) * 1_000_000, 2),
                'output_price_per_1m': round((variant.output_price_per_token or 0) * 1_000_000, 2),
                'context_window': variant.context_window or 0,
                'max_output_tokens': variant.max_output_tokens or 0,
            })
        
        return jsonify({
            'model_slug': model_slug,
            'base_model_id': base_id,
            'variants': formatted_variants,
            'count': len(formatted_variants)
        })
        
    except Exception as e:
        logger.error(f"Error fetching variants for model {model_slug}: {str(e)}")
        return jsonify({'error': str(e)}), 500

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
