"""Legacy-compatible batch control and partial endpoints.

These endpoints provide a minimal surface expected by legacy tests:
 - POST /batch/api/batch/dispatch-next : triggers dispatch of next pending job
 - GET  /batch/api/batch/export        : returns JSON export summary
 - GET  /batch/partials/queue-status   : HTML fragment with queue stats
 - GET  /batch/partials/job-list       : HTML fragment with simple job list

They intentionally use simplified logic mapped onto the modern batch_service.
"""

from flask import Blueprint, jsonify, current_app
from app.services.task_service import queue_service, batch_service as modern_batch_service
from app.utils.template_paths import render_template_compat

batch_compat_bp = Blueprint('batch_compat', __name__)


@batch_compat_bp.route('/batch/api/batch/dispatch-next', methods=['POST'])
def legacy_dispatch_next():
    """Dispatch the next pending job (legacy shim)."""
    try:
        # Call dispatch_next if available on the modern batch service
        if hasattr(modern_batch_service, 'dispatch_next'):
            result = getattr(modern_batch_service, 'dispatch_next')()
        else:
            result = {'dispatched': 0, 'reason': 'dispatch_next not implemented'}
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        current_app.logger.error(f"dispatch-next error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@batch_compat_bp.route('/batch/api/batch/export')
def legacy_batch_export():
    """Return a minimal export of current batch jobs."""
    try:
        jobs = getattr(modern_batch_service, 'list_jobs', lambda: [])()
        # Fallback: infer jobs from internal storage if list_jobs absent
        if not jobs and hasattr(modern_batch_service, '_jobs'):
            jobs = list(getattr(modern_batch_service, '_jobs').values())  # type: ignore[index]
        payload = []
        for j in jobs:
            job_dict = getattr(j, 'to_dict', lambda: {})()
            if not job_dict:
                # Construct minimal dict
                job_dict = {
                    'job_id': getattr(j, 'job_id', None),
                    'status': getattr(j, 'status', None),
                    'total_tasks': getattr(j, 'total_tasks', None),
                    'completed_tasks': getattr(j, 'completed_tasks', None),
                }
            payload.append(job_dict)
        return jsonify({'success': True, 'jobs': payload, 'count': len(payload)})
    except Exception as e:
        current_app.logger.error(f"batch export error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@batch_compat_bp.route('/batch/partials/queue-status')
def legacy_queue_status_partial():
    """Render queue status fragment."""
    stats = queue_service.get_queue_status() if queue_service else {}
    return render_template_compat('partials/batch/queue_status.html', stats=stats)


@batch_compat_bp.route('/batch/partials/job-list')
def legacy_job_list_partial():
    """Render job list fragment."""
    jobs = getattr(modern_batch_service, 'list_jobs', lambda: [])()
    return render_template_compat('partials/batch/job_list.html', jobs=jobs)
