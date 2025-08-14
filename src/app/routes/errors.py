"""
Error Handlers
=============

Global error handlers for the application.
"""

from flask import render_template, jsonify, request
from werkzeug.routing.exceptions import WebsocketMismatch


def register_error_handlers(app):
    """Register error handlers with the Flask app."""
    
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            'single_page.html',
            page_title='Not Found',
            main_partial='partials/common/error.html',
            error="Page not found"
        ), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template(
            'single_page.html',
            page_title='Server Error',
            main_partial='partials/common/error.html',
            error="Internal server error"
        ), 500
    
    @app.errorhandler(503)
    def service_unavailable_error(error):
        return render_template(
            'single_page.html',
            page_title='Service Unavailable',
            main_partial='partials/common/error.html',
            error="Service temporarily unavailable"
        ), 503

    # Gracefully handle accidental WebSocket requests on Flask routes
    @app.errorhandler(WebsocketMismatch)
    def websocket_mismatch_error(error):
        # If the request targets an API path, return JSON; otherwise render a minimal page
        status = 400
        message = 'WebSocket endpoint not available. Use Socket.IO client or REST fallback.'
        if request.path.startswith('/api'):
            return jsonify({
                'error': 'websocket_mismatch',
                'message': message,
                'hint': 'Use /api/websocket/* endpoints for polling when real-time is disabled'
            }), status
        # Non-API paths – show a friendly page
        return render_template(
            'single_page.html',
            page_title='WebSocket Not Available',
            main_partial='partials/common/error.html',
            error=message
        ), status
