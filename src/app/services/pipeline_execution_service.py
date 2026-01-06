"""Pipeline Execution Service
==============================

Background daemon service that processes automation pipelines.
Handles the two-stage pipeline workflow: Generation → Analysis

Key features:
- Polls database for running pipelines
- Executes generation jobs sequentially
- Executes analysis jobs with configurable parallelism (default: 3 concurrent)
- Automatic container management (start at pipeline start, stop on completion)
- Pre-flight health checks before analysis
- Emits real-time updates via WebSocket if available

Architecture:
- Uses main task + subtasks pattern for parallel analysis (like TaskExecutionService)
- Tracks in-flight task count for parallelism control
- Respects maxConcurrentTasks config setting
"""

from __future__ import annotations

import os
import threading
import time
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, Future, as_completed
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Set

from app.utils.logging_config import get_logger
from app.extensions import db, get_components
from app.models import PipelineExecution, PipelineExecutionStatus, GeneratedApplication, AnalysisTask
from app.constants import AnalysisStatus
from app.services.service_locator import ServiceLocator

logger = get_logger("pipeline_executor")

# Thread safety lock for shared mutable state
_pipeline_state_lock = threading.RLock()

# Default parallelism limit for analysis tasks
DEFAULT_MAX_CONCURRENT_TASKS = 3


class PipelineExecutionService:
    """Background service for executing automation pipelines.
    
    Lifecycle:
    - Polls DB for pipelines with status='running'
    - For each running pipeline, executes the next pending job
    - Handles stage transitions (generation → analysis → done)
    - Auto-manages containers (start before analysis, stop after completion)
    - Supports parallel analysis execution with configurable limits
    """
    
    def __init__(self, poll_interval: float = 3.0, app=None):
        """Initialize pipeline execution service.
        
        Args:
            poll_interval: Seconds between polling for work
            app: Flask application instance for context
        """
        self.poll_interval = poll_interval
        self._app = app
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._current_pipeline_id: Optional[str] = None
        
        # Parallel analysis execution
        self._analysis_executor: Optional[ThreadPoolExecutor] = None
        self._analysis_futures: Dict[str, Dict[str, Future]] = {}  # pipeline_id -> {task_id -> Future}
        self._in_flight_tasks: Dict[str, Set[str]] = {}  # pipeline_id -> set of task_ids
        
        # Analyzer health cache
        self._analyzer_healthy: Optional[bool] = None
        self._analyzer_check_time: float = 0.0
        self._analyzer_check_interval: float = 60.0  # Re-check every 60 seconds
        
        # Container management state
        self._containers_started_for: Set[str] = set()  # pipeline_ids with auto-started containers
        
        # App container tracking (model_slug, app_number) tuples started per pipeline
        self._app_containers_started: Dict[str, Set[tuple]] = {}  # pipeline_id -> {(model, app_num), ...}
        
        self._log("PipelineExecutionService initialized (poll_interval=%s)", poll_interval)
    
    def _log(self, msg: str, *args, level: str = 'info', **kwargs):
        """Log with consistent formatting."""
        formatted = msg % args if args else msg
        log_func = getattr(logger, level, logger.info)
        log_func(f"[PipelineExecutor] {formatted}")
    
    def start(self):
        """Start the background execution thread."""
        if self._running:
            return
        
        self._running = True
        
        # Initialize thread pool for parallel analysis
        self._analysis_executor = ThreadPoolExecutor(
            max_workers=8,  # Allow up to 8 concurrent threads (actual limit controlled per-pipeline)
            thread_name_prefix="pipeline_analysis"
        )
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("PipelineExecutionService started")
    
    def stop(self):
        """Stop the background execution thread."""
        self._running = False
        
        # Shutdown thread pool
        if self._analysis_executor:
            self._analysis_executor.shutdown(wait=True, cancel_futures=False)
            self._analysis_executor = None
        
        if self._thread:
            self._thread.join(timeout=5)
        
        self._log("PipelineExecutionService stopped")
    
    def _run_loop(self):
        """Main execution loop - polls for and processes pipelines."""
        self._log("Execution loop started")
        
        while self._running:
            with (self._app.app_context() if self._app else _nullcontext()):
                try:
                    # Get running pipelines
                    pipelines = PipelineExecution.get_running_pipelines()

                    if not pipelines:
                        time.sleep(self.poll_interval)
                        continue

                    self._log("Found %d running pipeline(s)", len(pipelines), level='debug')

                    # Process each running pipeline
                    for pipeline in pipelines:
                        try:
                            self._current_pipeline_id = pipeline.pipeline_id
                            self._process_pipeline(pipeline)
                        except Exception as e:
                            self._log(
                                "Error processing pipeline %s: %s",
                                pipeline.pipeline_id, e,
                                level='error'
                            )
                            # Mark pipeline as failed on exception
                            try:
                                pipeline.fail(str(e))
                                db.session.commit()
                                # Clean up containers on failure
                                self._stop_all_app_containers_for_pipeline(pipeline)
                                self._cleanup_pipeline_containers(pipeline.pipeline_id)
                            except Exception as cleanup_error:
                                self._log("Failed to cleanup after pipeline error: %s", cleanup_error, level='error')
                                try:
                                    db.session.rollback()
                                except Exception as rollback_error:
                                    self._log("Critical: Failed to rollback session: %s", rollback_error, level='critical')
                            finally:
                                # Ensure session is cleaned up
                                try:
                                    db.session.remove()
                                except Exception:
                                    pass
                        finally:
                            self._current_pipeline_id = None

                except Exception as e:
                    self._log("Pipeline execution loop error: %s", e, level='error')
                    # Clean up session on loop errors
                    try:
                        db.session.remove()
                    except Exception:
                        pass

                time.sleep(self.poll_interval)
    
    def _process_pipeline(self, pipeline: PipelineExecution):
        """Process a single pipeline - execute its next job or check completion."""
        # Debug: Log current state before getting next job
        status_val = pipeline.status.value if hasattr(pipeline.status, 'value') else str(pipeline.status)  # type: ignore[union-attr]
        self._log(
            "[DEBUG] Pipeline %s: stage=%s, job_index=%d, status=%s",
            pipeline.pipeline_id, pipeline.current_stage, 
            pipeline.current_job_index, status_val
        )
        
        # Handle analysis stage with parallel execution
        if pipeline.current_stage == 'analysis':
            self._process_analysis_stage(pipeline)
            return
        
        # Get next job to execute (generation stage)
        job = pipeline.get_next_job()
        
        if job is None:
            self._log(
                "[DEBUG] Pipeline %s: get_next_job returned None, checking stage transition",
                pipeline.pipeline_id
            )
            # No more jobs - check if we need to transition stages
            self._check_stage_transition(pipeline)
            return
        
        self._log(
            "Processing pipeline %s: stage=%s, job=%s",
            pipeline.pipeline_id, job['stage'], job.get('job_index', 0)
        )
        
        # Execute generation job
        if job['stage'] == 'generation':
            # FIX: Advance job_index FIRST and commit to prevent race condition
            # This ensures the next poll sees the updated index before we execute
            # The duplicate detection in _execute_generation_job handles edge cases
            # Note: advance_job_index() before add_generation_result() is safe because:
            #   1. add_generation_result() resets job_index=0 on stage transition anyway
            #   2. Duplicate detection in _execute_generation_job handles concurrent executions
            pipeline.advance_job_index()
            db.session.commit()
            
            # Execute generation - may cause stage transition
            stage_transitioned = self._execute_generation_job(pipeline, job)
            
            # Commit the generation results (and possibly stage transition)
            db.session.commit()
            self._emit_progress_update(pipeline)
    
    def _process_analysis_stage(self, pipeline: PipelineExecution):
        """Process analysis stage with parallel execution.
        
        This method:
        1. Starts containers if needed (first time in analysis stage)
        2. Submits analysis tasks up to parallelism limit
        3. Tracks in-flight tasks and polls for completion
        4. Transitions to done stage when all tasks complete
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress
        config = pipeline.config
        
        # Get parallelism settings
        analysis_opts = config.get('analysis', {}).get('options', {})
        max_concurrent = progress.get('analysis', {}).get('max_concurrent', DEFAULT_MAX_CONCURRENT_TASKS)
        
        # Initialize tracking for this pipeline (thread-safe)
        with _pipeline_state_lock:
            if pipeline_id not in self._in_flight_tasks:
                self._in_flight_tasks[pipeline_id] = set()
        
        # STEP 1: Start containers if this is the first analysis job
        # NOTE: Analyzer container startup is a "soft requirement" - we warn but continue
        # Individual tasks will naturally succeed (static analysis) or skip (dynamic/perf)
        # based on container availability. This prevents pipeline abort on transient failures.
        with _pipeline_state_lock:
            containers_already_started = pipeline_id in self._containers_started_for
        
        if pipeline.current_job_index == 0 and not containers_already_started:
            auto_start = analysis_opts.get('autoStartContainers', True)  # Default to True for pipelines
            if auto_start:
                # Try to start analyzers with longer timeout (180s default)
                analyzers_ready = self._ensure_analyzers_healthy(pipeline)
                
                if analyzers_ready:
                    with _pipeline_state_lock:
                        self._containers_started_for.add(pipeline_id)
                    # Additional stabilization delay after startup to ensure ports are fully bound
                    time.sleep(5)
                    self._log("[PIPELINE %s] Analyzer containers ready, added 5s stabilization delay", pipeline_id)
                else:
                    # Retry once more after a longer delay (containers may still be starting)
                    self._log(
                        "[PIPELINE %s] First analyzer startup attempt failed, retrying after 30s delay...",
                        pipeline_id, level='warning'
                    )
                    time.sleep(30)
                    
                    # Second attempt - reset cache to force fresh check
                    self._analyzer_healthy = None
                    analyzers_ready = self._ensure_analyzers_healthy(pipeline)
                    
                    if analyzers_ready:
                        with _pipeline_state_lock:
                            self._containers_started_for.add(pipeline_id)
                        time.sleep(5)  # Stabilization delay
                        self._log("[PIPELINE %s] Analyzer containers ready on retry", pipeline_id)
                    else:
                        # Log warning but continue - static analysis and individual tasks
                        # will handle their own dependencies
                        self._log(
                            "[PIPELINE %s] WARNING: Analyzer containers could not be started after retry. "
                            "Static analysis will continue. Dynamic/performance analysis "
                            "will skip or fail for apps without running containers.",
                            pipeline_id, level='warning'
                        )
                        # Still mark as "attempted" to avoid retry on every poll
                        with _pipeline_state_lock:
                            self._containers_started_for.add(pipeline_id)
            else:
                # Auto-start disabled - check if containers are healthy anyway
                if not self._check_analyzers_running():
                    # Log warning but continue - let tasks handle their own dependencies
                    self._log(
                        "[PIPELINE %s] WARNING: Analyzer services not running and auto-start disabled. "
                        "Analysis tasks may partially succeed or skip dynamic/performance tests. "
                        "To enable all analysis types, start containers via: ./start.ps1 -Mode Start",
                        pipeline_id, level='warning'
                    )
        
        # STEP 2: Check completed in-flight tasks
        self._check_completed_analysis_tasks(pipeline)
        
        # STEP 3: Submit new tasks up to parallelism limit (thread-safe read)
        with _pipeline_state_lock:
            in_flight_count = len(self._in_flight_tasks.get(pipeline_id, set()))
        
        while in_flight_count < max_concurrent:
            job = pipeline.get_next_job()
            if job is None:
                break  # No more jobs to submit
            
            # Get job key for duplicate tracking
            model_slug = job.get('model_slug')
            app_number = job.get('app_number')
            job_key = f"{model_slug}:{app_number}"
            
            # FIX: Advance job_index FIRST and commit to prevent race condition
            # This ensures the next poll sees the updated index before we do the work
            pipeline.advance_job_index()
            db.session.commit()
            
            # Skip if generation failed for this job
            if not job.get('success', False):
                self._log(
                    "Skipping analysis for %s app %s - generation failed",
                    model_slug, app_number
                )
                pipeline.add_analysis_task_id('skipped:generation_failed', success=False,
                                              model_slug=model_slug, app_number=app_number)
                db.session.commit()
                continue
            
            # FIX: Check if this model:app combo was already submitted (duplicate guard)
            progress = pipeline.progress
            existing_task_ids = progress.get('analysis', {}).get('task_ids', [])
            submitted_apps = progress.get('analysis', {}).get('submitted_apps', [])
            
            if job_key in submitted_apps:
                self._log(
                    "Skipping duplicate analysis submission for %s app %d (already in submitted_apps)",
                    model_slug, app_number
                )
                continue
            
            # Double-check against existing tasks (belt-and-suspenders)
            already_submitted = False
            for task_id in existing_task_ids:
                if task_id.startswith('skipped') or task_id.startswith('error:'):
                    continue
                existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
                if (existing_task and 
                    existing_task.target_model == model_slug and 
                    existing_task.target_app_number == app_number):
                    self._log(
                        "Skipping duplicate analysis for %s app %d (already have task %s)",
                        model_slug, app_number, task_id
                    )
                    already_submitted = True
                    break
            
            if already_submitted:
                continue
            
            # Submit analysis task
            task_id = self._submit_analysis_task(pipeline, job)
            if task_id and not task_id.startswith('error:') and not task_id.startswith('skipped'):
                with _pipeline_state_lock:
                    self._in_flight_tasks[pipeline_id].add(task_id)
                in_flight_count += 1
            
            # Commit after task submission to record the task_id
            db.session.commit()
        
        # STEP 4: Check if all analysis is complete
        if self._check_analysis_tasks_completion(pipeline):
            # Analysis complete - commit completion status and stop containers
            db.session.commit()
            self._stop_all_app_containers_for_pipeline(pipeline)
            self._cleanup_pipeline_containers(pipeline_id)
        
        self._emit_progress_update(pipeline)
    
    def _submit_analysis_task(self, pipeline: PipelineExecution, job: Dict[str, Any]) -> str:
        """Create and submit a single analysis task.
        
        Returns task_id on success, or error/skipped marker on failure.
        """
        model_slug = job['model_slug']
        app_number = job['app_number']
        pipeline_id = pipeline.pipeline_id
        
        # Check for duplicate task (prevents issues on server restart)
        progress = pipeline.progress
        existing_task_ids = progress.get('analysis', {}).get('task_ids', [])
        
        for task_id in existing_task_ids:
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                continue
            existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if (existing_task and 
                existing_task.target_model == model_slug and 
                existing_task.target_app_number == app_number):
                self._log(
                    "Skipping duplicate analysis task for %s app %d (already have %s)",
                    model_slug, app_number, task_id
                )
                return task_id  # Return existing task ID
        
        # STEP 1: Validate app exists before attempting analysis
        exists, app_path, validation_msg = self._validate_app_exists(model_slug, app_number)
        if not exists:
            self._log(
                "Skipping analysis for %s app %d: %s",
                model_slug, app_number, validation_msg,
                level='warning'
            )
            skip_marker = f'skipped:app_missing:{validation_msg}'
            pipeline.add_analysis_task_id(skip_marker, success=False, 
                                          model_slug=model_slug, app_number=app_number)
            return skip_marker
        
        # STEP 2: Start app containers if autoStartContainers is enabled
        config = pipeline.config
        analysis_config = config.get('analysis', {})
        auto_start = analysis_config.get('autoStartContainers', 
                                         analysis_config.get('options', {}).get('autoStartContainers', True))
        
        if auto_start:
            start_result = self._start_app_containers(pipeline_id, model_slug, app_number)
            if not start_result.get('success'):
                # Log warning but continue - analysis might still work (e.g., static analysis)
                self._log(
                    "App container startup failed for %s app %d, continuing with analysis anyway: %s",
                    model_slug, app_number, start_result.get('error', 'Unknown'),
                    level='warning'
                )
        
        self._log("Creating analysis task for %s app %d", model_slug, app_number)
        
        try:
            from app.services.task_service import AnalysisTaskService
            from app.engines.container_tool_registry import get_container_tool_registry
            
            # Get analysis config
            config = pipeline.config
            analysis_config = config.get('analysis', {})
            tools = analysis_config.get('tools', [])
            
            # Get tool registry
            registry = get_container_tool_registry()
            all_tools = registry.get_all_tools()
            
            # Get default tools if none specified (same as API)
            if not tools:
                tools = [t.name for t in all_tools.values() if t.available]
            
            # ========== MATCH API BEHAVIOR: Resolve tools and group by service ==========
            # Build lookup: name (case-insensitive) -> tool object
            tools_lookup = {t.name.lower(): t for t in all_tools.values()}
            name_to_idx = {t.name.lower(): idx + 1 for idx, t in enumerate(all_tools.values())}
            
            tool_ids = []
            valid_tool_names = []
            tools_by_service = {}
            
            for tool_name in tools:
                tool_name_lower = tool_name.lower()
                tool_obj = tools_lookup.get(tool_name_lower)
                
                if tool_obj and tool_obj.available:
                    tool_id = name_to_idx.get(tool_name_lower)
                    if tool_id:
                        tool_ids.append(tool_id)
                        valid_tool_names.append(tool_obj.name)
                        service = tool_obj.container.value
                        tools_by_service.setdefault(service, []).append(tool_id)
                else:
                    self._log("Tool '%s' not found or unavailable", tool_name, level='warning')
            
            if not tools_by_service or not valid_tool_names:
                self._log(
                    "No valid tools found for %s app %d",
                    model_slug, app_number, level='error'
                )
                error_marker = 'error:no_valid_tools'
                pipeline.add_analysis_task_id(error_marker, success=False,
                                              model_slug=model_slug, app_number=app_number)
                return error_marker
            
            # Get container management options from pipeline config (matching API format)
            stop_after = analysis_config.get('stopAfterAnalysis',
                                             analysis_config.get('options', {}).get('stopAfterAnalysis', True))
            container_management = {
                'start_before_analysis': auto_start,  # Use the auto_start we already computed
                'build_if_missing': False,  # Pipeline handles building separately
                'stop_after_analysis': stop_after
            }
            
            # Build custom options matching API format EXACTLY
            custom_options = {
                'selected_tools': tool_ids,
                'selected_tool_names': valid_tool_names,
                'tools_by_service': tools_by_service,
                'source': 'automation_pipeline',
                'pipeline_id': pipeline_id,
                'container_management': container_management
            }
            
            # ALWAYS use unified analysis with subtasks (like custom wizard does)
            # This ensures consistent task structure and UI display regardless of service count
            custom_options['unified_analysis'] = True
            task = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug=model_slug,
                app_number=app_number,
                tools=valid_tool_names,
                priority='normal',
                custom_options=custom_options,
                task_name=f"pipeline:{model_slug}:{app_number}"
            )
            # ========== END MATCHING CUSTOM WIZARD BEHAVIOR ==========
            
            pipeline.add_analysis_task_id(task.task_id, success=True,
                                          model_slug=model_slug, app_number=app_number)
            
            self._log(
                "Created analysis task %s for %s app %d (unified=%s, services=%d, tools=%d)",
                task.task_id, model_slug, app_number,
                len(tools_by_service) > 1, len(tools_by_service), len(valid_tool_names)
            )
            return task.task_id
            
        except Exception as e:
            self._log(
                "Analysis task creation failed for %s app %d: %s",
                model_slug, app_number, e,
                level='error'
            )
            error_marker = f'error:{str(e)}'
            pipeline.add_analysis_task_id(error_marker, success=False,
                                          model_slug=model_slug, app_number=app_number)
            return error_marker
    
    def _check_completed_analysis_tasks(self, pipeline: PipelineExecution):
        """Check which in-flight tasks have completed and update tracking (thread-safe)."""
        pipeline_id = pipeline.pipeline_id
        
        # Thread-safe copy of in-flight tasks
        with _pipeline_state_lock:
            in_flight = self._in_flight_tasks.get(pipeline_id, set()).copy()
        
        for task_id in in_flight:
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                # Task not found - remove from tracking
                with _pipeline_state_lock:
                    self._in_flight_tasks.get(pipeline_id, set()).discard(task_id)
                continue
            
            if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS,
                              AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                # Task reached terminal state - remove from in-flight
                with _pipeline_state_lock:
                    self._in_flight_tasks.get(pipeline_id, set()).discard(task_id)
                self._log(
                    "Task %s completed with status %s",
                    task_id, task.status.value if task.status else 'unknown'
                )
    
    def _check_analyzers_running(self) -> bool:
        """Quick check if analyzer containers are running (no auto-start)."""
        try:
            import sys
            from pathlib import Path
            from flask import current_app
            
            project_root = Path(current_app.root_path).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from analyzer.analyzer_manager import AnalyzerManager
            manager = AnalyzerManager()
            
            containers = manager.get_container_status()
            return all(
                c.get('state') == 'running'
                for c in containers.values()
            ) if containers else False
            
        except Exception as e:
            self._log("Error checking analyzer status: %s", e, level='error')
            return False
    
    def _cleanup_pipeline_containers(self, pipeline_id: str):
        """Stop containers if they were auto-started for this pipeline (thread-safe)."""
        with _pipeline_state_lock:
            if pipeline_id not in self._containers_started_for:
                return
        
        try:
            import sys
            from pathlib import Path
            from flask import current_app
            
            project_root = Path(current_app.root_path).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from analyzer.analyzer_manager import AnalyzerManager
            manager = AnalyzerManager()
            
            self._log("Stopping analyzer containers (auto-started for pipeline %s)", pipeline_id)
            manager.stop_services()
            
        except Exception as e:
            self._log("Error stopping containers: %s", e, level='warning')
        finally:
            with _pipeline_state_lock:
                self._containers_started_for.discard(pipeline_id)
                # Clean up in-flight tracking
                self._in_flight_tasks.pop(pipeline_id, None)
                # Clean up app containers tracking
                self._app_containers_started.pop(pipeline_id, None)
    
    def _start_app_containers(
        self, 
        pipeline_id: str, 
        model_slug: str, 
        app_number: int
    ) -> Dict[str, Any]:
        """Start containers for a generated app before analysis.
        
        Args:
            pipeline_id: Pipeline ID for tracking
            model_slug: The model slug (e.g., 'openai_gpt-4')
            app_number: The app number
            
        Returns:
            Dict with 'success' and optional 'error' or 'message' fields
        """
        try:
            from app.services.docker_manager import DockerManager
            
            manager = DockerManager()
            
            self._log(
                "Starting containers for %s app %d (pipeline %s)",
                model_slug, app_number, pipeline_id
            )
            
            result = manager.start_containers(model_slug, app_number)
            
            if result.get('success'):
                # Track that we started these containers (thread-safe)
                with _pipeline_state_lock:
                    if pipeline_id not in self._app_containers_started:
                        self._app_containers_started[pipeline_id] = set()
                    self._app_containers_started[pipeline_id].add((model_slug, app_number))
                
                self._log(
                    "Successfully started containers for %s app %d",
                    model_slug, app_number
                )
            else:
                self._log(
                    "Failed to start containers for %s app %d: %s",
                    model_slug, app_number, result.get('error', 'Unknown error'),
                    level='warning'
                )
            
            return result
            
        except Exception as e:
            self._log(
                "Error starting app containers for %s app %d: %s",
                model_slug, app_number, e,
                level='error'
            )
            return {'success': False, 'error': str(e)}
    
    def _stop_app_containers(
        self, 
        pipeline_id: str, 
        model_slug: str, 
        app_number: int
    ) -> Dict[str, Any]:
        """Stop containers for a generated app after analysis.
        
        Args:
            pipeline_id: Pipeline ID for tracking
            model_slug: The model slug
            app_number: The app number
            
        Returns:
            Dict with 'success' and optional 'error' fields
        """
        try:
            from app.services.docker_manager import DockerManager
            
            manager = DockerManager()
            
            self._log(
                "Stopping containers for %s app %d (pipeline %s)",
                model_slug, app_number, pipeline_id
            )
            
            result = manager.stop_containers(model_slug, app_number)
            
            if result.get('success'):
                # Remove from tracking (thread-safe)
                with _pipeline_state_lock:
                    if pipeline_id in self._app_containers_started:
                        self._app_containers_started[pipeline_id].discard((model_slug, app_number))
                
                self._log(
                    "Successfully stopped containers for %s app %d",
                    model_slug, app_number
                )
            else:
                self._log(
                    "Failed to stop containers for %s app %d: %s",
                    model_slug, app_number, result.get('error', 'Unknown error'),
                    level='warning'
                )
            
            return result
            
        except Exception as e:
            self._log(
                "Error stopping app containers for %s app %d: %s",
                model_slug, app_number, e,
                level='error'
            )
            return {'success': False, 'error': str(e)}
    
    def _stop_all_app_containers_for_pipeline(self, pipeline: PipelineExecution):
        """Stop all app containers that were started for a pipeline.
        
        Called when pipeline analysis stage completes and stopAfterAnalysis is True.
        """
        pipeline_id = pipeline.pipeline_id
        
        # Thread-safe copy of started apps
        with _pipeline_state_lock:
            started_apps = self._app_containers_started.get(pipeline_id, set()).copy()
        
        if not started_apps:
            return
        
        config = pipeline.config
        analysis_config = config.get('analysis', {})
        stop_after = analysis_config.get('stopAfterAnalysis', 
                                         analysis_config.get('options', {}).get('stopAfterAnalysis', True))
        
        if not stop_after:
            self._log("stopAfterAnalysis disabled - keeping app containers running for pipeline %s", pipeline_id)
            return
        
        self._log("Stopping %d app container sets for pipeline %s", len(started_apps), pipeline_id)
        
        for model_slug, app_number in started_apps:
            self._stop_app_containers(pipeline_id, model_slug, app_number)
    
    def _validate_app_exists(self, model_slug: str, app_number: int) -> tuple:
        """Check if an app directory exists on the filesystem.
        
        Args:
            model_slug: The model slug
            app_number: The app number
            
        Returns:
            Tuple of (exists: bool, app_path: Path or None, message: str)
        """
        try:
            from app.utils.helpers import get_app_directory
            
            app_dir = get_app_directory(model_slug, app_number)
            
            if not app_dir.exists():
                return (False, app_dir, f"App directory not found: {app_dir}")
            
            # Check for docker-compose.yml (needed for container operations)
            compose_file = app_dir / 'docker-compose.yml'
            if not compose_file.exists():
                return (False, app_dir, f"No docker-compose.yml found in {app_dir}")
            
            return (True, app_dir, "App exists and has docker-compose.yml")
            
        except Exception as e:
            return (False, None, f"Error checking app existence: {e}")
    
    def _check_stage_transition(self, pipeline: PipelineExecution):
        """Check if pipeline should transition to next stage or complete."""
        progress = pipeline.progress
        config = pipeline.config
        
        if pipeline.current_stage == 'generation':
            gen_config = config.get('generation', {})
            generation_mode = gen_config.get('mode', 'generate')
            gen = progress.get('generation', {})
            
            if generation_mode == 'existing':
                # Existing apps mode - skip generation entirely, go to analysis
                progress['generation']['status'] = 'skipped'
                
                if progress.get('analysis', {}).get('status') != 'skipped':
                    pipeline.current_stage = 'analysis'
                    pipeline.current_job_index = 0
                    progress['analysis']['status'] = 'running'
                    pipeline.progress = progress
                    self._log("Pipeline %s (existing apps mode) transitioning to analysis stage", pipeline.pipeline_id)
                else:
                    # No analysis - complete pipeline
                    pipeline.status = PipelineExecutionStatus.COMPLETED
                    pipeline.completed_at = datetime.now(timezone.utc)
                    pipeline.current_stage = 'done'
                    self._log("Pipeline %s completed (existing apps, skipped analysis)", pipeline.pipeline_id)
            elif gen.get('status') == 'completed':
                # Generation complete - check if analysis is enabled
                if progress.get('analysis', {}).get('status') != 'skipped':
                    pipeline.current_stage = 'analysis'
                    pipeline.current_job_index = 0
                    progress['analysis']['status'] = 'running'
                    pipeline.progress = progress
                    self._log("Pipeline %s transitioning to analysis stage", pipeline.pipeline_id)
                else:
                    # No analysis - complete pipeline
                    pipeline.status = PipelineExecutionStatus.COMPLETED
                    pipeline.completed_at = datetime.now(timezone.utc)
                    pipeline.current_stage = 'done'
                    self._log("Pipeline %s completed (skipped analysis)", pipeline.pipeline_id)
        
        elif pipeline.current_stage == 'analysis':
            # This shouldn't normally happen since _process_analysis_stage handles completion
            # But if called directly, poll actual task completion status
            analysis_done = self._check_analysis_tasks_completion(pipeline)
            
            if analysis_done:
                # Pipeline complete after analysis (reports stage removed)
                self._stop_all_app_containers_for_pipeline(pipeline)
                self._cleanup_pipeline_containers(pipeline.pipeline_id)
        
        db.session.commit()
    
    def _check_analysis_tasks_completion(self, pipeline: PipelineExecution) -> bool:
        """Check actual completion status of analysis tasks from DB.
        
        Returns True if all tasks have reached a terminal state and marks pipeline complete.
        """
        progress = pipeline.progress
        task_ids = progress.get('analysis', {}).get('task_ids', [])
        
        # Get expected number of analysis jobs
        config = pipeline.config
        gen_config = config.get('generation', {})
        generation_mode = gen_config.get('mode', 'generate')
        
        if generation_mode == 'existing':
            expected_jobs = len(gen_config.get('existingApps', []))
        else:
            gen_results = progress.get('generation', {}).get('results', [])
            expected_jobs = len(gen_results)
        
        if not task_ids:
            # No tasks created yet - check if jobs remain
            if expected_jobs > 0 and pipeline.current_job_index < expected_jobs:
                self._log(
                    "Pipeline %s: No analysis tasks yet, but %d jobs remaining (index=%d)",
                    pipeline.pipeline_id, expected_jobs - pipeline.current_job_index, pipeline.current_job_index
                )
                return False
            else:
                self._log(
                    "Pipeline %s: No analysis tasks to wait for (expected=%d, index=%d)",
                    pipeline.pipeline_id, expected_jobs, pipeline.current_job_index
                )
                # Mark as complete
                pipeline.status = PipelineExecutionStatus.COMPLETED
                pipeline.completed_at = datetime.now(timezone.utc)
                pipeline.current_stage = 'done'
                return True
        
        completed_count = 0
        failed_count = 0
        pending_count = 0
        
        for task_id in task_ids:
            # Handle skipped/error markers
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                failed_count += 1
                continue
            
            # Query actual task status
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                self._log("Analysis task %s not found in database", task_id, level='warning')
                failed_count += 1
                continue
            
            if task.status == AnalysisStatus.COMPLETED:
                completed_count += 1
            elif task.status == AnalysisStatus.PARTIAL_SUCCESS:
                completed_count += 1  # Partial success counts as complete
            elif task.status in (AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                failed_count += 1
            else:
                pending_count += 1
        
        total_tasks = len(task_ids)
        terminal_count = completed_count + failed_count
        
        self._log(
            "Pipeline %s analysis status: %d/%d terminal (completed=%d, failed=%d, pending=%d)",
            pipeline.pipeline_id, terminal_count, total_tasks, completed_count, failed_count, pending_count
        )
        
        # Must wait for ALL tasks to reach terminal state
        if pending_count > 0:
            return False
        
        # Update pipeline progress with final counts
        pipeline.update_analysis_completion(completed_count, failed_count)
        
        self._log(
            "Pipeline %s: All %d analysis tasks finished (%d success, %d failed)",
            pipeline.pipeline_id, total_tasks, completed_count, failed_count
        )
        return True
    
    def _execute_generation_job(self, pipeline: PipelineExecution, job: Dict[str, Any]) -> bool:
        """Execute a single generation job.
        
        Uses the same parameters as the Sample Generator API to ensure 100% parity:
        - generation_mode='guarded' (4-query mode)
        - app_num=None (let service handle atomic allocation)
        - All other standard parameters
        
        Returns:
            True if this job caused a stage transition (generation complete -> analysis),
            False otherwise. Caller should NOT advance job_index when True.
        """
        job_index = job.get('job_index', pipeline.current_job_index)
        model_slug = job['model_slug']
        template_slug = job['template_slug']
        # Include job_index in key to allow multiple apps with same model:template
        job_key = f"{job_index}:{model_slug}:{template_slug}"
        # Legacy format (for backwards compatibility with old pipeline data)
        legacy_job_key = f"{model_slug}:{template_slug}"
        
        # ROBUST DUPLICATE DETECTION:
        # 1. Check submitted_jobs set first (prevents race condition duplicates)
        # 2. Check by job_index: if result already exists at this index, skip
        # This prevents duplicates on server restart and race conditions
        progress = pipeline.progress
        existing_results = progress.get('generation', {}).get('results', [])
        submitted_jobs = progress.get('generation', {}).get('submitted_jobs', [])
        
        # Check 0a: submitted_jobs set using job_index-aware key (prevents race condition duplicates)
        if job_key in submitted_jobs:
            self._log(
                "Skipping duplicate generation for job %d: %s with template %s (already in submitted_jobs)",
                job_index, model_slug, template_slug
            )
            return False  # No stage transition (job was skipped)
        
        # Check 0b: Also check legacy format without job_index prefix (backwards compatibility)
        # This handles pipelines created with older code format
        if legacy_job_key in submitted_jobs:
            self._log(
                "Skipping duplicate generation for job %d: %s with template %s (found legacy key in submitted_jobs)",
                job_index, model_slug, template_slug
            )
            return False  # No stage transition (job was skipped)
        
        # RACE CONDITION PREVENTION: Mark job as started BEFORE doing work
        # Add to submitted_jobs immediately and commit to prevent concurrent poll cycles from starting same job
        if 'submitted_jobs' not in progress['generation']:
            progress['generation']['submitted_jobs'] = []
        progress['generation']['submitted_jobs'].append(job_key)
        pipeline.progress = progress
        db.session.commit()
        self._log(
            "Marked job %d as started (pre-emptive race prevention): %s",
            job_index, job_key, level='debug'
        )
        
        # Check 1: Job-index-based detection (most reliable)
        for existing in existing_results:
            if existing.get('job_index') == job_index:
                self._log(
                    "Skipping job %d: result already exists (model=%s, template=%s, app=%d)",
                    job_index, existing.get('model_slug'), existing.get('template_slug'),
                    existing.get('app_number', -1)
                )
                return False  # No stage transition (job was skipped)
        
        self._log(
            "Generating app for %s with template %s (job %d)",
            model_slug, template_slug, job_index
        )
        
        try:
            # Get generation service
            from app.services.generation import get_generation_service
            svc = get_generation_service()
            
            # Use pipeline_id as batch_id for grouping related generations
            batch_id = pipeline.pipeline_id
            
            # Get generation config options (if any future options are added)
            gen_config = pipeline.config.get('generation', {})
            use_auto_fix = gen_config.get('use_auto_fix', False)
            
            # Run generation with SAME parameters as Sample Generator API
            # Key: app_num=None lets service handle atomic reservation (prevents race conditions)
            # Key: generation_mode='guarded' uses the 4-query system for quality output
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen_result = loop.run_until_complete(
                    svc.generate_full_app(
                        model_slug=model_slug,
                        app_num=None,  # Let service handle atomic allocation
                        template_slug=template_slug,
                        generate_frontend=True,
                        generate_backend=True,
                        batch_id=batch_id,
                        parent_app_id=None,
                        version=1,
                        generation_mode='guarded',  # Always use 4-query mode for quality
                        use_auto_fix=use_auto_fix,
                    )
                )
            finally:
                loop.close()
            
            # Get actual app_number from result (service allocated it atomically)
            app_number = gen_result.get('app_number')
            if app_number is None:
                # Fallback: try to get from app_id or other fields
                app_number = gen_result.get('app_id') or gen_result.get('app_num') or -1
                self._log(
                    "Warning: app_number not in result, using fallback: %d",
                    app_number, level='warning'
                )
            
            # Record result with job_index for tracking
            result = {
                'job_index': job_index,
                'model_slug': model_slug,
                'template_slug': template_slug,
                'app_number': app_number,
                'success': gen_result.get('success', True),
            }
            stage_transitioned = pipeline.add_generation_result(result)
            
            self._log(
                "Generated %s app %d with template %s (job %d, stage_transitioned=%s)",
                model_slug, app_number, template_slug, job_index, stage_transitioned
            )
            
            return stage_transitioned
            
        except Exception as e:
            self._log(
                "Generation failed for %s with %s (job %d): %s",
                model_slug, template_slug, job_index, e,
                level='error'
            )
            result = {
                'job_index': job_index,
                'model_slug': model_slug,
                'template_slug': template_slug,
                'success': False,
                'error': str(e),
            }
            stage_transitioned = pipeline.add_generation_result(result)
            
            # NOTE: Don't commit here - let _process_pipeline commit atomically
            # with advance_job_index() to prevent duplicate jobs on restart
            return stage_transitioned
    
    def _ensure_analyzers_healthy(self, pipeline: PipelineExecution) -> bool:
        """Check and optionally start analyzer containers.
        
        Returns True if analyzers are healthy or were successfully started.
        Uses smarter restart logic to avoid unnecessary rebuilds.
        """
        # Check cache first
        current_time = time.time()
        if (self._analyzer_healthy is not None and 
            (current_time - self._analyzer_check_time) < self._analyzer_check_interval):
            return self._analyzer_healthy
        
        config = pipeline.config
        analysis_config = config.get('analysis', {})
        # Check both analysis.autoStartContainers and analysis.options.autoStartContainers
        auto_start = analysis_config.get('autoStartContainers', 
                                         analysis_config.get('options', {}).get('autoStartContainers', True))
        
        try:
            import sys
            from pathlib import Path
            from flask import current_app
            
            # Add project root to path
            project_root = Path(current_app.root_path).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from analyzer.analyzer_manager import AnalyzerManager
            
            manager = AnalyzerManager()
            
            # Check current status
            containers = manager.get_container_status()
            all_running = all(
                c.get('state') == 'running'
                for c in containers.values()
            ) if containers else False
            
            # Check port accessibility with retries (ports can be temporarily unavailable)
            def check_all_ports():
                return all(
                    manager.check_port_accessibility('localhost', service_info.port)
                    for service_info in manager.services.values()
                )
            
            all_ports_accessible = check_all_ports()
            
            if all_running and all_ports_accessible:
                self._analyzer_healthy = True
                self._analyzer_check_time = current_time
                self._log("Analyzer containers healthy")
                return True
            
            # If containers are running but ports not accessible, wait a bit before giving up
            if all_running and not all_ports_accessible:
                self._log("Containers running but ports not accessible, waiting...")
                for _ in range(5):  # Wait up to 15 seconds
                    time.sleep(3)
                    if check_all_ports():
                        self._log("Ports now accessible")
                        self._analyzer_healthy = True
                        self._analyzer_check_time = current_time
                        return True
                self._log("Ports still not accessible after waiting", level='warning')
            
            # Need to start/restart containers if auto_start is enabled
            if auto_start:
                if all_running:
                    # Containers are running but unhealthy - use quick restart
                    self._log("Restarting analyzer containers (quick restart)...")
                    returncode, stdout, stderr = manager.run_command(
                        manager._compose_cmd + ['restart'], timeout=60
                    )
                    success = returncode == 0
                else:
                    # Containers not running - start without rebuild
                    self._log("Starting analyzer containers...")
                    returncode, stdout, stderr = manager.run_command(
                        manager._compose_cmd + ['up', '-d'], timeout=60
                    )
                    success = returncode == 0
                
                if not success:
                    self._log("Failed to start analyzer containers", level='error')
                    self._analyzer_healthy = False
                    self._analyzer_check_time = current_time
                    return False
                
                # Wait for containers to become healthy
                # Use 180s to match CONTAINER_READY_TIMEOUT - analyzer containers may need
                # time to start, especially if Docker is under load
                max_wait = int(os.environ.get('ANALYZER_STARTUP_TIMEOUT', 180))
                start_time = time.time()
                
                while time.time() - start_time < max_wait:
                    if check_all_ports():
                        self._log("Analyzer containers started and healthy")
                        self._analyzer_healthy = True
                        self._analyzer_check_time = current_time
                        return True
                    time.sleep(3)
                
                self._log("Timeout waiting for analyzer containers", level='warning')
                self._analyzer_healthy = False
                self._analyzer_check_time = current_time
                return False
            
            # Not auto-starting - just report status
            self._analyzer_healthy = False
            self._analyzer_check_time = current_time
            return False
            
        except Exception as e:
            self._log("Error checking analyzer health: %s", e, level='error')
            self._analyzer_healthy = False
            self._analyzer_check_time = current_time
            return False
    
    def _emit_progress_update(self, pipeline: PipelineExecution):
        """Emit real-time progress update via WebSocket if available."""
        try:
            from app.realtime.task_events import emit_task_event
            
            emit_task_event(
                "pipeline.updated",
                {
                    "pipeline_id": pipeline.pipeline_id,
                    "status": pipeline.status,
                    "stage": pipeline.current_stage,
                    "progress": pipeline.progress,
                    "overall_progress": pipeline.get_overall_progress(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        except Exception:
            pass  # WebSocket not available - that's fine


# Null context manager for when app is None
class _nullcontext:
    def __enter__(self):
        return None
    def __exit__(self, *args):
        pass


# Module-level singleton
_pipeline_execution_service: Optional[PipelineExecutionService] = None


def get_pipeline_execution_service() -> Optional[PipelineExecutionService]:
    """Get the pipeline execution service singleton."""
    return _pipeline_execution_service


def init_pipeline_execution_service(app) -> PipelineExecutionService:
    """Initialize and start the pipeline execution service."""
    global _pipeline_execution_service
    
    if _pipeline_execution_service is None:
        # Shorter interval in test mode
        poll_interval = 2.0 if app.config.get('TESTING') else 3.0
        
        _pipeline_execution_service = PipelineExecutionService(
            poll_interval=poll_interval,
            app=app
        )
        _pipeline_execution_service.start()
        
        logger.info("PipelineExecutionService initialized and started")
    
    return _pipeline_execution_service
