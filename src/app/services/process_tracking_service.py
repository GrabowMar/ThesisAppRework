"""
Process tracking service to replace PID files with database storage.
"""
import os
import psutil
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.exc import SQLAlchemyError

from ..models import db, ProcessTracking
import logging
logger = logging.getLogger(__name__)


class ProcessTrackingService:
    """Service for managing process tracking in database instead of PID files."""

    @staticmethod
    def register_process(service_name: str, service_type: str = 'main',
                        process_id: Optional[int] = None, host: Optional[str] = None,
                        port: Optional[int] = None, command_line: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> Optional[ProcessTracking]:
        """
        Register a new process in the tracking database.

        Args:
            service_name: Name of the service (celery_beat, celery_worker, flask_app)
            service_type: Type of service (main, analyzer)
            process_id: PID of the process (defaults to current process)
            host: Host where process is running (defaults to hostname)
            port: Port the service is listening on
            command_line: Command line used to start the process
            metadata: Additional metadata about the process

        Returns:
            ProcessTracking record or None if failed
        """
        try:
            if process_id is None:
                process_id = os.getpid()

            if host is None:
                import socket
                host = socket.gethostname()

            # Check if process with same service name and type already exists
            existing = ProcessTracking.query.filter_by(
                service_name=service_name,
                service_type=service_type,
                status='running'
            ).first()

            if existing:
                # Update existing record
                existing.process_id = process_id
                existing.host = host
                existing.port = port
                existing.command_line = command_line
                existing.last_heartbeat_at = datetime.now(timezone.utc)
                if metadata:
                    existing.set_environment_info(metadata)

                db.session.commit()
                logger.info(f"Updated process tracking for {service_name}:{service_type} PID {process_id}")
                return existing
            else:
                # Create new record
                tracking = ProcessTracking()
                tracking.service_name = service_name
                tracking.service_type = service_type
                tracking.process_id = process_id
                tracking.host = host
                tracking.port = port
                tracking.command_line = command_line
                tracking.status = 'running'
                tracking.started_at = datetime.now(timezone.utc)

                if metadata:
                    tracking.set_environment_info(metadata)

                db.session.add(tracking)
                db.session.commit()

                logger.info(f"Registered process tracking for {service_name}:{service_type} PID {process_id}")
                return tracking

        except SQLAlchemyError as e:
            logger.error(f"Database error registering process {service_name}: {e}")
            db.session.rollback()
            return None
        except Exception as e:
            logger.error(f"Error registering process {service_name}: {e}")
            return None

    @staticmethod
    def get_process(service_name: str, service_type: str = 'main') -> Optional[ProcessTracking]:
        """
        Get process tracking record for a service.

        Args:
            service_name: Name of the service
            service_type: Type of service

        Returns:
            ProcessTracking record or None if not found
        """
        try:
            return ProcessTracking.query.filter_by(
                service_name=service_name,
                service_type=service_type,
                status='running'
            ).first()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting process {service_name}: {e}")
            return None

    @staticmethod
    def get_process_id(service_name: str, service_type: str = 'main') -> Optional[int]:
        """
        Get the PID for a service (equivalent to reading a PID file).

        Args:
            service_name: Name of the service
            service_type: Type of service

        Returns:
            Process ID or None if not found/not running
        """
        process = ProcessTrackingService.get_process(service_name, service_type)
        if process:
            # Verify the process is actually running
            if ProcessTrackingService.is_process_running(process.process_id):
                return process.process_id
            else:
                # Process is dead, mark as stopped
                ProcessTrackingService.mark_stopped(service_name, service_type)
        return None

    @staticmethod
    def is_process_running(pid: int) -> bool:
        """
        Check if a process with given PID is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        try:
            return psutil.pid_exists(pid)
        except Exception:
            return False

    @staticmethod
    def mark_stopped(service_name: str, service_type: str = 'main') -> bool:
        """
        Mark a process as stopped in the database.

        Args:
            service_name: Name of the service
            service_type: Type of service

        Returns:
            True if successfully marked as stopped
        """
        try:
            process = ProcessTracking.query.filter_by(
                service_name=service_name,
                service_type=service_type,
                status='running'
            ).first()

            if process:
                process.status = 'stopped'
                process.stopped_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"Marked process {service_name}:{service_type} as stopped")
                return True
            return False

        except SQLAlchemyError as e:
            logger.error(f"Database error marking process stopped {service_name}: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def update_heartbeat(service_name: str, service_type: str = 'main',
                        resource_usage: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update heartbeat for a process (equivalent to touching a PID file).

        Args:
            service_name: Name of the service
            service_type: Type of service
            resource_usage: Current resource usage stats

        Returns:
            True if heartbeat updated successfully
        """
        try:
            process = ProcessTracking.query.filter_by(
                service_name=service_name,
                service_type=service_type,
                status='running'
            ).first()

            if process:
                process.last_heartbeat_at = datetime.now(timezone.utc)
                if resource_usage:
                    process.set_resource_usage(resource_usage)

                db.session.commit()
                return True
            return False

        except SQLAlchemyError as e:
            logger.error(f"Database error updating heartbeat {service_name}: {e}")
            db.session.rollback()
            return False

    @staticmethod
    def get_all_processes() -> List[ProcessTracking]:
        """
        Get all tracked processes.

        Returns:
            List of ProcessTracking records
        """
        try:
            return ProcessTracking.query.all()
        except SQLAlchemyError as e:
            logger.error(f"Database error getting all processes: {e}")
            return []

    @staticmethod
    def cleanup_dead_processes() -> int:
        """
        Mark processes as stopped if their PIDs are no longer running.

        Returns:
            Number of processes cleaned up
        """
        cleaned = 0
        try:
            running_processes = ProcessTracking.query.filter_by(status='running').all()

            for process in running_processes:
                if not ProcessTrackingService.is_process_running(process.process_id):
                    process.status = 'stopped'
                    process.stopped_at = datetime.now(timezone.utc)
                    cleaned += 1

            if cleaned > 0:
                db.session.commit()
                logger.info(f"Cleaned up {cleaned} dead processes")

            return cleaned

        except SQLAlchemyError as e:
            logger.error(f"Database error cleaning up dead processes: {e}")
            db.session.rollback()
            return 0

    @staticmethod
    def get_service_status() -> Dict[str, Dict[str, Any]]:
        """
        Get status of all services (replacement for checking multiple PID files).

        Returns:
            Dictionary with service status information
        """
        status = {}
        try:
            processes = ProcessTrackingService.get_all_processes()

            for process in processes:
                service_key = f"{process.service_name}_{process.service_type}"

                is_running = (process.status == 'running' and
                            ProcessTrackingService.is_process_running(process.process_id))

                status[service_key] = {
                    'service_name': process.service_name,
                    'service_type': process.service_type,
                    'status': 'running' if is_running else 'stopped',
                    'pid': process.process_id if is_running else None,
                    'host': process.host,
                    'port': process.port,
                    'start_time': process.started_at,
                    'last_heartbeat': process.last_heartbeat,
                    'resource_usage': process.get_resource_usage()
                }

            return status

        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {}
