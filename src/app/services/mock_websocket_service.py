"""
Lightweight no-op mock WebSocket service.

Kept to satisfy factory fallback imports when Celery-backed WebSocket is unavailable.
All methods are safe no-ops suitable for tests/development without SocketIO.
"""

from typing import Any, Dict, List, Optional


class MockWebSocketService:
    def __init__(self) -> None:
        self._events: List[Dict[str, Any]] = []

    def emit(self, event: str, data: Dict[str, Any], room: Optional[str] = None) -> None:
        self._events.append({'event': event, 'data': data, 'room': room})

    def broadcast_message(self, event: str, data: Dict[str, Any]) -> None:
        self.emit(event, data)

    def send_to_analysis_room(self, analysis_id: str, event: str, data: Dict[str, Any]) -> None:
        self.emit(event, data, room=f"analysis_{analysis_id}")

    def get_status(self) -> Dict[str, Any]:
        return {'service': 'mock_websocket', 'events': len(self._events)}

    def get_active_analyses(self) -> List[Dict[str, Any]]:
        return []

    def get_event_log(self) -> List[Dict[str, Any]]:
        return list(self._events)

    def clear_event_log(self) -> None:
        self._events.clear()


_mock_service: Optional[MockWebSocketService] = None


def initialize_mock_websocket_service() -> MockWebSocketService:
    global _mock_service
    _mock_service = MockWebSocketService()
    return _mock_service


def get_mock_websocket_service() -> Optional[MockWebSocketService]:
    return _mock_service


def broadcast_analysis_update(analysis_id: str, event: str, data: Dict[str, Any]) -> None:
    if _mock_service:
        _mock_service.send_to_analysis_room(analysis_id, event, data)
        _mock_service.broadcast_message(event, {**data, 'analysis_id': analysis_id})


def broadcast_system_update(event: str, data: Dict[str, Any]) -> None:
    if _mock_service:
        _mock_service.broadcast_message(event, data)
