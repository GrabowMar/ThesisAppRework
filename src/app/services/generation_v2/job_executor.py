"""Job Executor
==============

Simplified job executor for generation and analysis tasks.
Replaces the complex PipelineExecutionService and TaskExecutionService.

Design:
- Single ThreadPoolExecutor for all async work
- Database as source of truth (no application-level coordination)
- Simple polling loop
- Circuit breaker for external services
"""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set, Callable

from app.extensions import db
from app.models import PipelineExecution, PipelineExecutionStatus
from app.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

from .config import GenerationConfig, GenerationMode, GenerationResult
from .service import get_generation_service

logger = logging.getLogger(__name__)


class JobExecutor:
    """Unified executor for pipeline jobs.
    
    Handles both generation and analysis stages in a single, simple service.
    Uses database polling and ThreadPoolExecutor for async execution.
    """
    
    # Configuration
    MAX_WORKERS = 4
    POLL_INTERVAL = 3.0
    MAX_CONCURRENT_GENERATION = 2
    MAX_CONCURRENT_ANALYSIS = 3
    
    def __init__(self, app=None):
        """Initialize job executor.
        
        Args:
            app: Flask application instance for context
        """
        self._app = app
        self._executor: Optional[ThreadPoolExecutor] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._shutdown_event = threading.Event()
        
        # Track in-flight jobs
        self._in_flight: Dict[str, Set[str]] = {}  # pipeline_id -> set of job_keys
        self._futures: Dict[str, Dict[str, Future]] = {}  # pipeline_id -> {job_key: Future}
        self._lock = threading.RLock()
        
        logger.info("JobExecutor initialized")
    
    def start(self) -> None:
        """Start the executor service."""
        if self._running:
            logger.warning("JobExecutor already running")
            return
        
        self._running = True
        self._shutdown_event.clear()
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS, thread_name_prefix='job-exec')
        
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="JobExecutor")
        self._thread.start()
        
        logger.info("JobExecutor started")
    
    def stop(self) -> None:
        """Stop the executor service."""
        if not self._running:
            return
        
        logger.info("Stopping JobExecutor...")
        self._running = False
        self._shutdown_event.set()
        
        if self._executor:
            self._executor.shutdown(wait=True, cancel_futures=False)
            self._executor = None
        
        if self._thread:
            self._thread.join(timeout=10.0)
            self._thread = None
        
        logger.info("JobExecutor stopped")
    
    def _run_loop(self) -> None:
        """Main polling loop."""
        logger.info("JobExecutor loop started")
        
        while self._running:
            try:
                if self._app:
                    with self._app.app_context():
                        self._process_pipelines()
                else:
                    self._process_pipelines()
            except Exception as e:
                logger.exception(f"Error in executor loop: {e}")
            
            # Wait for next poll or shutdown
            self._shutdown_event.wait(timeout=self.POLL_INTERVAL)
        
        logger.info("JobExecutor loop ended")
    
    def _process_pipelines(self) -> None:
        """Process all running pipelines."""
        try:
            # Get running pipelines
            pipelines = PipelineExecution.query.filter_by(
                status=PipelineExecutionStatus.RUNNING
            ).all()
            
            for pipeline in pipelines:
                self._process_pipeline(pipeline)
                
        except Exception as e:
            logger.error(f"Error querying pipelines: {e}")
    
    def _process_pipeline(self, pipeline: PipelineExecution) -> None:
        """Process a single pipeline."""
        pipeline_id = pipeline.id
        stage = pipeline.current_stage
        
        # Initialize tracking for this pipeline
        with self._lock:
            if pipeline_id not in self._in_flight:
                self._in_flight[pipeline_id] = set()
                self._futures[pipeline_id] = {}
        
        # Check completed jobs
        self._check_completed_jobs(pipeline)
        
        # Process based on stage
        if stage == 'generation':
            self._process_generation_stage(pipeline)
        elif stage == 'analysis':
            self._process_analysis_stage(pipeline)
        elif stage == 'completed':
            self._cleanup_pipeline(pipeline_id)
    
    def _process_generation_stage(self, pipeline: PipelineExecution) -> None:
        """Process generation stage jobs."""
        pipeline_id = pipeline.id
        progress = pipeline.progress or {}
        config = pipeline.config or {}
        
        gen_progress = progress.get('generation', {})
        total = gen_progress.get('total', 0)
        completed = gen_progress.get('completed', 0)
        failed = gen_progress.get('failed', 0)
        
        with self._lock:
            in_flight = len(self._in_flight.get(pipeline_id, set()))
        
        # Check if generation is complete
        if completed + failed >= total and in_flight == 0:
            logger.info(f"[{pipeline_id}] Generation complete: {completed}/{total} succeeded")
            self._transition_to_analysis(pipeline)
            return
        
        # Submit new jobs up to limit
        while in_flight < self.MAX_CONCURRENT_GENERATION:
            job = pipeline.get_next_job()
            if not job or job.get('stage') != 'generation':
                break
            
            job_key = f"gen:{job.get('job_index', 0)}"
            
            with self._lock:
                if job_key in self._in_flight.get(pipeline_id, set()):
                    pipeline.advance_job_index()
                    db.session.commit()
                    continue
            
            # Submit job
            self._submit_generation_job(pipeline_id, job, config)
            pipeline.advance_job_index()
            db.session.commit()
            
            with self._lock:
                in_flight = len(self._in_flight.get(pipeline_id, set()))
    
    def _submit_generation_job(self, pipeline_id: str, job: Dict, config: Dict) -> None:
        """Submit a generation job to the executor."""
        job_index = job.get('job_index', 0)
        model_slug = job.get('model_slug')
        template_slug = job.get('template_slug')
        job_key = f"gen:{job_index}"
        
        logger.info(f"[{pipeline_id}] Submitting generation job {job_index}: {model_slug} + {template_slug}")
        
        # Add to in-flight tracking
        with self._lock:
            self._in_flight[pipeline_id].add(job_key)
        
        # Prepare config for generation
        gen_options = config.get('generation', {}).get('options', {})
        mode_str = gen_options.get('mode', 'guarded')
        
        gen_config = GenerationConfig(
            model_slug=model_slug,
            template_slug=template_slug,
            app_num=job_index + 1,  # App numbers are 1-based
            mode=GenerationMode.GUARDED if mode_str == 'guarded' else GenerationMode.UNGUARDED,
            max_tokens=gen_options.get('maxTokens', 32000),
            temperature=gen_options.get('temperature', 0.3),
        )
        
        # Submit to executor
        if self._executor:
            try:
                future = self._executor.submit(self._run_generation, pipeline_id, job_key, gen_config)
                with self._lock:
                    self._futures[pipeline_id][job_key] = future
            except RuntimeError as e:
                # Handle "cannot schedule new futures after shutdown" gracefully
                error_str = str(e).lower()
                if 'cannot schedule new futures' in error_str or 'interpreter shutdown' in error_str:
                    logger.warning(
                        f"Executor shutdown detected when submitting job {job_key}: {e}. "
                        "Job will not be started."
                    )
                    # Mark as failed in in-flight tracking then remove
                    with self._lock:
                        self._in_flight.get(pipeline_id, set()).discard(job_key)
                    # Note: The job will appear as not completed in the next poll cycle
                    # The pipeline progress will show incomplete jobs, allowing manual retry
                else:
                    raise
    
    def _run_generation(self, pipeline_id: str, job_key: str, config: GenerationConfig) -> Dict[str, Any]:
        """Run a generation job (executed in thread pool)."""
        try:
            if self._app:
                with self._app.app_context():
                    service = get_generation_service()
                    result = service.generate(config)
            else:
                service = get_generation_service()
                result = service.generate(config)
            
            return {
                'job_key': job_key,
                'success': result.success,
                'errors': result.errors,
                'metrics': result.metrics,
            }
            
        except Exception as e:
            logger.exception(f"Generation job {job_key} failed: {e}")
            return {
                'job_key': job_key,
                'success': False,
                'errors': [str(e)],
            }
    
    def _check_completed_jobs(self, pipeline: PipelineExecution) -> None:
        """Check for completed jobs and update progress."""
        pipeline_id = pipeline.id
        
        with self._lock:
            futures = dict(self._futures.get(pipeline_id, {}))
        
        for job_key, future in futures.items():
            if not future.done():
                continue
            
            try:
                result = future.result(timeout=0)
                self._record_job_result(pipeline, job_key, result)
            except Exception as e:
                logger.error(f"Job {job_key} raised exception: {e}")
                self._record_job_result(pipeline, job_key, {
                    'job_key': job_key,
                    'success': False,
                    'errors': [str(e)],
                })
            
            # Remove from tracking
            with self._lock:
                self._in_flight.get(pipeline_id, set()).discard(job_key)
                self._futures.get(pipeline_id, {}).pop(job_key, None)
    
    def _record_job_result(self, pipeline: PipelineExecution, job_key: str, result: Dict) -> None:
        """Record job result to pipeline progress."""
        try:
            progress = pipeline.progress or {}
            stage = 'generation' if job_key.startswith('gen:') else 'analysis'
            
            if stage not in progress:
                progress[stage] = {'completed': 0, 'failed': 0, 'results': []}
            
            progress[stage]['results'].append(result)
            
            if result.get('success'):
                progress[stage]['completed'] = progress[stage].get('completed', 0) + 1
            else:
                progress[stage]['failed'] = progress[stage].get('failed', 0) + 1
            
            pipeline.progress = progress
            db.session.commit()
            
            logger.info(f"[{pipeline.id}] Job {job_key}: {'✓' if result.get('success') else '✗'}")
            
        except Exception as e:
            logger.error(f"Failed to record job result: {e}")
            db.session.rollback()
    
    def _transition_to_analysis(self, pipeline: PipelineExecution) -> None:
        """Transition pipeline from generation to analysis stage."""
        try:
            progress = pipeline.progress or {}
            progress['generation']['status'] = 'completed'
            
            pipeline.progress = progress
            pipeline.current_stage = 'analysis'
            pipeline.current_job_index = 0
            db.session.commit()
            
            logger.info(f"[{pipeline.id}] Transitioned to analysis stage")
            
            # Cleanup generation tracking
            with self._lock:
                self._in_flight.pop(pipeline.id, None)
                self._futures.pop(pipeline.id, None)
                
        except Exception as e:
            logger.error(f"Failed to transition to analysis: {e}")
            db.session.rollback()
    
    def _process_analysis_stage(self, pipeline: PipelineExecution) -> None:
        """Process analysis stage jobs.
        
        TODO: Implement analysis job submission.
        For now, just mark as completed.
        """
        progress = pipeline.progress or {}
        analysis_progress = progress.get('analysis', {})
        
        # If analysis config is empty, skip to completed
        analysis_config = (pipeline.config or {}).get('analysis', {})
        if not analysis_config.get('types'):
            logger.info(f"[{pipeline.id}] No analysis configured, completing pipeline")
            self._complete_pipeline(pipeline)
            return
        
        # TODO: Implement analysis job submission
        # For now, mark analysis as complete
        progress['analysis'] = {'status': 'completed', 'completed': 0, 'failed': 0}
        pipeline.progress = progress
        db.session.commit()
        
        self._complete_pipeline(pipeline)
    
    def _complete_pipeline(self, pipeline: PipelineExecution) -> None:
        """Mark pipeline as completed."""
        try:
            pipeline.status = PipelineExecutionStatus.COMPLETED
            pipeline.current_stage = 'completed'
            pipeline.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            
            logger.info(f"[{pipeline.id}] Pipeline completed")
            self._cleanup_pipeline(pipeline.id)
            
        except Exception as e:
            logger.error(f"Failed to complete pipeline: {e}")
            db.session.rollback()
    
    def _cleanup_pipeline(self, pipeline_id: str) -> None:
        """Clean up tracking for a pipeline."""
        with self._lock:
            self._in_flight.pop(pipeline_id, None)
            self._futures.pop(pipeline_id, None)


# Singleton instance
_executor: Optional[JobExecutor] = None


def get_job_executor(app=None) -> JobExecutor:
    """Get shared job executor instance."""
    global _executor
    if _executor is None:
        _executor = JobExecutor(app=app)
    return _executor


def start_job_executor(app=None) -> JobExecutor:
    """Start the job executor service."""
    executor = get_job_executor(app)
    executor.start()
    return executor


def stop_job_executor() -> None:
    """Stop the job executor service."""
    global _executor
    if _executor:
        _executor.stop()
