#!/usr/bin/env python3
"""
WebSocket Connection Pooling and Resource Management
===================================================

Provides connection pooling, semaphore-based concurrency control, and
task lifecycle management to prevent resource exhaustion.

Features:
- Connection pool with automatic cleanup
- Semaphore-based concurrent connection limiting
- Task tracking and cancellation support
- Circuit breaker for failing services
- Request deduplication for idempotency
"""

import asyncio
import logging
import time
import websockets
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Set, Tuple
from enum import Enum


logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, fast-fail mode
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """Circuit breaker for external service resilience."""
    failure_threshold: int = 5
    timeout_seconds: int = 60
    half_open_max_calls: int = 3

    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    success_count: int = 0

    def record_success(self):
        """Record successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                logger.info(f"Circuit breaker recovered, closing circuit")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self):
        """Record failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            logger.warning(f"Circuit breaker failed during half-open, reopening circuit")
            self.state = CircuitState.OPEN
            self.success_count = 0
        elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            logger.error(f"Circuit breaker threshold reached ({self.failure_count} failures), opening circuit")
            self.state = CircuitState.OPEN

    def can_attempt(self) -> bool:
        """Check if call should be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout_seconds:
                logger.info(f"Circuit breaker timeout elapsed, entering half-open state")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return True
        return False


@dataclass
class ManagedTask:
    """Tracked analysis task with cancellation support."""
    task_id: str
    model_slug: str
    app_number: int
    analysis_type: str
    future: asyncio.Future
    created_at: datetime = field(default_factory=datetime.utcnow)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    subprocess_tasks: list = field(default_factory=list)

    def cancel(self):
        """Cancel the task and all subprocess tasks."""
        self.cancel_event.set()
        for proc in self.subprocess_tasks:
            try:
                proc.kill()
            except Exception:
                pass
        if not self.future.done():
            self.future.cancel()


class ConnectionPool:
    """WebSocket connection pool with concurrency control."""

    def __init__(
        self,
        max_concurrent_connections: int = 50,
        connection_timeout: int = 10,
        idle_timeout: int = 300,
        enable_pooling: bool = True
    ):
        """
        Initialize connection pool.

        Args:
            max_concurrent_connections: Maximum concurrent WebSocket connections
            connection_timeout: Timeout for establishing connections (seconds)
            idle_timeout: How long to keep idle connections alive (seconds)
            enable_pooling: Whether to reuse connections (disabled for now due to protocol constraints)
        """
        self.max_concurrent = max_concurrent_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        self.enable_pooling = enable_pooling

        # Semaphore to limit concurrent connections
        self._semaphore = asyncio.Semaphore(max_concurrent_connections)

        # Connection pool: url -> (websocket, last_used_timestamp)
        # Note: Currently disabled due to WebSocket message protocol constraints
        # Each analysis requires a fresh connection due to service closing after response
        self._pool: Dict[str, Tuple[Any, float]] = {}

        # Active managed tasks for cancellation support
        self._active_tasks: Dict[str, ManagedTask] = {}

        # Request deduplication: (model, app, task_id) -> Future
        self._pending_requests: Dict[Tuple[str, int, str], asyncio.Future] = {}

        # Circuit breakers per service URL
        self._circuit_breakers: Dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)

        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False

        logger.info(
            f"ConnectionPool initialized: max_concurrent={max_concurrent_connections}, "
            f"pooling={'enabled' if enable_pooling else 'disabled'}"
        )

    async def start(self):
        """Start background cleanup task."""
        if not self._running:
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("ConnectionPool background cleanup started")

    async def stop(self):
        """Stop background cleanup and close all connections."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # Close all pooled connections
        for websocket, _ in self._pool.values():
            try:
                await websocket.close()
            except Exception:
                pass
        self._pool.clear()

        # Cancel all active tasks
        for task in self._active_tasks.values():
            task.cancel()

        logger.info("ConnectionPool stopped and cleaned up")

    async def _cleanup_loop(self):
        """Background task to clean up idle connections."""
        while self._running:
            try:
                await asyncio.sleep(60)  # Run every minute
                await self._cleanup_idle_connections()
                await self._cleanup_completed_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_idle_connections(self):
        """Remove idle connections from pool."""
        if not self.enable_pooling:
            return

        now = time.time()
        to_remove = []

        for url, (websocket, last_used) in self._pool.items():
            if now - last_used > self.idle_timeout:
                to_remove.append(url)
                try:
                    await websocket.close()
                except Exception:
                    pass

        for url in to_remove:
            del self._pool[url]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} idle connections")

    async def _cleanup_completed_tasks(self):
        """Remove completed tasks from tracking."""
        to_remove = []

        for task_id, managed_task in self._active_tasks.items():
            if managed_task.future.done():
                to_remove.append(task_id)

        for task_id in to_remove:
            del self._active_tasks[task_id]

        if to_remove:
            logger.debug(f"Cleaned up {len(to_remove)} completed tasks")

    async def get_connection(self, url: str):
        """
        Get a WebSocket connection (with concurrency limiting).

        Note: Connection pooling is currently disabled because services
        close connections after each analysis. Each request gets a fresh connection.

        Args:
            url: WebSocket URL to connect to

        Returns:
            WebSocket connection (context manager)
        """
        # Check circuit breaker
        circuit = self._circuit_breakers[url]
        if not circuit.can_attempt():
            raise ConnectionError(f"Circuit breaker open for {url}, service unavailable")

        # Acquire semaphore to limit concurrent connections
        async with self._semaphore:
            try:
                # Always create fresh connection (pooling disabled due to protocol)
                logger.debug(f"Creating new WebSocket connection to {url}")
                ws = await websockets.connect(
                    url,
                    open_timeout=self.connection_timeout,
                    close_timeout=10,
                    ping_interval=None,  # Disable pings to avoid timeout during long analyses
                    ping_timeout=None,
                    max_size=100 * 1024 * 1024  # 100MB for large SARIF responses
                )
                circuit.record_success()
                return ws
            except Exception as e:
                circuit.record_failure()
                logger.error(f"Failed to connect to {url}: {e}")
                raise

    def register_task(
        self,
        task_id: str,
        model_slug: str,
        app_number: int,
        analysis_type: str,
        future: asyncio.Future
    ) -> ManagedTask:
        """
        Register a new managed task for tracking and cancellation.

        Args:
            task_id: Unique task identifier
            model_slug: Model being analyzed
            app_number: App number
            analysis_type: Type of analysis
            future: asyncio.Future for the task

        Returns:
            ManagedTask instance
        """
        managed_task = ManagedTask(
            task_id=task_id,
            model_slug=model_slug,
            app_number=app_number,
            analysis_type=analysis_type,
            future=future
        )
        self._active_tasks[task_id] = managed_task
        logger.debug(f"Registered task {task_id} for {model_slug}/app{app_number}")
        return managed_task

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a tracked task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if task was found and cancelled, False otherwise
        """
        managed_task = self._active_tasks.get(task_id)
        if managed_task:
            logger.info(f"Cancelling task {task_id}")
            managed_task.cancel()
            return True
        return False

    def get_task(self, task_id: str) -> Optional[ManagedTask]:
        """Get a tracked task by ID."""
        return self._active_tasks.get(task_id)

    async def deduplicate_request(
        self,
        model_slug: str,
        app_number: int,
        task_id: str,
        request_fn
    ):
        """
        Deduplicate concurrent analysis requests.

        If an identical request is already running, wait for and return that result
        instead of starting a new analysis.

        Args:
            model_slug: Model being analyzed
            app_number: App number
            task_id: Task ID
            request_fn: Async function to execute if no duplicate exists

        Returns:
            Analysis result (from cache or new execution)
        """
        key = (model_slug, app_number, task_id)

        # Check if request is already pending
        if key in self._pending_requests:
            logger.info(f"Deduplicating request for {model_slug}/app{app_number}/{task_id}")
            return await self._pending_requests[key]

        # Create new future for this request
        future = asyncio.get_event_loop().create_future()
        self._pending_requests[key] = future

        try:
            result = await request_fn()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            # Remove from pending requests
            self._pending_requests.pop(key, None)

    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        active_circuits = sum(1 for cb in self._circuit_breakers.values() if cb.state != CircuitState.CLOSED)

        return {
            "max_concurrent_connections": self.max_concurrent,
            "active_connections": self.max_concurrent - self._semaphore._value,
            "pooled_connections": len(self._pool),
            "active_tasks": len(self._active_tasks),
            "pending_requests": len(self._pending_requests),
            "circuit_breakers": {
                "total": len(self._circuit_breakers),
                "open_or_half_open": active_circuits
            }
        }


# Global singleton instance
_connection_pool: Optional[ConnectionPool] = None


def get_connection_pool() -> ConnectionPool:
    """Get the singleton ConnectionPool instance."""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = ConnectionPool()
    return _connection_pool


async def initialize_connection_pool(**kwargs):
    """Initialize and start the connection pool."""
    global _connection_pool
    _connection_pool = ConnectionPool(**kwargs)
    await _connection_pool.start()
    return _connection_pool


async def shutdown_connection_pool():
    """Shutdown the connection pool."""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.stop()
        _connection_pool = None
