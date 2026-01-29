# Analyzer Issues Analysis & Fixes

## Issues Identified

### 1. Performance Tester: "No reachable endpoints" Error

**Root Cause:**
The analyzer pool marks endpoints as unhealthy after 3 consecutive failures and applies a 60-second cooldown period before retrying. During this cooldown, any tasks requiring that analyzer will fail with "No reachable endpoints for performance-tester".

**Location:** `src/app/services/analyzer_pool.py:357`

**Configuration:**
```python
cooldown_period: int = 60  # Seconds to wait before retrying unhealthy endpoint
max_consecutive_failures: int = 3  # Mark unhealthy after N failures
```

**When It Happens:**
- High concurrent load (multiple pipeline tasks running)
- Temporary network glitches or service delays
- WebSocket connection timeouts (2s open_timeout + 3s response timeout)
- Service restart or health check during analysis

**Impact:** Medium
- Tasks fail with error status
- Static-only fallback may be triggered
- Analysis incomplete until cooldown expires

---

### 2. Dynamic Analyzer: Occasional Health Check Failures

**Root Cause:**
Similar to performance-tester, but less frequent because dynamic-analyzer (ZAP scans) typically takes longer and has fewer concurrent requests.

**When It Happens:**
- ZAP initialization delays during startup
- Docker network latency
- Concurrent scan conflicts

**Impact:** Low
- Less frequent than performance-tester
- Usually recovers after cooldown

---

### 3. Container Build Failures (Generated Apps)

**Root Cause:**
AI-generated apps may have invalid React/frontend configurations that fail to build. This is not an analyzer issue but triggers the static-only fallback.

**Example Error:**
```
exit code: 1
target frontend: failed to solve: React build failed
```

**Impact:** Low
- Expected behavior for invalid generated apps
- Fallback to static analysis works correctly
- Not an analyzer infrastructure issue

---

## Proposed Fixes

### Fix 1: Reduce Cooldown Period (Quick Fix)

**Change:**
```python
# From:
cooldown_period: int = 60  # Seconds

# To:
cooldown_period: int = 15  # Seconds - faster recovery
```

**Benefits:**
- Faster recovery from transient failures
- Reduced task failure window
- Better user experience

**Risks:**
- Slightly more health check traffic
- May retry genuinely dead endpoints sooner

---

### Fix 2: Increase Failure Threshold (Recommended)

**Change:**
```python
# From:
max_consecutive_failures: int = 3

# To:
max_consecutive_failures: int = 5  # More tolerant of transient failures
```

**Benefits:**
- More tolerant of temporary slowdowns
- Reduces false-positive unhealthy marks
- Better for high-concurrency scenarios

---

### Fix 3: Increase Health Check Timeouts

**Change in `_check_endpoint_health`:**
```python
# From:
open_timeout=2,
timeout=3

# To:
open_timeout=5,
timeout=8
```

**Benefits:**
- More forgiving during high load
- Accounts for analyzer startup delays
- Handles Docker network latency better

**Risks:**
- Slower to detect truly dead endpoints
- Slightly longer blocking during health checks

---

### Fix 4: Implement Graceful Degradation (Advanced)

**Approach:**
Instead of immediately failing with "No reachable endpoints", implement a fallback queue:
1. Retry with exponential backoff (5s, 10s, 15s)
2. Log warning but continue waiting during cooldown
3. Only fail after N retry attempts

**Benefits:**
- Zero user-visible failures for transient issues
- Self-healing behavior
- Better UX

---

## Recommended Implementation Order

1. **Immediate (Now):**
   - Reduce cooldown_period: 60 → 20 seconds
   - Increase max_consecutive_failures: 3 → 5

2. **Short-term (This Week):**
   - Increase health check timeouts (open_timeout: 5s, timeout: 8s)
   - Add retry logic with backoff in execute_subtask

3. **Medium-term (Next Sprint):**
   - Implement task queuing during cooldown
   - Add metrics/monitoring for endpoint health
   - Dashboard alert when endpoints unhealthy > 30s

---

## Monitoring Recommendations

### Key Metrics to Track:
1. Endpoint health status per service
2. Cooldown period activations (count/hour)
3. "No reachable endpoints" errors (count/hour)
4. Average health check latency
5. Concurrent request count per endpoint

### Log Patterns to Watch:
```bash
# Find recent endpoint failures
docker logs thesisapprework-celery-worker-1 | grep "No healthy endpoints"

# Check health check failures
docker logs thesisapprework-celery-worker-1 | grep "failed health check"

# Monitor cooldown activations
docker logs thesisapprework-celery-worker-1 | grep "cooldown"
```

---

## Current Status

**Healthy:** ✓
- All analyzers running and processing tasks
- Recent logs show successful analyses
- No current endpoint failures

**Occasional Failures:**
- 1 performance-tester failure observed at 09:19:39
- Recovered automatically after cooldown
- No cascading failures

---

## Configuration Files to Modify

1. `src/app/services/analyzer_pool.py` - Lines 78-87 (AnalyzerPoolConfig)
2. `src/app/services/analyzer_pool.py` - Lines 295-299 (health check timeouts)
3. `src/app/tasks.py` - Lines 144-150 (add retry logic)

---

**Date:** 2026-01-29  
**Status:** Analysis Complete - Fixes Ready for Implementation
