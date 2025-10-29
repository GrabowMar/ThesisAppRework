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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List

from app.utils.logging_config import get_logger
from app.config.config_manager import get_config
from app.extensions import db, get_components
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.services.result_summary_utils import summarise_findings

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
                logger.warning(
                    f"Service {service_name} timed out after {self._service_timeout}s - continuing with other services"
                )
                return {
                    'status': 'timeout',
                    'error': f'Service execution timed out after {self._service_timeout} seconds',
                    'payload': {}
                }
            
            if result_container['error']:
                logger.error(f"Service {service_name} failed: {result_container['error']}")
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
                        # No pending tasks - check for running tasks with subtasks (parallel execution polling)
                        self._poll_running_tasks_with_subtasks()
                        time.sleep(self.poll_interval)
                        continue

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
                        logger.info("Task %s started", task_db.task_id)

                        # Execute real analysis instead of simulation
                        try:
                            result = self._execute_real_analysis(task_db)
                            
                            # Handle parallel execution (status='running' means Celery took over)
                            if result.get('status') == 'running':
                                logger.info(f"Task {task_db.task_id} delegated to Celery workers, will poll for completion")
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
                                
                                logger.info("Saved analysis results for task %s with %d issues", task_db.task_id, task_db.issues_found or 0)
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
                            logger.error("Analysis execution failed for task %s: %s", task_db.task_id, e)
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
                                        logger.info(f"Wrote result files to disk for task {task_db.task_id}: {written_path}")
                                    else:
                                        logger.warning(f"Result file write returned None for task {task_db.task_id} - check logs for details")
                                except Exception as write_err:
                                    logger.warning(f"Failed to write result files to disk for task {task_db.task_id}: {write_err}")
                            except Exception as e:
                                logger.warning("Failed to store analysis results for task %s: %s", task_db.task_id, e)
                        
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
            analysis_type = task.task_name
            
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
            if explicit_unified_flag and not multi_service:
                logger.debug(
                    "Unified flag present but only one service (%s); treating as single-engine run.",
                    list(meta_tools_by_service.keys())
                )

            try:
                logger.debug(
                    "Task %s metadata tool snapshot: unified=%s selected_ids=%s selected_names=%s tools_by_service_keys=%s",
                    getattr(task, 'task_id', 'unknown'),
                    is_unified_analysis,
                    meta.get('selected_tools') or meta.get('custom_options', {}).get('selected_tools'),
                    selected_tools,
                    list((meta.get('tools_by_service') or {}).keys()) if isinstance(meta.get('tools_by_service'), dict) else None
                )
            except Exception:
                pass

            logger.debug(
                "Unified decision for task %s => unified=%s explicit_flag=%s multi_service=%s services=%s tool_count=%s",
                getattr(task, 'task_id', 'unknown'),
                is_unified_analysis,
                explicit_unified_flag,
                multi_service,
                list(meta_tools_by_service.keys()),
                len(selected_tools) if isinstance(selected_tools, list) else 'n/a'
            )
            
            if is_unified_analysis:
                logger.info(
                    "Executing UNIFIED analysis (all tool types) for task %s",
                    getattr(task, "task_id", "unknown")
                )
                # Handle unified analysis with multiple engines
                return self._execute_unified_analysis(task)
            else:
                # Regular single-engine analysis
                engine_name = task.task_name
                # Defensive correction: if metadata shows ONLY ai-analyzer tools but engine not 'ai', fix it.
                try:
                    only_services = list(meta_tools_by_service.keys())
                    if only_services and len(only_services) == 1 and only_services[0] == 'ai-analyzer' and engine_name != 'ai':
                        logger.warning(
                            "Task %s: correcting engine '%s' -> 'ai' because only AI tools selected (%s)",
                            getattr(task, 'task_id', 'unknown'), engine_name, selected_tools
                        )
                        engine_name = 'ai'
                except Exception:
                    pass
                
                engine = get_engine(engine_name)
                
                logger.info(
                    "Executing %s analysis for task %s",
                    engine_name,
                    getattr(task, "task_id", "unknown")
                )
            
            # Update progress
            task.progress_percentage = 40.0
            db.session.commit()
            
            # Resolve selected tools from task metadata (where routes store custom_options)
            resolved_tools = None
            try:
                # Routes store selected tools in metadata['custom_options']
                meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
                if not isinstance(meta, dict):
                    meta = {}
                
                # Extract custom_options from metadata
                custom_options = meta.get('custom_options', {})
                if not isinstance(custom_options, dict):
                    custom_options = {}
                
                # Get selected tools from custom_options
                cand = custom_options.get('selected_tools')
                
                # Fallback: check direct metadata keys
                if not isinstance(cand, list):
                    cand = meta.get('selected_tools')
            except Exception:
                cand = None
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
                        # Primary: use unified registry deterministic IDs
                        from app.engines.unified_registry import get_unified_tool_registry
                        unified = get_unified_tool_registry()
                        names: list[str] = []
                        for tid in id_list:
                            tool_name = unified.id_to_name(tid)
                            if tool_name:
                                names.append(tool_name)
                        # Transitional fallback: if no names resolved (older tasks saved using container order)
                        if not names:
                            try:
                                from app.engines.container_tool_registry import get_container_tool_registry
                                c_registry = get_container_tool_registry()
                                all_tools = c_registry.get_all_tools()
                                fallback_map = {idx + 1: tname for idx, (tname, _tool) in enumerate(all_tools.items())}
                                for tid in id_list:
                                    tname = fallback_map.get(tid)
                                    if tname and tname not in names:
                                        names.append(tname)
                            except Exception:
                                pass
                        resolved_tools = names or None
                    except Exception as e:
                        logger.warning(f"Failed to resolve tool IDs to names: {e}")
                        resolved_tools = None
                elif cand and all(isinstance(x, str) for x in cand):
                    resolved_tools = cand  # already names
                elif cand == []:
                    resolved_tools = []  # explicit empty (should rarely happen due to form validation)

            # Apply defaults only when no explicit selection present
            if resolved_tools is None:
                config = get_config()
                resolved_tools = config.get_default_tools(engine_name)

            # If engine_name is 'ai' but resolved_tools accidentally contains non-AI legacy defaults, restrict to requirements-scanner.
            if engine_name == 'ai':
                try:
                    from app.engines.unified_registry import get_unified_tool_registry
                    unified = get_unified_tool_registry()
                    ai_tools = [t for t in unified.by_container('ai-analyzer')]
                    # Filter to AI tools only (after alias resolution)
                    resolved_tools = [t for t in (resolved_tools or []) if t in ai_tools] or ['requirements-scanner']
                    if any(t not in ai_tools for t in (resolved_tools or [])):
                        logger.debug(
                            "Task %s: filtered non-AI tools from AI run (unified) -> %s", getattr(task, 'task_id', 'unknown'), resolved_tools
                        )
                except Exception as e:
                    logger.warning(f"Failed AI tool filtering (unified): {e}")

            # Debug: Log the engine call parameters
            try:
                logger.info(
                    "Task %s calling engine.run with model_slug=%s, app_number=%s, tools=%s",
                    getattr(task, "task_id", "unknown"),
                    task.target_model,
                    task.target_app_number,
                    resolved_tools
                )
            except Exception:
                pass

            # Execute the analysis with resolved tools (with persistence enabled)
            result = engine.run(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                tools=resolved_tools,
                persist=True  # Enable result file writes
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
                'payload': self._wrap_single_engine_payload(task, engine_name, result.payload),
                'error': result.error
            }
            
        except Exception as e:
            logger.error(
                "Failed to execute analysis for task %s: %s",
                getattr(task, "task_id", "unknown"),
                e,
                exc_info=True  # Include full traceback in logs
            )
            
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
        """Execute unified analysis using ALL engine types across all containers."""
        try:
            logger.info("Starting unified analysis for task %s", getattr(task, "task_id", "unknown"))
            
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
            
            logger.info("Forcing execution of ALL tools across ALL services: %s", tools_by_service)
            
            # Map service names to engine names
            service_to_engine = {
                'static-analyzer': 'security',
                'dynamic-analyzer': 'dynamic', 
                'performance-tester': 'performance',
                'ai-analyzer': 'ai',  # Route AI tools through AI engine
            }
            
            # Execute analysis for each service and aggregate results
            from app.services.analysis_engines import get_engine
            all_results = {}
            combined_tools_requested = []
            combined_tools_successful = 0
            combined_tools_failed = 0
            combined_tool_results: Dict[str, Dict[str, Any]] = {}
            all_findings: List[Dict[str, Any]] = []
            service_summaries: List[Dict[str, Any]] = []
            
            task.progress_percentage = 20.0
            db.session.commit()
            
            total_services = len(tools_by_service)
            progress_per_service = 60.0 / total_services if total_services > 0 else 60.0
            
            # Get subtasks if this is a main task
            subtasks_by_service = {}
            if hasattr(task, 'subtasks') and task.subtasks:
                for subtask in task.subtasks:
                    if subtask.service_name:
                        subtasks_by_service[subtask.service_name] = subtask
                logger.info(f"Found {len(subtasks_by_service)} subtasks for main task")
            
            # Map service names to Celery subtask functions
            service_to_celery_task = {
                'static-analyzer': 'app.tasks.run_static_analyzer_subtask',
                'dynamic-analyzer': 'app.tasks.run_dynamic_analyzer_subtask',
                'performance-tester': 'app.tasks.run_performance_tester_subtask',
                'ai-analyzer': 'app.tasks.run_ai_analyzer_subtask',
            }
            
            # Prepare parallel task invocations
            from celery import group, chord
            from app.tasks import (
                run_analyzer_subtask,
                aggregate_subtask_results
            )
            
            parallel_tasks = []
            for service_name, tool_ids in tools_by_service.items():
                # Get subtask DB record
                subtask = subtasks_by_service.get(service_name)
                if not subtask:
                    logger.warning(f"No subtask found for service {service_name}, skipping")
                    continue
                
                # Resolve tool IDs to names
                service_tool_names = self._resolve_tool_ids_to_names(tool_ids)
                logger.info(f"Queuing parallel subtask for {service_name} with tools: {service_tool_names}")
                
                # Create Celery task signature using the generic subtask runner
                task_sig = run_analyzer_subtask.s(subtask.id, task.target_model, task.target_app_number, service_tool_names, service_name)
                
                parallel_tasks.append(task_sig)
            
            # Execute all subtasks in parallel using Celery chord (PARALLEL ONLY - NO FALLBACK)
            if not parallel_tasks:
                error_msg = f"No parallel tasks created for unified analysis of task {task.task_id}"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            logger.info(f"Launching {len(parallel_tasks)} subtasks in parallel for task {task.task_id}")
            
            # Pre-flight checks: Celery availability
            if not self._is_celery_available():
                raise RuntimeError(
                    "Celery workers not available - cannot execute parallel analysis. "
                    "Start workers with: celery -A app.tasks worker --loglevel=info"
                )
            
            # Pre-flight checks: Analyzer containers
            container_services = list(tools_by_service.keys())
            if not self._validate_analyzer_containers(container_services):
                raise RuntimeError(
                    f"Analyzer containers not healthy: {container_services}. "
                    "Start containers with: python analyzer/analyzer_manager.py start"
                )
            
            # Create Celery chord: parallel group + aggregation callback
            try:
                job = chord(parallel_tasks)(aggregate_subtask_results.s(task.task_id))
                logger.info(
                    f"✅ Celery chord created for task {task.task_id} with {len(parallel_tasks)} parallel subtasks. "
                    f"Services: {', '.join(tools_by_service.keys())}"
                )
            except Exception as chord_error:
                logger.error(f"Failed to create Celery chord: {chord_error}")
                raise RuntimeError(f"Celery chord creation failed: {chord_error}") from chord_error
            
            # Don't block - let Celery workers handle it asynchronously
            # The main task execution loop (_run_loop) will poll subtask statuses
            logger.info(f"Task {task.task_id} delegated to Celery workers - returning to allow async execution")
            
            # Mark main task as RUNNING and return immediately
            task.status = AnalysisStatus.RUNNING
            task.progress_percentage = 30.0  # Subtasks started
            db.session.commit()
            
            return {
                'status': 'running',
                'engine': 'unified',
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'payload': {
                    'message': 'Subtasks executing in parallel via Celery',
                    'services': list(tools_by_service.keys()),
                    'subtask_count': len(parallel_tasks)
                },
                'celery_job_id': str(job.id) if hasattr(job, 'id') else None
            }
            
        except Exception as e:
            logger.error(f"Unified analysis failed for task {task.task_id}: {e}")
            # Mark all subtasks as failed
            if subtasks_by_service:
                for subtask in subtasks_by_service.values():
                    if subtask.status in (AnalysisStatus.PENDING, AnalysisStatus.RUNNING):
                        subtask.status = AnalysisStatus.FAILED
                        subtask.error_message = str(e)
                        subtask.completed_at = datetime.now(timezone.utc)
                db.session.commit()
            raise

    def _execute_unified_analysis_sequential_fallback_DEPRECATED(self, task: AnalysisTask, tools_by_service: Dict, subtasks_by_service: Dict) -> dict:
        """DEPRECATED: Sequential fallback path - kept for reference but should not be used.
        
        This method represents the old sequential execution model where each service
        was executed one after another, blocking the entire analysis.
        
        The new parallel execution model (Celery chord) should ALWAYS be used instead.
        This method is preserved only as documentation of the old approach.
        """
        logger.warning("DEPRECATED: Sequential fallback should not be used - parallel execution required")
        
        # Map service names to engine names
        service_to_engine = {
            'static-analyzer': 'security',
            'dynamic-analyzer': 'dynamic', 
            'performance-tester': 'performance',
            'ai-analyzer': 'ai',
        }
        
        from app.services.analysis_engines import get_engine
        all_results = {}
        combined_tool_results: Dict[str, Dict[str, Any]] = {}
        all_findings: List[Dict[str, Any]] = []
        
        # Sequential loop (OLD WAY - DO NOT USE)
        logger.warning(f"Executing subtasks SEQUENTIALLY for task {task.task_id} - this will be slow!")
        
        # This entire sequential loop has been REMOVED in favor of parallel Celery execution
        # The code below is kept for reference only
        raise NotImplementedError(
            "Sequential fallback is deprecated. Use parallel Celery execution instead. "
            "Ensure Celery workers and analyzer containers are running."
        )

    def _wrap_single_engine_payload(self, task: AnalysisTask, engine_name: str, raw_payload: dict | None) -> dict:
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
        # Build raw outputs from tool results
        raw_outputs_block = {}
        for tname, meta in tools.items():
            if isinstance(meta, dict):
                ro = {}
                for k in ('raw_output','stdout','stderr','command_line','exit_code','error','duration_seconds'):
                    if k in meta and meta[k] not in (None, ''):
                        ro[k] = meta[k]
                if ro:
                    raw_outputs_block[tname] = ro
        # Compose
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
            'raw_outputs': raw_outputs_block,
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
    
    def _group_tools_by_service(self, tool_names: list[str]) -> dict[str, list[int]]:
        """Group tool names by their service and return with tool IDs."""
        from app.engines.unified_registry import get_unified_tool_registry
        unified = get_unified_tool_registry()
        detailed = unified.list_tools_detailed()
        name_to_service: dict[str, str] = {}
        name_to_id: dict[str, int] = {}
        for info in detailed:
            name_val = info.get('name')
            container_val = info.get('container')
            if not isinstance(name_val, str) or not isinstance(container_val, str):
                continue
            if container_val == 'local':
                continue
            tid = unified.tool_id(name_val)
            if tid is None:
                continue
            name_to_service[name_val] = container_val
            name_to_id[name_val] = tid
        
        # Group by service
        tools_by_service = {}
        for tool_name in tool_names:
            service = name_to_service.get(tool_name)
            tool_id = name_to_id.get(tool_name)
            if service and tool_id:
                tools_by_service.setdefault(service, []).append(tool_id)
        
        return tools_by_service
    
    def _is_celery_available(self) -> bool:
        """Check if Celery broker and workers are available for parallel execution."""
        try:
            from app.extensions import get_celery
            celery = get_celery()
            
            if celery is None:
                logger.warning("Celery instance not initialized")
                return False
            
            # Check broker connection
            try:
                conn = celery.connection()
                conn.ensure_connection(max_retries=2, timeout=2.0)
                conn.release()
            except Exception as e:
                logger.warning(f"Celery broker not reachable: {e}")
                return False
            
            # Check for active workers
            try:
                inspect = celery.control.inspect(timeout=2.0)
                active = inspect.active()
                if not active:
                    logger.warning("No active Celery workers found")
                    return False
                logger.info(f"Found {len(active)} active Celery workers")
            except Exception as e:
                logger.warning(f"Cannot inspect Celery workers: {e}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Celery not available: {e}")
            return False
    
    def _validate_analyzer_containers(self, service_names: list[str]) -> bool:
        """Validate that all required analyzer containers are healthy."""
        try:
            from app.services.analyzer_integration import health_monitor
            
            if health_monitor is None:
                logger.warning("Health monitor not available")
                return False
            
            # Get cached health status
            health_status = health_monitor.get_cached_health_status()
            
            # If cache is empty, assume containers are healthy (they'll fail during execution if not)
            if not health_status:
                logger.info("Health status cache empty - assuming containers are healthy")
                return True
            
            unhealthy = []
            for service_name in service_names:
                service_health = health_status.get(service_name, {})
                status = service_health.get('status', 'unknown')
                if status != 'healthy':
                    unhealthy.append(service_name)
            
            if unhealthy:
                logger.error(f"Analyzer containers not healthy: {unhealthy}")
                return False
            
            logger.info(f"All analyzer containers are healthy: {service_names}")
            return True
        except Exception as e:
            logger.error(f"Failed to validate analyzer containers: {e}")
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
            nested = results_section.get('tool_results')
            if isinstance(nested, dict):
                candidates.append(nested)

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
                        logger.error("Analysis execution failed for task %s: %s", task_db.task_id, e)
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
                            logger.warning("Failed to store analysis results for task %s: %s", task_db.task_id, e)
                    
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
                    logger.debug("process_once completed task %s progress=%s", task_db.task_id, task_db.progress_percentage)
                    transitioned += 1
            except Exception as e:  # pragma: no cover
                logger.error("process_once error: %s", e)
        return transitioned

    def _poll_running_tasks_with_subtasks(self):
        """Poll running main tasks to check if their subtasks have completed."""
        try:
            # Find all main tasks that are RUNNING and have subtasks
            running_main_tasks = AnalysisTask.query.filter(
                AnalysisTask.status == AnalysisStatus.RUNNING,
                AnalysisTask.is_main_task.is_(True)
            ).all()
            
            for main_task in running_main_tasks:
                # Check if all subtasks are completed
                subtasks = AnalysisTask.query.filter_by(parent_task_id=main_task.task_id).all()
                
                if not subtasks:
                    continue  # No subtasks, let normal flow handle it
                
                all_completed = all(st.status == AnalysisStatus.COMPLETED for st in subtasks)
                any_failed = any(st.status == AnalysisStatus.FAILED for st in subtasks)
                
                if all_completed or any_failed:
                    # All subtasks done - aggregate results
                    logger.info(f"All subtasks completed for main task {main_task.task_id}, aggregating results")
                    
                    try:
                        # Collect subtask results from DB
                        all_results = {}
                        combined_findings = []
                        
                        for subtask in subtasks:
                            if subtask.status == AnalysisStatus.COMPLETED:
                                result_summary = subtask.get_result_summary() if hasattr(subtask, 'get_result_summary') else {}
                                if isinstance(result_summary, dict):
                                    service_name = subtask.service_name or f'service_{subtask.id}'
                                    all_results[service_name] = result_summary
                                    
                                    findings = result_summary.get('findings', [])
                                    if isinstance(findings, list):
                                        combined_findings.extend(findings)
                        
                        # Build unified payload
                        unified_payload = {
                            'task': {'task_id': main_task.task_id},
                            'summary': {
                                'total_findings': len(combined_findings),
                                'services_executed': len(all_results),
                                'status': 'completed' if not any_failed else 'partial'
                            },
                            'services': all_results,
                            'findings': combined_findings,
                            'metadata': {
                                'unified_analysis': True,
                                'generated_at': datetime.now(timezone.utc).isoformat()
                            }
                        }
                        
                        # Update main task
                        main_task.status = AnalysisStatus.COMPLETED if not any_failed else AnalysisStatus.FAILED
                        main_task.completed_at = datetime.now(timezone.utc)
                        main_task.progress_percentage = 100.0
                        if main_task.started_at:
                            # Ensure both timestamps are timezone-aware before subtraction
                            start = main_task.started_at if main_task.started_at.tzinfo else main_task.started_at.replace(tzinfo=timezone.utc)
                            end = main_task.completed_at if main_task.completed_at.tzinfo else main_task.completed_at.replace(tzinfo=timezone.utc)
                            main_task.actual_duration = (end - start).total_seconds()
                        main_task.set_result_summary(unified_payload)
                        
                        db.session.commit()
                        
                        # Emit completion event
                        try:
                            from app.realtime.task_events import emit_task_event
                            emit_task_event(
                                "task.completed",
                                {
                                    "task_id": main_task.task_id,
                                    "id": main_task.id,
                                    "status": main_task.status.value if main_task.status else None,
                                    "progress_percentage": main_task.progress_percentage,
                                    "completed_at": main_task.completed_at.isoformat() if main_task.completed_at else None,
                                    "actual_duration": main_task.actual_duration,
                                },
                            )
                        except Exception:
                            pass
                        
                        logger.info(f"Main task {main_task.task_id} marked as completed")
                    
                    except Exception as e:
                        logger.error(f"Failed to aggregate results for main task {main_task.task_id}: {e}")
                        main_task.status = AnalysisStatus.FAILED
                        main_task.error_message = f"Result aggregation failed: {e}"
                        db.session.commit()
                else:
                    # Emit progress event for subtasks
                    completed_count = sum(1 for st in subtasks if st.status == AnalysisStatus.COMPLETED)
                    progress = (completed_count / len(subtasks)) * 100.0
                    
                    if abs(main_task.progress_percentage - progress) > 1.0:  # Only update if changed significantly
                        main_task.progress_percentage = progress
                        db.session.commit()
                        
                        try:
                            from app.realtime.task_events import emit_task_event
                            emit_task_event(
                                "task.updated",
                                {
                                    "task_id": main_task.task_id,
                                    "id": main_task.id,
                                    "status": main_task.status.value if main_task.status else None,
                                    "progress_percentage": progress,
                                },
                            )
                        except Exception:
                            pass
        
        except Exception as e:
            logger.error(f"Error polling running tasks with subtasks: {e}")


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
