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

from app.decorators import log_execution

from app.utils.logging_config import get_logger
from app.extensions import db, get_components
from app.models import PipelineExecution, PipelineExecutionStatus, GeneratedApplication, AnalysisTask
from app.constants import AnalysisStatus
from app.services.service_locator import ServiceLocator
from app.services.generation_v2.concurrent_runner import ConcurrentGenerationRunner, GenerationJob
from app.services.generation_v2.concurrent_analysis_runner import ConcurrentAnalysisRunner, AnalysisJobSpec

logger = get_logger("pipeline_executor")

# Thread safety lock for shared mutable state
_pipeline_state_lock = threading.RLock()

# =============================================================================
# CONFIGURATION CONSTANTS (formerly magic numbers)
# =============================================================================

# Feature flag for new generation system


# Parallelism limits
# NOTE: Pipeline generation uses parallel execution like the original working implementation
# The circuit breaker in rate_limiter.py protects against cascading API failures
# IMPORTANT: Analysis concurrency is limited to avoid overwhelming the server with container builds
# The ConcurrentAnalysisRunner has smart semaphore-based batching for container builds (max 2)
# so we can safely run 2-3 analyses concurrently without resource exhaustion
DEFAULT_MAX_CONCURRENT_TASKS: int = 2  # Default analysis concurrency (overridden by dynamic capacity)
DEFAULT_MAX_CONCURRENT_GENERATION: int = 5  # Increased default for parallel generation
MAX_ANALYSIS_WORKERS: int = 20  # Increased thread pool to support high concurrency
MAX_GENERATION_WORKERS: int = 10  # Increased thread pool for generation

# Timing constants (seconds)
DEFAULT_POLL_INTERVAL: float = 3.0  # Polling interval for work
CONTAINER_STABILIZATION_DELAY: float = 5.0  # Wait after container startup
CONTAINER_RETRY_DELAY: float = 30.0  # Wait before retrying container startup
GRACEFUL_SHUTDOWN_TIMEOUT: float = 10.0  # Max wait for in-flight tasks on shutdown
THREAD_JOIN_TIMEOUT: float = 5.0  # Max wait for thread join
APP_CONTAINER_HEALTH_TIMEOUT: int = 180  # Max wait for app container health check (3 minutes for slow builds)
APP_CONTAINER_START_TIMEOUT: int = 300  # Max wait for app container startup (5 minutes)

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

# Tools that can run without app containers (static analysis)
STATIC_ANALYSIS_TOOLS: Set[str] = {
    'semgrep',
    'bandit',
    'eslint',
    'flake8',
    'mypy',
    'pylint',
    'safety',
    'pip-audit',
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
    
    # Circuit breaker configuration - increased threshold for more resilience
    # Configurable via environment variables
    CIRCUIT_BREAKER_THRESHOLD: int = int(os.environ.get('CIRCUIT_BREAKER_THRESHOLD', '5'))
    CIRCUIT_BREAKER_COOLDOWN: float = float(os.environ.get('CIRCUIT_BREAKER_COOLDOWN', '120.0'))
    
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

        # Streaming analysis tracking (for immediate per-app analysis)
        self._submitted_analyses: Dict[str, Set[str]] = {}  # pipeline_id -> set of job_keys submitted

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

    def _add_event(
        self,
        pipeline: PipelineExecution,
        event_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        stage: Optional[str] = None,
        target: Optional[str] = None,
        level: str = 'info'
    ) -> None:
        """Add an event to the pipeline activity log for UI display.

        Events are stored in pipeline.progress['events'] and displayed in the
        live activity feed in the pipeline progress modal.

        Args:
            pipeline: The pipeline execution instance
            event_type: Type of event (e.g., 'generation_start', 'api_call', 'analysis_start')
            message: Human-readable event message
            details: Optional dict with additional details
            stage: Current stage ('generation' or 'analysis')
            target: Target identifier (e.g., 'model-slug/app1')
            level: Event level ('info', 'success', 'warning', 'error')

        Event types:
        - pipeline_start, pipeline_complete, pipeline_failed
        - generation_start, generation_api_call, generation_response, generation_building
        - generation_files, generation_complete, generation_failed
        - analysis_start, analysis_tool_start, analysis_tool_complete
        - analysis_complete, analysis_failed
        - container_start, container_stop, health_check
        """
        try:
            progress = pipeline.progress.copy() if pipeline.progress else {}
            events = progress.setdefault('events', [])

            # Keep last 100 events to avoid unbounded growth
            MAX_EVENTS = 100
            if len(events) >= MAX_EVENTS:
                events = events[-(MAX_EVENTS - 1):]

            event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'type': event_type,
                'message': message,
                'level': level,
            }

            if stage:
                event['stage'] = stage
            if target:
                event['target'] = target
            if details:
                event['details'] = details

            events.append(event)
            progress['events'] = events
            pipeline.progress = progress

            # Commit if we have an active session
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                # Event logging failure shouldn't break pipeline execution
                pass

        except Exception as e:
            # Event logging failure should never break pipeline execution
            logger.debug(f"Failed to add event: {e}")

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
    
    @log_execution()
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
    
    @log_execution()
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

    # =============================================================================
    # STREAMING ANALYSIS METHODS (Immediate per-app analysis)
    # =============================================================================

    def _should_start_analysis_early(self, pipeline: PipelineExecution) -> bool:
        """Check if streaming mode is enabled for this pipeline.

        Streaming mode triggers analysis IMMEDIATELY after each app generates,
        rather than waiting for all apps to complete (batch mode).

        Args:
            pipeline: The pipeline execution instance

        Returns:
            True if streaming mode enabled, False for batch mode
        """
        config = pipeline.config
        analysis_config = config.get('analysis', {})

        # Check if analysis is enabled at all
        if not analysis_config.get('enabled', True):
            self._log("ANAL", "Analysis disabled - using batch mode")
            return False

        # Check for explicit streaming mode flag (default: True for immediate analysis)
        streaming_mode = analysis_config.get('options', {}).get('streamingAnalysis', True)
        
        # Disable streaming for existing mode (must use batch to submit tasks)
        gen_config = config.get('generation', {})
        gen_mode = gen_config.get('mode')
        if gen_mode == 'existing':
            self._log("ANAL", f"Existing mode detected (gen_mode={gen_mode}) - forcing batch mode")
            return False
        
        self._log("ANAL", f"Streaming mode={streaming_mode}, gen_mode={gen_mode}")
        return streaming_mode

    def _trigger_immediate_analysis(
        self,
        pipeline_id: str,
        model_slug: str,
        app_number: int,
        tools: List[str]
    ) -> None:
        """Trigger analysis IMMEDIATELY for a single generated app (non-blocking).

        This method runs in the background thread pool to avoid blocking generation.
        It submits the analysis task and tracks it for completion monitoring.

        Args:
            pipeline_id: Pipeline ID
            model_slug: Generated app model slug
            app_number: Generated app number
            tools: List of analysis tools to run
        """
        # Check if already submitted
        job_key = f"{model_slug}:{app_number}"

        with _pipeline_state_lock:
            if job_key in self._submitted_analyses.get(pipeline_id, set()):
                self._log("ANAL", f"Analysis already submitted for {job_key}", level='debug')
                return

        self._log("ANAL", f"🚀 IMMEDIATE analysis dispatch: {model_slug}/app{app_number}")

        # Submit to analysis executor (non-blocking)
        if self._analysis_executor:
            future = self._analysis_executor.submit(
                self._execute_immediate_analysis,
                pipeline_id,
                model_slug,
                app_number,
                tools
            )

            # Track in-flight
            with _pipeline_state_lock:
                self._analysis_futures.setdefault(pipeline_id, {})[job_key] = future
                self._submitted_analyses.setdefault(pipeline_id, set()).add(job_key)
        else:
            self._log("ANAL", "Analysis executor not available - skipping immediate analysis", level='warning')

    def _execute_immediate_analysis(
        self,
        pipeline_id: str,
        model_slug: str,
        app_number: int,
        tools: List[str]
    ) -> None:
        """Execute immediate analysis in background thread with Flask app context.

        This runs in a thread pool worker and submits the analysis task to the system.

        Args:
            pipeline_id: Pipeline ID
            model_slug: Model slug
            app_number: App number
            tools: Analysis tools
        """
        # Ensure we have app context
        if self._app:
            with self._app.app_context():
                self._execute_immediate_analysis_impl(pipeline_id, model_slug, app_number, tools)
        else:
            self._execute_immediate_analysis_impl(pipeline_id, model_slug, app_number, tools)

    def _execute_immediate_analysis_impl(
        self,
        pipeline_id: str,
        model_slug: str,
        app_number: int,
        tools: List[str]
    ) -> None:
        """Implementation of immediate analysis execution.

        Args:
            pipeline_id: Pipeline ID
            model_slug: Model slug
            app_number: App number
            tools: Analysis tools
        """
        try:
            # Get pipeline from DB
            pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
            if not pipeline:
                self._log("ANAL", f"Pipeline {pipeline_id} not found", level='error')
                return

            # Create job spec
            job = {
                'model_slug': model_slug,
                'app_number': app_number,
            }

            # Submit analysis task using existing method
            task_id = self._submit_analysis_task(pipeline, job)

            # Track in pipeline progress
            progress = pipeline.progress
            analysis_progress = progress.setdefault('analysis', {})
            analysis_progress.setdefault('task_ids', []).append(task_id)
            analysis_progress.setdefault('submitted_apps', []).append(f"{model_slug}:{app_number}")
            pipeline.progress = progress
            db.session.commit()

            self._log("ANAL", f"✓ Immediate analysis task created: {task_id} for {model_slug}/app{app_number}")

        except Exception as e:
            self._log("ANAL", f"✗ Immediate analysis failed for {model_slug}/app{app_number}: {e}", level='error')
        finally:
            # Remove from in-flight tracking
            with _pipeline_state_lock:
                job_key = f"{model_slug}:{app_number}"
                if pipeline_id in self._analysis_futures:
                    self._analysis_futures[pipeline_id].pop(job_key, None)

    # =============================================================================
    # GENERATION STAGE
    # =============================================================================

    def _process_generation_stage(self, pipeline: PipelineExecution):
        """Process generation stage using ConcurrentGenerationRunner.
        
        This is a simplified implementation that:
        1. Checks if generation is already complete
        2. If not started, runs all jobs as a batch using ConcurrentGenerationRunner
        3. Records all results and transitions to analysis stage
        
        The new approach uses asyncio.Semaphore for clean concurrency control
        instead of the complex ThreadPoolExecutor state tracking.
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress
        config = pipeline.config
        
        # Define progress callback
        def on_progress(completed_count, total_count, result):
            """Callback for generation progress."""
            try:
                # Update pipeline progress in DB
                self._log("GEN", f"Progress: {completed_count}/{total_count} (Job {result.job_index} finished)")
                
                # We need to refresh pipeline from DB to avoid conflicts, or just update the field
                # Since we are in the main thread (or celery worker thread), we can use the session
                # But ConcurrentGenerationRunner runs in a loop.
                # Actually, the runner calls this callback.
                
                # Fetch fresh object or update dict
                # Note: 'pipeline' object might be detached if session was committed/removed?
                # Best to query fresh or assume attached.
                
                # Update progress dict
                p_data = pipeline.progress.copy()
                p_gen = p_data.get('generation', {})
                p_gen['completed'] = completed_count
                
                # Add result to list
                results_list = p_gen.get('results', [])
                
                # Check if result already exists (retry/duplicate safety)
                existing_idx = next((i for i, r in enumerate(results_list) if r.get('job_index') == result.job_index), None)
                
                record = {
                    'job_index': result.job_index,
                    'model_slug': result.model_slug,
                    'template_slug': result.template_slug,
                    'app_number': result.app_number,
                    'success': result.success,
                    'error': result.error,
                    'duration': result.duration_seconds
                }
                
                if existing_idx is not None:
                    results_list[existing_idx] = record
                else:
                    results_list.append(record)
                    
                p_gen['results'] = results_list
                
                if not result.success:
                    p_gen['failed'] = p_gen.get('failed', 0) + 1
                    
                p_data['generation'] = p_gen
                pipeline.progress = p_data
                
                db.session.commit()

                # Add event for UI activity feed
                target = f"{result.model_slug}/app{result.app_number}"
                if result.success:
                    self._add_event(
                        pipeline,
                        'generation_complete',
                        f"Generated {target} ({completed_count}/{total_count})",
                        details={
                            'model_slug': result.model_slug,
                            'template_slug': result.template_slug,
                            'app_number': result.app_number,
                            'duration': result.duration_seconds
                        },
                        stage='generation',
                        target=target,
                        level='success'
                    )
                else:
                    self._add_event(
                        pipeline,
                        'generation_failed',
                        f"Failed to generate {target}: {result.error or 'Unknown error'}",
                        details={
                            'model_slug': result.model_slug,
                            'template_slug': result.template_slug,
                            'error': result.error
                        },
                        stage='generation',
                        target=target,
                        level='error'
                    )

                # Emit socket event
                self._emit_progress_update(pipeline)

                # STREAMING MODE: Trigger immediate analysis if enabled
                if result.success and self._should_start_analysis_early(pipeline):
                    analysis_config = config.get('analysis', {})
                    tools = analysis_config.get('tools', [])
                    self._trigger_immediate_analysis(
                        pipeline_id=pipeline_id,
                        model_slug=result.model_slug,
                        app_number=result.app_number,
                        tools=tools
                    )

            except Exception as e:
                self._log("GEN", f"Error in progress callback: {e}", level='error')
        
        # Check current state
        gen_progress = progress.get('generation', {})
        total = gen_progress.get('total', 0)
        completed = gen_progress.get('completed', 0)
        failed = gen_progress.get('failed', 0)
        status = gen_progress.get('status', 'pending')

        # Safety check: If all jobs are processed but status isn't completed, fix it
        processed = completed + failed
        if processed >= total and total > 0 and status not in ['completed', 'skipped']:
            self._log(
                "GEN", f"Auto-fixing stuck generation: {processed}/{total} jobs done but status={status}, marking as completed",
                level='warning'
            )
            progress['generation']['status'] = 'completed'
            pipeline.progress = progress
            db.session.commit()
            status = 'completed'

        self._log(
            "GEN", f"Processing generation stage: status={status}, completed={completed}/{total}, failed={failed}"
        )

        # If already completed, transition to analysis
        if status == 'completed' or (completed + failed >= total and total > 0):
            self._log("GEN", f"Generation already complete, transitioning to analysis")
            self._transition_to_analysis(pipeline)
            return
        
        # If in-progress, we're waiting for async batch to complete
        if status == 'in_progress':
            self._log("GEN", "Generation in progress, waiting for completion", level='debug')
            return
        
        # Get generation config
        gen_config = config.get('generation', {})
        gen_options = gen_config.get('options', {})
        models = gen_config.get('models', [])
        templates = gen_config.get('templates', [])
        
        # Check if using 'existing' mode (no generation needed)
        generation_mode = gen_config.get('mode', 'generate')
        if generation_mode == 'existing':
            self._log("GEN", "Existing mode - skipping generation, transitioning to analysis")
            self._transition_to_analysis(pipeline)
            return
        
        if not models or not templates:
            self._log("GEN", "No models or templates configured, transitioning to analysis")
            self._transition_to_analysis(pipeline)
            return
        
        # Mark as in-progress before starting
        progress['generation']['status'] = 'in_progress'
        pipeline.progress = progress
        db.session.commit()

        # Get concurrency settings
        use_parallel = gen_options.get('parallel', True)
        max_concurrent = gen_options.get('maxConcurrentTasks', DEFAULT_MAX_CONCURRENT_GENERATION) if use_parallel else 1
        total_jobs = len(models) * len(templates)

        self._log(
            "GEN", f"Starting batch generation: {len(models)} models × {len(templates)} templates = {total_jobs} jobs (max_concurrent={max_concurrent})"
        )

        # Add pipeline event for UI
        self._add_event(
            pipeline,
            'generation_start',
            f"Starting generation: {total_jobs} apps ({len(models)} models × {len(templates)} templates)",
            details={'models': models, 'templates': templates, 'max_concurrent': max_concurrent},
            stage='generation',
            level='info'
        )
        
        # Build job list
        jobs = []
        job_index = 0
        for model_slug in models:
            for template_slug in templates:
                jobs.append(GenerationJob(
                    model_slug=model_slug,
                    template_slug=template_slug,
                    batch_id=pipeline_id,
                ))
                job_index += 1
        
        # Run batch generation using the clean ConcurrentGenerationRunner
        try:
            runner = ConcurrentGenerationRunner(
                max_concurrent=max_concurrent,
                inter_job_delay=1.0,  # Small delay between job starts
                on_progress=on_progress
            )
            
            # Run async batch - this blocks until all jobs complete
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(runner.generate_batch(jobs, batch_id=pipeline_id))
            finally:
                loop.close()
            
            # Record all results
            succeeded = 0
            failures = 0
            result_records = []
            
            for i, result in enumerate(results):
                record = {
                    'job_index': result.job_index,
                    'model_slug': result.model_slug,
                    'template_slug': result.template_slug,
                    'app_number': result.app_number,
                    'success': result.success,
                }
                if result.error:
                    record['error'] = result.error
                
                result_records.append(record)
                
                if result.success:
                    succeeded += 1
                else:
                    failures += 1
                
                self._log(
                    "GEN", f"Job {result.job_index}: {result.model_slug}/app{result.app_number} - {'SUCCESS' if result.success else 'FAILED'}"
                )
            
            # Update progress in DB
            db.session.refresh(pipeline)
            progress = pipeline.progress
            progress['generation']['results'] = result_records
            progress['generation']['completed'] = succeeded
            progress['generation']['failed'] = failures
            progress['generation']['status'] = 'completed'
            pipeline.progress = progress
            db.session.commit()
            
            self._log(
                "GEN", f"Batch generation complete: {succeeded}/{len(jobs)} succeeded, {failures} failed"
            )

            # Add completion event
            self._add_event(
                pipeline,
                'generation_stage_complete',
                f"Generation complete: {succeeded} succeeded, {failures} failed",
                details={'succeeded': succeeded, 'failed': failures, 'total': len(jobs)},
                stage='generation',
                level='success' if failures == 0 else 'warning'
            )

        except Exception as e:
            self._log("GEN", f"Batch generation failed: {e}", level='error')
            # Mark as failed
            db.session.refresh(pipeline)
            progress = pipeline.progress
            progress['generation']['status'] = 'failed'
            progress['generation']['error'] = str(e)
            pipeline.progress = progress
            db.session.commit()

            # Add failure event
            self._add_event(
                pipeline,
                'generation_stage_failed',
                f"Generation failed: {str(e)}",
                details={'error': str(e)},
                stage='generation',
                level='error'
            )
            raise
        
        # Transition to analysis
        self._transition_to_analysis(pipeline)
        self._emit_progress_update(pipeline)
    
    def _transition_to_analysis(self, pipeline: PipelineExecution):
        """Transition pipeline from generation to analysis stage."""
        pipeline.current_stage = 'analysis'
        pipeline.current_job_index = 0
        db.session.commit()
        self._log("GEN", f"Transitioned to analysis stage")

    
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
        Uses generation_v2 package.
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
                
                result = self._execute_generation_v2(
                    pipeline_id, job_index, model_slug, template_slug, gen_options, result
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
        """Execute generation using generation_v2 with auto-allocation."""
        from app.services.generation_v2 import get_generation_service

        self._log("GEN", f"Using generation_v2 for job {job_index}")

        svc = get_generation_service()
        batch_id = pipeline_id

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            gen_result = loop.run_until_complete(
                svc.generate_full_app(
                    model_slug=model_slug,
                    app_num=None,  # Let service handle allocation to avoid app number drift
                    template_slug=template_slug,
                    generate_frontend=True,
                    generate_backend=True,
                    batch_id=batch_id,
                    parent_app_id=None,
                    version=1,
                )
            )
        finally:
            loop.close()

        # Map result
        result['success'] = gen_result.get('success', False)
        app_number = gen_result.get('app_number')
        if app_number is None:
            app_number = gen_result.get('app_num')
        result['app_number'] = app_number

        if not result['success']:
            errors = gen_result.get('errors') or []
            result['error'] = "; ".join(errors) if errors else gen_result.get('error') or 'Unknown error'

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
    
    def _get_dynamic_analysis_capacity(self) -> int:
        """Calculate analysis capacity based on available container resources.
        
        Dynamically adjusts concurrency based on the number of active analyzer replicas.
        """
        try:
            from app.services.analyzer_manager_wrapper import AnalyzerManager
            
            # Check if using PooledAnalyzerManager (has get_pool_stats)
            if AnalyzerManager and hasattr(AnalyzerManager, 'get_pool_stats'):
                # Instantiate manager to access pool stats
                manager = AnalyzerManager()
                
                # Execute async method synchronously
                import asyncio
                if asyncio.iscoroutinefunction(manager.get_pool_stats):
                    stats = asyncio.run(manager.get_pool_stats())
                else:
                    stats = manager.get_pool_stats()
                
                if isinstance(stats, dict) and 'error' not in stats:
                    # Sum up healthy endpoints across all services
                    total_capacity = 0
                    for service_name, service_stats in stats.items():
                        if isinstance(service_stats, dict):
                            # We can run parallel tasks equal to total healthy endpoints
                            # e.g. 3 static + 2 dynamic + 2 perf + 2 ai = 9 concurrent slots
                            total_capacity += service_stats.get('healthy_endpoints', 0)
                    
                    if total_capacity > 0:
                        # Apply a multiplier? No, let's stick to 1:1 mapping for safety first,
                        # but multiply by 2 since most tools are IO bound? 
                        # Actually ConcurrentAnalysisRunner manages tasks, and tasks block on IO.
                        # The pool manages the queuing. 
                        # So we can set the concurrency limit high (e.g. 2x capacity)
                        # and let the pool queue requests.
                        # But for now, let's use exact capacity to be safe and responsive.
                        effective_capacity = total_capacity * 2  # 2x capacity for queuing efficiency
                        
                        self._log("ANAL", f"Detected dynamic analysis capacity: {total_capacity} endpoints -> {effective_capacity} concurrent slots")
                        return effective_capacity
                        
        except Exception as e:
            self._log("ANAL", f"Failed to detect dynamic capacity: {e}", level='debug')
            
        return DEFAULT_MAX_CONCURRENT_TASKS

    def _process_analysis_stage(self, pipeline: PipelineExecution):
        """Process analysis stage - streaming or batch mode.

        STREAMING MODE (default):
        - Analyses triggered immediately as apps generate (via generation callback)
        - This method monitors completion of in-flight tasks
        - Transitions to done when all expected tasks complete

        BATCH MODE (legacy):
        - Waits for ALL generation to complete
        - Runs all analyses as a batch using ConcurrentAnalysisRunner
        - Records results and transitions to done

        Mode is controlled by config['analysis']['options']['streamingAnalysis'] (default: True)
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress
        config = pipeline.config

        # Check if using streaming mode
        streaming_mode = self._should_start_analysis_early(pipeline)

        if streaming_mode:
            self._monitor_streaming_analysis(pipeline)
        else:
            self._process_batch_analysis(pipeline)

    def _monitor_streaming_analysis(self, pipeline: PipelineExecution):
        """Monitor streaming analysis tasks and check completion.

        In streaming mode, tasks are already submitted via generation callbacks.
        This method just monitors their progress and transitions when done.
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress

        # Get expected count from generation results
        gen_results = progress.get('generation', {}).get('results', [])
        expected_count = sum(1 for r in gen_results if r.get('success'))

        # Get current analysis progress
        analysis_progress = progress.get('analysis', {})
        task_ids = analysis_progress.get('task_ids', [])
        submitted_apps = analysis_progress.get('submitted_apps', [])

        # Count completed/failed tasks
        completed = 0
        failed = 0
        for task_id in task_ids:
            if task_id.startswith('skipped:') or task_id.startswith('error:'):
                failed += 1
                continue

            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if task:
                if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS):
                    completed += 1
                elif task.status == AnalysisStatus.FAILED:
                    failed += 1

        # Update progress
        analysis_progress['completed'] = completed
        analysis_progress['failed'] = failed
        analysis_progress['total'] = expected_count
        analysis_progress['status'] = 'in_progress'
        progress['analysis'] = analysis_progress
        pipeline.progress = progress
        db.session.commit()

        # Log progress (at debug level to reduce noise)
        self._log(
            "ANAL",
            f"Streaming analysis: {completed} completed, {failed} failed, {len(submitted_apps)}/{expected_count} submitted",
            level='debug'
        )

        # Check if all done
        if (completed + failed) >= expected_count and len(submitted_apps) >= expected_count:
            self._log("ANAL", f"Streaming analysis complete: {completed} succeeded, {failed} failed")
            analysis_progress['status'] = 'completed'
            progress['analysis'] = analysis_progress
            pipeline.progress = progress
            db.session.commit()
            self._transition_to_done(pipeline)

    def _process_batch_analysis(self, pipeline: PipelineExecution):
        """Process batch analysis (legacy mode).

        Runs all analyses as a batch after generation completes.
        """
        pipeline_id = pipeline.pipeline_id
        progress = pipeline.progress
        config = pipeline.config

        # Check current state
        analysis_progress = progress.get('analysis', {})
        total = analysis_progress.get('total', 0)
        completed = analysis_progress.get('completed', 0)
        failed = analysis_progress.get('failed', 0)
        status = analysis_progress.get('status', 'pending')
        
        self._log(
            "ANAL", f"Processing analysis stage: status={status}, completed={completed}/{total}, failed={failed}"
        )
        
        # If already completed, transition to done
        if status == 'completed' or (completed + failed >= total and total > 0):
            self._log("ANAL", "Analysis already complete, transitioning to done")
            self._transition_to_done(pipeline)
            return
        
        # If in-progress, we're waiting for async batch to complete
        if status == 'in_progress':
            self._log("ANAL", "Analysis in progress, waiting for completion", level='debug')
            return
        
        # Get analysis config
        analysis_config = config.get('analysis', {})
        if not analysis_config.get('enabled', True):
            self._log("ANAL", "Analysis disabled, transitioning to done")
            self._transition_to_done(pipeline)
            return
        
        # Get concurrency settings
        analysis_opts = analysis_config.get('options', {})
        config_limit = analysis_opts.get('maxConcurrentTasks', DEFAULT_MAX_CONCURRENT_TASKS)
        
        # Dynamic capacity detection (use dynamic if available, otherwise config default)
        dynamic_capacity = self._get_dynamic_analysis_capacity()
        
        # If dynamic capacity was detected (> default), use it.
        # Otherwise respect the config limit (which defaults to 2).
        # We take the MAX to allow scaling up, but if dynamic is default (2) and config is lower, use config?
        # No, if dynamic is 18, we want 18.
        max_concurrent = max(dynamic_capacity, config_limit)
        
        if max_concurrent > config_limit:
             self._log("ANAL", f"Using dynamic concurrency: {max_concurrent} (config limit: {config_limit})")
        tools = analysis_config.get('tools', [])
        auto_start_containers = analysis_opts.get('autoStartContainers', True)
        
        # Collect apps to analyze
        apps_to_analyze = []
        gen_config = config.get('generation', {})
        
        if gen_config.get('mode') == 'existing':
            # Existing mode - get from config
            existing_apps = gen_config.get('existingApps', [])
            for app_str in existing_apps:
                # Format: "model_slug:app_number" or dict
                if isinstance(app_str, dict):
                    apps_to_analyze.append({
                        'model_slug': app_str.get('model'),
                        'app_number': app_str.get('app')
                    })
                elif ':' in app_str:
                    parts = app_str.rsplit(':', 1)
                    apps_to_analyze.append({
                        'model_slug': parts[0],
                        'app_number': int(parts[1])
                    })
        else:
            # Generate mode - get from generation results
            gen_results = progress.get('generation', {}).get('results', [])
            for result in gen_results:
                if result.get('success'):
                    apps_to_analyze.append({
                        'model_slug': result.get('model_slug'),
                        'app_number': result.get('app_number'),
                    })
        
        if not apps_to_analyze:
            self._log("ANAL", "No successful generated apps to analyze, transitioning to done")
            self._transition_to_done(pipeline)
            return
        
        # Mark as in-progress before starting
        progress['analysis']['status'] = 'in_progress'
        progress['analysis']['total'] = len(apps_to_analyze)
        pipeline.progress = progress
        db.session.commit()
        
        self._log(
            "ANAL", f"Starting batch analysis: {len(apps_to_analyze)} apps (max_concurrent={max_concurrent})"
        )

        # Add event for UI
        self._add_event(
            pipeline,
            'analysis_start',
            f"Starting analysis: {len(apps_to_analyze)} apps with {len(tools)} tools",
            details={'app_count': len(apps_to_analyze), 'tools': tools, 'max_concurrent': max_concurrent},
            stage='analysis',
            level='info'
        )

        # Build job list
        jobs = []
        for app in apps_to_analyze:
            jobs.append(AnalysisJobSpec(
                model_slug=app['model_slug'],
                app_number=app['app_number'],
                tools=tools if tools else None,
                pipeline_id=pipeline_id,
            ))
        
        # Run batch analysis using ConcurrentAnalysisRunner with progress tracking
        try:
            # Progress callback to update pipeline status during analysis
            def on_analysis_progress(completed: int, total: int, result: Any):
                """Update pipeline progress as analyses complete."""
                try:
                    # Re-fetch pipeline to get fresh state
                    from app.extensions import db
                    fresh_pipeline = PipelineExecution.query.filter_by(pipeline_id=pipeline_id).first()
                    if not fresh_pipeline:
                        return

                    prog = fresh_pipeline.progress
                    prog['analysis']['completed'] = completed
                    prog['analysis']['status'] = 'in_progress'
                    fresh_pipeline.progress = prog
                    db.session.commit()

                    # Add event for each completed analysis
                    if result and hasattr(result, 'model_slug'):
                        target = f"{result.model_slug}/app{result.app_number}"
                        if result.success:
                            self._add_event(
                                fresh_pipeline,
                                'analysis_complete',
                                f"Completed analysis: {target} ({completed}/{total})",
                                details={
                                    'model_slug': result.model_slug,
                                    'app_number': result.app_number,
                                    'findings_count': getattr(result, 'findings_count', 0)
                                },
                                stage='analysis',
                                target=target,
                                level='success'
                            )
                        else:
                            self._add_event(
                                fresh_pipeline,
                                'analysis_failed',
                                f"Analysis failed: {target} - {getattr(result, 'error', 'Unknown error')}",
                                details={
                                    'model_slug': result.model_slug,
                                    'app_number': result.app_number,
                                    'error': getattr(result, 'error', None)
                                },
                                stage='analysis',
                                target=target,
                                level='error'
                            )

                    self._log(
                        "ANAL", f"Progress update: {completed}/{total} analyses complete",
                        level='debug'
                    )
                    self._emit_progress_update(fresh_pipeline)
                except Exception as e:
                    self._log("ANAL", f"Progress callback error: {e}", level='warning')

            runner = ConcurrentAnalysisRunner(
                max_concurrent_analysis=max_concurrent,
                max_concurrent_container_builds=2,  # Limit container builds
                on_progress=on_analysis_progress,  # Add progress callback
            )

            # Run async batch - this blocks until all jobs complete
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    runner.analyze_batch(
                        jobs,
                        pipeline_id=pipeline_id,
                        tools=tools,
                        auto_start_app_containers=auto_start_containers,
                    )
                )
            finally:
                loop.close()
            
            # Record all results with detailed status tracking
            succeeded = 0
            failures = 0
            partial_success = 0
            total_findings = 0
            result_records = []

            for result in results:
                record = {
                    'job_index': result.job_index,
                    'model_slug': result.model_slug,
                    'app_number': result.app_number,
                    'task_id': result.task_id,
                    'success': result.success,
                    'findings_count': result.findings_count,
                    'status': result.status,
                }
                if result.error:
                    record['error'] = result.error

                result_records.append(record)
                total_findings += result.findings_count

                # Track success types separately
                if result.status == 'completed':
                    succeeded += 1
                elif result.status == 'partial':
                    partial_success += 1
                    succeeded += 1  # Count partials as success for overall stats
                else:
                    failures += 1

                # Enhanced logging with duration
                duration_str = f"{result.duration_seconds:.1f}s" if hasattr(result, 'duration_seconds') else "N/A"
                self._log(
                    "ANAL", f"Job {result.job_index}: {result.model_slug}/app{result.app_number} - "
                    f"{result.status.upper()} in {duration_str} ({result.findings_count} findings)"
                )
            
            # Update progress in DB with comprehensive status
            db.session.refresh(pipeline)
            progress = pipeline.progress
            progress['analysis']['results'] = result_records
            progress['analysis']['completed'] = succeeded
            progress['analysis']['failed'] = failures
            progress['analysis']['partial_success'] = partial_success
            progress['analysis']['total_findings'] = total_findings
            progress['analysis']['status'] = 'completed'
            pipeline.progress = progress
            db.session.commit()

            # Enhanced completion logging
            self._log(
                "ANAL", f"Batch analysis complete: {succeeded}/{len(jobs)} succeeded "
                f"({partial_success} partial), {failures} failed, {total_findings} total findings"
            )

            # Add completion event
            self._add_event(
                pipeline,
                'analysis_stage_complete',
                f"Analysis complete: {succeeded} succeeded, {failures} failed ({total_findings} findings)",
                details={
                    'succeeded': succeeded,
                    'failed': failures,
                    'partial_success': partial_success,
                    'total_findings': total_findings
                },
                stage='analysis',
                level='success' if failures == 0 else 'warning'
            )

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self._log("ANAL", f"Batch analysis failed: {e}\n{error_details}", level='error')

            # Mark as failed but preserve any partial results
            try:
                db.session.refresh(pipeline)
                progress = pipeline.progress
                progress['analysis']['status'] = 'failed'
                progress['analysis']['error'] = str(e)

                # If we have any partial results from before the crash, preserve them
                if 'results' in progress.get('analysis', {}) and progress['analysis']['results']:
                    self._log(
                        "ANAL", f"Preserving {len(progress['analysis']['results'])} partial results despite failure",
                        level='warning'
                    )

                pipeline.progress = progress
                db.session.commit()
            except Exception as db_error:
                self._log("ANAL", f"Failed to update pipeline status: {db_error}", level='error')

            # Don't re-raise - transition to done anyway to allow pipeline cleanup
            # The error is already recorded in progress
            self._log("ANAL", "Transitioning to done stage despite analysis failure", level='warning')
        
        # Transition to done
        self._transition_to_done(pipeline)
        self._emit_progress_update(pipeline)
    
    def _transition_to_done(self, pipeline: PipelineExecution):
        """Transition pipeline from analysis to done stage."""
        from app.models import PipelineExecutionStatus

        pipeline.current_stage = 'done'
        pipeline.status = PipelineExecutionStatus.COMPLETED
        pipeline.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        # Add pipeline completion event
        progress = pipeline.progress
        gen_completed = progress.get('generation', {}).get('completed', 0)
        analysis_completed = progress.get('analysis', {}).get('completed', 0)
        total_findings = progress.get('analysis', {}).get('total_findings', 0)

        self._add_event(
            pipeline,
            'pipeline_complete',
            f"Pipeline completed: {gen_completed} apps generated, {analysis_completed} analyzed ({total_findings} findings)",
            details={
                'gen_completed': gen_completed,
                'analysis_completed': analysis_completed,
                'total_findings': total_findings
            },
            stage='done',
            level='success'
        )

        # Cleanup containers for this pipeline
        self._stop_all_app_containers_for_pipeline(pipeline)
        self._cleanup_pipeline_containers(pipeline.pipeline_id)

        self._log("ANAL", "Pipeline completed successfully")
    
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
        
        # STEP 2: Build and start app containers if autoStartContainers is enabled
        config = pipeline.config
        analysis_config = config.get('analysis', {})
        auto_start = analysis_config.get('autoStartContainers',
                                         analysis_config.get('options', {}).get('autoStartContainers', True))

        containers_ready = False
        container_failed = False
        
        if auto_start:
            self._log("ANAL", f"Building/starting containers for {model_slug} app {app_number}...")
            start_result = self._start_app_containers(pipeline_id, model_slug, app_number)
            
            if not start_result.get('success'):
                # Container build/start failed
                error_msg = start_result.get('error', 'Unknown')
                self._log(
                    "ANAL", f"App container startup failed for {model_slug} app {app_number}: {error_msg}",
                    level='warning'
                )
                # Static analysis can still proceed, dynamic/performance will be skipped
                container_failed = True
            else:
                # SUCCESS: Containers built/started - wait for them to be healthy or fail
                self._log("ANAL", f"Containers started for {model_slug} app {app_number}, waiting for health check...")
                health_result = self._wait_for_app_containers_healthy(
                    model_slug, app_number, timeout=APP_CONTAINER_HEALTH_TIMEOUT
                )
                
                if health_result.get('healthy'):
                    containers_ready = True
                    self._log(
                        "ANAL", f"Containers ready for {model_slug} app {app_number} (took {health_result.get('elapsed_time', 0):.1f}s)"
                    )
                elif health_result.get('failed'):
                    # Container crashed/exited with error - this is a permanent failure
                    container_failed = True
                    crash_info = health_result.get('crash_containers', [])
                    self._log(
                        "ANAL", f"Container FAILED for {model_slug} app {app_number}: {crash_info}. "
                        "Static analysis will proceed, dynamic/performance analysis will be skipped.",
                        level='error'
                    )
                else:
                    # Timeout but not crashed - containers may still be starting
                    self._log(
                        "ANAL", f"Container health check timed out for {model_slug} app {app_number} after "
                        f"{health_result.get('elapsed_time', 0):.1f}s. Proceeding with analysis anyway.",
                        level='warning'
                    )

        self._log("ANAL", f"Creating analysis task for {model_slug} app {app_number} (containers_ready={containers_ready}, container_failed={container_failed})")
        
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
            
            # [FALLBACK] If containers failed to build/start, downgrade to static analysis only
            if container_failed:
                original_tool_count = len(tools)
                # Filter to only keep static tools (case-insensitive check)
                tools = [t for t in tools if t.lower() in STATIC_ANALYSIS_TOOLS]
                
                self._log(
                    "ANAL", 
                    f"Container startup failed - downgrading to static analysis only. "
                    f"Filtered tools from {original_tool_count} to {len(tools)} (kept: {', '.join(tools)})", 
                    level='warning'
                )
                
                if not tools:
                    # If no tools remain (i.e., user only selected dynamic tools), we must fail the task
                    self._log("ANAL", "No static tools selected and containers failed - cannot proceed.", level='error')
                    task_registry.release_claim(model_slug, app_number, pipeline_id)
                    error_marker = 'error:containers_failed_no_static_tools'
                    pipeline.add_analysis_task_id(error_marker, success=False,
                                                  model_slug=model_slug, app_number=app_number)
                    return error_marker

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
            
            # ========== FIX: IMMEDIATELY DISPATCH SUBTASKS ==========
            # Instead of relying on TaskExecutionService daemon to pick up the task (which can
            # cause race conditions), dispatch subtasks directly here. This ensures tasks are
            # executed as soon as they're created.
            if subtask_ids:
                try:
                    # Mark main task as RUNNING before dispatch
                    task.status = AnalysisStatus.RUNNING
                    task.started_at = datetime.now(timezone.utc)
                    db.session.commit()
                    
                    # Get TaskExecutionService and dispatch subtasks
                    from app.services.service_locator import ServiceLocator
                    task_exec_service = ServiceLocator.get_task_execution_service()
                    
                    if task_exec_service:
                        self._log(
                            "ANAL", f"Dispatching {len(subtask_ids)} subtasks for {task.task_id} immediately"
                        )
                        dispatch_result = task_exec_service.submit_parallel_subtasks(
                            task.task_id, subtask_ids
                        )
                        dispatch_status = dispatch_result.get('status', 'unknown')
                        self._log(
                            "ANAL", f"Subtask dispatch for {task.task_id}: status={dispatch_status}"
                        )
                    else:
                        self._log(
                            "ANAL", f"TaskExecutionService not available - task {task.task_id} will be picked up by daemon",
                            level='warning'
                        )
                except Exception as dispatch_err:
                    # Log but don't fail - daemon can still pick up the task
                    self._log(
                        "ANAL", f"Failed to dispatch subtasks for {task.task_id}: {dispatch_err}. "
                        "Task will be picked up by daemon.",
                        level='warning'
                    )
            # ========== END FIX ==========
            
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
        # Tools that run without analyzer containers (static analysis)
        # Uses module-level constant STATIC_ANALYSIS_TOOLS
        
        # If no tools specified, assume containers needed (conservative)
        if not tools:
            return True

        # Convert to set for efficient lookup
        selected_tool_set = set(tools)

        # If all selected tools are static, no containers needed
        return not selected_tool_set.issubset(STATIC_ANALYSIS_TOOLS)

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
            container_list = manager.get_project_containers(model_slug, app_number)
            containers_exist = bool(container_list)
            containers_running = all(
                c.get('status') == 'running' 
                for c in container_list
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
                    no_cache=True,  # Always rebuild to ensure latest code is used
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
        timeout: int = 120
    ) -> Dict[str, Any]:
        """Wait for app containers to become healthy or fail with an error.

        This prevents the race condition where analysis starts before containers are ready.
        Also detects container crashes/failures early to fail fast.

        Args:
            model_slug: The model slug
            app_number: The app number
            timeout: Max seconds to wait for healthy status (default 120s)

        Returns:
            Dict with:
            - 'healthy': bool - True if containers are ready
            - 'failed': bool - True if containers crashed/failed (permanent failure)
            - 'elapsed_time': float
            - 'message': str
            - 'crash_containers': list (if failed)
        """
        try:
            from app.services.docker_manager import DockerManager
            import time

            manager = DockerManager()
            start_time = time.time()
            poll_interval = 3.0  # Check every 3 seconds
            last_log_time = 0

            self._log(
                "CONTAINER", f"Waiting for containers {model_slug} app {app_number} to become healthy (timeout={timeout}s)"
            )

            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time
                
                # First check for crash loops (fail fast on permanent errors)
                crash_check = manager._check_for_crash_loop(model_slug, app_number)
                if crash_check.get('has_crash_loop'):
                    crash_containers = crash_check.get('crash_containers', [])
                    self._log(
                        "CONTAINER", f"Container failure detected for {model_slug} app {app_number}: {crash_containers}",
                        level='error'
                    )
                    return {
                        'healthy': False,
                        'failed': True,
                        'elapsed_time': elapsed,
                        'message': f'Container crash/failure detected after {elapsed:.1f}s',
                        'crash_containers': crash_containers
                    }

                # Get container health status
                status = manager.get_container_health(model_slug, app_number)
                containers = status.get('containers', {})
                
                # Check if all containers are healthy
                all_healthy = status.get('all_healthy', False)

                if all_healthy:
                    self._log(
                        "CONTAINER", f"All containers healthy for {model_slug} app {app_number} after {elapsed:.1f}s"
                    )
                    return {
                        'healthy': True,
                        'failed': False,
                        'elapsed_time': elapsed,
                        'message': f'All containers healthy after {elapsed:.1f}s'
                    }

                # Check for exited containers (might be a build/startup failure)
                exited_containers = [
                    name for name, info in containers.items() 
                    if info.get('status') == 'exited'
                ]
                if exited_containers:
                    # Check if they exited with error codes
                    exit_errors = []
                    for name in exited_containers:
                        container_info = containers.get(name, {})
                        exit_code = container_info.get('exit_code', 0)
                        if exit_code != 0:
                            exit_errors.append({'name': name, 'exit_code': exit_code})
                    
                    if exit_errors:
                        self._log(
                            "CONTAINER", f"Container exit errors for {model_slug} app {app_number}: {exit_errors}",
                            level='error'
                        )
                        return {
                            'healthy': False,
                            'failed': True,
                            'elapsed_time': elapsed,
                            'message': f'Containers exited with errors after {elapsed:.1f}s',
                            'crash_containers': exit_errors
                        }

                # Log progress every 15 seconds
                if elapsed - last_log_time >= 15:
                    healthy_count = sum(1 for c in containers.values() if c.get('health') == 'healthy')
                    total_count = len(containers)
                    container_states = {name: info.get('status', 'unknown') for name, info in containers.items()}
                    self._log(
                        "CONTAINER", f"Waiting for {model_slug} app {app_number}: {healthy_count}/{total_count} healthy, states={container_states} ({elapsed:.1f}s elapsed)"
                    )
                    last_log_time = elapsed

                time.sleep(poll_interval)

            # Timeout reached - do final crash check
            elapsed = time.time() - start_time
            crash_check = manager._check_for_crash_loop(model_slug, app_number)
            
            if crash_check.get('has_crash_loop'):
                return {
                    'healthy': False,
                    'failed': True,
                    'elapsed_time': elapsed,
                    'message': f'Container crash detected at timeout after {elapsed:.1f}s',
                    'crash_containers': crash_check.get('crash_containers', [])
                }
            
            status = manager.get_container_health(model_slug, app_number)
            containers = status.get('containers', {})
            healthy_count = sum(1 for c in containers.values() if c.get('health') == 'healthy')
            total_count = len(containers)

            self._log(
                "CONTAINER", f"Timeout waiting for {model_slug} app {app_number}: {healthy_count}/{total_count} healthy after {elapsed:.1f}s",
                level='warning'
            )

            return {
                'healthy': False,
                'failed': False,  # Timeout is not a permanent failure
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
                'failed': True,
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
        
        # Fallback: if started_apps is empty (e.g. using ConcurrentAnalysisRunner which bypasses tracking),
        # iterate through all successfully generated apps in the pipeline
        if not started_apps:
            self._log("CONTAINER", "No specific containers tracked - falling back to all generated apps")
            gen_results = getattr(pipeline, 'progress', {}).get('generation', {}).get('results', [])
            for res in gen_results:
                if res.get('success'):
                    m = res.get('model_slug')
                    a = res.get('app_number')
                    if m and a is not None:
                        started_apps.add((m, a))
        
        if not started_apps:
            self._log("CONTAINER", "No apps found to stop containers for")
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
            # Run in thread pool to avoid blocking if many containers (optional optimization)
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
        
        CRITICAL: This method checks BOTH:
        1. All expected jobs have been submitted (job_index >= expected_jobs)
        2. All created tasks have reached terminal state (completed/failed/cancelled)
        
        Bug Fix (Jan 2026): Previously only checked (2), causing pipeline to complete
        prematurely when all created tasks finished but more jobs remained to submit.
        Now checks both conditions to prevent incomplete pipelines.
        
        Returns True if all jobs submitted AND all tasks terminal, marks pipeline complete.
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
        
        # CRITICAL FIX: Check if we've created tasks for ALL expected jobs
        # If job_index < expected_jobs, there are still jobs to be submitted
        jobs_remaining = expected_jobs - pipeline.current_job_index
        
        self._log(
            "ANAL", f"Pipeline {pipeline.pipeline_id} analysis status: {terminal_count}/{total_main_tasks} main tasks terminal (completed={completed_count}, failed={failed_count}, pending={pending_count}), jobs_remaining={jobs_remaining}"
        )
        
        # Must wait for ALL jobs to be submitted AND all tasks to reach terminal state
        if jobs_remaining > 0:
            self._log(
                "ANAL", f"Pipeline {pipeline.pipeline_id}: Cannot complete - {jobs_remaining} jobs not yet submitted (index={pipeline.current_job_index}, expected={expected_jobs})"
            )
            return False
        
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
            from app.services.generation_v2 import get_generation_service
            svc = get_generation_service()
            
            # Use pipeline_id as batch_id for grouping related generations
            batch_id = pipeline.pipeline_id
            
            # Get generation config options (if any future options are added)
            gen_config = pipeline.config.get('generation', {})
            use_auto_fix = gen_config.get('use_auto_fix', False)
            
            # Run generation with SAME parameters as Sample Generator API
            # Key: app_num=None lets service handle atomic reservation (prevents race conditions)
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
