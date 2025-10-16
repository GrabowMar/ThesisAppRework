"""Event emission helpers for the analysis orchestrator.

Provides a thin abstraction that fans out orchestrator lifecycle events to
both the realtime Socket.IO bridge (via ``emit_task_event``) and the
persistent ``EventLog`` table when available. All emission paths are
best-effort—the orchestrator never fails because telemetry sinks are
unavailable.
"""

from __future__ import annotations

import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.logging_config import get_logger

try:  # pragma: no cover - optional dependency in some tests
    from app.realtime.task_events import emit_task_event  # type: ignore
except Exception:  # pragma: no cover
    def emit_task_event(event_type: str, data: Dict[str, Any]) -> None:  # type: ignore
        return None

try:  # pragma: no cover - import guards for early boot scenarios
    from app.extensions import db
except Exception:  # pragma: no cover
    db = None  # type: ignore


@dataclass
class OrchestrationEventPublisher:
    """Best-effort event publisher for analysis orchestration."""

    model_slug: str
    app_number: int
    task_id: Optional[str] = None

    def __post_init__(self) -> None:
        self._logger = get_logger("orchestrator.events")

    # ------------------------------------------------------------------
    # Public emission helpers
    # ------------------------------------------------------------------
    def emit_state(self, state: str, payload: Optional[Dict[str, Any]] = None) -> None:
        data = {"state": state}
        if payload:
            data.update(payload)
        self._emit("analysis.state", data)

    def emit_progress(self, stage: str, percentage: float, payload: Optional[Dict[str, Any]] = None) -> None:
        data = {"stage": stage, "percentage": round(percentage, 2)}
        if payload:
            data.update(payload)
        self._emit("analysis.progress", data)

    def emit_service_event(self, service: str, stage: str, payload: Optional[Dict[str, Any]] = None, *, severity: str = "info") -> None:
        data = {"service": service, "stage": stage}
        if payload:
            data.update(payload)
        self._emit("analysis.service", data, severity=severity)

    def emit_retry(self, service: str, attempt: int, max_attempts: int, error: str) -> None:
        self._emit(
            "analysis.retry",
            {
                "service": service,
                "attempt": attempt,
                "max_attempts": max_attempts,
                "error": error,
            },
            severity="warning",
        )

    def emit_heartbeat(self, stage: str, payload: Optional[Dict[str, Any]] = None) -> None:
        data = {"stage": stage}
        if payload:
            data.update(payload)
        self._emit("analysis.heartbeat", data)

    def emit_failure(self, message: str, error: str) -> None:
        self._emit("analysis.error", {"message": message, "error": error}, severity="error")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _emit(self, event_type: str, payload: Dict[str, Any], *, severity: str = "info") -> None:
        enriched = self._enrich_payload(payload, severity)
        with suppress(Exception):
            emit_task_event(event_type, enriched)
        self._persist_event(event_type, enriched, severity)

    def _enrich_payload(self, payload: Dict[str, Any], severity: str) -> Dict[str, Any]:
        base: Dict[str, Any] = {
            "model_slug": self.model_slug,
            "app_number": self.app_number,
            "task_id": self.task_id,
            "severity": severity,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        base.update(self._normalize(payload))
        return base

    def _persist_event(self, event_type: str, payload: Dict[str, Any], severity: str) -> None:
        # EventLog model not currently available - persistence disabled
        return
        # if not EventLog or not db:  # pragma: no cover - guard for tests
        #     return
        # session = None
        # try:
        #     session = db.create_scoped_session()
        #     log = EventLog(
        #         event_id=f"orchestrator-{uuid.uuid4().hex}",
        #         event_type="analysis",
        #         event_name=event_type,
        #         source="orchestrator",
        #         user_id=None,
        #         session_id=None,
        #         severity=severity,
        #         category="analysis",
        #         message=payload.get("message") or payload.get("state") or payload.get("stage"),
        #     )
        #     log.set_event_data(payload)
        #     log.timestamp = datetime.now(timezone.utc)
        #     session.add(log)
        #     session.commit()
        # except Exception as exc:  # pragma: no cover - telemetry errors ignored
        #     if session is not None:
        #         with suppress(Exception):
        #             session.rollback()
        #     self._logger.debug("Failed to persist orchestration event %s: %s", event_type, exc)
        # finally:
        #     if session is not None:
        #         with suppress(Exception):
        #             session.remove()

    def _normalize(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._normalize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [self._normalize(v) for v in value]
        if isinstance(value, Path):
            return str(value)
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return value

__all__ = ["OrchestrationEventPublisher"]
