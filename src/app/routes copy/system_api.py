"""System & Analysis lightweight API endpoints for dashboard JS."""
from __future__ import annotations
from flask import Blueprint, jsonify
from sqlalchemy import text

from app.services.service_locator import ServiceLocator
from app.extensions import get_session

system_api_bp = Blueprint('system_api', __name__, url_prefix='/api/system')
analysis_api_bp = Blueprint('analysis_api', __name__, url_prefix='/api/analysis')

@system_api_bp.get('/db-health')
def db_health():  # pragma: no cover (simple smoke endpoint)
    ok = False
    details = {}
    try:
        with get_session() as session:
            session.execute(text('SELECT 1'))
        ok = True
    except Exception as exc:  # noqa: BLE001
        details['error'] = str(exc)
    return jsonify({'success': ok, 'status': 'healthy' if ok else 'unhealthy', 'details': details}), (200 if ok else 500)

@analysis_api_bp.get('/count')
def analysis_count():
    svc = ServiceLocator.get_batch_service()
    jobs = getattr(svc, 'list_jobs', lambda: [])() if svc else []
    by_status = {}
    for j in jobs:
        status = j.get('status') if isinstance(j, dict) else getattr(j, 'status', None)
        if hasattr(status, 'value'):
            status = status.value  # type: ignore
        if status is None:
            status = 'unknown'
        by_status[status] = by_status.get(status, 0) + 1
    return jsonify({'success': True, 'counts': {'total': len(jobs), 'by_status': by_status}})
