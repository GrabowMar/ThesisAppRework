"""Rate Limiter Service
======================

Implements rate limiting and circuit breaker patterns for external API calls.

Key Features:
- Token bucket rate limiting for sustained throughput control
- Circuit breaker pattern to detect and respond to API instability
- Exponential backoff with jitter for retry delays
- Per-model and global rate limiting

This prevents cascading failures when external APIs (like OpenRouter) become unstable
by detecting error patterns and throttling requests proactively.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"      # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimiterConfig:
    """Configuration for rate limiter behavior.
    
    Attributes:
        requests_per_minute: Maximum sustained request rate
        burst_size: Maximum burst of requests allowed
        min_request_interval: Minimum seconds between requests (prevents burst)
        cooldown_after_batch: Seconds to wait after completing a batch
        max_concurrent_requests: Maximum concurrent API calls allowed
    """
    requests_per_minute: float = 10.0  # 10 requests/min = 1 every 6 seconds sustained
    burst_size: int = 3  # Allow small burst at start
    min_request_interval: float = 2.0  # Minimum 2 seconds between any requests
    cooldown_after_batch: float = 5.0  # 5 second cooldown between batches
    max_concurrent_requests: int = 2  # Maximum concurrent API calls


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior.
    
    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds before attempting recovery (half-open state)
        half_open_max_calls: Number of test calls in half-open state
        error_rate_threshold: Error percentage to trigger circuit (0.0-1.0)
        sample_window_size: Number of recent calls to track for error rate
    """
    failure_threshold: int = 3  # Open after 3 consecutive failures
    recovery_timeout: float = 60.0  # Wait 60 seconds before retry
    half_open_max_calls: int = 1  # Allow 1 test call in half-open
    error_rate_threshold: float = 0.5  # Open if 50% error rate
    sample_window_size: int = 10  # Track last 10 calls


@dataclass
class CallRecord:
    """Record of an API call for statistics."""
    timestamp: float
    success: bool
    duration: float
    error: Optional[str] = None


class TokenBucket:
    """Token bucket rate limiter implementation.
    
    Provides smooth rate limiting with burst capability.
    Tokens are added at a constant rate up to a maximum (burst_size).
    Each request consumes one token.
    """
    
    def __init__(self, rate: float, burst_size: int, min_interval: float = 0.0):
        """Initialize token bucket.
        
        Args:
            rate: Tokens per second to add
            burst_size: Maximum tokens (bucket capacity)
            min_interval: Minimum seconds between token consumption
        """
        self._rate = rate
        self._burst_size = burst_size
        self._min_interval = min_interval
        self._tokens = float(burst_size)  # Start with full bucket
        self._last_update = time.time()
        self._last_consume = 0.0
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._tokens = min(self._burst_size, self._tokens + elapsed * self._rate)
        self._last_update = now
    
    def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without blocking.
        
        Returns:
            True if tokens acquired, False if not enough tokens
        """
        with self._lock:
            self._refill()
            
            # Check minimum interval
            now = time.time()
            if self._min_interval > 0 and (now - self._last_consume) < self._min_interval:
                return False
            
            if self._tokens >= tokens:
                self._tokens -= tokens
                self._last_consume = now
                return True
            return False
    
    def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """Wait until a token is available.
        
        Args:
            timeout: Maximum seconds to wait (None = wait forever)
            
        Returns:
            True if token acquired, False if timeout
        """
        start_time = time.time()
        
        while True:
            if self.try_acquire():
                return True
            
            # Calculate wait time
            with self._lock:
                self._refill()
                tokens_needed = 1 - self._tokens
                wait_time = max(0.1, tokens_needed / self._rate)
                
                # Also check minimum interval
                if self._min_interval > 0:
                    time_since_last = time.time() - self._last_consume
                    interval_wait = self._min_interval - time_since_last
                    wait_time = max(wait_time, interval_wait)
            
            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            time.sleep(min(wait_time, 1.0))  # Sleep in small increments
    
    async def async_wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """Async version of wait_for_token."""
        start_time = time.time()
        
        while True:
            if self.try_acquire():
                return True
            
            # Calculate wait time
            with self._lock:
                self._refill()
                tokens_needed = 1 - self._tokens
                wait_time = max(0.1, tokens_needed / self._rate)
                
                if self._min_interval > 0:
                    time_since_last = time.time() - self._last_consume
                    interval_wait = self._min_interval - time_since_last
                    wait_time = max(wait_time, interval_wait)
            
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False
            
            await asyncio.sleep(min(wait_time, 1.0))
    
    @property
    def available_tokens(self) -> float:
        """Get current available tokens."""
        with self._lock:
            self._refill()
            return self._tokens


class CircuitBreaker:
    """Circuit breaker pattern implementation.
    
    Prevents cascading failures by detecting error patterns and
    temporarily blocking requests to unhealthy services.
    
    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service unhealthy, requests fail fast
    - HALF_OPEN: Testing recovery, limited requests allowed
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """Initialize circuit breaker.
        
        Args:
            name: Identifier for this circuit (e.g., 'openrouter')
            config: Circuit breaker configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._call_history: list[CallRecord] = []
        self._lock = threading.Lock()
        
        logger.info(f"CircuitBreaker '{name}' initialized (threshold={self.config.failure_threshold})")
    
    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if recovery timeout has elapsed
                if self._last_failure_time is not None:
                    elapsed = time.time() - self._last_failure_time
                    if elapsed >= self.config.recovery_timeout:
                        self._state = CircuitState.HALF_OPEN
                        self._half_open_calls = 0
                        logger.info(
                            f"CircuitBreaker '{self.name}' transitioning to HALF_OPEN "
                            f"after {elapsed:.1f}s recovery timeout"
                        )
            return self._state
    
    def can_execute(self) -> bool:
        """Check if a request can be executed.
        
        Returns:
            True if circuit allows execution, False if blocked
        """
        state = self.state  # This checks for timeout-based transitions
        
        if state == CircuitState.CLOSED:
            return True
        
        if state == CircuitState.HALF_OPEN:
            with self._lock:
                if self._half_open_calls < self.config.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
        
        # OPEN state
        return False
    
    def record_success(self, duration: float = 0.0) -> None:
        """Record a successful call.
        
        Args:
            duration: How long the call took in seconds
        """
        with self._lock:
            self._failure_count = 0
            self._call_history.append(CallRecord(
                timestamp=time.time(),
                success=True,
                duration=duration
            ))
            self._trim_history()
            
            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.CLOSED
                logger.info(f"CircuitBreaker '{self.name}' recovered, now CLOSED")
    
    def record_failure(self, error: Optional[str] = None, duration: float = 0.0) -> None:
        """Record a failed call.
        
        Args:
            error: Optional error message
            duration: How long the call took in seconds
        """
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            self._call_history.append(CallRecord(
                timestamp=time.time(),
                success=False,
                duration=duration,
                error=error
            ))
            self._trim_history()
            
            # Check if we should open the circuit
            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open goes back to open
                self._state = CircuitState.OPEN
                logger.warning(
                    f"CircuitBreaker '{self.name}' failed during recovery test, "
                    f"returning to OPEN state"
                )
            elif self._state == CircuitState.CLOSED:
                # Check consecutive failures
                if self._failure_count >= self.config.failure_threshold:
                    self._state = CircuitState.OPEN
                    logger.warning(
                        f"CircuitBreaker '{self.name}' OPENED after "
                        f"{self._failure_count} consecutive failures. "
                        f"Will retry in {self.config.recovery_timeout}s"
                    )
                # Also check error rate if we have enough samples
                elif len(self._call_history) >= self.config.sample_window_size:
                    error_rate = self._calculate_error_rate()
                    if error_rate >= self.config.error_rate_threshold:
                        self._state = CircuitState.OPEN
                        logger.warning(
                            f"CircuitBreaker '{self.name}' OPENED due to high error rate "
                            f"({error_rate:.1%}). Will retry in {self.config.recovery_timeout}s"
                        )
    
    def _calculate_error_rate(self) -> float:
        """Calculate recent error rate from call history."""
        if not self._call_history:
            return 0.0
        
        recent = self._call_history[-self.config.sample_window_size:]
        failures = sum(1 for c in recent if not c.success)
        return failures / len(recent)
    
    def _trim_history(self) -> None:
        """Keep only recent call history."""
        max_size = self.config.sample_window_size * 2
        if len(self._call_history) > max_size:
            self._call_history = self._call_history[-max_size:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        with self._lock:
            return {
                'name': self.name,
                'state': self.state.value,
                'failure_count': self._failure_count,
                'error_rate': self._calculate_error_rate(),
                'calls_in_window': len(self._call_history),
                'last_failure_time': self._last_failure_time,
                'time_until_retry': (
                    max(0, self.config.recovery_timeout - (time.time() - self._last_failure_time))
                    if self._state == CircuitState.OPEN and self._last_failure_time
                    else 0
                ),
            }
    
    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info(f"CircuitBreaker '{self.name}' manually reset to CLOSED")


class APIRateLimiter:
    """Combined rate limiter and circuit breaker for API calls.
    
    Provides:
    - Token bucket rate limiting for sustained throughput
    - Circuit breaker for failure detection
    - Exponential backoff with jitter
    - Batch cooldown periods
    - Concurrent request limiting
    """
    
    def __init__(
        self,
        name: str = "api",
        rate_config: Optional[RateLimiterConfig] = None,
        circuit_config: Optional[CircuitBreakerConfig] = None
    ):
        """Initialize API rate limiter.
        
        Args:
            name: Identifier for this limiter
            rate_config: Rate limiting configuration
            circuit_config: Circuit breaker configuration
        """
        self.name = name
        self.rate_config = rate_config or RateLimiterConfig()
        
        # Create token bucket (convert requests/minute to requests/second)
        rate_per_second = self.rate_config.requests_per_minute / 60.0
        self._bucket = TokenBucket(
            rate=rate_per_second,
            burst_size=self.rate_config.burst_size,
            min_interval=self.rate_config.min_request_interval
        )
        
        # Create circuit breaker
        self._circuit = CircuitBreaker(name, circuit_config)
        
        # Concurrent request tracking
        self._active_requests = 0
        self._active_lock = threading.Lock()
        
        # Batch tracking
        self._batch_start_time: Optional[float] = None
        self._batch_request_count = 0
        
        # Backoff state
        self._consecutive_failures = 0
        self._base_backoff = 2.0  # Base backoff in seconds
        self._max_backoff = 60.0  # Maximum backoff in seconds
        
        logger.info(
            f"APIRateLimiter '{name}' initialized: "
            f"rate={self.rate_config.requests_per_minute}/min, "
            f"burst={self.rate_config.burst_size}, "
            f"max_concurrent={self.rate_config.max_concurrent_requests}"
        )
    
    def _acquire_slot(self) -> bool:
        """Try to acquire a concurrent request slot.
        
        Returns:
            True if slot acquired, False if at capacity
        """
        with self._active_lock:
            if self._active_requests >= self.rate_config.max_concurrent_requests:
                return False
            self._active_requests += 1
            return True
    
    def _release_slot(self) -> None:
        """Release a concurrent request slot."""
        with self._active_lock:
            self._active_requests = max(0, self._active_requests - 1)
    
    def _calculate_backoff(self) -> float:
        """Calculate backoff delay with exponential increase and jitter.
        
        Implements exponential backoff: base_delay * (2 ^ (failures - 1))
        With jitter to prevent thundering herd: ±25% randomization
        
        Examples:
        - 0 failures: 0 delay
        - 1 failure: 2.0s ± 0.5s jitter
        - 2 failures: 4.0s ± 1.0s jitter  
        - 3 failures: 8.0s ± 2.0s jitter
        - Capped at max_backoff (60s)
        
        Returns:
            Delay in seconds before next retry (0 if no failures)
        """
        import random
        
        if self._consecutive_failures == 0:
            return 0.0
        
        # Exponential backoff: 2^failures * base, capped at max
        delay = min(
            self._max_backoff,
            self._base_backoff * (2 ** (self._consecutive_failures - 1))
        )
        
        # Add jitter (±25%) to prevent synchronized retries
        # random.random() returns 0.0-1.0, so (2*random-1) gives -1.0 to +1.0
        jitter = delay * 0.25 * (2 * random.random() - 1)
        return max(0, delay + jitter)
    
    async def acquire(self, timeout: Optional[float] = 300.0) -> bool:
        """Acquire permission to make an API call.
        
        This checks:
        1. Circuit breaker state
        2. Concurrent request limit
        3. Rate limit (token bucket)
        4. Backoff delay if recovering from failures
        
        Args:
            timeout: Maximum seconds to wait for permission
            
        Returns:
            True if permission granted, False if denied (circuit open or timeout)
        """
        start_time = time.time()
        
        # Step 1: Check circuit breaker - fail fast if circuit is open
        if not self._circuit.can_execute():
            stats = self._circuit.get_stats()
            logger.warning(
                f"APIRateLimiter '{self.name}' blocked by circuit breaker "
                f"(state={stats['state']}, retry in {stats['time_until_retry']:.1f}s)"
            )
            return False
        
        # Step 2: Apply exponential backoff delay if recovering from consecutive failures
        # This prevents thundering herd when service starts recovering
        backoff = self._calculate_backoff()
        if backoff > 0:
            logger.debug(f"Applying {backoff:.1f}s backoff delay after failures")
            await asyncio.sleep(backoff)
        
        # Step 3: Wait for available concurrent request slot
        # Poll until we get a slot or timeout
        while True:
            if self._acquire_slot():
                break
            
            elapsed = time.time() - start_time
            if timeout and elapsed > timeout:
                logger.warning(f"Timeout waiting for concurrent request slot")
                return False
            
            await asyncio.sleep(0.5)  # Poll every 500ms for slot availability
        
        # Step 4: Wait for rate limit token from token bucket
        # This ensures we don't exceed sustained request rate
        try:
            remaining_timeout = None
            if timeout:
                remaining_timeout = timeout - (time.time() - start_time)
                if remaining_timeout <= 0:
                    self._release_slot()  # Cleanup on timeout
                    return False
            
            if not await self._bucket.async_wait_for_token(timeout=remaining_timeout):
                self._release_slot()  # Cleanup on timeout
                logger.warning(f"Timeout waiting for rate limit token")
                return False
            
            return True  # All checks passed, permission granted
            
        except Exception as e:
            self._release_slot()  # Cleanup on exception
            raise
    
    def release(self, success: bool, error: Optional[str] = None, duration: float = 0.0) -> None:
        """Release the request slot and record result.
        
        Args:
            success: Whether the request succeeded
            error: Error message if failed
            duration: How long the request took
        """
        self._release_slot()
        
        if success:
            self._circuit.record_success(duration)
            self._consecutive_failures = 0
        else:
            self._circuit.record_failure(error, duration)
            self._consecutive_failures += 1
            logger.warning(
                f"APIRateLimiter '{self.name}' recorded failure "
                f"(consecutive={self._consecutive_failures}): {error}"
            )
    
    def start_batch(self) -> None:
        """Mark the start of a new batch of requests."""
        self._batch_start_time = time.time()
        self._batch_request_count = 0
        logger.debug(f"APIRateLimiter '{self.name}' starting new batch")
    
    async def end_batch(self) -> None:
        """Mark the end of a batch and apply cooldown."""
        if self._batch_start_time is not None:
            duration = time.time() - self._batch_start_time
            logger.info(
                f"APIRateLimiter '{self.name}' batch completed: "
                f"{self._batch_request_count} requests in {duration:.1f}s"
            )
        
        # Apply cooldown between batches
        if self.rate_config.cooldown_after_batch > 0:
            logger.debug(
                f"Applying {self.rate_config.cooldown_after_batch}s cooldown between batches"
            )
            await asyncio.sleep(self.rate_config.cooldown_after_batch)
        
        self._batch_start_time = None
        self._batch_request_count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiter and circuit breaker statistics."""
        with self._active_lock:
            active = self._active_requests
        
        return {
            'name': self.name,
            'active_requests': active,
            'max_concurrent': self.rate_config.max_concurrent_requests,
            'available_tokens': self._bucket.available_tokens,
            'consecutive_failures': self._consecutive_failures,
            'current_backoff': self._calculate_backoff(),
            'circuit': self._circuit.get_stats(),
        }
    
    def reset(self) -> None:
        """Reset rate limiter and circuit breaker state."""
        self._circuit.reset()
        self._consecutive_failures = 0
        with self._active_lock:
            self._active_requests = 0
        logger.info(f"APIRateLimiter '{self.name}' reset")


# ============================================================================
# Global singleton instances
# ============================================================================

_openrouter_limiter: Optional[APIRateLimiter] = None
_limiter_lock = threading.Lock()


def get_openrouter_rate_limiter() -> APIRateLimiter:
    """Get the global OpenRouter rate limiter singleton.
    
    Configured for OpenRouter's typical rate limits and reliability patterns.
    
    NOTE: Rate limiting is now more permissive to allow pipeline generation to work.
    The circuit breaker still provides protection against cascading failures.
    
    Returns:
        APIRateLimiter instance for OpenRouter API calls
    """
    global _openrouter_limiter
    
    with _limiter_lock:
        if _openrouter_limiter is None:
            # Configuration balanced for both protection and throughput
            # Pipeline generation needs higher concurrency to work properly
            rate_config = RateLimiterConfig(
                requests_per_minute=30.0,  # ~1 request every 2 seconds sustained
                burst_size=8,  # Allow burst for multi-query generation (4 queries per app)
                min_request_interval=0.5,  # Minimal interval - rely on circuit breaker for protection
                cooldown_after_batch=3.0,  # Short cooldown between batches
                max_concurrent_requests=4,  # Allow concurrent for pipeline (4 queries per app)
            )
            
            # Circuit breaker is the main protection against API instability
            circuit_config = CircuitBreakerConfig(
                failure_threshold=3,  # Open after 3 consecutive failures
                recovery_timeout=60.0,  # Wait 60 seconds before retry
                half_open_max_calls=1,  # Test with 1 call
                error_rate_threshold=0.5,  # Open if 50% error rate
                sample_window_size=10,  # Track last 10 calls
            )
            
            _openrouter_limiter = APIRateLimiter(
                name="openrouter",
                rate_config=rate_config,
                circuit_config=circuit_config
            )
            
            logger.info("OpenRouter rate limiter initialized (permissive mode for pipelines)")
    
    return _openrouter_limiter


def reset_openrouter_rate_limiter() -> None:
    """Reset the OpenRouter rate limiter (useful after service recovery)."""
    global _openrouter_limiter
    
    with _limiter_lock:
        if _openrouter_limiter is not None:
            _openrouter_limiter.reset()
