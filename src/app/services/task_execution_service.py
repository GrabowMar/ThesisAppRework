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
import json
from datetime import datetime
from typing import Optional

from app.utils.logging_config import get_logger
from app.config.config_manager import get_config
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

                        # Execute real analysis instead of simulation
                        try:
                            result = self._execute_real_analysis(task_db)
                            success = result.get('status') == 'success'
                            
                            # Save analysis results to database
                            if success and result.get('payload'):
                                # Store the full analysis payload as result summary
                                task_db.set_result_summary(result['payload'])
                                
                                # Extract summary metrics for the task
                                payload = result['payload']
                                if isinstance(payload, dict):
                                    analysis = payload.get('analysis', {})
                                    summary = analysis.get('summary', {})
                                    
                                    # Update task summary fields
                                    task_db.issues_found = summary.get('total_issues_found', 0)
                                    
                                    # Store severity breakdown if available
                                    severity_breakdown = summary.get('severity_breakdown', {})
                                    if severity_breakdown:
                                        task_db.severity_breakdown = json.dumps(severity_breakdown)
                                
                                logger.info("Saved analysis results for task %s with %d issues", task_db.task_id, task_db.issues_found or 0)
                            elif result.get('error'):
                                # Save error details
                                error_payload = {
                                    'status': 'error',
                                    'error': result['error'],
                                    'timestamp': datetime.utcnow().isoformat()
                                }
                                task_db.set_result_summary(error_payload)
                                task_db.error_message = result['error']
                                
                        except Exception as e:
                            logger.error("Analysis execution failed for task %s: %s", task_db.task_id, e)
                            success = False
                            result = {'status': 'error', 'error': str(e)}
                            # Save error to results
                            error_payload = {
                                'status': 'error',
                                'error': str(e),
                                'timestamp': datetime.utcnow().isoformat()
                            }
                            task_db.set_result_summary(error_payload)
                            task_db.error_message = str(e)

                        # Set final status based on analysis result
                        task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                        task_db.progress_percentage = 100.0
                        task_db.completed_at = datetime.utcnow()
                        
                        # Store analysis results if available
                        if result and result.get('payload'):
                            try:
                                task_db.set_metadata(result['payload'])
                            except Exception as e:
                                logger.warning("Failed to store analysis results for task %s: %s", task_db.task_id, e)
                        
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

    def _execute_real_analysis(self, task: AnalysisTask) -> dict:
        """Execute real analysis using the analysis engines."""
        try:
            # Get the analysis type (string)
            analysis_type = task.analysis_type.value if hasattr(task.analysis_type, 'value') else str(task.analysis_type)
            
            # Update progress to indicate analysis starting
            task.progress_percentage = 20.0
            db.session.commit()
            
            # Import engine registry and resolve a valid engine name
            from app.services.analysis_engines import get_engine, ENGINE_REGISTRY

            engine_name = analysis_type
            if engine_name not in ENGINE_REGISTRY:
                # Fallback: treat unknown/custom types as security (static) analysis
                engine_name = 'security'
            engine = get_engine(engine_name)
            
            logger.info(
                "Executing %s analysis for task %s",
                analysis_type,
                getattr(task, "task_id", "unknown")
            )
            
            # Update progress
            task.progress_percentage = 40.0
            db.session.commit()
            
            # Resolve selected tools from task metadata; default only when None
            resolved_tools = None
            try:
                meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            except Exception:
                meta = {}

            # Check direct key first, then custom_options nesting
            cand = meta.get('selected_tools')
            if not isinstance(cand, list):
                cand = (meta.get('custom_options') or {}).get('selected_tools') if isinstance(meta.get('custom_options'), dict) else None
            if isinstance(cand, list):
                # Normalize: resolve tool IDs (ints or numeric strings) to names via ToolRegistryService
                def _as_int_list(seq):
                    vals: list[int] = []
                    for v in seq:
                        if isinstance(v, int):
                            vals.append(v)
                        elif isinstance(v, str):
                            v2 = v.strip()
                            if v2.isdigit():
                                try:
                                    vals.append(int(v2))
                                except Exception:
                                    pass
                    return vals

                id_list = _as_int_list(cand)
                if id_list:
                    try:
                        from app.services.service_locator import ServiceLocator
                        tool_service = ServiceLocator.get_tool_registry_service()
                        names: list[str] = []
                        if tool_service:
                            for tid in id_list:
                                try:
                                    t = tool_service.get_tool(int(tid))  # type: ignore[attr-defined]
                                    name = (t or {}).get('name') if isinstance(t, dict) else None
                                    if name:
                                        names.append(name)
                                except Exception:
                                    continue
                        resolved_tools = names or None
                    except Exception:
                        resolved_tools = None
                elif cand and all(isinstance(x, str) for x in cand):
                    resolved_tools = cand  # already names
                elif cand == []:
                    resolved_tools = []  # explicit empty (should rarely happen due to form validation)

            # Apply defaults only when no explicit selection present
            if resolved_tools is None:
                config = get_config()
                resolved_tools = config.get_default_tools(engine_name)

            # Execute the analysis with resolved tools
            result = engine.run(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                tools=resolved_tools
            )

            try:
                logger.debug(
                    "Task %s resolved tools: %s",
                    getattr(task, "task_id", "unknown"),
                    resolved_tools,
                )
            except Exception:
                pass
            
            # Update progress
            task.progress_percentage = 80.0
            db.session.commit()
            
            logger.info(
                "Analysis completed for task %s with status: %s",
                getattr(task, "task_id", "unknown"),
                result.status,
            )
            
            return {
                'status': result.status,
                'payload': result.payload,
                'error': result.error
            }
            
        except Exception as e:
            logger.error(
                "Failed to execute analysis for task %s: %s",
                getattr(task, "task_id", "unknown"),
                e,
            )
            return {
                'status': 'error',
                'error': str(e),
                'payload': {}
            }

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

                    # Execute real analysis instead of simulation
                    try:
                        result = self._execute_real_analysis(task_db)
                        success = result.get('status') == 'success'
                    except Exception as e:
                        logger.error("Analysis execution failed for task %s: %s", task_db.task_id, e)
                        success = False
                        result = {'status': 'error', 'error': str(e)}

                    # Set final status based on analysis result  
                    task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                    task_db.progress_percentage = 100.0
                    task_db.completed_at = datetime.utcnow()
                    
                    # Store analysis results if available
                    if result and result.get('payload'):
                        try:
                            task_db.set_metadata(result['payload'])
                            
                            # Extract summary information and update task fields
                            payload = result['payload']
                            if isinstance(payload, dict):
                                analysis_data = payload.get('analysis', {})
                                summary = analysis_data.get('summary', {})
                                
                                # Update issues count
                                task_db.issues_found = summary.get('total_issues_found', 0)
                                
                                # Store result summary
                                if summary:
                                    task_db.set_result_summary(summary)
                                
                                # Calculate and store severity breakdown
                                severity_counts = {'error': 0, 'warning': 0, 'info': 0, 'medium': 0, 'high': 0, 'low': 0}
                                
                                if 'results' in analysis_data:
                                    results_data = analysis_data['results']
                                    
                                    # Count Python tool issues
                                    if 'python' in results_data:
                                        python_results = results_data['python']
                                        
                                        # Count Bandit issues
                                        if 'bandit' in python_results and 'issues' in python_results['bandit']:
                                            for issue in python_results['bandit']['issues']:
                                                severity = issue.get('issue_severity', 'unknown').lower()
                                                if severity in severity_counts:
                                                    severity_counts[severity] += 1
                                        
                                        # Count PyLint issues
                                        if 'pylint' in python_results and 'issues' in python_results['pylint']:
                                            for issue in python_results['pylint']['issues']:
                                                issue_type = issue.get('type', 'unknown').lower()
                                                if issue_type in severity_counts:
                                                    severity_counts[issue_type] += 1
                                    
                                    # Count JavaScript tool issues
                                    if 'javascript' in results_data:
                                        js_results = results_data['javascript']
                                        if 'eslint' in js_results and 'issues' in js_results['eslint']:
                                            for issue in js_results['eslint']['issues']:
                                                severity = issue.get('severity', 'unknown').lower()
                                                if severity in severity_counts:
                                                    severity_counts[severity] += 1
                                
                                # Store severity breakdown as JSON
                                import json
                                task_db.severity_breakdown = json.dumps(severity_counts)
                                
                        except Exception as e:
                            logger.warning("Failed to store analysis results for task %s: %s", task_db.task_id, e)
                    
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
