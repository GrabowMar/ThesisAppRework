"""
Models API Routes
================

API endpoints for AI model management and information.
"""

import logging
from typing import Any, Iterable, List
from flask import jsonify, render_template, request, Response
import os
from flask import current_app

from ..response_utils import json_success, handle_exceptions

from . import api_bp
from ...models import ModelCapability, GeneratedApplication, SecurityAnalysis, PerformanceTest
from ...extensions import db
import requests
import json
from datetime import datetime, timezone
import statistics
from ...services.data_initialization import data_init_service
from ...services.openrouter_service import OpenRouterService


def _upsert_openrouter_models(models_payload: list) -> int:
    """Upsert a list of OpenRouter model payloads into ModelCapability.

    Returns number of upserted rows.
    """
    upserted = 0
    for model_data in models_payload:
        model_id = model_data.get('id')
        if not model_id:
            continue
        # derive a safe canonical slug
        canonical = model_id.replace('/', '_').replace(':', '_')
        # If OpenRouter provides a canonical slug, normalize it
        raw_cs = model_data.get('canonical_slug') or ''
        if raw_cs:
            try:
                cs_norm = raw_cs.replace('/', '_').replace(':', '_').replace(' ', '_')
                # prefer the OpenRouter canonical if it looks useful
                canonical = cs_norm
            except Exception:
                pass
        provider = model_id.split('/')[0] if '/' in model_id else 'unknown'
        model_name = model_id.split('/')[-1]

        # Pricing extraction
        pricing = model_data.get('pricing', {}) or {}
        try:
            prompt_price = float(pricing.get('prompt') or pricing.get('prompt_tokens') or pricing.get('prompt_price') or 0)
        except Exception:
            prompt_price = 0.0
        try:
            completion_price = float(pricing.get('completion') or pricing.get('completion_price') or pricing.get('completion_tokens') or 0)
        except Exception:
            completion_price = 0.0

        context_window = None
        top_provider = model_data.get('top_provider') or {}
        if top_provider and top_provider.get('context_length'):
            try:
                context_window = int(top_provider.get('context_length') or 0)
            except Exception:
                context_window = None
        elif model_data.get('context_length'):
            try:
                context_window = int(model_data.get('context_length') or 0)
            except Exception:
                context_window = None

        existing = ModelCapability.query.filter_by(model_id=model_id).first()
        if not existing:
            existing = ModelCapability()
            existing.model_id = model_id
            existing.canonical_slug = canonical
            existing.provider = provider
            existing.model_name = model_name
            db.session.add(existing)
        else:
            existing.canonical_slug = canonical
            existing.provider = provider
            existing.model_name = model_name

        # Core numeric/boolean fields
        existing.is_free = bool(model_data.get('is_free', (prompt_price == 0 and completion_price == 0)))
        if context_window is not None:
            existing.context_window = context_window
        try:
            existing.input_price_per_token = prompt_price
        except Exception:
            pass
        try:
            existing.output_price_per_token = completion_price
        except Exception:
            pass

        # max output tokens
        try:
            existing.max_output_tokens = int(top_provider.get('max_completion_tokens') or model_data.get('max_output_tokens') or existing.max_output_tokens or 0)
        except Exception:
            pass

        # Performance metrics
        try:
            existing.cost_efficiency = float(model_data.get('cost_efficiency') or model_data.get('cost_efficiency_score') or existing.cost_efficiency or 0.0)
        except Exception:
            pass
        try:
            existing.safety_score = float(model_data.get('safety_score') or existing.safety_score or 0.0)
        except Exception:
            pass

        # Capability booleans
        existing.supports_function_calling = bool(model_data.get('supports_tool_calling') or model_data.get('supports_function_calling') or existing.supports_function_calling)
        existing.supports_json_mode = bool(model_data.get('supports_json') or model_data.get('supports_json_mode') or existing.supports_json_mode)
        existing.supports_streaming = bool(model_data.get('supports_streaming') or existing.supports_streaming)
        existing.supports_vision = bool(model_data.get('supports_vision') or existing.supports_vision)

        # Save the full OpenRouter payload in capabilities_json for later use
        try:
            existing.capabilities_json = json.dumps(model_data)
        except Exception:
            existing.capabilities_json = '{}'

        # Merge selected fields into metadata_json for quick access
        try:
            meta = existing.get_metadata() or {}
            meta.update({
                'openrouter_model_id': model_data.get('id'),
                'openrouter_name': model_data.get('name') or model_data.get('model_name'),
                'openrouter_created': model_data.get('created'),
                'openrouter_canonical_slug': model_data.get('canonical_slug'),
                'openrouter_description': model_data.get('description') or model_data.get('openrouter_description'),
                'openrouter_pricing': model_data.get('pricing', {}),
                'openrouter_supported_parameters': model_data.get('supported_parameters') or model_data.get('openrouter_supported_parameters'),
                'openrouter_top_provider': model_data.get('top_provider', {})
            })
            # copy some analytics fields if present
            for k in ('analyses_count', 'apps_count', 'architecture_input_modalities', 'architecture_modality', 'architecture_instruct_type', 'architecture_tokenizer'):
                if k in model_data:
                    meta[k] = model_data.get(k)
            existing.set_metadata(meta)
        except Exception:
            pass
        # Set installed flag by checking misc/models/<canonical_slug>
        try:
            repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
            models_base = os.path.join(repo_root, 'misc', 'models')
            existing.installed = os.path.isdir(os.path.join(models_base, existing.canonical_slug))
        except Exception:
            # leave existing.installed as-is on error
            pass

    existing.updated_at = datetime.now(timezone.utc)
    upserted += 1

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return upserted

# Set up logger
logger = logging.getLogger(__name__)

# Local OpenRouter service instance for this blueprint
_openrouter_service = OpenRouterService()


def _norm_caps(value: Any) -> List[str]:
    """Normalize various capability shapes into a list of strings.

    Accepts:
    - list/tuple of strings -> returns list
    - dict -> returns keys where value is truthy, or all keys if non-bool
    - string -> single-item list
    - None/other -> []
    """
    try:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            # Coerce all to strings just in case
            return [str(x) for x in value]
        if isinstance(value, dict):
            # Prefer truthy keys if boolean map, else all keys
            keys = []
            any_bool = any(isinstance(v, bool) for v in value.values())
            if any_bool:
                keys = [str(k) for k, v in value.items() if v]
            else:
                keys = [str(k) for k in value.keys()]
            return keys
        if isinstance(value, str):
            return [value]
        # Fallback: try to iterate
        if isinstance(value, Iterable):  # type: ignore[arg-type]
            return [str(x) for x in value]
    except Exception:
        pass
    return []


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
        # Optional installed-only filter via query param: prefer DB flag, fallback to filesystem
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        if installed_only:
            try:
                # Use DB indexed flag when available
                models = [m for m in models if getattr(m, 'installed', False)]
            except Exception:
                # Fallback: check filesystem for misc/models/<slug>
                repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                models_base = os.path.join(repo_root, 'misc', 'models')
                models = [m for m in models if os.path.isdir(os.path.join(models_base, m.canonical_slug))]
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

        # If DB is empty, try to fetch from OpenRouter (if API key configured) and upsert
        try:
            if not models:
                api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
                if api_key:
                    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
                    try:
                        # Be tolerant: OpenRouter may return data at top-level or under 'data' or 'models'.
                        resp = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
                        if resp.status_code == 200:
                            body = resp.json()
                            # Try common keys
                            payload = []
                            if isinstance(body, dict):
                                for key in ('data', 'models', 'items'):
                                    if key in body and isinstance(body[key], list):
                                        payload = body[key]
                                        break
                                # Sometimes endpoint returns list directly in body
                                if not payload and isinstance(body.get('results'), list):
                                    payload = body.get('results')
                            elif isinstance(body, list):
                                payload = body

                            # If payload large, we still upsert whatever we received; further pagination is not supported here.
                            if payload:
                                _upsert_openrouter_models(payload)
                                models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
                    except Exception:
                        # network or parsing errors are non-fatal here
                        pass
        except Exception:
            pass
        # Optional installed-only filter: prefer DB flag, fallback to filesystem
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        if installed_only:
            try:
                models = [m for m in models if getattr(m, 'installed', False)]
            except Exception:
                repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                models_base = os.path.join(repo_root, 'misc', 'models')
                models = [m for m in models if os.path.isdir(os.path.join(models_base, m.canonical_slug))]
        # Map to the fields referenced by the page's JS
        def map_model(m: ModelCapability):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            meta = m.get_metadata() or {}
            # Derive many fields and expose OpenRouter metadata where available
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
                # OpenRouter-specific passthrough fields
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
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            items.append({
                'slug': m.canonical_slug,
                'display_name': m.model_name,
                'name': m.model_name,
                'provider': m.provider,
                'status': 'active',
                'capabilities': caps_list,
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
        # Build base query for provider/search
        q = ModelCapability.query
        search = (request.args.get('search') or '').strip()
        # Support both single and multi-provider params: provider, providers=a,b
        provider = (request.args.get('provider') or '').strip()
        providers_param = (request.args.get('providers') or '').strip()
        providers = []
        if providers_param:
            providers = [p.strip() for p in providers_param.split(',') if p.strip()]
        elif provider:
            providers = [provider]

        if providers:
            # Case-insensitive provider match; OR across selected providers
            from sqlalchemy import or_
            ors = [ModelCapability.provider.ilike(p) for p in providers]
            q = q.filter(or_(*ors))
        if search:
            # search should match model_name, model_id, canonical_slug, provider, and metadata.description
            like = f"%{search}%"
            q = q.filter(
                (ModelCapability.model_name.ilike(like)) |
                (ModelCapability.model_id.ilike(like)) |
                (ModelCapability.canonical_slug.ilike(like)) |
                (ModelCapability.provider.ilike(like))
            )

        # Optional installed-only filter: prefer DB-level filter for performance
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        if installed_only:
            try:
                try:
                    # Prefer SQL expression for boolean columns
                    from sqlalchemy import true
                    q = q.filter(ModelCapability.installed.is_(true()))
                except Exception:
                    # Fallback boolean equality avoided; use is_ with Python True where supported
                    q = q.filter(ModelCapability.installed.is_(True))
            except Exception:
                # Fallback after query executed
                pass

        models = q.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # If installed flag couldn't be applied at DB-level and installed_only set, fallback to filesystem
        if installed_only:
            try:
                if not any(getattr(m, 'installed', False) for m in models):
                    repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                    models_base = os.path.join(repo_root, 'misc', 'models')
                    models = [m for m in models if os.path.isdir(os.path.join(models_base, m.canonical_slug))]
            except Exception:
                pass

        def map_model(m: ModelCapability):
            caps_raw = m.get_capabilities() or {}
            caps_list = _norm_caps(caps_raw.get('capabilities') if isinstance(caps_raw, dict) else caps_raw)
            return {
                'slug': m.canonical_slug,
                'name': m.model_name,
                'provider': m.provider,
                'provider_logo': '/static/images/default-avatar.svg',
                'capabilities': caps_list,
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'context_length': m.context_window or 0,
                'performance_score': int((m.cost_efficiency or 0.0) * 10) if (m.cost_efficiency or 0) <= 1 else int(m.cost_efficiency or 0),
                'status': 'active',
                'description': (m.get_metadata() or {}).get('description')
            }

        models_list = [map_model(m) for m in models]

        # Additional in-memory filters for fields that are stored in JSON or require derived logic
        # Support both single and multi-capability params: capability, capabilities=a,b
        capability_filter = (request.args.get('capability') or '').strip().lower()
        capabilities_param = (request.args.get('capabilities') or '').strip().lower()
        capability_filters = []
        if capabilities_param:
            capability_filters = [c.strip() for c in capabilities_param.split(',') if c.strip()]
        elif capability_filter:
            capability_filters = [capability_filter]
        price_filter = (request.args.get('price') or '').strip().lower()
        context_filter = (request.args.get('context') or '').strip().lower()
    # size_filter intentionally not used at this time (kept for future UI mapping)
        status_filter = (request.args.get('status') or '').strip().lower()
        specialization_filter = (request.args.get('specialization') or '').strip().lower()

        def matches_price(m):
            if not price_filter:
                return True
            # price categories: free, low (0-0.01), medium (0.01-0.05), high (0.05+)
            try:
                inp = float(m.get('input_price_per_1k') or 0)
                out = float(m.get('output_price_per_1k') or 0)
                avg = (inp + out) / 2
            except Exception:
                return False
            if price_filter == 'free':
                return avg == 0
            if price_filter == 'low':
                return avg <= 1.0  # since prices are per-1k scaled numbers; keep conservative bounds
            if price_filter == 'medium':
                return 1.0 < avg <= 50.0
            if price_filter == 'high':
                return avg > 50.0
            return True

        def matches_context(m):
            if not context_filter:
                return True
            try:
                ctx = int(m.get('context_length') or 0)
            except Exception:
                return False
            if context_filter == 'short':
                return ctx <= 4000
            if context_filter == 'medium':
                return 4000 < ctx <= 32000
            if context_filter == 'long':
                return 32000 < ctx <= 128000
            if context_filter == 'extended':
                return ctx >= 128000
            return True

        def matches_capability(m):
            if not capability_filters:
                return True
            caps = m.get('capabilities') or []
            # Normalize caps into list of lowercase strings
            if isinstance(caps, dict):
                caps_list = [k.lower() for k, v in caps.items() if bool(v)] or [k.lower() for k in caps.keys()]
            elif isinstance(caps, (list, tuple)):
                caps_list = [(c or '').lower() for c in caps]
            else:
                caps_list = [str(caps).lower()]
            # Match ANY of selected capabilities (OR semantics)
            return any(cf in caps_list or any(cf in c for c in caps_list) for cf in capability_filters)

        def matches_status(m):
            if not status_filter:
                return True
            return status_filter == (m.get('status') or '').lower()

        def matches_specialization(m):
            if not specialization_filter:
                return True
            desc = (m.get('description') or '')
            name = (m.get('name') or '')
            return specialization_filter in desc.lower() or specialization_filter in name.lower()

        filtered_models = [m for m in models_list if matches_capability(m) and matches_price(m) and matches_context(m) and matches_status(m) and matches_specialization(m)]
        providers = {m.provider for m in models}
        stats = {
            'total_models': len(filtered_models),
            'active_models': len(filtered_models),
            'unique_providers': len(providers),
            'avg_cost_per_1k': round(sum(x['input_price_per_1k'] for x in filtered_models) / max(len(filtered_models), 1), 6)
        }
        return jsonify({'models': filtered_models, 'statistics': stats})
    except Exception as e:
        logger.error(f"Error building models/filtered payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


# =================================================================
# OPENROUTER SOURCE: LIST AND FILTERED
# =================================================================

def _map_openrouter_model_to_table(m: dict, installed_slugs: set[str]) -> dict:
    """Map a raw OpenRouter model dict to the table row structure used by the UI."""
    try:
        model_id = m.get('id') or ''
        provider = model_id.split('/')[0] if '/' in model_id else (m.get('provider') or 'unknown')
        model_name = model_id.split('/')[-1] if '/' in model_id else (m.get('name') or m.get('model') or '')
        canonical_slug = model_id.replace('/', '_').replace(':', '_')
        pricing = m.get('pricing', {}) or {}
        try:
            prompt_price = float(pricing.get('prompt') or 0)
        except Exception:
            prompt_price = 0.0
        try:
            completion_price = float(pricing.get('completion') or 0)
        except Exception:
            completion_price = 0.0
        is_free = (prompt_price == 0 and completion_price == 0)
        # context length
        context_len = 0
        try:
            if m.get('top_provider') and m['top_provider'].get('context_length'):
                context_len = int(m['top_provider'].get('context_length') or 0)
            elif m.get('context_length'):
                context_len = int(m.get('context_length') or 0)
        except Exception:
            context_len = 0
        # capabilities heuristic from architecture and flags
        caps: list[str] = []
        arch = m.get('architecture') or {}
        modality = (arch.get('modality') or arch.get('modalities') or '').lower()
        if 'vision' in modality or (m.get('supports_vision')):
            caps.append('vision')
        if 'text' in modality or 'language' in modality:
            caps.append('language')
        if m.get('supports_tool_calling') or m.get('supports_function_calling'):
            caps.append('function_calling')
        if m.get('supports_json') or m.get('supports_json_mode'):
            caps.append('json_mode')
        if m.get('supports_streaming'):
            caps.append('streaming')
        # mark free tier explicitly if available
        if is_free:
            caps.append('free')

        row = {
            'slug': canonical_slug,
            'model_id': model_id,
            'name': model_name or m.get('name') or canonical_slug,
            'provider': provider,
            'provider_logo': '/static/images/default-avatar.svg',
            'capabilities': caps,
            'input_price_per_1k': round(prompt_price * 1000, 6),
            'output_price_per_1k': round(completion_price * 1000, 6),
            'context_length': context_len,
            'max_output_tokens': int((m.get('top_provider') or {}).get('max_completion_tokens') or m.get('max_output_tokens') or 0) if isinstance(m.get('top_provider'), dict) else int(m.get('max_output_tokens') or 0) if m.get('max_output_tokens') else 0,
            'performance_score': 0,
            'status': 'active',
            'description': m.get('description') or '',
            'installed': canonical_slug in installed_slugs,
            'openrouter': {
                'model_id': model_id,
                'name': m.get('name') or model_name,
                'canonical_slug': m.get('canonical_slug'),
                'pricing': pricing,
                'top_provider': m.get('top_provider') or {}
            }
        }
        return row
    except Exception:
        return {
            'slug': m.get('id', 'unknown').replace('/', '_'),
            'model_id': m.get('id', ''),
            'name': m.get('name') or m.get('id', ''),
            'provider': (m.get('id', '').split('/')[0] if '/' in (m.get('id') or '') else 'unknown'),
            'provider_logo': '/static/images/default-avatar.svg',
            'capabilities': [],
            'input_price_per_1k': 0,
            'output_price_per_1k': 0,
            'context_length': 0,
            'max_output_tokens': 0,
            'performance_score': 0,
            'status': 'active',
            'description': m.get('description') or '',
            'installed': False,
            'openrouter': {'model_id': m.get('id')}
        }


def _installed_slugs_from_db_or_fs() -> set[str]:
    """Collect installed canonical slugs using DB flag with filesystem fallback."""
    slugs: set[str] = set()
    try:
        rows = ModelCapability.query.filter_by(installed=True).all()
        slugs.update({r.canonical_slug for r in rows if getattr(r, 'canonical_slug', None)})
    except Exception:
        pass
    try:
        # filesystem fallback
        repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
        models_base = os.path.join(repo_root, 'misc', 'models')
        if os.path.isdir(models_base):
            for name in os.listdir(models_base):
                path = os.path.join(models_base, name)
                if os.path.isdir(path):
                    slugs.add(name)
    except Exception:
        pass
    return slugs


@api_bp.route('/models/openrouter/all')
def api_models_openrouter_all():
    """Return all available models directly from OpenRouter mapped to table structure.

    Supports query param installed=1 to filter to installed-only (DB/FS based).
    """
    try:
        models = _openrouter_service.fetch_all_models() or []
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        installed_slugs = _installed_slugs_from_db_or_fs()
        mapped = [_map_openrouter_model_to_table(m, installed_slugs) for m in models]
        if installed_only:
            mapped = [m for m in mapped if m.get('installed')]
        providers = {m.get('provider') for m in mapped}
        stats = {
            'total_models': len(mapped),
            'active_models': len(mapped),
            'unique_providers': len(providers),
            'avg_cost_per_1k': round(sum(x.get('input_price_per_1k') or 0 for x in mapped) / max(len(mapped), 1), 6)
        }
        return jsonify({'models': mapped, 'statistics': stats})
    except Exception as e:
        logger.error(f"Error building openrouter/all payload: {e}")
        return jsonify({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


@api_bp.route('/models/openrouter/filtered')
def api_models_openrouter_filtered():
    """Return filtered OpenRouter models, mirroring /models/filtered query params."""
    try:
        models = _openrouter_service.fetch_all_models() or []
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}
        installed_slugs = _installed_slugs_from_db_or_fs()
        rows = [_map_openrouter_model_to_table(m, installed_slugs) for m in models]
        if installed_only:
            rows = [r for r in rows if r.get('installed')]

        # Build filters similar to api_models_filtered
        search = (request.args.get('search') or '').strip().lower()
        provider = (request.args.get('provider') or '').strip()
        providers_param = (request.args.get('providers') or '').strip()
        providers = []
        if providers_param:
            providers = [p.strip().lower() for p in providers_param.split(',') if p.strip()]
        elif provider:
            providers = [provider.lower()]

        capability_filter = (request.args.get('capability') or '').strip().lower()
        capabilities_param = (request.args.get('capabilities') or '').strip().lower()
        capability_filters = []
        if capabilities_param:
            capability_filters = [c.strip() for c in capabilities_param.split(',') if c.strip()]
        elif capability_filter:
            capability_filters = [capability_filter]
        price_filter = (request.args.get('price') or '').strip().lower()
        context_filter = (request.args.get('context') or '').strip().lower()
        status_filter = (request.args.get('status') or '').strip().lower()
        specialization_filter = (request.args.get('specialization') or '').strip().lower()

        def match_search(r):
            if not search:
                return True
            blob = ' '.join([str(r.get('name') or ''), str(r.get('provider') or ''), str(r.get('model_id') or ''), str(r.get('slug') or ''), str(r.get('description') or '')]).lower()
            return search in blob

        def match_providers(r):
            if not providers:
                return True
            return (r.get('provider') or '').lower() in providers

        def matches_capability(r):
            if not capability_filters:
                return True
            caps = r.get('capabilities') or []
            caps = [str(c).lower() for c in (caps if isinstance(caps, list) else [caps])]
            return any(cf in caps or any(cf in c for c in caps) for cf in capability_filters)

        def matches_price(r):
            if not price_filter:
                return True
            try:
                avg = ((float(r.get('input_price_per_1k') or 0) + float(r.get('output_price_per_1k') or 0)) / 2.0)
            except Exception:
                return False
            if price_filter == 'free':
                return avg == 0
            if price_filter == 'low':
                return avg <= 1.0
            if price_filter == 'medium':
                return 1.0 < avg <= 50.0
            if price_filter == 'high':
                return avg > 50.0
            return True

        def matches_context(r):
            if not context_filter:
                return True
            try:
                ctx = int(r.get('context_length') or 0)
            except Exception:
                return False
            if context_filter == 'short':
                return ctx <= 4000
            if context_filter == 'medium':
                return 4000 < ctx <= 32000
            if context_filter == 'long':
                return 32000 < ctx <= 128000
            if context_filter == 'extended':
                return ctx >= 128000
            return True

        def matches_status(r):
            if not status_filter:
                return True
            return status_filter == (r.get('status') or '').lower()

        def matches_specialization(r):
            if not specialization_filter:
                return True
            desc = (r.get('description') or '')
            name = (r.get('name') or '')
            return specialization_filter in desc.lower() or specialization_filter in name.lower()

        filtered = [r for r in rows if match_search(r) and match_providers(r) and matches_capability(r) and matches_price(r) and matches_context(r) and matches_status(r) and matches_specialization(r)]
        providers_set = {r.get('provider') for r in filtered}
        stats = {
            'total_models': len(filtered),
            'active_models': len(filtered),
            'unique_providers': len(providers_set),
            'avg_cost_per_1k': round(sum(x.get('input_price_per_1k') or 0 for x in filtered) / max(len(filtered), 1), 6)
        }
        return jsonify({'models': filtered, 'statistics': stats})
    except Exception as e:
        logger.error(f"Error building openrouter/filtered payload: {e}")
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


@api_bp.route('/models/load-openrouter', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_models_load_openrouter():
    """Load/refresh ModelCapability rows from OpenRouter API.

    POST-only endpoint. Requires OPENROUTER_API_KEY in environment or app config.
    This will upsert ModelCapability rows for each model returned by OpenRouter.
    """
    api_key = os.getenv('OPENROUTER_API_KEY') or current_app.config.get('OPENROUTER_API_KEY')
    if not api_key:
        return jsonify({'success': False, 'error': 'OPENROUTER_API_KEY not configured'}), 400

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }

    try:
        resp = requests.get('https://openrouter.ai/api/v1/models', headers=headers, timeout=30)
        if resp.status_code != 200:
            logger.error(f'OpenRouter models fetch failed: {resp.status_code} {resp.text[:200]}')
            return jsonify({'success': False, 'error': f'OpenRouter API returned {resp.status_code}'}), 502

        body = resp.json()
        # Accept multiple response shapes
        if isinstance(body, dict):
            data = body.get('data') or body.get('models') or body.get('items') or body.get('results') or []
        elif isinstance(body, list):
            data = body
        else:
            data = []

        upserted = 0
        for model_data in data or []:
            model_id = model_data.get('id')
            if not model_id:
                continue
            canonical = model_id.replace('/', '_').replace(':', '_')
            provider = model_id.split('/')[0] if '/' in model_id else 'unknown'
            model_name = model_id.split('/')[-1]

            pricing = model_data.get('pricing', {}) or {}
            try:
                prompt_price = float(pricing.get('prompt', 0) or 0)
            except Exception:
                prompt_price = 0.0
            try:
                completion_price = float(pricing.get('completion', 0) or 0)
            except Exception:
                completion_price = 0.0

            context_window = None
            top_provider = model_data.get('top_provider') or {}
            if top_provider and top_provider.get('context_length'):
                try:
                    context_window = int(top_provider.get('context_length') or 0)
                except Exception:
                    context_window = None
            elif model_data.get('context_length'):
                try:
                    context_window = int(model_data.get('context_length') or 0)
                except Exception:
                    context_window = None

            # Upsert
            existing = ModelCapability.query.filter_by(model_id=model_id).first()
            if not existing:
                existing = ModelCapability()
                existing.model_id = model_id
                existing.canonical_slug = canonical
                existing.provider = provider
                existing.model_name = model_name
                db.session.add(existing)
            else:
                existing.canonical_slug = canonical
                existing.provider = provider
                existing.model_name = model_name

            # Update fields
            existing.is_free = bool(model_data.get('is_free', (prompt_price == 0 and completion_price == 0)))
            if context_window is not None:
                existing.context_window = context_window
            try:
                existing.input_price_per_token = float(model_data.get('prompt_price') or model_data.get('prompt') or prompt_price)
            except Exception:
                existing.input_price_per_token = prompt_price
            try:
                existing.output_price_per_token = float(model_data.get('completion_price') or model_data.get('completion') or completion_price)
            except Exception:
                existing.output_price_per_token = completion_price

            try:
                existing.max_output_tokens = int(top_provider.get('max_completion_tokens') or model_data.get('max_output_tokens') or existing.max_output_tokens or 0)
            except Exception:
                pass

            try:
                existing.cost_efficiency = float(model_data.get('cost_efficiency') or model_data.get('cost_efficiency_score') or existing.cost_efficiency or 0.0)
            except Exception:
                pass
            try:
                existing.safety_score = float(model_data.get('safety_score') or existing.safety_score or 0.0)
            except Exception:
                pass

            existing.supports_function_calling = bool(model_data.get('supports_tool_calling') or model_data.get('supports_function_calling') or existing.supports_function_calling)
            existing.supports_json_mode = bool(model_data.get('supports_json') or model_data.get('supports_json_mode') or existing.supports_json_mode)
            existing.supports_streaming = bool(model_data.get('supports_streaming') or existing.supports_streaming)
            existing.supports_vision = bool(model_data.get('supports_vision') or existing.supports_vision)

            try:
                existing.capabilities_json = json.dumps(model_data)
            except Exception:
                existing.capabilities_json = '{}'

            try:
                meta = existing.get_metadata() or {}
                meta_fields = {
                    'openrouter_model_id': model_data.get('id'),
                    'openrouter_name': model_data.get('name'),
                    'openrouter_created': model_data.get('created'),
                    'openrouter_canonical_slug': model_data.get('canonical_slug'),
                    'openrouter_pricing': model_data.get('pricing', {}),
                    'openrouter_top_provider': model_data.get('top_provider', {})
                }
                meta.update(meta_fields)
                existing.set_metadata(meta)
            except Exception:
                pass

            try:
                repo_root = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
                models_base = os.path.join(repo_root, 'misc', 'models')
                existing.installed = os.path.isdir(os.path.join(models_base, existing.canonical_slug))
            except Exception:
                pass

            existing.updated_at = datetime.now(timezone.utc)
            upserted += 1

        db.session.commit()

        # Optionally mark installed models automatically after loading from OpenRouter.
        try:
            mark_res = data_init_service.mark_installed_models(reset_first=False)
        except Exception:
            mark_res = {'success': False, 'updated': 0}

        return jsonify({'success': True, 'upserted': upserted, 'fetched': len(data or []), 'mark_installed': mark_res})
    except Exception as e:
        logger.error(f'Error loading models from OpenRouter: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/models/mark-installed', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_models_mark_installed():
    """Scan misc/models and set ModelCapability.installed=True for matching canonical_slugs.

    POST-only. Returns counts of updated records. This avoids doing filesystem checks on every filter request.
    """
    try:
        # Delegate to data initialization service helper which centralizes misc/models scanning
        try:
            res = data_init_service.mark_installed_models(reset_first=True)
            status_code = 200 if res.get('success', False) else 400
            return jsonify(res), status_code
        except Exception as e:
            logger.error(f'Error in mark-installed delegate: {e}')
            return jsonify({'success': False, 'error': str(e), 'updated': 0}), 500
    except Exception as e:
        logger.error(f'Error marking installed models: {e}')
        return jsonify({'success': False, 'error': str(e)}), 500


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


# =================================================================
# MODEL EXPORT ENDPOINT
# =================================================================

@api_bp.route('/models/export')
def api_models_export():
    """Export models data in JSON or CSV format.

    Query params:
    - format: json | csv | xlsx (xlsx not supported yet; returns 400)
    - installed: if truthy (1/true), export only models marked installed
    """
    try:
        export_format = (request.args.get('format') or 'json').lower()
        installed_param = request.args.get('installed') or request.args.get('installed_only')
        installed_only = str(installed_param).lower() in {'1', 'true', 'yes', 'on'}

        q = ModelCapability.query
        if installed_only:
            try:
                from sqlalchemy import true
                q = q.filter(ModelCapability.installed.is_(true()))
            except Exception:
                q = q.filter(ModelCapability.installed.is_(True))

        models = q.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # Build a flat export-friendly structure
        rows = []
        for m in models:
            meta = m.get_metadata() or {}
            row = {
                'provider': m.provider,
                'model_name': m.model_name,
                'model_id': m.model_id,
                'slug': m.canonical_slug,
                'installed': bool(getattr(m, 'installed', False)),
                'context_window': m.context_window or 0,
                'max_output_tokens': m.max_output_tokens or 0,
                'supports_function_calling': bool(m.supports_function_calling),
                'supports_json_mode': bool(m.supports_json_mode),
                'supports_streaming': bool(m.supports_streaming),
                'supports_vision': bool(m.supports_vision),
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                # Selected OpenRouter fields if present in metadata
                'openrouter_model_id': meta.get('openrouter_model_id'),
                'openrouter_name': meta.get('openrouter_name'),
                'openrouter_canonical_slug': meta.get('openrouter_canonical_slug'),
                'openrouter_created': meta.get('openrouter_created'),
                'openrouter_top_provider': meta.get('openrouter_top_provider'),
            }
            rows.append(row)

        if export_format == 'json':
            return jsonify({'models': rows, 'count': len(rows)})
        elif export_format == 'csv':
            try:
                # Reuse utility to generate CSV content
                from ...utils.helpers import dicts_to_csv
                csv_content = dicts_to_csv(rows, fieldnames=list(rows[0].keys()) if rows else None)
            except Exception:
                # Minimal fallback CSV
                headers = ['provider', 'model_name', 'slug']
                csv_content = ','.join(headers) + '\n' + '\n'.join(
                    f"{r.get('provider','')},{r.get('model_name','')},{r.get('slug','')}" for r in rows
                )
            filename = 'models_export.csv' if not installed_only else 'models_export_installed.csv'
            return Response(csv_content, mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={filename}'})
        elif export_format == 'xlsx':
            return jsonify({'error': 'xlsx export not supported yet. Use format=csv or format=json.'}), 400
        else:
            return jsonify({'error': f"Unknown export format: {export_format}"}), 400
    except Exception as e:
        logger.error(f"Error exporting models: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# COMPARISON STUB ENDPOINTS (basic placeholders for UI wiring)
# =================================================================

@api_bp.route('/models/comparison/refresh', methods=['POST'])
def api_models_comparison_refresh():
    """Render a comparison matrix fragment for selected models.

    Accepts form field 'models' as comma-separated slugs or multiple 'models[]'.
    Returns an HTML fragment with a compact table comparing key metrics.
    """
    try:
        # Accept either models (csv string) or models[] repeated fields
        selected: list[str] = []
        if 'models[]' in request.form:
            selected = [s for s in request.form.getlist('models[]') if s]
        elif request.form.get('models'):
            selected = [s for s in (request.form.get('models') or '').split(',') if s]

        # Require at least two models for a meaningful comparison. Do not hard-cap the maximum here;
        # the client or downstream export may apply limits. If fewer than 2 selected, render empty fragment with notice.
        if not selected or len(selected) < 2:
            # Render fragment with no models to show a helpful message
            return render_template('partials/models/comparison_matrix.html', models=[])

        # Fetch selected models preserving order
        slug_to_model: dict[str, ModelCapability] = {}
        rows = ModelCapability.query.filter(ModelCapability.canonical_slug.in_(selected)).all()
        for m in rows:
            slug_to_model[m.canonical_slug] = m

        # Map to comparison-friendly dicts
        def map_row(m: ModelCapability) -> dict:
            meta = m.get_metadata() or {}
            return {
                'slug': m.canonical_slug,
                'name': m.model_name,
                'provider': m.provider,
                'context_length': m.context_window or 0,
                'max_output_tokens': m.max_output_tokens or 0,
                'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                'supports_function_calling': bool(m.supports_function_calling),
                'supports_json_mode': bool(m.supports_json_mode),
                'supports_streaming': bool(m.supports_streaming),
                'supports_vision': bool(m.supports_vision),
                'openrouter_model_id': meta.get('openrouter_model_id'),
            }

        ordered_models = [map_row(slug_to_model[s]) for s in selected if s in slug_to_model]

        # Baseline selection: avg | median | model:<slug> (default avg)
        baseline_choice = (request.form.get('baseline') or request.args.get('baseline') or 'avg')
        baseline_choice = baseline_choice.lower() if isinstance(baseline_choice, str) else 'avg'
        numeric_keys = ['input_price_per_1k', 'output_price_per_1k', 'context_length', 'max_output_tokens']

        baseline_stats: dict = {}
        # compute baseline values per metric
        # support model:<slug> to use a selected model as the baseline
        if baseline_choice.startswith('model:'):
            bslug = baseline_choice.split(':', 1)[1]
            # find the model dict
            base_model = next((m for m in ordered_models if m.get('slug') == bslug), None)
            if base_model:
                for k in numeric_keys:
                    baseline_stats[k] = float(base_model.get(k) or 0)
            else:
                # fallback to avg if not found
                for k in numeric_keys:
                    vals = [float(m.get(k) or 0) for m in ordered_models]
                    baseline_stats[k] = float(sum(vals) / len(vals)) if vals else 0.0
        else:
            for k in numeric_keys:
                vals = [float(m.get(k) or 0) for m in ordered_models]
                if not vals:
                    baseline_stats[k] = 0
                    continue
                try:
                    if baseline_choice == 'median':
                        baseline_stats[k] = float(statistics.median(vals))
                    else:
                        baseline_stats[k] = float(sum(vals) / len(vals))
                except Exception:
                    baseline_stats[k] = float(sum(vals) / len(vals)) if vals else 0.0

        # colorize relative to baseline. For prices, lower is better; for context/max_out higher is better.
        def color_for(value: float, baseline: float, higher_is_better: bool = True) -> str:
            try:
                if baseline == 0:
                    # baseline zero: treat zero as best for prices; otherwise non-zero is worse
                    if value == 0:
                        return 'text-success'
                    return 'text-danger' if not higher_is_better else 'text-success'
                ratio = value / baseline
            except Exception:
                return 'text-muted'
            # thresholds: within 5% -> yellow, >5% better -> green, >5% worse -> red
            lower = 0.95
            upper = 1.05
            if higher_is_better:
                if ratio >= upper:
                    return 'text-success'
                if lower <= ratio < upper:
                    return 'text-warning'
                return 'text-danger'
            else:
                # lower is better (price)
                if ratio <= lower:
                    return 'text-success'
                if lower < ratio <= upper:
                    return 'text-warning'
                return 'text-danger'

        # Enrich each model dict with color hints
        for m in ordered_models:
            m['input_price_color'] = color_for(float(m.get('input_price_per_1k') or 0), baseline_stats.get('input_price_per_1k', 0), higher_is_better=False)
            m['output_price_color'] = color_for(float(m.get('output_price_per_1k') or 0), baseline_stats.get('output_price_per_1k', 0), higher_is_better=False)
            m['context_color'] = color_for(float(m.get('context_length') or 0), baseline_stats.get('context_length', 0), higher_is_better=True)
            m['max_out_color'] = color_for(float(m.get('max_output_tokens') or 0), baseline_stats.get('max_output_tokens', 0), higher_is_better=True)

        return render_template('partials/models/comparison_matrix.html', models=ordered_models, baseline_choice=baseline_choice, baseline_stats=baseline_stats)
    except Exception as e:
        logger.error(f"Comparison refresh error: {e}")
        return f"<div class='alert alert-danger'>Error: {str(e)}</div>", 500


@api_bp.route('/models/comparison/update', methods=['POST'])
def api_models_comparison_update():
    """Stub: update comparison parameters."""
    try:
        payload = {
            'success': True,
            'message': 'Comparison parameters accepted (stub)',
            'received': request.form.to_dict()
        }
        return jsonify(payload)
    except Exception as e:
        logger.error(f"Comparison update error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/models/comparison/export')
def api_models_comparison_export():
    """Export comparison data for selected models in csv or json.

    Query params: format=csv|json, models=slug1,slug2,... (max 5)
    """
    try:
        fmt = (request.args.get('format') or 'csv').lower()
        slugs = [s for s in (request.args.get('models') or '').split(',') if s]
    # No server-side hard cap: allow as many slugs as the caller provides.
    # Large requests may be rate-limited or otherwise protected by external
    # infrastructure; keep the payload handling simple here.
        if fmt not in {'csv', 'json'}:
            return jsonify({'error': f'Unsupported format: {fmt}'}), 400

        if not slugs:
            data: list[dict] = []
        else:
            rows = ModelCapability.query.filter(ModelCapability.canonical_slug.in_(slugs)).all()
            by_slug = {m.canonical_slug: m for m in rows}
            def map_row(m: ModelCapability) -> dict:
                return {
                    'slug': m.canonical_slug,
                    'name': m.model_name,
                    'provider': m.provider,
                    'context_length': m.context_window or 0,
                    'max_output_tokens': m.max_output_tokens or 0,
                    'input_price_per_1k': round((m.input_price_per_token or 0.0) * 1000, 6),
                    'output_price_per_1k': round((m.output_price_per_token or 0.0) * 1000, 6),
                    'supports_function_calling': bool(m.supports_function_calling),
                    'supports_json_mode': bool(m.supports_json_mode),
                    'supports_streaming': bool(m.supports_streaming),
                    'supports_vision': bool(m.supports_vision),
                }
            data = [map_row(by_slug[s]) for s in slugs if s in by_slug]

        if fmt == 'json':
            return jsonify({'models': data, 'count': len(data)})
        else:
            try:
                from ...utils.helpers import dicts_to_csv
                headers = list(data[0].keys()) if data else ['slug','name','provider']
                csv_content = dicts_to_csv(data, fieldnames=headers)
            except Exception:
                headers = ['slug','name','provider']
                csv_content = ','.join(headers) + '\n' + '\n'.join(
                    f"{r.get('slug','')},{r.get('name','')},{r.get('provider','')}" for r in data
                )
            return Response(csv_content, mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=comparison_export.csv'})
    except Exception as e:
        logger.error(f"Comparison export error: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# MODEL IMPORT ENDPOINT
# =================================================================

def _upsert_flat_models(rows: list[dict]) -> dict:
    """Upsert models from flat export-style rows.

    Each row may contain: provider, model_name, model_id, slug, input_price_per_1k,
    output_price_per_1k, context_window, max_output_tokens, supports_* booleans.
    """
    created = 0
    updated = 0
    errors: list[str] = []
    for r in rows:
        try:
            provider = (r.get('provider') or 'unknown').strip()
            model_name = (r.get('model_name') or r.get('name') or '').strip()
            slug = (r.get('slug') or r.get('canonical_slug') or '').strip()
            model_id = (r.get('model_id') or '').strip()
            if not slug:
                # derive a canonical slug from provider and model_name
                base = (model_name or model_id or 'model').replace('/', '_').replace(':', '_').replace(' ', '_')
                slug = f"{provider}_{base}" if provider else base

            # Prices are per 1k in export; convert back to per-token floats
            try:
                in_per_1k = float(r.get('input_price_per_1k') or 0)
            except Exception:
                in_per_1k = 0.0
            try:
                out_per_1k = float(r.get('output_price_per_1k') or 0)
            except Exception:
                out_per_1k = 0.0

            input_price_per_token = in_per_1k / 1000.0
            output_price_per_token = out_per_1k / 1000.0

            existing = ModelCapability.query.filter_by(canonical_slug=slug).first()
            is_new = existing is None
            m = existing or ModelCapability()

            # If new, set identity fields
            if is_new:
                m.canonical_slug = slug
                m.provider = provider
                m.model_name = model_name or slug
                m.model_id = model_id or f"{provider}/{model_name}" if provider and model_name else slug
                db.session.add(m)
            else:
                # Update core identifiers if provided
                if provider:
                    m.provider = provider
                if model_name:
                    m.model_name = model_name
                if model_id:
                    m.model_id = model_id

            # Common numeric/flags
            try:
                m.context_window = int(r.get('context_window') or m.context_window or 0)
            except Exception:
                pass
            try:
                m.max_output_tokens = int(r.get('max_output_tokens') or m.max_output_tokens or 0)
            except Exception:
                pass
            m.supports_function_calling = bool(r.get('supports_function_calling') or getattr(m, 'supports_function_calling', False))
            m.supports_json_mode = bool(r.get('supports_json_mode') or getattr(m, 'supports_json_mode', False))
            m.supports_streaming = bool(r.get('supports_streaming') or getattr(m, 'supports_streaming', False))
            m.supports_vision = bool(r.get('supports_vision') or getattr(m, 'supports_vision', False))
            try:
                m.input_price_per_token = float(input_price_per_token)
            except Exception:
                pass
            try:
                m.output_price_per_token = float(output_price_per_token)
            except Exception:
                pass
            # OpenRouter metadata passthrough if present in flat row
            meta = m.get_metadata() or {}
            for k in ('openrouter_model_id','openrouter_name','openrouter_canonical_slug','openrouter_created','openrouter_top_provider'):
                if r.get(k) is not None:
                    meta[k] = r.get(k)
            if meta:
                try:
                    m.set_metadata(meta)
                except Exception:
                    pass
            m.updated_at = datetime.now(timezone.utc)
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors.append(str(e))

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        errors.append(str(e))
    return {'created': created, 'updated': updated, 'errors': errors}


@api_bp.route('/models/import', methods=['POST'])
def api_models_import():
    """Import models from JSON payload.

    Accepts application/json bodies in two shapes:
    - {"models": [...]} where items are either flat export rows or OpenRouter model objects
    - [...] array at top-level
    Returns counts of upserts.
    """
    try:
        # Support JSON body only for now
        try:
            payload = request.get_json(force=True, silent=False)
        except Exception:
            return jsonify({'success': False, 'error': 'Invalid or missing JSON body'}), 400

        # Normalize to list
        items: list = []
        if isinstance(payload, dict) and 'models' in payload:
            items = payload.get('models') or []
        elif isinstance(payload, list):
            items = payload
        else:
            return jsonify({'success': False, 'error': 'Unsupported JSON shape; expected list or {"models": [...]}'}), 400

        if not isinstance(items, list) or not items:
            return jsonify({'success': False, 'imported': 0, 'message': 'No items to import'}), 200

        # Decide shape by inspecting first item
        first = items[0] if items else {}
        used_openrouter = False
        upsert_result = {'created': 0, 'updated': 0, 'errors': []}
        if isinstance(first, dict) and ('pricing' in first or 'top_provider' in first or 'architecture' in first) and 'id' in first:
            # Looks like OpenRouter payloads
            count_before = ModelCapability.query.count()
            upserted = _upsert_openrouter_models(items)
            count_after = ModelCapability.query.count()
            used_openrouter = True
            upsert_result = {'created': max(count_after - count_before, 0), 'updated': max(upserted - (count_after - count_before), 0), 'errors': []}
        else:
            # Flat export rows
            upsert_result = _upsert_flat_models(items)

        return jsonify({'success': True, 'import_strategy': 'openrouter' if used_openrouter else 'flat', **upsert_result})
    except Exception as e:
        logger.error(f"Error importing models: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
