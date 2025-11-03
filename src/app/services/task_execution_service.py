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
import logging
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed, Future

from app.utils.logging_config import get_logger
from app.config.config_manager import get_config
from app.extensions import db, get_components
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.services.result_summary_utils import summarise_findings

# Module-level logger (will be used by main thread)
logger = get_logger("task_executor")


class TaskExecutionService:
    """Simple cooperative task executor.

    Lifecycle:
    - poll DB for pending tasks using queue_service selection logic
    - mark a few as running, simulate work with small sleep, then mark completed

    In tests we shorten delays to keep suite fast (< 1s per task).
    """

    def __init__(self, poll_interval: float = 5.0, batch_size: int = 3, app=None, max_workers: int = 4):
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.max_workers = max_workers
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._app = app  # Keep explicit reference so we can push context inside thread
        
        # ThreadPoolExecutor for parallel task execution (replaces Celery)
        self.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix='analysis_worker'
        )
        self._active_futures: Dict[str, Future] = {}  # task_id -> Future
        self._futures_lock = threading.Lock()
        
        # Create a thread-local logger that will be properly configured in the thread
        self._thread_logger = None
        
        # Load analyzer service configuration
        try:
            from flask import current_app
            if current_app:
                self._service_timeout = current_app.config.get('ANALYZER_SERVICE_TIMEOUT', 600)
                self._retry_enabled = current_app.config.get('ANALYZER_RETRY_FAILED_SERVICES', False)
            else:
                self._service_timeout = 600
                self._retry_enabled = False
        except (RuntimeError, ImportError):
            self._service_timeout = 600
            self._retry_enabled = False

    def _execute_service_with_timeout(self, engine, model_slug: str, app_number: int, tools: list, service_name: str) -> Dict[str, Any]:
        """Execute a service with timeout protection.
        
        Returns:
            Dict with status, payload, and error (if any)
        """
        try:
            import threading
            result_container = {'result': None, 'error': None, 'completed': False}
            
            def run_service():
                try:
                    service_result = engine.run(
                        model_slug=model_slug,
                        app_number=app_number,
                        tools=tools,
                        persist=False
                    )
                    result_container['result'] = service_result
                    result_container['completed'] = True
                except Exception as e:
                    result_container['error'] = str(e)
                    result_container['completed'] = True
            
            thread = threading.Thread(target=run_service, daemon=True)
            thread.start()
            thread.join(timeout=self._service_timeout)
            
            if not result_container['completed']:
                self._log(
                    f"Service {service_name} timed out after {self._service_timeout}s - continuing with other services"
                , level='warning')
                return {
                    'status': 'timeout',
                    'error': f'Service execution timed out after {self._service_timeout} seconds',
                    'payload': {}
                }
            
            if result_container['error']:
                self._log(f"Service {service_name} failed: {result_container['error']}", level='error')
                return {
                    'status': 'error',
                    'error': result_container['error'],
                    'payload': {}
                }
            
            service_result = result_container['result']
            return {
                'status': service_result.status if service_result else 'error',
                'payload': service_result.payload if service_result else {},
                'error': service_result.error if service_result else None
            }
            
        except Exception as e:
            logger.exception(f"Unexpected error executing service {service_name}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'payload': {}
            }

    def start(self):  # pragma: no cover - thread start trivial
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("TaskExecutionService started (interval=%s batch=%s)", self.poll_interval, self.batch_size)

    def stop(self):  # pragma: no cover - not required in tests currently
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        # Shutdown thread pool executor
        self.executor.shutdown(wait=True, cancel_futures=False)
        self._log("TaskExecutionService stopped")

    # --- Internal helpers -------------------------------------------------
    def _run_loop(self):  # pragma: no cover - timing heavy, exercised indirectly
        from app.services.task_service import queue_service
        
        # Configure logging for this daemon thread
        # This ensures logs from the thread are properly captured
        self._thread_logger = self._setup_thread_logging()
        self._log("[THREAD] TaskExecutionService daemon thread started")

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
                        # No pending tasks - sleep and continue
                        self._log("[POLL] No tasks selected by queue service (checked PENDING tasks)", level='debug')
                        time.sleep(self.poll_interval)
                        continue
                    
                    self._log(
                        "[POLL] Selected %d task(s) for execution: %s",
                        len(next_tasks),
                        [t.task_id for t in next_tasks],
                        level='debug'
                    )
                    
                    for task in next_tasks:
                        task_db: AnalysisTask | None = AnalysisTask.query.filter_by(id=task.id).first()
                        if not task_db or task_db.status != AnalysisStatus.PENDING:
                            continue
                        task_db.status = AnalysisStatus.RUNNING
                        # Use timezone-aware UTC timestamps to prevent naive/aware mixing errors
                        task_db.started_at = datetime.now(timezone.utc)
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
                        self._log("Task %s started", task_db.task_id)

                        # Execute real analysis instead of simulation
                        try:
                            result = self._execute_real_analysis(task_db)
                            
                            # Handle parallel execution (status='running' means Celery took over)
                            if result.get('status') == 'running':
                                self._log(f"Task {task_db.task_id} delegated to Celery workers, will poll for completion")
                                # Don't mark as completed yet - let polling handle it
                                continue
                            
                            # Engine returns 'completed' on success or 'failed'/'error' otherwise
                            success = result.get('status') in ('success', 'completed')
                            
                            # Save analysis results to database
                            if success and result.get('payload'):
                                # Store the full analysis payload as result summary
                                task_db.set_result_summary(result['payload'])
                                
                                # Extract summary metrics for the task
                                payload = result['payload']
                                if isinstance(payload, dict):
                                    # Support both legacy shape (metadata['analysis']['summary']) and
                                    # new orchestrator shape (payload['summary']).
                                    summary = payload.get('summary') or payload.get('analysis', {}).get('summary', {})
                                    # Update task summary fields
                                    task_db.issues_found = summary.get('total_issues_found', summary.get('total_findings', 0))
                                    # Store severity breakdown if available
                                    severity_breakdown = summary.get('severity_breakdown', {})
                                    if severity_breakdown:
                                        task_db.severity_breakdown = json.dumps(severity_breakdown)
                                
                                self._log("Saved analysis results for task %s with %d issues", task_db.task_id, task_db.issues_found or 0)
                            elif result.get('error'):
                                # Save error details
                                error_payload = {
                                    'status': 'error',
                                    'error': result['error'],
                                    'timestamp': datetime.now(timezone.utc).isoformat()
                                }
                                task_db.set_result_summary(error_payload)
                                task_db.error_message = result['error']
                                
                        except Exception as e:
                            self._log("Analysis execution failed for task %s: %s", task_db.task_id, e, level='error')
                            success = False
                            result = {'status': 'error', 'error': str(e)}
                            # Save error to results
                            error_payload = {
                                'status': 'error',
                                'error': str(e),
                                'timestamp': datetime.now(timezone.utc).isoformat()
                            }
                            task_db.set_result_summary(error_payload)
                            task_db.error_message = str(e)

                        # Set final status based on analysis result
                        task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                        task_db.progress_percentage = 100.0
                        task_db.completed_at = datetime.now(timezone.utc)
                        
                        # Store analysis results if available (merge with existing metadata)
                        if result and result.get('payload'):
                            try:
                                # Preserve existing metadata (like custom_options) and merge execution results
                                existing_metadata = task_db.get_metadata()
                                merged_metadata = existing_metadata.copy()
                                merged_metadata.update(result['payload'])
                                task_db.set_metadata(merged_metadata)
                                
                                # Write result files to disk (standardized persistence)
                                from app.services.result_file_writer import write_task_result_files
                                try:
                                    written_path = write_task_result_files(task_db, result['payload'])
                                    if written_path:
                                        self._log(f"Successfully wrote result files to disk for task {task_db.task_id}: {written_path}")
                                        # Store file path in task metadata for reference
                                        task_db.set_metadata({**task_db.get_metadata(), 'result_file_path': str(written_path)})
                                    else:
                                        self._log(f"Result file write returned None for task {task_db.task_id} - payload may be incomplete. Check earlier logs for details.", level='error')
                                        # Add warning to task status
                                        task_db.set_metadata({**task_db.get_metadata(), 'result_file_warning': 'File write returned None'})
                                except Exception as write_err:
                                    self._log(f"CRITICAL: Failed to write result files to disk for task {task_db.task_id}: {write_err}", level='error', exc_info=True)
                                    # Store error in task metadata
                                    task_db.set_metadata({**task_db.get_metadata(), 'result_file_error': str(write_err)})
                            except Exception as e:
                                self._log("Failed to store analysis results for task %s: %s", task_db.task_id, e, level='warning')
                        
                        try:
                            if task_db.started_at and task_db.completed_at:
                                # Ensure both timestamps are timezone-aware before subtraction
                                start = task_db.started_at if task_db.started_at.tzinfo else task_db.started_at.replace(tzinfo=timezone.utc)
                                end = task_db.completed_at if task_db.completed_at.tzinfo else task_db.completed_at.replace(tzinfo=timezone.utc)
                                task_db.actual_duration = (end - start).total_seconds()
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
                        self._log("Task %s completed", task_db.task_id)
                except Exception as e:  # pragma: no cover - defensive
                    self._log("TaskExecutionService loop error: %s", e, level='error')
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
            analysis_type = task.task_name
            
            self._log(
                "[EXEC] Starting analysis execution for task %s: type=%s, model=%s, app=%s",
                task.task_id, analysis_type, task.target_model, task.target_app_number
            )
            
            # Update progress to indicate analysis starting
            task.progress_percentage = 20.0
            db.session.commit()
            
            # Import engine registry and resolve a valid engine name
            from app.services.analysis_engines import get_engine

            # Check if this is a unified analysis with tools from multiple services
            meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            
            # Unified if explicit flag true AND more than one service represented
            meta_tools_by_service = meta.get('tools_by_service') or meta.get('custom_options', {}).get('tools_by_service') or {}
            if not isinstance(meta_tools_by_service, dict):
                meta_tools_by_service = {}
            multi_service = len(meta_tools_by_service.keys()) > 1
            explicit_unified_flag = bool(
                meta.get('unified_analysis') or meta.get('custom_options', {}).get('unified_analysis')
            )
            selected_tools = meta.get('selected_tool_names', []) or meta.get('custom_options', {}).get('selected_tool_names', [])
            is_unified_analysis = explicit_unified_flag and multi_service
            
            self._log(
                "[EXEC] Task %s metadata analysis: unified_flag=%s, multi_service=%s (services=%s), "
                "is_unified=%s, selected_tools=%s",
                task.task_id, explicit_unified_flag, multi_service, list(meta_tools_by_service.keys()),
                is_unified_analysis, selected_tools
            , level='debug')
            
            if explicit_unified_flag and not multi_service:
                self._log(
                    "Unified flag present but only one service (%s); treating as single-engine run.",
                    list(meta_tools_by_service.keys())
                , level='debug')

            try:
                self._log(
                    "Task %s metadata tool snapshot: unified=%s selected_ids=%s selected_names=%s tools_by_service_keys=%s",
                    getattr(task, 'task_id', 'unknown'),
                    is_unified_analysis,
                    meta.get('selected_tools') or meta.get('custom_options', {}).get('selected_tools'),
                    selected_tools,
                    list((meta.get('tools_by_service') or {}).keys()) if isinstance(meta.get('tools_by_service'), dict) else None
                , level='debug')
            except Exception:
                pass

            self._log(
                "Unified decision for task %s => unified=%s explicit_flag=%s multi_service=%s services=%s tool_count=%s",
                getattr(task, 'task_id', 'unknown'),
                is_unified_analysis,
                explicit_unified_flag,
                multi_service,
                list(meta_tools_by_service.keys()),
                len(selected_tools) if isinstance(selected_tools, list) else 'n/a'
            , level='debug')
            
            if is_unified_analysis:
                self._log(
                    "[EXEC] Task %s => UNIFIED analysis path (multi-service orchestration)",
                    task.task_id
                )
                # Handle unified analysis with multiple engines
                return self._execute_unified_analysis(task)
            else:
                # Regular single-engine analysis
                engine_name = task.task_name
                self._log(
                    "[EXEC] Task %s => SINGLE-ENGINE analysis path (engine=%s)",
                    task.task_id, engine_name
                )
                # Defensive correction: if metadata shows ONLY ai-analyzer tools but engine not 'ai', fix it.
                try:
                    only_services = list(meta_tools_by_service.keys())
                    if only_services and len(only_services) == 1 and only_services[0] == 'ai-analyzer' and engine_name != 'ai':
                        self._log(
                            "Task %s: correcting engine '%s' -> 'ai' because only AI tools selected (%s)",
                            getattr(task, 'task_id', 'unknown'), engine_name, selected_tools
                        , level='warning')
                        engine_name = 'ai'
                except Exception:
                    pass
                
                engine = get_engine(engine_name)
                
                self._log(
                    "[EXEC] Task %s: Engine resolved to '%s' (%s)",
                    task.task_id, engine_name, type(engine).__name__
                )
            
            # Update progress
            task.progress_percentage = 40.0
            db.session.commit()
            
            # Streamlined tool resolution: check tool NAMES first (stored by create_task)
            resolved_tools = None
            try:
                meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
                if not isinstance(meta, dict):
                    meta = {}
                
                custom_options = meta.get('custom_options', {})
                if not isinstance(custom_options, dict):
                    custom_options = {}
                
                # Priority 1: Check 'tools' key (canonical names set by create_task)
                tools_cand = custom_options.get('tools')
                if isinstance(tools_cand, list) and tools_cand and all(isinstance(t, str) for t in tools_cand):
                    resolved_tools = tools_cand
                    self._log(
                        "[TOOL-SELECT] Task %s: Using tools from metadata.custom_options.tools: %s",
                        task.task_id, resolved_tools, level='debug'
                    )
                
                # Priority 2: Check 'selected_tool_names' (legacy UI route format)
                if resolved_tools is None:
                    names_cand = custom_options.get('selected_tool_names')
                    if isinstance(names_cand, list) and names_cand and all(isinstance(t, str) for t in names_cand):
                        resolved_tools = names_cand
                        self._log(
                            "[TOOL-SELECT] Task %s: Using tools from metadata.custom_options.selected_tool_names: %s",
                            task.task_id, resolved_tools, level='debug'
                        )
                
                # Priority 3: Legacy ID resolution (for old tasks with 'selected_tools' IDs)
                if resolved_tools is None:
                    ids_cand = custom_options.get('selected_tools')
                    if isinstance(ids_cand, list) and ids_cand:
                        # Try to resolve IDs to names
                        id_list = [v for v in ids_cand if isinstance(v, int)]
                        if id_list:
                            try:
                                from app.engines.unified_registry import get_unified_tool_registry
                                unified = get_unified_tool_registry()
                                names = [unified.id_to_name(tid) for tid in id_list]
                                names = [n for n in names if n]  # filter None
                                if names:
                                    resolved_tools = names
                                    self._log(
                                        "[TOOL-SELECT] Task %s: Resolved tool IDs to names: %s",
                                        task.task_id, resolved_tools, level='debug'
                                    )
                            except Exception as e:
                                self._log(f"[TOOL-SELECT] Failed to resolve tool IDs: {e}", level='warning')
            
            except Exception as e:
                self._log(f"[TOOL-SELECT] Error reading tool metadata: {e}", level='warning')
            
            # No fallback to defaults - if tools not specified, that's an error
            if resolved_tools is None or not resolved_tools:
                self._log(
                    "[TOOL-SELECT] ERROR: Task %s has NO TOOLS specified in metadata! Cannot execute.",
                    task.task_id, level='error'
                )
                # Return error result
                return ExecutionResult(
                    status='failed',
                    error=f'No tools specified for task {task.task_id}',
                    payload=None
                )

            # If engine_name is 'ai' but resolved_tools accidentally contains non-AI legacy defaults, restrict to requirements-scanner.
            if engine_name == 'ai':
                try:
                    from app.engines.unified_registry import get_unified_tool_registry
                    unified = get_unified_tool_registry()
                    ai_tools = [t for t in unified.by_container('ai-analyzer')]
                    # Filter to AI tools only (after alias resolution)
                    resolved_tools = [t for t in (resolved_tools or []) if t in ai_tools] or ['requirements-scanner']
                    if any(t not in ai_tools for t in (resolved_tools or [])):
                        self._log(
                            "Task %s: filtered non-AI tools from AI run (unified) -> %s", getattr(task, 'task_id', 'unknown'), resolved_tools
                        , level='debug')
                except Exception as e:
                    self._log(f"Failed AI tool filtering (unified): {e}", level='warning')

            # Log the orchestrator call parameters
            self._log(
                "[EXEC] Task %s: Calling engine.run(model_slug=%s, app_number=%s, tools=%s, persist=True)",
                task.task_id, task.target_model, task.target_app_number, resolved_tools
            )

            # Execute the analysis with resolved tools (with persistence enabled)
            result = engine.run(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                tools=resolved_tools,
                persist=True  # Enable result file writes
            )
            
            self._log(
                "[EXEC] Task %s: Engine.run completed with status=%s, has_payload=%s, error=%s",
                task.task_id, result.status, bool(result.payload), bool(result.error)
            )

            try:
                self._log(
                    "Task %s resolved tools: %s",
                    getattr(task, "task_id", "unknown"),
                    resolved_tools,
                    level='debug')
            except Exception:
                pass
            
            # Update progress
            task.progress_percentage = 80.0
            db.session.commit()
            
            self._log(
                "[EXEC] Task %s: Analysis completed with status=%s",
                task.task_id, result.status
            )
            
            wrapped_payload = self._wrap_single_engine_payload(task, engine_name, result.payload)
            self._log(
                "[EXEC] Task %s: Wrapped payload - total_findings=%s, tools_executed=%s",
                task.task_id, 
                wrapped_payload.get('summary', {}).get('total_findings', 0),
                wrapped_payload.get('summary', {}).get('tools_executed', 0)
            , level='debug')
            
            return {
                'status': result.status,
                'payload': wrapped_payload,
                'error': result.error
            }
            
        except Exception as e:
            self._log(
                "[EXEC] Task %s: EXCEPTION during analysis execution: %s",
                task.task_id, e, level='error', exc_info=True
            )
            self._log(
                "[EXEC] Task %s: Exception context - model=%s, app=%s, analysis_type=%s",
                task.task_id, task.target_model, task.target_app_number, task.task_name
            , level='debug')
            
            # Store error message on task for debugging
            try:
                task.error_message = str(e)
                task.status = AnalysisStatus.FAILED
                db.session.commit()
            except Exception:
                pass
            
            return {
                'status': 'error',
                'error': str(e),
                'payload': {}
            }

    def _execute_unified_analysis(self, task: AnalysisTask) -> dict:
        """Execute unified analysis using ThreadPoolExecutor for parallel subtask execution."""
        try:
            self._log(
                "[UNIFIED] Starting unified analysis for task %s (model=%s, app=%s)",
                task.task_id, task.target_model, task.target_app_number
            )
            
            # Get ALL tools from unified registry
            from app.engines.unified_registry import get_unified_tool_registry
            unified = get_unified_tool_registry()
            detailed = unified.list_tools_detailed()

            tools_by_service: dict[str, list[int]] = {}
            for tool_info in detailed:
                container_val = tool_info.get('container')
                name_val = tool_info.get('name')
                if not isinstance(container_val, str) or not isinstance(name_val, str):
                    continue
                # Exclude purely local legacy tools from forced unified runs
                if container_val == 'local':
                    continue
                tid = unified.tool_id(name_val)
                if tid is None:
                    continue
                tools_by_service.setdefault(container_val, []).append(tid)
            
            self._log(
                "[UNIFIED] Task %s: Forcing execution across ALL services: %s (total_tools=%s)",
                task.task_id, list(tools_by_service.keys()), 
                sum(len(tools) for tools in tools_by_service.values())
            )
            
            # Get subtasks if this is a main task
            subtasks_by_service = {}
            if hasattr(task, 'subtasks') and task.subtasks:
                for subtask in task.subtasks:
                    if subtask.service_name:
                        subtasks_by_service[subtask.service_name] = subtask
                self._log(
                    "[UNIFIED] Task %s: Found %s subtasks: %s",
                    task.task_id, len(subtasks_by_service), list(subtasks_by_service.keys())
                )
            
            # Validate analyzer containers
            container_services = list(tools_by_service.keys())
            self._log(
                "[UNIFIED] Task %s: Validating analyzer containers: %s",
                task.task_id, container_services
            , level='debug')
            if not self._validate_analyzer_containers(container_services):
                error_msg = (
                    f"Analyzer containers not healthy: {container_services}. "
                    "Start containers with: python analyzer/analyzer_manager.py start"
                )
                self._log("[UNIFIED] Task %s: %s", task.task_id, error_msg, level='error')
                
                # Mark all subtasks as failed before raising
                for subtask in subtasks_by_service.values():
                    subtask.status = AnalysisStatus.FAILED
                    subtask.error_message = error_msg
                    subtask.completed_at = datetime.now(timezone.utc)
                db.session.commit()
                
                raise RuntimeError(error_msg)
            self._log("[UNIFIED] Task %s: All analyzer containers healthy", task.task_id)
            
            # Execute subtasks in parallel using ThreadPoolExecutor
            subtask_ids = [subtask.task_id for subtask in subtasks_by_service.values()]
            return self.submit_parallel_subtasks(task.task_id, subtask_ids)
            
        except Exception as e:
            self._log(
                "[UNIFIED] Task %s: EXCEPTION during unified analysis: %s",
                task.task_id, e, exc_info=True
            , level='error')
            # Mark all subtasks as failed
            if 'subtasks_by_service' in locals():
                for subtask in subtasks_by_service.values():
                    if subtask.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
                        subtask.status = AnalysisStatus.FAILED
                        subtask.error_message = str(e)
                        subtask.completed_at = datetime.now(timezone.utc)
                db.session.commit()
            raise
    
    def submit_parallel_subtasks(
        self,
        main_task_id: str,
        subtask_ids: List[str]
    ) -> dict:
        """Submit multiple subtasks for parallel execution using ThreadPoolExecutor.
        
        Replaces Celery group/chord pattern with ThreadPoolExecutor.
        
        Args:
            main_task_id: Main task ID
            subtask_ids: List of subtask IDs to execute in parallel
        """
        # Get main task from DB
        main_task = AnalysisTask.query.filter_by(task_id=main_task_id).first()
        if not main_task:
            raise ValueError(f"Main task {main_task_id} not found")
        
        # Get all subtasks from DB
        subtasks = []
        for subtask_id in subtask_ids:
            subtask = AnalysisTask.query.filter_by(task_id=subtask_id).first()
            if subtask:
                subtasks.append(subtask)
        
        if not subtasks:
            error_msg = f"No subtasks found for main task {main_task_id}"
            self._log(error_msg, level='error')
            raise RuntimeError(error_msg)
        
        futures = []
        subtask_info = []
        
        for subtask in subtasks:
            service_name = subtask.service_name
            
            # Get tool names from subtask metadata
            metadata = subtask.get_metadata() if hasattr(subtask, 'get_metadata') else {}
            custom_options = metadata.get('custom_options', {})
            tool_names = custom_options.get('tool_names', [])
            
            if not tool_names:
                self._log(f"No tools found for subtask {subtask.task_id} ({service_name}), skipping", level='warning')
                continue
            
            self._log(f"Queuing parallel subtask for {service_name} with tools: {tool_names}")
            
            # Submit subtask to thread pool
            future = self.executor.submit(
                self._execute_subtask_in_thread,
                subtask.id,
                main_task.target_model,
                main_task.target_app_number,
                tool_names,
                service_name
            )
            futures.append(future)
            subtask_info.append({
                'service': service_name,
                'subtask_id': subtask.id,
                'subtask_task_id': subtask.task_id,
                'tools': tool_names
            })
        
        if not futures:
            error_msg = f"No parallel subtasks created for unified analysis of task {main_task_id}"
            self._log(error_msg, level='error')
            raise RuntimeError(error_msg)
        
        self._log(
            f"✅ Submitted {len(futures)} subtasks to ThreadPoolExecutor for task {main_task_id}. "
            f"Services: {', '.join([info['service'] for info in subtask_info])}"
        )
        
        # Mark main task as RUNNING and spawn aggregation thread
        main_task.status = AnalysisStatus.RUNNING
        main_task.progress_percentage = 30.0  # Subtasks started
        db.session.commit()
        
        # Submit aggregation task that waits for all subtasks
        aggregation_future = self.executor.submit(
            self._aggregate_subtask_results_in_thread,
            main_task_id,
            futures,
            subtask_info
        )
        
        # Track the aggregation future
        with self._futures_lock:
            self._active_futures[main_task_id] = aggregation_future
        
        return {
            'status': 'running',
            'engine': 'unified',
            'model_slug': main_task.target_model,
            'app_number': main_task.target_app_number,
            'payload': {
                'message': 'Subtasks executing in parallel via ThreadPoolExecutor',
                'services': [info['service'] for info in subtask_info],
                'subtask_count': len(futures)
            }
        }
    
    def _execute_subtask_in_thread(
        self,
        subtask_id: int,
        model_slug: str,
        app_number: int,
        tools: List[str],
        service_name: str
    ) -> Dict[str, Any]:
        """Execute subtask via WebSocket to analyzer microservice."""
        with self._app.app_context():
            try:
                # Get fresh subtask from DB
                subtask = AnalysisTask.query.get(subtask_id)
                if not subtask:
                    return {'status': 'error', 'error': f'Subtask {subtask_id} not found'}
                
                # Mark as running
                subtask.status = AnalysisStatus.RUNNING
                subtask.started_at = datetime.now(timezone.utc)
                db.session.commit()
                
                self._log(
                    f"[SUBTASK] Executing subtask {subtask_id} via WebSocket to {service_name} with tools {tools}"
                )
                
                # Execute via WebSocket to analyzer microservice
                result = self._execute_via_websocket(
                    service_name=service_name,
                    model_slug=model_slug,
                    app_number=app_number,
                    tools=tools,
                    timeout=600
                )
                
                # Store result and mark complete
                success = result.get('status') in ('success', 'completed', 'ok')
                subtask.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                subtask.completed_at = datetime.now(timezone.utc)
                subtask.progress_percentage = 100.0
                
                if result.get('payload'):
                    subtask.set_result_summary(result['payload'])
                
                if result.get('error'):
                    subtask.error_message = result['error']
                
                db.session.commit()
                
                self._log(
                    f"[SUBTASK] Completed subtask {subtask_id} for {service_name}: {result.get('status')}"
                )
                
                return {
                    'status': result.get('status', 'error'),
                    'payload': result.get('payload', {}),
                    'error': result.get('error'),
                    'service_name': service_name,
                    'subtask_id': subtask_id
                }
                
            except Exception as e:
                self._log(
                    f"[SUBTASK] Exception in subtask {subtask_id}: {e}",
                    level='error',
                    exc_info=True
                )
                # Mark subtask as failed
                try:
                    subtask = AnalysisTask.query.get(subtask_id)
                    if subtask:
                        subtask.status = AnalysisStatus.FAILED
                        subtask.error_message = str(e)
                        subtask.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    pass
                
                return {
                    'status': 'error',
                    'error': str(e),
                    'service_name': service_name,
                    'subtask_id': subtask_id
                }
    
    def _aggregate_subtask_results_in_thread(
        self,
        main_task_id: str,
        futures: List[Future],
        subtask_info: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Wait for all subtasks to complete and aggregate results (replaces aggregate_subtask_results Celery task)."""
        # Push Flask app context for this thread
        with self._app.app_context():
            try:
                self._log(f"[AGGREGATE] Waiting for {len(futures)} subtasks to complete for main task {main_task_id}")
                
                # Wait for all futures with per-future timeout to prevent hangs
                results = []
                for idx, future in enumerate(futures):
                    try:
                        # Individual timeout per subtask (10 minutes each)
                        result = future.result(timeout=600)
                        results.append(result)
                        self._log(f"[AGGREGATE] Subtask {idx+1}/{len(futures)} completed successfully")
                    except TimeoutError:
                        self._log(f"[AGGREGATE] Subtask {idx+1}/{len(futures)} timed out after 600s", level='error')
                        results.append({'status': 'error', 'error': 'Subtask execution timeout (600s)'})
                    except Exception as e:
                        self._log(f"[AGGREGATE] Subtask {idx+1}/{len(futures)} raised exception: {e}", level='error', exc_info=True)
                        results.append({'status': 'error', 'error': str(e)})
                
                self._log(f"[AGGREGATE] All {len(results)} subtasks completed for main task {main_task_id}")
                
                # Get main task from DB
                main_task = AnalysisTask.query.filter_by(task_id=main_task_id).first()
                if not main_task:
                    self._log(f"[AGGREGATE] Main task {main_task_id} not found", level='error')
                    return {'status': 'error', 'error': 'Main task not found'}
                
                # Aggregate results from subtasks
                all_services = {}
                all_findings = []
                combined_tool_results = {}
                any_failed = False
                
                for result in results:
                    service_name = result.get('service_name', 'unknown')
                    all_services[service_name] = result
                    
                    if result.get('status') not in ('success', 'completed'):
                        any_failed = True
                    
                    # Extract findings and tool results
                    payload = result.get('payload', {})
                    if isinstance(payload, dict):
                        findings = payload.get('findings', [])
                        if isinstance(findings, list):
                            all_findings.extend(findings)
                        
                        tool_results = payload.get('tool_results', {})
                        if isinstance(tool_results, dict):
                            combined_tool_results.update(tool_results)
                
                # Build unified payload
                unified_payload = {
                    'task': {'task_id': main_task_id},
                    'summary': {
                        'total_findings': len(all_findings),
                        'services_executed': len(all_services),
                        'tools_executed': len(combined_tool_results),
                        'status': 'completed' if not any_failed else 'partial'
                    },
                    'services': all_services,
                    'tools': combined_tool_results,
                    'findings': all_findings,
                    'metadata': {
                        'unified_analysis': True,
                        'orchestrator_version': '3.0.0',
                        'executor': 'ThreadPoolExecutor',
                        'generated_at': datetime.now(timezone.utc).isoformat()
                    }
                }
                
                # Update main task
                main_task.status = AnalysisStatus.COMPLETED if not any_failed else AnalysisStatus.FAILED
                main_task.completed_at = datetime.now(timezone.utc)
                main_task.progress_percentage = 100.0
                if main_task.started_at:
                    # Ensure started_at is timezone-aware before subtraction to prevent
                    # "can't subtract offset-naive and offset-aware datetimes" error
                    started_at = main_task.started_at
                    if started_at.tzinfo is None:
                        # If somehow started_at is naive, make it aware (assume UTC)
                        started_at = started_at.replace(tzinfo=timezone.utc)
                    duration = (main_task.completed_at - started_at).total_seconds()
                    main_task.actual_duration = duration
                main_task.set_result_summary(unified_payload)
                db.session.commit()
                
                # Persist results to filesystem (matching analyzer_manager structure)
                try:
                    self._write_task_results_to_filesystem(
                        main_task.target_model,
                        main_task.target_app_number,
                        main_task_id,
                        unified_payload
                    )
                except Exception as fs_error:
                    self._log(
                        f"[AGGREGATE] Failed to write results to filesystem: {fs_error}",
                        level='warning'
                    )
                
                self._log(f"[AGGREGATE] Main task {main_task_id} marked as completed")
                
                # Remove from active futures
                with self._futures_lock:
                    self._active_futures.pop(main_task_id, None)
                
                return unified_payload
                
            except Exception as e:
                self._log(
                    f"[AGGREGATE] Exception aggregating results for {main_task_id}: {e}",
                    exc_info=True,
                    level='error'
                )
                # Mark main task as failed
                try:
                    main_task = AnalysisTask.query.filter_by(task_id=main_task_id).first()
                    if main_task:
                        main_task.status = AnalysisStatus.FAILED
                        main_task.error_message = f"Aggregation failed: {str(e)}"
                        main_task.completed_at = datetime.now(timezone.utc)
                        db.session.commit()
                except Exception:
                    pass
                
                # Remove from active futures
                with self._futures_lock:
                    self._active_futures.pop(main_task_id, None)
                
                return {'status': 'error', 'error': str(e)}

    def _execute_via_websocket(
        self,
        service_name: str,
        model_slug: str,
        app_number: int,
        tools: List[str],
        timeout: int = 600
    ) -> Dict[str, Any]:
        """Execute analysis via WebSocket (synchronous wrapper for thread pool)."""
        # Service port mapping
        SERVICE_PORTS = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002,
            'performance-tester': 2003,
            'ai-analyzer': 2004
        }
        
        port = SERVICE_PORTS.get(service_name)
        if not port:
            return {
                'status': 'error',
                'error': f'Unknown service: {service_name}',
                'payload': {}
            }
        
        # Run async WebSocket communication in new event loop
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._websocket_request_async(
                        service_name, port, model_slug, app_number, tools, timeout
                    )
                )
                return result
            finally:
                loop.close()
        except Exception as e:
            self._log(f"[WebSocket] Error: {e}", level='error', exc_info=True)
            return {
                'status': 'error',
                'error': f'WebSocket execution error: {str(e)}',
                'payload': {}
            }
    
    async def _websocket_request_async(
        self,
        service_name: str,
        port: int,
        model_slug: str,
        app_number: int,
        tools: List[str],
        timeout: int
    ) -> Dict[str, Any]:
        """Execute WebSocket request to analyzer service (async)."""
        import websockets
        from websockets.exceptions import ConnectionClosed
        import time
        
        websocket_url = f'ws://localhost:{port}'
        
        # Service-specific message type mapping
        MESSAGE_TYPES = {
            'static-analyzer': 'static_analyze',
            'dynamic-analyzer': 'dynamic_analyze',
            'ai-analyzer': 'ai_analyze',
            'performance-tester': 'performance_test'
        }
        
        message_type = MESSAGE_TYPES.get(service_name, 'analysis_request')
        
        # Build request message in format expected by analyzer services
        request_message = {
            'type': message_type,
            'model_slug': model_slug,  # Services expect model_slug, not model
            'app_number': app_number,   # Services expect app_number, not app
            'tools': tools,
            'id': f"{model_slug}_app{app_number}_{service_name}",
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        self._log(
            f"[WebSocket] Connecting to {service_name} at {websocket_url} "
            f"for {model_slug}/app{app_number} with tools: {tools}"
        )
        
        try:
            async with websockets.connect(
                websocket_url,
                open_timeout=10,
                close_timeout=10,
                ping_interval=None,
                ping_timeout=None
            ) as websocket:
                # Send request
                await websocket.send(json.dumps(request_message))
                self._log(f"[WebSocket] Sent request to {service_name}")
                
                # Wait for response (handle progress frames)
                deadline = time.time() + timeout
                first_frame: Optional[Dict[str, Any]] = None
                terminal_frame: Optional[Dict[str, Any]] = None
                
                while time.time() < deadline:
                    remaining = max(0.1, deadline - time.time())
                    
                    try:
                        raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
                    except asyncio.TimeoutError:
                        self._log(f"[WebSocket] Timeout waiting for {service_name}", level='warning')
                        break
                    except ConnectionClosed:
                        self._log(f"[WebSocket] Connection closed by {service_name}", level='warning')
                        break
                    
                    # Parse frame
                    try:
                        frame = json.loads(raw)
                    except json.JSONDecodeError as e:
                        self._log(f"[WebSocket] Invalid JSON from {service_name}: {str(e)}", level='error')
                        continue
                    
                    if first_frame is None:
                        first_frame = frame
                    
                    # Check if terminal frame
                    frame_type = str(frame.get('type', '')).lower()
                    has_analysis = isinstance(frame.get('analysis'), dict)
                    
                    self._log(
                        f"[WebSocket] Frame from {service_name}: type={frame_type}, "
                        f"has_analysis={has_analysis}, status={frame.get('status')}",
                        level='debug'
                    )
                    
                    # Terminal conditions
                    if ('analysis_result' in frame_type) or (frame_type.endswith('_analysis') and has_analysis):
                        terminal_frame = frame
                        if has_analysis:
                            self._log(f"[WebSocket] Received terminal frame from {service_name}")
                            break
                
                # Return best available frame
                result = terminal_frame or first_frame or {
                    'status': 'error',
                    'error': 'No response from service'
                }
                
                self._log(
                    f"[WebSocket] Analysis complete from {service_name}: status={result.get('status')}"
                )
                
                return {
                    'status': result.get('status', 'error'),
                    'payload': result.get('analysis', result),
                    'error': result.get('error')
                }
                
        except asyncio.TimeoutError:
            return {
                'status': 'timeout',
                'error': f'Connection to {service_name} timed out after {timeout}s',
                'payload': {}
            }
        except ConnectionClosed:
            return {
                'status': 'error',
                'error': f'Connection to {service_name} closed unexpectedly',
                'payload': {}
            }
        except Exception as e:
            self._log(f"[WebSocket] Error connecting to {service_name}: {e}", level='error', exc_info=True)
            return {
                'status': 'error',
                'error': f'WebSocket error: {str(e)}',
                'payload': {}
            }
    
    def _wrap_single_engine_payload(self, task, engine_name: str, raw_payload: dict) -> dict:
        """Wrap a single-engine (non-unified) payload into the big schema format.

        raw_payload: orchestrator-style payload (may already have tool_results etc.)
        """
        if not isinstance(raw_payload, dict):
            raw_payload = {}
        tools = raw_payload.get('tool_results') or {}
        requested = raw_payload.get('tools_requested') or []
        task_id_val = getattr(task, 'task_id', 'unknown')
        # Map engine_name to synthetic service key for consistency
        engine_service_map = {
            'security': 'static-analyzer',
            'static': 'static-analyzer',
            'dynamic': 'dynamic-analyzer',
            'performance': 'performance-tester',
            'ai': 'ai-analyzer'
        }
        svc_name = engine_service_map.get(engine_name, engine_name)
        # Compose unified result structure
        wrapped = {
            'task': {
                'task_id': task_id_val,
                'task_name': task.task_name,
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': None
            },
            'summary': {
                'total_findings': raw_payload.get('summary', {}).get('total_findings', 0),
                'services_executed': 1,
                'tools_executed': len(tools),
                'severity_breakdown': raw_payload.get('summary', {}).get('severity_breakdown', {}),
                'findings_by_tool': raw_payload.get('summary', {}).get('tools_breakdown', {}),
                'tools_used': requested,
                'tools_failed': [t for t,v in tools.items() if v.get('status') not in ('success','completed')],
                'tools_skipped': [],
                'status': raw_payload.get('success') and 'completed' or 'failed'
            },
            'services': {svc_name: raw_payload},
            'tools': tools,
            'findings': raw_payload.get('findings', []),
            'metadata': {
                'unified_analysis': False,
                'orchestrator_version': '2.0.0',
                'schema_version': '3.0',
                'generated_at': datetime.now(timezone.utc).isoformat() if 'datetime' in globals() else None,
                'input': {
                    'requested_tools': requested,
                    'requested_services': [svc_name],
                    'engine_mode': 'single'
                }
            }
        }
        return wrapped
    
    def _write_task_results_to_filesystem(
        self,
        model_slug: str,
        app_number: int,
        task_id: str,
        unified_payload: Dict[str, Any]
    ) -> None:
        """Write task results to filesystem matching analyzer_manager structure.
        
        Saves to: results/{model_slug}/app{app_number}/task_{task_id}/
        """
        # Build results directory path (mirroring analyzer_manager.py structure)
        results_base = Path(__file__).resolve().parent.parent.parent.parent / "results"
        safe_slug = str(model_slug).replace('/', '_').replace('\\', '_')
        sanitized_task = str(task_id).replace(':', '_').replace('/', '_')
        
        # Don't add "task_" prefix if task_id already starts with "task_"
        task_folder_name = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
        
        task_dir = results_base / safe_slug / f"app{app_number}" / task_folder_name
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Build filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use task_folder_name which already has correct "task_" prefix handling
        filename = f"{safe_slug}_app{app_number}_{task_folder_name}_{timestamp}.json"
        filepath = task_dir / filename
        
        # Build comprehensive results structure (matching analyzer_manager format)
        full_results = {
            'metadata': {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': task_id,
                'timestamp': datetime.now().isoformat() + '+00:00',
                'analyzer_version': '1.0.0',
                'module': 'analysis',
                'version': '1.0',
                'executor': 'task_execution_service'
            },
            'results': unified_payload
        }
        
        # Write the main consolidated file
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(full_results, f, indent=2, default=str)
        
        self._log(
            f"[FILESYSTEM] Task results written to: {filepath}",
            level='info'
        )
        
        # Also write a manifest.json for easy discovery
        manifest_path = task_dir / "manifest.json"
        manifest = {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'result_file': filename,
            'created_at': datetime.now().isoformat(),
            'status': unified_payload.get('summary', {}).get('status', 'unknown'),
            'total_findings': unified_payload.get('summary', {}).get('total_findings', 0),
            'services_executed': unified_payload.get('summary', {}).get('services_executed', 0)
        }
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, default=str)
    
    def _validate_analyzer_containers(self, service_names: list[str]) -> bool:
        """Validate that all required analyzer containers are healthy."""
        try:
            from app.services.analyzer_integration import health_monitor
            
            if health_monitor is None:
                self._log("Health monitor not available", level='warning')
                return False
            
            # Get cached health status
            health_status = health_monitor.get_cached_health_status()
            
            # If cache is empty, assume containers are healthy (they'll fail during execution if not)
            if not health_status:
                self._log("Health status cache empty - assuming containers are healthy")
                return True
            
            unhealthy = []
            for service_name in service_names:
                service_health = health_status.get(service_name, {})
                status = service_health.get('status', 'unknown')
                if status != 'healthy':
                    unhealthy.append(service_name)
            
            if unhealthy:
                self._log(f"Analyzer containers not healthy: {unhealthy}", level='error')
                return False
            
            self._log(f"All analyzer containers are healthy: {service_names}")
            return True
        except Exception as e:
            self._log(f"Failed to validate analyzer containers: {e}", level='error')
            return False

    def _resolve_tool_ids_to_names(self, tool_ids: list[int]) -> list[str]:
        """Resolve tool IDs back to tool names."""
        from app.engines.unified_registry import get_unified_tool_registry
        unified = get_unified_tool_registry()
        names: list[str] = []
        for tid in tool_ids:
            name = unified.id_to_name(tid)
            if name:
                names.append(name)
        if names:
            return names
        # Transitional fallback: container registry mapping if unified returned nothing
        try:
            from app.engines.container_tool_registry import get_container_tool_registry
            c_registry = get_container_tool_registry()
            all_tools = c_registry.get_all_tools()
            fallback = {idx + 1: tname for idx, (tname, _tool) in enumerate(all_tools.items())}
            for tid in tool_ids:
                tname = fallback.get(tid)
                if tname and tname not in names:
                    names.append(tname)
        except Exception:
            pass
        return names

    def _is_success_status(self, status: Any) -> bool:
        value = str(status or '').lower()
        return value in ('success', 'completed', 'ok', 'passed', 'done')

    def _load_saved_service_payloads(self, model_slug: str, app_number: int) -> Dict[str, Dict[str, Any]]:
        payloads: Dict[str, Dict[str, Any]] = {}
        try:
            from app.engines.orchestrator import get_analysis_orchestrator
            orchestrator = get_analysis_orchestrator()
        except Exception:
            return payloads

        base_path_obj = getattr(getattr(orchestrator, 'results_manager', None), 'base_path', None)
        if not base_path_obj:
            return payloads

        safe_slug = model_slug.replace('/', '_').replace('\\', '_')
        app_dir = Path(base_path_obj) / safe_slug / f"app{app_number}"
        if not app_dir.exists():
            return payloads
        legacy_dir = app_dir / 'analysis'

        pattern_map: Dict[str, List[str]] = {
            'static-analyzer': ['static', 'security'],
            'dynamic-analyzer': ['dynamic'],
            'performance-tester': ['performance'],
            'ai-analyzer': ['ai']
        }

        for service_name, tokens in pattern_map.items():
            # Prefer snapshots written inside task folders
            snapshot_candidates: List[Path] = []
            for task_dir in app_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                if not (task_dir.name.startswith('task-') or task_dir.name.startswith('task_')):
                    continue
                services_dir = task_dir / 'services'
                if not services_dir.exists():
                    continue
                candidate = services_dir / f"{safe_slug}_app{app_number}_{service_name}.json"
                if candidate.exists():
                    snapshot_candidates.append(candidate)
            snapshot_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

            loaded = False
            for candidate in snapshot_candidates:
                try:
                    with candidate.open('r', encoding='utf-8') as handle:
                        data = json.load(handle)
                    if isinstance(data, dict):
                        payloads[service_name] = data
                        loaded = True
                        break
                except Exception:
                    continue
            if loaded:
                continue

            if not legacy_dir.exists():
                continue

            legacy_candidates: List[Path] = []
            for token in tokens:
                matches = [
                    p for p in legacy_dir.glob(f"*_{token}_*.json")
                    if '_task-' not in p.name
                ]
                matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                legacy_candidates.extend(matches)

            for candidate in legacy_candidates:
                try:
                    with candidate.open('r', encoding='utf-8') as handle:
                        data = json.load(handle)
                    if isinstance(data, dict):
                        payloads[service_name] = data
                        break
                except Exception:
                    continue
        return payloads

    def _unwrap_service_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(data, dict):
            return {}
        if 'results' in data and isinstance(data['results'], dict):
            merged = dict(data['results'])
            for key in ('raw_outputs', 'services', 'summary', 'tools_used', 'findings'):
                if key in data and key not in merged:
                    merged[key] = data[key]
            if 'metadata' in data and 'metadata' not in merged:
                merged['metadata'] = data['metadata']
            return merged
        return data

    def _normalize_tool_result(self, tool_data: Any) -> Dict[str, Any]:
        if not isinstance(tool_data, dict):
            return {'status': 'unknown'}
        normalized: Dict[str, Any] = {}
        for key in ('status', 'executed', 'duration_seconds', 'total_issues', 'issue_count', 'exit_code', 'error', 'command_line', 'command'):
            if key in tool_data and tool_data[key] not in (None, ''):
                normalized[key] = tool_data[key]
        if 'issue_count' in normalized and 'total_issues' not in normalized:
            normalized['total_issues'] = normalized.pop('issue_count')
        if 'raw_output' in tool_data and tool_data['raw_output']:
            normalized['raw_output'] = tool_data['raw_output']
        if 'stdout' in tool_data and tool_data['stdout']:
            normalized['stdout'] = tool_data['stdout']
        if 'stderr' in tool_data and tool_data['stderr']:
            normalized['stderr'] = tool_data['stderr']
        raw_block = tool_data.get('raw')
        if isinstance(raw_block, dict):
            merged_raw = dict(raw_block)
            normalized['raw'] = merged_raw
            if merged_raw.get('stdout') and 'raw_output' not in normalized:
                normalized['raw_output'] = merged_raw['stdout']
            if merged_raw.get('duration_seconds') and 'duration_seconds' not in normalized:
                normalized['duration_seconds'] = merged_raw['duration_seconds']
        if 'status' not in normalized:
            normalized['status'] = tool_data.get('state') or 'unknown'
        return normalized

    def _extract_tool_results_from_payload(self, service_name: str, payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        tools: Dict[str, Dict[str, Any]] = {}
        if not isinstance(payload, dict):
            return tools

        candidates: List[Dict[str, Any]] = []
        if isinstance(payload.get('tool_results'), dict):
            candidates.append(payload['tool_results'])

        results_section = payload.get('results')
        if isinstance(results_section, dict):
            # Check for tool_results at results level
            nested = results_section.get('tool_results')
            if isinstance(nested, dict):
                candidates.append(nested)
            
            # CRITICAL FIX: Extract from language-specific sections (e.g., results.python.bandit)
            # This is the actual structure returned by static-analyzer and dynamic-analyzer services
            for lang_key in ['python', 'javascript', 'css', 'html', 'connectivity']:
                lang_section = results_section.get(lang_key)
                if isinstance(lang_section, dict):
                    # Each tool is a direct key in the language section
                    for tool_name, tool_data in lang_section.items():
                        if isinstance(tool_data, dict) and 'status' in tool_data:
                            # This is a tool result (has status, executed, etc.)
                            normalized = self._normalize_tool_result(tool_data)
                            tools[tool_name] = self._merge_tool_records(tools.get(tool_name), normalized)

        services_section = payload.get('services')
        if isinstance(services_section, dict):
            for svc_data in services_section.values():
                if not isinstance(svc_data, dict):
                    continue
                analysis = svc_data.get('analysis') if isinstance(svc_data.get('analysis'), dict) else None
                if analysis:
                    nested_results = analysis.get('tool_results') or analysis.get('tool_runs')
                    if isinstance(nested_results, dict):
                        candidates.append(nested_results)

        raw_section = payload.get('raw_outputs')
        if isinstance(raw_section, dict):
            for entry in raw_section.values():
                if isinstance(entry, dict) and isinstance(entry.get('tools'), dict):
                    candidates.append(entry['tools'])

        for candidate in candidates:
            for tool_name, tool_data in candidate.items():
                if not isinstance(tool_name, str):
                    continue
                normalized = self._normalize_tool_result(tool_data)
                tools[tool_name] = self._merge_tool_records(tools.get(tool_name), normalized)

        summary = payload.get('summary')
        if isinstance(summary, dict):
            by_tool = summary.get('by_tool')
            if isinstance(by_tool, dict):
                for tool_name, issue_count in by_tool.items():
                    existing = tools.get(tool_name, {'status': 'success'})
                    if isinstance(issue_count, (int, float)) and isinstance(existing, dict) and 'total_issues' not in existing:
                        existing['total_issues'] = int(issue_count)
                    tools[tool_name] = existing

        return tools

    def _merge_tool_records(self, existing: Optional[Dict[str, Any]], new: Dict[str, Any]) -> Dict[str, Any]:
        if not existing:
            return dict(new) if isinstance(new, dict) else {}
        merged = dict(existing)
        for key, value in new.items():
            if value in (None, '', [], {}):
                continue
            if key == 'raw' and isinstance(value, dict):
                combined_raw = dict(merged.get('raw', {}))
                combined_raw.update(value)
                merged['raw'] = combined_raw
            elif key not in merged or merged[key] in (None, '', [], {}):
                merged[key] = value
            elif key == 'raw_output' and not merged.get('raw_output'):
                merged[key] = value
        return merged

    def _compile_summary_metrics(
        self,
        findings: List[Dict[str, Any]],
        service_summaries: List[Dict[str, Any]],
        tool_results: Dict[str, Dict[str, Any]]
    ) -> tuple[int, Dict[str, int], Dict[str, int]]:
        total_findings, severity_counts, findings_by_tool = summarise_findings(
            findings,
            service_summaries,
            tool_results,
            normalise_severity=True,
        )
        return total_findings, severity_counts, findings_by_tool

    def _extract_raw_outputs_from_payload(self, service_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        extracted: Dict[str, Any] = {}
        if not isinstance(payload, dict):
            return extracted
        raw_section = payload.get('raw_outputs')
        if not isinstance(raw_section, dict):
            return extracted
        for key, entry in raw_section.items():
            if isinstance(entry, dict) and isinstance(entry.get('tools'), dict):
                for tool_name, tool_data in entry['tools'].items():
                    if not isinstance(tool_data, dict):
                        continue
                    normalized: Dict[str, Any] = {}
                    for raw_key in ('raw_output', 'stdout', 'stderr', 'command', 'command_line', 'exit_code', 'error', 'duration', 'duration_seconds', 'raw'):
                        if raw_key in tool_data and tool_data[raw_key] not in (None, '', [], {}):
                            normalized[raw_key] = tool_data[raw_key]
                    if normalized:
                        extracted[tool_name] = self._merge_tool_records(extracted.get(tool_name), normalized)
            elif isinstance(entry, dict):
                extracted[f"{service_name}:{key}"] = entry
        return extracted

    def _build_raw_outputs_block(
        self,
        tool_results: Dict[str, Dict[str, Any]],
        services_block: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        raw_outputs: Dict[str, Any] = {}
        for tool_name, meta in tool_results.items():
            if not isinstance(meta, dict):
                continue
            raw_entry: Dict[str, Any] = {}
            for key in ('raw_output', 'stdout', 'stderr', 'command', 'command_line', 'exit_code', 'error', 'duration_seconds', 'raw'):
                if key in meta and meta[key] not in (None, '', [], {}):
                    raw_entry[key] = meta[key]
            if raw_entry:
                raw_outputs[tool_name] = raw_entry

        for svc_name, svc_payload in services_block.items():
            extracted = self._extract_raw_outputs_from_payload(svc_name, svc_payload)
            for key, value in extracted.items():
                if key not in raw_outputs:
                    raw_outputs[key] = value
            raw_outputs.setdefault(
                f'service:{svc_name}',
                {
                    'status': 'ok',
                    'tool_count': len(self._extract_tool_results_from_payload(svc_name, svc_payload))
                }
            )

        return raw_outputs

    def _dedupe_findings(self, findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not findings:
            return []
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            message = finding.get('message')
            if isinstance(message, dict):
                message_val = message.get('title') or message.get('description') or ''
            else:
                message_val = message or ''
            key = "|".join([
                str(finding.get('id') or finding.get('rule_id') or ''),
                str(finding.get('tool') or finding.get('tool_name') or ''),
                str(message_val)
            ])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(finding)
        return deduped

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
                    task_db.started_at = datetime.now(timezone.utc)
                    db.session.commit()

                    # Execute real analysis instead of simulation
                    try:
                        result = self._execute_real_analysis(task_db)
                        success = result.get('status') == 'success'
                    except Exception as e:
                        self._log("Analysis execution failed for task %s: %s", task_db.task_id, e, level='error')
                        success = False
                        result = {'status': 'error', 'error': str(e)}

                    # Set final status based on analysis result  
                    task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                    task_db.progress_percentage = 100.0
                    task_db.completed_at = datetime.now(timezone.utc)
                    
                    # Store analysis results if available (merge with existing metadata)
                    if result and result.get('payload'):
                        try:
                            # Preserve existing metadata (like custom_options) and merge execution results
                            existing_metadata = task_db.get_metadata()
                            merged_metadata = existing_metadata.copy()
                            merged_metadata.update(result['payload'])
                            task_db.set_metadata(merged_metadata)
                            # Extract summary information and update task fields (supports both payload shapes)
                            payload = result['payload']
                            if isinstance(payload, dict):
                                summary = payload.get('summary') or payload.get('analysis', {}).get('summary', {})
                                # Update issues count
                                task_db.issues_found = summary.get('total_issues_found', summary.get('total_findings', 0))
                                # Store result summary if present
                                if summary:
                                    task_db.set_result_summary(summary)
                                # Store severity breakdown if present
                                sev = summary.get('severity_breakdown') or {}
                                if sev:
                                    task_db.severity_breakdown = json.dumps(sev)
                        except Exception as e:
                            self._log("Failed to store analysis results for task %s: %s", task_db.task_id, e, level='warning')
                    
                    try:
                        if task_db.started_at and task_db.completed_at:
                            # Ensure both timestamps are timezone-aware before subtraction
                            start = task_db.started_at if task_db.started_at.tzinfo else task_db.started_at.replace(tzinfo=timezone.utc)
                            end = task_db.completed_at if task_db.completed_at.tzinfo else task_db.completed_at.replace(tzinfo=timezone.utc)
                            task_db.actual_duration = (end - start).total_seconds()
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
                    self._log("process_once completed task %s progress=%s", task_db.task_id, task_db.progress_percentage, level='debug')
                    transitioned += 1
            except Exception as e:  # pragma: no cover
                self._log("process_once error: %s", e, level='error')
        return transitioned

    def _setup_thread_logging(self) -> logging.Logger:
        """Set up logging for the daemon thread with explicit handler configuration.
        
        This ensures that logs from the daemon thread are properly written to the
        log file by forcing immediate flush and using the same handlers as the main thread.
        """
        thread_logger = logging.getLogger("ThesisApp.task_executor_thread")
        thread_logger.setLevel(logging.INFO)
        
        # Get the root logger's handlers (configured in logging_config.py)
        root_logger = logging.getLogger()
        
        # Copy all handlers from root logger to ensure thread logs go to same destinations
        for handler in root_logger.handlers:
            if handler not in thread_logger.handlers:
                thread_logger.addHandler(handler)
        
        # Prevent propagation to avoid duplicate logs
        thread_logger.propagate = False
        
        return thread_logger
    
    def _log(self, msg: str, *args, level: str = 'info', exc_info: bool = False):
        """Thread-safe logging helper that forces immediate flush.
        
        Args:
            msg: Log message (can contain %s placeholders)
            *args: Arguments for string formatting
            level: Log level ('info', 'debug', 'warning', 'error')
            exc_info: Whether to include exception info in log
        """
        if self._thread_logger:
            log_method = getattr(self._thread_logger, level)
            log_method(msg, *args, exc_info=exc_info)
            # Force flush to ensure logs are written immediately
            for handler in self._thread_logger.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass
        else:
            # Fallback to module logger if thread logger not set up
            log_method = getattr(logger, level)
            log_method(msg, *args, exc_info=exc_info)


# Global singleton style helper (mirrors other services)
task_execution_service: Optional[TaskExecutionService] = None


def init_task_execution_service(poll_interval: float | None = None, app=None) -> TaskExecutionService:
    global task_execution_service
    if task_execution_service is not None:
        return task_execution_service
    from flask import current_app
    app_obj = app or (current_app._get_current_object() if current_app else None)  # type: ignore[attr-defined]
    interval = poll_interval or (0.5 if (app_obj and app_obj.config.get("TESTING")) else 5.0)
    svc = TaskExecutionService(poll_interval=interval, app=app_obj, max_workers=4)
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
