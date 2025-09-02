"""Sample Generator Jinja Routes
====================================

Web interface routes for the AI-powered sample code generation system.
Provides a comprehensive UI for template management, model selection,
generation tracking, and result analysis.

This interface mirrors the functionality of the legacy generateOutputs.py
GUI application while leveraging the modern REST API backend.
"""

from flask import Blueprint, render_template, jsonify
from app.services.sample_generation_service import get_sample_generation_service

sample_generator_bp = Blueprint('sample_generator', __name__, url_prefix='/sample-generator')

@sample_generator_bp.route('/')
def index():
    """Main sample generator interface."""
    return render_template('pages/sample_generator/sample_generator_main.html')

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