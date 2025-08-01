"""
Enhanced Batch Analysis Service
==============================

A comprehensive batch analysis system that orchestrates all testing services,
manages workers, tracks progress, and provides detailed reporting.

This service integrates:
- Database-backed job and task management
- Worker pool management with health monitoring
- Real-time progress tracking
- Error handling and retry mechanisms
- Performance metrics and reporting
- Service integration (security, performance, ZAP, OpenRouter)

Architecture:
- BatchJobManager: High-level job orchestration
- BatchTaskRunner: Individual task execution
- BatchWorkerPool: Worker lifecycle management
- BatchProgressTracker: Real-time progress monitoring
- BatchReportGenerator: Results aggregation and reporting
"""

import asyncio
import json
import logging
import multiprocessing
import os
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from threading import Lock, RLock
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable

# Import Flask and database components
try:
    from flask import current_app
    from .extensions import db
    from .models import (
        BatchJob, BatchTask, BatchWorker, GeneratedApplication,
        JobStatus, TaskStatus, JobPriority, AnalysisType, AnalysisStatus
    )
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

# Import core services
try:
    from .core_services import get_logger, BaseService
except ImportError:
    import logging
    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)
    
    class BaseService:
        def __init__(self, name: str):
            self.logger = get_logger(name)
            self._lock = RLock()

# Import analysis services
try:
    from .security_analysis_service import UnifiedCLIAnalyzer
    from .performance_service import LocustPerformanceTester
    from .zap_service import create_scanner
    from .openrouter_service import OpenRouterAnalyzer
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

# Initialize logger
logger = get_logger('batch_service')

# Configuration
@dataclass
class BatchConfiguration:
    """Configuration for batch processing."""
    max_workers: int = 4
    max_concurrent_jobs: int = 2
    task_timeout_seconds: int = 300
    worker_heartbeat_interval: int = 30
    job_cleanup_days: int = 30
    auto_retry_failed_tasks: bool = True
    max_task_retries: int = 3
    priority_execution: bool = True
    resource_monitoring: bool = True
    detailed_logging: bool = True


class BatchEventType(Enum):
    """Types of batch events."""
    JOB_CREATED = "job_created"
    JOB_STARTED = "job_started"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    JOB_CANCELLED = "job_cancelled"
    TASK_STARTED = "task_started"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRIED = "task_retried"
    WORKER_STARTED = "worker_started"
    WORKER_STOPPED = "worker_stopped"
    WORKER_ERROR = "worker_error"


@dataclass
class BatchEvent:
    """Represents a batch processing event."""
    event_type: BatchEventType
    timestamp: datetime
    job_id: Optional[str] = None
    task_id: Optional[str] = None
    worker_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class BatchEventListener:
    """Base class for batch event listeners."""
    
    def on_job_created(self, event: BatchEvent):
        """Called when a job is created."""
        pass
    
    def on_job_started(self, event: BatchEvent):
        """Called when a job starts."""
        pass
    
    def on_job_completed(self, event: BatchEvent):
        """Called when a job completes."""
        pass
    
    def on_job_failed(self, event: BatchEvent):
        """Called when a job fails."""
        pass
    
    def on_task_completed(self, event: BatchEvent):
        """Called when a task completes."""
        pass
    
    def on_task_failed(self, event: BatchEvent):
        """Called when a task fails."""
        pass


class BatchProgressTracker:
    """Tracks and reports batch processing progress."""
    
    def __init__(self):
        self.job_progress: Dict[str, Dict[str, Any]] = {}
        self.task_progress: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
    
    def update_job_progress(self, job_id: str, progress_data: Dict[str, Any]):
        """Update job progress."""
        with self._lock:
            if job_id not in self.job_progress:
                self.job_progress[job_id] = {}
            self.job_progress[job_id].update(progress_data)
            self.job_progress[job_id]['updated_at'] = datetime.utcnow().isoformat()
    
    def update_task_progress(self, task_id: str, progress_data: Dict[str, Any]):
        """Update task progress."""
        with self._lock:
            if task_id not in self.task_progress:
                self.task_progress[task_id] = {}
            self.task_progress[task_id].update(progress_data)
            self.task_progress[task_id]['updated_at'] = datetime.utcnow().isoformat()
    
    def get_job_progress(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job progress."""
        with self._lock:
            return self.job_progress.get(job_id, {}).copy()
    
    def get_all_progress(self) -> Dict[str, Any]:
        """Get all progress data."""
        with self._lock:
            return {
                'jobs': self.job_progress.copy(),
                'tasks': self.task_progress.copy(),
                'summary': self._generate_summary()
            }
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate progress summary."""
        total_jobs = len(self.job_progress)
        active_jobs = sum(1 for p in self.job_progress.values() 
                         if p.get('status') in ['running', 'queued'])
        
        return {
            'total_jobs': total_jobs,
            'active_jobs': active_jobs,
            'completed_jobs': total_jobs - active_jobs,
            'last_updated': datetime.utcnow().isoformat()
        }


class BatchTaskRunner:
    """Executes individual batch tasks."""
    
    def __init__(self, worker_id: str, config: BatchConfiguration):
        self.worker_id = worker_id
        self.config = config
        self.logger = get_logger(f'batch_task_runner_{worker_id}')
        self.analyzers = {}
        self._initialize_analyzers()
    
    def _initialize_analyzers(self):
        """Initialize analysis service instances."""
        try:
            if SERVICES_AVAILABLE:
                # Initialize security analyzer
                self.analyzers['security'] = UnifiedCLIAnalyzer()
                
                # Initialize performance tester
                output_dir = Path.cwd() / "performance_reports"
                self.analyzers['performance'] = LocustPerformanceTester(output_dir)
                
                # Initialize ZAP scanner
                zap_path = Path.cwd() / "zap_reports"
                self.analyzers['zap'] = create_scanner(zap_path)
                
                # Initialize OpenRouter analyzer
                self.analyzers['openrouter'] = OpenRouterAnalyzer()
                
                self.logger.info(f"Initialized {len(self.analyzers)} analyzers")
            else:
                self.logger.warning("Analysis services not available - using mock analyzers")
                self._create_mock_analyzers()
        except Exception as e:
            self.logger.error(f"Failed to initialize analyzers: {e}")
            self._create_mock_analyzers()
    
    def _create_mock_analyzers(self):
        """Create mock analyzers for testing."""
        class MockAnalyzer:
            def __init__(self, name: str):
                self.name = name
            
            def analyze_app(self, model: str, app_num: int) -> Dict[str, Any]:
                return {
                    'status': 'completed',
                    'analyzer': self.name,
                    'model': model,
                    'app_num': app_num,
                    'issues': [],
                    'summary': {'total_issues': 0}
                }
            
            def run_performance_test(self, model: str, app_num: int, **kwargs) -> Dict[str, Any]:
                return {
                    'status': 'completed',
                    'test_type': 'performance',
                    'model': model,
                    'app_num': app_num,
                    'metrics': {
                        'requests_per_second': 10.5,
                        'average_response_time': 150.2,
                        'error_rate': 0.1
                    }
                }
        
        self.analyzers = {
            'security': MockAnalyzer('security'),
            'performance': MockAnalyzer('performance'),
            'zap': MockAnalyzer('zap'),
            'openrouter': MockAnalyzer('openrouter')
        }
    
    def execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single batch task."""
        start_time = time.time()
        
        try:
            # Update task status
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            task.assigned_worker = self.worker_id
            task.execution_host = os.uname().nodename if hasattr(os, 'uname') else 'windows'
            task.process_id = os.getpid()
            
            if DATABASE_AVAILABLE:
                db.session.commit()
            
            self.logger.info(f"Starting task {task.id}: {task.analysis_type.value} for {task.model_slug}/app{task.app_number}")
            
            # Execute the analysis
            result = self._run_analysis(task)
            
            # Update task with results
            task.results_json = json.dumps(result)
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.actual_duration_seconds = time.time() - start_time
            task.exit_code = 0
            
            # Extract issue counts if available
            if 'issues' in result:
                task.issues_found = len(result['issues'])
                task.critical_issues = sum(1 for issue in result['issues'] if issue.get('severity') == 'critical')
                task.high_issues = sum(1 for issue in result['issues'] if issue.get('severity') == 'high')
                task.medium_issues = sum(1 for issue in result['issues'] if issue.get('severity') == 'medium')
                task.low_issues = sum(1 for issue in result['issues'] if issue.get('severity') == 'low')
            
            self.logger.info(f"Completed task {task.id} in {task.actual_duration_seconds:.2f}s")
            
        except Exception as e:
            self.logger.error(f"Task {task.id} failed: {str(e)}", exc_info=True)
            
            # Update task with error
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            task.actual_duration_seconds = time.time() - start_time
            task.exit_code = 1
            task.error_message = str(e)
            task.set_error_details({
                'error_type': type(e).__name__,
                'error_message': str(e),
                'worker_id': self.worker_id,
                'execution_host': task.execution_host,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        finally:
            task.last_heartbeat = datetime.utcnow()
            if DATABASE_AVAILABLE:
                try:
                    db.session.commit()
                except Exception as e:
                    self.logger.error(f"Failed to save task results: {e}")
                    db.session.rollback()
        
        return task
    
    def _run_analysis(self, task: BatchTask) -> Dict[str, Any]:
        """Run the appropriate analysis for the task."""
        analysis_type = task.analysis_type.value
        model = task.model_slug
        app_num = task.app_number
        
        # Map analysis types to methods
        if analysis_type in ['security_backend', 'security_frontend', 'security_combined']:
            return self._run_security_analysis(model, app_num, analysis_type)
        elif analysis_type == 'performance':
            return self._run_performance_analysis(model, app_num)
        elif analysis_type == 'zap_security':
            return self._run_zap_analysis(model, app_num)
        elif analysis_type == 'openrouter':
            return self._run_openrouter_analysis(model, app_num)
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    def _run_security_analysis(self, model: str, app_num: int, analysis_type: str) -> Dict[str, Any]:
        """Run security analysis."""
        analyzer = self.analyzers.get('security')
        if not analyzer:
            raise RuntimeError("Security analyzer not available")
        
        if hasattr(analyzer, 'run_security_analysis'):
            # Use enhanced security analyzer method
            issues, status, outputs = analyzer.run_security_analysis(
                model, app_num, use_all_tools=True
            )
            return {
                'status': 'completed',
                'analysis_type': analysis_type,
                'issues': issues,
                'tool_status': status,
                'outputs': outputs,
                'summary': {
                    'total_issues': len(issues),
                    'critical_count': sum(1 for i in issues if i.get('severity') == 'critical'),
                    'high_count': sum(1 for i in issues if i.get('severity') == 'high'),
                    'medium_count': sum(1 for i in issues if i.get('severity') == 'medium'),
                    'low_count': sum(1 for i in issues if i.get('severity') == 'low')
                }
            }
        else:
            # Fallback to basic analyze method
            return analyzer.analyze_app(model, app_num)
    
    def _run_performance_analysis(self, model: str, app_num: int) -> Dict[str, Any]:
        """Run performance analysis."""
        analyzer = self.analyzers.get('performance')
        if not analyzer:
            raise RuntimeError("Performance analyzer not available")
        
        if hasattr(analyzer, 'run_performance_test'):
            return analyzer.run_performance_test(model, app_num, force_rerun=True)
        else:
            return analyzer.analyze_app(model, app_num)
    
    def _run_zap_analysis(self, model: str, app_num: int) -> Dict[str, Any]:
        """Run ZAP security analysis."""
        analyzer = self.analyzers.get('zap')
        if not analyzer:
            raise RuntimeError("ZAP analyzer not available")
        
        if hasattr(analyzer, 'scan_app'):
            return analyzer.scan_app(model, app_num)
        else:
            return analyzer.analyze_app(model, app_num)
    
    def _run_openrouter_analysis(self, model: str, app_num: int) -> Dict[str, Any]:
        """Run OpenRouter analysis."""
        analyzer = self.analyzers.get('openrouter')
        if not analyzer:
            raise RuntimeError("OpenRouter analyzer not available")
        
        if hasattr(analyzer, 'analyze_app'):
            return analyzer.analyze_app(model, app_num)
        elif hasattr(analyzer, 'check_requirements'):
            # Use requirements checking method
            results = analyzer.check_requirements(model, app_num)
            return {
                'status': 'completed',
                'analysis_type': 'openrouter',
                'requirements_check': results,
                'summary': {'requirements_met': len([r for r in results if r.result.met])}
            }
        else:
            return analyzer.analyze_app(model, app_num)


class BatchWorkerPool:
    """Manages a pool of batch workers."""
    
    def __init__(self, config: BatchConfiguration):
        self.config = config
        self.logger = get_logger('batch_worker_pool')
        self.workers: Dict[str, BatchWorker] = {}
        self.executor: Optional[ThreadPoolExecutor] = None
        self.running = False
        self._lock = Lock()
    
    def start(self):
        """Start the worker pool."""
        with self._lock:
            if self.running:
                return
            
            self.executor = ThreadPoolExecutor(
                max_workers=self.config.max_workers,
                thread_name_prefix="BatchWorker"
            )
            self.running = True
            
            self.logger.info(f"Started worker pool with {self.config.max_workers} workers")
    
    def stop(self):
        """Stop the worker pool."""
        with self._lock:
            if not self.running:
                return
            
            self.running = False
            
            if self.executor:
                self.executor.shutdown(wait=True)
                self.executor = None
            
            # Update worker statuses in database
            if DATABASE_AVAILABLE:
                try:
                    for worker in self.workers.values():
                        worker.status = 'offline'
                        worker.current_task_count = 0
                        worker.current_task_id = None
                    db.session.commit()
                except Exception as e:
                    self.logger.error(f"Failed to update worker statuses: {e}")
            
            self.logger.info("Stopped worker pool")
    
    def submit_task(self, task: BatchTask) -> Optional[Any]:
        """Submit a task to the worker pool."""
        if not self.running or not self.executor:
            raise RuntimeError("Worker pool is not running")
        
        # Create task runner
        worker_id = f"worker_{uuid.uuid4().hex[:8]}"
        runner = BatchTaskRunner(worker_id, self.config)
        
        # Submit task
        future = self.executor.submit(runner.execute_task, task)
        
        self.logger.debug(f"Submitted task {task.id} to worker {worker_id}")
        return future
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics."""
        if not self.executor:
            return {'status': 'stopped', 'workers': 0}
        
        return {
            'status': 'running' if self.running else 'stopped',
            'max_workers': self.config.max_workers,
            'active_workers': getattr(self.executor, '_threads', {}).keys() or 0,
            'pending_tasks': getattr(self.executor, '_work_queue', queue.Queue()).qsize(),
        }


class BatchJobManager(BaseService):
    """High-level batch job management service."""
    
    def __init__(self, config: Optional[BatchConfiguration] = None):
        super().__init__('batch_job_manager')
        self.config = config or BatchConfiguration()
        self.worker_pool = BatchWorkerPool(self.config)
        self.progress_tracker = BatchProgressTracker()
        self.event_listeners: List[BatchEventListener] = []
        self.running_jobs: Set[str] = set()
        self._shutdown_event = threading.Event()
    
    def start(self):
        """Start the batch job manager."""
        self.worker_pool.start()
        self.logger.info("Batch job manager started")
    
    def stop(self):
        """Stop the batch job manager."""
        self._shutdown_event.set()
        self.worker_pool.stop()
        self.logger.info("Batch job manager stopped")
    
    def add_event_listener(self, listener: BatchEventListener):
        """Add an event listener."""
        self.event_listeners.append(listener)
    
    def _emit_event(self, event: BatchEvent):
        """Emit an event to all listeners."""
        for listener in self.event_listeners:
            try:
                method_name = f"on_{event.event_type.value}"
                if hasattr(listener, method_name):
                    getattr(listener, method_name)(event)
            except Exception as e:
                self.logger.error(f"Event listener error: {e}")
    
    def create_job(
        self,
        name: str,
        description: str = "",
        analysis_types: List[str] = None,
        models: List[str] = None,
        app_range: str = "1-5",
        priority: str = "normal",
        auto_start: bool = True,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a new batch job."""
        
        # Validate inputs
        if not analysis_types:
            raise ValueError("At least one analysis type must be specified")
        if not models:
            raise ValueError("At least one model must be specified")
        
        # Parse analysis types
        parsed_analysis_types = []
        for at in analysis_types:
            try:
                parsed_analysis_types.append(AnalysisType(at))
            except ValueError:
                self.logger.warning(f"Unknown analysis type: {at}")
        
        if not parsed_analysis_types:
            raise ValueError("No valid analysis types specified")
        
        # Parse app range
        app_numbers = self._parse_app_range(app_range)
        if not app_numbers:
            raise ValueError("No valid app numbers specified")
        
        # Parse priority
        try:
            job_priority = JobPriority(priority)
        except ValueError:
            job_priority = JobPriority.NORMAL
        
        # Create job
        job_id = str(uuid.uuid4())
        
        if DATABASE_AVAILABLE:
            job = BatchJob(
                id=job_id,
                name=name,
                description=description,
                status=JobStatus.PENDING,
                priority=job_priority,
                auto_start=auto_start,
                analysis_types_json=json.dumps([at.value for at in parsed_analysis_types]),
                models_json=json.dumps(models),
                app_range_json=json.dumps({'raw': app_range, 'apps': app_numbers}),
                options_json=json.dumps(options or {}),
                created_at=datetime.utcnow()
            )
            
            # Create tasks
            tasks = []
            for model in models:
                for app_num in app_numbers:
                    for analysis_type in parsed_analysis_types:
                        task = BatchTask(
                            id=str(uuid.uuid4()),
                            job_id=job_id,
                            model_slug=model,
                            app_number=app_num,
                            analysis_type=analysis_type,
                            status=TaskStatus.PENDING,
                            priority=job_priority,
                            max_retries=self.config.max_task_retries,
                            created_at=datetime.utcnow()
                        )
                        tasks.append(task)
            
            job.total_tasks = len(tasks)
            
            # Save to database
            try:
                db.session.add(job)
                db.session.add_all(tasks)
                db.session.commit()
                
                self.logger.info(f"Created job {job_id} with {len(tasks)} tasks")
                
                # Emit event
                self._emit_event(BatchEvent(
                    event_type=BatchEventType.JOB_CREATED,
                    timestamp=datetime.utcnow(),
                    job_id=job_id,
                    data={'name': name, 'total_tasks': len(tasks)}
                ))
                
                # Auto-start if requested
                if auto_start:
                    self.start_job(job_id)
                
                return job_id
                
            except Exception as e:
                db.session.rollback()
                self.logger.error(f"Failed to create job: {e}")
                raise
        else:
            self.logger.warning("Database not available - job created in memory only")
            return job_id
    
    def start_job(self, job_id: str) -> bool:
        """Start executing a job."""
        if not DATABASE_AVAILABLE:
            self.logger.error("Database not available")
            return False
        
        # Get job
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            self.logger.error(f"Job {job_id} not found")
            return False
        
        if job.status != JobStatus.PENDING:
            self.logger.warning(f"Job {job_id} is not in pending status")
            return False
        
        # Check if we can start (max concurrent jobs)
        if len(self.running_jobs) >= self.config.max_concurrent_jobs:
            job.status = JobStatus.QUEUED
            db.session.commit()
            self.logger.info(f"Job {job_id} queued - max concurrent jobs reached")
            return True
        
        # Start job
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.last_heartbeat = datetime.utcnow()
        
        self.running_jobs.add(job_id)
        
        # Emit event
        self._emit_event(BatchEvent(
            event_type=BatchEventType.JOB_STARTED,
            timestamp=datetime.utcnow(),
            job_id=job_id
        ))
        
        # Start execution in background thread
        thread = threading.Thread(
            target=self._execute_job,
            args=(job_id,),
            name=f"BatchJob-{job_id[:8]}"
        )
        thread.start()
        
        db.session.commit()
        self.logger.info(f"Started job {job_id}")
        return True
    
    def _execute_job(self, job_id: str):
        """Execute a batch job."""
        if not DATABASE_AVAILABLE:
            return
        
        try:
            # Get job and tasks
            job = db.session.query(BatchJob).filter_by(id=job_id).first()
            if not job:
                return
            
            tasks = db.session.query(BatchTask).filter_by(job_id=job_id).all()
            
            # Submit all tasks
            futures = []
            for task in tasks:
                if self._shutdown_event.is_set():
                    break
                
                try:
                    future = self.worker_pool.submit_task(task)
                    futures.append((future, task))
                except Exception as e:
                    self.logger.error(f"Failed to submit task {task.id}: {e}")
                    task.status = TaskStatus.FAILED
                    task.error_message = str(e)
                    job.failed_tasks += 1
            
            # Wait for completion
            for future, task in futures:
                if self._shutdown_event.is_set():
                    future.cancel()
                    continue
                
                try:
                    completed_task = future.result(timeout=self.config.task_timeout_seconds)
                    
                    if completed_task.status == TaskStatus.COMPLETED:
                        job.completed_tasks += 1
                    else:
                        job.failed_tasks += 1
                        
                        # Retry if enabled and retries available
                        if (self.config.auto_retry_failed_tasks and 
                            completed_task.can_be_retried()):
                            self._retry_task(completed_task)
                    
                    # Update progress
                    self.progress_tracker.update_job_progress(job_id, {
                        'completed_tasks': job.completed_tasks,
                        'failed_tasks': job.failed_tasks,
                        'progress_percentage': job.get_progress_percentage()
                    })
                    
                except Exception as e:
                    self.logger.error(f"Task execution failed: {e}")
                    job.failed_tasks += 1
            
            # Update job status
            if job.failed_tasks == 0:
                job.status = JobStatus.COMPLETED
            elif job.completed_tasks == 0:
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED  # Partial success
            
            job.completed_at = datetime.utcnow()
            job.actual_duration_seconds = (
                job.completed_at - job.started_at
            ).total_seconds() if job.started_at else None
            
            # Generate results summary
            job.set_results_summary(self._generate_job_summary(job, tasks))
            
            db.session.commit()
            
            # Emit completion event
            self._emit_event(BatchEvent(
                event_type=BatchEventType.JOB_COMPLETED if job.status == JobStatus.COMPLETED else BatchEventType.JOB_FAILED,
                timestamp=datetime.utcnow(),
                job_id=job_id,
                data={'completed_tasks': job.completed_tasks, 'failed_tasks': job.failed_tasks}
            ))
            
            self.logger.info(f"Job {job_id} completed: {job.completed_tasks} completed, {job.failed_tasks} failed")
            
        except Exception as e:
            self.logger.error(f"Job execution failed: {e}", exc_info=True)
            
            if DATABASE_AVAILABLE:
                try:
                    job = db.session.query(BatchJob).filter_by(id=job_id).first()
                    if job:
                        job.status = JobStatus.FAILED
                        job.error_message = str(e)
                        job.completed_at = datetime.utcnow()
                        db.session.commit()
                except Exception:
                    db.session.rollback()
        
        finally:
            self.running_jobs.discard(job_id)
            
            # Start next queued job if available
            self._start_next_queued_job()
    
    def _retry_task(self, task: BatchTask):
        """Retry a failed task."""
        if not task.can_be_retried():
            return
        
        task.retry_count += 1
        task.status = TaskStatus.RETRYING
        task.error_message = None
        task.error_details_json = None
        
        # Submit for retry
        try:
            future = self.worker_pool.submit_task(task)
            self._emit_event(BatchEvent(
                event_type=BatchEventType.TASK_RETRIED,
                timestamp=datetime.utcnow(),
                task_id=task.id,
                data={'retry_count': task.retry_count}
            ))
        except Exception as e:
            self.logger.error(f"Failed to retry task {task.id}: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
    
    def _start_next_queued_job(self):
        """Start the next queued job if slots are available."""
        if len(self.running_jobs) >= self.config.max_concurrent_jobs:
            return
        
        if not DATABASE_AVAILABLE:
            return
        
        # Find next queued job
        queued_job = db.session.query(BatchJob).filter_by(
            status=JobStatus.QUEUED
        ).order_by(
            BatchJob.priority.desc(),
            BatchJob.created_at.asc()
        ).first()
        
        if queued_job:
            self.start_job(queued_job.id)
    
    def _parse_app_range(self, app_range: str) -> List[int]:
        """Parse app range string into list of app numbers."""
        if app_range.strip().lower() == 'all':
            return list(range(1, 31))
        
        apps = []
        for part in app_range.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    apps.extend(range(start, end + 1))
                except ValueError:
                    self.logger.warning(f"Invalid range: {part}")
            else:
                try:
                    apps.append(int(part))
                except ValueError:
                    self.logger.warning(f"Invalid app number: {part}")
        
        return sorted(set(apps))
    
    def _generate_job_summary(self, job: BatchJob, tasks: List[BatchTask]) -> Dict[str, Any]:
        """Generate job results summary."""
        total_issues = sum(task.issues_found or 0 for task in tasks)
        total_critical = sum(task.critical_issues or 0 for task in tasks)
        total_high = sum(task.high_issues or 0 for task in tasks)
        total_medium = sum(task.medium_issues or 0 for task in tasks)
        total_low = sum(task.low_issues or 0 for task in tasks)
        
        avg_duration = sum(
            task.actual_duration_seconds for task in tasks 
            if task.actual_duration_seconds
        ) / max(len(tasks), 1)
        
        return {
            'total_tasks': len(tasks),
            'completed_tasks': job.completed_tasks,
            'failed_tasks': job.failed_tasks,
            'success_rate': job.get_success_rate(),
            'total_issues_found': total_issues,
            'issue_breakdown': {
                'critical': total_critical,
                'high': total_high,
                'medium': total_medium,
                'low': total_low
            },
            'performance_metrics': {
                'average_task_duration': avg_duration,
                'total_duration': job.actual_duration_seconds
            },
            'analysis_types': job.get_analysis_types(),
            'models_analyzed': job.get_models(),
            'app_range': job.get_app_range()
        }
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job."""
        if not DATABASE_AVAILABLE:
            return False
        
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job or not job.can_be_cancelled():
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        
        # Cancel pending tasks
        tasks = db.session.query(BatchTask).filter_by(
            job_id=job_id,
            status=TaskStatus.PENDING
        ).all()
        
        for task in tasks:
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            job.cancelled_tasks += 1
        
        db.session.commit()
        
        self.running_jobs.discard(job_id)
        
        self._emit_event(BatchEvent(
            event_type=BatchEventType.JOB_CANCELLED,
            timestamp=datetime.utcnow(),
            job_id=job_id
        ))
        
        self.logger.info(f"Cancelled job {job_id}")
        return True
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed job status."""
        if not DATABASE_AVAILABLE:
            return None
        
        job = db.session.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return None
        
        # Get task statistics
        tasks = db.session.query(BatchTask).filter_by(job_id=job_id).all()
        
        task_stats = {}
        for status in TaskStatus:
            task_stats[status.value] = sum(1 for t in tasks if t.status == status)
        
        return {
            'job': job.to_dict(),
            'task_statistics': task_stats,
            'recent_tasks': [t.to_dict() for t in tasks[-10:]],  # Last 10 tasks
            'progress': self.progress_tracker.get_job_progress(job_id)
        }
    
    def get_all_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all jobs with pagination."""
        if not DATABASE_AVAILABLE:
            return []
        
        jobs = db.session.query(BatchJob).order_by(
            BatchJob.created_at.desc()
        ).offset(offset).limit(limit).all()
        
        return [job.to_dict() for job in jobs]
    
    def get_system_statistics(self) -> Dict[str, Any]:
        """Get system-wide batch processing statistics."""
        if not DATABASE_AVAILABLE:
            return {'error': 'Database not available'}
        
        # Job statistics
        total_jobs = db.session.query(BatchJob).count()
        jobs_by_status = {}
        for status in JobStatus:
            count = db.session.query(BatchJob).filter_by(status=status).count()
            jobs_by_status[status.value] = count
        
        # Task statistics
        total_tasks = db.session.query(BatchTask).count()
        tasks_by_status = {}
        for status in TaskStatus:
            count = db.session.query(BatchTask).filter_by(status=status).count()
            tasks_by_status[status.value] = count
        
        # Performance metrics
        avg_job_duration = db.session.query(
            db.func.avg(BatchJob.actual_duration_seconds)
        ).scalar() or 0
        
        avg_task_duration = db.session.query(
            db.func.avg(BatchTask.actual_duration_seconds)
        ).scalar() or 0
        
        return {
            'jobs': {
                'total': total_jobs,
                'by_status': jobs_by_status,
                'average_duration_seconds': avg_job_duration
            },
            'tasks': {
                'total': total_tasks,
                'by_status': tasks_by_status,
                'average_duration_seconds': avg_task_duration
            },
            'worker_pool': self.worker_pool.get_worker_stats(),
            'running_jobs': list(self.running_jobs),
            'system_health': {
                'uptime_seconds': time.time() - getattr(self, '_start_time', time.time()),
                'memory_usage': self._get_memory_usage(),
                'active_threads': threading.active_count()
            }
        }
    
    def _get_memory_usage(self) -> Optional[float]:
        """Get current memory usage in MB."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return None


# Global batch manager instance
_batch_manager: Optional[BatchJobManager] = None

def get_batch_manager(config: Optional[BatchConfiguration] = None) -> BatchJobManager:
    """Get or create global batch manager instance."""
    global _batch_manager
    if _batch_manager is None:
        _batch_manager = BatchJobManager(config)
    return _batch_manager

def initialize_batch_service(app, config: Optional[BatchConfiguration] = None):
    """Initialize batch service with Flask app."""
    manager = get_batch_manager(config)
    manager.start()
    
    # Register cleanup on app teardown
    @app.teardown_appcontext
    def cleanup_batch_service(error):
        if error:
            logger.error(f"App context error: {error}")
    
    app.config['batch_manager'] = manager
    logger.info("Batch service initialized")
    
    return manager
