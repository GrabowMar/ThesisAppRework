"""
Models routes for the Flask application
========================================"""

from __future__ import annotations

from typing import Any

from flask import Blueprint, current_app, flash, request, Response, redirect, url_for
from flask_login import current_user
from werkzeug.exceptions import HTTPException
from app.utils.template_paths import render_template_compat as render_template
from app.extensions import db
from app.models import (
    ModelCapability,
    GeneratedApplication,
    SecurityAnalysis,
    PerformanceTest,
    ExternalModelInfoCache,
)
from app.utils.helpers import deep_merge_dicts, dicts_to_csv
from sqlalchemy import or_
from app.routes.jinja.detail_context import build_model_detail_context

# Blueprint for models routes
models_bp = Blueprint('models', __name__, url_prefix='/models')


# Require authentication
@models_bp.before_request
def require_authentication():
    """Require authentication for all model endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access model features.', 'info')
        return redirect(url_for('auth.login', next=request.url))


def _enrich_model(m: ModelCapability) -> dict:
    """Minimal model enrichment used by CSV export and models filter/comparison.

    Avoids network calls; derives fields from stored capabilities/metadata.
    """
    try:
        caps_raw = m.get_capabilities() or {}
    except Exception:
        caps_raw = {}
    try:
        meta = m.get_metadata() or {}
    except Exception:
        meta = {}

    # Normalize capabilities to a simple dict/list when possible
    caps: Any = {}
    if isinstance(caps_raw, dict):
        caps = caps_raw.get('capabilities') if 'capabilities' in caps_raw else caps_raw
    else:
        # Best-effort: if it's a sequence, map to a flag dict; otherwise keep empty
        try:
            caps_iter = list(caps_raw)  # type: ignore[arg-type]
            caps = {str(k): True for k in caps_iter}
        except Exception:
            caps = {}

    # Map a small set of openrouter- style fields from metadata when present
    data = {
        'provider': m.provider,
        'name': m.model_name,
        'capabilities': caps if isinstance(caps, (dict, list)) else {},
        'openrouter_context_length': meta.get('openrouter_context_length') or meta.get('context_length') or m.context_window,
        'openrouter_prompt_price': meta.get('openrouter_prompt_price') or meta.get('input_price_per_1k'),
        'openrouter_completion_price': meta.get('openrouter_completion_price') or meta.get('output_price_per_1k'),
        'openrouter_pricing_request': meta.get('openrouter_pricing_request'),
        'openrouter_pricing_image': meta.get('openrouter_pricing_image'),
        'openrouter_pricing_web_search': meta.get('openrouter_pricing_web_search'),
        'openrouter_pricing_internal_reasoning': meta.get('openrouter_pricing_internal_reasoning'),
        'openrouter_pricing_input_cache_read': meta.get('openrouter_pricing_input_cache_read'),
        'openrouter_pricing_input_cache_write': meta.get('openrouter_pricing_input_cache_write'),
        'architecture_modality': meta.get('architecture_modality'),
        'architecture_input_modalities': meta.get('architecture_input_modalities'),
        'architecture_output_modalities': meta.get('architecture_output_modalities'),
        'architecture_tokenizer': meta.get('architecture_tokenizer'),
        'architecture_instruct_type': meta.get('architecture_instruct_type'),
        'performance_score': meta.get('performance_score') or m.cost_efficiency,
        # Additional fields from OpenRouter API
        'hugging_face_id': meta.get('hugging_face_id') or caps.get('hugging_face_id') if isinstance(caps, dict) else None,
        'default_parameters': meta.get('default_parameters') or (caps.get('default_parameters') if isinstance(caps, dict) else None),
        'openrouter_created': meta.get('created') or (caps.get('created') if isinstance(caps, dict) else None),
        'openrouter_name': meta.get('name') or meta.get('openrouter_name'),
        'openrouter_description': meta.get('description') or meta.get('openrouter_description'),
        'openrouter_canonical_slug': meta.get('canonical_slug') or meta.get('openrouter_canonical_slug') or m.canonical_slug,
        'openrouter_supported_parameters': meta.get('supported_parameters') or (caps.get('supported_parameters') if isinstance(caps, dict) else None),
        'openrouter_per_request_limits': meta.get('per_request_limits') or (caps.get('per_request_limits') if isinstance(caps, dict) else None),
        'top_provider_context_length': meta.get('top_provider_context_length') or (caps.get('top_provider', {}).get('context_length') if isinstance(caps, dict) and isinstance(caps.get('top_provider'), dict) else None),
        'top_provider_is_moderated': meta.get('top_provider_is_moderated') or (caps.get('top_provider', {}).get('is_moderated') if isinstance(caps, dict) and isinstance(caps.get('top_provider'), dict) else None),
        'top_provider_max_completion_tokens': meta.get('top_provider_max_completion_tokens') or (caps.get('top_provider', {}).get('max_completion_tokens') if isinstance(caps, dict) and isinstance(caps.get('top_provider'), dict) else None),
    }
    return data


@models_bp.route('/')
def models_index():
    """Legacy models index → redirect to main models overview page."""
    return redirect(url_for('main.models_overview'))


@models_bp.route('/models_overview')
def models_overview():
    """Compatibility endpoint name used by some templates; delegate to main."""
    return redirect(url_for('main.models_overview'))


@models_bp.route('/model_actions/<model_slug>')
@models_bp.route('/model_actions')
def model_actions(model_slug=None):
    """HTMX endpoint for model actions modal content."""
    try:
        if model_slug:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()

            app_count = GeneratedApplication.query.filter_by(model_slug=model_slug).count()
            security_count = db.session.query(SecurityAnalysis).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()
            performance_count = db.session.query(PerformanceTest).join(GeneratedApplication).filter(
                GeneratedApplication.model_slug == model_slug
            ).count()

            return render_template(
                'pages/models/partials/model_actions.html',
                model=model,
                stats={
                    'applications': app_count,
                    'security_tests': security_count,
                    'performance_tests': performance_count
                }
            )
        else:
            # Bulk operations modal - redirect to applications blueprint
            return redirect(url_for('applications.bulk_operations'))

    except Exception as e:
        current_app.logger.error(f"Error loading model actions for {model_slug}: {e}")
        return f'<div class="alert alert-danger">Error loading model actions: {str(e)}</div>'


@models_bp.route('/model_apps/<model_slug>')
def model_apps(model_slug):
    """View applications for a specific model."""
    try:
        # Route now serves as a compatibility alias. Redirect to Applications page
        # with model filter applied so the UI reflects the requested model.
        _ = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        return redirect(url_for('main.applications_index', model=model_slug))
    except Exception as e:
        current_app.logger.error(f"Error loading model apps for {model_slug}: {e}")
        flash(f'Error loading applications: {str(e)}', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Model Applications Error',
            error_message=str(e),
            python_version='3.11'
        )


@models_bp.route('/import')
def models_import_page():
    """Render a simple import page to upload JSON and call the API."""
    try:
        return render_template('pages/models/models_import.html')
    except Exception as e:
        current_app.logger.error(f"Error rendering models import page: {e}")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Import Page Error',
            error_message=str(e)
        ), 500


@models_bp.route('/export/models.csv')
def export_models_csv():
    """Export models overview to CSV with selected fields."""
    try:
        models = ModelCapability.query.order_by(
            ModelCapability.provider, ModelCapability.model_name
        ).all()
        rows = []
        for m in models:
            data = _enrich_model(m)
            cached = ExternalModelInfoCache.query.filter_by(model_slug=m.canonical_slug).first()
            if cached:
                try:
                    data = deep_merge_dicts(data, cached.get_data())
                except Exception:  # pragma: no cover
                    pass
            rows.append({
                'provider': m.provider,
                'model_name': m.model_name,
                'slug': m.canonical_slug,
                'context_window': data.get('openrouter_context_length') or m.context_window,
                'prompt_price': data.get('openrouter_prompt_price'),
                'completion_price': data.get('openrouter_completion_price'),
                'pricing_request': data.get('openrouter_pricing_request'),
                'pricing_image': data.get('openrouter_pricing_image'),
                'pricing_web_search': data.get('openrouter_pricing_web_search'),
                'pricing_internal_reasoning': data.get('openrouter_pricing_internal_reasoning'),
                'pricing_input_cache_read': data.get('openrouter_pricing_input_cache_read'),
                'pricing_input_cache_write': data.get('openrouter_pricing_input_cache_write'),
                'modality': data.get('architecture_modality'),
                'input_modalities': '|'.join(data.get('architecture_input_modalities') or []) if isinstance(data.get('architecture_input_modalities'), list) else data.get('architecture_input_modalities'),
                'output_modalities': '|'.join(data.get('architecture_output_modalities') or []) if isinstance(data.get('architecture_output_modalities'), list) else data.get('architecture_output_modalities'),
                'tokenizer': data.get('architecture_tokenizer'),
                'instruct_type': data.get('architecture_instruct_type'),
                'supported_parameters': '|'.join(data.get('openrouter_supported_parameters') or []) if isinstance(data.get('openrouter_supported_parameters'), list) else data.get('openrouter_supported_parameters'),
                'is_free': m.is_free,
            })

        csv_content = dicts_to_csv(rows)
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=models_export.csv'}
        )
    except Exception as e:  # pragma: no cover - export failures rare
        current_app.logger.error(f"Error exporting models CSV: {e}")
        return Response('provider,model_name,slug\n', mimetype='text/csv')


@models_bp.route('/filter')
def models_filter():
    """HTMX endpoint: Return filtered models grid for dynamic updates."""
    try:
        # Get filter parameters
        search = request.args.get('search', '').strip()
        provider = request.args.get('provider', '').strip()
        capabilities = request.args.get('capabilities', '').strip()
        pricing = request.args.get('pricing', '').strip()
        sort = request.args.get('sort', 'name')

        # Base query
        query = ModelCapability.query

        # Apply filters
        if provider:
            query = query.filter(ModelCapability.provider.ilike(f'%{provider}%'))

        if search:
            query = query.filter(
                or_(
                    ModelCapability.model_name.ilike(f'%{search}%'),
                    ModelCapability.provider.ilike(f'%{search}%'),
                    ModelCapability.canonical_slug.ilike(f'%{search}%')
                )
            )

        if pricing:
            if pricing == 'free':
                query = query.filter(ModelCapability.is_free)
            elif pricing == 'paid':
                query = query.filter(~ModelCapability.is_free)

        # Apply sorting
        if sort == 'provider':
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        elif sort == 'cost':
            # Sort by pricing (this is approximate since pricing comes from OpenRouter)
            query = query.order_by(ModelCapability.provider, ModelCapability.model_name)
        else:  # name
            query = query.order_by(ModelCapability.model_name)

        models = query.all()

        # Enrich models with OpenRouter data and filter by capabilities
        enriched_models = []
        for model in models:
            enriched_data = _enrich_model(model)
            app_count = GeneratedApplication.query.filter_by(model_slug=model.canonical_slug).count()
            enriched_data['apps_count'] = app_count

            # Filter by capabilities if specified
            if capabilities:
                model_caps = enriched_data.get('capabilities', {})
                cap_supported = False

                if capabilities == 'text' and model_caps.get('text'):
                    cap_supported = True
                elif capabilities == 'vision' and (model_caps.get('vision') or model_caps.get('images')):
                    cap_supported = True
                elif capabilities == 'multimodal' and model_caps.get('multimodal'):
                    cap_supported = True
                elif capabilities == 'function_calling' and model_caps.get('function_calling'):
                    cap_supported = True
                elif capabilities == 'streaming' and model_caps.get('streaming'):
                    cap_supported = True

                if not cap_supported:
                    continue

            enriched_models.append(enriched_data)

        # Return just the models grid
        return render_template('pages/models/partials/models-grid.html', models=enriched_models)

    except Exception as e:
        current_app.logger.error(f"Error filtering models: {e}")
        return f'<div class="alert alert-danger">Error filtering models: {str(e)}</div>', 500


@models_bp.route('/comparison')
def models_comparison():
    """Render comparison page with optional selected models list."""
    try:
        raw = request.args.get('models', '')
        slugs = [s.strip() for s in raw.split(',') if s.strip()][:6]  # limit to 6 for layout
        selected_models = []
        comparison_rows = []
        capability_union: set[str] = set()
        pricing = []
        if slugs:
            for slug in slugs:
                m = ModelCapability.query.filter_by(canonical_slug=slug).first()
                if not m:
                    continue
                data = _enrich_model(m)
                caps = data.get('capabilities') or {}
                # normalize capability keys
                if isinstance(caps, dict):
                    for k, v in caps.items():
                        if v:
                            capability_union.add(k)
                # Normalize price fields to float (original sources may be strings like '0.0012')
                def _to_float(v):
                    try:
                        if v is None or v == '':
                            return 0.0
                        return float(v)
                    except Exception:
                        return 0.0
                selected_models.append({
                    'slug': slug,
                    'name': data.get('name') or m.model_name,
                    'provider': data.get('provider') or m.provider,
                    'context_length': data.get('openrouter_context_length') or m.context_window,
                    'input_price': _to_float(data.get('openrouter_prompt_price') or data.get('input_price_per_1k')),
                    'output_price': _to_float(data.get('openrouter_completion_price') or data.get('output_price_per_1k')),
                    'performance_score': data.get('performance_score'),
                    'capabilities': caps,
                })
            # Pricing delta baseline (first model)
            if selected_models:
                base = selected_models[0]
                b_in = float(base.get('input_price') or 0) or 0.0
                b_out = float(base.get('output_price') or 0) or 0.0
                for sm in selected_models:
                    in_p = float(sm.get('input_price') or 0) or 0.0
                    out_p = float(sm.get('output_price') or 0) or 0.0
                    pricing.append({
                        'slug': sm['slug'],
                        'name': sm['name'],
                        'input_price': in_p,
                        'output_price': out_p,
                        'input_delta': (in_p - b_in) if b_in else None,
                        'output_delta': (out_p - b_out) if b_out else None,
                    })
            # Capability matrix
            capability_list = sorted(capability_union)
            for cap in capability_list:
                row = {'capability': cap, 'support': []}
                for sm in selected_models:
                    caps = sm.get('capabilities') or {}
                    val = False
                    if isinstance(caps, dict):
                        val = bool(caps.get(cap))
                    elif isinstance(caps, list):
                        val = cap in caps
                    row['support'].append(val)
                comparison_rows.append(row)
        return render_template(
            'pages/models/models_comparison.html',
            models=selected_models,
            pricing=pricing,
            capability_rows=comparison_rows,
            selected_models=slugs,
        )
    except Exception as e:
        current_app.logger.error(f"Error building comparison page: {e}")
        flash('Error building comparison', 'error')
        return render_template(
            'pages/errors/errors_main.html',
            error_code=500,
            error_title='Comparison Error',
            error_message=str(e)
        ), 500


# Model details routes (placed at end to avoid conflicts with static routes)
@models_bp.route('/<model_slug>')
def model_details(model_slug):
    """Detailed view of a specific model."""
    try:
        context = build_model_detail_context(model_slug, enrich_model=_enrich_model)
        return render_template('pages/models/models_detail.html', **context)
    except HTTPException:
        raise
    except Exception as exc:
        current_app.logger.error("Error loading model details for %s: %s", model_slug, exc)
        flash(f"Error loading model details: {exc}", "error")
        return render_template(
            'pages/errors/errors_main.html',
            error_code=404,
            error_title='Model Not Found',
            error_message=f"Model '{model_slug}' not found"
        )


@models_bp.route('/<model_slug>/refresh', methods=['POST'])
def refresh_model_data(model_slug):
    """Force refresh OpenRouter data for a specific model."""
    try:
        from app.services.service_locator import ServiceLocator
        from app.services.openrouter_service import OpenRouterService
        
        # Verify model exists
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first_or_404()
        
        # Get OpenRouter service
        openrouter_service: OpenRouterService | None = ServiceLocator.get('openrouter_service')  # type: ignore[assignment]
        if not openrouter_service:
            return {'error': 'OpenRouter service not available'}, 503
        
        # Clear cache for this model
        from app.models import OpenRouterModelCache, ExternalModelInfoCache
        OpenRouterModelCache.query.filter_by(model_id=model.model_id).delete()
        ExternalModelInfoCache.query.filter_by(model_slug=model_slug).delete()
        db.session.commit()
        
        # Fetch fresh data
        fresh_data = openrouter_service.fetch_model_by_id(model.model_id)
        if not fresh_data:
            # Try alternate ID format
            if '_' in model_slug:
                provider, model_part = model_slug.split('_', 1)
                alt_id = f"{provider}/{model_part}"
                fresh_data = openrouter_service.fetch_model_by_id(alt_id)
        
        if fresh_data:
            # Store in external cache
            from datetime import timedelta
            extracted = openrouter_service._extract_openrouter_details(fresh_data)
            
            # Create or update cache entry
            cache_entry = ExternalModelInfoCache.query.filter_by(model_slug=model_slug).first()
            if cache_entry:
                cache_entry.set_data(extracted)
                cache_entry.mark_refreshed(ttl_hours=24)
                cache_entry.source_notes = 'openrouter_api'
            else:
                cache_entry = ExternalModelInfoCache()
                cache_entry.model_slug = model_slug
                cache_entry.set_data(extracted)
                cache_entry.cache_expires_at = cache_entry.last_refreshed + timedelta(hours=24)
                cache_entry.source_notes = 'openrouter_api'
                db.session.add(cache_entry)
            
            db.session.commit()
            
            current_app.logger.info(f"Refreshed OpenRouter data for model {model_slug}")
            return {'success': True, 'message': 'Model data refreshed successfully', 'updated_at': cache_entry.updated_at.isoformat()}
        else:
            current_app.logger.warning(f"Could not fetch fresh data for model {model_slug}")
            return {'success': False, 'message': 'Could not fetch fresh data from OpenRouter'}, 404
            
    except Exception as exc:
        current_app.logger.error(f"Error refreshing model data for {model_slug}: {exc}")
        db.session.rollback()
        return {'error': str(exc)}, 500


@models_bp.route('/detail/<model_slug>/section/<section>')
def model_section(model_slug, section):
    """Render specific sections of model details page (HTMX)."""
    try:
        context = build_model_detail_context(model_slug, enrich_model=_enrich_model)
        section_cfg = context.get('sections_map', {}).get(section)
        if not section_cfg:
            current_app.logger.warning(f"Unknown section '{section}' requested for model '{model_slug}'")
            return render_template(
                'shared/components/_error_section.html',
                error_title='Unknown Section',
                error_message=f"The section '{section}' does not exist for this model.",
                error_icon='fas fa-question-circle'
            ), 404
        
        current_app.logger.debug(f"Rendering section '{section}' for model '{model_slug}' using template '{section_cfg['template']}'")
        return render_template(section_cfg['template'], **context)
    except HTTPException as http_ex:
        current_app.logger.error(f"HTTP exception rendering section {section} for {model_slug}: {http_ex}")
        return render_template(
            'shared/components/_error_section.html',
            error_title='Section Load Failed',
            error_message=f"Could not load {section} section: {str(http_ex)}",
            error_icon='fas fa-exclamation-triangle',
            retry_url=f"/models/detail/{model_slug}/section/{section}"
        ), http_ex.code or 500
    except Exception as exc:
        current_app.logger.error("Error rendering model section %s for %s: %s", section, model_slug, exc, exc_info=True)
        return render_template(
            'shared/components/_error_section.html',
            error_title='Section Error',
            error_message=f"An unexpected error occurred loading {section}.",
            error_detail=str(exc) if current_app.debug else None,
            error_icon='fas fa-bug',
            retry_url=f"/models/detail/{model_slug}/section/{section}"
        ), 500
