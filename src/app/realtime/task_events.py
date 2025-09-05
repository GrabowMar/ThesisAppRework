"""Task & Batch Realtime Event Emitter
======================================

Lightweight abstraction for emitting task/batch lifecycle events over
Socket.IO when available, with an in-memory ring buffer fallback for
REST polling and unit tests.

Design goals:
- Zero hard dependency on SocketIO (tests still pass without it)
- Thread-safe append & bounded history
- Simple event envelope with versioning
- Filtering left for future namespace implementation

Event Envelope::
    {
      "event": "task.created",  # see EVENT_TYPES
      "version": 1,
      "timestamp": "ISO-8601",
      "data": { ... domain payload ... }
    }

Public API:
- emit_task_event(event_type: str, data: dict) -> None
- get_recent_events(kind_prefix: Optional[str]=None) -> list[dict]
- clear_events() -> None

NOTE: Namespace /tasks will be added separately; for now we emit on the
default namespace (broadcast) to keep wiring minimal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional

from app.utils.logging_config import get_logger

try:  # SocketIO may be unavailable in some test environments
    from app.extensions import SOCKETIO_AVAILABLE, socketio  # type: ignore
except Exception:  # pragma: no cover - defensive import
    SOCKETIO_AVAILABLE, socketio = False, None  # type: ignore

logger = get_logger("task_events")

EVENT_VERSION = 1
MAX_EVENTS = 200


@dataclass
class TaskEvent:
    event: str
    data: Dict[str, Any]
    timestamp: str
    version: int = EVENT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event": self.event,
            "version": self.version,
            "timestamp": self.timestamp,
            "data": self.data,
        }


class _TaskEventBuffer:
    def __init__(self, max_events: int = MAX_EVENTS):
        self._events: List[TaskEvent] = []
        self._lock = Lock()
        self._max = max_events

    def add(self, evt: TaskEvent) -> None:
        with self._lock:
            self._events.append(evt)
            if len(self._events) > self._max:
                self._events = self._events[-self._max :]

    def list(self, kind_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._lock:
            if kind_prefix:
                return [e.to_dict() for e in self._events if e.event.startswith(kind_prefix)]
            return [e.to_dict() for e in self._events]

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


_buffer = _TaskEventBuffer()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_task_event(event_type: str, data: Dict[str, Any]) -> None:
    """Emit a task/batch related event.

    Falls back to in-memory buffer only if SocketIO unavailable.
    """
    evt = TaskEvent(event=event_type, data=data, timestamp=_now_iso())
    _buffer.add(evt)

    if SOCKETIO_AVAILABLE and socketio is not None:
        try:
            # Broadcast globally for now. Namespace-specific emission will be added later.
            socketio.emit(event_type, evt.to_dict())  # type: ignore[attr-defined]
        except Exception as e:  # pragma: no cover - logging only
            logger.debug("SocketIO emit failed (%s): %s", event_type, e)


def get_recent_events(kind_prefix: Optional[str] = None) -> List[Dict[str, Any]]:
    return _buffer.list(kind_prefix=kind_prefix)


def clear_events() -> None:
    _buffer.clear()


__all__ = [
    "emit_task_event",
    "get_recent_events",
    "clear_events",
]
