# Analyzer Folder Robustness Analysis
## Comprehensive Security and Orchestration Review

**Date:** 2026-01-10
**Scope:** Complete analyzer infrastructure including services, gateway, manager, and shared modules

---

## Executive Summary

The analyzer system is generally well-structured with good separation of concerns. However, several critical robustness issues were identified that could impact reliability, especially under high load or error conditions. This analysis identifies **23 issues** ranging from critical to low severity.

### Key Findings
- ✅ **Strengths:** Good use of asyncio, comprehensive error handling, no bare exception swallowing
- ⚠️ **Concerns:** Resource leak potential, race conditions, insufficient timeout handling, missing cancellation support
- 🔴 **Critical:** WebSocket connection pool exhaustion, task cancellation gaps, ZAP daemon lifecycle issues

---

## Critical Issues (Priority 1)

### 1. WebSocket Connection Pool Exhaustion
**File:** `analyzer_manager.py:1000-1050`
**Severity:** 🔴 CRITICAL

**Problem:**
The `_send_to_service` method creates new WebSocket connections without proper pooling or connection limits. Under high concurrent analysis load, this can exhaust system resources.

```python
async with websockets.connect(url, ...) as websocket:
    # No connection pooling, no semaphore limiting concurrent connections
```

**Impact:**
- System can run out of file descriptors
- Network connection exhaustion
- Service degradation under load

**Recommendation:**
```python
class AnalyzerManager:
    def __init__(self, ...):
        self._connection_semaphore = asyncio.Semaphore(50)  # Limit concurrent connections
        self._connection_pool = {}  # Reusable connection pool
```

---

### 2. Missing Task Cancellation Support
**File:** `analyzer_manager.py:815-830`, `websocket_gateway.py:183-251`
**Severity:** 🔴 CRITICAL

**Problem:**
When analysis tasks are cancelled (via `cancel_request`), there's no mechanism to actually cancel running subprocess tools (semgrep, bandit, etc.) or WebSocket streams.

**Impact:**
- Zombie processes consuming resources
- Cannot interrupt long-running analyses
- Resource leaks when clients disconnect

**Recommendation:**
```python
class AnalysisTask:
    def __init__(self):
        self.cancel_event = asyncio.Event()
        self.subprocess_tasks = []

    async def cancel(self):
        self.cancel_event.set()
        for proc in self.subprocess_tasks:
            proc.kill()
```

---

### 3. ZAP Daemon Lifecycle Issues
**File:** `services/dynamic-analyzer/main.py:84-104`, `services/dynamic-analyzer/zap_scanner.py`
**Severity:** 🔴 CRITICAL

**Problem:**
The ZAP scanner assumes an external ZAP daemon is always running. No health checking, restart mechanism, or graceful degradation if ZAP becomes unavailable.

**Impact:**
- Silent failures if ZAP daemon crashes
- No recovery mechanism
- Tests hang waiting for non-responsive ZAP

**Recommendation:**
- Add periodic health checks to ZAP connection
- Implement connection pooling with retry logic
- Add circuit breaker pattern for ZAP availability
- Provide meaningful error messages when ZAP is unavailable

---

## High Priority Issues (Priority 2)

### 4. Insufficient Timeout Propagation
**File:** Multiple service `main.py` files
**Severity:** ⚠️ HIGH

**Problem:**
Service-level timeouts don't properly cascade to subprocess tools. A 300s analysis timeout doesn't prevent individual tools from hanging indefinitely.

**Current:**
```python
# analyzer_manager timeout=300
await self._send_to_service(...)
    # static-analyzer receives message
    # bandit runs with default timeout (infinite)
```

**Recommendation:**
- Calculate per-tool timeout budgets based on analysis timeout
- Implement hierarchical timeout: analysis_timeout > service_timeout > tool_timeout
- Add timeout context propagation through request chain

---

### 5. Race Condition in Health Check Task
**File:** `analyzer_manager.py:819`, `analyzer_manager.py:1080-1095`
**Severity:** ⚠️ HIGH

**Problem:**
Health check task is created but never awaited or tracked:
```python
asyncio.create_task(self.check_all_services_health())  # Fire and forget!
```

**Impact:**
- Exceptions in health checks are silently lost
- No way to know if health checks completed
- Potential memory leak from orphaned tasks

**Recommendation:**
```python
self._health_check_task = asyncio.create_task(self.check_all_services_health())
self._background_tasks.add(self._health_check_task)
self._health_check_task.add_done_callback(self._background_tasks.discard)
```

---

### 6. Service Base Graceful Close After Every Request
**File:** `shared/service_base.py:173-181`
**Severity:** ⚠️ HIGH

**Problem:**
The base service closes the WebSocket connection after EVERY message:
```python
await self.handle_message(websocket, data)
await websocket.close(1000, "Analysis complete")
return  # Exit handler after analysis
```

**Impact:**
- Cannot stream multiple progress updates
- Forces reconnection for every request
- Breaks long-running analysis scenarios

**Recommendation:**
Only close after terminal messages (analysis_result, error), not progress updates or status requests.

---

### 7. Inadequate Error Context in Service Responses
**File:** All service `main.py` implementations
**Severity:** ⚠️ HIGH

**Problem:**
Error messages lack critical debugging information:
```python
return {'status': 'error', 'error': str(e)}  # What was the request? Which tool failed?
```

**Recommendation:**
```python
return {
    'status': 'error',
    'error': str(e),
    'error_type': type(e).__name__,
    'traceback': traceback.format_exc() if debug_mode else None,
    'context': {
        'tool': tool_name,
        'model': model_slug,
        'app_number': app_number,
        'timestamp': datetime.utcnow().isoformat()
    }
}
```

---

## Medium Priority Issues (Priority 3)

### 8. Event Log Memory Leak Potential
**File:** `websocket_gateway.py:68-116`
**Severity:** ⚠️ MEDIUM

**Problem:**
EVENT_LOG has MAX_EVENT_LOG=200, but high-frequency events can still cause memory growth. JSONL file I/O is async but lacks error handling for disk full scenarios.

**Recommendation:**
- Implement circular buffer with hard memory limit
- Add disk space check before writing EVENT_LOG_FILE
- Rate-limit high-frequency events

---

### 9. Port Configuration Cache Never Invalidates
**File:** `analyzer_manager.py:420-470`
**Severity:** ⚠️ MEDIUM

**Problem:**
```python
if self._port_config_cache is not None:
    return self._port_config_cache  # Cached forever!
```

If port configurations change in database during runtime, manager won't see updates.

**Recommendation:**
```python
def _load_port_config(self, max_age_seconds=300):
    now = time.time()
    if self._port_config_cache and (now - self._cache_timestamp < max_age_seconds):
        return self._port_config_cache
    # Reload from database
```

---

### 10. Missing Idempotency for Analysis Requests
**File:** `analyzer_manager.py`, `websocket_gateway.py`
**Severity:** ⚠️ MEDIUM

**Problem:**
No deduplication of concurrent analysis requests for the same (model, app, task_id). Multiple clients can trigger redundant analyses.

**Recommendation:**
```python
class AnalyzerManager:
    def __init__(self):
        self._active_analyses = {}  # (model, app, task) -> Future

    async def analyze(self, request):
        key = (request.model_slug, request.app_number, request.task_id)
        if key in self._active_analyses:
            return await self._active_analyses[key]  # Wait for existing
        # Start new analysis
```

---

### 11. Subprocess Stdout/Stderr Truncation Can Hide Errors
**File:** `services/static-analyzer/main.py:110-116`
**Severity:** ⚠️ MEDIUM

**Problem:**
```python
return {'tool': tool_name, 'executed': True, 'status': 'error',
        'error': result.stderr[:500]}  # First 500 chars might not include root cause!
```

**Recommendation:**
Store full stderr, return last N lines (errors typically appear at end of output).

---

### 12. No Circuit Breaker for External Services
**File:** `services/ai-analyzer/main.py` (OpenRouter API calls)
**Severity:** ⚠️ MEDIUM

**Problem:**
Repeated failures to external APIs (OpenRouter, ZAP) cause cascading timeouts without backoff.

**Recommendation:**
Implement circuit breaker pattern:
- After N consecutive failures, trip circuit
- Fast-fail for X seconds before retrying
- Exponential backoff on retry

---

### 13. Gateway SERVICE_URLS Mixing Environment Keys
**File:** `websocket_gateway.py:61-66`
**Severity:** ⚠️ MEDIUM

**Problem:**
```python
SERVICE_URLS: Dict[ServiceType, str] = {
    ServiceType.CODE_QUALITY: os.getenv("STATIC_ANALYZER_URL", ...),
    ServiceType.SECURITY_ANALYZER: os.getenv("STATIC_ANALYZER_URL", ...),  # Same URL!
}
```

CODE_QUALITY and SECURITY_ANALYZER both use STATIC_ANALYZER_URL, which is correct architecturally but confusing.

**Recommendation:**
Add comment explaining services share the same backend URL.

---

## Low Priority Issues (Priority 4)

### 14. Inefficient SARIF Rule Stripping
**File:** `services/static-analyzer/main.py:217-262`
**Severity:** ℹ️ LOW

**Problem:**
SARIF rules are stripped after parsing. Better to configure tools to not include verbose rules in the first place.

**Recommendation:**
Use tool-specific flags: `semgrep --sarif --no-rules-metadata`

---

### 15. Missing Request Rate Limiting
**File:** `websocket_gateway.py:325-452`
**Severity:** ℹ️ LOW

**Problem:**
No per-client rate limiting. A malicious/buggy client can flood the gateway.

**Recommendation:**
```python
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self, max_requests=10, window_seconds=60):
        self.requests = defaultdict(list)
        self.max_requests = max_requests
        self.window = window_seconds
```

---

### 16. Duplicate Tool Detection Logic
**File:** All service `_detect_available_tools()` methods
**Severity:** ℹ️ LOW

**Problem:**
Each service duplicates tool detection. Should be centralized.

**Recommendation:**
Create `shared/tool_detector.py` with:
```python
def detect_tool(tool_name: str, version_flag='--version') -> bool:
    ...
```

---

### 17. Inconsistent Logging Levels
**File:** Multiple files
**Severity:** ℹ️ LOW

**Problem:**
Some services use `logger.info()` for debug-level details, others use `logger.debug()`.

**Recommendation:**
Establish logging conventions:
- DEBUG: Tool command lines, parsing steps
- INFO: Analysis start/complete, major milestones
- WARNING: Recoverable errors, degraded mode
- ERROR: Fatal errors requiring attention

---

### 18. Missing Structured Logging
**File:** All services
**Severity:** ℹ️ LOW

**Problem:**
Logs are plain text, making automated analysis difficult.

**Recommendation:**
Use structured logging (JSON):
```python
logger.info("analysis_started", extra={
    'model': model_slug,
    'app_number': app_number,
    'service': 'static-analyzer'
})
```

---

### 19. No Distributed Tracing
**File:** All services
**Severity:** ℹ️ LOW

**Problem:**
Cannot trace a request through gateway -> service -> tool.

**Recommendation:**
Add correlation IDs:
- Gateway assigns UUID to each request
- Pass through all hops
- Log with correlation ID at each stage

---

### 20. Config Loader File I/O Blocking Event Loop
**File:** `config_loader.py:196-214`, `config_loader.py:252-274`
**Severity:** ℹ️ LOW

**Problem:**
Config loading uses synchronous file I/O in async context:
```python
with open(path, 'r') as f:  # Blocks event loop!
    return yaml.safe_load(f)
```

**Recommendation:**
Use `aiofiles` for async file I/O or offload to thread pool:
```python
import asyncio
loop = asyncio.get_event_loop()
return await loop.run_in_executor(None, lambda: self._load_file(path))
```

---

### 21. Framework Detection Scans Too Many Files
**File:** `services/static-analyzer/main.py:264-365`
**Severity:** ℹ️ LOW

**Problem:**
```python
max_files_to_check = 20  # Still scans 20 Python files every analysis
```

**Recommendation:**
Cache framework detection results per model/app, invalidate on code changes.

---

### 22. Missing Metrics/Observability
**File:** All services
**Severity:** ℹ️ LOW

**Problem:**
No metrics exported (Prometheus, StatsD) for:
- Analysis duration by tool
- Error rates
- Queue depths
- Active connections

**Recommendation:**
Add metrics endpoint:
```python
from prometheus_client import Counter, Histogram
analysis_duration = Histogram('analysis_duration_seconds', 'Analysis duration', ['tool', 'model'])
```

---

### 23. No Graceful Shutdown Handling
**File:** `services/*/main.py`, `websocket_gateway.py`
**Severity:** ℹ️ LOW

**Problem:**
Services don't handle SIGTERM gracefully. In-flight analyses are aborted on shutdown.

**Recommendation:**
```python
async def shutdown(signal, loop):
    logger.info(f"Received exit signal {signal.name}")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)
    loop.stop()

for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda s=sig: asyncio.create_task(shutdown(s, loop)))
```

---

## Positive Observations

### What's Working Well ✅

1. **Async Architecture**: Proper use of `asyncio` throughout, avoiding blocking operations in event loops
2. **Protocol Design**: Clean separation with `shared/protocol.py` defining message types
3. **Tool Abstraction**: `BaseWSService` provides excellent reusable foundation
4. **Error Handling**: No bare `except: pass` statements found - all exceptions are logged
5. **Configuration System**: Flexible `config_loader.py` supporting multiple formats (YAML, JSON, TOML)
6. **Tool Logging**: `ToolExecutionLogger` provides comprehensive debugging capabilities
7. **SARIF Support**: Strong SARIF integration for standardized security tool output
8. **Type Hints**: Good use of type annotations for maintainability
9. **Path Resolution**: Robust path handling with `path_utils.py`
10. **Resource Limits**: WebSocket `max_size` configured to handle large SARIF responses

---

## Recommended Action Plan

### Phase 1: Critical Fixes (Week 1)
1. Implement connection pooling with semaphore limiting
2. Add task cancellation support throughout the chain
3. Implement ZAP health checking and circuit breaker
4. Fix health check task tracking

### Phase 2: High Priority (Week 2)
5. Implement hierarchical timeout propagation
6. Fix service base to allow streaming
7. Enhance error context in responses
8. Add request deduplication

### Phase 3: Medium Priority (Week 3-4)
9. Add circuit breakers for external services
10. Implement port config cache expiry
11. Add rate limiting to gateway
12. Improve SARIF processing efficiency

### Phase 4: Low Priority (Ongoing)
13. Centralize tool detection
14. Add structured logging
15. Implement distributed tracing
16. Add metrics/observability
17. Implement graceful shutdown

---

## Testing Recommendations

### Robustness Tests Needed

1. **Connection Exhaustion Test**
   ```python
   async def test_concurrent_analysis_limit():
       # Trigger 100 concurrent analyses
       # Verify system remains responsive
       # Verify no file descriptor exhaustion
   ```

2. **Cancellation Test**
   ```python
   async def test_analysis_cancellation():
       # Start long-running analysis
       # Send cancel request
       # Verify subprocess is killed
       # Verify resources are cleaned up
   ```

3. **ZAP Failure Recovery Test**
   ```python
   async def test_zap_daemon_down():
       # Stop ZAP daemon
       # Trigger dynamic analysis
       # Verify graceful error message
       # Restart ZAP, verify recovery
   ```

4. **Timeout Cascade Test**
   ```python
   async def test_timeout_propagation():
       # Set analysis timeout to 60s
       # Mock a tool that hangs for 120s
       # Verify analysis times out at 60s, not 120s
   ```

5. **Load Test**
   ```python
   async def test_sustained_load():
       # Run 50 analyses in parallel for 10 minutes
       # Monitor memory growth
       # Verify no resource leaks
   ```

---

## Conclusion

The analyzer infrastructure is well-architected with strong foundations, but needs targeted improvements to handle edge cases, high load, and failure scenarios robustly. The identified issues are fixable without major refactoring. Priority should be given to connection management, task cancellation, and timeout handling to ensure production-ready reliability.

**Overall Robustness Score: 7/10**
With recommended fixes implemented: **9/10**
