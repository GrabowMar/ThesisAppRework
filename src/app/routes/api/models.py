"""
Models API routes
=================

Endpoints for model management, OpenRouter integration, and model metadata.
"""

import os
from flask import Blueprint, request, current_app

from app.models import ModelCapability, GeneratedApplication
from app.services.data_initialization import data_init_service
from app.utils.generated_apps import list_generated_models, load_model_capabilities
from ..shared_utils import _upsert_openrouter_models, _norm_caps
from .common import api_success, api_error


models_bp = Blueprint('models_api', __name__)


@models_bp.route('/')
def api_models():
    """Get all models (standardized envelope)."""
    models = ModelCapability.query.all()
    data = [{
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
        return api_success({'models': models_list, 'statistics': stats})
    except Exception as e:
        current_app.logger.error(f"Error building models/all payload: {e}")
        return api_success({'models': [], 'statistics': {'total_models': 0, 'active_models': 0, 'unique_providers': 0, 'avg_cost_per_1k': 0}})


@models_bp.route('/filtered')
def api_models_filtered():
    """Filtered models list used by models.js applyFilters()."""
    try:
        search = (request.args.get('search') or '').strip().lower()
        providers = {p.lower() for p in request.args.getlist('providers') if p.strip()}
        caps_filter = {c.lower() for c in request.args.getlist('capabilities') if c.strip()}
        price_tier = (request.args.get('price') or '').lower()

        base = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()

        # If DB empty, synthesize base list from filesystem so filtering still works
        if not base:
            try:
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