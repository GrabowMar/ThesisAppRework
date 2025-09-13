"""
Celery-backed WebSocket Testing Service
======================================

Real-time-like service that bridges HTTP/WebSocket API with Celery tasks.
- Starts analyzer Celery tasks for security/performance/static/ai
- Tracks task state and emits progress/completion events via SocketIO when available
- Provides simple in-process event log for debugging

Note: This module does not require the analyzer "gateway". It relies only on
Celery and the existing tasks defined in app.tasks.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from threading import Lock, Thread
from typing import Any, Dict, List, Optional, cast

from celery.result import AsyncResult

# Import Celery tasks module instance for consistent broker/backend
from app.tasks import (
    celery as tasks_celery,
    security_analysis_task,
    performance_test_task,
    static_analysis_task,
    dynamic_analysis_task,
    ai_analysis_task,
)

logger = logging.getLogger(__name__)


class CeleryWebSocketService:
    """Bridge service: start Celery jobs and surface their status over SocketIO."""

    def __init__(self, socketio: Optional[Any] = None):
        self.socketio = socketio
        self.celery = tasks_celery
        self.active_analyses: Dict[str, Dict[str, Any]] = {}
        self.event_log: List[Dict[str, Any]] = []
        self._lock = Lock()
        self._monitor_thread: Optional[Thread] = None
        self._monitor_running = False

        # Start background monitor
        self._start_monitoring()
        logger.info("CeleryWebSocketService initialized")

    # ---------------------------- public API ----------------------------
    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'active_analyses': len(self.active_analyses),
                'connected': True,  # service available
                'last_update': datetime.now(timezone.utc).isoformat(),
                'service': 'celery_websocket',
            }

    def get_active_analyses(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.active_analyses.values())

    def get_event_log(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.event_log)

    def clear_event_log(self) -> None:
        """Clear the in-memory event log (useful for smoke/E2E runs)."""
        with self._lock:
            self.event_log.clear()

    def start_analysis(self, data: Dict[str, Any]) -> Optional[str]:
        """Start a Celery task based on analysis_type and return the task id."""
        try:
            analysis_type = data.get('analysis_type') or data.get('type')
            model_slug = data.get('model_slug')
            app_number = data.get('app_number')
            config = data.get('config') or data.get('options') or {}
            tools = data.get('tools')

            if not all([analysis_type, model_slug, app_number is not None]):
                raise ValueError('Missing required fields: analysis_type, model_slug, app_number')

            if app_number is None:
                raise ValueError('app_number is required')
            app_num = int(app_number)

            task_id: Optional[str] = None

            if analysis_type == 'security':
                # security_analysis_task(self, model_slug, app_number, tools=None, options=None)
                async_task: Any = cast(Any, security_analysis_task)
                async_res = async_task.delay(model_slug, app_num, tools=tools, options=config)
                task_id = async_res.id
            elif analysis_type == 'performance':
                # performance_test_task(self, model_slug, app_number, test_config=None)
                async_task = cast(Any, performance_test_task)
                async_res = async_task.delay(model_slug, app_num, test_config=config)
                task_id = async_res.id
            elif analysis_type == 'static':
                async_task = cast(Any, static_analysis_task)
                async_res = async_task.delay(model_slug, app_num, tools=tools, options=config)
                task_id = async_res.id
            elif analysis_type == 'dynamic':
                # dynamic_analysis_task(self, model_slug, app_number, options=None)
                # Pass tools inside options to keep signature stable
                if tools:
                    if not isinstance(config, dict):
                        config = {}
                    config['selected_tools'] = tools
                async_task = cast(Any, dynamic_analysis_task)
                async_res = async_task.delay(model_slug, app_num, options=config)
                task_id = async_res.id
            elif analysis_type == 'ai':
                async_task = cast(Any, ai_analysis_task)
                async_res = async_task.delay(model_slug, app_num, analysis_types=data.get('analysis_types'), options=config)
                task_id = async_res.id
            else:
                raise ValueError(f'Unknown analysis_type: {analysis_type}')

            if not task_id:
                raise RuntimeError('No task id returned from Celery')

            with self._lock:
                self.active_analyses[task_id] = {
                    'id': task_id,
                    'type': analysis_type,
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'status': 'queued',
                    'progress': 0,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                }

            self._emit('analysis_started', {'analysis_id': task_id, 'status': 'started'})
            logger.info(f"Started Celery analysis task {task_id} ({analysis_type}) for {model_slug} app {app_number}")
            return task_id

        except Exception as e:
            logger.error(f"Failed to start analysis: {e}")
            self._emit('analysis_error', {'error': str(e), 'timestamp': datetime.now(timezone.utc).isoformat()})
            return None

    def cancel_analysis(self, analysis_id: str) -> bool:
        try:
            # Best-effort revoke
            self.celery.control.revoke(analysis_id, terminate=True)

            with self._lock:
                if analysis_id in self.active_analyses:
                    self.active_analyses[analysis_id]['status'] = 'cancelled'

            self._emit('analysis_cancelled', {'analysis_id': analysis_id, 'success': True})
            logger.info(f"Cancelled Celery analysis task {analysis_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel analysis {analysis_id}: {e}")
            return False

    def broadcast_message(self, event: str, data: Dict[str, Any]):
        self._emit(event, data)

    def send_to_analysis_room(self, analysis_id: str, event: str, data: Dict[str, Any]):
        self._emit(event, data, room=f"analysis_{analysis_id}")

    # ---------------------------- internals ----------------------------
    def _emit(self, event: str, data: Dict[str, Any], room: Optional[str] = None):
        entry = {
            'event': event,
            'data': data,
            'room': room,
            'timestamp': datetime.now(timezone.utc).isoformat(),
        }
        with self._lock:
            self.event_log.append(entry)
            if len(self.event_log) > 100:
                self.event_log = self.event_log[-100:]

        if self.socketio:
            try:
                self.socketio.emit(event, data if room is None else data, room=room)
            except Exception as e:
                logger.debug(f"SocketIO emit failed ({event}): {e}")

    def _start_monitoring(self):
        if self._monitor_thread and self._monitor_thread.is_alive():
            return

        self._monitor_running = True

        def _monitor_loop():
            # Poll Celery for task status and emit updates
            while self._monitor_running:
                try:
                    with self._lock:
                        task_ids = list(self.active_analyses.keys())
                    for task_id in task_ids:
                        res = AsyncResult(task_id, app=self.celery)
                        state = res.state  # PENDING, STARTED, RETRY, SUCCESS, FAILURE
                        info = res.info if isinstance(res.info, dict) else {}

                        # Map to progress number if available
                        progress = int(info.get('progress', 0)) if 'progress' in info else None
                        stage = info.get('stage') if isinstance(info, dict) else None

                        # Update cached status
                        with self._lock:
                            if task_id in self.active_analyses:
                                self.active_analyses[task_id]['status'] = state.lower()
                                if progress is not None:
                                    self.active_analyses[task_id]['progress'] = progress

                        # Emit progress for STARTED/PROGRESS
                        if state in ('STARTED', 'RETRY') or (progress is not None and state not in ('SUCCESS', 'FAILURE')):
                            payload = {
                                'analysis_id': task_id,
                                'status': state.lower(),
                                'progress': progress if progress is not None else 0,
                                'stage': stage,
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            }
                            self._emit('analysis_progress', payload, room=f"analysis_{task_id}")

                        # Completion handling
                        if state == 'SUCCESS':
                            try:
                                result = res.get(timeout=0)  # non-blocking for SUCCESS
                            except Exception as ge:  # pragma: no cover
                                result = {'status': 'completed', 'result_fetch_error': str(ge)}

                            self._emit('analysis_completed', {
                                'analysis_id': task_id,
                                'result': result,
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            })
                            with self._lock:
                                self.active_analyses.pop(task_id, None)

                        elif state == 'FAILURE':
                            err_msg = str(res.info) if res.info else 'Task failed'
                            self._emit('analysis_error', {
                                'analysis_id': task_id,
                                'error': err_msg,
                                'timestamp': datetime.now(timezone.utc).isoformat(),
                            })
                            with self._lock:
                                self.active_analyses.pop(task_id, None)

                except Exception as e:
                    logger.debug(f"Monitor loop error: {e}")
                finally:
                    time.sleep(2)

        self._monitor_thread = Thread(target=_monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("CeleryWebSocketService monitor thread started")


# Global instance helpers
_service: Optional[CeleryWebSocketService] = None


def initialize_celery_websocket_service(socketio: Optional[Any] = None) -> CeleryWebSocketService:
    global _service
    _service = CeleryWebSocketService(socketio)
    return _service


def get_celery_websocket_service() -> Optional[CeleryWebSocketService]:
    return _service
