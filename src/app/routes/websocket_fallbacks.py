"""
Basic WebSocket endpoint for /ws/analysis
"""

from flask import jsonify
import logging

logger = logging.getLogger(__name__)

def register_websocket_routes(app):
    """Register basic WebSocket routes."""
    
    @app.route('/ws/analysis')
    def websocket_analysis():
        """Basic WebSocket endpoint for analysis dashboard."""
        try:
            # This is a placeholder for WebSocket connection
            # In production, this would handle WebSocket upgrades
            # Explicitly indicate upgrade required / not supported in this environment
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
