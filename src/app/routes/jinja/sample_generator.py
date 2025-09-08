"""Sample Generator Jinja Routes
====================================

Web interface routes for the AI-powered sample code generation system.
Provides a comprehensive UI for template management, model selection,
generation tracking, and result analysis.

This interface mirrors the functionality of the legacy generateOutputs.py
GUI application while leveraging the modern REST API backend.
"""

from flask import Blueprint, render_template, jsonify, request
from app.services.sample_generation_service import get_sample_generation_service

sample_generator_bp = Blueprint('sample_generator', __name__, url_prefix='/sample-generator')

@sample_generator_bp.route('/')
def index():
    """Main sample generator interface.

    Provide initial status context so first paint does not 500 if fragment include
    renders before HTMX polling.
    """
    service = get_sample_generation_service()
    try:
        status = service.get_generation_status()
    except Exception:  # pragma: no cover - defensive
        status = {
            'in_flight_count': 0,
            'available_slots': 0,
            'max_concurrent': 0,
            'in_flight_keys': []
        }
    return render_template('pages/sample_generator/sample_generator_main.html', status=status)


# ---------------------------------------------------------------------------
# HTMX partial endpoints (lightweight HTML fragments)
# ---------------------------------------------------------------------------

@sample_generator_bp.route('/fragments/status')
def fragment_status():
    """Return status metrics fragment for htmx polling."""
    service = get_sample_generation_service()
    status = service.get_generation_status()
    return render_template('pages/sample_generator/partials/_status_metrics.html', status=status)


@sample_generator_bp.route('/fragments/recent')
def fragment_recent():
    """Return recent results table rows fragment."""
    service = get_sample_generation_service()
    # limit parameter (default 10)
    try:
        limit = int(request.args.get('limit', 10))
    except ValueError:
        limit = 10
    results = service.list_results(limit=limit)  # returns list of tuples (id, GenerationResult)
    table = []
    for rid, result in results:
        table.append({
            'id': rid,
            'template': getattr(result, 'app_name', None) or getattr(result, 'app_num', ''),
            'model': getattr(result, 'model', ''),
            'success': getattr(result, 'success', False),
            'duration': getattr(result, 'duration', None),
            'timestamp': getattr(result, 'timestamp', None),
        })
    return render_template('pages/sample_generator/partials/_recent_rows.html', recent=table)

@sample_generator_bp.route('/api/proxy/<path:endpoint>')
def api_proxy(endpoint):
    """Proxy API calls for frontend convenience (optional fallback)."""
    # This allows the frontend to make requests to /sample-generator/api/proxy/*
    # which gets forwarded to /api/sample-gen/*
    # Useful if we need to avoid CORS issues
    service = get_sample_generation_service()
    
    if endpoint == 'status':
        return jsonify(service.get_generation_status())
    elif endpoint == 'templates':
        return jsonify(service.list_templates())
    # Add other proxy endpoints as needed
    
    return jsonify({"error": "Endpoint not supported"}), 404