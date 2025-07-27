"""
Improved Batch Analysis Module for Flask Application
=====================================================

Provides robust batch processing capabilities for security and performance analysis.
Fixes bugs and improves error handling, API consistency, and data serialization.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass, field
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import json

from flask import (
    Blueprint, render_template, request, jsonify, flash, redirect, 
    url_for, current_app
)

if TYPE_CHECKING:
    from flask import Flask

from logging_service import create_logger_for_component

# Initialize logger
logger = create_logger_for_component('batch_analysis')


class JobStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELLING = "cancelling"
    ARCHIVED = "archived"
    ERROR = "error"


class TaskStatus(Enum):
    """Status of a batch task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class AnalysisType(Enum):
    """Types of analysis that can be performed."""
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_SECURITY = "backend_security"
    PERFORMANCE = "performance"
    ZAP = "zap"
    GPT4ALL = "gpt4all"
    CODE_QUALITY = "code_quality"


@dataclass
class BatchTask:
    """Represents a single task within a batch job."""
    id: str
    job_id: str
    model: str
    app_num: int
    analysis_type: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    issues_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "model": self.model,
            "app_num": self.app_num,
            "analysis_type": self.analysis_type,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "result": self.result,
            "error": self.error,
            "issues_count": self.issues_count
        }


@dataclass
class BatchJob:
    """Represents a batch analysis job."""
    id: str
    name: str
    description: str
    status: JobStatus
    analysis_types: List[AnalysisType]
    models: List[str]
    app_range: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Dict[str, int] = field(default_factory=lambda: {"total": 0, "completed": 0, "failed": 0})
    results: List[Dict] = field(default_factory=list)
    error_message: Optional[str] = None
    auto_start: bool = True

    @property
    def created_at_formatted(self) -> str:
        """Format created_at for display."""
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "analysis_types": [at.value if hasattr(at, 'value') else str(at) for at in self.analysis_types],
            "models": self.models,
            "app_range": self.app_range,
            "created_at": self.created_at.isoformat(),
            "created_at_formatted": self.created_at_formatted,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "results": self.results,
            "error_message": self.error_message,
            "auto_start": self.auto_start
        }


class BatchTaskWorker:
    """Worker class for executing batch analysis tasks."""
    
    def __init__(self, app: 'Flask'):
        self.app = app
        self.logger = create_logger_for_component('batch_worker')
    
    def execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single analysis task."""
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            with self.app.app_context():
                result = self._run_analysis(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
                if result and 'issues' in result:
                    task.issues_count = len(result.get('issues', []))
                elif result and 'issues_count' in result:
                    task.issues_count = result['issues_count']
                else:
                    task.issues_count = 0
                
        except Exception as e:
            self.logger.error(f"Task {task.id} failed: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = {
                "message": str(e),
                "category": type(e).__name__
            }
        
        finally:
            task.completed_at = datetime.now()
            task.duration_seconds = time.time() - start_time
        
        return task
    
    def _run_analysis(self, task: BatchTask) -> Dict[str, Any]:
        """Run the specific analysis for the task."""
        analysis_type = task.analysis_type
        model = task.model
        app_num = task.app_num
        
        self.logger.info(f"Running {analysis_type} analysis for {model} app {app_num}")
        
        # Check if we're in development mode and should use mock data
        use_mock = current_app.config.get('USE_MOCK_ANALYSIS', False)
        
        if use_mock:
            return self._generate_mock_result(analysis_type, model, app_num)
        
        # Get the appropriate analyzer based on analysis type
        if analysis_type == AnalysisType.FRONTEND_SECURITY.value:
            analyzer = getattr(current_app, 'frontend_security_analyzer', None)
            if not analyzer:
                raise ValueError("Frontend security analyzer not available")
            
            issues, status, outputs = analyzer.run_security_analysis(
                model, app_num, use_all_tools=True
            )
            
            return {
                "issues": issues,
                "tool_status": status,
                "outputs": outputs,
                "summary": f"Found {len(issues)} security issues"
            }
            
        elif analysis_type == AnalysisType.BACKEND_SECURITY.value:
            analyzer = getattr(current_app, 'backend_security_analyzer', None)
            if not analyzer:
                raise ValueError("Backend security analyzer not available")
            
            issues, status, outputs = analyzer.run_security_analysis(
                model, app_num, use_all_tools=True
            )
            
            return {
                "issues": issues,
                "tool_status": status,
                "outputs": outputs,
                "summary": f"Found {len(issues)} security issues"
            }
            
        elif analysis_type == AnalysisType.PERFORMANCE.value:
            analyzer = getattr(current_app, 'performance_analyzer', None)
            if not analyzer:
                raise ValueError("Performance analyzer not available")
            
            result = analyzer.run_performance_test(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.ZAP.value:
            scanner = getattr(current_app, 'zap_scanner', None)
            if not scanner:
                raise ValueError("ZAP scanner not available")
            
            result = scanner.scan_app(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.GPT4ALL.value:
            analyzer = getattr(current_app, 'gpt4all_analyzer', None)
            if not analyzer:
                raise ValueError("GPT4All analyzer not available")
            
            result = analyzer.analyze_app(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.CODE_QUALITY.value:
            analyzer = getattr(current_app, 'code_quality_analyzer', None)
            if not analyzer:
                raise ValueError("Code quality analyzer not available")
            
            result = analyzer.analyze_app(model, app_num)
            return result
            
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    def _generate_mock_result(self, analysis_type: str, model: str, app_num: int, 
                            error_msg: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock results for testing."""
        if error_msg:
            return {
                "error": error_msg,
                "summary": f"Mock {analysis_type} analysis failed",
                "issues": []
            }
        
        if analysis_type in [AnalysisType.FRONTEND_SECURITY.value, AnalysisType.BACKEND_SECURITY.value]:
            # Mock security issues
            return {
                "issues": [
                    {
                        "id": f"mock-issue-1-{model}-{app_num}",
                        "severity": "HIGH",
                        "issue_type": "Mock Security Issue",
                        "issue_text": f"This is a mock {analysis_type} issue for {model} app {app_num}",
                        "filename": f"mock_file_{app_num}.js",
                        "line_number": 42
                    },
                    {
                        "id": f"mock-issue-2-{model}-{app_num}", 
                        "severity": "MEDIUM",
                        "issue_type": "Mock Warning",
                        "issue_text": f"This is a mock medium severity issue for {model}",
                        "filename": f"another_file_{app_num}.py",
                        "line_number": 100
                    }
                ],
                "tool_status": {
                    "mock_tool": "Completed with mock data"
                },
                "summary": "Found 2 mock issues"
            }
        
        elif analysis_type == AnalysisType.PERFORMANCE.value:
            # Mock performance data
            return {
                "requests_per_sec": 150.5 + (app_num * 10),
                "avg_response_time": 45.2 + (app_num * 5),
                "median_response_time": 40.0 + (app_num * 4),
                "percentile_95": 120.0 + (app_num * 10),
                "total_requests": 1000,
                "total_failures": 5,
                "summary": "Mock performance test completed"
            }
        
        else:
            # Generic mock response
            return {
                "status": "completed",
                "summary": f"Mock {analysis_type} analysis completed for {model} app {app_num}",
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "app_num": app_num
                }
            }


class BatchAnalysisService:
    """Service for managing batch analysis jobs."""
    
    def __init__(self, app: Optional['Flask'] = None):
        self.jobs: Dict[str, BatchJob] = {}
        self.tasks: Dict[str, BatchTask] = {}
        self.app: Optional['Flask'] = app
        self.worker_pool: Optional[ThreadPoolExecutor] = None
        self.job_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
        self.logger = create_logger_for_component('batch_service')
        self._lock = threading.Lock()
        
        if app:
            self.init_app(app)

    def init_app(self, app: 'Flask'):
        """Initialize the service with Flask app."""
        self.app = app
        max_workers = app.config.get('BATCH_MAX_WORKERS', 4)
        self.worker_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.logger.info(f"Batch analysis service initialized with {max_workers} workers")

    def create_job(self, name: str, description: str, analysis_types: List[str],
                   models: List[str], app_range_str: str, 
                   auto_start: bool = True) -> BatchJob:
        """Create a new batch job."""
        # Parse app range
        app_range = self._parse_app_range(app_range_str)
        
        # Validate inputs
        if not analysis_types:
            raise ValueError("At least one analysis type must be selected")
        if not models:
            raise ValueError("At least one model must be selected")
        if not app_range['apps']:
            raise ValueError("Invalid app range specified")
        
        # Convert string analysis types to enums
        analysis_type_enums = []
        for at_str in analysis_types:
            try:
                analysis_type_enums.append(AnalysisType(at_str))
            except ValueError:
                self.logger.warning(f"Unknown analysis type: {at_str}")
                continue
        
        if not analysis_type_enums:
            raise ValueError("No valid analysis types specified")
        
        # Create job
        job_id = str(uuid.uuid4())
        job = BatchJob(
            id=job_id,
            name=name,
            description=description or "",
            status=JobStatus.PENDING,
            analysis_types=analysis_type_enums,
            models=models,
            app_range=app_range,
            created_at=datetime.now(),
            auto_start=auto_start
        )
        
        # Calculate total tasks
        total_tasks = len(models) * len(app_range['apps']) * len(analysis_type_enums)
        job.progress['total'] = total_tasks
        
        # Create tasks
        for model in models:
            for app_num in app_range['apps']:
                for analysis_type in analysis_type_enums:
                    task_id = str(uuid.uuid4())
                    task = BatchTask(
                        id=task_id,
                        job_id=job_id,
                        model=model,
                        app_num=app_num,
                        analysis_type=analysis_type.value
                    )
                    self.tasks[task_id] = task
        
        # Store job
        with self._lock:
            self.jobs[job_id] = job
        
        self.logger.info(f"Created batch job {job_id} with {total_tasks} tasks")
        
        # Auto-start if enabled
        if auto_start:
            self.start_job(job_id)
        
        return job

    def _parse_app_range(self, app_range_str: str) -> Dict[str, Any]:
        """Parse app range string into list of app numbers."""
        apps = []
        parts = app_range_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range (e.g., "1-5")
                try:
                    start, end = part.split('-')
                    start = int(start.strip())
                    end = int(end.strip())
                    if start <= end:
                        apps.extend(range(start, end + 1))
                except ValueError:
                    self.logger.warning(f"Invalid range format: {part}")
            else:
                # Single number
                try:
                    apps.append(int(part))
                except ValueError:
                    self.logger.warning(f"Invalid app number: {part}")
        
        # Remove duplicates and sort
        apps = sorted(list(set(apps)))
        
        return {
            "raw": app_range_str,
            "apps": apps
        }

    def get_all_jobs(self) -> List[BatchJob]:
        """Get all jobs."""
        with self._lock:
            return list(self.jobs.values())

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a specific job."""
        return self.jobs.get(job_id)

    def get_job_tasks(self, job_id: str) -> List[BatchTask]:
        """Get all tasks for a job."""
        return [task for task in self.tasks.values() if task.job_id == job_id]

    def get_task(self, task_id: str) -> Optional[BatchTask]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            "total": len(self.jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self.jobs.values():
            status = job.status.value if hasattr(job.status, 'value') else str(job.status)
            if status in stats:
                stats[status] += 1
        
        return stats

    def start_job(self, job_id: str) -> bool:
        """Start executing a job."""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False
        
        # Start job execution in a separate thread
        thread = threading.Thread(
            target=self._execute_job,
            args=(job_id,),
            name=f"BatchJob-{job_id[:8]}"
        )
        
        with self._lock:
            self.job_threads[job_id] = thread
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
        
        thread.start()
        self.logger.info(f"Started batch job: {job_id}")
        return True

    def _execute_job(self, job_id: str):
        """Execute a job by running all its tasks."""
        job = self.get_job(job_id)
        if not job:
            return
        
        try:
            tasks = self.get_job_tasks(job_id)
            worker = BatchTaskWorker(self.app)
            
            # Submit tasks to worker pool
            futures = []
            for task in tasks:
                if self.shutdown_event.is_set():
                    break
                    
                future = self.worker_pool.submit(worker.execute_task, task)
                futures.append((future, task))
            
            # Wait for tasks to complete
            for future, task in futures:
                if self.shutdown_event.is_set():
                    future.cancel()
                    continue
                
                try:
                    completed_task = future.result(timeout=300)  # 5 minute timeout
                    self.tasks[task.id] = completed_task
                    
                    # Update progress
                    if completed_task.status == TaskStatus.COMPLETED:
                        job.progress["completed"] += 1
                    elif completed_task.status == TaskStatus.FAILED:
                        job.progress["failed"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Task {task.id} execution failed: {str(e)}")
                    task.status = TaskStatus.FAILED
                    task.error = {"message": str(e), "category": "ExecutionError"}
                    self.tasks[task.id] = task
                    job.progress["failed"] = job.progress.get("failed", 0) + 1
            
            # Determine final job status
            failed_count = job.progress.get("failed", 0)
            if failed_count == 0:
                job.status = JobStatus.COMPLETED
            elif failed_count == len(tasks):
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED  # Partial success
            
        except Exception as e:
            self.logger.error(f"Job {job_id} execution failed: {str(e)}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
        
        finally:
            job.completed_at = datetime.now()
            with self._lock:
                if job_id in self.job_threads:
                    del self.job_threads[job_id]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            
            # Cancel running tasks
            for task in self.get_job_tasks(job_id):
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                    self.tasks[task.id] = task
            
            self.logger.info(f"Cancelled batch job: {job_id}")
            return True
        return False

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its tasks."""
        with self._lock:
            if job_id in self.jobs:
                # Remove all tasks for this job
                task_ids_to_remove = [task_id for task_id, task in self.tasks.items() 
                                    if task.job_id == job_id]
                for task_id in task_ids_to_remove:
                    del self.tasks[task_id]
                
                del self.jobs[job_id]
                self.logger.info(f"Deleted batch job: {job_id}")
                return True
        return False

    def archive_job(self, job_id: str) -> bool:
        """Archive a completed job."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.status = JobStatus.ARCHIVED
            self.logger.info(f"Archived batch job: {job_id}")
            return True
        return False

    def clean_corrupted_jobs(self):
        """Clean up any corrupted jobs."""
        with self._lock:
            corrupted_job_ids = []
            for job_id, job in self.jobs.items():
                try:
                    # Try to access job properties
                    _ = job.status
                    _ = job.created_at
                except Exception as e:
                    self.logger.warning(f"Found corrupted job {job_id}: {str(e)}")
                    corrupted_job_ids.append(job_id)
            
            for job_id in corrupted_job_ids:
                del self.jobs[job_id]
                # Also remove associated tasks
                task_ids_to_remove = [task_id for task_id, task in self.tasks.items() 
                                    if task.job_id == job_id]
                for task_id in task_ids_to_remove:
                    del self.tasks[task_id]

    def shutdown(self):
        """Shutdown the batch service."""
        self.shutdown_event.set()
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True)
        
        # Wait for job threads to complete
        for thread in self.job_threads.values():
            thread.join(timeout=5)


# Create the blueprint
batch_analysis_bp = Blueprint('batch_analysis', __name__, url_prefix='/batch-analysis')


# Helper functions for safe template data
def _create_safe_job_dict(job: BatchJob) -> Dict[str, Any]:
    """Create a template-safe job dictionary."""
    try:
        return job.to_dict()
    except Exception as e:
        logger.error(f"Error creating safe job dict: {str(e)}")
        # Return minimal safe data
        return {
            'id': str(job.id) if hasattr(job, 'id') else 'unknown',
            'name': str(job.name) if hasattr(job, 'name') else 'Unknown Job',
            'description': '',
            'status': 'error',
            'created_at_formatted': 'Unknown',
            'progress': {'total': 0, 'completed': 0, 'failed': 0}
        }


def _create_safe_task_dict(task: BatchTask) -> Dict[str, Any]:
    """Create a template-safe task dictionary."""
    try:
        return task.to_dict()
    except Exception as e:
        logger.error(f"Error creating safe task dict: {str(e)}")
        # Return minimal safe data
        return {
            'id': str(task.id) if hasattr(task, 'id') else 'unknown',
            'model': str(task.model) if hasattr(task, 'model') else 'unknown',
            'app_num': int(task.app_num) if hasattr(task, 'app_num') else 0,
            'analysis_type': str(task.analysis_type) if hasattr(task, 'analysis_type') else 'unknown',
            'status': 'error',
            'issues_count': None,
            'duration_seconds': None
        }


def _calculate_progress_stats(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate progress statistics from tasks."""
    stats = {
        'progress': {
            'total': len(tasks),
            'completed': 0,
            'running': 0,
            'pending': 0,
            'failed': 0,
            'cancelled': 0
        }
    }
    
    for task in tasks:
        status = task.get('status', 'unknown')
        if status in stats['progress']:
            stats['progress'][status] += 1
    
    return stats


# Routes
@batch_analysis_bp.route('/')
def batch_dashboard():
    """Main batch analysis dashboard."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            flash("Batch analysis service not available", "error")
            return render_template('error.html', error_message="Batch analysis service not available"), 500
        
        # Clean up any corrupted jobs first
        service.clean_corrupted_jobs()
        
        jobs = service.get_all_jobs()
        
        # Create safe job representations for templates
        safe_jobs = []
        for job in jobs:
            try:
                safe_job = _create_safe_job_dict(job)
                safe_jobs.append(safe_job)
            except Exception as e:
                logger.warning(f"Skipping corrupted job: {str(e)}")
                continue
        
        # Sort jobs by created_at descending
        safe_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        stats = service.get_job_stats()
        if not stats or not isinstance(stats, dict):
            # Provide default stats if service returns invalid data
            stats = {
                "total": 0,
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0
            }
        
        # Get models list
        raw_models = current_app.config.get('AI_MODELS', [])
        models = []
        for model in raw_models:
            if hasattr(model, 'name'):
                models.append(model.name)
            elif hasattr(model, 'id'):
                models.append(model.id)
            elif isinstance(model, str):
                models.append(model)
            else:
                models.append(str(model))
        
        default_job_name = f"Batch Job {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        analysis_types = list(AnalysisType)
        
        return render_template(
            'batch_dashboard.html',
            view_mode='dashboard',
            jobs=safe_jobs,
            job_stats=stats,
            models=models,
            default_job_name=default_job_name,
            analysis_types=analysis_types
        )
    except Exception as e:
        logger.error(f"Error in batch_dashboard: {str(e)}", exc_info=True)
        flash(f"Error loading dashboard: {str(e)}", "error")
        return render_template('error.html', error_message=str(e)), 500


@batch_analysis_bp.route('/create', methods=['GET', 'POST'])
def create_batch_job():
    """Create a new batch job."""
    if request.method == 'POST':
        try:
            service = getattr(current_app, 'batch_service', None)
            if not service:
                flash("Batch analysis service not available", "error")
                return redirect(url_for('batch_analysis.batch_dashboard'))
            
            # Get form data
            job_name = request.form.get('job_name', '').strip()
            description = request.form.get('description', '').strip()
            analysis_types = request.form.getlist('analysis_types')
            models = request.form.getlist('models')
            app_range = request.form.get('app_range', '').strip()
            auto_start = request.form.get('auto_start', 'true').lower() == 'true'
            
            # Create job
            job = service.create_job(
                name=job_name,
                description=description,
                analysis_types=analysis_types,
                models=models,
                app_range_str=app_range,
                auto_start=auto_start
            )
            
            flash(f"Batch job '{job.name}' created successfully!", "success")
            return redirect(url_for('batch_analysis.view_job', job_id=job.id))
            
        except Exception as e:
            logger.error(f"Error creating batch job: {str(e)}", exc_info=True)
            flash(f"Error creating job: {str(e)}", "error")
            return redirect(url_for('batch_analysis.create_batch_job'))
    
    # GET request
    try:
        # Get models list
        raw_models = current_app.config.get('AI_MODELS', [])
        models = []
        for model in raw_models:
            if hasattr(model, 'name'):
                models.append(model.name)
            elif hasattr(model, 'id'):
                models.append(model.id)
            elif isinstance(model, str):
                models.append(model)
            else:
                models.append(str(model))
        
        default_job_name = f"Batch Job {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Enhanced analysis types with availability and descriptions
        analysis_types_info = []
        
        # Check availability of each analyzer
        for analysis_type in AnalysisType:
            info = {
                'value': analysis_type.value,
                'name': analysis_type.value.replace('_', ' ').title(),
                'available': True,
                'description': '',
                'status_message': '',
                'recommended': False
            }
            
            # Check specific analyzer availability and add descriptions
            if analysis_type == AnalysisType.FRONTEND_SECURITY:
                analyzer = getattr(current_app, 'frontend_security_analyzer', None)
                info['description'] = 'Scans frontend code for security vulnerabilities using npm-audit, ESLint, and JSHint'
                info['available'] = analyzer is not None
                info['recommended'] = True
                if not info['available']:
                    info['status_message'] = 'Frontend analyzer not available'
                elif hasattr(analyzer, 'available_tools'):
                    tools = getattr(analyzer, 'available_tools', [])
                    if tools:
                        info['status_message'] = f'Available tools: {", ".join(tools)}'
                    else:
                        info['status_message'] = 'No security tools available'
                        info['available'] = False
                        
            elif analysis_type == AnalysisType.BACKEND_SECURITY:
                analyzer = getattr(current_app, 'backend_security_analyzer', None)
                info['description'] = 'Analyzes backend code for security issues and vulnerabilities'
                info['available'] = analyzer is not None
                info['recommended'] = True
                if not info['available']:
                    info['status_message'] = 'Backend analyzer not available'
                elif hasattr(analyzer, 'available_tools'):
                    tools = getattr(analyzer, 'available_tools', [])
                    if tools:
                        info['status_message'] = f'Available tools: {", ".join(tools)}'
                    else:
                        info['status_message'] = 'No security tools available'
                        
            elif analysis_type == AnalysisType.PERFORMANCE:
                analyzer = getattr(current_app, 'performance_analyzer', None)
                info['description'] = 'Load testing and performance analysis using Locust framework'
                info['available'] = analyzer is not None and hasattr(analyzer, 'run_performance_test')
                if not info['available']:
                    analyzer_alt = getattr(current_app, 'performance_tester', None)
                    if analyzer_alt and hasattr(analyzer_alt, 'run_performance_test'):
                        info['available'] = True
                        info['status_message'] = 'Performance testing available'
                    else:
                        info['status_message'] = 'Performance testing unavailable (gevent module required)'
                        
            elif analysis_type == AnalysisType.ZAP:
                analyzer = getattr(current_app, 'zap_scanner', None)
                info['description'] = 'OWASP ZAP dynamic security scanning for web applications'
                
                # Check if analyzer exists and has the required methods
                if analyzer and hasattr(analyzer, 'scan_app'):
                    # Check if ZAP is available (zapv2 module exists, etc.)
                    if hasattr(analyzer, 'is_available'):
                        info['available'] = analyzer.is_available()
                        if info['available']:
                            info['status_message'] = 'ZAP dynamic security scanning ready'
                        else:
                            info['status_message'] = 'ZAP scanner unavailable (zapv2 module required)'
                    else:
                        # Fallback: assume available if scanner exists
                        info['available'] = True
                        info['status_message'] = 'ZAP dynamic security scanning ready'
                else:
                    info['available'] = False
                    info['status_message'] = 'ZAP scanner not found'
                    
            elif analysis_type == AnalysisType.GPT4ALL:
                analyzer = getattr(current_app, 'gpt4all_analyzer', None)
                info['description'] = 'Requirements compliance and code quality analysis using GPT4All'
                info['available'] = analyzer is not None and hasattr(analyzer, 'analyze_app')
                if info['available']:
                    info['status_message'] = 'GPT4All requirements analysis ready'
                else:
                    info['status_message'] = 'GPT4All analyzer not available'
                    
            elif analysis_type == AnalysisType.CODE_QUALITY:
                info['description'] = 'General code quality metrics and static analysis'
                info['available'] = False  # Not implemented yet
                info['status_message'] = 'Code quality analysis not yet implemented'
            
            analysis_types_info.append(info)
        
        return render_template(
            'batch_dashboard.html',
            view_mode='create',
            models=models,
            default_job_name=default_job_name,
            analysis_types=analysis_types_info
        )
    except Exception as e:
        logger.error(f"Error loading create job form: {str(e)}")
        flash(f"Error loading form: {str(e)}", "error")
        return redirect(url_for('batch_analysis.batch_dashboard'))


@batch_analysis_bp.route('/job/<job_id>')
def view_job(job_id):
    """View details of a specific job."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            flash("Batch analysis service not available", "error")
            return redirect(url_for('batch_analysis.batch_dashboard'))
        
        job = service.get_job(job_id)
        if not job:
            flash("Job not found", "error")
            return redirect(url_for('batch_analysis.batch_dashboard'))
        
        # Get tasks for this job
        tasks = service.get_job_tasks(job_id)
        
        # Create safe representations
        safe_job = _create_safe_job_dict(job)
        safe_tasks = [_create_safe_task_dict(task) for task in tasks]
        
        # Sort tasks by model, app_num, and analysis_type
        safe_tasks.sort(key=lambda x: (x.get('model', ''), x.get('app_num', 0), x.get('analysis_type', '')))
        
        # Calculate progress statistics
        progress_stats = _calculate_progress_stats(safe_tasks)
        
        return render_template(
            'batch_dashboard.html',
            view_mode='view_job',
            job=safe_job,
            results=safe_tasks,
            status_data=progress_stats
        )
    except Exception as e:
        logger.error(f"Error viewing job {job_id}: {str(e)}", exc_info=True)
        flash(f"Error loading job: {str(e)}", "error")
        return redirect(url_for('batch_analysis.batch_dashboard'))


@batch_analysis_bp.route('/job/<job_id>/status')
def get_job_status(job_id):
    """Get real-time status of a job (for polling)."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            return jsonify({"error": "Batch service not available"}), 500
        
        job = service.get_job(job_id)
        if not job:
            return jsonify({"error": "Job not found"}), 404
        
        tasks = service.get_job_tasks(job_id)
        
        # Create safe representations
        safe_job = _create_safe_job_dict(job)
        safe_tasks = [_create_safe_task_dict(task) for task in tasks]
        
        return jsonify({
            "job": safe_job,
            "tasks": safe_tasks,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@batch_analysis_bp.route('/task/<task_id>')
def get_task_details(task_id):
    """Get details of a specific task."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            return jsonify({"error": "Batch service not available"}), 500
        
        task = service.get_task(task_id)
        if not task:
            return jsonify({"error": "Task not found"}), 404
        
        safe_task = _create_safe_task_dict(task)
        return jsonify(safe_task)
    except Exception as e:
        logger.error(f"Error getting task details {task_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@batch_analysis_bp.route('/job/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    """Cancel a job."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            return jsonify({"error": "Batch service not available"}), 500
        
        success = service.cancel_job(job_id)
        if success:
            return jsonify({"success": True, "message": "Job cancelled"})
        else:
            return jsonify({"error": "Could not cancel job"}), 400
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


@batch_analysis_bp.route('/api/jobs')
def api_get_jobs():
    """API endpoint to get all jobs with stats."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            return jsonify({"error": "Batch service not available"}), 500
        
        jobs = service.get_all_jobs()
        safe_jobs = []
        
        for job in jobs:
            try:
                safe_job = _create_safe_job_dict(job)
                safe_jobs.append(safe_job)
            except Exception as e:
                logger.warning(f"Skipping corrupted job in API: {str(e)}")
                continue
        
        # Sort jobs by created_at descending
        safe_jobs.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        
        stats = service.get_job_stats()
        if not stats or not isinstance(stats, dict):
            # Provide default stats if service returns invalid data
            stats = {
                "total": 0,
                "pending": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "cancelled": 0
            }
        
        return jsonify({
            "jobs": safe_jobs,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"API error getting jobs: {str(e)}")
        return jsonify({"error": str(e)}), 500


@batch_analysis_bp.route('/job/<job_id>/delete', methods=['POST'])
def delete_job(job_id):
    """Delete a job."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            flash("Batch service not available", "error")
            return redirect(url_for('batch_analysis.batch_dashboard'))
        
        success = service.delete_job(job_id)
        if success:
            flash("Job deleted successfully", "success")
        else:
            flash("Could not delete job", "error")
        
        return redirect(url_for('batch_analysis.batch_dashboard'))
    except Exception as e:
        logger.error(f"Error deleting job {job_id}: {str(e)}")
        flash(f"Error deleting job: {str(e)}", "error")
        return redirect(url_for('batch_analysis.batch_dashboard'))


@batch_analysis_bp.route('/job/<job_id>/archive', methods=['POST'])
def archive_job(job_id):
    """Archive a completed job."""
    try:
        service = getattr(current_app, 'batch_service', None)
        if not service:
            return jsonify({"error": "Batch service not available"}), 500
        
        success = service.archive_job(job_id)
        if success:
            return jsonify({"success": True, "message": "Job archived"})
        else:
            return jsonify({"error": "Could not archive job"}), 400
    except Exception as e:
        logger.error(f"Error archiving job {job_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500


def init_batch_analysis(app: 'Flask') -> None:
    """Initialize the batch analysis module with the Flask app."""
    try:
        # Create and initialize the batch service
        batch_service = BatchAnalysisService()
        batch_service.init_app(app)
        
        # Attach the service to the app
        app.batch_service = batch_service
        
        # Register the blueprint
        app.register_blueprint(batch_analysis_bp)
        
        logger.info("Batch analysis module initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize batch analysis module: {str(e)}")
        raise