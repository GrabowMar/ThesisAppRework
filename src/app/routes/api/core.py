"""
Core API Routes
===============

Basic API endpoints and utilities.
"""

import logging

from ..response_utils import json_success, handle_exceptions

from . import api_bp

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/')
@handle_exceptions(logger_override=logger)
def api_overview():
    """API overview endpoint.

    Returns a standardized envelope so frontend consumers have consistent shape.
    """
    return json_success({
        'version': '1.0',
        'endpoints': {
            'models': '/api/models',
            'applications': '/api/applications',
            'statistics': '/api/statistics',
            'system': '/api/system',
            'analysis': '/api/analysis'
        }
    }, message='Thesis Research App API')


@api_bp.route('/health')
@handle_exceptions(logger_override=logger)
def api_health():
    """API health check endpoint."""
    return json_success({
        'status': 'healthy',
        'timestamp': None,
        'version': '1.0'
    })
