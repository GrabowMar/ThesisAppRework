"""Concurrent Analysis Runner
==============================

Clean, reliable concurrent app analysis using asyncio.

Key features:
- asyncio.Semaphore for clean concurrency limiting
- Pre-ensures analyzer containers are healthy
- Batches app container builds (with concurrency limit)  
- Pre-creates all tasks atomically before execution
- Clean progress callbacks

This wraps the existing analyzer infrastructure rather than replacing it.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Callable

logger = logging.getLogger(__name__)

# Tools that can run without app containers (static analysis + AI analysis)
# These tools analyze source code and don't require running application containers
STATIC_ANALYSIS_TOOLS = {
    # Python static analysis
    'bandit',
    'pylint',
    'flake8',
    'mypy',
    'vulture',
    'ruff',
    'safety',
    'pip-audit',

    # JavaScript/CSS static analysis
    'eslint',
    'jshint',
    'stylelint',
    'npm-audit',

    # Multi-language security
    'semgrep',

    # AI-powered analysis (analyzes source code, not running apps)
    'requirements-scanner',
    'code-quality-analyzer',
    'curl-endpoint-tester',  # Note: This actually needs endpoints, will fail gracefully
}


@dataclass
class AnalysisJobSpec:
    """Specification for a single analysis job."""
    model_slug: str
    app_number: int
    tools: Optional[List[str]] = None  # None = all tools
    pipeline_id: Optional[str] = None
    
    # Filled in during execution
    task_id: Optional[str] = None
    containers_ready: bool = False


@dataclass
class AnalysisJobResult:
    """Result of a single analysis job."""
    job_index: int
    model_slug: str
    app_number: int
    task_id: Optional[str]
    success: bool
    error: Optional[str] = None
    duration_seconds: float = 0.0
    findings_count: int = 0
    status: str = 'pending'  # pending, running, completed, failed, partial


class ConcurrentAnalysisRunner:
    """Asynchronous concurrent app analyzer with proper resource pre-allocation.
    
    Uses asyncio.Semaphore for clean concurrency control.
    Pre-builds containers and creates tasks before starting analysis.
    
    Usage:
        runner = ConcurrentAnalysisRunner(max_concurrent_analysis=2)
        jobs = [
            AnalysisJobSpec(model_slug='model_a', app_number=1),
            AnalysisJobSpec(model_slug='model_a', app_number=2),
        ]
        results = await runner.analyze_batch(jobs)
    """
    
    def __init__(
        self,
        max_concurrent_analysis: int = 2,
        max_concurrent_container_builds: int = 2,
        container_build_timeout: int = 300,
        analysis_timeout: int = 600,
        on_progress: Optional[Callable[[int, int, AnalysisJobResult], None]] = None
    ):
        """Initialize runner.
        
        Args:
            max_concurrent_analysis: Maximum concurrent analysis jobs
            max_concurrent_container_builds: Maximum concurrent container builds
            container_build_timeout: Timeout for container builds (seconds)
            analysis_timeout: Timeout for each analysis (seconds)
            on_progress: Optional callback(completed, total, result) for progress updates
        """
        self.max_concurrent_analysis = max_concurrent_analysis
        self.max_concurrent_container_builds = max_concurrent_container_builds
        self.container_build_timeout = container_build_timeout
        self.analysis_timeout = analysis_timeout
        self.on_progress = on_progress
        
        # Tracking
        self._completed = 0
        self._total = 0
        self._lock = asyncio.Lock()
        self._started_containers: List[tuple[str, int]] = []  # (model_slug, app_number) pairs
        
        logger.info(
            f"ConcurrentAnalysisRunner initialized "
            f"(max_analysis={max_concurrent_analysis}, max_builds={max_concurrent_container_builds})"
        )
    
    async def analyze_batch(
        self,
        jobs: List[AnalysisJobSpec],
        pipeline_id: Optional[str] = None,
        tools: Optional[List[str]] = None,
        skip_container_build: bool = False,
        auto_start_app_containers: bool = True,
    ) -> List[AnalysisJobResult]:
        """Analyze multiple apps concurrently.
        
        Args:
            jobs: List of analysis job specifications
            pipeline_id: Optional pipeline ID for all jobs
            tools: Default tools for jobs that don't specify their own
            skip_container_build: Skip container build phase (for static-only analysis)
            auto_start_app_containers: Whether to start app containers before analysis
            
        Returns:
            List of AnalysisJobResult for each job (in same order as input)
        """
        if not jobs:
            return []
        
        self._completed = 0
        self._total = len(jobs)
        self._started_containers = []
        
        # Assign pipeline_id and tools to jobs if not set
        for job in jobs:
            if job.pipeline_id is None:
                job.pipeline_id = pipeline_id
            if job.tools is None and tools:
                job.tools = tools
        
        logger.info(f"Starting batch analysis: {len(jobs)} jobs, max_concurrent={self.max_concurrent_analysis}")
        
        try:
            # STEP 1: Ensure analyzer containers are healthy
            logger.info("[STEP 1] Checking analyzer container health...")
            analyzers_ready = await self._ensure_analyzers_ready()
            if not analyzers_ready:
                logger.warning("Analyzer containers not fully healthy, proceeding anyway (static analysis may work)")
            
            # STEP 2: Pre-build app containers in parallel (if enabled)
            # Note: Even for "existing" apps, we should check/build containers unless explicitly skipped
            if auto_start_app_containers and not skip_container_build:
                logger.info("[STEP 2] Pre-building app containers...")
                await self._prebuild_app_containers(jobs)
            else:
                logger.info("[STEP 2] Skipping container builds (disabled or static-only)")
            
            # STEP 3: Pre-create all analysis tasks atomically
            logger.info("[STEP 3] Pre-creating analysis tasks...")
            await self._precreate_tasks(jobs)
            
            # STEP 4: Run analysis with semaphore limiting
            logger.info("[STEP 4] Running analysis jobs...")
            semaphore = asyncio.Semaphore(self.max_concurrent_analysis)
            
            async def run_with_sem(idx: int, job: AnalysisJobSpec) -> AnalysisJobResult:
                async with semaphore:
                    return await self._run_single_analysis(idx, job)
            
            tasks = [run_with_sem(i, job) for i, job in enumerate(jobs)]
            raw_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Convert exceptions to error results
            results: List[AnalysisJobResult] = []
            for i, r in enumerate(raw_results):
                if isinstance(r, Exception):
                    results.append(AnalysisJobResult(
                        job_index=i,
                        model_slug=jobs[i].model_slug,
                        app_number=jobs[i].app_number,
                        task_id=jobs[i].task_id,
                        success=False,
                        error=str(r),
                        status='failed',
                    ))
                else:
                    results.append(r)
            
            # Log summary
            succeeded = sum(1 for r in results if r.success)
            failed = len(results) - succeeded
            total_findings = sum(r.findings_count for r in results)
            logger.info(
                f"Batch analysis complete: {succeeded}/{len(results)} succeeded, "
                f"{failed} failed, {total_findings} total findings"
            )
            
            return results
        finally:
            # STEP 5: Stop all app containers that were started during this batch
            await self._stop_started_containers()
    
    async def _ensure_analyzers_ready(self) -> bool:
        """Ensure analyzer service containers are healthy.
        
        Returns True if all required analyzers are healthy.
        """
        try:
            from app.services.service_locator import ServiceLocator
            
            # Get analyzer status
            docker_mgr = ServiceLocator.get_docker_manager()
            if not docker_mgr:
                logger.warning("Docker manager not available")
                return False
            
            # Check analyzer services health
            # For now, just check if they're reachable via TCP
            import socket
            
            ANALYZER_PORTS = {
                'static-analyzer': 2001,
                'dynamic-analyzer': 2002,
                'ai-analyzer': 2004,
            }
            
            all_healthy = True
            for service, port in ANALYZER_PORTS.items():
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2.0)
                    result = sock.connect_ex(('127.0.0.1', port))
                    sock.close()
                    
                    if result == 0:
                        logger.debug(f"Analyzer {service} healthy on port {port}")
                    else:
                        logger.warning(f"Analyzer {service} not reachable on port {port}")
                        all_healthy = False
                except Exception as e:
                    logger.warning(f"Failed to check {service}: {e}")
                    all_healthy = False
            
            return all_healthy
            
        except Exception as e:
            logger.error(f"Failed to check analyzer health: {e}")
            return False
    
    async def _prebuild_app_containers(self, jobs: List[AnalysisJobSpec]) -> None:
        """Pre-build app containers for all jobs in parallel batches.
        
        Uses semaphore to limit concurrent builds.
        Updates GeneratedApplication.container_status in DB on success/failure.
        """
        from app.services.service_locator import ServiceLocator
        
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            logger.warning("Docker manager not available, skipping container builds")
            return
        
        semaphore = asyncio.Semaphore(self.max_concurrent_container_builds)
        
        async def build_one(job: AnalysisJobSpec) -> bool:
            async with semaphore:
                max_build_retries = 2
                last_error = 'Unknown error'
                
                for attempt in range(max_build_retries + 1):
                    try:
                        if attempt > 0:
                            logger.info(
                                f"Retrying container build for {job.model_slug}/app{job.app_number} "
                                f"(attempt {attempt + 1}/{max_build_retries + 1})"
                            )
                        else:
                            logger.info(f"Building containers for {job.model_slug}/app{job.app_number}...")
                        
                        # Run build in executor to not block event loop
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(
                            None,
                            lambda: docker_mgr.build_containers(
                                job.model_slug,
                                job.app_number,
                                no_cache=False,
                                start_after=True
                            )
                        )
                        
                        if result.get('success'):
                            job.containers_ready = True
                            self._started_containers.append((job.model_slug, job.app_number))
                            self._update_app_container_status(job.model_slug, job.app_number, 'running')
                            logger.info(f"Containers ready for {job.model_slug}/app{job.app_number}")
                            return True
                        else:
                            last_error = result.get('error', 'Unknown error')
                            if attempt < max_build_retries:
                                backoff = 5 * (attempt + 1)
                                logger.warning(
                                    f"Container build failed for {job.model_slug}/app{job.app_number}: "
                                    f"{last_error}. Retrying in {backoff}s..."
                                )
                                await asyncio.sleep(backoff)
                            
                    except Exception as e:
                        last_error = str(e)
                        if attempt < max_build_retries:
                            backoff = 5 * (attempt + 1)
                            logger.warning(
                                f"Container build error for {job.model_slug}/app{job.app_number}: "
                                f"{e}. Retrying in {backoff}s..."
                            )
                            await asyncio.sleep(backoff)
                
                # All retries exhausted
                self._update_app_container_status(job.model_slug, job.app_number, 'build_failed')
                logger.error(
                    f"Container build failed for {job.model_slug}/app{job.app_number} "
                    f"after {max_build_retries + 1} attempts: {last_error}"
                )
                return False
        
        # Build all containers in parallel (with semaphore limiting)
        await asyncio.gather(*[build_one(job) for job in jobs], return_exceptions=True)
        
        # Count successes
        ready_count = sum(1 for job in jobs if job.containers_ready)
        logger.info(f"Container builds complete: {ready_count}/{len(jobs)} ready")
    
    async def _stop_started_containers(self) -> None:
        """Stop all app containers that were started during this batch.
        
        Called in the finally block of analyze_batch() to ensure cleanup.
        """
        if not self._started_containers:
            logger.debug("No containers to stop after batch analysis")
            return
        
        logger.info(f"Stopping {len(self._started_containers)} app container sets after batch analysis...")
        
        from app.services.service_locator import ServiceLocator
        docker_mgr = ServiceLocator.get_docker_manager()
        if not docker_mgr:
            logger.error("Docker manager not available - cannot stop containers!")
            return
        
        loop = asyncio.get_event_loop()
        for model_slug, app_number in self._started_containers:
            try:
                result = await loop.run_in_executor(
                    None,
                    lambda m=model_slug, a=app_number: docker_mgr.stop_containers(m, a)
                )
                if result.get('success'):
                    self._update_app_container_status(model_slug, app_number, 'stopped')
                    logger.info(f"Stopped containers for {model_slug}/app{app_number}")
                else:
                    logger.warning(f"Failed to stop containers for {model_slug}/app{app_number}: {result.get('error')}")
            except Exception as e:
                logger.error(f"Error stopping containers for {model_slug}/app{app_number}: {e}")
        
        self._started_containers.clear()
    
    @staticmethod
    def _update_app_container_status(model_slug: str, app_number: int, status: str) -> None:
        """Update GeneratedApplication.container_status in the database."""
        try:
            from app.models import GeneratedApplication
            from app.extensions import db
            
            app_record = GeneratedApplication.query.filter_by(
                model_slug=model_slug, app_number=app_number
            ).first()
            if app_record:
                app_record.container_status = status
                db.session.commit()
                logger.debug(f"Updated container_status to '{status}' for {model_slug}/app{app_number}")
        except Exception as e:
            logger.warning(f"Failed to update container_status for {model_slug}/app{app_number}: {e}")
            try:
                from app.extensions import db
                db.session.rollback()
            except Exception:
                pass
    
    async def _precreate_tasks(self, jobs: List[AnalysisJobSpec]) -> None:
        """Pre-create all analysis tasks atomically.
        
        This prevents race conditions in task creation.
        """
        from app.services.task_service import AnalysisTaskService
        from app.extensions import db
        
        for idx, job in enumerate(jobs):
            try:
                # Check if containers are ready; if not, downgrade to static analysis only
                final_tools = job.tools or []

                if not job.containers_ready and final_tools:
                    # Filter to only keep static tools
                    original_count = len(final_tools)
                    # Normalize tool names for robust comparison
                    filtered_tools = [
                        t for t in final_tools 
                        if t.lower() in STATIC_ANALYSIS_TOOLS or 
                           any(st in t.lower() for st in STATIC_ANALYSIS_TOOLS)
                    ]

                    # If we filtered out non-static tools, log it
                    if original_count > len(filtered_tools):
                        logger.warning(
                            f"Containers not ready for {job.model_slug}/app{job.app_number} - "
                            f"downgraded to static analysis only (kept {len(filtered_tools)}/{original_count} tools)"
                        )
                        final_tools = filtered_tools

                    # If no tools remain after filtering, log warning but continue with empty list
                    # The analyzer will use all available static tools as fallback
                    if not final_tools:
                        logger.warning(
                            f"{job.model_slug}/app{job.app_number}: No static tools in selection, "
                            f"will use all available static tools as fallback"
                        )
                        # Ensure we don't pass an empty list if we want fallback, 
                        # OR if the downstream service handles empty list as "all static", then fine.
                        # AnalysisTaskService.create_main_task_with_subtasks usually interprets empty as "all available for this category"
                elif not job.containers_ready:
                    # No tools specified but containers failed - use all static tools
                    logger.info(
                        f"{job.model_slug}/app{job.app_number}: No tools specified, "
                        f"containers not ready - will use all available static tools"
                    )

                logger.debug(f"Creating task for {job.model_slug}/app{job.app_number}...")
                
                # Build custom options
                custom_options = {
                    'source': 'concurrent_analysis_runner',
                    'pipeline_id': job.pipeline_id,
                    'container_management': {
                        'start_before_analysis': False,  # Already built (or failed)
                        'build_if_missing': False,
                        'stop_after_analysis': True,
                    }
                }
                
                # Use the filtered tool list
                if final_tools:
                    custom_options['selected_tool_names'] = final_tools
                
                # Create main task with subtasks
                task = AnalysisTaskService.create_main_task_with_subtasks(
                    model_slug=job.model_slug,
                    app_number=job.app_number,
                    tools=final_tools,
                    priority='normal',
                    custom_options=custom_options,
                    task_name=f"concurrent:{job.model_slug}:app{job.app_number}"
                )
                
                job.task_id = task.task_id
                logger.debug(f"Created task {task.task_id} for {job.model_slug}/app{job.app_number}")
                
            except Exception as e:
                logger.error(f"Failed to create task for {job.model_slug}/app{job.app_number}: {e}", exc_info=True)
                # Continue with other jobs
        
        db.session.commit()
        
        created_count = sum(1 for job in jobs if job.task_id)
        logger.info(f"Tasks created: {created_count}/{len(jobs)}")
    
    async def _run_single_analysis(
        self, 
        job_index: int, 
        job: AnalysisJobSpec
    ) -> AnalysisJobResult:
        """Execute a single analysis job.
        
        Returns AnalysisJobResult (never raises - errors are captured in result).
        """
        start_time = time.time()
        
        result = AnalysisJobResult(
            job_index=job_index,
            model_slug=job.model_slug,
            app_number=job.app_number,
            task_id=job.task_id,
            success=False,
            status='running',
        )
        
        if not job.task_id:
            result.error = "No task ID - task creation failed"
            result.status = 'failed'
            return result
        
        try:
            logger.info(f"[Job {job_index}] Waiting for task completion: {job.model_slug}/app{job.app_number} (task={job.task_id})")
            
            # Import required modules
            from app.models import AnalysisTask
            from app.constants import AnalysisStatus
            from app.extensions import db
            
            # Poll for task completion (execution handled by TaskExecutionService daemon)
            poll_interval = 5.0  # seconds
            max_polls = int(self.analysis_timeout / poll_interval)
            
            for poll_count in range(max_polls):
                # Fetch fresh task state from DB with retry on connection issues
                try:
                    db.session.expire_all()
                    task = AnalysisTask.query.filter_by(task_id=job.task_id).first()
                except Exception as db_error:
                    logger.warning(f"[Job {job_index}] Database query error (will retry): {db_error}")
                    await asyncio.sleep(poll_interval)
                    continue

                if not task:
                    # Task not found - check if it was deleted or never created
                    if poll_count == 0:
                        result.error = f"Task {job.task_id} not found in database (never created)"
                    else:
                        result.error = f"Task {job.task_id} disappeared from database after {poll_count} polls"
                    result.status = 'failed'
                    return result

                # Check if task reached terminal state
                if task.status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIAL_SUCCESS,
                                   AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                    # Task finished
                    result.duration_seconds = time.time() - start_time

                    if task.status == AnalysisStatus.COMPLETED:
                        result.success = True
                        result.status = 'completed'
                    elif task.status == AnalysisStatus.PARTIAL_SUCCESS:
                        result.success = True
                        result.status = 'partial'
                    else:
                        result.success = False
                        result.status = 'failed'
                        result.error = task.error_message or 'Task failed'

                    # Try to get findings count from task results
                    try:
                        summary = task.get_result_summary() if hasattr(task, 'get_result_summary') else {}
                        if isinstance(summary, dict):
                            result.findings_count = summary.get('total_findings', 0)
                    except Exception as e:
                        logger.debug(f"[Job {job_index}] Could not extract findings count: {e}")

                    logger.info(
                        f"[Job {job_index}] {result.status.upper()}: {job.model_slug}/app{job.app_number} "
                        f"in {result.duration_seconds:.1f}s ({result.findings_count or 0} findings)"
                    )
                    break

                # Task still running - wait and poll again
                if poll_count % 12 == 0 and poll_count > 0:  # Log every ~minute
                    elapsed = time.time() - start_time
                    logger.info(
                        f"[Job {job_index}] Still waiting for {job.model_slug}/app{job.app_number} "
                        f"({elapsed:.0f}s elapsed, status={task.status.value if task.status else 'unknown'}, "
                        f"progress={task.progress_percentage if hasattr(task, 'progress_percentage') else 0:.0f}%)"
                    )

                await asyncio.sleep(poll_interval)
            else:
                # Timeout - max polls reached
                result.error = f"Analysis timed out after {self.analysis_timeout}s"
                result.status = 'failed'
                result.duration_seconds = time.time() - start_time
                logger.error(f"[Job {job_index}] TIMEOUT: {job.model_slug}/app{job.app_number}")
                
        except asyncio.CancelledError:
            result.error = "Task was cancelled"
            result.status = 'failed'
            result.duration_seconds = time.time() - start_time
            logger.warning(f"[Job {job_index}] CANCELLED: {job.model_slug}/app{job.app_number}")
            
        except Exception as e:
            result.error = str(e)
            result.status = 'failed'
            result.duration_seconds = time.time() - start_time
            logger.error(f"[Job {job_index}] FAILED: {job.model_slug}/app{job.app_number}: {e}")
        
        # Update progress
        async with self._lock:
            self._completed += 1
            if self.on_progress:
                try:
                    self.on_progress(self._completed, self._total, result)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")
        
        return result


# Convenience function for simple usage
async def analyze_apps_concurrent(
    apps: List[Dict[str, Any]],
    tools: Optional[List[str]] = None,
    max_concurrent: int = 2,
    pipeline_id: Optional[str] = None,
) -> List[AnalysisJobResult]:
    """Analyze multiple apps concurrently.
    
    Args:
        apps: List of app specs as dicts with 'model_slug' and 'app_number'
        tools: Optional list of tools to run
        max_concurrent: Maximum concurrent analyses
        pipeline_id: Optional pipeline identifier
        
    Returns:
        List of AnalysisJobResult
    """
    jobs = [
        AnalysisJobSpec(
            model_slug=app['model_slug'],
            app_number=app['app_number'],
            tools=app.get('tools') or tools,
            pipeline_id=pipeline_id,
        )
        for app in apps
    ]
    
    runner = ConcurrentAnalysisRunner(max_concurrent_analysis=max_concurrent)
    return await runner.analyze_batch(jobs, pipeline_id=pipeline_id, tools=tools)
