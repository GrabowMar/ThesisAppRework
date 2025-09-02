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
from flask import Blueprint, request, current_app, jsonify

from app.utils.helpers import create_success_response, create_error_response
from app.services.sample_generation_service import get_sample_generation_service

sample_gen_bp = Blueprint('sample_generation_api', __name__, url_prefix='/api/sample-gen')


def _svc():  # small helper
    return get_sample_generation_service()


@sample_gen_bp.route('/status', methods=['GET'])
def get_status():
    """Get current generation activity status."""
    service = get_sample_generation_service()
    status = service.get_generation_status()
    return jsonify(status)

@sample_gen_bp.route('/models', methods=['GET'])
def list_models():
    """List all available models from the model registry."""
    try:
        models = _svc().model_registry.get_available_models()
        return create_success_response(models, message="Models fetched")
    except Exception as e:
        current_app.logger.exception("Failed listing models")
        return create_error_response(str(e), 500)

@sample_gen_bp.route('/templates', methods=['GET'])
def list_templates():
    try:
        return create_success_response(_svc().list_templates(), message="Templates fetched")
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("Failed listing templates")
        return create_error_response(str(e), 500)


@sample_gen_bp.route('/templates/load-dir', methods=['POST'])
def load_templates_dir():
    data = request.get_json(silent=True) or {}
    directory = data.get('directory') or data.get('path')
    if not directory:
        return create_error_response("'directory' is required", 400)
    try:
        result = _svc().load_templates_from_directory(directory)
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
    temperature = data.get('temperature')
    max_tokens = data.get('max_tokens')
    try:
        result_id, result = asyncio.run(_svc().generate_async(template_id, model, temperature, max_tokens))
        payload = {"result_id": result_id, **result.to_dict(include_content=False)}
        return create_success_response(payload, message="Generation started")
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
    if not template_ids or not models:
        return create_error_response("'template_ids' and 'models' are required (non-empty lists)", 400)
    parallel_workers = int(data.get('parallel_workers', 3))
    try:
        result = asyncio.run(_svc().generate_batch_async([str(t) for t in template_ids], models, parallel_workers))
        return create_success_response(result, message="Batch generation complete")
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
        return create_success_response(payload, message="Regeneration completed")
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
