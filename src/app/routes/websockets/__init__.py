"""
WebSocket Routes Package
Handles WebSocket-related routes and functionality.
"""

from .api import websocket_api_bp
from .fallbacks import register_websocket_routes, register_error_handlers

__all__ = [
    'websocket_api_bp',
    'register_websocket_routes',
    'register_error_handlers'
]