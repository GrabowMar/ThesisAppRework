"""
Container Action Service
========================

Service for managing container operations (build, start, stop, restart) with:
- Async execution with real-time progress tracking
- Concurrent action limits (one active action per app)
- Docker build output parsing for progress estimation
- WebSocket event emission for real-time UI updates
- Action history with 30-day retention
"""
from __future__ import annotations

import logging
import re
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..extensions import db
from ..models.container_action import ContainerAction, ContainerActionType, ContainerActionStatus
from ..realtime.task_events import emit_task_event
from ..utils.time import utc_now

logger = logging.getLogger('svc.container_action')


class ContainerActionService:
    """Service for executing and tracking container actions."""
    
    # Thread pool for async execution
    _executor: Optional[ThreadPoolExecutor] = None
    _executor_lock = threading.Lock()
    
    # Track active actions per app to enforce concurrency limits
    _active_actions: Dict[str, str] = {}  # key: "model:app_num", value: action_id
    _active_lock = threading.Lock()
    
    # Retention period for completed actions (30 days)
    RETENTION_DAYS = 30
    
    def __init__(self, app=None):
        """Initialize service with optional Flask app context."""
        self.app = app
        self._ensure_executor()
        # Clean up stuck actions on startup
        if app:
            self._cleanup_stuck_actions(app)
    
    def _cleanup_stuck_actions(self, app) -> None:
        """Clean up actions stuck in RUNNING or PENDING state from previous crashes."""
        try:
            with app.app_context():
                # Find actions that are stuck (RUNNING or PENDING for too long)
                stuck_threshold = utc_now() - timedelta(minutes=30)
                
                stuck_actions = ContainerAction.query.filter(
                    ContainerAction.status.in_([ContainerActionStatus.RUNNING, ContainerActionStatus.PENDING]),
                    ContainerAction.created_at < stuck_threshold
                ).all()
                
                for action in stuck_actions:
                    logger.warning(f"Cleaning up stuck action {action.action_id} (status: {action.status}, created: {action.created_at})")
                    action.status = ContainerActionStatus.FAILED
                    action.error_message = "Action was interrupted (server restart or timeout)"
                    action.completed_at = utc_now()
                
                if stuck_actions:
                    db.session.commit()
                    logger.info(f"Cleaned up {len(stuck_actions)} stuck container actions")
                    
                # Also clean up the in-memory active actions dict
                # Any action in DB that's RUNNING but was created before restart should be cleared
                with self._active_lock:
                    self._active_actions.clear()
                    
        except Exception as e:
            logger.error(f"Error cleaning up stuck actions: {e}")
    
    @classmethod
    def _ensure_executor(cls) -> ThreadPoolExecutor:
        """Ensure ThreadPoolExecutor is initialized."""
        with cls._executor_lock:
            if cls._executor is None:
                cls._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='container-action')
            return cls._executor
    
    @staticmethod
    def _app_key(model_slug: str, app_number: int) -> str:
        """Generate unique key for model/app pair."""
        return f"{model_slug}:{app_number}"
    
    def get_active_action(self, model_slug: str, app_number: int) -> Optional[ContainerAction]:
        """Get currently active action for an app, if any."""
        key = self._app_key(model_slug, app_number)
        with self._active_lock:
            action_id = self._active_actions.get(key)
        
        if action_id:
            return ContainerAction.query.filter_by(action_id=action_id).first()
        return None
    
    def has_active_action(self, model_slug: str, app_number: int) -> bool:
        """Check if there's an active action for the given app."""
        active = self.get_active_action(model_slug, app_number)
        return active is not None and active.is_active
    
    def create_action(
        self,
        action_type: ContainerActionType,
        model_slug: str,
        app_number: int,
        triggered_by: Optional[str] = None,
    ) -> Tuple[Optional[ContainerAction], Optional[str]]:
        """Create a new container action.
        
        Returns:
            Tuple of (ContainerAction, error_message). If error, action is None.
        """
        # Check for active action
        if self.has_active_action(model_slug, app_number):
            active = self.get_active_action(model_slug, app_number)
            return None, f"Action already in progress: {active.action_type.value} ({active.action_id})"
        
        # Generate unique action ID
        action_id = f"action_{uuid.uuid4().hex[:12]}"
        
        # Create action record
        action = ContainerAction(
            action_id=action_id,
            action_type=action_type,
            target_model=model_slug,
            target_app_number=app_number,
            status=ContainerActionStatus.PENDING,
            triggered_by=triggered_by,
            progress_percentage=0.0,
            current_step="Queued",
        )
        
        db.session.add(action)
        db.session.commit()
        
        # Register as active
        key = self._app_key(model_slug, app_number)
        with self._active_lock:
            self._active_actions[key] = action_id
        
        # Emit event
        emit_task_event("container.action_created", {
            "action_id": action_id,
            "action_type": action_type.value,
            "model_slug": model_slug,
            "app_number": app_number,
            "status": "pending",
        })
        
        logger.info(f"Created container action {action_id}: {action_type.value} for {model_slug}/app{app_number}")
        return action, None
    
    def execute_action_async(self, action_id: str) -> bool:
        """Submit action for async execution.
        
        Returns:
            True if submitted successfully, False if action not found or invalid state.
        """
        action = ContainerAction.query.filter_by(action_id=action_id).first()
        if not action:
            logger.error(f"Action {action_id} not found")
            return False
        
        if action.status != ContainerActionStatus.PENDING:
            logger.warning(f"Action {action_id} is not pending (status: {action.status})")
            return False
        
        executor = self._ensure_executor()
        executor.submit(self._execute_action_worker, action_id)
        return True
    
    def _execute_action_worker(self, action_id: str) -> None:
        """Worker function that executes the action in a background thread."""
        # Need Flask app context for database operations
        from flask import current_app
        try:
            app = current_app._get_current_object()
        except RuntimeError:
            # No app context, try to get from self.app or create new
            if self.app:
                app = self.app
            else:
                from app.factory import create_app
                app = create_app()
        
        with app.app_context():
            self._execute_action(action_id)
    
    def _execute_action(self, action_id: str) -> None:
        """Execute a container action (runs in background thread)."""
        action = ContainerAction.query.filter_by(action_id=action_id).first()
        if not action:
            logger.error(f"Action {action_id} not found in worker")
            return
        
        # Mark as running
        action.start_execution()
        action.current_step = "Initializing..."
        db.session.commit()
        
        emit_task_event("container.action_started", {
            "action_id": action_id,
            "action_type": action.action_type.value,
            "model_slug": action.target_model,
            "app_number": action.target_app_number,
        })
        
        try:
            # Get Docker manager
            from .service_locator import ServiceLocator
            docker_mgr = ServiceLocator.get_docker_manager()
            
            # Check if Docker manager is available
            if not docker_mgr:
                result = {'success': False, 'error': 'Docker manager not available. Is Docker running?'}
            # Execute based on action type
            elif action.action_type == ContainerActionType.BUILD:
                result = self._execute_build(action, docker_mgr)
            elif action.action_type == ContainerActionType.START:
                result = self._execute_start(action, docker_mgr)
            elif action.action_type == ContainerActionType.STOP:
                result = self._execute_stop(action, docker_mgr)
            elif action.action_type == ContainerActionType.RESTART:
                result = self._execute_restart(action, docker_mgr)
            else:
                result = {'success': False, 'error': f'Unknown action type: {action.action_type}'}
            
            # Update action with result
            action.stdout = result.get('stdout', '')
            action.stderr = result.get('stderr', '')
            action.exit_code = result.get('exit_code', result.get('returncode', -1))
            
            if result.get('success'):
                action.complete_execution(success=True, exit_code=action.exit_code)
                emit_task_event("container.action_completed", {
                    "action_id": action_id,
                    "action_type": action.action_type.value,
                    "model_slug": action.target_model,
                    "app_number": action.target_app_number,
                    "duration_seconds": action.duration_seconds,
                })
                
                # Update app's container_status on success
                self._update_app_container_status(
                    action.target_model, 
                    action.target_app_number,
                    'running' if action.action_type in (ContainerActionType.BUILD, ContainerActionType.START) else 'stopped'
                )
            else:
                action.complete_execution(
                    success=False,
                    exit_code=action.exit_code,
                    error_message=result.get('error', 'Unknown error')
                )
                emit_task_event("container.action_failed", {
                    "action_id": action_id,
                    "action_type": action.action_type.value,
                    "model_slug": action.target_model,
                    "app_number": action.target_app_number,
                    "error": result.get('error', 'Unknown error'),
                })
                
                # Update app's container_status to 'build_failed' on build failure
                if action.action_type == ContainerActionType.BUILD:
                    self._update_app_container_status(
                        action.target_model,
                        action.target_app_number,
                        'build_failed'
                    )
            
            db.session.commit()
            
            # Invalidate status cache
            self._invalidate_status_cache(action.target_model, action.target_app_number)
            
        except Exception as e:
            logger.exception(f"Error executing action {action_id}")
            action.complete_execution(success=False, exit_code=-1, error_message=str(e))
            db.session.commit()
            
            emit_task_event("container.action_failed", {
                "action_id": action_id,
                "action_type": action.action_type.value,
                "model_slug": action.target_model,
                "app_number": action.target_app_number,
                "error": str(e),
            })
        finally:
            # Remove from active actions
            key = self._app_key(action.target_model, action.target_app_number)
            with self._active_lock:
                if self._active_actions.get(key) == action_id:
                    del self._active_actions[key]
    
    def _update_app_container_status(self, model_slug: str, app_number: int, status: str) -> None:
        """Update the container_status field of a GeneratedApplication."""
        from app.models import GeneratedApplication
        try:
            app = GeneratedApplication.query.filter_by(
                model_slug=model_slug,
                app_number=app_number
            ).first()
            if app:
                app.container_status = status
                db.session.commit()
                logger.info(f"Updated container_status for {model_slug}/app{app_number} to '{status}'")
        except Exception as e:
            logger.error(f"Failed to update app container_status: {e}")
            # Don't fail the action if status update fails
    
    def _execute_build(self, action: ContainerAction, docker_mgr) -> Dict[str, Any]:
        """Execute build action with progress tracking."""
        action.current_step = "Building containers..."
        action.update_progress(5, "Starting Docker build")
        db.session.commit()
        self._emit_progress(action)
        
        # Use streaming build for progress updates
        result = self._streaming_compose_command(
            action=action,
            docker_mgr=docker_mgr,
            command=['build', '--no-cache'],
            timeout=600,
            progress_parser=self._parse_build_progress,
        )
        
        # If build succeeded, also start containers
        if result.get('success'):
            action.current_step = "Starting containers..."
            action.update_progress(90, "Starting containers")
            db.session.commit()
            self._emit_progress(action)
            
            start_result = docker_mgr.start_containers(action.target_model, action.target_app_number)
            if not start_result.get('success'):
                result['success'] = False
                result['error'] = f"Build succeeded but start failed: {start_result.get('error', 'Unknown')}"
        
        return result
    
    def _execute_start(self, action: ContainerAction, docker_mgr) -> Dict[str, Any]:
        """Execute start action."""
        action.current_step = "Starting containers..."
        action.update_progress(10, "Starting containers")
        db.session.commit()
        self._emit_progress(action)
        
        result = docker_mgr.start_containers(action.target_model, action.target_app_number)
        
        # Improve error message if compose file not found
        if not result.get('success'):
            error = result.get('error', '')
            if 'compose file not found' in error.lower() or 'not found' in error.lower():
                result['error'] = 'App not built. Click Build first.'
        
        action.update_progress(100 if result.get('success') else 50, 
                              "Containers started" if result.get('success') else result.get('error', 'Start failed'))
        db.session.commit()
        self._emit_progress(action)
        
        return result
    
    def _execute_stop(self, action: ContainerAction, docker_mgr) -> Dict[str, Any]:
        """Execute stop action."""
        action.current_step = "Stopping containers..."
        action.update_progress(10, "Stopping containers")
        db.session.commit()
        self._emit_progress(action)
        
        result = docker_mgr.stop_containers(action.target_model, action.target_app_number)
        
        # Improve error message if compose file not found
        if not result.get('success'):
            error = result.get('error', '')
            if 'compose file not found' in error.lower() or 'not found' in error.lower():
                result['error'] = 'App not built. Nothing to stop.'
        
        action.update_progress(100 if result.get('success') else 50,
                              "Containers stopped" if result.get('success') else result.get('error', 'Stop failed'))
        db.session.commit()
        self._emit_progress(action)
        
        return result
    
    def _execute_restart(self, action: ContainerAction, docker_mgr) -> Dict[str, Any]:
        """Execute restart action."""
        action.current_step = "Stopping containers..."
        action.update_progress(10, "Stopping containers")
        db.session.commit()
        self._emit_progress(action)
        
        result = docker_mgr.restart_containers(action.target_model, action.target_app_number)
        
        # Improve error message if compose file not found
        if not result.get('success'):
            error = result.get('error', '')
            if 'compose file not found' in error.lower() or 'not found' in error.lower():
                result['error'] = 'App not built. Click Build first.'
        
        action.update_progress(100 if result.get('success') else 50,
                              "Containers restarted" if result.get('success') else result.get('error', 'Restart failed'))
        db.session.commit()
        self._emit_progress(action)
        
        return result
    
    def _streaming_compose_command(
        self,
        action: ContainerAction,
        docker_mgr,
        command: List[str],
        timeout: int = 300,
        progress_parser: Optional[Callable[[str, ContainerAction], None]] = None,
    ) -> Dict[str, Any]:
        """Execute compose command with streaming output and progress parsing."""
        import shutil
        import os
        
        compose_path = docker_mgr._get_compose_path(action.target_model, action.target_app_number)
        project_name = docker_mgr._get_project_name(action.target_model, action.target_app_number)
        
        if not compose_path.exists():
            return {'success': False, 'error': f'Docker compose file not found: {compose_path}'}
        
        # Determine compose command
        docker_path = shutil.which('docker')
        if docker_path:
            base_cmd = ['docker', 'compose']
        else:
            docker_compose_path = shutil.which('docker-compose')
            if docker_compose_path:
                base_cmd = ['docker-compose']
            else:
                return {'success': False, 'error': 'Docker CLI not found in PATH'}
        
        cmd = base_cmd + ['-f', str(compose_path), '-p', project_name] + command
        
        env = os.environ.copy()
        env['PROJECT_NAME'] = project_name
        
        stdout_lines = []
        stderr_lines = []
        
        try:
            process = subprocess.Popen(
                cmd,
                cwd=compose_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                bufsize=1,
            )
            
            start_time = time.time()
            
            # Read output in real-time
            import select
            import sys
            
            # For Windows compatibility, use threads to read stdout/stderr
            if sys.platform == 'win32':
                stdout_data, stderr_data = self._read_process_output_windows(
                    process, action, progress_parser, timeout, start_time
                )
                stdout_lines = stdout_data.splitlines() if stdout_data else []
                stderr_lines = stderr_data.splitlines() if stderr_data else []
            else:
                # Unix: use select for non-blocking read
                while process.poll() is None:
                    if time.time() - start_time > timeout:
                        process.kill()
                        return {'success': False, 'error': f'Command timed out after {timeout}s'}
                    
                    # Read available output
                    readable, _, _ = select.select([process.stdout, process.stderr], [], [], 0.5)
                    for stream in readable:
                        line = stream.readline()
                        if line:
                            if stream == process.stdout:
                                stdout_lines.append(line)
                            else:
                                stderr_lines.append(line)
                            
                            action.append_output(line)
                            if progress_parser:
                                progress_parser(line, action)
                            db.session.commit()
                            self._emit_progress(action)
                
                # Read any remaining output
                remaining_stdout, remaining_stderr = process.communicate(timeout=5)
                if remaining_stdout:
                    stdout_lines.extend(remaining_stdout.splitlines(keepends=True))
                if remaining_stderr:
                    stderr_lines.extend(remaining_stderr.splitlines(keepends=True))
            
            exit_code = process.returncode
            success = exit_code == 0
            
            result = {
                'success': success,
                'exit_code': exit_code,
                'stdout': ''.join(stdout_lines),
                'stderr': ''.join(stderr_lines),
            }
            
            if not success:
                error_text = ''.join(stderr_lines).strip() or ''.join(stdout_lines).strip()
                if error_text:
                    lines = [l.strip() for l in error_text.splitlines() if l.strip()]
                    result['error'] = lines[-1] if lines else f'Exit code {exit_code}'
                else:
                    result['error'] = f'Command failed with exit code {exit_code}'
            
            return result
            
        except subprocess.TimeoutExpired:
            process.kill()
            return {'success': False, 'error': f'Command timed out after {timeout}s'}
        except Exception as e:
            logger.exception(f"Error in streaming compose command")
            return {'success': False, 'error': str(e)}
    
    def _read_process_output_windows(
        self,
        process: subprocess.Popen,
        action: ContainerAction,
        progress_parser: Optional[Callable],
        timeout: int,
        start_time: float,
    ) -> Tuple[str, str]:
        """Read process output on Windows using threads."""
        import queue
        
        stdout_queue: queue.Queue = queue.Queue()
        stderr_queue: queue.Queue = queue.Queue()
        
        def read_stream(stream, q):
            try:
                for line in iter(stream.readline, ''):
                    if line:
                        q.put(line)
                stream.close()
            except Exception:
                pass
        
        stdout_thread = threading.Thread(target=read_stream, args=(process.stdout, stdout_queue))
        stderr_thread = threading.Thread(target=read_stream, args=(process.stderr, stderr_queue))
        stdout_thread.daemon = True
        stderr_thread.daemon = True
        stdout_thread.start()
        stderr_thread.start()
        
        stdout_data = []
        stderr_data = []
        
        while process.poll() is None:
            if time.time() - start_time > timeout:
                process.kill()
                break
            
            # Drain queues
            try:
                while True:
                    line = stdout_queue.get_nowait()
                    stdout_data.append(line)
                    action.append_output(line)
                    if progress_parser:
                        progress_parser(line, action)
            except queue.Empty:
                pass
            
            try:
                while True:
                    line = stderr_queue.get_nowait()
                    stderr_data.append(line)
                    action.append_output(line)
                    if progress_parser:
                        progress_parser(line, action)
            except queue.Empty:
                pass
            
            db.session.commit()
            self._emit_progress(action)
            time.sleep(0.1)
        
        # Final drain
        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)
        
        try:
            while True:
                stdout_data.append(stdout_queue.get_nowait())
        except queue.Empty:
            pass
        
        try:
            while True:
                stderr_data.append(stderr_queue.get_nowait())
        except queue.Empty:
            pass
        
        return ''.join(stdout_data), ''.join(stderr_data)
    
    def _parse_build_progress(self, line: str, action: ContainerAction) -> None:
        """Parse Docker build output for progress updates."""
        line = line.strip()
        if not line:
            return
        
        # Docker BuildKit progress patterns
        # e.g., "#5 [backend 2/5] RUN pip install ..."
        buildkit_match = re.match(r'#\d+\s+\[(\w+)\s+(\d+)/(\d+)\]', line)
        if buildkit_match:
            service = buildkit_match.group(1)
            current = int(buildkit_match.group(2))
            total = int(buildkit_match.group(3))
            # Map to 5-90% range (leave room for startup)
            progress = 5 + (current / total) * 85
            action.update_progress(progress, f"Building {service}: step {current}/{total}")
            return
        
        # Legacy Docker build progress
        # e.g., "Step 2/10 : RUN npm install"
        legacy_match = re.match(r'Step\s+(\d+)/(\d+)\s*:', line)
        if legacy_match:
            current = int(legacy_match.group(1))
            total = int(legacy_match.group(2))
            progress = 5 + (current / total) * 85
            action.update_progress(progress, f"Build step {current}/{total}")
            return
        
        # Service building started
        if 'Building' in line:
            service_match = re.search(r'Building\s+(\w+)', line)
            if service_match:
                action.current_step = f"Building {service_match.group(1)}..."
            return
        
        # Image pull
        if 'Pulling' in line or 'Pull' in line:
            action.current_step = "Pulling base images..."
            return
    
    def _emit_progress(self, action: ContainerAction) -> None:
        """Emit progress event for action."""
        emit_task_event("container.progress", {
            "action_id": action.action_id,
            "action_type": action.action_type.value,
            "model_slug": action.target_model,
            "app_number": action.target_app_number,
            "progress": action.progress_percentage,
            "step": action.current_step,
            "status": action.status.value,
        })
    
    def _invalidate_status_cache(self, model_slug: str, app_number: int) -> None:
        """Invalidate Docker status cache for the app."""
        try:
            from .service_locator import ServiceLocator
            cache = ServiceLocator.get_docker_status_cache()
            if cache:
                cache.invalidate(model_slug, app_number)
        except Exception as e:
            logger.debug(f"Could not invalidate status cache: {e}")
    
    # --- Query methods ---
    
    def get_action(self, action_id: str) -> Optional[ContainerAction]:
        """Get action by ID."""
        return ContainerAction.query.filter_by(action_id=action_id).first()
    
    def get_action_history(
        self,
        model_slug: Optional[str] = None,
        app_number: Optional[int] = None,
        limit: int = 50,
        include_active: bool = True,
    ) -> List[ContainerAction]:
        """Get action history with optional filters."""
        query = ContainerAction.query
        
        if model_slug:
            query = query.filter_by(target_model=model_slug)
        if app_number is not None:
            query = query.filter_by(target_app_number=app_number)
        if not include_active:
            query = query.filter(ContainerAction.status.notin_([
                ContainerActionStatus.PENDING,
                ContainerActionStatus.RUNNING
            ]))
        
        return query.order_by(ContainerAction.created_at.desc()).limit(limit).all()
    
    def cancel_action(self, action_id: str, reason: str = "Cancelled by user") -> bool:
        """Cancel a pending or running action.
        
        Note: This marks the action as cancelled but doesn't kill running processes.
        """
        action = ContainerAction.query.filter_by(action_id=action_id).first()
        if not action:
            return False
        
        if not action.is_active:
            return False
        
        action.cancel(reason)
        db.session.commit()
        
        # Remove from active actions
        key = self._app_key(action.target_model, action.target_app_number)
        with self._active_lock:
            if self._active_actions.get(key) == action_id:
                del self._active_actions[key]
        
        emit_task_event("container.action_cancelled", {
            "action_id": action_id,
            "action_type": action.action_type.value,
            "model_slug": action.target_model,
            "app_number": action.target_app_number,
            "reason": reason,
        })
        
        return True
    
    def cleanup_old_actions(self) -> int:
        """Delete actions older than retention period.
        
        Returns number of deleted actions.
        """
        cutoff = utc_now() - timedelta(days=self.RETENTION_DAYS)
        
        old_actions = ContainerAction.query.filter(
            ContainerAction.created_at < cutoff,
            ContainerAction.status.notin_([
                ContainerActionStatus.PENDING,
                ContainerActionStatus.RUNNING
            ])
        ).all()
        
        count = len(old_actions)
        for action in old_actions:
            db.session.delete(action)
        
        if count:
            db.session.commit()
            logger.info(f"Cleaned up {count} old container actions")
        
        return count


# Module-level instance (lazy initialization)
_service_instance: Optional[ContainerActionService] = None
_service_lock = threading.Lock()


def get_container_action_service(app=None) -> ContainerActionService:
    """Get or create ContainerActionService instance."""
    global _service_instance
    with _service_lock:
        if _service_instance is None:
            _service_instance = ContainerActionService(app)
        return _service_instance
