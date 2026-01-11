"""
Circuit Breaker and Retry Utilities
====================================

Provides resilience patterns for service calls:
- Circuit breaker to prevent cascading failures
- Exponential backoff retry for transient errors
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from threading import Lock
from typing import Any, Callable, Dict, Optional, TypeVar, Generic

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation, requests pass through
    OPEN = "open"          # Failing, requests are rejected
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5      # Failures before opening circuit
    recovery_timeout: float = 30.0  # Seconds before trying again
    success_threshold: int = 2      # Successes in half-open before closing
    

@dataclass
class CircuitBreakerState:
    """State tracking for a circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    lock: Lock = field(default_factory=Lock)


class CircuitBreaker:
    """Circuit breaker implementation for service resilience.
    
    When a service fails repeatedly, the circuit "opens" and rejects
    requests immediately, giving the service time to recover. After
    a timeout, the circuit enters "half-open" state where it allows
    a few test requests through.
    
    Usage:
        breaker = CircuitBreaker("analyzer-service")
        
        @breaker
        def call_analyzer():
            return analyzer.run()
    
    Or manually:
        if breaker.allow_request():
            try:
                result = call_analyzer()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure()
                raise
    """
    
    # Shared state across instances with same name
    _breakers: Dict[str, CircuitBreakerState] = {}
    _global_lock = Lock()
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        # Get or create shared state
        with CircuitBreaker._global_lock:
            if name not in CircuitBreaker._breakers:
                CircuitBreaker._breakers[name] = CircuitBreakerState()
            self._state = CircuitBreaker._breakers[name]
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        return self._state.state
    
    @property
    def is_closed(self) -> bool:
        """Check if circuit is closed (normal operation)."""
        return self._state.state == CircuitState.CLOSED
    
    @property
    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        return self._state.state == CircuitState.OPEN
    
    def allow_request(self) -> bool:
        """Check if a request should be allowed through.
        
        Returns:
            True if request is allowed, False if circuit is open
        """
        with self._state.lock:
            if self._state.state == CircuitState.CLOSED:
                return True
            
            if self._state.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if self._state.last_failure_time:
                    elapsed = (datetime.now() - self._state.last_failure_time).total_seconds()
                    if elapsed >= self.config.recovery_timeout:
                        logger.info(f"Circuit {self.name}: transitioning to HALF_OPEN after {elapsed:.1f}s")
                        self._state.state = CircuitState.HALF_OPEN
                        self._state.success_count = 0
                        return True
                return False
            
            # HALF_OPEN - allow limited requests
            return True
    
    def record_success(self) -> None:
        """Record a successful request."""
        with self._state.lock:
            self._state.last_success_time = datetime.now()
            
            if self._state.state == CircuitState.HALF_OPEN:
                self._state.success_count += 1
                if self._state.success_count >= self.config.success_threshold:
                    logger.info(f"Circuit {self.name}: closing after {self._state.success_count} successes")
                    self._state.state = CircuitState.CLOSED
                    self._state.failure_count = 0
                    self._state.success_count = 0
            elif self._state.state == CircuitState.CLOSED:
                # Reset failure count on success
                self._state.failure_count = 0
    
    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed request."""
        with self._state.lock:
            self._state.last_failure_time = datetime.now()
            self._state.failure_count += 1
            
            if self._state.state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                logger.warning(f"Circuit {self.name}: reopening after failure in HALF_OPEN")
                self._state.state = CircuitState.OPEN
                self._state.success_count = 0
            elif self._state.state == CircuitState.CLOSED:
                if self._state.failure_count >= self.config.failure_threshold:
                    logger.warning(
                        f"Circuit {self.name}: opening after {self._state.failure_count} failures"
                    )
                    self._state.state = CircuitState.OPEN
    
    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._state.lock:
            self._state.state = CircuitState.CLOSED
            self._state.failure_count = 0
            self._state.success_count = 0
            self._state.last_failure_time = None
            logger.info(f"Circuit {self.name}: manually reset")
    
    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to wrap a function with circuit breaker."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not self.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is open"
                )
            
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure(e)
                raise
        
        return wrapper
    
    def get_status(self) -> Dict[str, Any]:
        """Get current circuit breaker status."""
        with self._state.lock:
            return {
                'name': self.name,
                'state': self._state.state.value,
                'failure_count': self._state.failure_count,
                'success_count': self._state.success_count,
                'last_failure': self._state.last_failure_time.isoformat() if self._state.last_failure_time else None,
                'last_success': self._state.last_success_time.isoformat() if self._state.last_success_time else None,
                'config': {
                    'failure_threshold': self.config.failure_threshold,
                    'recovery_timeout': self.config.recovery_timeout,
                    'success_threshold': self.config.success_threshold,
                }
            }


class CircuitBreakerOpenError(Exception):
    """Raised when a circuit breaker is open and rejecting requests."""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    retryable_exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        retryable_exceptions: Tuple of exceptions that should trigger retry
        on_retry: Optional callback called on each retry with (attempt, exception)
    
    Usage:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def call_service():
            return service.request()
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt >= max_retries:
                        logger.error(
                            f"Retry exhausted after {max_retries + 1} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
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


# Pre-configured circuit breakers for common services
ANALYZER_CIRCUIT_BREAKER = CircuitBreaker(
    "analyzer-services",
    CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=30.0,
        success_threshold=2
    )
)

STATIC_ANALYZER_BREAKER = CircuitBreaker(
    "static-analyzer",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=20.0)
)

DYNAMIC_ANALYZER_BREAKER = CircuitBreaker(
    "dynamic-analyzer",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0)  # Longer for ZAP
)

PERFORMANCE_TESTER_BREAKER = CircuitBreaker(
    "performance-tester",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
)

AI_ANALYZER_BREAKER = CircuitBreaker(
    "ai-analyzer",
    CircuitBreakerConfig(failure_threshold=3, recovery_timeout=30.0)
)


def get_all_circuit_breaker_statuses() -> Dict[str, Dict[str, Any]]:
    """Get status of all circuit breakers."""
    return {
        name: CircuitBreaker(name).get_status()
        for name in CircuitBreaker._breakers.keys()
    }


__all__ = [
    'CircuitBreaker',
    'CircuitBreakerConfig',
    'CircuitBreakerOpenError',
    'CircuitState',
    'retry_with_backoff',
    'ANALYZER_CIRCUIT_BREAKER',
    'STATIC_ANALYZER_BREAKER',
    'DYNAMIC_ANALYZER_BREAKER',
    'PERFORMANCE_TESTER_BREAKER',
    'AI_ANALYZER_BREAKER',
    'get_all_circuit_breaker_statuses',
]
