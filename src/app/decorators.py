"""
Standardized Decorators for the Application
=========================================

This module contains reusable decorators to standardize behavior across the application.
"""

import functools
import logging
import time
from typing import Any, Callable, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: Union[type[Exception], tuple[type[Exception], ...]] = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Exception type or tuple of exceptions that should trigger retry
        on_retry: Optional callback called on each retry with (attempt, exception)
    
    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def call_service():
            return service.request()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        logger.error(
                            f"Retry exhausted after {max_retries + 1} attempts for {func.__name__}: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    
                    if on_retry:
                        on_retry(attempt + 1, e)
                    
                    time.sleep(delay)
            
            # Should never reach here, but for type safety
            if last_exception:
                raise last_exception
            raise RuntimeError("Retry logic error")
        
        return wrapper
    return decorator


def log_execution(
    level: int = logging.INFO,
    with_args: bool = False,
    with_result: bool = False
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to log function execution details.
    
    Args:
        level: Logging level (default: logging.INFO)
        with_args: If True, log arguments (be careful with sensitive data)
        with_result: If True, log the result (be careful with large/sensitive data)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            func_name = func.__name__
            
            if with_args:
                args_str = ", ".join([str(a) for a in args] + [f"{k}={v}" for k, v in kwargs.items()])
                logger.log(level, f"Executing {func_name}({args_str})")
            else:
                logger.log(level, f"Executing {func_name}")
            
            start_time = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration = time.perf_counter() - start_time
                
                if with_result:
                    logger.log(level, f"{func_name} completed in {duration:.4f}s with result: {result}")
                else:
                    logger.log(level, f"{func_name} completed in {duration:.4f}s")
                    
                return result
            except Exception as e:
                duration = time.perf_counter() - start_time
                logger.error(f"{func_name} failed after {duration:.4f}s: {e}")
                raise
        
        return wrapper
    return decorator
