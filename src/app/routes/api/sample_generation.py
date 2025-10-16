"""Sample Generation API Routes
================================

Provides endpoints to manage templates and trigger AI-backed code generation
using the integrated SampleGenerationService.

Endpoints (prefixed with /api/sample-gen):
 - GET    /templates              List loaded templates
 - POST   /templates/load-dir     Load templates from a filesystem directory
 - POST   /templates/upsert       Upsert templates from JSON payload
 - POST   /generate               Generate code for a single template/model
 - POST   /generate/batch         Batch generation across multiple templates/models
 - GET    /results                List generation results (metadata only)
 - GET    /results/<result_id>    Get a single result (optionally include content)
 - GET    /structure              Get current generated project structure

Notes:
 - These routes perform network calls to OpenRouter and will block the request
   thread while awaiting async tasks via asyncio.run(). For large batches or
   high concurrency, consider delegating to a background worker.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, current_app, jsonify

from app.paths import APP_TEMPLATES_DIR, GENERATED_APPS_DIR, PROJECT_ROOT
from app.utils.helpers import create_success_response, create_error_response
from app.services.sample_generation_service import get_sample_generation_service, to_openrouter_slug

sample_gen_bp = Blueprint('sample_generation_api', __name__, url_prefix='/api/sample-gen')


def _svc():  # small helper
    return get_sample_generation_service()


@sample_gen_bp.route('/status', methods=['GET'])
def get_status():
    """Get current generation activity status."""
    service = get_sample_generation_service()
    status = service.get_generation_status()
    summary = service.get_summary_metrics()
    status.update(summary)
    status.setdefault('available_templates', summary.get('total_templates', 0))
    status.setdefault('connected_models', summary.get('total_models', 0))
    status['timestamp'] = datetime.utcnow().isoformat()
    return jsonify(status)

@sample_gen_bp.route('/models', methods=['GET'])
def list_models():
    """List all available models from the model registry."""
    try:
        mode = request.args.get('mode', 'scaffolded').lower()
        force_sync = request.args.get('sync', '0').lower() in ('1', 'true', 'yes')
        detail = request.args.get('detail', '0').lower() in ('1', 'true', 'yes')
        # Prefer database-backed list of models that have scaffolded applications
        model_slugs: list[str] = []
        try:
            from app.models import ModelCapability, GeneratedApplication  # type: ignore
            from sqlalchemy import exists  # type: ignore
            if force_sync:
                try:
                    from app.services.model_sync_service import sync_models_from_filesystem  # type: ignore
                    sync_models_from_filesystem()
                except Exception as sync_err:  # noqa: BLE001
                    current_app.logger.warning("Model filesystem sync failed: %s", sync_err)
            # Get models that have at least one GeneratedApplication
            db_models = (
                ModelCapability.query
                .filter(
                    exists().where(GeneratedApplication.model_slug == ModelCapability.canonical_slug)
                ).all()
            )
            for m in db_models:
                if not getattr(m, 'canonical_slug', None):
                    continue
                # Convert canonical_slug provider_model to provider/model for consistency with previous frontend expectations
                cs = m.canonical_slug
                if '_' in cs:
                    provider, rest = cs.split('_', 1)
                    model_slugs.append(f"{provider}/{rest}")
                else:
                    model_slugs.append(cs)
        except Exception as db_err:  # noqa: BLE001
            current_app.logger.warning("DB model fetch failed, falling back to registry: %s", db_err)
        # Fallback if no DB-derived scaffolded models
        if not model_slugs:
            # Attempt filesystem-based detection of scaffold directories under generated/apps
            discovered: set[str] = set()
            try:
                from app.services.model_sync_service import sync_models_from_filesystem  # type: ignore

                search_roots = [GENERATED_APPS_DIR, PROJECT_ROOT / 'generated']
                for gen_dir in search_roots:
                    if not gen_dir.exists():
                        continue
                    for child in gen_dir.iterdir():
                        if not child.is_dir():
                            continue
                        if not any(p.is_dir() for p in child.glob('app*')):
                            continue
                        discovered.add(to_openrouter_slug(child.name))

                if discovered:
                    model_slugs.extend(sorted(discovered))

                # Attempt a sync so DB gets populated for next call
                try:
                    sync_models_from_filesystem()
                except Exception:
                    pass
            except Exception as fs_err:
                current_app.logger.debug("Filesystem model discovery failed: %s", fs_err)
        registry_models = _svc().model_registry.get_available_models()
        if mode != 'scaffolded':  # union of all known models
            union = sorted(set(model_slugs) | set(registry_models))
            if detail:
                detailed = []
                reg = _svc().model_registry
                for slug in union:
                    info = reg.get_model_info(slug)
                    detailed.append({
                        'name': slug,
                        'provider': info.provider,
                        'is_free': info.is_free or slug.endswith(':free'),
                        'capabilities': sorted(list(info.capabilities)),
                    })
                return create_success_response(detailed, message="All models (detailed)")
            return create_success_response(union, message="All models (scaffolded + available)")
        # Final fallback to legacy in-memory registry if still empty (so UI not empty)
        if not model_slugs:
            model_slugs = registry_models
        model_slugs = sorted(set(model_slugs))
        if detail:
            detailed = []
            reg = _svc().model_registry
            for slug in model_slugs:
                info = reg.get_model_info(slug)
                detailed.append({
                    'name': slug,
                    'provider': info.provider,
                    'is_free': info.is_free or slug.endswith(':free'),
                    'capabilities': sorted(list(info.capabilities)),
                })
            return create_success_response(detailed, message="Scaffolded models fetched (detailed)")
        return create_success_response(model_slugs, message="Scaffolded models fetched")
    except Exception as e:
        current_app.logger.exception("Failed listing models")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/templates', methods=['GET'])
def list_templates():
    try:
        templates = _svc().list_templates()
        current_app.logger.info(f"Templates available: {len(templates)} total")
        for template in templates:
            current_app.logger.info(f"Template: {template.get('name')} (app_num: {template.get('app_num')}, type: {template.get('template_type')})")
        return create_success_response(templates, message="Templates fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed listing templates")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/templates/app/<path:template_path>', methods=['GET'])
def get_template_content(template_path: str):
    """Get template content for preview (handles frontend/backend template pairs)."""
    try:
        # Extract app_num from template path (e.g., "1.md" -> 1)
        app_num_str = template_path.replace('.md', '').replace('.txt', '')
        try:
            app_num = int(app_num_str)
        except ValueError:
            return create_error_response(f"Invalid app number in template path: {template_path}", 400)
            
        service = _svc()
        templates = service.template_registry.templates
        
        # Find frontend and backend templates for this app
        frontend_template = None
        backend_template = None
        
        for template in templates:
            if template.app_num == app_num:
                if template.template_type and 'frontend' in template.template_type.lower():
                    frontend_template = template
                elif template.template_type and 'backend' in template.template_type.lower():
                    backend_template = template
                elif not template.template_type or template.template_type == 'generic':
                    # Use generic template as fallback
                    if not frontend_template:
                        frontend_template = template
                    if not backend_template:
                        backend_template = template
        
        # Combine content from both templates for preview
        content_parts = []
        
        if frontend_template:
            content_parts.append(f"# Frontend Template\n\n{frontend_template.content}")
            
        if backend_template:
            content_parts.append(f"# Backend Template\n\n{backend_template.content}")
        
        if not content_parts:
            return create_error_response(f"No templates found for app {app_num}", 404)
        
        combined_content = "\n\n---\n\n".join(content_parts)
        
        return create_success_response({
            "content": combined_content,
            "app_num": app_num,
            "has_frontend": frontend_template is not None,
            "has_backend": backend_template is not None,
            "frontend_requirements": frontend_template.requirements if frontend_template else [],
            "backend_requirements": backend_template.requirements if backend_template else []
        }, message="Template content fetched")
        
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed getting template content for path %s", template_path)
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/templates/load-dir', methods=['POST'])
def load_templates_dir():
    data = request.get_json(silent=True) or {}
    directory = data.get('directory') or data.get('path')
    try:
        if directory:
            candidate = Path(directory)
            if not candidate.is_absolute():
                candidate = (PROJECT_ROOT / directory).resolve()
            if not candidate.exists():
                current_app.logger.warning(
                    "Template directory %s not found, falling back to default %s",
                    directory,
                    APP_TEMPLATES_DIR,
                )
                candidate = APP_TEMPLATES_DIR
        else:
            candidate = APP_TEMPLATES_DIR

        result = _svc().load_templates_from_directory(candidate)
        return create_success_response(result, message="Templates loaded from directory")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed loading templates dir")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/templates/upsert', methods=['POST'])
def upsert_templates():
    data = request.get_json(silent=True) or {}
    templates = data.get('templates')
    if not isinstance(templates, list):
        return create_error_response("'templates' list required", 400)
    try:
        result = _svc().upsert_templates(templates)
        return create_success_response(result, message="Templates upserted")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed upserting templates")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/generate', methods=['POST'])
def generate_single():
    data = request.get_json(silent=True) or {}
    template_id = data.get('template_id') or data.get('template')
    model = data.get('model')
    if not template_id or not model:
        return create_error_response("'template_id' and 'model' are required", 400)
    numeric_fields = {
        'temperature': float,
        'top_p': float,
        'top_k': int,
        'min_p': float,
        'frequency_penalty': float,
        'presence_penalty': float,
        'repetition_penalty': float,
        'max_tokens': int,
        'seed': int,
    }
    generation_overrides: dict[str, float | int] = {}
    for key, caster in numeric_fields.items():
        raw_value = data.get(key)
        if raw_value in (None, '', []):
            continue
        try:
            parsed = caster(raw_value)
        except (TypeError, ValueError):
            current_app.logger.warning("Ignoring invalid %s override: %r", key, raw_value)
            continue
        generation_overrides[key] = parsed

    temperature = generation_overrides.pop('temperature', None)
    if temperature is not None:
        try:
            temperature = float(temperature)
        except (TypeError, ValueError):
            current_app.logger.warning("Invalid temperature override discarded: %r", temperature)
            temperature = None
    max_tokens = generation_overrides.pop('max_tokens', None)
    if max_tokens is not None:
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError):
            current_app.logger.warning("Invalid max_tokens override discarded: %r", max_tokens)
            max_tokens = None
    # New options for file replacement behavior
    create_backup = data.get('create_backup', True)
    generate_frontend = data.get('generate_frontend', True)
    generate_backend = data.get('generate_backend', True)
    
    # Debug logging to check if parameters are received correctly
    current_app.logger.info(f"Generation request: template_id={template_id}, model={model}")
    current_app.logger.info(f"Options: create_backup={create_backup}, generate_frontend={generate_frontend}, generate_backend={generate_backend}")
    if generation_overrides:
        current_app.logger.info("Model overrides: %s", generation_overrides)
    
    try:
        # Use the new dual-generation method that makes separate frontend/backend calls
        results = asyncio.run(_svc().generate_frontend_backend_async(
            template_id, model, temperature, max_tokens, create_backup, 
            generate_frontend, generate_backend, generation_overrides or None
        ))
        
        # Return information about both generations
        return create_success_response(results, message="File replacement completed")
    except ValueError as ve:  # Template not found etc.
        return create_error_response(str(ve), 404)
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Generation failed")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/generate/batch', methods=['POST'])
def generate_batch():
    data = request.get_json(silent=True) or {}
    template_ids = data.get('template_ids') or data.get('templates') or []
    models = data.get('models') or []
    current_app.logger.info(f"[ROUTE] generate_batch called: templates={template_ids}, models={models}")
    if not template_ids or not models:
        return create_error_response("'template_ids' and 'models' are required (non-empty lists)", 400)
    parallel_workers = int(data.get('parallel_workers', 3))
    try:
        current_app.logger.info(f"[ROUTE] Calling generate_batch_async with {len(template_ids)} templates, {len(models)} models")
        result = asyncio.run(_svc().generate_batch_async([str(t) for t in template_ids], models, parallel_workers))
        current_app.logger.info(f"[ROUTE] generate_batch_async returned: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        return create_success_response(result, message="Batch file replacement complete")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Batch generation failed")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/batches', methods=['GET'])
def list_batch_operations():
    """List all batch operations with their progress."""
    try:
        service = get_sample_generation_service()
        batches = service.list_batch_operations()
        return jsonify({
            "success": True,
            "data": batches,
            "message": f"Found {len(batches)} batch operations"
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed to list batch operations")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/batches/<batch_id>', methods=['GET'])
def get_batch_progress(batch_id):
    """Get progress information for a specific batch operation."""
    try:
        service = get_sample_generation_service()
        progress = service.get_batch_progress(batch_id)
        if not progress:
            return create_error_response(f"Batch operation {batch_id} not found", 404)
        
        return jsonify({
            "success": True,
            "data": progress,
            "message": f"Batch progress for {batch_id}"
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed to get batch progress for %s", batch_id)
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/batches/cleanup', methods=['POST'])
def cleanup_completed_batches():
    """Clean up completed batch operations older than specified hours."""
    try:
        data = request.get_json() or {}
        max_age_hours = int(data.get('max_age_hours', 24))
        
        service = get_sample_generation_service()
        cleaned_count = service.cleanup_completed_batches(max_age_hours)
        
        return jsonify({
            "success": True,
            "data": {"cleaned_count": cleaned_count, "max_age_hours": max_age_hours},
            "message": f"Cleaned up {cleaned_count} completed batch operations"
        })
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed to cleanup batch operations")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/results', methods=['GET'])
def list_results():
    try:
        model = request.args.get('model')
        success_param = request.args.get('success')
        success = None
        if success_param is not None:
            if success_param.lower() in ('true', '1', 'yes'):
                success = True
            elif success_param.lower() in ('false', '0', 'no'):
                success = False
        try:
            limit = int(request.args.get('limit', 50))
        except ValueError:
            limit = 50
        try:
            offset = int(request.args.get('offset', 0))
        except ValueError:
            offset = 0
        results = _svc().list_results(model=model, success=success, limit=limit, offset=offset)
        return create_success_response(results, message="Results fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed listing results")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/results/<result_id>', methods=['GET'])
def get_result(result_id: str):
    include_content = request.args.get('include_content', 'false').lower() in ('1', 'true', 'yes')
    try:
        res = _svc().get_result(result_id, include_content=include_content)
        if not res:
            return create_error_response("Result not found", 404)
        return create_success_response(res, message="Result fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed retrieving result")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/results/<result_id>/meta', methods=['GET'])
def get_result_metadata(result_id: str):
    """Return metadata for a generation result without full content payload.

    Includes timing, token usage, attempts, block summaries, and port replacement info.
    """
    try:
        res = _svc().get_result(result_id, include_content=False)
        if not res:
            return create_error_response("Result not found", 404)
        # Ensure meta shape stable (no raw content even if backend included by mistake)
        res.pop('content', None)
        return create_success_response(res, message="Result metadata fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed retrieving result metadata")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/results/<result_id>', methods=['DELETE'])
def delete_result(result_id: str):
    try:
        deleted = _svc().delete_result(result_id)
        if not deleted:
            return create_error_response("Result not found", 404)
        return create_success_response({"deleted": True}, message="Result deleted")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed deleting result")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/cleanup', methods=['POST'])
def cleanup_results():
    data = request.get_json(silent=True) or {}
    max_age_days = int(data.get('max_age_days', 30))
    dry_run = bool(data.get('dry_run', False))
    try:
        result = _svc().cleanup_old_results(max_age_days=max_age_days, dry_run=dry_run)
        return create_success_response(result, message="Cleanup completed")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed cleanup")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/api-logs', methods=['GET'])
def get_api_logs():
    """Get OpenRouter API request/response logs for debugging."""
    try:
        model_filter = request.args.get('model')
        status_filter = request.args.get('status')
        limit = int(request.args.get('limit', 25))
        
        # Get all results with API data
        results = _svc().list_results(model=model_filter, limit=limit)
        
        # Filter and format for API logs view
        api_logs = []
        for result in results:
            # Skip results without API data
            if not result.get('request_payload') and not result.get('response_json'):
                continue
            
            # Filter by status if specified
            if status_filter:
                resp_status = result.get('response_status', 0)
                if status_filter == 'success' and resp_status != 200:
                    continue
                elif status_filter == 'error' and (resp_status == 200 or resp_status == 0):
                    continue
            
            log_entry = {
                'id': result.get('result_id'),
                'timestamp': result.get('timestamp'),
                'model': result.get('model'),
                'app_num': result.get('app_num'),
                'app_name': result.get('app_name'),
                'request_payload': result.get('request_payload', {}),
                'request_headers': result.get('request_headers', {}),
                'response_status': result.get('response_status', 0),
                'response_headers': result.get('response_headers', {}),
                'response_json': result.get('response_json', {}),
                'response_text': result.get('response_text', ''),
                'duration': result.get('duration', 0),
                'success': result.get('success', False),
                'error_message': result.get('error_message'),
                # Token usage
                'prompt_tokens': result.get('prompt_tokens', 0),
                'completion_tokens': result.get('completion_tokens', 0),
                'total_tokens': result.get('total_tokens', 0),
                'estimated_cost': result.get('estimated_cost', 0),
            }
            api_logs.append(log_entry)
        
        return create_success_response(api_logs, message=f"Found {len(api_logs)} API logs")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed to get API logs")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/regenerate', methods=['POST'])
def regenerate_result():
    data = request.get_json(silent=True) or {}
    result_id = data.get('result_id')
    if not result_id:
        return create_error_response("'result_id' is required", 400)
    temperature = data.get('temperature')
    max_tokens = data.get('max_tokens')
    try:
        new_result_id, result = _svc().regenerate(result_id, temperature, max_tokens)
        payload = {"result_id": new_result_id, **result.to_dict(include_content=False)}
        return create_success_response(payload, message="File replacement completed")
    except ValueError as ve:
        return create_error_response(str(ve), 404)
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed regeneration")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/structure', methods=['GET'])
def project_structure():
    try:
        return create_success_response(_svc().project_structure(), message="Project structure fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed getting structure")
        return create_error_response(str(e), 500)
