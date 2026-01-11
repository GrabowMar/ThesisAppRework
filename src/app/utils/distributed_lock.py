"""Distributed locking using Redis for concurrent access control.

This module provides Redis-based distributed locks to prevent race conditions
when multiple workers or processes access shared resources concurrently.

Key use cases:
- Database write operations (especially SQLite which has poor concurrency)
- Port allocation across multiple workers
- Container lifecycle operations
- Result file writes
"""

import time
import redis
from contextlib import contextmanager
from typing import Optional
import logging

from app.utils.redis_isolation import get_redis_db_number, get_isolation_aware_redis_url

logger = logging.getLogger(__name__)


class DistributedLock:
    """Redis-based distributed lock for cross-process synchronization.

    Uses Redis's built-in locking mechanism which is atomic and distributed.
    Supports timeouts and blocking/non-blocking acquisition.

    Example:
        >>> lock = DistributedLock(redis_client, "my_resource")
        >>> if lock.acquire(blocking=True):
        ...     try:
        ...         # Critical section
        ...         pass
        ...     finally:
        ...         lock.release()
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_name: str,
        timeout: float = 10.0,
        blocking_timeout: float = 5.0
    ):
        """Initialize distributed lock.

        Args:
            redis_client: Connected Redis client instance
            lock_name: Name of the lock (will be prefixed with 'lock:')
            timeout: How long to hold the lock before auto-release (seconds)
            blocking_timeout: How long to wait when acquiring in blocking mode (seconds)
        """
        self.redis_client = redis_client
        self.lock_name = f'lock:{lock_name}'
        self.timeout = timeout
        self.blocking_timeout = blocking_timeout
        self._lock: Optional[redis.lock.Lock] = None

    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the distributed lock.

        Args:
            blocking: If True, wait up to blocking_timeout for the lock.
                     If False, return immediately if lock is unavailable.

        Returns:
            bool: True if lock was acquired, False otherwise
        """
        try:
            self._lock = self.redis_client.lock(
                self.lock_name,
                timeout=self.timeout,
                blocking_timeout=self.blocking_timeout if blocking else 0
            )
            acquired = self._lock.acquire(blocking=blocking)
            if acquired:
                logger.debug(f"Acquired lock: {self.lock_name}")
            else:
                logger.debug(f"Failed to acquire lock: {self.lock_name}")
            return acquired
        except redis.exceptions.LockError as e:
            logger.warning(f"Lock error for {self.lock_name}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error acquiring lock {self.lock_name}: {e}")
            return False

    def release(self):
        """Release the distributed lock if held."""
        if self._lock:
            try:
                self._lock.release()
                logger.debug(f"Released lock: {self.lock_name}")
            except redis.exceptions.LockError:
                # Lock already released or expired
                logger.debug(f"Lock {self.lock_name} already released or expired")
            except Exception as e:
                logger.warning(f"Error releasing lock {self.lock_name}: {e}")
            finally:
                self._lock = None

    def __enter__(self):
        """Context manager entry - acquire lock."""
        self.acquire()
        return self

    def __exit__(self, exc_type, _exc_val, _exc_tb):
        """Context manager exit - release lock."""
        self.release()


def get_redis_client() -> Optional[redis.Redis]:
    """Get a Redis client for distributed locking.

    Returns:
        redis.Redis: Connected Redis client, or None if Redis unavailable

    This function creates a NEW Redis connection specifically for locking.
    It uses isolation-aware database selection for test isolation.
    """
    try:
        import os
        base_url = os.environ.get('REDIS_URL') or os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
        redis_url = get_isolation_aware_redis_url(base_url)

        client = redis.from_url(
            redis_url,
            socket_timeout=5.0,
            socket_connect_timeout=5.0,
            decode_responses=False  # Keep bytes for compatibility
        )
        # Test connection
        client.ping()
        return client
    except ImportError:
        logger.warning("redis-py not installed - distributed locking unavailable")
        return None
    except Exception as e:
        logger.warning(f"Could not connect to Redis for locking: {e}")
        return None


@contextmanager
def redis_lock(lock_name: str, timeout: float = 10.0, blocking_timeout: float = 5.0):
    """Context manager for Redis-based distributed locking.

    This is a convenience wrapper around DistributedLock for common use cases.

    Args:
        lock_name: Name of the resource to lock
        timeout: How long to hold the lock before auto-release (seconds)
        blocking_timeout: How long to wait for the lock (seconds)

    Example:
        >>> with redis_lock('port_allocation', timeout=30.0):
        ...     # Critical section - only one worker can be here at a time
        ...     allocate_ports()

    Yields:
        None (lock is held during context)

    Note:
        If Redis is unavailable, this will log a warning and proceed WITHOUT locking.
        This ensures the system degrades gracefully in tests without Redis.
    """
    redis_client = get_redis_client()

    if redis_client is None:
        # Redis unavailable - log warning and proceed without locking
        logger.warning(f"Redis unavailable - proceeding without lock for '{lock_name}' (UNSAFE for production!)")
        yield
        return

    lock = DistributedLock(redis_client, lock_name, timeout, blocking_timeout)
    try:
        acquired = lock.acquire(blocking=True)
        if not acquired:
            logger.warning(f"Could not acquire lock '{lock_name}' within {blocking_timeout}s - proceeding anyway (potential race condition)")
        yield
    finally:
        if lock._lock:
            lock.release()


@contextmanager
def database_write_lock(resource_id: str = "database"):
    """Specialized lock for database write operations.

    SQLite has poor concurrency support. Use this lock to serialize
    database writes across multiple Celery workers.

    Args:
        resource_id: Optional identifier for the specific resource (default: "database")

    Example:
        >>> with database_write_lock("task_status_update"):
        ...     task.status = 'completed'
        ...     db.session.commit()
    """
    with redis_lock(f'db_write:{resource_id}', timeout=30.0, blocking_timeout=10.0):
        yield
