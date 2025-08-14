"""
Task Manager Service for AI Research Platform
============================================

Orchestrates analysis tasks using Celery and integrates with the analyzer infrastructure.
Provides high-level interface for managing analysis workflows.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Protocol, runtime_checkable
import logging

from celery.result import AsyncResult

# Import tasks
from app.tasks import (
    celery,
    security_analysis_task,
    performance_test_task,
    static_analysis_task,
    ai_analysis_task,
    dynamic_analysis_task,
    batch_analysis_task,
    container_management_task,
    health_check_analyzers,
)

@runtime_checkable
class SupportsDelay(Protocol):
    def delay(self, *args: Any, **kwargs: Any) -> AsyncResult: ...

logger = logging.getLogger(__name__)

class TaskStatus:
    """Task status constants."""
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    PROGRESS = 'PROGRESS'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'
    RETRY = 'RETRY'
    REVOKED = 'REVOKED'

class AnalysisType:
    """Analysis type constants."""
    SECURITY = 'security'
    PERFORMANCE = 'performance'
    STATIC = 'static'
    AI = 'ai'
    BATCH = 'batch'
    DYNAMIC = 'dynamic'

class TaskManager:
    """
    Manages analysis tasks and coordinates with containerized analyzers.
    """
    
    def __init__(self):
        self.active_tasks = {}
        self.task_history = {}
        
    def start_security_analysis(self, model_slug: str, app_number: int, 
                               tools: Optional[List[str]] = None, 
                               options: Optional[Dict] = None) -> str:
        """
        Start a security analysis task.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Security tools to run
            options: Additional options
            
        Returns:
            Task ID
        """
        
        try:
            # Submit task to Celery
            task: SupportsDelay = security_analysis_task  # type: ignore[assignment]
            result = task.delay(
                model_slug=model_slug,
                app_number=app_number,
                tools=tools,
                options=options or {}
            )
            
            task_id = str(result.id)
            
            # Track task
            self.active_tasks[task_id] = {
                'type': AnalysisType.SECURITY,
                'model_slug': model_slug,
                'app_number': app_number,
                'tools': tools,
                'options': options,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }
            
            logger.info(f"Started security analysis task {task_id} for {model_slug} app {app_number}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start security analysis: {e}")
            raise
    
    def start_performance_test(self, model_slug: str, app_number: int,
                              test_config: Optional[Dict] = None) -> str:
        """
        Start a performance testing task.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            test_config: Performance test configuration
            
        Returns:
            Task ID
        """
        
        try:
            task: SupportsDelay = performance_test_task  # type: ignore[assignment]
            result = task.delay(
                model_slug=model_slug,
                app_number=app_number,
                test_config=test_config or {}
            )
            
            task_id = str(result.id)
            
            self.active_tasks[task_id] = {
                'type': AnalysisType.PERFORMANCE,
                'model_slug': model_slug,
                'app_number': app_number,
                'test_config': test_config,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }
            
            logger.info(f"Started performance test task {task_id} for {model_slug} app {app_number}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start performance test: {e}")
            raise
    
    def start_static_analysis(self, model_slug: str, app_number: int,
                             tools: Optional[List[str]] = None,
                             options: Optional[Dict] = None) -> str:
        """
        Start a static analysis task.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            tools: Static analysis tools to run
            options: Additional options
            
        Returns:
            Task ID
        """
        
        try:
            task: SupportsDelay = static_analysis_task  # type: ignore[assignment]
            result = task.delay(
                model_slug=model_slug,
                app_number=app_number,
                tools=tools,
                options=options or {}
            )
            
            task_id = str(result.id)
            
            self.active_tasks[task_id] = {
                'type': AnalysisType.STATIC,
                'model_slug': model_slug,
                'app_number': app_number,
                'tools': tools,
                'options': options,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }
            
            logger.info(f"Started static analysis task {task_id} for {model_slug} app {app_number}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start static analysis: {e}")
            raise

    def start_dynamic_analysis(self, model_slug: str, app_number: int,
                               options: Optional[Dict] = None) -> str:
        """
        Start a dynamic (ZAP-like) security analysis task.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            options: Additional scan options (e.g., target_url, scan_type)
        
        Returns:
            Task ID
        """

        try:
            task: SupportsDelay = dynamic_analysis_task  # type: ignore[assignment]
            result = task.delay(
                model_slug=model_slug,
                app_number=app_number,
                options=options or {}
            )

            task_id = str(result.id)

            self.active_tasks[task_id] = {
                'type': AnalysisType.DYNAMIC,
                'model_slug': model_slug,
                'app_number': app_number,
                'options': options,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }

            logger.info(f"Started dynamic analysis task {task_id} for {model_slug} app {app_number}")

            return task_id

        except Exception as e:
            logger.error(f"Failed to start dynamic analysis: {e}")
            raise
    
    def start_ai_analysis(self, model_slug: str, app_number: int,
                         analysis_types: Optional[List[str]] = None,
                         options: Optional[Dict] = None) -> str:
        """
        Start an AI-powered analysis task.
        
        Args:
            model_slug: Model identifier
            app_number: Application number
            analysis_types: Types of AI analysis to perform
            options: Additional options
            
        Returns:
            Task ID
        """
        
        try:
            task: SupportsDelay = ai_analysis_task  # type: ignore[assignment]
            result = task.delay(
                model_slug=model_slug,
                app_number=app_number,
                analysis_types=analysis_types,
                options=options or {}
            )
            
            task_id = str(result.id)
            
            self.active_tasks[task_id] = {
                'type': AnalysisType.AI,
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_types': analysis_types,
                'options': options,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }
            
            logger.info(f"Started AI analysis task {task_id} for {model_slug} app {app_number}")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start AI analysis: {e}")
            raise
    
    def start_batch_analysis(self, models: List[str], apps: List[int],
                           analysis_types: List[str],
                           options: Optional[Dict] = None) -> str:
        """
        Start a batch analysis task.
        
        Args:
            models: List of model slugs
            apps: List of application numbers
            analysis_types: Types of analysis to perform
            options: Additional options
            
        Returns:
            Task ID
        """
        
        try:
            task: SupportsDelay = batch_analysis_task  # type: ignore[assignment]
            result = task.delay(
                models=models,
                apps=apps,
                analysis_types=analysis_types,
                options=options or {}
            )
            
            task_id = str(result.id)
            
            self.active_tasks[task_id] = {
                'type': AnalysisType.BATCH,
                'models': models,
                'apps': apps,
                'analysis_types': analysis_types,
                'options': options,
                'started_at': datetime.now(timezone.utc),
                'result': result
            }
            
            logger.info(f"Started batch analysis task {task_id} for {len(models)} models, {len(apps)} apps")
            
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to start batch analysis: {e}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            Task status information
        """
        
        try:
            # Get result from Celery
            result = AsyncResult(task_id, app=celery)
            
            # Get task info from our tracking
            task_info = self.active_tasks.get(task_id, {})
            
            status_info = {
                'task_id': task_id,
                'status': result.status,
                'progress': None,
                'result': None,
                'error': None,
                'started_at': task_info.get('started_at'),
                'completed_at': None,
                'type': task_info.get('type'),
                'metadata': task_info
            }
            
            if result.status == TaskStatus.PROGRESS:
                status_info['progress'] = result.info
            elif result.status == TaskStatus.SUCCESS:
                status_info['result'] = result.result
                status_info['completed_at'] = datetime.now(timezone.utc)
                # Move to history
                if task_id in self.active_tasks:
                    self.task_history[task_id] = self.active_tasks.pop(task_id)
                    self.task_history[task_id]['completed_at'] = status_info['completed_at']
            elif result.status == TaskStatus.FAILURE:
                status_info['error'] = str(result.info)
                status_info['completed_at'] = datetime.now(timezone.utc)
                # Move to history
                if task_id in self.active_tasks:
                    self.task_history[task_id] = self.active_tasks.pop(task_id)
                    self.task_history[task_id]['completed_at'] = status_info['completed_at']
                    self.task_history[task_id]['error'] = status_info['error']
            
            return status_info
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {e}")
            return {
                'task_id': task_id,
                'status': TaskStatus.FAILURE,
                'error': str(e)
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.
        
        Args:
            task_id: Task identifier
            
        Returns:
            True if successfully cancelled
        """
        
        try:
            result = AsyncResult(task_id, app=celery)
            result.revoke(terminate=True)
            
            # Remove from active tasks
            if task_id in self.active_tasks:
                self.task_history[task_id] = self.active_tasks.pop(task_id)
                self.task_history[task_id]['cancelled_at'] = datetime.now(timezone.utc)
            
            logger.info(f"Cancelled task {task_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {e}")
            return False
    
    def get_active_tasks(self) -> Dict[str, Dict[str, Any]]:
        """
        Get all active tasks.
        
        Returns:
            Dictionary of active tasks
        """
        
        active_tasks_status = {}
        
        for task_id in list(self.active_tasks.keys()):
            try:
                status = self.get_task_status(task_id)
                if status['status'] not in [TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED]:
                    active_tasks_status[task_id] = status
                else:
                    # Task completed, remove from active
                    if task_id in self.active_tasks:
                        self.task_history[task_id] = self.active_tasks.pop(task_id)
            except Exception as e:
                logger.error(f"Error getting status for task {task_id}: {e}")
        
        return active_tasks_status
    
    def get_task_history(self, limit: int = 100) -> Dict[str, Dict[str, Any]]:
        """
        Get task history.
        
        Args:
            limit: Maximum number of tasks to return
            
        Returns:
            Dictionary of historical tasks
        """
        
        # Sort by completion time, most recent first
        sorted_history = sorted(
            self.task_history.items(),
            key=lambda x: x[1].get('completed_at', datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True
        )
        
        return dict(sorted_history[:limit])
    
    def get_analyzer_health(self) -> Dict[str, Any]:
        """
        Get health status of analyzer services.
        
        Returns:
            Health status information
        """
        
        try:
            task: SupportsDelay = health_check_analyzers  # type: ignore[assignment]
            result = task.delay()
            health_info = result.get(timeout=30) or {}
            return health_info
            
        except Exception as e:
            logger.error(f"Failed to get analyzer health: {e}")
            return {
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def manage_containers(self, action: str, service: Optional[str] = None) -> Dict[str, Any]:
        """
        Manage analyzer containers.
        
        Args:
            action: Action to perform (start, stop, restart, status)
            service: Specific service name (optional)
            
        Returns:
            Operation result
        """
        
        try:
            task: SupportsDelay = container_management_task  # type: ignore[assignment]
            result = task.delay(action=action, service=service)
            operation_result = result.get(timeout=120) or {}
            return operation_result
            
        except Exception as e:
            logger.error(f"Failed to manage containers ({action}): {e}")
            return {
                'action': action,
                'service': service,
                'status': 'error',
                'message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics and monitoring data.
        
        Returns:
            System statistics
        """
        
        try:
            # Get active tasks count
            active_count = len(self.get_active_tasks())
            
            # Get completed tasks count (last 24 hours)
            from datetime import timedelta
            yesterday = datetime.now(timezone.utc) - timedelta(days=1)
            recent_completed = sum(
                1 for task in self.task_history.values()
                if task.get('completed_at') and task['completed_at'] > yesterday
            )
            
            # Get Celery worker stats
            inspect = celery.control.inspect()
            stats = inspect.stats() or {}
            active_queues = inspect.active_queues() or {}
            
            return {
                'active_tasks': active_count,
                'completed_today': recent_completed,
                'total_history': len(self.task_history),
                'celery_workers': len(stats),
                'worker_stats': stats,
                'active_queues': active_queues,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get system stats: {e}")
            return {
                'error': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        Clean up old task history.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of tasks cleaned up
        """
        
        try:
            from datetime import timedelta
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
            
            cleaned_count = 0
            tasks_to_remove = []
            
            for task_id, task_info in self.task_history.items():
                completed_at = task_info.get('completed_at')
                if completed_at and completed_at < cutoff_date:
                    tasks_to_remove.append(task_id)
            
            for task_id in tasks_to_remove:
                del self.task_history[task_id]
                cleaned_count += 1
            
            logger.info(f"Cleaned up {cleaned_count} old tasks")
            
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0

# Global task manager instance
_task_manager = None

def get_task_manager() -> TaskManager:
    """Get the global task manager instance."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
