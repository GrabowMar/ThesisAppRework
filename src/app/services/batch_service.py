"""
Batch Analysis Service for Celery App

Manages batch analysis jobs for processing multiple AI-generated applications.
Provides job creation, progress tracking, and result aggregation.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor
import threading

from ..models import BatchAnalysis
from ..constants import JobStatus, AnalysisType
from ..extensions import get_session

logger = logging.getLogger(__name__)


class BatchJob:
    """Represents a batch analysis job."""
    
    def __init__(self, id: str, name: str, description: str, 
                 analysis_types: List[AnalysisType], models: List[str], 
                 app_range: List[int], options: Optional[Dict[str, Any]] = None):
        self.id = id
        self.name = name
        self.description = description
        self.status = JobStatus.PENDING
        self.analysis_types = analysis_types
        self.models = models
        self.app_range = app_range
        self.options = options or {}
        self.created_at = datetime.now(timezone.utc)
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.total_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.results = {}
        self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'analysis_types': [at.value for at in self.analysis_types],
            'models': self.models,
            'app_range': self.app_range,
            'options': self.options,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'progress_percentage': (self.completed_tasks / self.total_tasks * 100) if self.total_tasks > 0 else 0,
            'results': self.results,
            'errors': self.errors
        }


class BatchAnalysisService:
    """Service for managing batch analysis jobs using Celery."""
    
    def __init__(self):
        self.logger = logger
        self.jobs: Dict[str, BatchJob] = {}
        self.worker_pool: Optional[ThreadPoolExecutor] = None
        self.shutdown_event = threading.Event()
        self.max_workers = 4
    
    def initialize(self, max_workers: int = 4):
        """Initialize the service with worker pool."""
        self.max_workers = max_workers
        self.worker_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.logger.info(f"Batch analysis service initialized with {max_workers} workers")
    
    def create_job(self, name: str, description: str, analysis_types: List[str],
                   models: List[str], app_range_str: str, 
                   options: Optional[Dict[str, Any]] = None) -> str:
        """Create a new batch analysis job."""
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Parse analysis types
        analysis_type_enums = []
        for at in analysis_types:
            try:
                analysis_type_enums.append(AnalysisType(at))
            except ValueError:
                self.logger.warning(f"Unknown analysis type: {at}")
        
        # Parse app range
        app_range = self._parse_app_range(app_range_str)
        
        # Create job
        job = BatchJob(
            id=job_id,
            name=name,
            description=description,
            analysis_types=analysis_type_enums,
            models=models,
            app_range=app_range,
            options=options or {}
        )
        
        # Calculate total tasks
        job.total_tasks = len(models) * len(app_range) * len(analysis_type_enums)
        
        # Store job
        self.jobs[job_id] = job
        
        # Create database record
        try:
            with get_session() as session:
                batch_analysis = BatchAnalysis()
                batch_analysis.batch_id = job_id
                batch_analysis.status = JobStatus.PENDING
                batch_analysis.total_tasks = job.total_tasks
                batch_analysis.completed_tasks = 0
                batch_analysis.failed_tasks = 0
                batch_analysis.set_analysis_types([at.value for at in analysis_type_enums])
                batch_analysis.set_model_filter(models)
                batch_analysis.set_app_filter(app_range)
                batch_analysis.set_config(options or {})
                
                session.add(batch_analysis)
                session.commit()
                
                self.logger.info(f"Created batch job {job_id} with {job.total_tasks} tasks")
        
        except Exception as e:
            self.logger.error(f"Failed to create database record for batch job: {e}")
        
        return job_id
    
    def start_job(self, job_id: str) -> bool:
        """Start a batch analysis job using Celery tasks."""
        job = self.jobs.get(job_id)
        if not job:
            self.logger.error(f"Job {job_id} not found")
            return False
        
        if job.status != JobStatus.PENDING:
            self.logger.warning(f"Job {job_id} is not in pending state")
            return False
        
        try:
            # Get Celery app instance
            from ..factory import get_celery_app
            celery_app = get_celery_app()
            
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            
            # Update database
            self._update_job_in_db(job)
            
            # Submit Celery tasks
            for model in job.models:
                for app_num in job.app_range:
                    for analysis_type in job.analysis_types:
                        task_options = job.options.copy()
                        task_options['batch_job_id'] = job_id
                        
                        if analysis_type == AnalysisType.SECURITY_BACKEND:
                            celery_app.send_task(
                                'app.tasks.security_analysis_task',
                                args=[model, app_num],
                                kwargs={
                                    'tools': ['bandit', 'safety', 'pylint'],
                                    'options': task_options
                                }
                            )
                        elif analysis_type == AnalysisType.PERFORMANCE:
                            celery_app.send_task(
                                'app.tasks.performance_test_task',
                                args=[model, app_num],
                                kwargs={'test_config': task_options}
                            )
                        elif analysis_type == AnalysisType.CODE_QUALITY:
                            celery_app.send_task(
                                'app.tasks.static_analysis_task',
                                args=[model, app_num],
                                kwargs={
                                    'tools': ['pylint', 'flake8'],
                                    'options': task_options
                                }
                            )
                        elif analysis_type == AnalysisType.OPENROUTER:
                            celery_app.send_task(
                                'app.tasks.ai_analysis_task',
                                args=[model, app_num],
                                kwargs={
                                    'analysis_prompt': "Analyze this application for code quality and security",
                                    'options': task_options
                                }
                            )
            
            self.logger.info(f"Started batch job {job_id} with {job.total_tasks} tasks")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start batch job {job_id}: {e}")
            job.status = JobStatus.FAILED
            self._update_job_in_db(job)
            return False
    
    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a batch job by ID."""
        return self.jobs.get(job_id)
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status and progress."""
        job = self.jobs.get(job_id)
        if not job:
            return None
        
        return job.to_dict()
    
    def update_task_progress(self, job_id: str, task_completed: bool = False, 
                           task_failed: bool = False, result: Any = None):
        """Update progress for a task in a batch job."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        if task_completed:
            job.completed_tasks += 1
        elif task_failed:
            job.failed_tasks += 1
        
        # Store result if provided
        if result:
            if 'results' not in job.results:
                job.results['results'] = []
            job.results['results'].append(result)
        
        # Check if job is complete
        if job.completed_tasks + job.failed_tasks >= job.total_tasks:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            self.logger.info(f"Batch job {job_id} completed")
        
        # Update database
        self._update_job_in_db(job)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running batch job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        
        # Update database
        self._update_job_in_db(job)
        
        self.logger.info(f"Cancelled batch job {job_id}")
        return True
    
    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Dict[str, Any]]:
        """List all batch jobs, optionally filtered by status."""
        jobs = []
        for job in self.jobs.values():
            if status is None or job.status == status:
                jobs.append(job.to_dict())
        
        return sorted(jobs, key=lambda x: x['created_at'], reverse=True)
    
    def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            'total': len(self.jobs),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0
        }
        
        for job in self.jobs.values():
            status = job.status.value.lower()
            if status in stats:
                stats[status] += 1
        
        return stats
    
    def cleanup_old_jobs(self, max_age_hours: int = 24) -> int:
        """Clean up old completed jobs."""
        from datetime import timedelta
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        removed_count = 0
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                job.completed_at and job.completed_at < cutoff_time):
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            removed_count += 1
        
        self.logger.info(f"Cleaned up {removed_count} old batch jobs")
        return removed_count
    
    def _parse_app_range(self, app_range_str: str) -> List[int]:
        """Parse app range string into list of app numbers."""
        if app_range_str.strip().lower() == 'all':
            return list(range(1, 31))  # Apps 1-30
        
        apps = []
        for part in app_range_str.split(','):
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
    
    def _update_job_in_db(self, job: BatchJob):
        """Update job status in database."""
        try:
            with get_session() as session:
                batch_analysis = session.query(BatchAnalysis).filter_by(
                    batch_id=job.id
                ).first()
                
                if batch_analysis:
                    batch_analysis.status = job.status
                    batch_analysis.completed_tasks = job.completed_tasks
                    batch_analysis.failed_tasks = job.failed_tasks
                    batch_analysis.update_progress()
                    
                    if job.started_at:
                        batch_analysis.started_at = job.started_at
                    if job.completed_at:
                        batch_analysis.completed_at = job.completed_at
                    
                    session.commit()
        
        except Exception as e:
            self.logger.error(f"Failed to update job in database: {e}")
    
    def shutdown(self):
        """Shutdown the service gracefully."""
        self.shutdown_event.set()
        
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True)
        
        self.logger.info("Batch analysis service shut down")


# Global instance
batch_service = BatchAnalysisService()
