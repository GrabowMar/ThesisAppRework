"""
Background Task Service
======================

Service for managing background tasks and real-time updates.
"""

from app.utils.logging_config import get_logger
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict

logger = get_logger('background_service')


@dataclass
class BackgroundTask:
    """Represents a background task."""
    task_id: str
    task_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: int = 0
    message: str = ""
    result: Optional[Any] = None
    error: Optional[str] = None


class BackgroundTaskService:
    """Service for managing background tasks.

    Deliberately lean: persistence, advanced scheduling, and websocket
    broadcasting are handled elsewhere. This service keeps only in-memory
    state for short-lived tasks used by UI progress components.
    """
    
    def __init__(self):
            # In-memory task registry and subscriber callbacks
            self.tasks: Dict[str, BackgroundTask] = {}
            self.subscribers: Dict[str, List[Callable[[Any], None]]] = {}
            self._lock = threading.Lock()
            self._running = False
            self._update_thread = None
        
    def start(self):
        """Start the background service."""
        if not self._running:
            self._running = True
            self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self._update_thread.start()
            logger.info("Background task service started")
    
    def stop(self):
        """Stop the background service."""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=5)
        logger.info("Background task service stopped")
    
    def create_task(self, task_id: str, task_type: str, message: str = "") -> BackgroundTask:
        """Create a new background task."""
        with self._lock:
            task = BackgroundTask(
                task_id=task_id,
                task_type=task_type,
                status="pending",
                created_at=datetime.now(timezone.utc),
                message=message
            )
            self.tasks[task_id] = task
            logger.info(f"Created background task: {task_id} ({task_type})")
            return task
    
    def start_task(self, task_id: str) -> bool:
        """Start a background task."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = "running"
                task.started_at = datetime.now(timezone.utc)
                task.message = "Task started"
                logger.info(f"Started background task: {task_id}")
                self._notify_subscribers(task_id)
                return True
            return False
    
    def update_task_progress(self, task_id: str, progress: int, message: str = "") -> bool:
        """Update task progress."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.progress = max(0, min(100, progress))
                if message:
                    task.message = message
                logger.debug(f"Updated task {task_id} progress: {progress}%")
                self._notify_subscribers(task_id)
                return True
            return False
    
    def complete_task(self, task_id: str, result: Any = None, message: str = "Task completed") -> bool:
        """Mark a task as completed."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = "completed"
                task.progress = 100
                task.completed_at = datetime.now(timezone.utc)
                task.result = result
                task.message = message
                logger.info(f"Completed background task: {task_id}")
                self._notify_subscribers(task_id)
                return True
            return False
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                task.status = "failed"
                task.completed_at = datetime.now(timezone.utc)
                task.error = error
                task.message = f"Task failed: {error}"
                logger.error(f"Failed background task {task_id}: {error}")
                self._notify_subscribers(task_id)
                return True
            return False
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """Get a task by ID."""
        with self._lock:
            return self.tasks.get(task_id)
    
    def get_tasks(self, task_type: Optional[str] = None, status: Optional[str] = None) -> List[BackgroundTask]:
        """Get tasks by type and/or status."""
        with self._lock:
            tasks = list(self.tasks.values())
            
            if task_type:
                tasks = [t for t in tasks if t.task_type == task_type]
            
            if status:
                tasks = [t for t in tasks if t.status == status]
            
            return sorted(tasks, key=lambda t: t.created_at, reverse=True)
    
    def get_active_tasks(self) -> List[BackgroundTask]:
        """Get all active (running or pending) tasks."""
        return [
            *self.get_tasks(status="running"),
            *self.get_tasks(status="pending"),
        ]

    def list_tasks_dict(self, task_type: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return tasks as list of dictionaries (already JSON-safe)."""
        return [self.to_dict(t) for t in self.get_tasks(task_type=task_type, status=status)]
    
    def subscribe(self, task_id: str, callback: Callable[[Any], None]) -> None:
        """Subscribe to task updates."""
        with self._lock:
            if task_id not in self.subscribers:
                self.subscribers[task_id] = []
            self.subscribers[task_id].append(callback)
    
    def unsubscribe(self, task_id: str, callback: Callable[[Any], None]) -> None:
        """Unsubscribe from task updates."""
        with self._lock:
            if task_id in self.subscribers:
                self.subscribers[task_id] = [cb for cb in self.subscribers[task_id] if cb != callback]
                if not self.subscribers[task_id]:
                    del self.subscribers[task_id]
    
    def _notify_subscribers(self, task_id: str) -> None:
        """Notify subscribers of task updates."""
        if task_id in self.subscribers:
            task = self.tasks[task_id]
            for callback in self.subscribers[task_id]:
                try:
                    callback(task)
                except Exception as e:
                    logger.error(f"Error notifying subscriber: {e}")
    
    def _update_loop(self) -> None:
        """Background update loop."""
        while self._running:
            try:
                # Clean up old completed tasks (older than 1 hour)
                cutoff_time = datetime.now(timezone.utc).timestamp() - 3600
                with self._lock:
                    tasks_to_remove = [
                        task_id for task_id, task in self.tasks.items()
                        if task.status in ["completed", "failed"] and 
                        task.completed_at and 
                        task.completed_at.timestamp() < cutoff_time
                    ]
                    
                    for task_id in tasks_to_remove:
                        del self.tasks[task_id]
                        if task_id in self.subscribers:
                            del self.subscribers[task_id]
                
                if tasks_to_remove:
                    logger.info(f"Cleaned up {len(tasks_to_remove)} old tasks")
                
                time.sleep(30)  # Clean up every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in background update loop: {e}")
                time.sleep(10)
    
    def to_dict(self, task: BackgroundTask) -> Dict[str, Any]:
        """Convert task to dictionary for JSON serialization."""
        data = asdict(task)
        # Convert datetime objects to ISO format strings
        for field in ['created_at', 'started_at', 'completed_at']:
            if data[field]:
                data[field] = data[field].isoformat()
        return data
    
    def get_task_summary(self) -> Dict[str, Any]:
        """Get summary of all tasks."""
        with self._lock:
            tasks = list(self.tasks.values())
            
            summary = {
                'total': len(tasks),
                'pending': len([t for t in tasks if t.status == "pending"]),
                'running': len([t for t in tasks if t.status == "running"]),
                'completed': len([t for t in tasks if t.status == "completed"]),
                'failed': len([t for t in tasks if t.status == "failed"]),
                'recent': [self.to_dict(t) for t in sorted(tasks, key=lambda x: x.created_at, reverse=True)[:5]]
            }
            
            return summary


# Global service instance
background_service = BackgroundTaskService()


def get_background_service() -> BackgroundTaskService:
    """Get the global background service instance."""
    return background_service


def init_background_service():
    """Initialize and start the background service."""
    background_service.start()
    return background_service


def shutdown_background_service():
    """Shutdown the background service."""
    background_service.stop()

__all__ = [
    'BackgroundTask', 'BackgroundTaskService', 'background_service',
    'get_background_service', 'init_background_service', 'shutdown_background_service'
]
