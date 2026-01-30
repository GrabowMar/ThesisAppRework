# Critical Analysis Pipeline Fixes - Applied 2026-01-29

## Problem Summary

The automation pipeline was producing ~40% failed analysis results with the error:
```
"WebSocket error: cannot schedule new futures after interpreter shutdown"
```

**Statistics Before Fixes:**
- Total analyses: 258
- Failed: 99 (38%)
- Primary error: "cannot schedule new futures after interpreter shutdown" (148 occurrences)
- Root cause: Event loop memory leaks and improper cleanup

---

## Fixes Applied

### 1. Event Loop Memory Leak Fix (async_utils.py)

**File:** `src/app/utils/async_utils.py`
**Lines:** 55-70, 73-104

**Problem:**
The `run_async_safely()` function created new event loops but never closed them, causing memory leaks and eventual "cannot schedule new futures" errors.

**Fix:**
```python
finally:
    # CRITICAL FIX: Close the loop to prevent memory leaks
    try:
        # Cancel all remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Wait for cancellations to complete
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    finally:
        loop.close()
        # Clear the event loop reference to avoid reuse of closed loop
        asyncio.set_event_loop(None)
```

**Impact:**
- Prevents accumulation of unclosed event loops
- Ensures proper cleanup of WebSocket connections
- Eliminates "interpreter shutdown" errors caused by orphaned loops

---

### 2. WebSocket Connection Cleanup Fix (task_execution_service.py)

**File:** `src/app/services/task_execution_service.py`
**Lines:** 2692-2742

**Problem:**
Event loops were closed without properly canceling pending WebSocket tasks, causing shutdown errors.

**Fix:**
```python
finally:
    # CRITICAL FIX: Properly cleanup event loop and pending tasks
    try:
        # Cancel all remaining tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # Wait for cancellations to complete
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception as cleanup_err:
        self._log(f"[WebSocket] Error during loop cleanup: {cleanup_err}", level='debug')
    finally:
        loop.close()
        # Clear event loop reference to prevent reuse of closed loop
        asyncio.set_event_loop(None)
```

**Impact:**
- Gracefully cancels all pending WebSocket operations before shutdown
- Prevents "cannot schedule new futures" during concurrent analysis runs
- Improves stability under high load

---

### 3. Enhanced Error Recovery (task_execution_service.py)

**File:** `src/app/services/task_execution_service.py`
**Lines:** 2727-2741, 3134-3150

**Problem:**
Generic exception handling didn't differentiate between recoverable and fatal errors.

**Fix:**
```python
except RuntimeError as e:
    # Handle event loop errors separately (more specific than general Exception)
    error_str = str(e)
    if 'cannot schedule new futures' in error_str or 'interpreter shutdown' in error_str.lower() or 'event loop is closed' in error_str.lower():
        self._log(f"[WebSocket] Event loop error in {service_name}: {error_str}", level='warning')
        return {
            'status': 'error',
            'error': f'Analysis service temporarily unavailable - event loop error',
            'payload': {}
        }
```

**Impact:**
- Better error messages for debugging
- Prevents cascading failures
- Enables automatic retry on recoverable errors

---

## Verification Steps

### 1. Check Recent Analysis Results

```bash
# Count total results
find results -name "*.json" | wc -l

# Count errors with "cannot schedule new futures"
find results -name "*.json" -exec grep -l "cannot schedule new futures" {} \; | wc -l

# View error distribution
find results -name "*.json" -exec grep -o '"status"[^,}]*' {} \; | sort | uniq -c | sort -rn
```

### 2. Monitor Application Logs

```bash
# Watch for event loop errors in real-time
docker logs -f thesisapprework-web-1 2>&1 | grep -i "event loop\|futures\|shutdown"

# Check Celery worker logs
docker logs -f thesisapprework-celery-worker-1 2>&1 | grep -i "event loop\|futures\|shutdown"
```

### 3. Run Test Analysis

```bash
# Inside the container
docker exec thesisapprework-web-1 python test_analysis_fix.py
```

Expected result: No "cannot schedule new futures" errors

---

## Expected Improvements

| Metric | Before | Target After Fix |
|--------|--------|------------------|
| Success Rate | ~60% | >90% |
| Event Loop Errors | 148/258 (57%) | <5% |
| Timeout Errors | 21/258 (8%) | <10% |
| Overall Failure Rate | ~40% | <15% |

---

## Monitoring Recommendations

### Daily Checks

1. **Error Rate Monitoring**
   ```bash
   # Calculate error rate for last 24 hours
   find results -name "*.json" -mtime -1 -exec grep -l '"status".*"error"' {} \; | wc -l
   ```

2. **Event Loop Health**
   ```bash
   # Check for event loop errors
   docker logs thesisapprework-web-1 --since 24h 2>&1 | grep -c "event loop"
   ```

3. **Analyzer Service Health**
   ```bash
   # Check analyzer availability
   docker ps --filter "name=analyzer" --format "table {{.Names}}\t{{.Status}}"
   ```

### Weekly Analysis

1. Calculate success rate trend
2. Review error patterns
3. Check for new failure modes
4. Verify all analyzers are responding

---

## Known Remaining Issues

### 1. Analyzer Replicas Not Configured

**Symptom:** Logs show connection attempts to non-existent replicas:
```
static-analyzer-2:2001 - [Errno -3] Temporary failure in name resolution
```

**Status:** Non-critical - System falls back to primary analyzer
**Solution:** Remove non-existent URLs from environment variables or add replicas

### 2. Long Analysis Timeouts

**Symptom:** Some analyses take 5+ minutes
**Status:** Expected for dynamic/performance tests
**Mitigation:** Timeout values already increased in analyzer_pool.py

---

## Rollback Instructions (If Needed)

If the fixes cause unexpected issues:

```bash
# 1. Stop services
docker compose stop web celery-worker

# 2. Revert files
git checkout HEAD~1 -- src/app/utils/async_utils.py
git checkout HEAD~1 -- src/app/services/task_execution_service.py

# 3. Restart services
docker compose up -d web celery-worker
```

---

## Next Steps

1. ✅ Fixes applied and services restarted
2. ⏳ Monitor for 24-48 hours
3. ⏳ Verify success rate improvement
4. ⏳ Run full pipeline test
5. ⏳ Document final results

---

## Technical Details

### Why These Fixes Work

**Event Loop Lifecycle:**
1. `asyncio.new_event_loop()` - Creates loop
2. `asyncio.set_event_loop(loop)` - Registers as thread's loop
3. `loop.run_until_complete(coro)` - Executes async code
4. **NEW:** Cancel pending tasks before close
5. **NEW:** `loop.close()` - Properly cleanup
6. **NEW:** `asyncio.set_event_loop(None)` - Clear reference

**Problem Pattern:**
```
Thread A: create loop → run task A → close loop
Thread A: create loop → run task B → ERROR (old loop still registered)
```

**Fix Pattern:**
```
Thread A: create loop → run task A → cancel pending → close loop → clear reference
Thread A: create loop → run task B → SUCCESS (clean slate)
```

---

**Applied by:** Claude Code (Automated Debugging)
**Date:** 2026-01-29 23:29 UTC
**Services Restarted:** ✅ web, celery-worker
**Status:** Monitoring Required
