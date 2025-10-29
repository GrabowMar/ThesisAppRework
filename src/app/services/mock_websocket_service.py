"""
Mock WebSocket Service
===================

Simple mock implementation of WebSocket service for development/testing
when Celery-backed service is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MockWebSocketService:
    """Mock WebSocket service that logs events without real WebSocket connections."""

    def __init__(self):
        self.event_log: List[Dict[str, Any]] = []
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
        logger.info("MockWebSocketService initialized")

    def get_status(self) -> Dict[str, Any]:
        return {
            'active_analyses': len(self.active_analyses),
            'connected': False,  # mock service
            'last_update': datetime.now(timezone.utc).isoformat(),
            'service': 'mock_websocket',
        }

    def get_active_analyses(self) -> List[Dict[str, Any]]:
        return list(self.active_analyses.values())

    def get_event_log(self) -> List[Dict[str, Any]]:
        return list(self.event_log)

    def clear_event_log(self) -> None:
        self.event_log.clear()

    def start_analysis(self, data: Dict[str, Any]) -> Optional[str]:
        """Mock analysis start - just logs the request."""
        analysis_id = f"mock_{datetime.now(timezone.utc).timestamp()}"
        self.active_analyses[analysis_id] = {
            'id': analysis_id,
            'status': 'pending',
            'data': data,
            'started_at': datetime.now(timezone.utc).isoformat()
        }
        self._log_event('analysis_started', {'analysis_id': analysis_id, 'data': data})
        logger.info(f"Mock analysis started: {analysis_id}")
        return analysis_id

    def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        return self.active_analyses.get(analysis_id)

    def cancel_analysis(self, analysis_id: str) -> bool:
        if analysis_id in self.active_analyses:
            self.active_analyses[analysis_id]['status'] = 'cancelled'
            self._log_event('analysis_cancelled', {'analysis_id': analysis_id})
            return True
        return False

    def emit(self, event: str, data: Any, room: Optional[str] = None) -> None:
        """Mock emit - just logs."""
        self._log_event(event, data)

    def _log_event(self, event_type: str, data: Any) -> None:
        event = {
            'type': event_type,
            'data': data,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        self.event_log.append(event)
        logger.debug(f"Mock WebSocket event: {event_type}")


def initialize_mock_websocket_service() -> MockWebSocketService:
    """Initialize and return mock WebSocket service."""
    return MockWebSocketService()
