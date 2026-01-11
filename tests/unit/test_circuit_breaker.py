"""Tests for circuit breaker utility."""

import pytest
import time
from unittest.mock import Mock, patch

from app.utils.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
    retry_with_backoff,
    get_all_circuit_breaker_statuses,
)


class TestCircuitBreaker:
    """Test CircuitBreaker class."""
    
    def test_initial_state_is_closed(self):
        """Circuit breaker should start in closed state."""
        breaker = CircuitBreaker("test-initial")
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed
        assert not breaker.is_open
    
    def test_allows_request_when_closed(self):
        """Closed circuit should allow requests."""
        breaker = CircuitBreaker("test-allow")
        assert breaker.allow_request() is True
    
    def test_opens_after_failure_threshold(self):
        """Circuit should open after reaching failure threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test-open", config)
        
        # Record failures up to threshold
        for i in range(3):
            breaker.record_failure()
        
        assert breaker.state == CircuitState.OPEN
        assert breaker.is_open
    
    def test_rejects_requests_when_open(self):
        """Open circuit should reject requests."""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=60.0)
        breaker = CircuitBreaker("test-reject", config)
        
        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        
        assert breaker.allow_request() is False
    
    def test_success_resets_failure_count(self):
        """Success should reset failure count in closed state."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test-reset", config)
        
        # Record some failures but not enough to open
        breaker.record_failure()
        breaker.record_failure()
        
        # Record success
        breaker.record_success()
        
        # Now need 3 more failures to open
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.CLOSED
        
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
    
    def test_transitions_to_half_open_after_timeout(self):
        """Circuit should transition to half-open after recovery timeout."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker("test-half-open", config)
        
        # Open the circuit
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Next request should be allowed and transition to half-open
        assert breaker.allow_request() is True
        assert breaker.state == CircuitState.HALF_OPEN
    
    def test_closes_after_success_in_half_open(self):
        """Circuit should close after success threshold in half-open."""
        config = CircuitBreakerConfig(
            failure_threshold=1, 
            recovery_timeout=0.1,
            success_threshold=2
        )
        breaker = CircuitBreaker("test-close-half", config)
        
        # Open the circuit
        breaker.record_failure()
        time.sleep(0.15)
        
        # Transition to half-open
        breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Record successes
        breaker.record_success()
        assert breaker.state == CircuitState.HALF_OPEN  # Need 2 successes
        
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
    
    def test_reopens_on_failure_in_half_open(self):
        """Circuit should reopen on failure in half-open state."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker("test-reopen", config)
        
        # Open and transition to half-open
        breaker.record_failure()
        time.sleep(0.15)
        breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN
        
        # Failure reopens
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
    
    def test_decorator_success(self):
        """Decorator should pass through successful calls."""
        breaker = CircuitBreaker("test-decorator-success")
        
        @breaker
        def successful_func():
            return "success"
        
        result = successful_func()
        assert result == "success"
    
    def test_decorator_failure(self):
        """Decorator should record failures on exceptions."""
        config = CircuitBreakerConfig(failure_threshold=2)
        breaker = CircuitBreaker("test-decorator-fail", config)
        
        @breaker
        def failing_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            failing_func()
        
        with pytest.raises(ValueError):
            failing_func()
        
        # Circuit should now be open
        assert breaker.is_open
    
    def test_decorator_rejects_when_open(self):
        """Decorator should raise CircuitBreakerOpenError when open."""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=60.0)
        breaker = CircuitBreaker("test-decorator-reject", config)
        
        @breaker
        def func():
            raise ValueError("error")
        
        # Open the circuit
        with pytest.raises(ValueError):
            func()
        
        # Next call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            func()
    
    def test_reset(self):
        """Reset should return circuit to closed state."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test-reset-method", config)
        
        # Open the circuit
        breaker.record_failure()
        assert breaker.is_open
        
        # Reset
        breaker.reset()
        assert breaker.is_closed
    
    def test_get_status(self):
        """Get status should return circuit state info."""
        breaker = CircuitBreaker("test-status")
        status = breaker.get_status()
        
        assert status['name'] == "test-status"
        assert status['state'] == "closed"
        assert 'failure_count' in status
        assert 'config' in status


class TestRetryWithBackoff:
    """Test retry_with_backoff decorator."""
    
    def test_succeeds_on_first_try(self):
        """Should succeed without retry if first call succeeds."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3)
        def success_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = success_func()
        assert result == "success"
        assert call_count == 1
    
    def test_retries_on_failure(self):
        """Should retry on exception."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def failing_then_succeeding():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary failure")
            return "success"
        
        result = failing_then_succeeding()
        assert result == "success"
        assert call_count == 3
    
    def test_raises_after_max_retries(self):
        """Should raise exception after exhausting retries."""
        call_count = 0
        
        @retry_with_backoff(max_retries=2, base_delay=0.01)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("persistent failure")
        
        with pytest.raises(ValueError, match="persistent failure"):
            always_fails()
        
        assert call_count == 3  # 1 initial + 2 retries
    
    def test_only_retries_specified_exceptions(self):
        """Should only retry on specified exception types."""
        call_count = 0
        
        @retry_with_backoff(
            max_retries=3, 
            base_delay=0.01,
            retryable_exceptions=(ValueError,)
        )
        def raises_type_error():
            nonlocal call_count
            call_count += 1
            raise TypeError("not retryable")
        
        with pytest.raises(TypeError):
            raises_type_error()
        
        # Should not retry on TypeError
        assert call_count == 1
    
    def test_on_retry_callback(self):
        """Should call on_retry callback on each retry."""
        retries = []
        
        def on_retry(attempt, exc):
            retries.append((attempt, str(exc)))
        
        @retry_with_backoff(
            max_retries=2, 
            base_delay=0.01,
            on_retry=on_retry
        )
        def always_fails():
            raise ValueError("test")
        
        with pytest.raises(ValueError):
            always_fails()
        
        assert len(retries) == 2
        assert retries[0][0] == 1
        assert retries[1][0] == 2


class TestGetAllCircuitBreakerStatuses:
    """Test get_all_circuit_breaker_statuses function."""
    
    def test_returns_all_breaker_statuses(self):
        """Should return status for all created circuit breakers."""
        # Create a few breakers
        breaker1 = CircuitBreaker("status-test-1")
        breaker2 = CircuitBreaker("status-test-2")
        
        statuses = get_all_circuit_breaker_statuses()
        
        assert "status-test-1" in statuses
        assert "status-test-2" in statuses
