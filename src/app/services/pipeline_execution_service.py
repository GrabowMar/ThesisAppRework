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
                            except Exception:
                                db.session.rollback()
                        finally:
                            self._current_pipeline_id = None
                    
                except Exception as e:
                    self._log("Pipeline execution loop error: %s", e, level='error')
                
                time.sleep(self.poll_interval)
    
    def _process_pipeline(self, pipeline: PipelineExecution):
        """Process a single pipeline - execute its next job or check completion."""
        # Debug: Log current state before getting next job
        status_val = pipeline.status.value if hasattr(pipeline.status, 'value') else str(pipeline.status)
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
            self._execute_generation_job(pipeline, job)
            pipeline.advance_job_index()
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
        
        # Initialize tracking for this pipeline
        if pipeline_id not in self._in_flight_tasks:
            self._in_flight_tasks[pipeline_id] = set()
        
        # STEP 1: Start containers if this is the first analysis job
        if pipeline.current_job_index == 0 and pipeline_id not in self._containers_started_for:
            auto_start = analysis_opts.get('autoStartContainers', True)  # Default to True for pipelines
            if auto_start:
                if not self._ensure_analyzers_healthy(pipeline):
                    # Failed to start containers - fail pipeline
                    error_msg = (
                        "Failed to start analyzer containers. "
                        "Please check Docker is running and try again."
                    )
                    self._log("Failing pipeline %s - container startup failed", pipeline_id, level='error')
                    pipeline.fail(error_msg)
                    db.session.commit()
                    return
                self._containers_started_for.add(pipeline_id)
            else:
                # Auto-start disabled - check if containers are healthy anyway
                if not self._check_analyzers_running():
                    error_msg = (
                        "Analyzer services are not running. Either:\n"
                        "1. Start containers manually: ./start.ps1 -Mode Start\n"
                        "2. Or enable 'Auto-start containers' in pipeline settings"
                    )
                    self._log("Failing pipeline %s - analyzers not running", pipeline_id, level='error')
                    pipeline.fail(error_msg)
                    db.session.commit()
                    return
        
        # STEP 2: Check completed in-flight tasks
        self._check_completed_analysis_tasks(pipeline)
        
        # STEP 3: Submit new tasks up to parallelism limit
        in_flight_count = len(self._in_flight_tasks.get(pipeline_id, set()))
        
        while in_flight_count < max_concurrent:
            job = pipeline.get_next_job()
            if job is None:
                break  # No more jobs to submit
            
            # Skip if generation failed for this job
            if not job.get('success', False):
                self._log(
                    "Skipping analysis for %s app %s - generation failed",
                    job.get('model_slug'), job.get('app_number')
                )
                pipeline.add_analysis_task_id('skipped', success=False)
                pipeline.advance_job_index()
                continue
            
            # Submit analysis task
            task_id = self._submit_analysis_task(pipeline, job)
            if task_id and not task_id.startswith('error:') and not task_id.startswith('skipped'):
                self._in_flight_tasks[pipeline_id].add(task_id)
                in_flight_count += 1
            
            pipeline.advance_job_index()
        
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
            pipeline.add_analysis_task_id(skip_marker, success=False)
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
            
            # Get default tools if none specified
            if not tools:
                try:
                    registry = get_container_tool_registry()
                    all_tools = registry.get_all_tools()
                    tools = [t.name for t in all_tools.values() if t.available]
                except Exception:
                    tools = []
            
            # Create analysis task
            task = AnalysisTaskService.create_task(
                model_slug=model_slug,
                app_number=app_number,
                tools=tools,
                priority='normal',
                custom_options={
                    'source': 'automation_pipeline',
                    'pipeline_id': pipeline_id,
                },
            )
            
            pipeline.add_analysis_task_id(task.task_id, success=True)
            
            self._log(
                "Created analysis task %s for %s app %d",
                task.task_id, model_slug, app_number
            )
            return task.task_id
            
        except Exception as e:
            self._log(
                "Analysis task creation failed for %s app %d: %s",
                model_slug, app_number, e,
                level='error'
            )
            error_marker = f'error:{str(e)}'
            pipeline.add_analysis_task_id(error_marker, success=False)
            return error_marker
    
    def _check_completed_analysis_tasks(self, pipeline: PipelineExecution):
        """Check which in-flight tasks have completed and update tracking."""
        pipeline_id = pipeline.pipeline_id
        in_flight = self._in_flight_tasks.get(pipeline_id, set()).copy()
        
        for task_id in in_flight:
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                # Task not found - remove from tracking
                self._in_flight_tasks[pipeline_id].discard(task_id)
                continue
            
            if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS,
                              AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                # Task reached terminal state - remove from in-flight
                self._in_flight_tasks[pipeline_id].discard(task_id)
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
        """Stop containers if they were auto-started for this pipeline."""
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
                # Track that we started these containers
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
                # Remove from tracking
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
    
    def _execute_generation_job(self, pipeline: PipelineExecution, job: Dict[str, Any]):
        """Execute a single generation job."""
        job_index = job.get('job_index', pipeline.current_job_index)
        model_slug = job['model_slug']
        template_slug = job['template_slug']
        
        # ROBUST DUPLICATE DETECTION:
        # 1. Check by job_index: if result already exists at this index, skip
        # 2. Check by model+template: fallback for edge cases
        # This prevents duplicates on server restart and race conditions
        progress = pipeline.progress
        existing_results = progress.get('generation', {}).get('results', [])
        
        # Check 1: Job-index-based detection (most reliable)
        if job_index < len(existing_results):
            existing = existing_results[job_index]
            self._log(
                "Skipping job %d: result already exists (model=%s, template=%s, app=%d)",
                job_index, existing.get('model_slug'), existing.get('template_slug'),
                existing.get('app_number', -1)
            )
            return
        
        # Check 2: Model+template combination (handles out-of-order edge cases)
        for existing_result in existing_results:
            if (existing_result.get('model_slug') == model_slug and
                existing_result.get('template_slug') == template_slug):
                self._log(
                    "Skipping duplicate generation for %s with template %s (already generated app %d)",
                    model_slug, template_slug, existing_result.get('app_number')
                )
                return  # Already generated this model+template combo
        
        self._log(
            "Generating app for %s with template %s",
            model_slug, template_slug
        )
        
        try:
            # Get generation service
            from app.services.generation import get_generation_service
            svc = get_generation_service()
            
            # Get next app number for this model
            max_app = GeneratedApplication.query.filter_by(
                model_slug=model_slug
            ).order_by(
                GeneratedApplication.app_number.desc()
            ).first()
            app_num = (max_app.app_number + 1) if max_app else 1
            
            # Run generation (async wrapper)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                gen_result = loop.run_until_complete(
                    svc.generate_full_app(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                    )
                )
            finally:
                loop.close()
            
            # Record result with job_index for tracking
            result = {
                'job_index': job_index,
                'model_slug': model_slug,
                'template_slug': template_slug,
                'app_number': gen_result.get('app_number', app_num),
                'success': gen_result.get('success', True),
            }
            pipeline.add_generation_result(result)
            
            self._log(
                "Generated %s app %d with template %s (job %d)",
                model_slug, result['app_number'], template_slug, job_index
            )
            
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
            pipeline.add_generation_result(result)
        
        # NOTE: Don't commit here - let _process_pipeline commit atomically
        # with advance_job_index() to prevent duplicate jobs on restart
    
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
                max_wait = 60  # Reduced from 90
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
