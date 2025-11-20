"""
Celery WebSocket Service
========================

Real implementation of WebSocket service using Celery and Redis for
distributed task execution and message broadcasting.
"""

from __future__ import annotations

import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus

logger = logging.getLogger(__name__)

class CeleryWebSocketService:
    """
    WebSocket service that integrates with Celery for task management
    and SocketIO for real-time updates.
    """

    def __init__(self, socketio=None):
        self.socketio = socketio
        self._redis_client = None
        logger.info(f"CeleryWebSocketService initialized (SocketIO available: {bool(socketio)})")

    @property
    def redis(self):
        """Lazy load Redis client."""
        if self._redis_client is None:
            try:
                import redis
                import os
                redis_url = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
                self._redis_client = redis.from_url(redis_url)
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                return None
        return self._redis_client

    def get_status(self) -> Dict[str, Any]:
        """Get service status."""
        redis_connected = False
        try:
            if self.redis:
                redis_connected = self.redis.ping()
        except Exception:
            pass

        return {
            'service': 'celery_websocket',
            'socketio_available': bool(self.socketio),
            'redis_connected': redis_connected,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def get_active_analyses(self) -> List[Dict[str, Any]]:
        """Get currently running analyses from DB."""
        tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
        return [
            {
                'id': t.task_id,
                'status': t.status.value,
                'model': t.target_model,
                'app': t.target_app_number,
                'started_at': t.started_at.isoformat() if t.started_at else None
            }
            for t in tasks
        ]

    def get_event_log(self) -> List[Dict[str, Any]]:
        """
        Get recent events.
        In a real distributed system, this might query a persistent event log.
        For now, we return an empty list or implement a limited in-memory buffer if needed.
        """
        return []

    def clear_event_log(self) -> None:
        """Clear event log."""
        pass

    def start_analysis(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Start an analysis task.
        This is now handled by TaskExecutionService dispatching to Celery,
        but we keep this for compatibility if direct invocation is needed.
        """
        # This method is largely legacy/direct-invoke.
        # The preferred path is creating an AnalysisTask and letting the executor pick it up.
        logger.warning("Direct start_analysis called on CeleryWebSocketService - prefer creating AnalysisTask")
        return None

    def get_analysis_status(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific analysis."""
        task = AnalysisTask.query.filter_by(task_id=analysis_id).first()
        if not task:
            return None
        
        return {
            'id': task.task_id,
            'status': task.status.value,
            'progress': task.progress_percentage,
            'result': task.result_summary
        }

    def cancel_analysis(self, analysis_id: str) -> bool:
        """Cancel a running analysis."""
        task = AnalysisTask.query.filter_by(task_id=analysis_id).first()
        if task and task.status in [AnalysisStatus.PENDING, AnalysisStatus.RUNNING]:
            task.status = AnalysisStatus.CANCELLED
            task.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            
            # Revoke Celery task if we had the ID stored
            # This would require storing the celery_task_id in the AnalysisTask model
            # if task.celery_task_id:
            #     from app.celery_worker import celery
            #     celery.control.revoke(task.celery_task_id, terminate=True)
            
            self.emit('analysis_cancelled', {'analysis_id': analysis_id})
            return True
        return False

    def emit(self, event: str, data: Any, room: Optional[str] = None) -> None:
        """Emit a WebSocket event."""
        if self.socketio:
            try:
                if room:
                    self.socketio.emit(event, data, room=room)
                else:
                    self.socketio.emit(event, data)
            except Exception as e:
                logger.error(f"SocketIO emit failed: {e}")
        else:
            logger.debug(f"SocketIO not available, skipping emit: {event}")


def initialize_celery_websocket_service(socketio=None) -> CeleryWebSocketService:
    """Initialize and return the service."""
    return CeleryWebSocketService(socketio)
