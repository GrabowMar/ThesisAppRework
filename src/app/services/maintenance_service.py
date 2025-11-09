"""
Maintenance Service
==================

Periodic background service that keeps the application healthy by:
- Cleaning up orphan database records (apps without filesystem directories)
- Removing orphan tasks (tasks targeting non-existent apps)
- Cleaning up stuck tasks (RUNNING/PENDING for too long)
- Deleting old completed/failed/cancelled tasks

Runs as a daemon thread on a configurable interval (default: 1 hour).
Executes once on startup, then periodically.
"""

import threading
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from app.utils.logging_config import get_logger
from app.extensions import db
from app.models import GeneratedApplication, AnalysisTask
from app.constants import AnalysisStatus

logger = get_logger("maintenance")


class MaintenanceService:
    """Background service for periodic maintenance tasks."""
    
    def __init__(
        self,
        interval_seconds: int = 3600,  # 1 hour default
        app=None,
        auto_start: bool = True
    ):
        """Initialize maintenance service.
        
        Args:
            interval_seconds: How often to run maintenance (default: 1 hour)
            app: Flask app instance (needed for app context)
            auto_start: Whether to start automatically on init
        """
        self.interval = interval_seconds
        self._app = app
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._thread_logger: Optional[logging.Logger] = None
        
        # Configuration
        self.config = {
            'cleanup_orphan_apps': True,
            'cleanup_orphan_tasks': True,
            'cleanup_stuck_tasks': True,
            'cleanup_old_tasks': True,
            'task_retention_days': 30,
            'stuck_task_timeout_minutes': 60,
        }
        
        # Statistics tracking
        self.stats = {
            'runs': 0,
            'last_run': None,
            'orphan_apps_cleaned': 0,
            'orphan_tasks_cleaned': 0,
            'stuck_tasks_cleaned': 0,
            'old_tasks_cleaned': 0,
            'errors': 0,
        }
        
        if auto_start:
            self.start()
    
    def start(self):
        """Start the maintenance service daemon thread."""
        if self._running:
            logger.info("Maintenance service already running")
            return
        
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name='maintenance_service'
        )
        self._thread.start()
        logger.info(
            "Maintenance service started (interval=%d seconds = %s)",
            self.interval,
            self._format_interval(self.interval)
        )
    
    def stop(self):
        """Stop the maintenance service."""
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        
        logger.info("Maintenance service stopped")
    
    def _run_loop(self):
        """Main loop - runs maintenance tasks periodically."""
        # Set up thread-specific logging
        self._thread_logger = self._setup_thread_logging()
        self._log("Maintenance service daemon thread started")
        
        # Run once immediately on startup
        try:
            with (self._app.app_context() if self._app else self._nullcontext()):
                self._log("Running initial maintenance on startup...")
                self._run_maintenance()
        except Exception as e:
            self._log(f"Error in initial maintenance run: {e}", level='error', exc_info=True)
            self.stats['errors'] += 1
        
        # Then run periodically
        while self._running:
            try:
                # Sleep until next run
                self._log(
                    f"Next maintenance run in {self._format_interval(self.interval)}",
                    level='debug'
                )
                
                # Sleep in chunks to allow clean shutdown
                sleep_remaining = self.interval
                while sleep_remaining > 0 and self._running:
                    sleep_chunk = min(10, sleep_remaining)
                    time.sleep(sleep_chunk)
                    sleep_remaining -= sleep_chunk
                
                # Run maintenance tasks
                if self._running:
                    with (self._app.app_context() if self._app else self._nullcontext()):
                        self._run_maintenance()
                    
            except Exception as e:
                self._log(
                    f"Error in maintenance loop: {e}",
                    level='error',
                    exc_info=True
                )
                self.stats['errors'] += 1
                # Sleep before retrying
                time.sleep(60)
    
    def _run_maintenance(self):
        """Execute all enabled maintenance tasks."""
        self._log("Starting maintenance run...")
        start_time = datetime.now(timezone.utc)
        
        results = {
            'orphan_apps': 0,
            'orphan_tasks': 0,
            'stuck_tasks': 0,
            'old_tasks': 0,
        }
        
        try:
            # 1. Clean up orphan app records
            if self.config['cleanup_orphan_apps']:
                results['orphan_apps'] = self._cleanup_orphan_apps()
            
            # 2. Clean up orphan tasks (tasks for non-existent apps)
            if self.config['cleanup_orphan_tasks']:
                results['orphan_tasks'] = self._cleanup_orphan_tasks()
            
            # 3. Clean up stuck tasks
            if self.config['cleanup_stuck_tasks']:
                results['stuck_tasks'] = self._cleanup_stuck_tasks()
            
            # 4. Clean up old completed/failed tasks
            if self.config['cleanup_old_tasks']:
                results['old_tasks'] = self._cleanup_old_tasks()
            
            # Update statistics
            self.stats['runs'] += 1
            self.stats['last_run'] = start_time
            self.stats['orphan_apps_cleaned'] += results['orphan_apps']
            self.stats['orphan_tasks_cleaned'] += results['orphan_tasks']
            self.stats['stuck_tasks_cleaned'] += results['stuck_tasks']
            self.stats['old_tasks_cleaned'] += results['old_tasks']
            
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            # Log summary
            if any(results.values()):
                self._log(
                    f"Maintenance completed in {duration:.1f}s: "
                    f"orphan_apps={results['orphan_apps']}, "
                    f"orphan_tasks={results['orphan_tasks']}, "
                    f"stuck_tasks={results['stuck_tasks']}, "
                    f"old_tasks={results['old_tasks']}"
                )
            else:
                self._log(f"Maintenance completed in {duration:.1f}s: no cleanup needed", level='debug')
            
        except Exception as e:
            self._log(f"Error during maintenance run: {e}", level='error', exc_info=True)
            self.stats['errors'] += 1
    
    def _cleanup_orphan_apps(self) -> int:
        """Remove database records for apps that don't exist on filesystem."""
        try:
            all_apps = GeneratedApplication.query.all()
            base_path = Path('generated/apps')
            
            orphans = []
            for app_record in all_apps:
                app_dir = base_path / app_record.model_slug / f'app{app_record.app_number}'
                if not app_dir.exists():
                    orphans.append(app_record)
            
            if orphans:
                self._log(
                    f"Found {len(orphans)} orphan app records (database records without filesystem directories)"
                )
                
                for orphan in orphans:
                    self._log(
                        f"  Deleting orphan app: {orphan.model_slug}/app{orphan.app_number}",
                        level='debug'
                    )
                    db.session.delete(orphan)
                
                db.session.commit()
                self._log(f"Cleaned up {len(orphans)} orphan app records")
            
            return len(orphans)
            
        except Exception as e:
            self._log(f"Error cleaning up orphan apps: {e}", level='error', exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0
    
    def _cleanup_orphan_tasks(self) -> int:
        """Remove tasks targeting non-existent apps."""
        try:
            # Get all pending/running tasks
            active_tasks = AnalysisTask.query.filter(
                AnalysisTask.status.in_([
                    AnalysisStatus.PENDING,
                    AnalysisStatus.RUNNING
                ])
            ).all()
            
            orphan_tasks = []
            for task in active_tasks:
                # Check if target app exists in database
                app_exists = GeneratedApplication.query.filter_by(
                    model_slug=task.target_model,
                    app_number=task.target_app_number
                ).first()
                
                if not app_exists:
                    orphan_tasks.append(task)
            
            if orphan_tasks:
                self._log(
                    f"Found {len(orphan_tasks)} orphan tasks (targeting non-existent apps)"
                )
                
                for task in orphan_tasks:
                    self._log(
                        f"  Cancelling orphan task: {task.task_id} "
                        f"(target: {task.target_model}/app{task.target_app_number})",
                        level='debug'
                    )
                    task.status = AnalysisStatus.CANCELLED
                    task.error_message = "Target app no longer exists - cancelled by maintenance service"
                    task.completed_at = datetime.now(timezone.utc)
                
                db.session.commit()
                self._log(f"Cancelled {len(orphan_tasks)} orphan tasks")
            
            return len(orphan_tasks)
            
        except Exception as e:
            self._log(f"Error cleaning up orphan tasks: {e}", level='error', exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0
    
    def _cleanup_stuck_tasks(self) -> int:
        """Clean up tasks stuck in RUNNING or old PENDING state."""
        try:
            timeout_minutes = self.config['stuck_task_timeout_minutes']
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
            
            # Find stuck RUNNING tasks
            stuck_running = AnalysisTask.query.filter(
                AnalysisTask.status == AnalysisStatus.RUNNING,
                AnalysisTask.started_at < cutoff
            ).all()
            
            # Find old PENDING tasks
            stuck_pending = AnalysisTask.query.filter(
                AnalysisTask.status == AnalysisStatus.PENDING,
                AnalysisTask.created_at < cutoff
            ).all()
            
            stuck_tasks = stuck_running + stuck_pending
            
            if stuck_tasks:
                self._log(
                    f"Found {len(stuck_tasks)} stuck tasks "
                    f"({len(stuck_running)} RUNNING, {len(stuck_pending)} PENDING) "
                    f"older than {timeout_minutes} minutes"
                )
                
                for task in stuck_running:
                    self._log(
                        f"  Marking stuck RUNNING task as FAILED: {task.task_id}",
                        level='debug'
                    )
                    task.status = AnalysisStatus.FAILED
                    task.error_message = f"Task stuck in RUNNING state for >{timeout_minutes}m - cleaned by maintenance"
                    task.completed_at = datetime.now(timezone.utc)
                
                for task in stuck_pending:
                    self._log(
                        f"  Marking stuck PENDING task as CANCELLED: {task.task_id}",
                        level='debug'
                    )
                    task.status = AnalysisStatus.CANCELLED
                    task.error_message = f"Task stuck in PENDING state for >{timeout_minutes}m - cleaned by maintenance"
                    task.completed_at = datetime.now(timezone.utc)
                
                db.session.commit()
                self._log(f"Cleaned up {len(stuck_tasks)} stuck tasks")
            
            return len(stuck_tasks)
            
        except Exception as e:
            self._log(f"Error cleaning up stuck tasks: {e}", level='error', exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0
    
    def _cleanup_old_tasks(self) -> int:
        """Delete old completed/failed/cancelled tasks."""
        try:
            retention_days = self.config['task_retention_days']
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            
            # Find old terminal tasks
            old_tasks = AnalysisTask.query.filter(
                AnalysisTask.status.in_([
                    AnalysisStatus.COMPLETED,
                    AnalysisStatus.FAILED,
                    AnalysisStatus.CANCELLED
                ]),
                AnalysisTask.completed_at < cutoff
            ).all()
            
            if old_tasks:
                self._log(
                    f"Found {len(old_tasks)} old tasks completed more than {retention_days} days ago"
                )
                
                for task in old_tasks:
                    self._log(
                        f"  Deleting old task: {task.task_id} "
                        f"(status: {task.status}, completed: {task.completed_at})",
                        level='debug'
                    )
                    db.session.delete(task)
                
                db.session.commit()
                self._log(f"Deleted {len(old_tasks)} old tasks")
            
            return len(old_tasks)
            
        except Exception as e:
            self._log(f"Error cleaning up old tasks: {e}", level='error', exc_info=True)
            try:
                db.session.rollback()
            except Exception:
                pass
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get maintenance service status and statistics."""
        return {
            'running': self._running,
            'interval_seconds': self.interval,
            'interval_human': self._format_interval(self.interval),
            'config': dict(self.config),
            'stats': dict(self.stats),
            'next_run': self._estimate_next_run(),
        }
    
    def _estimate_next_run(self) -> Optional[str]:
        """Estimate when the next maintenance run will occur."""
        if not self._running or not self.stats['last_run']:
            return None
        
        next_run = self.stats['last_run'] + timedelta(seconds=self.interval)
        return next_run.isoformat()
    
    def _format_interval(self, seconds: int) -> str:
        """Format interval in human-readable form."""
        if seconds < 60:
            return f"{seconds}s"
        elif seconds < 3600:
            return f"{seconds // 60}m"
        elif seconds < 86400:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}h{minutes}m" if minutes else f"{hours}h"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}d{hours}h" if hours else f"{days}d"
    
    def _setup_thread_logging(self) -> logging.Logger:
        """Set up logging for the maintenance thread."""
        thread_logger = logging.getLogger("ThesisApp.maintenance_thread")
        thread_logger.setLevel(logging.INFO)
        
        # Copy handlers from root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if handler not in thread_logger.handlers:
                thread_logger.addHandler(handler)
        
        thread_logger.propagate = False
        return thread_logger
    
    def _log(self, msg: str, level: str = 'info', exc_info: bool = False):
        """Thread-safe logging helper."""
        if self._thread_logger:
            log_method = getattr(self._thread_logger, level)
            log_method(msg, exc_info=exc_info)
            # Force flush
            for handler in self._thread_logger.handlers:
                try:
                    handler.flush()
                except Exception:
                    pass
        else:
            log_method = getattr(logger, level)
            log_method(msg, exc_info=exc_info)
    
    def _nullcontext(self):
        """Null context manager for when app context is not needed."""
        class _NullContext:
            def __enter__(self):
                return None
            def __exit__(self, *exc):
                return False
        return _NullContext()


# Global singleton
_maintenance_service: Optional[MaintenanceService] = None


def init_maintenance_service(
    interval_seconds: int = 3600,
    app=None,
    auto_start: bool = True
) -> MaintenanceService:
    """Initialize and start the maintenance service.
    
    Args:
        interval_seconds: How often to run maintenance (default: 1 hour)
        app: Flask app instance
        auto_start: Whether to start automatically
    
    Returns:
        MaintenanceService instance
    """
    global _maintenance_service
    
    if _maintenance_service is not None:
        return _maintenance_service
    
    from flask import current_app
    app_obj = app or (current_app._get_current_object() if current_app else None)
    
    # Use shorter interval in test mode
    if app_obj and app_obj.config.get('TESTING'):
        interval_seconds = min(interval_seconds, 60)  # Max 1 minute in tests
    
    _maintenance_service = MaintenanceService(
        interval_seconds=interval_seconds,
        app=app_obj,
        auto_start=auto_start
    )
    
    return _maintenance_service


def get_maintenance_service() -> Optional[MaintenanceService]:
    """Get the global maintenance service instance."""
    return _maintenance_service


__all__ = [
    'MaintenanceService',
    'init_maintenance_service',
    'get_maintenance_service',
]
