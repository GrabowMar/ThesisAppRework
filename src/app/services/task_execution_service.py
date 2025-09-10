"""Task Execution Service
=========================

Lightweight in-process executor that advances `AnalysisTask` instances
from pending -> running -> completed for demo/testing purposes.

Why this exists:
- Current codebase creates tasks but nothing is responsible for actually
  starting them, so they remain permanently in the pending state.
- For local dev and tests we implement a cooperative thread that
  periodically selects a small batch of pending tasks using
  `queue_service.get_next_tasks()` from `task_service` and advances
  their lifecycle.

Design goals:
- Non-blocking: runs in a daemon thread and can be safely ignored in prod
- Deterministic & fast in tests (interval shortened when TESTING is True)
- Minimal coupling: only depends on SQLAlchemy models & existing services
- Safe: best-effort error handling so failures don't crash the app

Future extension points (left as TODO comments):
- Replace with real analyzer dispatch (workers / Celery)
- Emit websocket events on state changes
- Per-task execution plugins by analysis_type
"""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Optional

from app.utils.logging_config import get_logger
from app.extensions import db, get_components
from app.models import AnalysisTask
from app.constants import AnalysisStatus

logger = get_logger("task_executor")


class TaskExecutionService:
    """Simple cooperative task executor.

    Lifecycle:
    - poll DB for pending tasks using queue_service selection logic
    - mark a few as running, simulate work with small sleep, then mark completed

    In tests we shorten delays to keep suite fast (< 1s per task).
    """

    def __init__(self, poll_interval: float = 5.0, batch_size: int = 3, app=None):
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._app = app  # Keep explicit reference so we can push context inside thread

    def start(self):  # pragma: no cover - thread start trivial
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("TaskExecutionService started (interval=%s batch=%s)", self.poll_interval, self.batch_size)

    def stop(self):  # pragma: no cover - not required in tests currently
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("TaskExecutionService stopped")

    # --- Internal helpers -------------------------------------------------
    def _run_loop(self):  # pragma: no cover - timing heavy, exercised indirectly
        from app.services.task_service import queue_service

        # We deliberately push an app context each loop iteration to ensure a fresh
        # DB session binding (avoids stale sessions across test database teardown/create).
        while self._running:
            with (self._app.app_context() if self._app else _nullcontext()):
                try:
                    components = get_components()
                    if not components:  # Should not happen if context active
                        time.sleep(self.poll_interval)
                        continue

                    next_tasks = queue_service.get_next_tasks(limit=self.batch_size)
                    if not next_tasks:
                        time.sleep(self.poll_interval)
                        continue

                    for task in next_tasks:
                        task_db: AnalysisTask | None = AnalysisTask.query.filter_by(id=task.id).first()
                        if not task_db or task_db.status != AnalysisStatus.PENDING:
                            continue
                        task_db.status = AnalysisStatus.RUNNING
                        # Use naive UTC timestamps for compatibility with existing
                        # columns that may store naive datetimes (avoids aware/naive errors)
                        task_db.started_at = datetime.utcnow()
                        db.session.commit()
                        try:  # Emit start
                            from app.realtime.task_events import emit_task_event
                            emit_task_event(
                                "task.updated",
                                {
                                    "task_id": task_db.task_id,
                                    "id": task_db.id,
                                    "status": task_db.status.value if task_db.status else None,
                                    "progress_percentage": task_db.progress_percentage,
                                    "started_at": task_db.started_at.isoformat() if task_db.started_at else None,
                                },
                            )
                        except Exception:
                            pass
                        logger.info("Task %s started", task_db.task_id)

                        simulated_steps = 3
                        for i in range(1, simulated_steps + 1):
                            task_db.progress_percentage = (i / simulated_steps) * 100.0
                            db.session.commit()
                            try:  # Emit throttled progress (only final step will also mark completed later)
                                from app.realtime.task_events import emit_task_event
                                if i == simulated_steps:  # only emit final progress before completion
                                    emit_task_event(
                                        "task.progress",
                                        {
                                            "task_id": task_db.task_id,
                                            "id": task_db.id,
                                            "progress_percentage": task_db.progress_percentage,
                                            "status": task_db.status.value if task_db.status else None,
                                        },
                                    )
                            except Exception:
                                pass
                            time.sleep(0.05 if self._is_test_mode() else 0.3)

                        # Ensure completion sets progress to 100 (model.complete_execution would do this
                        # but we manipulate fields directly here for speed & isolation)
                        task_db.status = AnalysisStatus.COMPLETED
                        task_db.progress_percentage = 100.0
                        task_db.completed_at = datetime.utcnow()
                        try:
                            if task_db.started_at and task_db.completed_at:
                                task_db.actual_duration = (task_db.completed_at - task_db.started_at).total_seconds()
                        except Exception:  # pragma: no cover - defensive
                            task_db.actual_duration = None
                        db.session.commit()
                        try:  # Emit completion
                            from app.realtime.task_events import emit_task_event
                            emit_task_event(
                                "task.completed",
                                {
                                    "task_id": task_db.task_id,
                                    "id": task_db.id,
                                    "status": task_db.status.value if task_db.status else None,
                                    "progress_percentage": task_db.progress_percentage,
                                    "completed_at": task_db.completed_at.isoformat() if task_db.completed_at else None,
                                    "actual_duration": task_db.actual_duration,
                                },
                            )
                        except Exception:
                            pass
                        logger.info("Task %s completed", task_db.task_id)
                except Exception as e:  # pragma: no cover - defensive
                    logger.error("TaskExecutionService loop error: %s", e)
                    time.sleep(self.poll_interval)

    def _is_test_mode(self) -> bool:
        try:
            from flask import current_app
            return bool(current_app and current_app.config.get("TESTING"))
        except Exception:  # pragma: no cover
            return False

    # --- Synchronous helper for tests ------------------------------------
    def process_once(self, limit: int | None = None) -> int:
        """Advance a single batch of pending tasks synchronously.

        Returns number of tasks transitioned to COMPLETED. Safe to call repeatedly.
        """
        from app.services.task_service import queue_service
        try:
            from flask import has_app_context
            in_ctx = has_app_context()
        except Exception:
            in_ctx = False

        transitioned = 0
        # Reuse existing context/session if already active to avoid stale identity map in tests
        with (self._app.app_context() if (self._app and not in_ctx) else _nullcontext()):
            try:
                next_tasks = queue_service.get_next_tasks(limit=limit or self.batch_size)
                if not next_tasks:
                    return 0
                for task in next_tasks:
                    task_db: AnalysisTask | None = AnalysisTask.query.filter_by(id=task.id).first()
                    if not task_db or task_db.status != AnalysisStatus.PENDING:
                        continue
                    task_db.status = AnalysisStatus.RUNNING
                    task_db.started_at = datetime.utcnow()
                    db.session.commit()

                    # Simulated quick progress
                    simulated_steps = 3
                    for i in range(1, simulated_steps + 1):
                        task_db.progress_percentage = (i / simulated_steps) * 100.0
                        db.session.commit()
                    # Explicitly force 100% completion for deterministic test expectations
                    task_db.status = AnalysisStatus.COMPLETED
                    task_db.progress_percentage = 100.0
                    task_db.completed_at = datetime.utcnow()
                    try:
                        if task_db.started_at and task_db.completed_at:
                            task_db.actual_duration = (task_db.completed_at - task_db.started_at).total_seconds()
                    except Exception:
                        task_db.actual_duration = None
                    db.session.commit()
                    try:
                        # Refresh to ensure subsequent queries in same context see updated values
                        db.session.refresh(task_db)
                    except Exception:
                        pass
                    try:  # Emit completion (sync path)
                        from app.realtime.task_events import emit_task_event
                        emit_task_event(
                            "task.completed",
                            {
                                "task_id": task_db.task_id,
                                "id": task_db.id,
                                "status": task_db.status.value if task_db.status else None,
                                "progress_percentage": task_db.progress_percentage,
                                "completed_at": task_db.completed_at.isoformat() if task_db.completed_at else None,
                                "actual_duration": task_db.actual_duration,
                            },
                        )
                    except Exception:
                        pass
                    logger.debug("process_once completed task %s progress=%s", task_db.task_id, task_db.progress_percentage)
                    transitioned += 1
            except Exception as e:  # pragma: no cover
                logger.error("process_once error: %s", e)
        return transitioned


# Global singleton style helper (mirrors other services)
task_execution_service: Optional[TaskExecutionService] = None


def init_task_execution_service(poll_interval: float | None = None, app=None) -> TaskExecutionService:
    global task_execution_service
    if task_execution_service is not None:
        return task_execution_service
    from flask import current_app
    app_obj = app or (current_app._get_current_object() if current_app else None)  # type: ignore[attr-defined]
    interval = poll_interval or (0.5 if (app_obj and app_obj.config.get("TESTING")) else 5.0)
    svc = TaskExecutionService(poll_interval=interval, app=app_obj)
    svc.start()
    task_execution_service = svc
    return svc


def _nullcontext():  # pragma: no cover - simple helper
    class _Ctx:
        def __enter__(self):
            return None
        def __exit__(self, *exc):
            return False
    return _Ctx()

__all__ = ["TaskExecutionService", "init_task_execution_service", "task_execution_service"]
