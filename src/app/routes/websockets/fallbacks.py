"""
WebSocket Fallback Routes
Handles WebSocket fallback routes and error handlers.
"""

from flask import request, jsonify, render_template
from werkzeug.routing.exceptions import WebsocketMismatch
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


def register_websocket_routes(app):
    """Register basic WebSocket routes."""

    @app.route('/ws/analysis')
    def websocket_analysis():
        """Basic WebSocket endpoint for analysis dashboard."""
        try:
            return jsonify({
                'error': 'websocket_upgrade_required',
                'message': 'Native WebSocket upgrade not supported by this server route',
                'hint': 'Use Socket.IO client if enabled, or REST API at /api/websocket/* for polling',
            }), 426
        except Exception as e:
            logger.error(f"WebSocket analysis endpoint error: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route('/socket.io/')
    def socket_io_fallback():
        """Fallback for Socket.IO requests when not available."""
        return jsonify({
            'status': 'Socket.IO not available',
            'message': 'Using mock WebSocket service',
            'alternative': 'Use REST API at /api/websocket/ for WebSocket functionality'
        }), 404


def register_error_handlers(app):
    """Register error handlers with the Flask app."""

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            'pages/errors/errors.html',
            error_code=404,
            error_title='Page Not Found',
            error_message="The page you're looking for doesn't exist or has been moved."
        ), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template(
            'pages/errors/errors.html',
            error_code=500,
            error_title='Internal Server Error',
            error_message="Something went wrong on our end. Please try again later."
        ), 500

    @app.errorhandler(503)
    def service_unavailable_error(error):
        return render_template(
            'pages/errors/errors.html',
            error_code=503,
            error_title='Service Unavailable',
            error_message="The service is temporarily unavailable. Please try again later."
        ), 503

    @app.errorhandler(WebsocketMismatch)
    def websocket_mismatch_error(error):
        status = 400
        message = 'WebSocket endpoint not available. Use Socket.IO client or REST fallback.'
        if request.path.startswith('/api'):
            return jsonify({
                'error': 'websocket_mismatch',
                'message': message,
                'hint': 'Use /api/websocket/* endpoints for polling when real-time is disabled'
            }), status
        return render_template(
            'pages/errors/errors.html',
            error_code=status,
            error_title='WebSocket Not Available',
            error_message=message
        ), status