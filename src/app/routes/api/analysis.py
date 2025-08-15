"""Analysis API Routes (Refactored)
=================================

JSON endpoints now delegate to service layer (`analysis_service`) and return
standard response envelopes via `json_success` / `json_error` with the
`handle_exceptions` decorator centralizing error handling.

HTMX / template endpoints retained (will be incrementally migrated later).
"""

import logging
from flask import request, render_template, jsonify

from . import api_bp
from ..response_utils import json_success, json_error, handle_exceptions
from ...extensions import db
from ...models import BatchAnalysis, ContainerizedTest, GeneratedApplication
from ...services.analysis_service import (
    list_security_analyses,
    create_security_analysis,
    list_performance_tests,
    create_performance_test,
    list_dynamic_analyses,
    create_dynamic_analysis,
    start_dynamic_analysis,
    start_security_analysis,
    create_comprehensive_security_analysis,
    update_security_analysis,
    get_analysis_results as service_get_analysis_results,
    get_dynamic_results as service_get_dynamic_results,
    AnalysisServiceError, NotFoundError, ValidationError, InvalidStateError, TaskEnqueueError
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Error Mapping Helpers
# ---------------------------------------------------------------------------

ERROR_STATUS = {
    NotFoundError: 404,
    ValidationError: 400,
    InvalidStateError: 409,
    TaskEnqueueError: 503,
}

def _map_service_error(exc: Exception):  # returns Flask response tuple
    status = ERROR_STATUS.get(exc.__class__, 500)
    return json_error(str(exc), status=status, error_type=exc.__class__.__name__)


@api_bp.route('/analysis/model/<model_slug>/security', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_model_security_batch(model_slug):
    """Create+start security analyses for all apps under a model."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        created_ids = []
        for app in apps:
            created = create_comprehensive_security_analysis(app.id, {"application_id": app.id})
            created_ids.append(created.get('id'))
            try:
                start_security_analysis(created['id'])
            except Exception as _:
                pass
        return json_success({'count': len(created_ids), 'analysis_ids': created_ids}, message='Security analyses started')
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/model/<model_slug>/performance', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_model_performance_batch(model_slug):
    """Create performance test records for all apps under a model."""
    try:
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        created_ids = []
        for app in apps:
            created = create_performance_test({"application_id": app.id})
            created_ids.append(created.get('id'))
        return json_success({'count': len(created_ids), 'test_ids': created_ids}, message='Performance tests created')
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/security')
@handle_exceptions(logger_override=logger)
def api_list_security_analyses():
    data = list_security_analyses()
    return json_success(data, message="Security analyses fetched")


@api_bp.route('/analysis/security', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_create_security_analysis():
    payload = request.get_json() or {}
    try:
        created = create_security_analysis(payload)
        return json_success(created, message="Security analysis created", status=201)
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/performance')
@handle_exceptions(logger_override=logger)
def api_list_performance_tests():
    data = list_performance_tests()
    return json_success(data, message="Performance tests fetched")


@api_bp.route('/analysis/performance', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_create_performance_test():
    payload = request.get_json() or {}
    try:
        created = create_performance_test(payload)
        return json_success(created, message="Performance test created", status=201)
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/dynamic')
@handle_exceptions(logger_override=logger)
def api_list_dynamic_analyses():
    data = list_dynamic_analyses()
    return json_success(data, message="Dynamic analyses fetched")


@api_bp.route('/analysis/dynamic', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_create_dynamic_analysis():
    payload = request.get_json() or {}
    try:
        created = create_dynamic_analysis(payload)
        return json_success(created, message="Dynamic analysis created", status=201)
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/dynamic/start', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_start_dynamic_analysis():
    payload = request.get_json() or {}
    if not payload.get('analysis_id'):
        return json_error("analysis_id required", status=400)
    try:
        started = start_dynamic_analysis(payload['analysis_id'])
        return json_success(started, message="Dynamic analysis started", status=201)
    except (AnalysisServiceError,) as exc:
        return _map_service_error(exc)


@api_bp.route('/analysis/batch')
def api_analysis_batch():
    """API endpoint: Get batch analyses."""
    try:
        batches = BatchAnalysis.query.all()
        return jsonify([batch.to_dict() for batch in batches])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting batch analyses: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/containerized')
def api_analysis_containerized():
    """API endpoint: Get containerized tests."""
    try:
        tests = ContainerizedTest.query.all()
        return jsonify([test.to_dict() for test in tests])
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting containerized tests: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch', methods=['POST'])
def api_create_batch():
    """API endpoint: Create batch analysis."""
    try:
        data = request.get_json() or {}
        import uuid
        from ...constants import JobStatus

        batch = BatchAnalysis()
        batch.batch_id = str(uuid.uuid4())
        batch.status = JobStatus.PENDING.value
        batch.total_tasks = data.get('total_tasks', 0)
        batch.completed_tasks = 0
        batch.failed_tasks = 0

        if 'analysis_types' in data:
            batch.set_analysis_types(data['analysis_types'])

        db.session.add(batch)
        db.session.commit()
        return jsonify(batch.to_dict()), 201

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error creating batch analysis: {e}")
        return jsonify({'error': str(e)}), 400


@api_bp.route('/batch/<batch_id>/status')
def api_batch_status(batch_id):
    """API endpoint: Get batch status."""
    try:
        batch = BatchAnalysis.query.filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404
        return jsonify(batch.to_dict())
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error getting batch status: {e}")
        return jsonify({'error': str(e)}), 500


# =================================================================
# ANALYSIS ORCHESTRATION AND CONFIGURATION
# =================================================================

@api_bp.route('/analysis/configure/<int:app_id>')
def api_analysis_configure_modal(app_id):
    """API endpoint to get analysis configuration modal."""
    try:
        app = GeneratedApplication.query.get(app_id)
        if not app:
            return f'<div class="alert alert-warning">Application {app_id} not found</div>', 404

        return render_template('partials/analysis_configure_modal.html', app=app)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error loading analysis configuration modal: {e}")
        return f'<div class="alert alert-danger">Error loading analysis configuration: {str(e)}</div>', 500


@api_bp.route('/analysis/start/<int:app_id>', methods=['POST'])
def api_analysis_start(app_id):
    """API endpoint to start comprehensive analysis for an application."""
    try:
        from ...services.background_service import get_background_service

        app = GeneratedApplication.query.get(app_id)
        if not app:
            return jsonify({'error': f'Application {app_id} not found'}), 404

        service = get_background_service()
        if service:
            task_id = f"comprehensive_analysis_{app_id}"
            service.create_task(
                task_id=task_id,
                task_type="comprehensive_analysis",
                message=f"Starting comprehensive analysis for application {app_id}"
            )
            service.start_task(task_id)
            return jsonify({'success': True, 'message': 'Comprehensive analysis started', 'task_id': task_id})
        return jsonify({'error': 'Background service not available'}), 503

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error starting analysis for app {app_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/security/<int:app_id>', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_analysis_security(app_id):
    try:
        created = create_security_analysis({"application_id": app_id})
        return json_success(created, message="Security analysis record created")
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)


@api_bp.route('/analysis/security/start', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_analysis_security_start():
    payload = request.get_json() or {}
    if not payload.get('application_id'):
        return json_error("Application ID required", status=400)
    try:
        created = create_comprehensive_security_analysis(payload['application_id'], payload)
        started = start_security_analysis(created['id'])
        return json_success({"created": created, "start": started}, message="Security analysis started", status=201)
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)


@api_bp.route('/analysis/security/configure', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_analysis_security_configure():
    payload = request.get_json() or {}
    if 'analysis_id' not in payload:
        return json_error("analysis_id required", status=400)
    try:
        updated = update_security_analysis(payload['analysis_id'], payload)
        return json_success(updated, message="Security analysis configuration saved")
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)


@api_bp.route('/analysis/performance/<int:app_id>', methods=['POST'])
@handle_exceptions(logger_override=logger)
def api_analysis_performance(app_id):
    try:
        created = create_performance_test({"application_id": app_id})
        return json_success(created, message="Performance test record created")
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)


@api_bp.route('/batch/active')
def api_batch_active():
    """API endpoint for active batch analyses (HTMX)."""
    try:
        from ...constants import JobStatus

        active_batches = db.session.query(BatchAnalysis).filter(
            BatchAnalysis.status.in_([JobStatus.RUNNING.value, JobStatus.PENDING.value])
        ).order_by(BatchAnalysis.created_at.desc()).all()

        return render_template('partials/active_batches.html', active_batches=active_batches)
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error loading active batches: {e}")
        return f'<div class="alert alert-danger">Error loading active batches: {str(e)}</div>'


@api_bp.route('/batch/create', methods=['POST'])
def api_batch_create():
    """API endpoint to create a new batch analysis."""
    try:
        from ...services.background_service import get_background_service
        from ...constants import JobStatus
        import uuid

        data = request.get_json() or {}
        batch_id_uuid = str(uuid.uuid4())
        batch = BatchAnalysis()
        batch.batch_id = batch_id_uuid
        batch.status = JobStatus.PENDING.value
        batch.total_tasks = data.get('total_tasks', 0)
        batch.completed_tasks = 0
        batch.failed_tasks = 0

        db.session.add(batch)
        db.session.commit()

        service = get_background_service()
        task = service.create_task(
            task_id=f"batch_{batch_id_uuid}",
            task_type="batch_analysis",
            message=f"Starting batch analysis with {data.get('total_tasks', 0)} tasks"
        ) if service else None

        return jsonify({
            'success': True,
            'batch_id': batch_id_uuid,
            'task_id': task.task_id if task else None
        })
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error creating batch: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/batch/<batch_id>/start', methods=['POST'])
def api_batch_start(batch_id):
    """API endpoint to start a batch analysis."""
    try:
        from ...services.background_service import get_background_service
        from ...constants import JobStatus
        from datetime import datetime, timezone

        batch = db.session.query(BatchAnalysis).filter_by(batch_id=batch_id).first()
        if not batch:
            return jsonify({'error': 'Batch not found'}), 404

        batch.status = JobStatus.RUNNING.value
        batch.started_at = datetime.now(timezone.utc)
        db.session.commit()

        service = get_background_service()
        if service:
            service.start_task(f"batch_{batch_id}")

        return jsonify({'success': True, 'status': 'started'})
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error starting batch {batch_id}: {e}")
        return jsonify({'error': str(e)}), 500


@api_bp.route('/analysis/security/<int:analysis_id>/results')
@handle_exceptions(logger_override=logger)
def api_analysis_security_results(analysis_id):
    try:
        result = service_get_analysis_results(analysis_id)
        return json_success(result, message="Security analysis results fetched")
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)


@api_bp.route('/analysis/dynamic/<int:analysis_id>/results')
@handle_exceptions(logger_override=logger)
def api_analysis_dynamic_results(analysis_id):
    try:
        result = service_get_dynamic_results(analysis_id)
        return json_success(result, message="Dynamic analysis results fetched")
    except (AnalysisServiceError,) as exc:  # pragma: no cover - defensive
        return _map_service_error(exc)
