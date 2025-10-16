"""
Modern Task Management Service
=============================

Comprehensive task management system for analysis operations.
Handles individual tasks, batch operations, queuing, and progress tracking.
"""

from app.utils.logging_config import get_logger
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy import desc, asc, delete, text
from ..extensions import db
from ..models import AnalysisTask, BatchAnalysis, AnalyzerConfiguration, AnalysisResult
from ..constants import AnalysisStatus, AnalysisType, JobPriority as Priority, JobStatus as BatchStatus


logger = get_logger('task_service')


class AnalysisTaskService:
    """Service for managing individual analysis tasks (simplified)."""

    @staticmethod
    def create_task(
        model_slug: str,
        app_number: int,
        analysis_type: str,
        config_id: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        batch_id: Optional[int] = None,
        task_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> AnalysisTask:
        """Create and persist an AnalysisTask using actual model fields.

        Notes:
        - Maps legacy (model_slug/app_number) to target_model/target_app_number.
        - Stores enum instances directly (model uses Enum columns).
        - Accepts integer batch DB id; stores its batch_id string in task.batch_id.
        """
        task_uuid = f"task_{uuid.uuid4().hex[:12]}"

        # Resolve analyzer configuration
        analyzer_config = None
        if config_id:
            try:
                analyzer_config = AnalyzerConfiguration.query.get(int(config_id))  # type: ignore[arg-type]
            except Exception:
                analyzer_config = None
        if analyzer_config is None:
            analyzer_config = AnalyzerConfiguration.query.first()
        if analyzer_config is None:
            default_type = list(AnalysisType)[0]
            analyzer_config = AnalyzerConfiguration()
            analyzer_config.name = f"AutoDefault-{default_type.value}"
            analyzer_config.analyzer_type = default_type
            analyzer_config.config_data = "{}"
            db.session.add(analyzer_config)
            db.session.flush()

        at_enum = next((at for at in AnalysisType if at.value == analysis_type), None) or list(AnalysisType)[0]
        pr_enum = next((pr for pr in Priority if pr.value == priority), None) or Priority.NORMAL

        task = AnalysisTask()
        task.task_id = task_uuid
        task.analyzer_config_id = analyzer_config.id
        task.analysis_type = at_enum
        task.status = AnalysisStatus.PENDING
        task.priority = pr_enum
        task.target_model = model_slug
        task.target_app_number = app_number
        task.task_name = task_name or f"{at_enum.value}:{model_slug}:{app_number}"
        task.description = description
        if batch_id is not None:
            batch_obj = BatchAnalysis.query.get(batch_id)
            if batch_obj:
                task.batch_id = batch_obj.batch_id
        if custom_options:
            try:
                task.set_metadata({'custom_options': custom_options})
            except Exception:
                pass
        db.session.add(task)
        db.session.commit()
        logger.info(f"Created analysis task {task.task_id}: {at_enum.value} for {model_slug} app {app_number}")
        # Realtime event (best-effort)
        try:  # pragma: no cover - small wrapper
            from app.realtime.task_events import emit_task_event
            emit_task_event(
                "task.created",
                {
                    "id": task.id,
                    "task_id": task.task_id,
                    "analysis_type": task.analysis_type.value if task.analysis_type else None,
                    "status": task.status.value if task.status else None,
                    "priority": task.priority.value if task.priority else None,
                    "target_model": task.target_model,
                    "target_app_number": task.target_app_number,
                    "progress_percentage": task.progress_percentage,
                    "created_at": task.created_at.isoformat() if task.created_at else None,
                },
            )
        except Exception:
            pass
        return task

    @staticmethod
    def _estimate_task_duration(analysis_type: str, config: Dict[str, Any]) -> int:
        mapping = {
            'security_backend': 300,
            'security_frontend': 300,
            'security_combined': 420,
            'performance': 180,
            'zap_security': 480,
            'openrouter': 120,
            'code_quality': 150,
            'dependency_check': 200,
            'docker_scan': 210,
            'frontend_security': 300,
            'backend_security': 300
        }
        base = mapping.get(analysis_type, 300)
        timeout = (config or {}).get('execution_config', {}).get('timeout') if isinstance(config, dict) else None
        if isinstance(timeout, int) and timeout > 0:
            base = min(base, int(timeout * 0.8))
        return base
    
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
        """List tasks with filtering and pagination (accept legacy strings)."""
        query = AnalysisTask.query
        if status:
            status_enum = next((st for st in AnalysisStatus if st.value == status), None)
            query = query.filter_by(status=status_enum or status)
        if analysis_type:
            at_enum = next((at for at in AnalysisType if at.value == analysis_type), None)
            query = query.filter_by(analysis_type=at_enum or analysis_type)
        if model_slug:
            query = query.filter_by(target_model=model_slug)
        if batch_id:
            query = query.filter_by(batch_id=batch_id)
        if hasattr(AnalysisTask, order_by):
            order_col = getattr(AnalysisTask, order_by)
            query = query.order_by(desc(order_col) if order_desc else asc(order_col))
        return query.offset(offset).limit(limit).all()
    
    @staticmethod
    def get_active_tasks() -> List[AnalysisTask]:
        """Get active tasks (pending or running)."""
        return AnalysisTask.query.filter(
            AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])  # type: ignore[attr-defined]
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
        
        # Tolerant update for shim or ORM task
        if hasattr(task, 'update_progress'):
            try:
                task.update_progress(percentage, message)  # type: ignore[arg-type]
            except Exception:
                setattr(task, 'progress_percentage', percentage)
        else:
            setattr(task, 'progress_percentage', percentage)
        db.session.commit()
        
        logger.debug(f"Updated progress for task {task_id}: {percentage}%")
        return task
    
    @staticmethod
    def start_task(task_id: str) -> Optional[AnalysisTask]:
        """Mark task as started."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        if hasattr(task, 'start_execution'):
            task.start_execution()
        elif hasattr(task, 'mark_started'):
            task.mark_started()  # type: ignore[attr-defined]
        else:
            setattr(task, 'status', 'running')
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
        
        if hasattr(task, 'complete_execution'):
            task.complete_execution(success=True)
        elif hasattr(task, 'mark_completed'):
            task.mark_completed(results)  # type: ignore[attr-defined]
        else:
            setattr(task, 'status', 'completed')
            setattr(task, 'progress_percentage', 100.0)
        db.session.commit()
        
        # Auto-cache tool results in database for performance
        try:
            BatchAnalysisService._cache_tool_results_on_completion(task_id)
        except Exception as e:
            logger.warning(f"Failed to cache tool results for task {task_id}: {e}")
        
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
        
        if hasattr(task, 'complete_execution'):
            if error is not None:
                task.complete_execution(success=False, error_message=error)  # type: ignore[arg-type]
            else:
                task.complete_execution(success=False)
        elif hasattr(task, 'mark_failed'):
            task.mark_failed(error)  # type: ignore[attr-defined]
        else:
            setattr(task, 'status', 'failed')
        db.session.commit()
        
        logger.warning(f"Failed task {task_id}: {error}")
        return task
    
    @staticmethod
    def cancel_task(task_id: str) -> Optional[AnalysisTask]:
        """Cancel a task."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return None
        
        if getattr(task, 'is_complete', False):
            raise ValueError("Cannot cancel completed task")
        if hasattr(task, 'mark_cancelled'):
            task.mark_cancelled()  # type: ignore[attr-defined]
        else:
            setattr(task, 'status', 'cancelled')
        db.session.commit()
        
        logger.info(f"Cancelled task {task_id}")
        return task
    
    @staticmethod
    def delete_task(task_id: str, *, allow_batch: bool = False, commit: bool = True) -> bool:
        """Delete a task and related rows without loading full ORM graphs."""
        task = AnalysisTaskService.get_task(task_id)
        if not task:
            return False

        if task.batch_id and not allow_batch:
            raise ValueError("Cannot delete task that is part of a batch")

        # Remove dependent records first to avoid foreign key violations
        db.session.execute(delete(AnalysisResult).where(AnalysisResult.task_id == task_id))

        # Legacy tables (analysis_jobs, etc.) are best-effort cleanup; ignore errors from stale schemas
        try:
            db.session.execute(text("DELETE FROM analysis_jobs WHERE task_id = :task_id"), {"task_id": task_id})
        except Exception as exc:
            logger.debug("Skipping analysis_jobs cleanup for %s due to %s", task_id, exc)

        result = db.session.execute(delete(AnalysisTask).where(AnalysisTask.task_id == task_id))
        removed = result.rowcount > 0

        if removed:
            if commit:
                db.session.commit()
            logger.info(f"Deleted task {task_id}")
        elif commit:
            db.session.rollback()
        return removed
    
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
        completed_tasks = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
            AnalysisTask.actual_duration != None  # noqa: E711  # type: ignore[arg-type]
        ).all()
        
        avg_duration_by_type = {}
        for analysis_type in AnalysisType:
            type_tasks = [t for t in completed_tasks if t.analysis_type == analysis_type]
            if type_tasks:
                durations = [t.actual_duration for t in type_tasks if t.actual_duration]
                if durations:
                    avg_duration = sum(durations) / len(durations)
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
    """Service for managing batch analysis operations (adapted to current BatchAnalysis schema)."""
    
    @staticmethod
    def create_batch(
        name: str,  # kept for legacy signature (ignored)
        description: str,  # kept for legacy signature (ignored)
        analysis_types: List[str],
        target_models: List[str],
        target_apps: List[int],
        priority: str = Priority.NORMAL.value,  # kept for legacy signature (ignored)
        config: Optional[Dict[str, Any]] = None
    ) -> BatchAnalysis:
        """Create a new batch analysis using available BatchAnalysis columns."""
        valid_types = [t.value for t in AnalysisType]
        invalid = [t for t in analysis_types if t not in valid_types]
        if invalid:
            raise ValueError(f"Invalid analysis types: {invalid}")
        batch = BatchAnalysis()
        batch.batch_id = f"batch_{uuid.uuid4().hex[:10]}"
        batch.set_analysis_types(analysis_types)
        batch.set_model_filter(target_models)  # type: ignore[attr-defined]
        batch.set_app_filter(target_apps)  # type: ignore[attr-defined]
        if config:
            batch.set_config(config)  # type: ignore[attr-defined]
        batch.total_tasks = len(target_models) * len(target_apps) * len(analysis_types)
        db.session.add(batch)
        db.session.commit()
        logger.info(f"Created batch analysis {batch.batch_id} ({batch.total_tasks} tasks)")
        return batch
    
    @staticmethod
    def generate_batch_tasks(batch_db_id: int) -> List[AnalysisTask]:
        batch = BatchAnalysis.query.get(batch_db_id)
        if not batch:
            raise ValueError(f"Batch not found: {batch_db_id}")
        # Only allow generation if still pending
        if batch.status not in (BatchStatus.PENDING, BatchStatus.QUEUED):
            raise ValueError(f"Batch not in a generatable status: {batch.status}")
        analysis_types = batch.get_analysis_types()
        models = batch.get_model_filter()
        apps = batch.get_app_filter()
        cfg = batch.get_config()
        tasks: List[AnalysisTask] = []
        for m in models:
            for a in apps:
                for at in analysis_types:
                    try:
                        t = AnalysisTaskService.create_task(
                            model_slug=m,
                            app_number=a,
                            analysis_type=at,
                            custom_options=cfg.get('task_options') if cfg else None,
                            batch_id=batch.id
                        )
                        tasks.append(t)
                    except Exception as e:  # pragma: no cover
                        logger.error(f"Task gen failed for {m}:{a}:{at}: {e}")
        batch.total_tasks = len(tasks)
        db.session.commit()
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
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        if batch.status not in (BatchStatus.PENDING, BatchStatus.QUEUED):
            raise ValueError(f"Cannot start batch from status: {batch.status}")
        # Generate tasks if none exist yet
        existing = AnalysisTask.query.filter_by(batch_id=batch.batch_id).count()
        if existing == 0:
            BatchAnalysisService.generate_batch_tasks(batch.id)
        batch.status = BatchStatus.RUNNING
        batch.started_at = datetime.now(timezone.utc)
        db.session.commit()
        return batch
    
    @staticmethod
    def update_batch_progress(batch_id: str) -> Optional[BatchAnalysis]:
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        # Recalculate counts
        total = batch.total_tasks or 0
        completed = AnalysisTask.query.filter_by(batch_id=batch.batch_id, status=AnalysisStatus.COMPLETED).count()
        failed = AnalysisTask.query.filter_by(batch_id=batch.batch_id, status=AnalysisStatus.FAILED).count()
        batch.completed_tasks = completed
        batch.failed_tasks = failed
        if total > 0:
            batch.progress_percentage = (completed / total) * 100.0
        # Mark completion
        if total > 0 and completed + failed >= total and batch.status == BatchStatus.RUNNING:
            batch.status = BatchStatus.COMPLETED if failed == 0 else BatchStatus.FAILED
            batch.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return batch
    
    @staticmethod
    def cancel_batch(batch_id: str) -> Optional[BatchAnalysis]:
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return None
        if batch.status in (BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED):
            raise ValueError("Batch already finished")
        # Mark tasks as cancelled (best-effort)
        tasks = AnalysisTask.query.filter_by(batch_id=batch.batch_id).all()
        for t in tasks:
            if t.status not in (AnalysisStatus.COMPLETED, AnalysisStatus.FAILED, AnalysisStatus.CANCELLED):
                t.status = AnalysisStatus.CANCELLED
        batch.status = BatchStatus.CANCELLED
        batch.completed_at = datetime.now(timezone.utc)
        db.session.commit()
        return batch
    
    @staticmethod
    def delete_batch(batch_id: str) -> bool:
        """Delete a batch and all its tasks."""
        batch = BatchAnalysisService.get_batch(batch_id)
        if not batch:
            return False
        
        if batch.status in (BatchStatus.RUNNING, BatchStatus.QUEUED):
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
        
        from sqlalchemy import or_
        active_batches = BatchAnalysis.query.filter(
            or_(BatchAnalysis.status == BatchStatus.QUEUED, BatchAnalysis.status == BatchStatus.RUNNING)
        ).count()
        
        return {
            'total_batches': total_batches,
            'status_counts': status_counts,
            'active_batches': active_batches,
            'last_updated': datetime.now(timezone.utc).isoformat()
        }
    
    @staticmethod
    def _cache_tool_results_on_completion(task_id: str) -> None:
        """Cache tool results in database when a task completes."""
        try:
            from .simple_tool_results_service import SimpleToolResultsService
            from .results_api_service import ResultsAPIService
            
            # Get raw results from API
            api_service = ResultsAPIService()
            raw_results = api_service._fetch_raw_results(task_id)
            
            if raw_results:
                # Store in database
                tool_service = SimpleToolResultsService()
                success = tool_service.store_tool_results_from_json(task_id, raw_results)
                
                if success:
                    logger.info(f"Successfully cached tool results in database for task {task_id}")
                else:
                    logger.warning(f"Failed to cache tool results for task {task_id}")
            else:
                logger.info(f"No results found to cache for task {task_id}")
                
        except Exception as e:
            logger.error(f"Error caching tool results for task {task_id}: {e}")


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
    
    def get_next_tasks(self, limit: Optional[int] = None) -> List[AnalysisTask]:
        """Get next tasks to execute based on priority and availability."""
        if limit is None:
            limit = self.queue_config['max_concurrent_tasks']
        
        # Get currently running tasks
        running_tasks = AnalysisTaskService.get_active_tasks()
        running_count = len([t for t in running_tasks if t.status == AnalysisStatus.RUNNING])
        
        # Calculate available slots
        available_slots = max(0, self.queue_config['max_concurrent_tasks'] - running_count)
        # Ensure limit is within bounds
        limit_int = int(limit) if limit is not None else self.queue_config['max_concurrent_tasks']
        available_slots = min(available_slots, limit_int)
        
        if available_slots == 0:
            return []
        
        # Get pending tasks ordered by priority
        pending_tasks = AnalysisTask.query.filter_by(
            status=AnalysisStatus.PENDING
        ).order_by(
            self._get_priority_order(),
            AnalysisTask.created_at.asc()
        ).limit(available_slots * 2).all()  # Get more than needed for filtering
        
        # Filter based on per-type concurrency limits
        running_by_type = {}
        for task in running_tasks:
            if task.status == AnalysisStatus.RUNNING:
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
            (AnalysisTask.priority == Priority.URGENT, 4),
            (AnalysisTask.priority == Priority.HIGH, 3),
            (AnalysisTask.priority == Priority.NORMAL, 2),
            (AnalysisTask.priority == Priority.LOW, 1),
            else_=2  # Default to normal priority
        )
        
        return desc(priority_order)
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        active_tasks = AnalysisTaskService.get_active_tasks()
        running_tasks = [t for t in active_tasks if t.status == AnalysisStatus.RUNNING]
        queued_tasks: List[AnalysisTask] = []
        pending_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
        
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



