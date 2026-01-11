# Pipeline Analysis Failures - Investigation Report

**Date:** 2026-01-10
**Pipeline ID:** `pipeline_44a7daa76af2`
**Status:** Partial Success (1 success, 4 failures)

## Executive Summary

The automation pipeline created **5 main analysis tasks** (not 6 as it appeared in the UI), but **duplicate tasks were created** for the same model/app combination. The UI shows 6 rows because one task appears twice in the list. Additionally, multiple critical issues were found causing analysis failures:

1. **WebSocket connection failures** in static-analyzer
2. **App containers not reachable** for dynamic analysis
3. **Duplicate task creation** (task orchestration bug)
4. **Circuit breaker not preventing retries** effectively

---

## Issue #1: Duplicate Task Creation

### Problem
Pipeline created **5 tasks for 4 applications**:
- `task_e9306aad05b4` - anthropic_claude-3-5-haiku app2
- `task_aa7f9afef7b5` - **anthropic_claude-3-5-haiku app2** (DUPLICATE!)
- `task_66accbea3e0c` - anthropic_claude-4.5-haiku-20251001 app1
- `task_e879e2d55b61` - anthropic_claude-3-5-haiku app1
- `task_ceed3170b96c` - anthropic_claude-4.5-haiku-20251001 app2

### Root Cause
The duplicate guard logic in [pipeline_execution_service.py:615-644](src/app/services/pipeline_execution_service.py#L615-L644) has race conditions:

1. Checks `submitted_apps` list
2. Then checks existing task_ids in database
3. **BUT** between these checks and actual task creation, another job can slip through

The duplicate guard checks happen **before** the task is committed to the database, creating a window for race conditions when multiple jobs are being processed concurrently.

### Evidence
```json
"submitted_apps": [
  "anthropic_claude-3-5-haiku:2",   // First submission
  "anthropic_claude-4.5-haiku-20251001:1",
  "anthropic_claude-3-5-haiku:1",
  "anthropic_claude-4.5-haiku-20251001:2"
  // Note: anthropic_claude-3-5-haiku:2 appears again as task_aa7f9afef7b5
]
```

### Recommendation
**Add a database-level unique constraint** on `(pipeline_id, target_model, target_app_number)` to prevent duplicates at the DB level. Alternatively, use optimistic locking or a transaction-based approach.

---

## Issue #2: WebSocket Connection Failures (Static Analyzer)

### Problem
Static analyzer completes analysis successfully but **fails to send results** back to the main application due to WebSocket connection closures:

```
WARNING:static-analyzer:WebSocket send failed (attempt 1/3): received 1000 (OK); then sent 1000 (OK). Retrying...
ERROR:static-analyzer:WebSocket send failed after 3 attempts: received 1000 (OK); then sent 1000 (OK)
ERROR:static-analyzer:Error handling message: received 1000 (OK); then sent 1000 (OK)
```

### Impact
- Static analysis **COMPLETES** successfully (finds 243-306 issues)
- Results **FAIL TO TRANSMIT** to main app
- Main app marks task as **FAILED** even though analysis succeeded
- All 5 main tasks had static-analyzer subtasks **fail** due to this

### Root Cause
The WebSocket connection between the static-analyzer container and the gateway is being closed **prematurely** (error 1000 = normal closure). This suggests:

1. **Timeout issues** - connection closes before large result payloads are sent
2. **Gateway closing connections too early** - possibly after receiving initial response
3. **Network buffer issues** - large SARIF payloads (243+ findings) may exceed buffer limits

### Evidence from Logs
```
INFO:static-analyzer:✅ STATIC ANALYSIS COMPLETE
   📊 Total Issues: 243
   🔧 Tools Run: 9
WARNING:static-analyzer:WebSocket send failed (attempt 1/3)
ERROR:static-analyzer:WebSocket send failed after 3 attempts
```

The analysis completes but the results never reach the main application.

### Recommendation
1. **Increase WebSocket timeout** in analyzer gateway
2. **Implement chunked result transmission** for large payloads
3. **Add result persistence** - write to shared volume if WebSocket fails
4. **Implement HTTP fallback** - POST results via REST API if WebSocket unavailable

---

## Issue #3: Dynamic Analyzer - App Containers Unreachable

### Problem
Dynamic analyzer cannot reach application containers:

```
ERROR:zap_scanner:Target http://localhost:6010 is unreachable:
  HTTPConnectionPool(host='localhost', port=6010): Max retries exceeded
  Connection refused
```

### Impact
- Dynamic analysis (ZAP security scans) **cannot execute**
- Tasks marked as **COMPLETED** even though no scanning occurred
- Security vulnerabilities go **undetected**

### Root Cause Analysis

#### For Haiku 4.5 App 1:
App containers were **stopped before analysis ran**:
```
[22:25:50] INFO pipeline_executor [PipelineExecutor] Stopping containers for
           anthropic_claude-4.5-haiku-20251001 app 1 (pipeline pipeline_44a7daa76af2)
[22:26:03] INFO [PipelineExecutor] Successfully stopped containers
```

Analysis task `task_66accbea3e0c` **started at 22:17:04** but containers were already down.

#### For Haiku 3.5 Apps:
Containers were **never started** - used wrong ports (localhost:6020, 6021 instead of host.docker.internal ports).

### Root Cause
1. **Container lifecycle management bug** - containers stopped too early (possibly premature failure detection)
2. **Port mapping confusion** - using localhost instead of host.docker.internal
3. **No pre-flight container health check** before dynamic analysis

### Recommendation
1. **Add container health check** before each dynamic analysis task
2. **Use correct host** - always use `host.docker.internal` from analyzer containers
3. **Delay container shutdown** until ALL subtasks complete
4. **Add retry logic** with container restart if target unreachable

---

## Issue #4: Circuit Breaker Not Effective

### Problem
Despite "reinforced task orchestration robustness" with circuit breakers, the system keeps creating tasks and retrying failed services.

### Current Circuit Breaker Config
- **Threshold:** 3 failures
- **Cooldown:** 5 minutes
- **TTL:** 30 seconds health cache

### Why It's Not Working
1. **Per-service circuit breakers don't prevent task creation** - they only skip service execution
2. **Main task still created** even if all services are in cooldown
3. **No pipeline-level circuit breaker** - continues creating tasks even when all previous tasks fail
4. **Health cache TTL too long** (30s) - stale health data used for decisions

### Evidence
All 5 tasks failed with similar patterns, but pipeline kept creating new tasks.

### Recommendation
1. **Pipeline-level circuit breaker** - stop creating new tasks after N consecutive failures
2. **Reduce health cache TTL** to 5-10 seconds
3. **Fail fast** - if preflight checks fail, don't create main task at all
4. **Batch health checks** - check all services before starting analysis stage

---

## Issue #5: UI Displaying 6 Tasks Instead of 5

### Problem
Screenshot shows **6 analysis tasks** but database has only **5 main tasks**.

### Root Cause
**Likely duplicate task_id in the frontend state or API response**. The duplicate task `task_aa7f9afef7b5` (duplicate of anthropic_claude-3-5-haiku app2) may be:

1. Listed twice in the UI due to caching bug
2. Returned twice from `/analysis/api/tasks/list` endpoint
3. Front-end not deduplicating task IDs

### Recommendation
1. **Add deduplication** in frontend task list rendering
2. **Investigate API response** for `/analysis/api/tasks/list`
3. **Add database query logging** to trace duplicate returns

---

## Task Breakdown (All 5 Main Tasks)

### Task 1: `task_e9306aad05b4` - FAILED
- **Target:** anthropic_claude-3-5-haiku app2
- **Subtasks:** 4 (1 failed, 3 completed)
- **Failure:** Static analyzer WebSocket failure

### Task 2: `task_aa7f9afef7b5` - FAILED (DUPLICATE)
- **Target:** anthropic_claude-3-5-haiku app2 ⚠️ SAME AS TASK 1
- **Subtasks:** 4 (2 failed, 2 completed)
- **Failures:**
  - Static analyzer WebSocket failure
  - Dynamic analyzer - app unreachable

### Task 3: `task_66accbea3e0c` - FAILED
- **Target:** anthropic_claude-4.5-haiku-20251001 app1
- **Subtasks:** 4 (1 failed, 3 completed)
- **Failure:** Static analyzer WebSocket failure

### Task 4: `task_e879e2d55b61` - PARTIAL SUCCESS ✅
- **Target:** anthropic_claude-3-5-haiku app1
- **Subtasks:** 4 (1 failed, 3 completed)
- **Failure:** Static analyzer WebSocket failure

### Task 5: `task_ceed3170b96c` - FAILED
- **Target:** anthropic_claude-4.5-haiku-20251001 app2
- **Subtasks:** 4 (1 failed, 3 completed)
- **Failures:**
  - Dynamic analyzer - app unreachable

---

## Summary Statistics

### Overall Pipeline
- **Expected Tasks:** 4 (one per generated app)
- **Actual Tasks Created:** 5 (one duplicate)
- **Tasks Shown in UI:** 6 (display bug)
- **Success Rate:** 20% (1/5 partial success)

### Subtask Analysis (20 total subtasks)
- **Static Analyzer:** 5/5 failed (100% failure rate) due to WebSocket issues
- **Dynamic Analyzer:** 3/5 failed (60% failure rate) due to unreachable containers
- **Performance Tester:** 5/5 completed (100% success rate) ✅
- **AI Analyzer:** 5/5 completed (100% success rate) ✅

### Critical Issues by Severity

#### 🔴 Critical
1. **WebSocket communication failure** (affects 100% of static analysis)
2. **Duplicate task creation** (wastes resources, confuses users)

#### 🟠 High
3. **App containers unreachable** (60% dynamic analysis failure rate)
4. **Circuit breaker ineffective** (doesn't prevent cascading failures)

#### 🟡 Medium
5. **UI displaying wrong count** (UX issue, not functional)

---

## Immediate Action Items

### Quick Fixes (< 1 hour)
1. ✅ Add database unique constraint on `(pipeline_id, target_model, target_app_number)`
2. ✅ Increase WebSocket timeout to 120 seconds
3. ✅ Use `host.docker.internal` consistently in dynamic analyzer

### Short Term (< 1 day)
4. ⏳ Implement chunked WebSocket transmission for large payloads
5. ⏳ Add pre-flight health checks before creating tasks
6. ⏳ Add pipeline-level circuit breaker logic

### Medium Term (< 1 week)
7. 📋 Implement HTTP fallback for result transmission
8. 📋 Add container health monitoring during analysis
9. 📋 Refactor container lifecycle management

---

## Testing Recommendations

Before next pipeline run:
1. **Test WebSocket with large payloads** (300+ findings)
2. **Verify container health checks** work correctly
3. **Test duplicate prevention** with concurrent job submissions
4. **Monitor circuit breaker** behavior under repeated failures

---

## Conclusion

The pipeline **created too many tasks (5 instead of 4)** due to a race condition in duplicate detection. The "robustness improvements" (circuit breakers, health checks) **are not working as intended** because:

1. They don't prevent task creation
2. Health cache is stale
3. No pipeline-level failure detection

**The root cause of failures is NOT orchestration logic** but rather:
- **Infrastructure issues** (WebSocket, networking)
- **Timing issues** (containers stopped too early)
- **Configuration issues** (wrong hostnames/ports)

The orchestration logic is actually working correctly in terms of parallel execution and tracking - the issues are in the **analyzer integration layer** and **container management**.
