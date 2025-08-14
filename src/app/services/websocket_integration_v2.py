"""
DEPRECATED: WebSocket Integration v2 (shim)
------------------------------------------
This module now delegates to the Celery-backed WebSocket service.
It remains for backward-compatibility but should be removed once callers
are fully migrated.
"""

from typing import Any, Optional, Dict

from .celery_websocket_service import (
    initialize_celery_websocket_service as _init_celery_ws,
    get_celery_websocket_service as _get_celery_ws,
    CeleryWebSocketService,
)

# Backwards-compatible aliases
WebSocketIntegrationService = CeleryWebSocketService

_websocket_service: Optional[CeleryWebSocketService] = None


def initialize_websocket_service(socketio: Any) -> CeleryWebSocketService:
    global _websocket_service
    _websocket_service = _init_celery_ws(socketio)
    return _websocket_service


def get_websocket_service() -> Optional[CeleryWebSocketService]:
    return _get_celery_ws()


def broadcast_analysis_update(analysis_id: str, event: str, data: Dict[str, Any]):
    svc = _get_celery_ws()
    if svc:
        svc.send_to_analysis_room(analysis_id, event, data)
        svc.broadcast_message(event, {**data, 'analysis_id': analysis_id})


def broadcast_system_update(event: str, data: Dict[str, Any]):
    svc = _get_celery_ws()
    if svc:
        svc.broadcast_message(event, data)
