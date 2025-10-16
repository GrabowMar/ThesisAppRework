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

from flask import Blueprint, current_app, jsonify, render_template

from app.services.simple_generation_service import get_simple_generation_service

sample_generator_bp = Blueprint('sample_generator', __name__, url_prefix='/sample-generator')


def _service():
    return get_simple_generation_service()


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
    """Load recent results - stubbed for now as SimpleGenerationService has different interface."""
    try:
        # SimpleGenerationService doesn't have list_results method
        # Return empty list for now - UI will need updating
        return []
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
        return jsonify({'success': True, 'data': _load_recent(limit=10)})
    return jsonify({"error": "Endpoint not supported"}), 404