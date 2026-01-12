"""
Async Utilities
===============

Safe utilities for running async code from synchronous contexts,
handling the common case where an event loop may or may not already be running.
"""

import asyncio
import logging
import threading
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar('T')


def run_async_safely(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async coroutine safely from a synchronous context.
    
    This function handles the common problem of needing to run async code
    from a sync context when there may or may not already be an event loop running
    (e.g., from Celery workers using prefork pool, Flask request handlers, etc.).
    
    Strategy:
    1. First, try to get or create an event loop for this thread
    2. If a loop exists and is running (we're inside async code), we need a new thread
    3. If a loop exists but isn't running, we can use it
    4. If no loop exists, create one and use it
    
    This avoids creating nested ThreadPoolExecutors which can fail with
    "cannot schedule new futures after shutdown" errors.
    
    Args:
        coro: The coroutine to run
        
    Returns:
        The result of the coroutine
        
    Raises:
        Any exception raised by the coroutine
    """
    # First, check if there's a RUNNING event loop (i.e., we're inside async code)
    try:
        loop = asyncio.get_running_loop()
        # We're inside an async context - need to run in a separate thread
        # to avoid blocking the running loop
        logger.debug("Running async code via separate thread (event loop already running)")
        return _run_in_new_thread(coro)
    except RuntimeError:
        # No running event loop - we can create/use one in this thread
        pass
    
    # Create a new event loop for this thread (avoids deprecation warning)
    # We always create a new loop to avoid issues with closed loops
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Now run the coroutine in the loop
    logger.debug(f"Running async code via event loop in thread {threading.current_thread().name}")
    try:
        return loop.run_until_complete(coro)
    finally:
        # Don't close the loop - it might be reused for subsequent calls
        # in the same thread (e.g., multiple API calls in a generation job)
        pass


def _run_in_new_thread(coro: Coroutine[Any, Any, T]) -> T:
    """Run a coroutine in a new thread with its own event loop.
    
    This is used when we're already inside an async context and can't
    use the current event loop directly.
    
    Uses a simple thread instead of ThreadPoolExecutor to avoid
    "cannot schedule new futures after shutdown" errors when the
    parent process is shutting down.
    """
    result = None
    exception = None
    
    def _thread_runner():
        nonlocal result, exception
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
        except Exception as e:
            exception = e
        finally:
            loop.close()
    
    thread = threading.Thread(target=_thread_runner, daemon=True)
    thread.start()
    thread.join()  # Wait for completion
    
    if exception is not None:
        raise exception
    return result


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
