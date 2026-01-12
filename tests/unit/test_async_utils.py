"""Tests for async utilities."""
import asyncio
import threading
import time
import pytest
from concurrent.futures import ThreadPoolExecutor

from app.utils.async_utils import run_async_safely, run_async_with_timeout, is_event_loop_running


@pytest.mark.unit
class TestRunAsyncSafely:
    """Test run_async_safely function."""
    
    def test_simple_coroutine(self):
        """Test running a simple coroutine."""
        async def simple():
            return 42
        
        result = run_async_safely(simple())
        assert result == 42
    
    def test_coroutine_with_await(self):
        """Test running a coroutine that awaits."""
        async def with_await():
            await asyncio.sleep(0.01)
            return "done"
        
        result = run_async_safely(with_await())
        assert result == "done"
    
    def test_exception_propagation(self):
        """Test that exceptions are propagated correctly."""
        async def failing():
            raise ValueError("test error")
        
        with pytest.raises(ValueError, match="test error"):
            run_async_safely(failing())
    
    def test_multiple_sequential_calls(self):
        """Test multiple sequential calls in the same thread."""
        async def counter(n):
            await asyncio.sleep(0.01)
            return n * 2
        
        # Call multiple times - this should reuse the event loop
        results = []
        for i in range(3):
            results.append(run_async_safely(counter(i)))
        
        assert results == [0, 2, 4]
    
    def test_from_thread_pool_worker(self):
        """Test calling from a thread pool worker thread.
        
        This simulates the pipeline execution scenario where generation
        jobs run in a ThreadPoolExecutor.
        """
        async def async_work():
            await asyncio.sleep(0.01)
            return threading.current_thread().name
        
        results = []
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for _ in range(4):
                future = executor.submit(lambda: run_async_safely(async_work()))
                futures.append(future)
            
            for future in futures:
                results.append(future.result())
        
        # All should complete successfully
        assert len(results) == 4
        assert all(r is not None for r in results)
    
    def test_multiple_async_calls_per_thread_worker(self):
        """Test multiple sequential async calls within a single thread worker.
        
        This simulates the generation scenario where one job makes 4 API calls.
        """
        call_count = []
        
        async def api_call(n):
            await asyncio.sleep(0.01)
            return f"call_{n}"
        
        def worker_job():
            """Simulates a generation job that makes multiple API calls."""
            results = []
            for i in range(4):  # 4 API calls (guarded mode)
                result = run_async_safely(api_call(i))
                results.append(result)
            return results
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(worker_job) for _ in range(2)]
            results = [f.result() for f in futures]
        
        # Each worker should have made 4 successful calls
        assert len(results) == 2
        for worker_results in results:
            assert worker_results == ["call_0", "call_1", "call_2", "call_3"]
    
    def test_parallel_jobs_dont_interfere(self):
        """Test that parallel jobs in thread pool don't interfere with each other.
        
        This is the key test for the bug fix - parallel jobs should not
        cause "cannot schedule new futures after shutdown" errors.
        """
        async def slow_work(job_id, call_num):
            await asyncio.sleep(0.05)  # Simulate API latency
            return f"job{job_id}_call{call_num}"
        
        def generation_job(job_id):
            """Simulates a generation job with multiple async calls."""
            results = []
            for i in range(4):
                result = run_async_safely(slow_work(job_id, i))
                results.append(result)
            return results
        
        # Run 4 parallel jobs (similar to real pipeline scenario)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(generation_job, i) for i in range(4)]
            results = [f.result() for f in futures]
        
        # All jobs should complete successfully
        assert len(results) == 4
        for job_id, job_results in enumerate(results):
            expected = [f"job{job_id}_call{i}" for i in range(4)]
            assert job_results == expected


@pytest.mark.unit
class TestRunAsyncWithTimeout:
    """Test run_async_with_timeout function."""
    
    def test_completes_within_timeout(self):
        """Test successful completion within timeout."""
        async def quick():
            await asyncio.sleep(0.01)
            return "done"
        
        result = run_async_with_timeout(quick(), timeout=1.0)
        assert result == "done"
    
    def test_timeout_returns_default(self):
        """Test that timeout returns default value."""
        async def slow():
            await asyncio.sleep(10)
            return "done"
        
        result = run_async_with_timeout(slow(), timeout=0.1, default="timeout")
        assert result == "timeout"


@pytest.mark.unit
class TestIsEventLoopRunning:
    """Test is_event_loop_running function."""
    
    def test_not_running_in_sync_context(self):
        """Test that no event loop is running in normal sync context."""
        assert is_event_loop_running() is False
    
    def test_running_inside_async_context(self):
        """Test that event loop is running inside async context."""
        async def check():
            return is_event_loop_running()
        
        # Run in a new loop to test from inside async context
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(check())
            assert result is True
        finally:
            loop.close()
