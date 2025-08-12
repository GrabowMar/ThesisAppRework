"""
Core API Routes
===============

Basic API endpoints and utilities.
"""

import logging
from flask import jsonify

from . import api_bp

# Set up logger
logger = logging.getLogger(__name__)


@api_bp.route('/')
def api_overview():
    """API overview endpoint."""
    return jsonify({
        'message': 'Thesis Research App API',
        'version': '1.0',
        'endpoints': {
            'models': '/api/models',
            'applications': '/api/applications',
            'statistics': '/api/statistics',
            'system': '/api/system',
            'analysis': '/api/analysis'
        }
    })


@api_bp.route('/health')
def api_health():
    """API health check endpoint."""
    try:
        return jsonify({
            'status': 'healthy',
            'timestamp': None,
            'version': '1.0'
        })
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500
