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
from app.services.service_locator import ServiceLocator

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
                            
                            # Engine returns 'completed' on success, 'partial' for mixed results, or 'failed'/'error' otherwise
                            # Partial success (some services succeeded) should be treated as success since results are generated
                            status = str(result.get('status', '')).lower()
                            success = status in ('success', 'completed', 'partial')
                            is_partial = status == 'partial'
                            
                            # Save analysis results to database via UnifiedResultService
                            if success and result.get('payload'):
                                try:
                                    unified_service = ServiceLocator.get_unified_result_service()
                                    unified_service.store_analysis_results(
                                        task_id=task_db.task_id,
                                        payload=result['payload'],
                                        model_slug=task_db.target_model,
                                        app_number=task_db.target_app_number
                                    )
                                    self._log("Saved analysis results via UnifiedResultService for task %s", task_db.task_id)
                                except Exception as e:
                                    self._log("Failed to store results via UnifiedResultService: %s", e, level='error')
                                    # Fallback to basic DB update if service fails
                                    task_db.set_result_summary(result['payload'])
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
                        if is_partial:
                            task_db.status = AnalysisStatus.PARTIAL_SUCCESS
                        else:
                            task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                        task_db.progress_percentage = 100.0
                        task_db.completed_at = datetime.now(timezone.utc)
                        
                        # Store analysis results if available (merge with existing metadata)
                        # Note: UnifiedResultService now handles result storage.
                        # Legacy metadata merging removed to prevent duplication.
                        
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
        """Execute real analysis using analyzer_manager directly."""
        try:
            # Try to dispatch to Celery first if available
            try:
                # Check if we should use Celery (env var or config)
                use_celery = os.environ.get('USE_CELERY_ANALYSIS', 'true').lower() == 'true'
                
                if use_celery:
                    from app.tasks import execute_analysis
                    self._log(f"[EXEC] Dispatching task {task.task_id} to Celery worker")
                    # Dispatch task
                    execute_analysis.delay(task.id)
                    return {'status': 'running', 'payload': {'message': 'Dispatched to Celery'}}
            except (ImportError, Exception) as e:
                self._log(f"[EXEC] Celery dispatch failed: {e}, falling back to local execution", level='warning')

            # Get the analysis type (string)
            analysis_type = task.task_name
            
            self._log(
                "[EXEC] Starting analysis execution via analyzer_manager for task %s: type=%s, model=%s, app=%s",
                task.task_id, analysis_type, task.target_model, task.target_app_number
            )
            
            # Update progress to indicate analysis starting
            task.progress_percentage = 20.0
            db.session.commit()
            
            # Import analyzer wrapper
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            wrapper = get_analyzer_wrapper()
            
            # Extract tool names from metadata if available
            meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            custom_options = meta.get('custom_options', {})
            tool_names = custom_options.get('tools') or custom_options.get('selected_tool_names') or []
            
            # DEBUG: Log full metadata
            self._log(
                "[DEBUG] Task %s metadata: custom_options=%s, tools=%s",
                task.task_id, custom_options, tool_names
            )
            
            # Determine analysis type from task_name or infer from tools
            analysis_type_map = {
                'security': 'security',
                'static': 'static',
                'dynamic': 'dynamic',
                'performance': 'performance',
                'ai': 'ai',
                'comprehensive': 'comprehensive'
            }
            
            analysis_method = analysis_type_map.get(task.task_name, 'comprehensive')
            
            self._log(
                "[EXEC] Task %s: Running %s analysis via analyzer_manager (tools=%s)",
                task.task_id, analysis_method, tool_names
            )
            
            # Update progress
            task.progress_percentage = 40.0
            db.session.commit()
            
            # Generate task name for results folder
            task_name = task.task_id  # Use task_id directly instead of prepending "task_"
            
            # Run the appropriate analysis method based on analysis_method
            if analysis_method == 'comprehensive':
                # Use comprehensive analysis because it saves results incrementally to disk,
                # avoiding WebSocket payload size issues with large SARIF documents.
                # When tools are specified, pass them to run only those tools; otherwise run all.
                if tool_names:
                    self._log(
                        "[EXEC] Task %s: Running comprehensive analysis with tool filter: %s",
                        task.task_id, tool_names
                    )
                else:
                    self._log(
                        "[EXEC] Task %s: Running comprehensive analysis with all tools",
                        task.task_id
                    )
                
                analyzer_result = wrapper.run_comprehensive_analysis(
                    model_slug=task.target_model,
                    app_number=task.target_app_number,
                    task_name=task_name,
                    tools=tool_names if tool_names else None
                )
            elif analysis_method == 'security':
                analyzer_result = {
                    'security': wrapper.run_security_analysis(
                        model_slug=task.target_model,
                        app_number=task.target_app_number,
                        tools=tool_names if tool_names else None
                    )
                }
            elif analysis_method == 'static':
                analyzer_result = {
                    'static': wrapper.run_static_analysis(
                        model_slug=task.target_model,
                        app_number=task.target_app_number,
                        tools=tool_names if tool_names else None
                    )
                }
            elif analysis_method == 'dynamic':
                analyzer_result = {
                    'dynamic': wrapper.run_dynamic_analysis(
                        model_slug=task.target_model,
                        app_number=task.target_app_number,
                        tools=tool_names if tool_names else None
                    )
                }
            elif analysis_method == 'performance':
                analyzer_result = {
                    'performance': wrapper.run_performance_test(
                        model_slug=task.target_model,
                        app_number=task.target_app_number,
                        tools=tool_names if tool_names else None
                    )
                }
            elif analysis_method == 'ai':
                analyzer_result = {
                    'ai': wrapper.run_ai_analysis(
                        model_slug=task.target_model,
                        app_number=task.target_app_number,
                        tools=tool_names if tool_names else None
                    )
                }
            else:
                raise ValueError(f"Unknown analysis type: {analysis_method}")
            
            # CRITICAL FIX: Validate analyzer_result structure before processing
            if not isinstance(analyzer_result, dict):
                raise ValueError(f"Analyzer returned invalid type: {type(analyzer_result).__name__}")
            
            # Check for required top-level keys
            if 'metadata' not in analyzer_result and 'results' not in analyzer_result:
                # If neither key exists, this might be raw service results - check for service keys
                has_service_keys = any(k in analyzer_result for k in ['static', 'dynamic', 'performance', 'ai', 'security'])
                if not has_service_keys:
                    logger.warning(f"Analyzer result missing expected structure. Keys: {list(analyzer_result.keys())}")
            
            self._log(
                "[EXEC] Task %s: analyzer_manager completed with results for services: %s",
                task.task_id, list(analyzer_result.keys())
            )
            
            # Extract metadata about saved results
            meta = analyzer_result.get('_meta', {})
            results_path = meta.get('results_path', f"results/{task.target_model}/app{task.target_app_number}/{task_name}")
            
            # Update progress
            task.progress_percentage = 80.0
            db.session.commit()
            
            # analyzer_result can have TWO formats:
            # 1. Direct service response: {static: {...}, dynamic: {...}, _meta: {...}}
            # 2. Fallback wrapper: {metadata: {...}, results: {services: {static: {...}, dynamic: {...}}}}
            
            # CRITICAL FIX: Extract services from either format
            services_to_process = {}
            
            # Check if this is the fallback wrapper format
            if 'results' in analyzer_result and isinstance(analyzer_result['results'], dict):
                # Nested format from fallback path
                services_to_process = analyzer_result['results'].get('services', {})
                self._log("[DEBUG] Using nested services structure from fallback format")
            else:
                # Direct format from successful file read
                services_to_process = {k: v for k, v in analyzer_result.items() if k not in ('_meta', 'metadata', 'results')}
                self._log("[DEBUG] Using direct services structure from file read")
            
            # Count statistics for summary
            total_findings = 0
            all_services_status = []
            
            for service_name, service_result in services_to_process.items():
                if not isinstance(service_result, dict):
                    continue
                
                status = service_result.get('status', 'unknown')
                all_services_status.append(status)
                
                # Count findings from analysis section if available
                if isinstance(service_result.get('analysis'), dict):
                    summary = service_result['analysis'].get('summary', {})
                    if isinstance(summary, dict):
                        # Support both field names: total_findings and total_issues_found
                        findings = summary.get('total_findings') or summary.get('total_issues_found', 0)
                        total_findings += findings
                        self._log(f"[DEBUG] Service {service_name} has {findings} findings")
            
            self._log(f"[DEBUG] Total findings across all services: {total_findings}")
            
            # Determine overall status
            # CRITICAL FIX: Default to 'partial' when status list is empty but findings exist
            if not all_services_status:
                # Empty status list - this happens with fallback format
                # If we have findings, assume partial success; otherwise failed
                overall_status = 'partial' if total_findings > 0 else 'failed'
                self._log(f"[DEBUG] Empty status list, defaulting to '{overall_status}' (findings={total_findings})")
            elif all(s == 'success' for s in all_services_status):
                overall_status = 'completed'
            elif any(s == 'success' for s in all_services_status):
                overall_status = 'partial'
            else:
                overall_status = 'failed'
            
            # The payload structure matches analyzer_manager's saved JSON structure:
            # {metadata: {...}, services: {...}, tools: {...}, findings: [...], summary: {...}}
            # We just need to wrap it minimally for task execution context
            wrapped_payload = {
                'analysis_type': analysis_method,
                'task_name': task_name,
                'results_path': results_path,
                'services': services_to_process,  # Use normalized services
                'summary': {
                    'total_findings': total_findings,
                    'services_completed': list(services_to_process.keys()),
                    'overall_status': overall_status
                }
            }
            
            self._log(
                "[EXEC] Task %s: Analysis completed with status=%s, total_findings=%s, results_path=%s",
                task.task_id, overall_status, total_findings, results_path
            )
            
            return {
                'status': overall_status,
                'payload': wrapped_payload,
                'error': None
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
        """Execute unified/comprehensive analysis using analyzer_manager directly."""
        try:
            self._log(
                "[UNIFIED] Starting comprehensive analysis for task %s (model=%s, app=%s)",
                task.task_id, task.target_model, task.target_app_number
            )
            
            # For unified analysis, always run comprehensive
            from app.services.analyzer_manager_wrapper import get_analyzer_wrapper
            wrapper = get_analyzer_wrapper()
            
            task_name = task.task_id  # Use task_id directly (already has "task_" prefix)
            
            self._log(
                "[UNIFIED] Task %s: Running comprehensive analysis via analyzer_manager",
                task.task_id
            )
            
            # Update task to running
            task.progress_percentage = 30.0
            db.session.commit()
            
            # Run comprehensive analysis
            analyzer_result = wrapper.run_comprehensive_analysis(
                model_slug=task.target_model,
                app_number=task.target_app_number,
                task_name=task_name
            )
            
            self._log(
                "[UNIFIED] Task %s: Comprehensive analysis completed with services: %s",
                task.task_id, list(analyzer_result.keys())
            )
            
            # Transform results
            total_findings = 0
            all_services_status = []
            
            for service_name, service_result in analyzer_result.items():
                status = service_result.get('status', 'unknown')
                all_services_status.append(status)
                
                # Count findings if available
                if isinstance(service_result.get('analysis'), dict):
                    summary = service_result['analysis'].get('summary', {})
                    total_findings += summary.get('total_findings', 0)
            
            # Determine overall status
            if all(s == 'success' for s in all_services_status):
                overall_status = 'completed'
            elif any(s == 'success' for s in all_services_status):
                overall_status = 'partial'
            else:
                overall_status = 'failed'
            
            wrapped_payload = {
                'summary': {
                    'total_findings': total_findings,
                    'services': list(analyzer_result.keys()),
                    'analysis_type': 'comprehensive'
                },
                'services': analyzer_result,
                'task_name': task_name,
                'results_path': f"results/{task.target_model}/app{task.target_app_number}/{task_name}"
            }
            
            return {
                'status': overall_status,
                'payload': wrapped_payload,
                'error': None
            }
            
        except Exception as e:
            self._log(
                "[UNIFIED] Task %s: EXCEPTION during comprehensive analysis: %s",
                task.task_id, e, exc_info=True
            , level='error')
            raise
    
    def submit_parallel_subtasks(
        self,
        main_task_id: str,
        subtask_ids: List[str]
    ) -> dict:
        """Submit multiple subtasks for parallel execution using Celery (with ThreadPool fallback).
        
        Uses Celery 'chord' primitive: group(subtasks) | aggregate_callback
        
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
            
        # Try to use Celery first
        try:
            from celery import chord
            from app.tasks import execute_subtask, aggregate_results
            
            header = []
            subtask_info = []
            
            for subtask in subtasks:
                service_name = subtask.service_name
                metadata = subtask.get_metadata() if hasattr(subtask, 'get_metadata') else {}
                custom_options = metadata.get('custom_options', {})
                tool_names = custom_options.get('tool_names', [])
                
                if not tool_names:
                    self._log(f"No tools found for subtask {subtask.task_id} ({service_name}), skipping", level='warning')
                    continue
                
                # Create Celery signature for subtask
                sig = execute_subtask.s(
                    subtask.id,
                    main_task.target_model,
                    main_task.target_app_number,
                    tool_names,
                    service_name
                )
                header.append(sig)
                subtask_info.append(service_name)
            
            if not header:
                raise RuntimeError("No valid subtasks to submit")
                
            # Create callback signature
            callback = aggregate_results.s(main_task_id)
            
            # Execute chord
            self._log(f"Dispatching Celery chord for task {main_task_id} with {len(header)} subtasks")
            chord(header)(callback)
            
            # Mark main task as RUNNING
            main_task.status = AnalysisStatus.RUNNING
            main_task.progress_percentage = 30.0
            db.session.commit()
            
            return {
                'status': 'running',
                'engine': 'celery',
                'model_slug': main_task.target_model,
                'app_number': main_task.target_app_number,
                'payload': {
                    'message': 'Subtasks executing in parallel via Celery',
                    'services': subtask_info,
                    'subtask_count': len(header)
                }
            }
            
        except (ImportError, OSError) as e:
            self._log(f"Celery dispatch failed ({e}), falling back to ThreadPoolExecutor", level='warning')
            
            # Fallback to ThreadPoolExecutor implementation
            futures = []
            subtask_info = []
            
            for subtask in subtasks:
                service_name = subtask.service_name
                
                # Get tool names from subtask metadata
                metadata = subtask.get_metadata() if hasattr(subtask, 'get_metadata') else {}
                custom_options = metadata.get('custom_options', {})
                tool_names = custom_options.get('tool_names', [])
                
                if not tool_names:
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
                
                # Store result and mark complete (partial is still a success - results were generated)
                status = str(result.get('status', '')).lower()
                success = status in ('success', 'completed', 'ok', 'partial')
                is_partial = status == 'partial'
                subtask.status = AnalysisStatus.PARTIAL_SUCCESS if is_partial else (AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED)
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
                
                # Update main task status and duration
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
                
                # Store results via UnifiedResultService (handles DB and Filesystem)
                try:
                    unified_service = ServiceLocator.get_unified_result_service()
                    unified_service.store_analysis_results(
                        task_id=main_task_id,
                        payload=unified_payload,
                        model_slug=main_task.target_model,
                        app_number=main_task.target_app_number
                    )
                    self._log(f"[AGGREGATE] Stored unified results for {main_task_id}")
                except Exception as e:
                    self._log(f"[AGGREGATE] Failed to store unified results: {e}", level='error')
                    # Fallback DB update
                    main_task.set_result_summary(unified_payload)
                    db.session.commit()
                
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
    
    def _extract_sarif_to_files(self, services: Dict[str, Any], sarif_dir: Path) -> Dict[str, Any]:
        """Extract SARIF data from service results to separate files.
        
        Returns a copy of services with SARIF data replaced by file references.
        Matches analyzer_manager.py implementation.
        """
        services_copy = {}
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                services_copy[service_name] = service_data
                continue
            
            service_copy = dict(service_data)
            
            # Handle different service result structures
            # Some services have analysis.tool_results, others have analysis.results
            analysis = service_copy.get('analysis', {})
            if not isinstance(analysis, dict):
                services_copy[service_name] = service_copy
                continue
            
            analysis_copy = dict(analysis)
            
            # Handle tool_results (dynamic, performance)
            if 'tool_results' in analysis_copy and isinstance(analysis_copy['tool_results'], dict):
                tool_results_copy = {}
                for tool_name, tool_data in analysis_copy['tool_results'].items():
                    if not isinstance(tool_data, dict):
                        tool_results_copy[tool_name] = tool_data
                        continue
                    
                    tool_copy = dict(tool_data)
                    if 'sarif' in tool_copy and isinstance(tool_copy['sarif'], dict):
                        sarif_filename = f"{service_name}_{tool_name}.sarif.json"
                        sarif_path = sarif_dir / sarif_filename
                        
                        try:
                            with open(sarif_path, 'w', encoding='utf-8') as f:
                                json.dump(tool_copy['sarif'], f, indent=2, default=str)
                            self._log(f"Extracted SARIF for {tool_name} to {sarif_filename}", level='info')
                            tool_copy['sarif_file'] = f"sarif/{sarif_filename}"
                            del tool_copy['sarif']
                        except Exception as e:
                            self._log(f"Failed to extract SARIF for {tool_name}: {e}", level='error')
                    
                    tool_results_copy[tool_name] = tool_copy
                
                analysis_copy['tool_results'] = tool_results_copy
            
            # Handle nested results structure (static, security)
            if 'results' in analysis_copy and isinstance(analysis_copy['results'], dict):
                results_copy = {}
                for category, category_data in analysis_copy['results'].items():
                    if not isinstance(category_data, dict):
                        results_copy[category] = category_data
                        continue
                    
                    category_copy = {}
                    for tool_name, tool_data in category_data.items():
                        if not isinstance(tool_data, dict):
                            category_copy[tool_name] = tool_data
                            continue
                        
                        tool_copy = dict(tool_data)
                        if 'sarif' in tool_copy and isinstance(tool_copy['sarif'], dict):
                            sarif_filename = f"{service_name}_{category}_{tool_name}.sarif.json"
                            sarif_path = sarif_dir / sarif_filename
                            
                            try:
                                with open(sarif_path, 'w', encoding='utf-8') as f:
                                    json.dump(tool_copy['sarif'], f, indent=2, default=str)
                                self._log(f"Extracted SARIF for {category}/{tool_name} to {sarif_filename}", level='info')
                                tool_copy['sarif_file'] = f"sarif/{sarif_filename}"
                                del tool_copy['sarif']
                            except Exception as e:
                                self._log(f"Failed to extract SARIF for {category}/{tool_name}: {e}", level='error')
                        
                        category_copy[tool_name] = tool_copy
                    
                    results_copy[category] = category_copy
                
                analysis_copy['results'] = results_copy
            
            service_copy['analysis'] = analysis_copy
            services_copy[service_name] = service_copy
        
        return services_copy
    
    def _write_service_snapshots(self, task_dir: Path, services: Dict[str, Any], timestamp: str) -> None:
        """Write per-service snapshot files with full original data including SARIF.
        
        Provides backward compatibility for tools expecting full SARIF embedded.
        """
        services_dir = task_dir / 'services'
        services_dir.mkdir(exist_ok=True)
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            snapshot_filename = f"{service_name}_analysis_{timestamp}.json"
            snapshot_path = services_dir / snapshot_filename
            
            try:
                with open(snapshot_path, 'w', encoding='utf-8') as f:
                    json.dump(service_data, f, indent=2, default=str)
                self._log(f"Wrote service snapshot: {snapshot_filename}", level='debug')
            except Exception as e:
                self._log(f"Failed to write service snapshot for {service_name}: {e}", level='error')
    
    def _aggregate_findings_from_services(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate findings from all services into flat severity-based structure.
        
        Matches analyzer_manager._aggregate_findings behavior.
        """
        aggregated = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'info': []
        }
        
        tools_executed = set()
        findings_by_tool = {}
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            analysis = service_data.get('analysis', {})
            if not isinstance(analysis, dict):
                continue
            
            # Extract from tool_results
            tool_results = analysis.get('tool_results', {})
            if isinstance(tool_results, dict):
                for tool_name, tool_data in tool_results.items():
                    if not isinstance(tool_data, dict):
                        continue
                    
                    tools_executed.add(tool_name)
                    
                    # Get issues/findings
                    issues = tool_data.get('issues', [])
                    if not isinstance(issues, list):
                        issues = []
                    
                    findings_by_tool[tool_name] = len(issues)
                    
                    # Categorize by severity
                    for issue in issues:
                        if not isinstance(issue, dict):
                            continue
                        
                        severity = str(issue.get('severity', 'info')).lower()
                        finding = {
                            'severity': severity,
                            'message': issue.get('message', ''),
                            'file': issue.get('file', issue.get('filename', '')),
                            'line': issue.get('line', issue.get('line_number', 0)),
                            'tool': tool_name,
                            'service': service_name,
                            'rule_id': issue.get('rule_id', issue.get('test_id', ''))
                        }
                        
                        if severity in aggregated:
                            aggregated[severity].append(finding)
                        else:
                            aggregated['info'].append(finding)
            
            # Extract from nested results structure
            results = analysis.get('results', {})
            if isinstance(results, dict):
                for category, category_data in results.items():
                    if not isinstance(category_data, dict):
                        continue
                    
                    for tool_name, tool_data in category_data.items():
                        if not isinstance(tool_data, dict):
                            continue
                        
                        tools_executed.add(tool_name)
                        
                        issues = tool_data.get('issues', [])
                        if not isinstance(issues, list):
                            issues = []
                        
                        findings_by_tool[tool_name] = findings_by_tool.get(tool_name, 0) + len(issues)
                        
                        for issue in issues:
                            if not isinstance(issue, dict):
                                continue
                            
                            severity = str(issue.get('severity', 'info')).lower()
                            finding = {
                                'severity': severity,
                                'message': issue.get('message', ''),
                                'file': issue.get('file', issue.get('filename', '')),
                                'line': issue.get('line', issue.get('line_number', 0)),
                                'tool': tool_name,
                                'service': service_name,
                                'category': category,
                                'rule_id': issue.get('rule_id', issue.get('test_id', ''))
                            }
                            
                            if severity in aggregated:
                                aggregated[severity].append(finding)
                            else:
                                aggregated['info'].append(finding)
        
        total_findings = sum(len(v) for v in aggregated.values())
        
        return {
            'findings': aggregated,
            'findings_total': total_findings,
            'findings_by_severity': {k: len(v) for k, v in aggregated.items()},
            'findings_by_tool': findings_by_tool,
            'tools_executed': sorted(list(tools_executed))
        }
    
    def _collect_normalized_tools(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """Collect normalized tool status map across all services.
        
        Returns flat dict of {tool_name: {status, exit_code, findings_count, service, ...}}
        """
        normalized_tools = {}
        
        for service_name, service_data in services.items():
            if not isinstance(service_data, dict):
                continue
            
            analysis = service_data.get('analysis', {})
            if not isinstance(analysis, dict):
                continue
            
            # Process tool_results
            tool_results = analysis.get('tool_results', {})
            if isinstance(tool_results, dict):
                for tool_name, tool_data in tool_results.items():
                    if not isinstance(tool_data, dict):
                        continue
                    
                    issues = tool_data.get('issues', [])
                    normalized_tools[tool_name] = {
                        'status': tool_data.get('status', 'unknown'),
                        'exit_code': tool_data.get('exit_code', 0),
                        'findings_count': len(issues) if isinstance(issues, list) else 0,
                        'service': service_name
                    }
                    
                    # Add SARIF file reference if present
                    if 'sarif_file' in tool_data:
                        normalized_tools[tool_name]['sarif_file'] = tool_data['sarif_file']
            
            # Process nested results
            results = analysis.get('results', {})
            if isinstance(results, dict):
                for category, category_data in results.items():
                    if not isinstance(category_data, dict):
                        continue
                    
                    for tool_name, tool_data in category_data.items():
                        if not isinstance(tool_data, dict):
                            continue
                        
                        issues = tool_data.get('issues', [])
                        
                        # Update or create tool entry
                        if tool_name not in normalized_tools:
                            normalized_tools[tool_name] = {
                                'status': tool_data.get('status', 'unknown'),
                                'exit_code': tool_data.get('exit_code', 0),
                                'findings_count': 0,
                                'service': service_name,
                                'category': category
                            }
                        
                        # Add to findings count
                        normalized_tools[tool_name]['findings_count'] = normalized_tools[tool_name].get('findings_count', 0) + (len(issues) if isinstance(issues, list) else 0)
                        
                        # Add SARIF file reference if present
                        if 'sarif_file' in tool_data:
                            normalized_tools[tool_name]['sarif_file'] = tool_data['sarif_file']
        
        return normalized_tools
    
    def _write_task_results_to_filesystem(
        self,
        model_slug: str,
        app_number: int,
        task_id: str,
        unified_payload: Dict[str, Any]
    ) -> None:
        """Write task results to filesystem matching analyzer_manager structure.
        
        Saves to: results/{model_slug}/app{app_number}/task_{task_id}/
        
        Creates:
        - Main consolidated JSON (with SARIF extracted)
        - sarif/ directory with individual SARIF files
        - services/ directory with full service snapshots
        - manifest.json for quick metadata access
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
        filename = f"{safe_slug}_app{app_number}_{task_folder_name}_{timestamp}.json"
        filepath = task_dir / filename
        
        # Extract services from unified_payload
        services = unified_payload.get('services', {})
        
        # 1. Write service snapshots FIRST (before SARIF extraction) - preserves full original data
        self._write_service_snapshots(task_dir, services, timestamp)
        
        # 2. Create SARIF directory and extract SARIF to separate files
        sarif_dir = task_dir / 'sarif'
        sarif_dir.mkdir(exist_ok=True)
        services_with_sarif_refs = self._extract_sarif_to_files(services, sarif_dir)
        
        # 3. Aggregate findings from services (use original services with full SARIF)
        aggregated_findings = self._aggregate_findings_from_services(services)
        
        # 4. Collect normalized tools
        normalized_tools = self._collect_normalized_tools(services_with_sarif_refs)
        
        # 5. Build comprehensive results structure (matching analyzer_manager format)
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
            'results': {
                'task': unified_payload.get('task', {
                    'task_id': task_id,
                    'analysis_type': task_id,
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'started_at': datetime.now().isoformat(),
                    'completed_at': datetime.now().isoformat()
                }),
                'summary': {
                    'total_findings': aggregated_findings.get('findings_total', 0),
                    'services_executed': len([k for k, v in services.items() if isinstance(v, dict) and v.get('status') == 'success']),
                    'tools_executed': len(normalized_tools),
                    'severity_breakdown': aggregated_findings.get('findings_by_severity', {}),
                    'findings_by_tool': aggregated_findings.get('findings_by_tool', {}),
                    'tools_used': sorted(aggregated_findings.get('tools_executed', [])),
                    'tools_failed': sorted([t for t, d in normalized_tools.items() if str(d.get('status', '')).lower() not in ('success', 'completed', 'no_issues')]),
                    'tools_skipped': [],
                    'status': 'completed'
                },
                # Services with SARIF extracted to separate files
                'services': services_with_sarif_refs,
                # Flat normalized view of all tools
                'tools': normalized_tools,
                # Aggregated findings by severity
                'findings': aggregated_findings.get('findings', {})
            }
        }
        
        # 6. Write the main consolidated file (with SARIF extracted)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(full_results, f, indent=2, default=str)
        
        self._log(
            f"[FILESYSTEM] Consolidated task results saved to: {filepath}",
            level='info'
        )
        self._log(
            f"[FILESYSTEM] SARIF files extracted to: {sarif_dir}",
            level='info'
        )
        
        # 7. Write enhanced manifest.json
        manifest_path = task_dir / "manifest.json"
        manifest = {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'analysis_type': task_id,
            'timestamp': datetime.now().isoformat(),
            'status': 'completed',
            'main_result_file': filename,
            'sarif_directory': 'sarif/',
            'services_directory': 'services/',
            'total_findings': aggregated_findings.get('findings_total', 0),
            'services': {name: data.get('status', 'unknown') if isinstance(data, dict) else 'unknown' for name, data in services.items()},
            'tools_count': len(normalized_tools),
            'file_sizes': {
                'main_json_mb': round(filepath.stat().st_size / 1024 / 1024, 2) if filepath.exists() else 0,
                'sarif_total_mb': round(sum(f.stat().st_size for f in sarif_dir.glob('*.sarif.json')) / 1024 / 1024, 2) if sarif_dir.exists() else 0
            }
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
                        status = str(result.get('status', '')).lower()
                        success = status in ('success', 'completed', 'partial')
                        is_partial = status == 'partial'
                    except Exception as e:
                        self._log("Analysis execution failed for task %s: %s", task_db.task_id, e, level='error')
                        success = False
                        is_partial = False
                        result = {'status': 'error', 'error': str(e)}

                    # Set final status based on analysis result  
                    if is_partial:
                        task_db.status = AnalysisStatus.PARTIAL_SUCCESS
                    else:
                        task_db.status = AnalysisStatus.COMPLETED if success else AnalysisStatus.FAILED
                    task_db.progress_percentage = 100.0
                    task_db.completed_at = datetime.now(timezone.utc)
                    
                    # Store analysis results via UnifiedResultService
                    if result and result.get('payload'):
                        try:
                            unified_service = ServiceLocator.get_unified_result_service()
                            unified_service.store_analysis_results(
                                task_id=task_db.task_id,
                                payload=result['payload'],
                                model_slug=task_db.target_model,
                                app_number=task_db.target_app_number
                            )
                        except Exception as e:
                            self._log("Failed to store analysis results for task %s: %s", task_db.task_id, e, level='warning')
                            # Fallback
                            task_db.set_result_summary(result['payload'])
                    
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
