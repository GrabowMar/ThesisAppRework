"""
Modern Task Management Service
=============================

Comprehensive task management system for analysis operations.
Handles individual tasks, batch operations, queuing, and progress tracking.
"""

from app.utils.logging_config import get_logger
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone, timedelta
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc
from celery import Task

from ..extensions import db
from ..models import (
    AnalysisTask, BatchAnalysis, AnalyzerConfiguration
)
from ..constants import AnalysisStatus, AnalysisType, JobPriority as Priority, JobStatus as BatchStatus
from .analyzer_service import analyzer_manager_service


logger = get_logger('task_service')


class TaskPriority(Enum):
    """Task priority levels with ordering."""
    LOW = (1, "low")
    NORMAL = (2, "normal") 
    HIGH = (3, "high")
    CRITICAL = (4, "critical")
    
    def __init__(self, order, label):
        self.order = order
        self.label = label


class AnalysisTaskService:
    """Service for managing individual analysis tasks."""
    
    @staticmethod
    def create_task(
        model_slug: str,
        app_number: int,
        analysis_type: str,
        config_id: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        batch_id: Optional[int] = None
    ) -> AnalysisTask:
        """Create a new analysis task."""
        
        # Validate the request
        is_valid, message, config = analyzer_manager_service.validate_analysis_request(
            analyzer_type=analysis_type,
            model_slug=model_slug,
            app_number=app_number,
            config_id=config_id
        )
        
        if not is_valid:
            raise ValueError(f"Invalid analysis request: {message}")
        
        # Prepare analysis configuration
        analysis_config = analyzer_manager_service.prepare_analysis_config(
            config=config,
            model_slug=model_slug,
            app_number=app_number,
            custom_options=custom_options
        )
        
        # Create task
        task = AnalysisTask(
            model_slug=model_slug,
            app_number=app_number,
            analysis_type=analysis_type,
            priority=priority,
            batch_id=batch_id
        )
        
        task.set_config(analysis_config)
        if custom_options:
            task.set_metadata({'custom_options': custom_options})
        
        # Estimate duration based on analysis type and configuration
        estimated_duration = AnalysisTaskService._estimate_task_duration(
            analysis_type, analysis_config
        )
        task.estimated_duration = estimated_duration
        
        db.session.add(task)
        db.session.commit()
        
        logger.info(f"Created analysis task {task.task_id}: {analysis_type} for {model_slug} app {app_number}")
        return task
    
    @staticmethod
    def _estimate_task_duration(analysis_type: str, config: Dict[str, Any]) -> int:
        """Estimate task duration in seconds based on type and configuration."""
        base_durations = {
            AnalysisType.SECURITY.value: 300,     # 5 minutes
            AnalysisType.PERFORMANCE.value: 180,  # 3 minutes
            AnalysisType.STATIC.value: 120,       # 2 minutes
            AnalysisType.DYNAMIC.value: 600,      # 10 minutes
            AnalysisType.AI_REVIEW.value: 240,    # 4 minutes
            AnalysisType.COMPREHENSIVE.value: 900 # 15 minutes
        }
        
        base_duration = base_durations.get(analysis_type, 300)
        
        # Adjust based on configuration
        execution_config = config.get('execution_config', {})
        if 'timeout' in execution_config:
            # Use configured timeout as upper bound
            timeout = execution_config['timeout']
            base_duration = min(base_duration, timeout * 0.8)  # 80% of timeout
        
        return int(base_duration)
    
    @staticmethod
    def get_task(task_id: str) -> Optional[AnalysisTask]:
        """Get task by ID."""
        return AnalysisTask.query.filter_by(task_id=task_id).first()
    
    @staticmethod
    def get_task_by_db_id(task_db_id: int) -> Optional[AnalysisTask]:
        """Get task by database ID."""
        return AnalysisTask.query.get(task_db_id)
    
    @staticmethod
    def list_tasks(
        status: Optional[str] = None,
        analysis_type: Optional[str] = None,
        model_slug: Optional[str] = None,
        batch_id: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = 'created_at',
        order_desc: bool = True
    ) -> List[AnalysisTask]:
        """List tasks with filtering and pagination."""
        query = AnalysisTask.query
        
        # Apply filters
        if status:
            query = query.filter_by(status=status)
        if analysis_type:
            query = query.filter_by(analysis_type=analysis_type)
        if model_slug:
            query = query.filter_by(model_slug=model_slug)
        if batch_id:
            query = query.filter_by(batch_id=batch_id)
        
        # Apply ordering
        if hasattr(AnalysisTask, order_by):
            order_col = getattr(AnalysisTask, order_by)
            if order_desc:
                query = query.order_by(desc(order_col))
            else:
                query = query.order_by(asc(order_col))
        
        # Apply pagination
        return query.offset(offset).limit(limit).all()
    
    @staticmethod
    def get_active_tasks() -> List[AnalysisTask]:
        """Get all currently active (running or queued) tasks."""
        return AnalysisTask.query.filter(
            AnalysisTask.status.in_([
                AnalysisStatus.QUEUED.value,
                AnalysisStatus.RUNNING.value
            ])
        ).order_by(AnalysisTask.created_at.desc()).all()
    
    @staticmethod
    def get_recent_tasks(limit: int = 20) -> List[AnalysisTask]:
        """Get recent tasks regardless of status."""
        return AnalysisTask.query.order_by(
            AnalysisTask.created_at.desc()
        ).limit(limit).all()
    
    @staticmethod
    def update_task_progress(
        task_id: str,
        percentage: float,
        message: Optional[str] = None
    ) -> Optional[AnalysisTask]:
        """Update task progress."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        task.update_progress(percentage, message)
        db.session.commit()
        
        logger.debug(f"Updated progress for task {task_id}: {percentage}%")
        return task
    
    @staticmethod
    def start_task(task_id: str) -> Optional[AnalysisTask]:
        """Mark task as started."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        task.mark_started()
        db.session.commit()
        
        logger.info(f"Started task {task_id}")
        return task
    
    @staticmethod
    def complete_task(
        task_id: str,
        results: Optional[Dict[str, Any]] = None
    ) -> Optional[AnalysisTask]:
        """Mark task as completed."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        task.mark_completed(results)
        db.session.commit()
        
        logger.info(f"Completed task {task_id}")
        return task
    
    @staticmethod
    def fail_task(
        task_id: str,
        error: Optional[str] = None
    ) -> Optional[AnalysisTask]:
        """Mark task as failed."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        task.mark_failed(error)
        db.session.commit()
        
        logger.warning(f"Failed task {task_id}: {error}")
        return task
    
    @staticmethod
    def cancel_task(task_id: str) -> Optional[AnalysisTask]:
        """Cancel a task."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        if task.is_complete:
            raise ValueError("Cannot cancel completed task")
        
        task.mark_cancelled()
        db.session.commit()
        
        logger.info(f"Cancelled task {task_id}")
        return task
    
    @staticmethod
    def delete_task(task_id: str) -> bool:
        """Delete a task (only if not part of batch)."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return False
        
        if task.batch_id:
            raise ValueError("Cannot delete task that is part of a batch")
        
        db.session.delete(task)
        db.session.commit()
        
        logger.info(f"Deleted task {task_id}")
        return True
    
    @staticmethod
    def get_task_statistics() -> Dict[str, Any]:
        """Get task statistics."""
        total_tasks = AnalysisTask.query.count()
        
        status_counts = {}
        for status in AnalysisStatus:
            count = AnalysisTask.query.filter_by(status=status.value).count()
            status_counts[status.value] = count
        
        type_counts = {}
        for analysis_type in AnalysisType:
            count = AnalysisTask.query.filter_by(analysis_type=analysis_type.value).count()
            type_counts[analysis_type.value] = count
        
        # Calculate average durations
        completed_tasks = AnalysisTask.query.filter_by(
            status=AnalysisStatus.COMPLETED.value
        ).filter(AnalysisTask.actual_duration.isnot(None)).all()
        
        avg_duration_by_type = {}
        for analysis_type in AnalysisType:
            type_tasks = [t for t in completed_tasks if t.analysis_type == analysis_type.value]
            if type_tasks:
                avg_duration = sum(t.actual_duration for t in type_tasks) / len(type_tasks)
                avg_duration_by_type[analysis_type.value] = round(avg_duration, 1)
        
        return {
            'total_tasks': total_tasks,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'average_duration_by_type': avg_duration_by_type,
            'active_tasks': len(AnalysisTaskService.get_active_tasks()),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }


class BatchAnalysisService:
    """Service for managing batch analysis operations."""
    
    @staticmethod
    def create_batch(
        name: str,
        description: str,
        analysis_types: List[str],
        target_models: List[str],
        target_apps: List[int],
        priority: str = Priority.NORMAL.value,
        config: Optional[Dict[str, Any]] = None
    ) -> BatchAnalysis:
        """Create a new batch analysis."""
        
        # Validate analysis types
        valid_types = [t.value for t in AnalysisType]
        invalid_types = [t for t in analysis_types if t not in valid_types]
        if invalid_types:
            raise ValueError(f"Invalid analysis types: {invalid_types}")
        
        # Create batch
        batch = BatchAnalysis(
            name=name,
            description=description,
            priority=priority
        )
        
        batch.set_analysis_types(analysis_types)
        batch.set_target_models(target_models)
        batch.set_target_apps(target_apps)
        
        if config:
            batch.set_config(config)
        
        # Calculate total tasks
        total_tasks = len(target_models) * len(target_apps) * len(analysis_types)
        batch.total_tasks = total_tasks
        
        db.session.add(batch)
        db.session.commit()
        
        logger.info(f"Created batch analysis {batch.batch_id}: {name} ({total_tasks} tasks)")
        return batch
    
    @staticmethod
    def generate_batch_tasks(batch_id: int) -> List[AnalysisTask]:
        """Generate all tasks for a batch."""
        batch = BatchAnalysis.query.get(batch_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_id}")
        
        if batch.status != BatchStatus.CREATED.value:
            raise ValueError(f"Batch is not in CREATED status: {batch.status}")
        
        tasks = []
        analysis_types = batch.get_analysis_types()
        target_models = batch.get_target_models()
        target_apps = batch.get_target_apps()
        batch_config = batch.get_config()
        
        for model_slug in target_models:
            for app_number in target_apps:
                for analysis_type in analysis_types:
                    try:
                        task = AnalysisTaskService.create_task(
                            model_slug=model_slug,
                            app_number=app_number,
                            analysis_type=analysis_type,
                            priority=batch.priority,
                            custom_options=batch_config.get('task_options'),
                            batch_id=batch.id
                        )
                        tasks.append(task)
                    except Exception as e:
                        logger.error(f"Failed to create task for {model_slug} app {app_number} {analysis_type}: {e}")
                        # Continue creating other tasks
        
        # Update batch with actual task count
        batch.total_tasks = len(tasks)
        db.session.commit()
        
        logger.info(f"Generated {len(tasks)} tasks for batch {batch.batch_id}")
        return tasks
    
    @staticmethod
    def get_batch(batch_id: str) -> Optional[BatchAnalysis]:
        """Get batch by ID."""
        return BatchAnalysis.query.filter_by(batch_id=batch_id).first()
    
    @staticmethod
    def get_batch_by_db_id(batch_db_id: int) -> Optional[BatchAnalysis]:
        """Get batch by database ID."""
        return BatchAnalysis.query.get(batch_db_id)
    
    @staticmethod
    def list_batches(
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[BatchAnalysis]:
        """List batches with filtering and pagination."""
        query = BatchAnalysis.query
        
        if status:
            query = query.filter_by(status=status)
        
        return query.order_by(
            BatchAnalysis.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    @staticmethod
    def start_batch(batch_id: str) -> Optional[BatchAnalysis]:
        """Start a batch analysis."""
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        
        if batch.status != BatchStatus.CREATED.value:
            raise ValueError(f"Batch cannot be started from status: {batch.status}")
        
        # Generate tasks if not already done
        if len(batch.tasks) == 0:
            BatchAnalysisService.generate_batch_tasks(batch.id)
        
        batch.mark_started()
        db.session.commit()
        
        logger.info(f"Started batch {batch_id} with {len(batch.tasks)} tasks")
        return batch
    
    @staticmethod
    def update_batch_progress(batch_id: str) -> Optional[BatchAnalysis]:
        """Update batch progress based on task status."""
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        
        batch.update_task_counts()
        
        # Check if batch is complete
        if batch.progress_percentage >= 100:
            if batch.failed_tasks > 0 and not batch.get_config().get('continue_on_failure', True):
                batch.mark_failed("Some tasks failed")
            else:
                batch.mark_completed()
        
        db.session.commit()
        return batch
    
    @staticmethod
    def cancel_batch(batch_id: str) -> Optional[BatchAnalysis]:
        """Cancel a batch and all its tasks."""
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        
        if batch.is_complete:
            raise ValueError("Cannot cancel completed batch")
        
        # Cancel all non-completed tasks
        for task in batch.tasks:
            if not task.is_complete:
                task.mark_cancelled()
        
        batch.mark_cancelled()
        db.session.commit()
        
        logger.info(f"Cancelled batch {batch_id}")
        return batch
    
    @staticmethod
    def delete_batch(batch_id: str) -> bool:
        """Delete a batch and all its tasks."""
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return False
        
        if batch.is_running:
            raise ValueError("Cannot delete running batch")
        
        db.session.delete(batch)
        db.session.commit()
        
        logger.info(f"Deleted batch {batch_id}")
        return True
    
    @staticmethod
    def get_batch_statistics() -> Dict[str, Any]:
        """Get batch statistics."""
        total_batches = BatchAnalysis.query.count()
        
        status_counts = {}
        for status in BatchStatus:
            count = BatchAnalysis.query.filter_by(status=status.value).count()
            status_counts[status.value] = count
        
        active_batches = BatchAnalysis.query.filter(
            BatchAnalysis.status.in_([
                BatchStatus.QUEUED.value,
                BatchStatus.RUNNING.value
            ])
        ).count()
        
        return {
            'total_batches': total_batches,
            'status_counts': status_counts,
            'active_batches': active_batches,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }


class TaskQueueService:
    """Service for managing task queues and execution order."""
    
    def __init__(self):
        self.queue_config = {
            'max_concurrent_tasks': 5,
            'max_concurrent_per_type': 2,
            'priority_weights': {
                Priority.URGENT.value: 10,
                Priority.HIGH.value: 5,
                Priority.NORMAL.value: 1,
                Priority.LOW.value: 0.5
            }
        }
    
    def get_next_tasks(self, limit: int = None) -> List[AnalysisTask]:
        """Get next tasks to execute based on priority and availability."""
        if limit is None:
            limit = self.queue_config['max_concurrent_tasks']
        
        # Get currently running tasks
        running_tasks = AnalysisTaskService.get_active_tasks()
        running_count = len([t for t in running_tasks if t.status == AnalysisStatus.RUNNING.value])
        
        # Calculate available slots
        available_slots = max(0, self.queue_config['max_concurrent_tasks'] - running_count)
        available_slots = min(available_slots, limit)
        
        if available_slots == 0:
            return []
        
        # Get pending tasks ordered by priority
        pending_tasks = AnalysisTask.query.filter_by(
            status=AnalysisStatus.PENDING.value
        ).order_by(
            self._get_priority_order(),
            AnalysisTask.created_at.asc()
        ).limit(available_slots * 2).all()  # Get more than needed for filtering
        
        # Filter based on per-type concurrency limits
        running_by_type = {}
        for task in running_tasks:
            if task.status == AnalysisStatus.RUNNING.value:
                running_by_type[task.analysis_type] = running_by_type.get(task.analysis_type, 0) + 1
        
        selected_tasks = []
        selected_by_type = {}
        
        for task in pending_tasks:
            if len(selected_tasks) >= available_slots:
                break
            
            current_type_count = running_by_type.get(task.analysis_type, 0) + selected_by_type.get(task.analysis_type, 0)
            max_per_type = self.queue_config['max_concurrent_per_type']
            
            if current_type_count < max_per_type:
                selected_tasks.append(task)
                selected_by_type[task.analysis_type] = selected_by_type.get(task.analysis_type, 0) + 1
        
        return selected_tasks
    
    def _get_priority_order(self):
        """Get SQLAlchemy order expression for task priority."""
        # Map priority values to numeric order
        from sqlalchemy import case
        
        priority_order = case(
            (AnalysisTask.priority == Priority.URGENT.value, 4),
            (AnalysisTask.priority == Priority.HIGH.value, 3),
            (AnalysisTask.priority == Priority.NORMAL.value, 2),
            (AnalysisTask.priority == Priority.LOW.value, 1),
            else_=2  # Default to normal priority
        )
        
        return desc(priority_order)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        active_tasks = AnalysisTaskService.get_active_tasks()
        running_tasks = [t for t in active_tasks if t.status == AnalysisStatus.RUNNING.value]
        queued_tasks = [t for t in active_tasks if t.status == AnalysisStatus.QUEUED.value]
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING.value).all()
        
        # Group by type
        running_by_type = {}
        pending_by_type = {}
        
        for task in running_tasks:
            running_by_type[task.analysis_type] = running_by_type.get(task.analysis_type, 0) + 1
        
        for task in pending_tasks:
            pending_by_type[task.analysis_type] = pending_by_type.get(task.analysis_type, 0) + 1
        
        return {
            'total_running': len(running_tasks),
            'total_queued': len(queued_tasks),
            'total_pending': len(pending_tasks),
            'running_by_type': running_by_type,
            'pending_by_type': pending_by_type,
            'max_concurrent': self.queue_config['max_concurrent_tasks'],
            'max_per_type': self.queue_config['max_concurrent_per_type'],
            'available_slots': max(0, self.queue_config['max_concurrent_tasks'] - len(running_tasks)),
            'last_updated': datetime.now(timezone.utc).isoformat()
        }


# Initialize service instances
task_service = AnalysisTaskService()
batch_service = BatchAnalysisService()
queue_service = TaskQueueService()



