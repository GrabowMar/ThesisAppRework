"""
Async Utilities
===============

Safe utilities for running async code from synchronous contexts,
handling the common case where an event loop may or may not already be running.
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine safely from a synchronous context.
    
    This function handles the common problem of needing to run async code
    from a sync context when there may or may not already be an event loop running
    (e.g., from Celery workers using prefork pool, Flask request handlers, etc.).
    
    Strategy:
    1. If no event loop is running, create a new one and run the coroutine
    2. If an event loop IS running (e.g., in Celery prefork), use a thread pool
       to run the coroutine in a separate thread with its own event loop
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
        
    Raises:
        Any exception raised by the coroutine
    """
    try:
        # Check if there's already a running event loop
        loop = asyncio.get_running_loop()
        # We're inside an async context - use thread pool to avoid blocking
        logger.debug("Running async code via thread pool (event loop already running)")
        return _run_in_thread(coro)
    except RuntimeError:
        # No running event loop - safe to create one
        logger.debug("Running async code via new event loop")
        return asyncio.run(coro)


def _run_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a separate thread with its own event loop.
    
    This is used when we're already inside an async context and can't
    use asyncio.run() directly.
    """
    def _thread_runner():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()
    
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_thread_runner)
        return future.result()


def run_async_with_timeout(
    coro: Coroutine[Any, Any, T],
    timeout: float = 30.0,
    default: T = None  # type: ignore
) -> T:
    """Run an async coroutine safely with a timeout.
    
    Args:
        coro: The coroutine to run
        timeout: Timeout in seconds
        default: Default value to return on timeout
        
    Returns:
        The result of the coroutine, or default on timeout
    """
    async def _with_timeout():
        return await asyncio.wait_for(coro, timeout=timeout)
    
    try:
        return run_async_safely(_with_timeout())
    except asyncio.TimeoutError:
        logger.warning(f"Async operation timed out after {timeout}s")
        return default
    except Exception as e:
        logger.error(f"Async operation failed: {e}")
        return default


def is_event_loop_running() -> bool:
    """Check if there's currently an event loop running.
    
    Returns:
        True if an event loop is running, False otherwise
    """
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False


__all__ = [
    'run_async_safely',
    'run_async_with_timeout',
    'is_event_loop_running',
]
