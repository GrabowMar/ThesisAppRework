"""Sample Generator Jinja Routes
====================================

Web interface routes for the AI-powered sample code generation system.
Provides a comprehensive UI for template management, model selection,
generation tracking, and result analysis.

This interface mirrors the functionality of the legacy generateOutputs.py
GUI application while leveraging the modern REST API backend.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import Blueprint, current_app, jsonify, render_template, flash, redirect, url_for, request
from flask_login import current_user

from app.services.generation import get_generation_service

sample_generator_bp = Blueprint('sample_generator', __name__, url_prefix='/sample-generator')

# Require authentication
@sample_generator_bp.before_request
def require_authentication():
    """Require authentication for all sample generator endpoints."""
    if not current_user.is_authenticated:
        flash('Please log in to access the sample generator.', 'info')
        return redirect(url_for('auth.login', next=request.url))


def _service():
    return get_generation_service()


def _build_status() -> Dict[str, Any]:
    try:
        svc = _service()
        status = svc.get_generation_status()
        summary = svc.get_summary_metrics()
        status.update(summary)
        status.setdefault('stubbed', False)
        return status
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to build sample generator status", exc_info=exc)
        return {
            'in_flight_count': 0,
            'available_slots': 0,
            'max_concurrent': 0,
            'in_flight_keys': [],
            'total_results': 0,
            'total_templates': 0,
            'total_models': 0,
            'active_tasks': 0,
            'system_healthy': False,
            'stubbed': True,
        }


def _load_recent(limit: int = 10) -> List[Dict[str, Any]]:
    """Load recent generation results from GeneratedApplication table."""
    try:
        from app.models import GeneratedApplication
        from app.constants import AnalysisStatus

        results = (
            GeneratedApplication.query
            .order_by(GeneratedApplication.created_at.desc())
            .limit(limit)
            .all()
        )

        def _get_status_info(result):
            """Determine status and message for a generation result."""
            status = result.generation_status
            metadata = result.get_metadata() or {}
            
            # Determine success/failed/pending based on status enum
            if status == AnalysisStatus.COMPLETED:
                return 'completed', None
            elif status == AnalysisStatus.FAILED:
                # Extract error message from metadata
                errors = metadata.get('errors', [])
                error_msg = errors[0] if errors else 'Generation failed'
                return 'failed', error_msg
            elif status == AnalysisStatus.RUNNING:
                return 'running', 'Generation in progress...'
            else:  # PENDING, CANCELLED, or unknown
                return 'pending', None

        return [
            {
                'timestamp': result.created_at,
                'app_name': f"{result.template_slug or 'App'} #{result.app_number}",
                'app_num': result.app_number,
                'model': result.model_slug,
                'status': _get_status_info(result)[0],
                'success': result.generation_status == AnalysisStatus.COMPLETED,
                'error_message': _get_status_info(result)[1],
                'duration': None,  # Not tracked in GeneratedApplication
                'result_id': f"{result.model_slug}_app{result.app_number}",
                'template_slug': result.template_slug,
                'provider': result.provider,
            }
            for result in results
        ]
    except Exception as exc:  # noqa: BLE001
        current_app.logger.exception("Failed to load recent sample generations", exc_info=exc)
        return []


@sample_generator_bp.route('/')
def index():
    """Main sample generator interface with live status context."""
    status = _build_status()
    recent = _load_recent(limit=8)
    return render_template(
        'pages/sample_generator/sample_generator_main.html',
        status=status,
        recent=recent,
    )


# ---------------------------------------------------------------------------
# HTMX partial endpoints (lightweight HTML fragments)
# ---------------------------------------------------------------------------


@sample_generator_bp.route('/fragments/status')
def fragment_status():
    """Return status metrics fragment for htmx polling."""
    return render_template('pages/sample_generator/partials/_status_metrics.html', status=_build_status())


@sample_generator_bp.route('/fragments/recent')
def fragment_recent():
    """Return recent results table rows fragment."""
    return render_template('pages/sample_generator/partials/_recent_rows.html', recent=_load_recent())


@sample_generator_bp.route('/api/proxy/<path:endpoint>')
def api_proxy(endpoint):
    """Proxy limited API calls for frontend convenience (optional fallback)."""
    if endpoint == 'status':
        return jsonify({'success': True, 'data': _build_status()})
    if endpoint == 'recent':
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(limit, 1), 100)  # Clamp between 1 and 100
        return jsonify({'success': True, 'data': _load_recent(limit=limit)})
    return jsonify({"error": "Endpoint not supported"}), 404