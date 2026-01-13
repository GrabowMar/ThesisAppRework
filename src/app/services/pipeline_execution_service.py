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
from concurrent.futures import ThreadPoolExecutor, Future
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

# =============================================================================
# CONFIGURATION CONSTANTS (formerly magic numbers)
# =============================================================================

# Feature flag for new generation system
# Set USE_GENERATION_V2=true to use simplified generation_v2 package
USE_GENERATION_V2: bool = os.environ.get('USE_GENERATION_V2', 'true').lower() in ('true', '1', 'yes')

# Parallelism limits
# NOTE: Pipeline generation uses parallel execution like the original working implementation
# The circuit breaker in rate_limiter.py protects against cascading API failures
DEFAULT_MAX_CONCURRENT_TASKS: int = 2  # Default parallel analysis tasks
DEFAULT_MAX_CONCURRENT_GENERATION: int = 2  # Parallel generation (original working config)
MAX_ANALYSIS_WORKERS: int = 8  # ThreadPool size for analysis
MAX_GENERATION_WORKERS: int = 4  # ThreadPool size for generation

# Timing constants (seconds)
DEFAULT_POLL_INTERVAL: float = 3.0  # Polling interval for work
CONTAINER_STABILIZATION_DELAY: float = 5.0  # Wait after container startup
CONTAINER_RETRY_DELAY: float = 30.0  # Wait before retrying container startup
GRACEFUL_SHUTDOWN_TIMEOUT: float = 10.0  # Max wait for in-flight tasks on shutdown
THREAD_JOIN_TIMEOUT: float = 5.0  # Max wait for thread join
APP_CONTAINER_HEALTH_TIMEOUT: int = 60  # Max wait for app container health check (1 minute)
APP_CONTAINER_START_TIMEOUT: int = 120  # Max wait for app container startup (2 minutes)

# Generation orchestration delays
GENERATION_BATCH_COOLDOWN: float = 5.0  # Seconds between generation batches (reduced)
HEALING_RETRY_DELAY: float = 10.0  # Delay between healing retries

# Service port mapping
ANALYZER_SERVICE_PORTS: Dict[str, int] = {
    'static-analyzer': 2001,
    'dynamic-analyzer': 2002,
    'performance-tester': 2003,
    'ai-analyzer': 2004
}


class PipelineExecutionService:
    """Background service for executing automation pipelines.
    
    Lifecycle:
    - Polls DB for pipelines with status='running'
    - For each running pipeline, executes the next pending job
    - Handles stage transitions (generation → analysis → done)
    - Auto-manages containers (start before analysis, stop after completion)
    - Supports parallel analysis execution with configurable limits
    
    Robustness Features:
    - Circuit breaker pattern per analyzer service (3 failures → 5min cooldown)
    - Exponential backoff retries (2s → 4s → 8s → 16s)
    - Per-service health checking (partial execution when some services unavailable)
    - Health check TTL (30s cache invalidation)
    - Graceful shutdown with in-flight task state preservation
    - File-based locking for SQLite compatibility (row locking is no-op in SQLite)
    """
    
    # Circuit breaker configuration
    CIRCUIT_BREAKER_THRESHOLD: int = 3  # Failures before circuit opens
    CIRCUIT_BREAKER_COOLDOWN: float = 300.0  # 5 minutes cooldown
    
    # Retry configuration (exponential backoff)
    MAX_STARTUP_RETRIES: int = 4  # Max retry attempts for analyzer startup
    BASE_RETRY_DELAY: float = 2.0  # Base delay in seconds (doubles each attempt)
    MAX_TASK_CREATION_RETRIES: int = 3  # Retries for task creation conflicts
    
    # Health check TTL
    HEALTH_CHECK_TTL: float = 30.0  # Invalidate health cache after 30 seconds
    
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
        
        # Parallel generation execution
        self._generation_executor: Optional[ThreadPoolExecutor] = None
        self._generation_futures: Dict[str, Dict[str, Future]] = {}  # pipeline_id -> {job_key -> Future}
        self._in_flight_generation: Dict[str, Set[str]] = {}  # pipeline_id -> set of job_keys
        
        # Analyzer health cache (per-service)
        self._analyzer_healthy: Optional[bool] = None
        self._analyzer_check_time: float = 0.0
        self._analyzer_check_interval: float = 60.0  # Re-check every 60 seconds
        self._service_health_cache: Dict[str, Dict[str, Any]] = {}  # service_name -> {healthy: bool, check_time: float}
        
        # Circuit breaker state (per-service)
        self._analyzer_failures: Dict[str, int] = {}  # service_name -> consecutive failures
        self._analyzer_cooldown_until: Dict[str, float] = {}  # service_name -> cooldown end time
        
        # Container management state
        self._containers_started_for: Set[str] = set()  # pipeline_ids with auto-started containers
        
        # App container tracking (model_slug, app_number) tuples started per pipeline
        self._app_containers_started: Dict[str, Set[tuple]] = {}  # pipeline_id -> {(model, app_num), ...}
        
        # Graceful shutdown state
        self._shutting_down: bool = False
        self._shutdown_event: threading.Event = threading.Event()
        
        self._log("INIT", f"PipelineExecutionService initialized (poll_interval={poll_interval})")
    
    def _log(self, context: str, msg: str, level: str = 'info') -> None:
        """Log with consistent formatting and context prefixes.
        
        Uses f-strings for message formatting (NOT printf-style %s).
        
        Logging format: [PIPELINE:{pipeline_id}:{context}] message
        
        Standard context prefixes:
        - INIT: Service initialization
        - GEN: Generation stage
        - ANAL: Analysis stage  
        - TASK: Task operations
        - HEALTH: Health checks
        - CIRCUIT: Circuit breaker
        - CONTAINER: Container ops
        - SHUTDOWN: Shutdown
        
        Example usage:
            self._log("GEN", f"Processing job {job_index} for {model_slug}")
        """
        log_func = getattr(logger, level, logger.info)
        
        # Build prefix based on current context
        if self._current_pipeline_id:
            prefix = f"[{self._current_pipeline_id}:{context}]"
        else:
            prefix = f"[PIPELINE:{context}]"
        
        log_func(f"{prefix} {msg}")
    
    def _get_analyzer_host(self, service_name: str) -> str:
        """Get the hostname for an analyzer service.
        
        In Docker environment, uses container names for inter-container communication.
        Falls back to localhost for local development.
        
        Args:
            service_name: Name of the analyzer service
            
        Returns:
            Hostname string (e.g., 'static-analyzer' in Docker, 'localhost' locally)
        """
        in_docker = os.environ.get('IN_DOCKER', '').lower() in ('true', '1', 'yes')
        
        if in_docker:
            # Use container names for Docker inter-container communication
            return service_name
        
        # Use environment variable if set, otherwise localhost
        return os.environ.get('ANALYZER_HOST', 'localhost')
    
    def _is_service_circuit_open(self, service_name: str) -> bool:
        """Check if service circuit breaker is open (service should be skipped).
        
        Returns True if the service has failed too many times and is in cooldown.
        """
        current_time = time.time()
        cooldown_until = self._analyzer_cooldown_until.get(service_name, 0)
        
        if current_time < cooldown_until:
            remaining = int(cooldown_until - current_time)
            self._log(
                "CIRCUIT", f"Service {service_name} circuit OPEN, {remaining}s remaining in cooldown",
                level='debug'
            )
            return True
        
        # Cooldown expired - reset circuit breaker if it was tripped
        if cooldown_until > 0 and current_time >= cooldown_until:
            self._log(
                "CIRCUIT", f"Service {service_name} cooldown expired, resetting circuit breaker"
            )
            self._analyzer_failures[service_name] = 0
            self._analyzer_cooldown_until[service_name] = 0
        
        return False
    
    def _record_service_failure(self, service_name: str) -> None:
        """Record a service failure and potentially open circuit breaker."""
        failures = self._analyzer_failures.get(service_name, 0) + 1
        self._analyzer_failures[service_name] = failures
        
        if failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            cooldown_end = time.time() + self.CIRCUIT_BREAKER_COOLDOWN
            self._analyzer_cooldown_until[service_name] = cooldown_end
            self._log(
                "CIRCUIT", f"Service {service_name} circuit breaker TRIPPED after {failures} failures. "
                f"Cooldown for {int(self.CIRCUIT_BREAKER_COOLDOWN)}s",
                level='warning'
            )
        else:
            self._log(
                "CIRCUIT", f"Service {service_name} failure recorded ({failures}/{self.CIRCUIT_BREAKER_THRESHOLD} before trip)",
                level='debug'
            )
    
    def _record_service_success(self, service_name: str) -> None:
        """Record a service success and reset failure counter."""
        if self._analyzer_failures.get(service_name, 0) > 0:
            self._log(
                "CIRCUIT", f"Service {service_name} success, resetting failure count",
                level='debug'
            )
        self._analyzer_failures[service_name] = 0
    
    def _get_service_health(self, service_name: str, force_refresh: bool = False) -> Dict[str, Any]:
        """Get health status for a specific analyzer service with TTL caching.
        
        Returns cached health if within TTL, otherwise performs fresh check.
        
        Args:
            service_name: Name of the analyzer service
            force_refresh: If True, bypass cache and check fresh
            
        Returns:
            Dict with 'healthy': bool, 'check_time': float, 'error': Optional[str]
        """
        current_time = time.time()
        cached = self._service_health_cache.get(service_name, {})
        
        # Return cached result if valid and not forcing refresh
        if not force_refresh and cached:
            cache_age = current_time - cached.get('check_time', 0)
            if cache_age < self.HEALTH_CHECK_TTL:
                return cached
        
        # Perform fresh health check using global constant
        port = ANALYZER_SERVICE_PORTS.get(service_name)
        if not port:
            return {
                'healthy': False,
                'check_time': current_time,
                'error': f'Unknown service: {service_name}'
            }
        
        # Check if circuit breaker is open
        if self._is_service_circuit_open(service_name):
            return {
                'healthy': False,
                'check_time': current_time,
                'error': 'Circuit breaker open (cooldown)',
                'circuit_open': True
            }
        
        # TCP port check
        import socket
        host = self._get_analyzer_host(service_name)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5.0)
            result = sock.connect_ex((host, port))
            sock.close()
            
            is_healthy = (result == 0)
            health_result = {
                'healthy': is_healthy,
                'check_time': current_time,
                'port': port,
                'host': host,
                'error': None if is_healthy else f'Port {port} not accessible'
            }
            
            # Update circuit breaker based on result
            if is_healthy:
                self._record_service_success(service_name)
            else:
                self._record_service_failure(service_name)
            
        except socket.error as e:
            health_result = {
                'healthy': False,
                'check_time': current_time,
                'error': str(e)
            }
            self._record_service_failure(service_name)
        
        # Cache the result
        self._service_health_cache[service_name] = health_result
        return health_result
    
    def _check_services_health(self, service_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """Check health of multiple services and return per-service status.
        
        Args:
            service_names: List of service names to check
            
        Returns:
            Dict mapping service_name -> health status dict
        """
        results = {}
        for service_name in service_names:
            results[service_name] = self._get_service_health(service_name)
        return results
    
    def _get_available_services(self, required_services: List[str]) -> tuple:
        """Determine which required services are available for partial execution.
        
        Implements Option B: Partial execution when some services unavailable.
        
        Args:
            required_services: List of services needed for analysis
            
        Returns:
            Tuple of (available_services, unavailable_services)
        """
        health_status = self._check_services_health(required_services)
        
        available = []
        unavailable = []
        
        for service_name, status in health_status.items():
            if status.get('healthy', False):
                available.append(service_name)
            else:
                unavailable.append(service_name)
                reason = status.get('error', 'Unknown')
                self._log(
                    "HEALTH", f"Service {service_name} unavailable: {reason}", level='warning'
                )
        
        if unavailable:
            self._log(
                "HEALTH", f"Partial execution mode: {len(available)}/{len(required_services)} services available. "
                f"Unavailable: {', '.join(unavailable)}",
                level='warning'
            )
        else:
            self._log(
                "HEALTH", f"All {len(required_services)} required services available"
            )
        
        return (available, unavailable)
    
    def _invalidate_health_cache(self, service_name: Optional[str] = None) -> None:
        """Invalidate health cache to force fresh checks.
        
        Args:
            service_name: If provided, only invalidate that service. Otherwise invalidate all.
        """
        if service_name:
            self._service_health_cache.pop(service_name, None)
            self._log("HEALTH", f"Invalidated cache for {service_name}", level='debug')
        else:
            self._service_health_cache.clear()
            self._analyzer_healthy = None
            self._log("HEALTH", "Invalidated all health caches", level='debug')
    
    def start(self):
        """Start the background execution thread."""
        if self._running:
            return
        
        self._running = True
        self._shutting_down = False
        self._shutdown_event.clear()
        
        # Initialize thread pool for parallel analysis
        self._analysis_executor = ThreadPoolExecutor(
            max_workers=MAX_ANALYSIS_WORKERS,
            thread_name_prefix="pipeline_analysis"
        )
        
        # Initialize thread pool for parallel generation
        self._generation_executor = ThreadPoolExecutor(
            max_workers=MAX_GENERATION_WORKERS,
            thread_name_prefix="pipeline_generation"
        )
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log("INIT", "PipelineExecutionService started")
    
    def stop(self):
        """Stop the background execution thread with graceful shutdown.
        
        Graceful shutdown process:
        1. Signal shutdown to main loop
        2. Wait for in-flight tasks to complete (with timeout)
        3. Persist state for any incomplete tasks
        4. Shutdown thread pools
        """
        self._log("SHUTDOWN", "Initiating graceful shutdown...")
        self._shutting_down = True
        self._running = False
        self._shutdown_event.set()
        
        # Wait for in-flight tasks with timeout
        start_time = time.time()
        while time.time() - start_time < GRACEFUL_SHUTDOWN_TIMEOUT:
            # Count in-flight work
            with _pipeline_state_lock:
                total_in_flight = sum(len(tasks) for tasks in self._in_flight_tasks.values())
                total_in_flight += sum(len(jobs) for jobs in self._in_flight_generation.values())
            
            if total_in_flight == 0:
                self._log("SHUTDOWN", "All in-flight tasks completed")
                break
            
            self._log("SHUTDOWN", f"Waiting for {total_in_flight} in-flight items... ({GRACEFUL_SHUTDOWN_TIMEOUT - (time.time() - start_time):.1f}s remaining)")
            time.sleep(1.0)
        else:
            # Timeout reached - persist incomplete state
            self._log("SHUTDOWN", "Timeout reached, persisting incomplete task state", level='warning')
            self._persist_incomplete_state()
        
        # Shutdown thread pools
        if self._analysis_executor:
            self._analysis_executor.shutdown(wait=True, cancel_futures=False)
            self._analysis_executor = None
        
        if self._generation_executor:
            self._generation_executor.shutdown(wait=True, cancel_futures=False)
            self._generation_executor = None
        
        if self._thread:
            self._thread.join(timeout=THREAD_JOIN_TIMEOUT)
        
        self._log("SHUTDOWN", "PipelineExecutionService stopped")
    
    def _persist_incomplete_state(self) -> None:
        """Persist state for incomplete tasks on forced shutdown.
        
        Records which tasks were in-flight so they can be recovered on restart.
        """
        with _pipeline_state_lock:
            for pipeline_id, task_ids in self._in_flight_tasks.items():
                if task_ids:
                    self._log("SHUTDOWN", f"Pipeline {pipeline_id} has {len(task_ids)} in-flight analysis tasks: {list(task_ids)}", level='warning')
            
            for pipeline_id, job_keys in self._in_flight_generation.items():
                if job_keys:
                    self._log("SHUTDOWN", f"Pipeline {pipeline_id} has {len(job_keys)} in-flight generation jobs: {list(job_keys)}", level='warning')
    
    def _run_loop(self):
        """Main execution loop - polls for and processes pipelines."""
        self._log("INIT", "Execution loop started")
        
        while self._running:
            # Check for shutdown signal
            if self._shutting_down:
                self._log("SHUTDOWN", "Shutdown signal received, exiting loop")
                break
            
            with (self._app.app_context() if self._app else _nullcontext()):
                try:
                    # Get running pipelines
                    pipelines = PipelineExecution.get_running_pipelines()

                    if not pipelines:
                        time.sleep(self.poll_interval)
                        continue

                    self._log("MAIN", f"Found {len(pipelines)} running pipeline(s)", level='debug')

                    # Process each running pipeline
                    for pipeline in pipelines:
                        try:
                            self._current_pipeline_id = pipeline.pipeline_id
                            self._process_pipeline(pipeline)
                        except Exception as e:
                            self._log(
                                "ERROR", f"Error processing pipeline {pipeline.pipeline_id}: {e}",
                                level='error'
                            )
                            # Mark pipeline as failed on exception
                            try:
                                pipeline.fail(str(e))
                                db.session.commit()
                                # Clean up containers on failure
                                self._stop_all_app_containers_for_pipeline(pipeline)
                                self._cleanup_pipeline_containers(pipeline.pipeline_id)
                                # Clean up generation tracking
                                self._cleanup_generation_tracking(pipeline.pipeline_id)
                            except Exception as cleanup_error:
                                self._log("ERROR", f"Failed to cleanup after pipeline error: {cleanup_error}", level='error')
                                try:
                                    db.session.rollback()
                                except Exception as rollback_error:
                                    self._log("ERROR", f"Critical: Failed to rollback session: {rollback_error}", level='critical')
                            finally:
                                # Ensure session is cleaned up
                                try:
                                    db.session.remove()
                                except Exception:
                                    pass
                        finally:
                            self._current_pipeline_id = None

                except Exception as e:
                    self._log("ERROR", f"Pipeline execution loop error: {e}", level='error')
                    # Clean up session on loop errors
                    try:
                        db.session.remove()
                    except Exception:
                        pass

                time.sleep(self.poll_interval)
    
    def _process_pipeline(self, pipeline: PipelineExecution):
        """Process a single pipeline - execute its next job or check completion."""
        # Debug: Log current state before getting next job (at debug level to reduce noise)
        status_val = pipeline.status.value if hasattr(pipeline.status, 'value') else str(pipeline.status)  # type: ignore[union-attr]
        self._log(
            "DEBUG", f"Pipeline {pipeline.pipeline_id}: stage={pipeline.current_stage}, job_index={pipeline.current_job_index}, status={status_val}",
            level='debug'  # Use debug level to prevent spam
        )
        
        # Handle analysis stage with parallel execution
        if pipeline.current_stage == 'analysis':
            self._process_analysis_stage(pipeline)
            return
        
        # Handle generation stage with parallel execution
        if pipeline.current_stage == 'generation':
            self._process_generation_stage(pipeline)
            return
        
        # Unknown stage - check completion
        self._check_stage_transition(pipeline)
    
    def _process_generation_stage(self, pipeline: PipelineExecution):
        """Process generation stage with parallel execution.
        
        This method:
        1. Submits generation jobs up to parallelism limit
        2. Tracks in-flight jobs and polls for completion
        3. Transitions to analysis stage when all jobs complete
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress
        config = pipeline.config
        
        # Log entry to this method for debugging
        total = progress.get('generation', {}).get('total', 0)
        completed = progress.get('generation', {}).get('completed', 0)
        failed = progress.get('generation', {}).get('failed', 0)
        self._log(
            "GEN", f"Processing generation stage: job_index={pipeline.current_job_index}, total={total}, completed={completed}, failed={failed}"
        )
        
        # Get parallelism settings from config
        # NOTE: Parallel generation works fine - circuit breaker protects against API failures
        gen_config = config.get('generation', {})
        gen_options = gen_config.get('options', {})
        use_parallel = gen_options.get('parallel', True)  # Default to parallel (original working config)
        max_concurrent = gen_options.get('maxConcurrentTasks', DEFAULT_MAX_CONCURRENT_GENERATION) if use_parallel else 1
        
        # Initialize tracking for this pipeline (thread-safe)
        with _pipeline_state_lock:
            if pipeline_id not in self._in_flight_generation:
                self._in_flight_generation[pipeline_id] = set()
            if pipeline_id not in self._generation_futures:
                self._generation_futures[pipeline_id] = {}
        
        # STEP 1: Check completed in-flight generation jobs
        self._check_completed_generation_jobs(pipeline)
        
        # STEP 2: Submit new jobs up to parallelism limit
        with _pipeline_state_lock:
            in_flight_count = len(self._in_flight_generation.get(pipeline_id, set()))
            in_flight_jobs = list(self._in_flight_generation.get(pipeline_id, set()))
        
        submitted_any = False
        jobs_remaining = total - (completed + failed) - in_flight_count
        
        # Log when at capacity with jobs waiting
        if in_flight_count >= max_concurrent and jobs_remaining > 0:
            self._log(
                "GEN", f"At capacity ({in_flight_count}/{max_concurrent}), waiting for in-flight jobs to complete. {jobs_remaining} jobs remaining to submit. In-flight: {in_flight_jobs}",
                level='debug'
            )
        
        # Submit jobs up to max_concurrent limit
        while in_flight_count < max_concurrent:
            job = pipeline.get_next_job()
            if job is None:
                break  # No more jobs to submit
            
            if job['stage'] != 'generation':
                # Shouldn't happen but safety check
                break
            
            # Get job key for duplicate tracking
            job_index = job.get('job_index', 0)
            model_slug = job.get('model_slug')
            template_slug = job.get('template_slug')
            job_key = f"{job_index}:{model_slug}:{template_slug}"
            
            # Check if already in-flight (thread-safe)
            with _pipeline_state_lock:
                if job_key in self._in_flight_generation.get(pipeline_id, set()):
                    self._log(
                        "GEN", f"Skipping duplicate generation job {job_key} (already in-flight)",
                        level='debug'
                    )
                    # Advance index to avoid infinite loop
                    pipeline.advance_job_index()
                    db.session.commit()
                    continue
            
            # Check if already completed (in results) - refresh from DB to get latest state
            db.session.refresh(pipeline)
            fresh_progress = pipeline.progress
            existing_results = fresh_progress.get('generation', {}).get('results', [])
            already_done = any(
                r.get('job_index') == job_index for r in existing_results
            )
            if already_done:
                self._log(
                    "GEN", f"Skipping generation job {job_index} (already completed)",
                    level='debug'
                )
                pipeline.advance_job_index()
                db.session.commit()
                continue
            
            # Submit generation job to thread pool FIRST
            # This adds to _in_flight_generation before we advance the index
            self._submit_generation_job(pipeline_id, job)
            
            # Only advance job_index AFTER job is successfully added to in-flight tracking
            # This prevents the index from advancing without the job being tracked
            pipeline.advance_job_index()
            db.session.commit()
            submitted_any = True
            
            self._log(
                "GEN", f"Job {job_index} ({model_slug} + {template_slug}) submitted successfully, job_index now {pipeline.current_job_index}"
            )
            
            with _pipeline_state_lock:
                in_flight_count = len(self._in_flight_generation.get(pipeline_id, set()))
        
        # STEP 3: Check if all generation is complete
        with _pipeline_state_lock:
            in_flight_count = len(self._in_flight_generation.get(pipeline_id, set()))
        
        # Refresh progress from DB
        db.session.refresh(pipeline)
        progress = pipeline.progress
        
        total = progress.get('generation', {}).get('total', 0)
        completed = progress.get('generation', {}).get('completed', 0)
        failed = progress.get('generation', {}).get('failed', 0)
        done = completed + failed
        
        if done >= total and in_flight_count == 0:
            # All generation complete - transition to analysis
            self._log(
                "GEN", f"Generation complete for {pipeline_id}: {completed}/{total} succeeded, {failed} failed (total results: {len(progress.get('generation', {}).get('results', []))})"
            )
            
            # NEW: Apply batch cooldown before transitioning to analysis
            # This gives the API time to stabilize after heavy generation workload
            batch_cooldown = gen_options.get('batchCooldown', GENERATION_BATCH_COOLDOWN)
            if batch_cooldown > 0:
                self._log(
                    "GEN", f"Applying {batch_cooldown}s cooldown before analysis stage"
                )
                time.sleep(batch_cooldown)
            
            progress['generation']['status'] = 'completed'
            pipeline.progress = progress
            pipeline.current_stage = 'analysis'
            pipeline.current_job_index = 0
            db.session.commit()
            
            # Clean up generation tracking
            with _pipeline_state_lock:
                self._in_flight_generation.pop(pipeline_id, None)
                self._generation_futures.pop(pipeline_id, None)
        else:
            # Log detailed state to help debug early completion issues
            self._log(
                "GEN", f"Generation progress for {pipeline_id}: done={done}/{total}, in_flight={in_flight_count}, results={len(progress.get('generation', {}).get('results', []))}",
                level='debug'
            )
        
        if submitted_any or done > 0:
            self._emit_progress_update(pipeline)
    
    def _submit_generation_job(self, pipeline_id: str, job: Dict[str, Any]) -> None:
        """Submit a generation job to the thread pool.
        
        Handles executor shutdown gracefully by recording failures and cleaning up
        in-flight tracking if submission fails.
        """
        job_index = job.get('job_index', 0)
        model_slug = job.get('model_slug')
        template_slug = job.get('template_slug')
        job_key = f"{job_index}:{model_slug}:{template_slug}"
        
        self._log(
            "GEN", f"Submitting generation job {job_index} for {pipeline_id}: {model_slug} + {template_slug}"
        )
        
        # Check if service is shutting down before attempting submission
        if self._shutting_down:
            self._log(
                "GEN", f"Service shutting down - skipping job {job_index} for {pipeline_id}",
                level='warning'
            )
            # Record as failed due to shutdown
            self._record_generation_result(pipeline_id, job, {
                'job_index': job_index,
                'model_slug': model_slug,
                'template_slug': template_slug,
                'success': False,
                'error': 'Service shutdown in progress',
            })
            return
        
        # Add to in-flight tracking FIRST (before attempting submit)
        with _pipeline_state_lock:
            self._in_flight_generation[pipeline_id].add(job_key)
        
        # Submit to thread pool with proper error handling
        if self._generation_executor:
            try:
                future = self._generation_executor.submit(
                    self._execute_generation_job_async,
                    pipeline_id,
                    job
                )
                with _pipeline_state_lock:
                    self._generation_futures[pipeline_id][job_key] = future
            except RuntimeError as e:
                # Handle "cannot schedule new futures after shutdown" error
                self._log(
                    "GEN", f"Failed to submit job {job_index} to executor: {e}",
                    level='error'
                )
                # Clean up in-flight tracking since job wasn't actually submitted
                with _pipeline_state_lock:
                    self._in_flight_generation.get(pipeline_id, set()).discard(job_key)
                # Record as failed
                self._record_generation_result(pipeline_id, job, {
                    'job_index': job_index,
                    'model_slug': model_slug,
                    'template_slug': template_slug,
                    'success': False,
                    'error': f'Executor submission failed: {e}',
                })
        else:
            # Fallback to synchronous execution
            self._log(
                "GEN", f"No executor for {pipeline_id}, running generation synchronously",
                level='warning'
            )
            self._execute_generation_job_sync(pipeline_id, job)
    
    def _execute_generation_job_async(self, pipeline_id: str, job: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a generation job in a thread pool worker.
        
        This runs in a background thread and must handle its own Flask context.
        Uses generation_v2 package when USE_GENERATION_V2=true (default).
        """
        job_index = job.get('job_index', 0)
        model_slug: str = job.get('model_slug') or 'unknown'
        template_slug: str = job.get('template_slug') or 'unknown'
        job_key = f"{job_index}:{model_slug}:{template_slug}"
        
        result: Dict[str, Any] = {
            'job_index': job_index,
            'model_slug': model_slug,
            'template_slug': template_slug,
            'success': False,
            'error': None,
            'app_number': None,
        }
        
        try:
            # Push Flask app context for this thread
            with (self._app.app_context() if self._app else _nullcontext()):
                self._log(
                    "GEN", f"Worker starting job {job_index}: {model_slug} + {template_slug}"
                )
                
                # Validate required parameters
                if model_slug == 'unknown' or template_slug == 'unknown':
                    result['error'] = "Missing model_slug or template_slug in job"
                    return result
                
                # Get pipeline for configuration
                pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
                if not pipeline:
                    result['error'] = f"Pipeline {pipeline_id} not found"
                    return result
                
                gen_config = pipeline.config.get('generation', {})
                gen_options = gen_config.get('options', {})
                
                # Use generation_v2 if enabled (default: true)
                if USE_GENERATION_V2:
                    result = self._execute_generation_v2(
                        pipeline_id, job_index, model_slug, template_slug, gen_options, result
                    )
                else:
                    result = self._execute_generation_legacy(
                        pipeline_id, job_index, model_slug, template_slug, pipeline, result
                    )
                
                self._log(
                    "GEN", f"Worker completed job {job_index}: {model_slug} app {result.get('app_number')} (success={result['success']})"
                )
                
        except Exception as e:
            self._log(
                "GEN", f"Worker job {job_index} failed: {str(e)}", level='error'
            )
            result['error'] = str(e)
        
        return result
    
    def _execute_generation_v2(
        self, 
        pipeline_id: str, 
        job_index: int, 
        model_slug: str, 
        template_slug: str,
        gen_options: Dict[str, Any],
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute generation using the simplified generation_v2 package."""
        from app.services.generation_v2 import (
            GenerationConfig, GenerationMode, get_generation_service
        )
        
        self._log("GEN", f"Using generation_v2 for job {job_index}")
        
        # Get generation service
        svc = get_generation_service()
        
        # Build config
        mode_str = gen_options.get('mode', 'guarded')
        app_num = job_index + 1  # App numbers are 1-based
        
        config = GenerationConfig(
            model_slug=model_slug,
            template_slug=template_slug,
            app_num=app_num,
            mode=GenerationMode.GUARDED if mode_str == 'guarded' else GenerationMode.UNGUARDED,
            max_tokens=gen_options.get('maxTokens', 32000),
            temperature=gen_options.get('temperature', 0.3),
        )
        
        # Run synchronous generation
        gen_result = svc.generate(config)
        
        # Map result
        result['success'] = gen_result.success
        result['app_number'] = app_num
        
        if not gen_result.success:
            result['error'] = gen_result.error_message
        
        return result
    
    def _execute_generation_legacy(
        self, 
        pipeline_id: str, 
        job_index: int, 
        model_slug: str, 
        template_slug: str,
        pipeline: PipelineExecution,
        result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute generation using the legacy generation.py service."""
        from app.services.generation import get_generation_service
        
        self._log("GEN", f"Using legacy generation for job {job_index}")
        
        svc = get_generation_service()
        batch_id = pipeline.pipeline_id
        gen_config = pipeline.config.get('generation', {})
        use_auto_fix = gen_config.get('use_auto_fix', False)
        
        # Run generation
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
                    generation_mode='guarded',
                    use_auto_fix=use_auto_fix,
                )
            )
        finally:
            loop.close()
        
        # Extract results
        app_number = gen_result.get('app_number') or gen_result.get('app_id') or gen_result.get('app_num')
        result['success'] = gen_result.get('success', True)
        result['app_number'] = app_number
        
        if not result['success']:
            result['error'] = '; '.join(gen_result.get('errors', ['Unknown error']))
        
        return result
    
    def _execute_generation_job_sync(self, pipeline_id: str, job: Dict[str, Any]) -> None:
        """Execute generation job synchronously (fallback)."""
        result = self._execute_generation_job_async(pipeline_id, job)
        self._record_generation_result(pipeline_id, job, result)
    
    def _check_completed_generation_jobs(self, pipeline: PipelineExecution) -> None:
        """Check which in-flight generation jobs have completed and record results."""
        pipeline_id = pipeline.pipeline_id
        
        with _pipeline_state_lock:
            futures = dict(self._generation_futures.get(pipeline_id, {}))
        
        for job_key, future in futures.items():
            if future.done():
                try:
                    result = future.result(timeout=0.1)
                except Exception as e:
                    result = {
                        'job_index': int(job_key.split(':')[0]) if ':' in job_key else 0,
                        'model_slug': job_key.split(':')[1] if ':' in job_key else 'unknown',
                        'template_slug': job_key.split(':')[2] if ':' in job_key else 'unknown',
                        'success': False,
                        'error': str(e),
                    }
                
                # Record result in pipeline
                self._record_generation_result(pipeline_id, {'job_key': job_key}, result)
                
                # Remove from tracking
                with _pipeline_state_lock:
                    self._in_flight_generation.get(pipeline_id, set()).discard(job_key)
                    self._generation_futures.get(pipeline_id, {}).pop(job_key, None)
                
                self._log(
                    "GEN", f"Completed job {job_key} removed from in-flight tracking. Success={result.get('success', False)}"
                )
    
    def _record_generation_result(self, pipeline_id: str, job: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Record a generation result in the pipeline progress."""
        # Re-fetch pipeline with fresh DB session
        pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
        if not pipeline:
            self._log("GEN", f"Cannot record result - pipeline {pipeline_id} not found", level='error')
            return
        
        record = {
            'job_index': result.get('job_index'),
            'model_slug': result.get('model_slug'),
            'template_slug': result.get('template_slug'),
            'app_number': result.get('app_number'),
            'success': result.get('success', False),
        }
        if result.get('error'):
            record['error'] = result['error']
        
        # Use pipeline method to add result (handles stage transition)
        stage_transitioned = pipeline.add_generation_result(record)
        
        self._log(
            "GEN", f"Recorded generation result for {pipeline_id} job {record.get('job_index', -1)}: success={record['success']}, stage_transitioned={stage_transitioned}"
        )
        
        db.session.commit()
    
    def _cleanup_generation_tracking(self, pipeline_id: str) -> None:
        """Clean up generation tracking state for a pipeline.
        
        Called when a pipeline completes, fails, or is cancelled.
        """
        with _pipeline_state_lock:
            # Cancel any pending generation futures
            futures = self._generation_futures.pop(pipeline_id, {})
            for job_key, future in futures.items():
                if not future.done():
                    future.cancel()
                    self._log(
                        "CLEANUP", f"Cancelled generation job {job_key} for pipeline {pipeline_id}", level='debug'
                    )
            
            # Clear in-flight tracking
            self._in_flight_generation.pop(pipeline_id, None)
        
        self._log("CLEANUP", f"Cleaned up generation tracking for pipeline {pipeline_id}", level='debug')
    
    def _process_analysis_stage(self, pipeline: PipelineExecution):
        """Process analysis stage with parallel execution.
        
        This method:
        1. Clears health cache for new pipelines (prevents stale health data)
        2. Starts containers if needed (first time in analysis stage)
        3. Submits analysis tasks up to parallelism limit
        4. Tracks in-flight tasks and polls for completion
        5. Transitions to done stage when all tasks complete
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
                # FIX: Clear health cache when starting a new pipeline's analysis
                # This prevents stale health data from previous pipelines affecting this one
                self._invalidate_health_cache()
                self._log("ANAL", "Cleared health cache for new pipeline analysis stage")
        
        # STEP 1: Start containers if this is the first analysis job
        # NOTE: Analyzer container startup is a "soft requirement" - we warn but continue
        # Individual tasks will naturally succeed (static analysis) or skip (dynamic/perf)
        # based on container availability. This prevents pipeline abort on transient failures.
        with _pipeline_state_lock:
            containers_already_started = pipeline_id in self._containers_started_for
        
        if pipeline.current_job_index == 0 and not containers_already_started:
            # Check if selected tools actually require analyzer containers
            tools = config.get('analysis', {}).get('tools', [])
            needs_containers = self._requires_analyzer_containers(tools)

            if not needs_containers:
                # Static analysis only - skip container startup entirely
                self._log(
                    "ANAL", f"Skipping analyzer container startup for {pipeline_id} - static analysis tools only ({', '.join(tools)})"
                )
                with _pipeline_state_lock:
                    self._containers_started_for.add(pipeline_id)
            else:
                auto_start = analysis_opts.get('autoStartContainers', True)  # Default to True for pipelines
                if auto_start:
                    # Try to start analyzers with longer timeout (180s default)
                    analyzers_ready = self._ensure_analyzers_healthy(pipeline)

                    if analyzers_ready:
                        with _pipeline_state_lock:
                            self._containers_started_for.add(pipeline_id)
                        # Additional stabilization delay after startup to ensure ports are fully bound
                        time.sleep(5)
                        self._log("ANAL", "Analyzer containers ready, added 5s stabilization delay")
                    else:
                        # Retry once more after a longer delay (containers may still be starting)
                        self._log(
                            "ANAL", "First analyzer startup attempt failed, retrying after 30s delay...",
                            level='warning'
                        )
                        time.sleep(30)

                        # Second attempt - reset cache to force fresh check
                        self._analyzer_healthy = None
                        analyzers_ready = self._ensure_analyzers_healthy(pipeline)

                        if analyzers_ready:
                            with _pipeline_state_lock:
                                self._containers_started_for.add(pipeline_id)
                            time.sleep(5)  # Stabilization delay
                            self._log("ANAL", "Analyzer containers ready on retry")
                        else:
                            # Log warning but continue - static analysis and individual tasks
                            # will handle their own dependencies
                            self._log(
                                "ANAL", "WARNING: Analyzer containers could not be started after retry. "
                                "Static analysis will continue. Dynamic/performance analysis "
                                "will skip or fail for apps without running containers.",
                                level='warning'
                            )
                            # Still mark as "attempted" to avoid retry on every poll
                            with _pipeline_state_lock:
                                self._containers_started_for.add(pipeline_id)
                else:
                    # Auto-start disabled - check if containers are healthy anyway
                    if not self._check_analyzers_running():
                        # Log warning but continue - let tasks handle their own dependencies
                        self._log(
                            "ANAL", "WARNING: Analyzer services not running and auto-start disabled. "
                            "Analysis tasks may partially succeed or skip dynamic/performance tests. "
                            "To enable all analysis types, start containers via: ./start.ps1 -Mode Start",
                            level='warning'
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
            
            # Skip if generation failed for this job
            if not job.get('success', False):
                # Advance job_index and mark skipped atomically
                pipeline.advance_job_index()
                pipeline.add_analysis_task_id('skipped:generation_failed', success=False,
                                              model_slug=model_slug, app_number=app_number)
                db.session.commit()
                self._log("ANAL", f"Skipping analysis for {model_slug} app {app_number} - generation failed")
                continue
            
            # FIX: Check if this model:app combo was already submitted (duplicate guard)
            progress = pipeline.progress
            submitted_apps = progress.get('analysis', {}).get('submitted_apps', [])
            
            if job_key in submitted_apps:
                # Already submitted - just advance the index
                pipeline.advance_job_index()
                db.session.commit()
                self._log("ANAL", f"Skipping duplicate analysis submission for {model_slug} app {app_number} (already in submitted_apps)")
                continue
            
            # Double-check against existing main_task_ids (belt-and-suspenders)
            main_task_ids = progress.get('analysis', {}).get('main_task_ids', [])
            already_submitted = False
            for task_id in main_task_ids:
                if task_id.startswith('skipped') or task_id.startswith('error:'):
                    continue
                existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
                if (existing_task and 
                    existing_task.target_model == model_slug and 
                    existing_task.target_app_number == app_number):
                    self._log("ANAL", f"Skipping duplicate analysis for {model_slug} app {app_number} (already have task {task_id})")
                    already_submitted = True
                    break
            
            if already_submitted:
                pipeline.advance_job_index()
                db.session.commit()
                continue
            
            # FIX TRANSACTION BOUNDARY: Advance job_index AFTER successful task creation
            # We'll use a savepoint pattern to rollback only the job_index if task creation fails
            saved_job_index = pipeline.current_job_index
            
            # Submit analysis task (this creates the task in DB)
            task_id = self._submit_analysis_task(pipeline, job)
            
            # Only advance job_index if task was successfully created
            if task_id and not task_id.startswith('error:') and not task_id.startswith('skipped'):
                pipeline.advance_job_index()
                with _pipeline_state_lock:
                    self._in_flight_tasks[pipeline_id].add(task_id)
                in_flight_count += 1
                db.session.commit()
            elif task_id and task_id.startswith('skipped'):
                # Skipped tasks still advance the index (they're "handled")
                pipeline.advance_job_index()
                db.session.commit()
            else:
                # Error creating task - still advance index to avoid infinite loop
                # but mark as retryable in progress if it was a transient error
                pipeline.advance_job_index()
                # Check if this was a transient error that should allow retry
                if task_id and 'transient' in task_id.lower():
                    # Remove from submitted_apps to allow retry
                    self._mark_job_retryable(pipeline, model_slug, app_number)
                db.session.commit()
                self._log("ANAL", f"Task creation failed for {model_slug} app {app_number}: {task_id}", level='warning')
        
        # STEP 4: Check if all analysis is complete
        if self._check_analysis_tasks_completion(pipeline):
            # Analysis complete - commit completion status and stop containers
            db.session.commit()
            self._stop_all_app_containers_for_pipeline(pipeline)
            self._cleanup_pipeline_containers(pipeline_id)
        
        self._emit_progress_update(pipeline)
    
    def _mark_job_retryable(self, pipeline: PipelineExecution, model_slug: str, app_number: int) -> None:
        """Mark a job as retryable by removing it from submitted_apps.
        
        This allows the job to be retried on the next pipeline resume.
        """
        progress = pipeline.progress
        job_key = f"{model_slug}:{app_number}"
        submitted_apps = progress.get('analysis', {}).get('submitted_apps', [])
        
        if job_key in submitted_apps:
            submitted_apps.remove(job_key)
            progress['analysis']['submitted_apps'] = submitted_apps
            pipeline.progress = progress
            self._log("ANAL", f"Marked {job_key} as retryable (removed from submitted_apps)")
    
    def _submit_analysis_task(self, pipeline: PipelineExecution, job: Dict[str, Any]) -> str:
        """Create and submit a single analysis task.

        Returns task_id on success, or error/skipped marker on failure.
        
        Uses task registry for cross-service coordination to prevent race conditions.
        """
        from app.services.task_registry import get_task_registry
        
        model_slug = job['model_slug']
        app_number = job['app_number']
        pipeline_id = pipeline.pipeline_id
        
        task_registry = get_task_registry()
        
        # STEP 0: Check task registry for existing claim or task
        existing_task_id = task_registry.get_existing_task_id(model_slug, app_number, pipeline_id)
        if existing_task_id:
            self._log(
                "ANAL", f"Task already exists in registry for {model_slug} app {app_number}: {existing_task_id}"
            )
            return existing_task_id
        
        # Try to claim the task slot
        if not task_registry.try_claim_task(model_slug, app_number, pipeline_id, caller="PipelineExecutionService"):
            self._log(
                "ANAL", f"Could not claim task slot for {model_slug} app {app_number} - another service is creating it",
                level='warning'
            )
            # Return a marker indicating we should skip (another service handling it)
            return f'skipped:claimed_by_other_service:{model_slug}:{app_number}'

        # CRITICAL: Use SELECT FOR UPDATE to prevent race conditions
        # This locks the pipeline row until transaction commits, preventing concurrent duplicate creation
        # Refresh pipeline from DB with lock
        from sqlalchemy import select
        stmt = select(PipelineExecution).filter_by(pipeline_id=pipeline_id).with_for_update()
        pipeline = db.session.execute(stmt).scalar_one()

        # Check for duplicate task (prevents issues on server restart)
        progress = pipeline.progress
        existing_task_ids = progress.get('analysis', {}).get('task_ids', [])
        submitted_apps = progress.get('analysis', {}).get('submitted_apps', [])
        job_key = f"{model_slug}:{app_number}"

        # Check submitted_apps first (fastest check)
        if job_key in submitted_apps:
            self._log(
                "ANAL", f"Skipping duplicate analysis task for {model_slug} app {app_number} (in submitted_apps)"
            )
            # Find and return existing task_id
            for task_id in existing_task_ids:
                if task_id.startswith('skipped') or task_id.startswith('error:'):
                    continue
                existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
                if (existing_task and
                    existing_task.target_model == model_slug and
                    existing_task.target_app_number == app_number):
                    return task_id
            # Shouldn't reach here, but return marker if inconsistent state
            return f'error:duplicate_inconsistent_{model_slug}_{app_number}'

        # Double-check against existing tasks (belt-and-suspenders)
        for task_id in existing_task_ids:
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                continue
            existing_task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if (existing_task and
                existing_task.target_model == model_slug and
                existing_task.target_app_number == app_number):
                self._log(
                    "ANAL", f"Skipping duplicate analysis task for {model_slug} app {app_number} (already have {task_id})"
                )
                return task_id  # Return existing task ID
        
        # STEP 1: Validate app exists before attempting analysis
        exists, app_path, validation_msg = self._validate_app_exists(model_slug, app_number)
        if not exists:
            # Release registry claim before returning
            task_registry.release_claim(model_slug, app_number, pipeline_id)
            
            self._log(
                "ANAL", f"Skipping analysis for {model_slug} app {app_number}: {validation_msg}",
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
            self._log("ANAL", f"Starting containers for {model_slug} app {app_number}...")
            start_result = self._start_app_containers(pipeline_id, model_slug, app_number)
            if not start_result.get('success'):
                # Log warning but continue - analysis might still work (e.g., static analysis)
                self._log(
                    "ANAL", f"App container startup failed for {model_slug} app {app_number}, continuing with analysis anyway: {start_result.get('error', 'Unknown')}",
                    level='warning'
                )
            else:
                # SUCCESS: Containers started - wait for them to be healthy
                self._log("ANAL", f"Containers started for {model_slug} app {app_number}, waiting for health check...")
                health_result = self._wait_for_app_containers_healthy(model_slug, app_number, timeout=APP_CONTAINER_HEALTH_TIMEOUT)
                if health_result.get('healthy'):
                    self._log("ANAL", f"Containers healthy for {model_slug} app {app_number} (took {health_result.get('elapsed_time', 0):.1f}s)")
                else:
                    self._log(
                        "ANAL", f"Container health check timed out for {model_slug} app {app_number} after {health_result.get('elapsed_time', 0):.1f}s, continuing anyway: {health_result.get('message', 'Unknown')}",
                        level='warning'
                    )

        self._log("ANAL", f"Creating analysis task for {model_slug} app {app_number}")
        
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
                    self._log("ANAL", f"Tool '{tool_name}' not found or unavailable", level='warning')
            
            if not tools_by_service or not valid_tool_names:
                # Release registry claim before returning
                task_registry.release_claim(model_slug, app_number, pipeline_id)
                
                self._log(
                    "ANAL", f"No valid tools found for {model_slug} app {app_number}", level='error'
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
            
            # Register task in task registry (cross-service coordination)
            task_registry.mark_task_created(model_slug, app_number, pipeline_id, task.task_id)
            
            # Query subtask IDs for proper tracking
            subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
            subtask_ids = [st.task_id for st in subtasks]
            
            # Add main task with subtask IDs for proper tracking
            pipeline.add_analysis_task_id(
                task.task_id, 
                success=True,
                model_slug=model_slug, 
                app_number=app_number,
                is_main_task=True,
                subtask_ids=subtask_ids
            )
            
            self._log(
                "ANAL", f"Created analysis task {task.task_id} for {model_slug} app {app_number} (unified={len(tools_by_service) > 1}, services={len(tools_by_service)}, tools={len(valid_tool_names)}, subtasks={len(subtask_ids)})"
            )
            return task.task_id
            
        except Exception as e:
            # Release registry claim on error
            task_registry.release_claim(model_slug, app_number, pipeline_id)
            
            self._log(
                "ANAL", f"Analysis task creation failed for {model_slug} app {app_number}: {e}",
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
                    "ANAL", f"Task {task_id} completed with status {task.status.value if task.status else 'unknown'}"
                )
    
    def _requires_analyzer_containers(self, tools: list[str]) -> bool:
        """Check if selected tools require analyzer microservice containers.

        Static analysis tools (semgrep, bandit, eslint, etc.) run directly in
        the Flask app process and don't need analyzer microservices.

        Dynamic analysis and performance testing tools require analyzer containers.

        Args:
            tools: List of tool names selected for analysis

        Returns:
            True if any tool requires analyzer containers, False if all are static
        """
        # Tools that run without analyzer containers (static analysis)
        STATIC_TOOLS = {
            'semgrep',
            'bandit',
            'eslint',
            'flake8',
            'mypy',
            'pylint',
            'safety',
            'pip-audit',
        }

        # If no tools specified, assume containers needed (conservative)
        if not tools:
            return True

        # Convert to set for efficient lookup
        selected_tool_set = set(tools)

        # If all selected tools are static, no containers needed
        return not selected_tool_set.issubset(STATIC_TOOLS)

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
            self._log("ANALYZER", f"Error checking analyzer status: {e}", level='error')
            return False
    
    def _cleanup_pipeline_containers(self, pipeline_id: str):
        """Stop containers if they were auto-started for this pipeline (thread-safe).
        
        Also clears task registry entries for this pipeline.
        """
        # Clean up task registry entries for this pipeline
        try:
            from app.services.task_registry import get_task_registry
            task_registry = get_task_registry()
            cleared = task_registry.clear_pipeline(pipeline_id)
            if cleared > 0:
                self._log("CLEANUP", f"Cleared {cleared} task registry entries for pipeline {pipeline_id}")
        except Exception as e:
            self._log("CLEANUP", f"Error clearing task registry: {e}", level='warning')
        
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
            
            self._log("CONTAINER", f"Stopping analyzer containers (auto-started for pipeline {pipeline_id})")
            manager.stop_services()
            
        except Exception as e:
            self._log("CONTAINER", f"Error stopping containers: {e}", level='warning')
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
        """Build and start containers for a generated app before analysis.

        This method:
        1. Checks if containers already exist and are running
        2. If not, builds the Docker images first (required for dynamic/performance analysis)
        3. Then starts the containers

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
                "CONTAINER", f"Preparing containers for {model_slug} app {app_number} (pipeline {pipeline_id})"
            )

            # Check if containers already exist
            container_status = manager.get_container_status(model_slug, app_number)
            containers_exist = bool(container_status)
            containers_running = all(
                c.get('state') == 'running' 
                for c in container_status.values()
            ) if containers_exist else False

            if containers_running:
                self._log(
                    "CONTAINER", f"Containers already running for {model_slug} app {app_number}"
                )
                # Track that containers are running (even though we didn't start them)
                with _pipeline_state_lock:
                    if pipeline_id not in self._app_containers_started:
                        self._app_containers_started[pipeline_id] = set()
                    self._app_containers_started[pipeline_id].add((model_slug, app_number))
                return {'success': True, 'message': 'Containers already running'}

            # Build containers first if they don't exist (images need to be built)
            if not containers_exist:
                self._log(
                    "CONTAINER", f"Building containers for {model_slug} app {app_number} (no existing containers found)"
                )
                build_result = manager.build_containers(
                    model_slug, 
                    app_number,
                    no_cache=False,  # Use cache for faster builds
                    start_after=True  # Start containers after build
                )
                
                if build_result.get('success'):
                    # Track that we started these containers (thread-safe)
                    with _pipeline_state_lock:
                        if pipeline_id not in self._app_containers_started:
                            self._app_containers_started[pipeline_id] = set()
                        self._app_containers_started[pipeline_id].add((model_slug, app_number))
                    
                    self._log(
                        "CONTAINER", f"Successfully built and started containers for {model_slug} app {app_number}"
                    )
                    return build_result
                else:
                    self._log(
                        "CONTAINER", f"Failed to build containers for {model_slug} app {app_number}: {build_result.get('error', 'Unknown error')}",
                        level='warning'
                    )
                    return build_result

            # Containers exist but not running - just start them
            self._log(
                "CONTAINER", f"Starting existing containers for {model_slug} app {app_number}"
            )
            result = manager.start_containers(model_slug, app_number)

            if result.get('success'):
                # Track that we started these containers (thread-safe)
                with _pipeline_state_lock:
                    if pipeline_id not in self._app_containers_started:
                        self._app_containers_started[pipeline_id] = set()
                    self._app_containers_started[pipeline_id].add((model_slug, app_number))

                self._log(
                    "CONTAINER", f"Successfully started containers for {model_slug} app {app_number}"
                )
            else:
                self._log(
                    "CONTAINER", f"Failed to start containers for {model_slug} app {app_number}: {result.get('error', 'Unknown error')}",
                    level='warning'
                )

            return result

        except Exception as e:
            self._log(
                "CONTAINER", f"Error starting app containers for {model_slug} app {app_number}: {e}",
                level='error'
            )
            return {'success': False, 'error': str(e)}

    def _wait_for_app_containers_healthy(
        self,
        model_slug: str,
        app_number: int,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Wait for app containers to become healthy after startup.

        This prevents the race condition where tasks are created before containers are ready.

        Args:
            model_slug: The model slug
            app_number: The app number
            timeout: Max seconds to wait for healthy status

        Returns:
            Dict with 'healthy': bool, 'elapsed_time': float, 'message': str
        """
        try:
            from app.services.docker_manager import DockerManager
            import time

            manager = DockerManager()
            start_time = time.time()
            poll_interval = 2.0  # Check every 2 seconds

            while time.time() - start_time < timeout:
                # Get container status
                status = manager.get_container_health(model_slug, app_number)

                # Check if all containers are healthy
                all_healthy = status.get('all_healthy', False)

                if all_healthy:
                    elapsed = time.time() - start_time
                    return {
                        'healthy': True,
                        'elapsed_time': elapsed,
                        'message': f'All containers healthy after {elapsed:.1f}s'
                    }

                # Log progress every 10 seconds
                elapsed = time.time() - start_time
                if int(elapsed) % 10 == 0 and elapsed > 0:
                    containers = status.get('containers', {})
                    healthy_count = sum(1 for c in containers.values() if c.get('health') == 'healthy')
                    total_count = len(containers)
                    self._log(
                        "CONTAINER", f"Waiting for containers {model_slug} app {app_number}: {healthy_count}/{total_count} healthy ({elapsed:.1f}s elapsed)",
                        level='debug'
                    )

                time.sleep(poll_interval)

            # Timeout reached
            elapsed = time.time() - start_time
            status = manager.get_container_health(model_slug, app_number)
            containers = status.get('containers', {})
            healthy_count = sum(1 for c in containers.values() if c.get('health') == 'healthy')
            total_count = len(containers)

            return {
                'healthy': False,
                'elapsed_time': elapsed,
                'message': f'Timeout: {healthy_count}/{total_count} containers healthy after {elapsed:.1f}s'
            }

        except Exception as e:
            self._log(
                "CONTAINER", f"Error waiting for container health: {e}",
                level='error'
            )
            return {
                'healthy': False,
                'elapsed_time': 0.0,
                'message': f'Error checking health: {str(e)}'
            }
    
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
                "CONTAINER", f"Stopping containers for {model_slug} app {app_number} (pipeline {pipeline_id})"
            )
            
            result = manager.stop_containers(model_slug, app_number)
            
            if result.get('success'):
                # Remove from tracking (thread-safe)
                with _pipeline_state_lock:
                    if pipeline_id in self._app_containers_started:
                        self._app_containers_started[pipeline_id].discard((model_slug, app_number))
                
                self._log(
                    "CONTAINER", f"Successfully stopped containers for {model_slug} app {app_number}"
                )
            else:
                self._log(
                    "CONTAINER", f"Failed to stop containers for {model_slug} app {app_number}: {result.get('error', 'Unknown error')}",
                    level='warning'
                )
            
            return result
            
        except Exception as e:
            self._log(
                "CONTAINER", f"Error stopping app containers for {model_slug} app {app_number}: {e}",
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
            self._log("CONTAINER", f"stopAfterAnalysis disabled - keeping app containers running for pipeline {pipeline_id}")
            return
        
        self._log("CONTAINER", f"Stopping {len(started_apps)} app container sets for pipeline {pipeline_id}")
        
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
                    self._log("STAGE", f"Pipeline {pipeline.pipeline_id} (existing apps mode) transitioning to analysis stage")
                else:
                    # No analysis - complete pipeline
                    pipeline.status = PipelineExecutionStatus.COMPLETED
                    pipeline.completed_at = datetime.now(timezone.utc)
                    pipeline.current_stage = 'done'
                    self._log("STAGE", f"Pipeline {pipeline.pipeline_id} completed (existing apps, skipped analysis)")
            elif gen.get('status') == 'completed':
                # Generation complete - check if analysis is enabled
                if progress.get('analysis', {}).get('status') != 'skipped':
                    pipeline.current_stage = 'analysis'
                    pipeline.current_job_index = 0
                    progress['analysis']['status'] = 'running'
                    pipeline.progress = progress
                    self._log("STAGE", f"Pipeline {pipeline.pipeline_id} transitioning to analysis stage")
                else:
                    # No analysis - complete pipeline
                    pipeline.status = PipelineExecutionStatus.COMPLETED
                    pipeline.completed_at = datetime.now(timezone.utc)
                    pipeline.current_stage = 'done'
                    self._log("STAGE", f"Pipeline {pipeline.pipeline_id} completed (skipped analysis)")
        
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
        """Check actual completion status of MAIN analysis tasks from DB.
        
        Uses main_task_ids (not subtasks) for accurate job completion tracking.
        Subtasks are handled by their parent main task.
        
        Returns True if all main tasks have reached a terminal state and marks pipeline complete.
        """
        progress = pipeline.progress
        
        # Use main_task_ids for accurate counting (not subtasks)
        # Fall back to legacy task_ids if main_task_ids not populated
        main_task_ids = progress.get('analysis', {}).get('main_task_ids', [])
        if not main_task_ids:
            main_task_ids = progress.get('analysis', {}).get('task_ids', [])
        
        # Get expected number of analysis jobs
        config = pipeline.config
        gen_config = config.get('generation', {})
        generation_mode = gen_config.get('mode', 'generate')
        
        if generation_mode == 'existing':
            expected_jobs = len(gen_config.get('existingApps', []))
        else:
            gen_results = progress.get('generation', {}).get('results', [])
            expected_jobs = len(gen_results)
        
        if not main_task_ids:
            # No tasks created yet - check if jobs remain
            if expected_jobs > 0 and pipeline.current_job_index < expected_jobs:
                self._log(
                    "ANAL", f"Pipeline {pipeline.pipeline_id}: No analysis tasks yet, but {expected_jobs - pipeline.current_job_index} jobs remaining (index={pipeline.current_job_index})"
                )
                return False
            else:
                self._log(
                    "ANAL", f"Pipeline {pipeline.pipeline_id}: No analysis tasks to wait for (expected={expected_jobs}, index={pipeline.current_job_index})"
                )
                # Mark as complete
                pipeline.status = PipelineExecutionStatus.COMPLETED
                pipeline.completed_at = datetime.now(timezone.utc)
                pipeline.current_stage = 'done'
                return True
        
        completed_count = 0
        failed_count = 0
        pending_count = 0
        
        for task_id in main_task_ids:
            # Handle skipped/error markers
            if task_id.startswith('skipped') or task_id.startswith('error:'):
                failed_count += 1
                continue
            
            # Query actual task status (main task only, not subtasks)
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if not task:
                self._log("ANAL", f"Analysis task {task_id} not found in database", level='warning')
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
        
        total_main_tasks = len(main_task_ids)
        terminal_count = completed_count + failed_count
        
        self._log(
            "ANAL", f"Pipeline {pipeline.pipeline_id} analysis status: {terminal_count}/{total_main_tasks} main tasks terminal (completed={completed_count}, failed={failed_count}, pending={pending_count})"
        )
        
        # Must wait for ALL main tasks to reach terminal state
        if pending_count > 0:
            return False
        
        # Update pipeline progress with final counts
        pipeline.update_analysis_completion(completed_count, failed_count)
        
        self._log(
            "ANAL", f"Pipeline {pipeline.pipeline_id}: All {total_main_tasks} analysis main tasks finished ({completed_count} success, {failed_count} failed)"
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
                "GEN", f"Skipping duplicate generation for job {job_index}: {model_slug} with template {template_slug} (already in submitted_jobs)"
            )
            return False  # No stage transition (job was skipped)
        
        # Check 0b: Also check legacy format without job_index prefix (backwards compatibility)
        # This handles pipelines created with older code format
        if legacy_job_key in submitted_jobs:
            self._log(
                "GEN", f"Skipping duplicate generation for job {job_index}: {model_slug} with template {template_slug} (found legacy key in submitted_jobs)"
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
            "GEN", f"Marked job {job_index} as started (pre-emptive race prevention): {job_key}", level='debug'
        )
        
        # Check 1: Job-index-based detection (most reliable)
        for existing in existing_results:
            if existing.get('job_index') == job_index:
                self._log(
                    "GEN", f"Skipping job {job_index}: result already exists (model={existing.get('model_slug')}, template={existing.get('template_slug')}, app={existing.get('app_number', -1)})"
                )
                return False  # No stage transition (job was skipped)
        
        self._log(
            "GEN", f"Generating app for {model_slug} with template {template_slug} (job {job_index})"
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
                    "GEN", f"Warning: app_number not in result, using fallback: {app_number}", level='warning'
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
                "GEN", f"Generated {model_slug} app {app_number} with template {template_slug} (job {job_index}, stage_transitioned={stage_transitioned})"
            )
            
            return stage_transitioned
            
        except Exception as e:
            self._log(
                "GEN", f"Generation failed for {model_slug} with {template_slug} (job {job_index}): {e}",
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
        """Check and optionally start analyzer containers with circuit breaker and exponential backoff.
        
        Returns True if at least some analyzers are healthy (partial execution mode).
        Uses circuit breaker pattern to avoid repeated failures and exponential backoff
        for retry attempts.
        
        Robustness features:
        - Per-service health checking with TTL caching
        - Circuit breaker: 3 failures → 5 minute cooldown per service
        - Exponential backoff: 2s → 4s → 8s → 16s between retry attempts
        - Partial execution: Returns True if ANY services are available (Option B)
        """
        # Check global cache first (short-circuit for quick successive calls)
        current_time = time.time()
        if (self._analyzer_healthy is not None and 
            (current_time - self._analyzer_check_time) < self._analyzer_check_interval):
            return self._analyzer_healthy
        
        config = pipeline.config
        analysis_config = config.get('analysis', {})
        auto_start = analysis_config.get('autoStartContainers', 
                                         analysis_config.get('options', {}).get('autoStartContainers', True))
        
        # Define all analyzer services
        all_services = ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer']
        
        try:
            import sys
            from pathlib import Path
            from flask import current_app
            
            project_root = Path(current_app.root_path).parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            
            from analyzer.analyzer_manager import AnalyzerManager
            manager = AnalyzerManager()
            
            # Use new per-service health checking with circuit breaker integration
            available, unavailable = self._get_available_services(all_services)
            
            # Log initial status
            self._log(
                "ANALYZER", f"Initial health check: {len(available)}/{len(all_services)} services available"
            )
            
            # If all services available, we're good
            if len(available) == len(all_services):
                self._analyzer_healthy = True
                self._analyzer_check_time = current_time
                self._log("ANALYZER", "All analyzer containers healthy")
                return True
            
            # If some services unavailable and auto_start disabled, use partial execution
            if not auto_start:
                if available:
                    self._log(
                        "ANALYZER", f"Auto-start disabled. Partial execution with {len(available)}/{len(all_services)} services: {', '.join(available)}"
                    )
                    self._analyzer_healthy = True  # Partial is OK
                    self._analyzer_check_time = current_time
                    return True
                else:
                    self._log("ANALYZER", "Auto-start disabled and no services available", level='error')
                    self._analyzer_healthy = False
                    self._analyzer_check_time = current_time
                    return False
            
            # Auto-start enabled - attempt to start containers with exponential backoff
            self._log("ANALYZER", "Attempting to start analyzer containers...")
            
            # Check container status via AnalyzerManager
            containers = manager.get_container_status()
            all_running = all(
                c.get('state') == 'running'
                for c in containers.values()
            ) if containers else False
            
            # Retry loop with exponential backoff
            for attempt in range(self.MAX_STARTUP_RETRIES):
                # Calculate backoff delay: 2s, 4s, 8s, 16s
                if attempt > 0:
                    delay = self.BASE_RETRY_DELAY * (2 ** (attempt - 1))
                    self._log(
                        "ANALYZER", f"Retry attempt {attempt + 1}/{self.MAX_STARTUP_RETRIES} after {delay:.1f}s delay"
                    )
                    time.sleep(delay)
                
                # Start or restart containers
                if all_running:
                    self._log("ANALYZER", "Containers running but unhealthy, restarting...")
                    returncode, stdout, stderr = manager.run_command(
                        manager._compose_cmd + ['restart'], timeout=60
                    )
                else:
                    self._log("ANALYZER", "Starting analyzer containers...")
                    returncode, stdout, stderr = manager.run_command(
                        manager._compose_cmd + ['up', '-d'], timeout=60
                    )
                
                if returncode != 0:
                    self._log(
                        "ANALYZER", f"Container command failed (attempt {attempt + 1}/{self.MAX_STARTUP_RETRIES}): {stderr[:200] if stderr else 'Unknown error'}",
                        level='warning'
                    )
                    continue
                
                # Wait for services to become healthy with adaptive polling
                max_wait = int(os.environ.get('ANALYZER_STARTUP_TIMEOUT', 180))
                start_time = time.time()
                poll_interval = 2.0  # Start with 2s polling
                
                while time.time() - start_time < max_wait:
                    # Invalidate cache to force fresh checks
                    self._invalidate_health_cache()
                    
                    # Check which services are now available
                    available, unavailable = self._get_available_services(all_services)
                    
                    if len(available) == len(all_services):
                        # All services healthy
                        self._log("ANALYZER", f"All {len(all_services)} analyzer containers now healthy")
                        self._analyzer_healthy = True
                        self._analyzer_check_time = time.time()
                        return True
                    
                    if available and len(available) >= len(all_services) // 2:
                        # At least half are healthy - good enough for partial execution
                        elapsed = time.time() - start_time
                        self._log(
                            "ANALYZER", f"{len(available)}/{len(all_services)} services available after {elapsed:.1f}s. "
                            f"Proceeding with partial execution (unavailable: {', '.join(unavailable)})"
                        )
                        self._analyzer_healthy = True
                        self._analyzer_check_time = time.time()
                        return True
                    
                    # Adaptive polling: increase interval as we wait longer
                    elapsed = time.time() - start_time
                    if elapsed > 60:
                        poll_interval = 5.0
                    elif elapsed > 30:
                        poll_interval = 3.0
                    
                    time.sleep(poll_interval)
                
                # Timeout on this attempt - check if we have enough for partial execution
                available, unavailable = self._get_available_services(all_services)
                if available:
                    self._log(
                        "ANALYZER", f"Timeout on attempt {attempt + 1}/{self.MAX_STARTUP_RETRIES}, but {len(available)} services available. "
                        "Proceeding with partial execution.",
                        level='warning'
                    )
                    self._analyzer_healthy = True
                    self._analyzer_check_time = time.time()
                    return True
            
            # All retries exhausted - final check for partial execution
            self._invalidate_health_cache()
            available, unavailable = self._get_available_services(all_services)
            
            if available:
                self._log(
                    "ANALYZER", f"All {self.MAX_STARTUP_RETRIES} retry attempts exhausted. "
                    f"Partial execution with {len(available)}/{len(all_services)} services: {', '.join(available)}",
                    level='warning'
                )
                self._analyzer_healthy = True
                self._analyzer_check_time = time.time()
                return True
            
            self._log(
                "ANALYZER", f"Failed to start any analyzer containers after {self.MAX_STARTUP_RETRIES} attempts",
                level='error'
            )
            self._analyzer_healthy = False
            self._analyzer_check_time = time.time()
            return False
            
        except Exception as e:
            self._log("ANALYZER", f"Error during health check: {e}", level='error')
            self._analyzer_healthy = False
            self._analyzer_check_time = time.time()
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
    """Null context manager for compatibility with Python 3.7-3.9.

    Provides a no-op context manager that can be used as a substitute
    for contextlib.nullcontext (which was added in Python 3.10).
    Used when app_context is not needed.
    """
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
