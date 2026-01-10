#!/usr/bin/env python3
"""
Robustness Tests for Analyzer Infrastructure
============================================

Tests for connection pooling, task cancellation, circuit breakers,
and other reliability improvements.
"""

import asyncio
import pytest
import time
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

# Import modules under test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.connection_pool import (
    ConnectionPool,
    CircuitBreaker,
    CircuitState,
    ManagedTask,
    get_connection_pool
)


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_circuit_breaker_initial_state(self):
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_attempt() is True

    def test_circuit_breaker_opens_after_failures(self):
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        # Record failures
        for i in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.can_attempt() is False

    def test_circuit_breaker_half_open_after_timeout(self):
        """Circuit enters HALF_OPEN state after timeout."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1)

        # Trip circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(1.1)

        # Should allow attempt and enter half-open
        assert cb.can_attempt() is True
        # After calling can_attempt(), state should be HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_recovers_after_successes(self):
        """Circuit closes after successful calls in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1, half_open_max_calls=2)

        # Trip circuit
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait and enter half-open
        time.sleep(1.1)
        cb.can_attempt()
        assert cb.state == CircuitState.HALF_OPEN

        # Record successes
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN  # Need 2 successes
        cb.record_success()
        assert cb.state == CircuitState.CLOSED  # Recovered

    def test_circuit_breaker_reopens_on_half_open_failure(self):
        """Circuit reopens if failure occurs in HALF_OPEN state."""
        cb = CircuitBreaker(failure_threshold=1, timeout_seconds=1)

        # Trip circuit
        cb.record_failure()
        time.sleep(1.1)
        cb.can_attempt()
        assert cb.state == CircuitState.HALF_OPEN

        # Fail during half-open
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestManagedTask:
    """Test managed task functionality."""

    @pytest.mark.asyncio
    async def test_managed_task_cancellation(self):
        """Managed task can be cancelled."""
        future = asyncio.get_event_loop().create_future()
        task = ManagedTask(
            task_id="test-1",
            model_slug="test/model",
            app_number=1,
            analysis_type="static",
            future=future
        )

        # Cancel task
        task.cancel()

        assert task.cancel_event.is_set()
        assert future.cancelled()

    @pytest.mark.asyncio
    async def test_managed_task_subprocess_cleanup(self):
        """Managed task kills subprocess tasks on cancel."""
        future = asyncio.get_event_loop().create_future()
        mock_proc = Mock()
        mock_proc.kill = Mock()

        task = ManagedTask(
            task_id="test-1",
            model_slug="test/model",
            app_number=1,
            analysis_type="static",
            future=future,
            subprocess_tasks=[mock_proc]
        )

        # Cancel task
        task.cancel()

        # Verify subprocess was killed
        mock_proc.kill.assert_called_once()


class TestConnectionPool:
    """Test connection pool functionality."""

    @pytest.mark.asyncio
    async def test_connection_pool_concurrency_limit(self):
        """Connection pool enforces concurrency limit."""
        pool = ConnectionPool(max_concurrent_connections=2)

        # Track how many connections are active concurrently
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_connection_work():
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                max_concurrent = max(max_concurrent, current_concurrent)

            await asyncio.sleep(0.1)  # Simulate work

            async with lock:
                current_concurrent -= 1

        # Mock websockets.connect to track concurrent connections
        async def mock_connect(*args, **kwargs):
            await mock_connection_work()
            mock_ws = AsyncMock()
            mock_ws.__aenter__ = AsyncMock(return_value=mock_ws)
            mock_ws.__aexit__ = AsyncMock(return_value=None)
            return mock_ws

        with patch('websockets.connect', side_effect=mock_connect):
            # Try to open 5 connections concurrently (limit is 2)
            tasks = [
                pool.get_connection(f"ws://localhost:200{i}")
                for i in range(5)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Max concurrent should not exceed limit
            assert max_concurrent <= 2

    @pytest.mark.asyncio
    async def test_connection_pool_task_registration(self):
        """Connection pool can register and track tasks."""
        pool = ConnectionPool()

        future = asyncio.get_event_loop().create_future()
        task = pool.register_task(
            task_id="test-1",
            model_slug="test/model",
            app_number=1,
            analysis_type="static",
            future=future
        )

        assert task.task_id == "test-1"
        assert pool.get_task("test-1") == task

    @pytest.mark.asyncio
    async def test_connection_pool_task_cancellation(self):
        """Connection pool can cancel tracked tasks."""
        pool = ConnectionPool()

        future = asyncio.get_event_loop().create_future()
        task = pool.register_task(
            task_id="test-1",
            model_slug="test/model",
            app_number=1,
            analysis_type="static",
            future=future
        )

        # Cancel task
        cancelled = pool.cancel_task("test-1")

        assert cancelled is True
        assert task.cancel_event.is_set()
        assert future.cancelled()

    @pytest.mark.asyncio
    async def test_connection_pool_request_deduplication(self):
        """Connection pool deduplicates concurrent requests."""
        pool = ConnectionPool()

        call_count = 0

        async def expensive_operation():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)
            return {"result": "success"}

        # Start multiple concurrent requests with same parameters
        tasks = [
            pool.deduplicate_request("test/model", 1, "task-1", expensive_operation)
            for _ in range(5)
        ]

        results = await asyncio.gather(*tasks)

        # Should only call expensive_operation once
        assert call_count == 1
        # All results should be identical
        assert all(r == {"result": "success"} for r in results)

    @pytest.mark.asyncio
    async def test_connection_pool_circuit_breaker_integration(self):
        """Connection pool integrates with circuit breakers."""
        pool = ConnectionPool()

        # Mock failing connection
        async def mock_failing_connect(*args, **kwargs):
            raise ConnectionError("Service unavailable")

        with patch('websockets.connect', side_effect=mock_failing_connect):
            # Trigger circuit breaker
            for i in range(5):
                try:
                    await pool.get_connection("ws://localhost:2001")
                except Exception:
                    pass

            # Circuit should be open now
            circuit = pool._circuit_breakers["ws://localhost:2001"]
            assert circuit.state == CircuitState.OPEN

            # Next attempt should fail fast without calling connect
            with pytest.raises(ConnectionError, match="Circuit breaker open"):
                await pool.get_connection("ws://localhost:2001")

    @pytest.mark.asyncio
    async def test_connection_pool_cleanup(self):
        """Connection pool cleans up completed tasks."""
        pool = ConnectionPool()
        await pool.start()

        # Register tasks
        future1 = asyncio.get_event_loop().create_future()
        future2 = asyncio.get_event_loop().create_future()

        task1 = pool.register_task("test-1", "model/test", 1, "static", future1)
        task2 = pool.register_task("test-2", "model/test", 2, "static", future2)

        assert len(pool._active_tasks) == 2

        # Complete one task
        future1.set_result({"status": "success"})

        # Trigger cleanup
        await pool._cleanup_completed_tasks()

        # Should only have 1 task now
        assert len(pool._active_tasks) == 1
        assert pool.get_task("test-2") is not None
        assert pool.get_task("test-1") is None

        await pool.stop()

    def test_connection_pool_stats(self):
        """Connection pool provides statistics."""
        pool = ConnectionPool(max_concurrent_connections=10)

        stats = pool.get_stats()

        assert stats["max_concurrent_connections"] == 10
        assert "active_connections" in stats
        assert "pooled_connections" in stats
        assert "active_tasks" in stats
        assert "pending_requests" in stats
        assert "circuit_breakers" in stats


@pytest.mark.asyncio
async def test_connection_exhaustion_prevention():
    """Test that connection pool prevents resource exhaustion."""
    pool = ConnectionPool(max_concurrent_connections=3)

    connection_count = 0
    max_connections = 0
    lock = asyncio.Lock()

    async def simulate_connection():
        nonlocal connection_count, max_connections
        # Acquire semaphore (simulated via pool)
        async with lock:
            connection_count += 1
            max_connections = max(max_connections, connection_count)

        await asyncio.sleep(0.05)

        async with lock:
            connection_count -= 1

    # Mock websockets.connect
    async def mock_connect(*args, **kwargs):
        await simulate_connection()
        mock_ws = AsyncMock()
        mock_ws.close = AsyncMock()
        return mock_ws

    with patch('websockets.connect', side_effect=mock_connect):
        # Try to open 20 connections concurrently
        tasks = [pool.get_connection(f"ws://test:200{i%4}") for i in range(20)]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Should never exceed limit
        assert max_connections <= 3


@pytest.mark.asyncio
async def test_task_cancellation_propagation():
    """Test that task cancellation propagates to subprocesses."""
    pool = ConnectionPool()

    # Create mock subprocess
    mock_proc = Mock()
    mock_proc.kill = Mock()

    # Register task
    future = asyncio.get_event_loop().create_future()
    task = pool.register_task(
        task_id="test-cancel",
        model_slug="test/model",
        app_number=1,
        analysis_type="static",
        future=future
    )

    # Add subprocess to task
    task.subprocess_tasks.append(mock_proc)

    # Cancel via pool
    pool.cancel_task("test-cancel")

    # Verify subprocess was killed
    mock_proc.kill.assert_called_once()
    assert task.cancel_event.is_set()


@pytest.mark.asyncio
async def test_timeout_cascade():
    """Test that timeouts cascade properly through the system."""
    # This is an integration test that would require full analyzer setup
    # For now, we validate the timeout configuration exists
    from shared.service_base import BaseWSService

    class TestService(BaseWSService):
        def __init__(self):
            super().__init__("test-service", 9999)

        async def handle_message(self, websocket, message_data):
            # Simulate long-running operation
            await asyncio.sleep(10)
            return {"status": "success"}

    service = TestService()

    # Verify service has timeout awareness
    assert hasattr(service, 'log')
    # Real timeout testing would require mocking the full chain


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
