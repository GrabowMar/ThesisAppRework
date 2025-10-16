"""
Models API routes
=================

Endpoints for model management, OpenRouter integration, and model metadata.
"""

import os
from flask import Blueprint, request, current_app, jsonify

from app.models import ModelCapability, GeneratedApplication
from app.services.data_initialization import data_init_service
from ..shared_utils import _upsert_openrouter_models, _norm_caps
from .common import api_success, api_error


models_bp = Blueprint('models_api', __name__)


@models_bp.route('/', strict_slashes=False)
def api_models():
    """Get all models (standardized envelope)."""
    models = ModelCapability.query.all()
    data = [{
        'id': model.model_id,  # Frontend expects 'id'
        'model_id': model.model_id,
        'canonical_slug': model.canonical_slug,
        'provider': model.provider,
        'model_name': model.model_name,
        'capabilities': model.get_capabilities()
    } for model in models]
    return api_success(data, message="Models fetched")


@models_bp.route('/<model_slug>/apps')
def api_model_apps(model_slug):
    """Get applications for a model (standardized envelope)."""
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
    data = [{
        'app_id': app.id,
        'app_number': app.app_number,
        'model_slug': app.model_slug,
        'provider': app.provider,
        'created_at': app.created_at.isoformat() if app.created_at else None
    } for app in apps]
    return api_success(data, message="Applications fetched")


@models_bp.route('/list')
def api_models_list():
    """Get models list."""
    try:
        models = ModelCapability.query.all()
        return api_success([model.to_dict() for model in models])
    except Exception as e:
        current_app.logger.error(f"Error getting models list: {e}")
        return api_error("Failed to get models list", details={"reason": str(e)})


@models_bp.route('/list-options')
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
        return render_template('pages/models/partials/_model_options.html', models=models)
    except Exception as e:
        current_app.logger.error(f"Error rendering model options: {e}")
        return '<option value="">All Models</option>', 200


@models_bp.route('/all')
def api_models_all():
    """Return models and simple statistics for Models Overview page."""
    try:
        models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # If no models are found, automatically load from OpenRouter
        if not models:
            try:
                from app.services.data_initialization import DataInitializationService
                from app.extensions import db
                data_init_service = DataInitializationService()
                result = data_init_service.load_model_capabilities()
                if result.get('openrouter_loaded', 0) > 0:
                    db.session.commit()
                    models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
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
            'source': 'database'
        }
        return api_success({'models': models_list, 'statistics': stats})
    except Exception as e:
        current_app.logger.error(f"Error building models/all payload: {e}")
        return api_success({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


@models_bp.route('/paginated')
def api_models_paginated():
    """Paginated models list with filtering support."""
    try:
        # Pagination params
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 100))
        source = request.args.get('source', 'database')  # database or openrouter
        
        # Filter params - support both singular and plural parameter names
        search = (request.args.get('search') or '').strip().lower()
        
        # Provider filter - accept both 'provider' (singular) and 'providers' (plural)
        provider_single = request.args.get('provider', '').strip()
        provider_list = request.args.getlist('providers')
        if provider_single:
            providers = {provider_single.lower()}
        elif provider_list:
            providers = {p.lower() for p in provider_list if p.strip()}
        else:
            providers = set()
        
        # Capabilities filter - accept both 'capability' and 'capabilities'
        cap_single = request.args.get('capability', '').strip()
        cap_list = request.args.getlist('capabilities')
        if cap_single:
            caps_filter = {cap_single.lower()}
        elif cap_list:
            caps_filter = {c.lower() for c in cap_list if c.strip()}
        else:
            caps_filter = set()
        
        price_tier = (request.args.get('price') or '').lower()
        context_size = (request.args.get('context') or '').lower()
        has_apps = request.args.get('has_apps') == '1'
        installed_only = request.args.get('installed_only') == '1'
        free_models = request.args.get('free_models') == '1'
        
        # Advanced filters
        features = request.args.getlist('features')  # function_calling, vision, json_mode, streaming
        modalities = request.args.getlist('modalities')  # text, image, audio, video
        parameters = request.args.getlist('parameters')  # temperature, top_p, etc.
        max_output_size = (request.args.get('max_output') or '').lower()
        tokenizer_filter = (request.args.get('tokenizer') or '').lower()
        instruct_type_filter = (request.args.get('instruct_type') or '').lower()
        cost_efficiency_filter = (request.args.get('cost_efficiency') or '').lower()
        safety_score_filter = (request.args.get('safety_score') or '').lower()
        
        current_app.logger.info(f"[Models API] Filters - search: {search}, provider: {providers}, price: {price_tier}, "
                               f"context: {context_size}, has_apps: {has_apps}, installed: {installed_only}, "
                               f"free: {free_models}, features: {features}, modalities: {modalities}")
        
        # Get all models
        base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        
        # If no models and source is openrouter, try loading
        if not base and source == 'openrouter':
            try:
                from app.services.data_initialization import DataInitializationService
                from app.extensions import db
                data_init_service = DataInitializationService()
                result = data_init_service.load_model_capabilities()
                if result.get('openrouter_loaded', 0) > 0:
                    db.session.commit()
                    base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
            except Exception:
                pass
        
        def price_bucket(val: float) -> str:
            if val == 0:
                return 'free'
            if val < 0.001:
                return 'low'
            if val <= 0.01:
                return 'medium'
            return 'high'
        
        def context_bucket(val: int) -> str:
            if val < 8000:
                return 'small'
            if val < 32000:
                return 'medium'
            if val < 128000:
                return 'large'
            return 'xlarge'
        
        def max_output_bucket(val: int) -> str:
            if val < 4000:
                return 'small'
            if val < 16000:
                return 'medium'
            return 'large'
        
        # Apply filters
        filtered = []
        for m in base:
            name_l = (m.model_name or '').lower()
            slug_l = (m.canonical_slug or '').lower()
            desc = (m.get_metadata() or {}).get('description', '').lower()
            
            # Text search
            if search and not (search in name_l or search in slug_l or search in desc):
                continue
            
            # Provider filter
            if providers and m.provider.lower() not in providers:
                continue
            
            # Capabilities filter
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            caps_lower = {c.lower() for c in caps_list}
            if caps_filter and not caps_filter.issubset(caps_lower):
                continue
            
            # Price filter
            if price_tier:
                bucket = price_bucket(m.input_price_per_token or 0.0)
                if bucket != price_tier:
                    continue
            
            # Context size filter
            if context_size:
                ctx_bucket = context_bucket(m.context_window or 0)
                if ctx_bucket != context_size:
                    continue
            
            # Free models filter
            if free_models:
                if (m.input_price_per_token or 0.0) > 0 or (m.output_price_per_token or 0.0) > 0:
                    continue
            
            # Installed only filter
            if installed_only and not getattr(m, 'installed', False):
                continue
            
            # Has applications filter
            if has_apps:
                # Check if model has any applications in the database
                # This would need to be implemented based on your schema
                pass
            
            # Feature filters
            if features:
                arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
                supported_params = caps_raw.get('supported_parameters', []) if isinstance(caps_raw, dict) else []
                
                supports_function_calling = 'tools' in supported_params or 'tool_choice' in supported_params
                supports_vision = any('image' in str(mod).lower() for mod in arch.get('input_modalities', []))
                supports_json = 'response_format' in supported_params or 'json' in str(caps_raw).lower()
                supports_streaming = 'stream' in supported_params
                
                if 'function_calling' in features and not supports_function_calling:
                    continue
                if 'vision' in features and not supports_vision:
                    continue
                if 'json_mode' in features and not supports_json:
                    continue
                if 'streaming' in features and not supports_streaming:
                    continue
            
            # Modality filters
            if modalities:
                arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
                modality_str = (arch.get('modality') or '').lower()
                input_mods = [str(m).lower() for m in arch.get('input_modalities', [])]
                
                has_required_modalities = True
                for mod in modalities:
                    mod_lower = mod.lower()
                    if not (mod_lower in modality_str or any(mod_lower in im for im in input_mods)):
                        has_required_modalities = False
                        break
                
                if not has_required_modalities:
                    continue
            
            # Parameter filters
            if parameters:
                arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
                supported_params = caps_raw.get('supported_parameters', []) if isinstance(caps_raw, dict) else []
                supported_params_lower = [str(p).lower() for p in supported_params]
                
                has_required_params = all(param.lower() in supported_params_lower for param in parameters)
                if not has_required_params:
                    continue
            
            # Max output filter
            if max_output_size:
                output_bucket = max_output_bucket(m.max_output_tokens or 0)
                if output_bucket != max_output_size:
                    continue
            
            # Tokenizer filter
            if tokenizer_filter:
                arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
                tok = (arch.get('tokenizer') or '').lower()
                if tokenizer_filter == 'gpt' and not ('gpt' in tok or 'claude' in tok):
                    continue
                elif tokenizer_filter == 'llama' and 'llama' not in tok:
                    continue
                elif tokenizer_filter == 'qwen' and 'qwen' not in tok:
                    continue
                elif tokenizer_filter == 'mistral' and 'mistral' not in tok:
                    continue
                elif tokenizer_filter == 'other' and any(x in tok for x in ['gpt', 'claude', 'llama', 'qwen', 'mistral']):
                    continue
            
            # Instruction type filter
            if instruct_type_filter:
                arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
                inst_type = arch.get('instruct_type')
                
                if instruct_type_filter == 'none':
                    # Base model - no instruction tuning
                    if inst_type is not None and inst_type != '' and inst_type.lower() != 'none':
                        continue
                elif instruct_type_filter == 'chat':
                    if not inst_type or 'chat' not in inst_type.lower():
                        continue
                elif instruct_type_filter == 'instruction':
                    if not inst_type or 'instruct' not in inst_type.lower():
                        continue
            
            # Cost efficiency filter
            if cost_efficiency_filter:
                cost_eff = m.cost_efficiency or 0.0
                if cost_efficiency_filter == 'high' and cost_eff < 0.7:
                    continue
                elif cost_efficiency_filter == 'medium' and not (0.3 <= cost_eff < 0.7):
                    continue
                elif cost_efficiency_filter == 'low' and cost_eff >= 0.3:
                    continue
            
            # Safety score filter (if available in your schema)
            if safety_score_filter:
                # Implement based on your schema
                pass
            
            filtered.append(m)
        
        current_app.logger.info(f"[Models API] Filtered {len(filtered)} models from {len(base)} total")
        current_app.logger.info(f"[Models API] Filtered {len(filtered)} models from {len(base)} total")
        
        # Calculate pagination
        total = len(filtered)
        total_pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        start = (page - 1) * per_page
        end = start + per_page
        page_models = filtered[start:end]
        
        def map_model(m: ModelCapability):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            
            # Extract architecture info for frontend
            arch = caps_raw.get('architecture', {}) if isinstance(caps_raw, dict) else {}
            
            # Check for feature support
            supported_params = caps_raw.get('supported_parameters', []) if isinstance(caps_raw, dict) else []
            
            return {
                'id': m.model_id,
                'slug': m.canonical_slug,
                'model_id': m.model_id,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/images/default-avatar.svg',
                'capabilities': caps_list,
                'capabilities_raw': caps_raw,  # Include full capabilities for frontend
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'max_output_tokens': m.max_output_tokens or 0,
                'cost_efficiency': m.cost_efficiency or 0.0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': meta.get('openrouter_description') or meta.get('description') or None,
                'installed': bool(getattr(m, 'installed', False)),
                # Feature flags for frontend
                'supports_function_calling': 'tools' in supported_params or 'tool_choice' in supported_params,
                'supports_vision': any('image' in str(mod).lower() for mod in arch.get('input_modalities', [])),
                'supports_json_mode': 'response_format' in supported_params or 'json' in str(caps_raw).lower(),
                'supports_streaming': 'stream' in supported_params,
            }
        
        models_list = [map_model(m) for m in page_models]
        providers_set = {m.provider for m in filtered}
        
        # Collect available filter values from ALL filtered results (not just current page)
        all_capabilities = set()
        for m in filtered:
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            all_capabilities.update(caps_list)
        
        result = {
            'models': models_list,
            'statistics': {
                'total_models': total,
                'active_models': total,
                'unique_providers': len(providers_set),
                'avg_cost_per_1k': round(sum(map_model(x)['input_price_per_1k'] for x in filtered) / max(total, 1), 6)
            },
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total,
                'total_pages': total_pages,
                'current_page': page,
                'has_prev': page > 1,
                'has_next': page < total_pages
            },
            'filters': {
                'providers': sorted(providers_set),
                'capabilities': sorted(all_capabilities),
                'price_tiers': ['free', 'low', 'medium', 'high']
            }
        }
        return api_success(result)
    except Exception as e:
        current_app.logger.error(f"Error in paginated models: {e}", exc_info=True)
        return api_error(str(e), status=500)


@models_bp.route('/filtered')
def api_models_filtered():
    """Filtered models list used by models.js applyFilters()."""
    try:
        search = (request.args.get('search') or '').strip().lower()
        providers = {p.lower() for p in request.args.getlist('providers') if p.strip()}
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').lower()

        base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # If no models found, try loading from OpenRouter
        if not base:
            try:
                from app.services.data_initialization import DataInitializationService
                from app.extensions import db
                data_init_service = DataInitializationService()
                result = data_init_service.load_model_capabilities()
                if result.get('openrouter_loaded', 0) > 0:
                    db.session.commit()
                    base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
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
        return api_success({'models': models_list, 'statistics': stats})
    except Exception as e:  # pragma: no cover - unexpected failure path
        current_app.logger.error(f"Error building models/filtered payload: {e}")
        return api_success({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


@models_bp.route('/export')
def models_export():
    """Export models in JSON format (only format supported)."""
    try:
        fmt = request.args.get('format', 'json').lower()
        if fmt != 'json':
            return api_error('only json supported', status=400)
        models = ModelCapability.query.all()
        data = [m.to_dict() for m in models]
        return api_success({'format': 'json', 'count': len(data), 'models': data})
    except Exception as e:
        current_app.logger.error(f"Models export failed: {e}")
        return api_success({'format': 'json', 'count': 0, 'models': []})


@models_bp.route('/load-openrouter', methods=['POST'])
def api_models_load_openrouter():
    """Load/refresh ModelCapability rows from OpenRouter API."""
    api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
    if not api_key:
        return api_error('OPENROUTER_API_KEY not configured', status=400)

    import requests
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
        if resp.status_code != 200:
            current_app.logger.error(f'OpenRouter models fetch failed: {resp.status_code} {resp.text[:200]}')
            return api_error(f'OpenRouter API returned {resp.status_code}', status=502)

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

        return api_success({'upserted': upserted, 'fetched': len(data or []), 'mark_installed': mark_res})
    except Exception as e:
        current_app.logger.error(f'Error loading models from OpenRouter: {e}')
        return api_error("Failed to load models from OpenRouter", details={"reason": str(e)})


@models_bp.route('/mark-installed', methods=['POST'])
def api_models_mark_installed():
    """Scan generated and set ModelCapability.installed=True for matching canonical_slugs."""
    try:
        try:
            res = data_init_service.mark_installed_models(reset_first=True)
            status_code = 200 if res.get('success', False) else 400
            return api_success(res) if status_code == 200 else api_error("Mark installed failed", details=res)
        except Exception as e:
            current_app.logger.error(f'Error in mark-installed delegate: {e}')
            return api_error("Failed to mark installed models (delegate)", details={"reason": str(e), "updated": 0})
    except Exception as e:
        current_app.logger.error(f'Error marking installed models: {e}')
        return api_error("Failed to mark installed models", details={"reason": str(e)})


@models_bp.route('/rescan-used', methods=['POST'])
def api_models_rescan_used():
    """Rescan generated/apps folder and update 'used' models marker.
    
    Steps:
    1. Reset all models' installed flag to False
    2. Scan generated/apps folder for existing model directories
    3. Mark only those models as installed=True
    4. Return statistics about the operation
    """
    try:
        import os
        from pathlib import Path
        from app.extensions import db
        
        # Get the generated/apps path
        repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        apps_path = Path(repo_root) / 'generated' / 'apps'
        
        # Step 1: Reset all models
        try:
            reset_count = db.session.query(ModelCapability).update({ModelCapability.installed: False})
            db.session.flush()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error resetting installed flags: {e}')
            return api_error("Failed to reset models", details={"reason": str(e)})
        
        # Step 2: Scan for existing model directories
        found_models = []
        if apps_path.exists():
            for item in apps_path.iterdir():
                if item.is_dir() and not item.name.startswith('_'):
                    found_models.append(item.name)
        
        # Step 3: Mark found models as installed
        marked_count = 0
        for model_slug in found_models:
            try:
                model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
                if model:
                    model.installed = True
                    marked_count += 1
            except Exception as e:
                current_app.logger.error(f'Error marking model {model_slug}: {e}')
        
        # Commit changes
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error committing rescan changes: {e}')
            return api_error("Failed to commit changes", details={"reason": str(e)})
        
        return api_success({
            'reset': reset_count,
            'scanned': len(found_models),
            'marked': marked_count,
            'found_models': found_models,
            'apps_folder_empty': len(found_models) == 0
        }, message=f"Rescanned: {marked_count} used models found")
        
    except Exception as e:
        current_app.logger.error(f'Error rescanning used models: {e}')
        return api_error("Failed to rescan used models", details={"reason": str(e)})


@models_bp.route('/sync', methods=['POST'])
def api_models_sync():
    """Sync filesystem model/app directories into the database."""
    try:
        from app.services.model_sync_service import sync_models_from_filesystem
        summary = sync_models_from_filesystem()
        summary['success'] = True
        return api_success(summary)
    except Exception as e:  # pragma: no cover - unexpected failures
        current_app.logger.error(f"Filesystem sync failed: {e}")
        return api_error("Filesystem model sync failed", details={"reason": str(e)})


# Model container operations moved to separate endpoints for clarity

@models_bp.route('/<model_slug>/containers/start', methods=['POST'])
def api_model_start_containers(model_slug):
    """Start all application containers for a model."""
    try:
        from app.services import application_service as app_service
        result = app_service.start_model_containers(model_slug)
        response = api_success(result, message=f'Model {model_slug} applications started')
        # Trigger front-end grid refresh if HTMX
        if request.headers.get('HX-Request'):
            from flask import make_response
            resp = make_response(response[0], response[1])
            resp.headers['HX-Trigger'] = 'refresh-grid'
            return resp
        return response
    except Exception as e:  # pragma: no cover - unexpected
        return api_error(f'Failed to start containers for model {model_slug}: {e}')


@models_bp.route('/<model_slug>/containers/stop', methods=['POST'])
def api_model_stop_containers(model_slug):
    """Stop all running application containers for a model."""
    try:
        from app.services import application_service as app_service
        result = app_service.stop_model_containers(model_slug)
        response = api_success(result, message=f'Model {model_slug} applications stopped')
        if request.headers.get('HX-Request'):
            from flask import make_response
            resp = make_response(response[0], response[1])
            resp.headers['HX-Trigger'] = 'refresh-grid'
            return resp
        return response
    except Exception as e:  # pragma: no cover
        return api_error(f'Failed to stop containers for model {model_slug}: {e}')


@models_bp.route('/<model_slug>/containers/sync-status', methods=['POST'])
@models_bp.route('/model/<model_slug>/containers/sync-status', methods=['POST'])  # Legacy route support
def api_model_containers_sync_status(model_slug):
    """Return current application container statuses for a model."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).order_by(GeneratedApplication.app_number.asc()).all()
        
        # HTMX/HTML fragment variant: only table rows supported
        if (request.args.get('format') == 'html') or request.headers.get('HX-Request'):
            hx_target = request.headers.get('HX-Target', '')
            if 'model-apps-table-body' in hx_target:
                rows = []
                for a in apps:
                    status = (a.container_status or 'unknown').lower()
                    badge = 'success' if status == 'running' else 'secondary' if status == 'stopped' else 'warning'
                    rows.append(
                        f'<tr>'
                        f'<td class="text-nowrap"><span class="badge bg-secondary">#{a.app_number}</span></td>'
                        f'<td>{a.app_type or ""}</td>'
                        f'<td><span class="badge bg-{badge}">{status}</span></td>'
                        f'</tr>'
                    )
                return '\n'.join(rows)
            # Legacy cards/grid container variant (models page). Provide minimal card markup
            if 'model-apps' in hx_target or (request.args.get('format') == 'html'):
                cards = []
                for a in apps:
                    status = (a.container_status or 'unknown').lower()
                    badge = 'success' if status == 'running' else 'secondary' if status == 'stopped' else 'warning'
                    app_no = a.app_number
                    app_type = a.app_type or ''
                    cards.append(
                        '<div class="col-12 col-sm-6 col-md-4 col-lg-3 mb-3">'
                        '  <div class="card shadow-sm h-100">'
                        '    <div class="card-body p-3 d-flex flex-column">'
                        f'      <div class="d-flex justify-content-between align-items-center mb-2">'
                        f'        <span class="badge bg-secondary">#{app_no}</span>'
                        f'        <span class="badge bg-{badge}">{status}</span>'
                        '      </div>'
                        f'      <div class="small text-muted">{app_type}</div>'
                        '    </div>'
                        '  </div>'
                        '</div>'
                    )
                return '\n'.join(cards)
        
        # JSON response: simplified list
        return api_success({
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
        return api_error(f'Failed to sync container statuses for model {model_slug}: {e}')


@models_bp.route('/test')
def test_endpoint():
    """Test endpoint to verify models API is working"""
    return jsonify({"message": "Models API is working", "endpoint": "/api/models/test"})


@models_bp.route('/comparison/refresh', methods=['POST'])
def models_comparison_refresh():
    """Compute lightweight comparison metrics for provided models.
    
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
                    metrics[slug] = {  # type: ignore[assignment]
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
            baseline_metrics = metrics.get(bslug) or (metrics.get(model_slugs[0]) if model_slugs else {})  # type: ignore[assignment]
        elif baseline_kind in ('avg','average'):
            baseline_metrics = _aggregate('avg')
        elif baseline_kind in ('median','med'):
            baseline_metrics = _aggregate('median')
        else:  # default avg
            baseline_metrics = _aggregate('avg')

        # Summary stats for research insight
        summary = {}
        for k in numeric_keys:
            vals = [float(metrics[s][k]) for s in model_slugs if isinstance(metrics.get(s, {}).get(k), (int,float))]  # type: ignore[arg-type]
            if not vals:
                continue
            try:
                summary[k] = {
                    'avg': round(sum(vals)/len(vals), 6),
                    'median': round(median(vals), 6),
                    'min': min(vals),  # type: ignore[arg-type]
                    'max': max(vals),  # type: ignore[arg-type]
                    'min_slug': next((s for s in model_slugs if float(metrics[s][k]) == min(vals)), None),  # type: ignore[arg-type]
                    'max_slug': next((s for s in model_slugs if float(metrics[s][k]) == max(vals)), None),  # type: ignore[arg-type]
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
        return jsonify({'models': [], 'baseline': 'avg', 'metrics': {}, 'error': str(e)}), 500