"""
Modern Task Management Service
=============================

Comprehensive task management system for analysis operations.
Handles individual tasks, queuing, and progress tracking.
"""

from app.utils.logging_config import get_logger
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from sqlalchemy import desc, asc, delete
from ..extensions import db
from ..models import AnalysisTask, BatchAnalysis, AnalyzerConfiguration, AnalysisResult
from ..constants import AnalysisStatus, AnalysisType, JobPriority as Priority


logger = get_logger('task_service')


class AnalysisTaskService:
    """Service for managing individual analysis tasks (simplified)."""

    @staticmethod
    def create_task(
        model_slug: str,
        app_number: int,
        tools: List[str],  # Replaced analysis_type with tools
        config_id: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        batch_id: Optional[int] = None,
        task_name: Optional[str] = None,
        description: Optional[str] = None,
        dispatch: bool = True,
    ) -> AnalysisTask:
        """Create and persist an AnalysisTask based on a list of tools.

        Args:
            model_slug: Model identifier.
            app_number: Application number.
            tools: Canonical tool names to execute.
            config_id: Optional analyzer configuration id.
            priority: Task priority enum value.
            custom_options: Metadata stored with the task.
            batch_id: Optional batch identifier.
            task_name: Optional override for task name.
            description: Optional description.
            dispatch: When False, skip immediate Celery dispatch (caller handles).
            
        Raises:
            DuplicateTaskError: If a task for this model/app/batch already exists.
        """
        from sqlalchemy.exc import IntegrityError
        
        # Resolve batch_id string for duplicate checking
        batch_id_str = None
        if batch_id is not None:
            batch_obj = BatchAnalysis.query.get(batch_id)
            if batch_obj:
                batch_id_str = batch_obj.batch_id
        
        # Extract pipeline_id from custom_options if present (for pipeline-created tasks)
        options = dict(custom_options or {})
        pipeline_id = options.get('pipeline_id')
        if pipeline_id and not batch_id_str:
            batch_id_str = pipeline_id
        
        # PRE-CHECK: Query for existing task with same model/app/batch to fail fast
        # This is a defense-in-depth check before the unique constraint
        existing = AnalysisTask.query.filter_by(
            target_model=model_slug,
            target_app_number=app_number,
            batch_id=batch_id_str,
            is_main_task=True  # Only check main tasks, not subtasks
        ).first()
        
        if existing:
            logger.warning(
                "Duplicate task prevented (pre-check): %s app %s already has task %s in batch %s",
                model_slug, app_number, existing.task_id, batch_id_str
            )
            # Return existing task instead of creating duplicate
            return existing
        
        task_uuid = f"task_{uuid.uuid4().hex[:12]}"

        # Resolve analyzer configuration (less relevant now, but kept for structure)
        analyzer_config = None
        if config_id:
            try:
                analyzer_config = AnalyzerConfiguration.query.get(int(config_id))
            except Exception:
                analyzer_config = None
        if analyzer_config is None:
            analyzer_config = AnalyzerConfiguration.query.first()
        if analyzer_config is None:
            # Create a default config if none exists
            analyzer_config = AnalyzerConfiguration(
                name="AutoDefault-Universal",
                config_data="{}"
            )
            db.session.add(analyzer_config)
            db.session.flush()

        # Use a generic/custom analysis type as the old enum is deprecated
        at_enum = AnalysisType.CUSTOM
        pr_enum = next((pr for pr in Priority if pr.value == priority), None) or Priority.NORMAL

        task = AnalysisTask()
        task.task_id = task_uuid
        task.analyzer_config_id = analyzer_config.id
        task.status = AnalysisStatus.PENDING
        task.priority = pr_enum
        task.target_model = model_slug
        task.target_app_number = app_number
        task.task_name = task_name or f"custom:{model_slug}:{app_number}"
        task.description = description
        task.is_main_task = True  # Mark as main task so daemon will pick it up
        task.current_step = "Task created, waiting for execution..."  # Initial progress message
        
        # Store tools in metadata - use already-computed options dict
        options['tools'] = tools
        
        # Set batch_id from computed batch_id_str (for unique constraint)
        if batch_id_str:
            task.batch_id = batch_id_str
        elif batch_id is not None:
            batch_obj = BatchAnalysis.query.get(batch_id)
            if batch_obj:
                task.batch_id = batch_obj.batch_id
        
        try:
            task.set_metadata({'custom_options': options})
        except Exception:
            pass
        
        # Try to add task, handle IntegrityError from unique constraint (race condition)
        try:
            db.session.add(task)
            db.session.commit()
        except IntegrityError as e:
            db.session.rollback()
            # Race condition: another process created the task between our check and commit
            # Try to find and return the existing task
            existing = AnalysisTask.query.filter_by(
                target_model=model_slug,
                target_app_number=app_number,
                batch_id=batch_id_str,
                is_main_task=True
            ).first()
            if existing:
                logger.warning(
                    "Duplicate task prevented (constraint): %s app %s already has task %s (race condition)",
                    model_slug, app_number, existing.task_id
                )
                return existing
            # If we can't find the existing task, re-raise the error
            logger.error("IntegrityError but no existing task found: %s", e)
            raise
            
        logger.info(
            "Created analysis task %s for %s app %s with tools: %s",
            task.task_id,
            model_slug,
            app_number,
            tools,
        )
        
        # Note: TaskExecutionService background thread picks up pending tasks automatically
        # Manual dispatch via execute_task() method not needed (and doesn't exist)
        # Task will be executed when the background thread processes the queue
        if dispatch:
            logger.info("Task %s created and pending - will be picked up by TaskExecutionService background thread", task.task_id)
        
        # Realtime event (best-effort)
        try:
            from app.realtime.task_events import emit_task_event
            status_value = task.status.value if hasattr(task.status, 'value') else str(task.status)
            analysis_label = options.get('analysis_type') or (task.task_name or 'analysis')
            emit_task_event(
                "task.created",
                {
                    "id": task.id,
                    "task_id": task.task_id,
                    "analysis_type": analysis_label,
                    "status": status_value,
                    "priority": task.priority.value,
                    "target_model": task.target_model,
                    "target_app_number": task.target_app_number,
                    "progress_percentage": task.progress_percentage,
                    "created_at": task.created_at.isoformat(),
                },
            )
        except Exception:
            pass
        return task
    
    @staticmethod
    def create_main_task_with_subtasks(
        model_slug: str,
        app_number: int,
        tools: List[str],
        config_id: Optional[str] = None,
        priority: str = Priority.NORMAL.value,
        custom_options: Optional[Dict[str, Any]] = None,
        batch_id: Optional[int] = None,
        task_name: Optional[str] = None,
        description: Optional[str] = None
    ) -> AnalysisTask:
        """Create a main task with subtasks for each service in unified analysis.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: List of canonical tool names to execute
            config_id: Optional analyzer configuration ID
            priority: Task priority
            custom_options: Additional options
            batch_id: Optional batch ID
            task_name: Optional custom task name
            description: Optional task description
            
        Returns:
            Main AnalysisTask with subtasks created, or existing task if duplicate
        """
        # Group tools by their service container
        from app.engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        registry_tools = registry.get_all_tools()
        
        tools_by_service: Dict[str, List[str]] = {}
        for tool_name in tools:
            tool_obj = registry_tools.get(tool_name)
            if tool_obj and tool_obj.available:
                service = tool_obj.container.value if tool_obj.container else 'unknown'
                tools_by_service.setdefault(service, []).append(tool_name)
        base_options: Dict[str, Any] = dict(custom_options or {})
        base_options['tools_by_service'] = tools_by_service  # Now stores tool names
        base_options['unified_analysis'] = True
        base_options['selected_tool_names'] = tools

        # Create the main task without dispatching; subtasks handle execution.
        main_task = AnalysisTaskService.create_task(
            model_slug=model_slug,
            app_number=app_number,
            tools=tools,
            config_id=config_id,
            priority=priority,
            custom_options=base_options,
            batch_id=batch_id,
            task_name=task_name,
            description=description,
            dispatch=False,
        )
        
        # DUPLICATE HANDLING: If create_task returned an existing task (due to unique constraint),
        # return it as-is without creating subtasks. The existing task already has its subtasks.
        # This prevents race condition duplicates in pipelines.
        if main_task.status not in (AnalysisStatus.PENDING, AnalysisStatus.CREATED):
            # Task already exists and is beyond initial state - return it as-is
            logger.warning(
                "Returning existing task %s (status=%s) for %s app %s - duplicate prevented",
                main_task.task_id, main_task.status.value if main_task.status else 'unknown',
                model_slug, app_number
            )
            return main_task
        
        # Also check if this task already has subtasks (was returned from duplicate check)
        existing_subtasks = AnalysisTask.query.filter_by(parent_task_id=main_task.task_id).count()
        if existing_subtasks > 0:
            logger.warning(
                "Returning existing task %s with %d subtasks for %s app %s - duplicate prevented",
                main_task.task_id, existing_subtasks, model_slug, app_number
            )
            return main_task

        main_task.is_main_task = True
        main_task.total_steps = len(tools_by_service)
        main_task.completed_steps = 0
        # CRITICAL: Keep status as CREATED (not PENDING) until ALL subtasks are created
        # This prevents TaskExecutionService from picking up the task before subtasks exist
        main_task.status = AnalysisStatus.CREATED
        db.session.add(main_task)
        # DO NOT COMMIT HERE - wait until all subtasks are created for atomic transaction
        db.session.flush()  # Get the main_task.task_id without committing

        analyzer_config_id = main_task.analyzer_config_id
        pr_enum = main_task.priority

        for service_name, tool_names_for_service in tools_by_service.items():
            subtask_uuid = f"task_{uuid.uuid4().hex[:12]}"

            subtask = AnalysisTask()
            subtask.task_id = subtask_uuid
            subtask.parent_task_id = main_task.task_id
            subtask.is_main_task = False
            subtask.service_name = service_name
            subtask.analyzer_config_id = analyzer_config_id
            subtask.status = AnalysisStatus.PENDING
            subtask.priority = pr_enum
            subtask.target_model = model_slug
            subtask.target_app_number = app_number
            subtask.task_name = f"{service_name}:{model_slug}:{app_number}"
            subtask.description = description or f"Subtask for {service_name} service"
            subtask.progress_percentage = 0.0

            if batch_id is not None:
                batch_obj = BatchAnalysis.query.get(batch_id)
                if batch_obj:
                    subtask.batch_id = batch_obj.batch_id

            subtask_options: Dict[str, Any] = {
                'service_name': service_name,
                'tool_names': list(tool_names_for_service),  # Store tool names, not IDs
                'parent_task_id': main_task.task_id,
                'unified_analysis': True,
            }
            if custom_options:
                subtask_options.update(custom_options)

            try:
                subtask.set_metadata({'custom_options': subtask_options})
            except Exception:
                pass

            db.session.add(subtask)
            logger.info(
                "Created subtask %s for service %s under main task %s",
                subtask.task_id,
                service_name,
                main_task.task_id,
            )

        # NOW set main task to PENDING and commit ATOMICALLY with all subtasks
        # This ensures TaskExecutionService never sees a main task without its subtasks
        main_task.status = AnalysisStatus.PENDING
        db.session.commit()
        logger.info(
            "Created main task %s with %s subtasks (atomic commit)",
            main_task.task_id,
            len(tools_by_service),
        )

        # NOTE: Do NOT dispatch subtasks immediately - let the daemon TaskExecutionService pick up
        # the main task and execute it through _execute_unified_analysis, which will then submit
        # subtasks to the daemon's ThreadPoolExecutor (not a temporary one that dies immediately).
        # 
        # Previous behavior: Created TaskExecutionService here with separate ThreadPoolExecutor,
        # marked task as RUNNING, then exited - killing the executor before subtasks completed.
        # This prevented the daemon from ever picking up the task (it was stuck in RUNNING state).
        
        # Reload main task with fresh relationships for return value
        refreshed_main = AnalysisTaskService.get_task(main_task.task_id) or main_task
        logger.info(
            "Main task %s with %s subtasks created and queued for daemon execution",
            main_task.task_id,
            len(tools_by_service)
        )

        return refreshed_main
    
    @staticmethod
    def _estimate_task_duration(analysis_type: str, config: Dict[str, Any]) -> int:
        """Estimate task duration in seconds based on analysis type.

        Provides reasonable time estimates for different analysis types.
        Respects timeout configuration from analyzer config if provided.

        Args:
            analysis_type: Type of analysis to estimate
            config: Analyzer configuration with optional timeout settings

        Returns:
            Estimated duration in seconds (defaults to 300s if unknown)
        """
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
            # Note: AnalysisTask no longer has analysis_type column, using task_name instead
            # This query will return 0 for all types - consider removing or refactoring
            count = 0  # Placeholder - analysis_type field removed from model
            type_counts[analysis_type.value] = count
        
        # Calculate average durations
        completed_tasks = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.COMPLETED,  # type: ignore[arg-type]
            AnalysisTask.actual_duration != None  # noqa: E711  # type: ignore[arg-type]
        ).all()
        
        avg_duration_by_type = {}
        for analysis_type in AnalysisType:
            # Note: task.analysis_type now returns task_name (string), not enum
            # Compare string values instead of enum objects
            type_tasks = [t for t in completed_tasks if t.analysis_type == analysis_type.value]
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


class TaskQueueService:
    """Service for managing task queues and execution order."""
    
    def __init__(self):
        """Initialize the queue service with configuration from config manager."""
        try:
            from app.config.config_manager import get_config
            config = get_config()
            queue_cfg = config.get_queue_config()
            max_concurrent = queue_cfg['max_concurrent_tasks']
            max_per_type = queue_cfg['max_concurrent_per_type']
        except (RuntimeError, ImportError, AttributeError):
            # Fallback when not in app context or config not available
            max_concurrent = 5
            max_per_type = 3
        
        self.queue_config = {
            'max_concurrent_tasks': max_concurrent,
            'max_concurrent_per_type': max_per_type,
            'priority_weights': {
                Priority.URGENT.value: 10,
                Priority.HIGH.value: 5,
                Priority.NORMAL.value: 1,
                Priority.LOW.value: 0.5
            }
        }
        logger.info(
            "QueueService initialized: max_concurrent=%d, max_per_type=%d",
            max_concurrent, max_per_type
        )
    
    def get_next_tasks(self, limit: Optional[int] = None) -> List[AnalysisTask]:
        """Get next tasks to execute based on priority and availability."""
        logger.debug("[QUEUE] get_next_tasks called with limit=%s", limit)
        
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
        
        logger.debug(
            "[QUEUE] Concurrency check: running=%d, max_concurrent=%d, available_slots=%d",
            running_count, self.queue_config['max_concurrent_tasks'], available_slots
        )
        
        if available_slots == 0:
            logger.debug("[QUEUE] No available slots - returning empty list")
            return []
        
        # Get pending tasks ordered by priority
        # ONLY get main tasks (subtasks are handled by their parent task's executor)
        # Include tasks where is_main_task is None for backward compatibility
        pending_tasks = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.PENDING,  # type: ignore[arg-type]
            (AnalysisTask.is_main_task == True) | (AnalysisTask.is_main_task == None)  # type: ignore[arg-type]  # noqa: E711,E712
        ).order_by(
            self._get_priority_order(),
            AnalysisTask.created_at.asc()
        ).limit(available_slots * 2).all()  # Get more than needed for filtering
        
        logger.debug(
            "[QUEUE] Found %d PENDING main tasks in DB (is_main_task=True or NULL)",
            len(pending_tasks)
        )
        if pending_tasks:
            logger.debug(
                "[QUEUE] Pending task IDs: %s",
                [t.task_id for t in pending_tasks[:5]]  # Show first 5
            )
        
        # Filter based on per-type concurrency limits
        running_by_type = {}
        for task in running_tasks:
            if task.status == AnalysisStatus.RUNNING:
                running_by_type[task.analysis_type] = running_by_type.get(task.analysis_type, 0) + 1
        
        logger.debug(
            "[QUEUE] Running tasks by type: %s (max_per_type=%d)",
            running_by_type, self.queue_config['max_concurrent_per_type']
        )
        
        selected_tasks = []
        selected_by_type = {}
        filtered_count = 0
        
        for task in pending_tasks:
            if len(selected_tasks) >= available_slots:
                break
            
            current_type_count = running_by_type.get(task.analysis_type, 0) + selected_by_type.get(task.analysis_type, 0)
            max_per_type = self.queue_config['max_concurrent_per_type']
            
            if current_type_count < max_per_type:
                selected_tasks.append(task)
                selected_by_type[task.analysis_type] = selected_by_type.get(task.analysis_type, 0) + 1
            else:
                filtered_count += 1
                logger.debug(
                    "[QUEUE] Filtered task %s (type=%s) - per-type limit reached (%d/%d)",
                    task.task_id, task.analysis_type, current_type_count, max_per_type
                )
        
        if filtered_count > 0:
            logger.debug("[QUEUE] Filtered %d tasks due to per-type limits", filtered_count)
        
        logger.debug(
            "[QUEUE] Returning %d selected task(s): %s",
            len(selected_tasks),
            [t.task_id for t in selected_tasks]
        )
        
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
queue_service = TaskQueueService()



