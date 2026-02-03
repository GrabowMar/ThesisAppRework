# Pipeline Failure Investigation Report
**Date:** 2026-02-03
**Pipeline ID:** `pipeline_989200953cc3`
**Status:** STUCK (running for 12+ minutes in analysis stage)

---

## Executive Summary

The automation pipeline is **STUCK** in the analysis stage with 8 out of 12 analysis tasks failing due to **WebSocket connection timeouts**. The generation stage completed successfully (3 apps generated), but analysis tasks are experiencing long execution times (up to 10 minutes) that exceed retry limits, causing connections to close before results are transmitted back.

**Root Cause:** Long-running analysis tasks combined with WebSocket connection instability and event loop errors in the task execution layer.

---

## Pipeline Status

### Overall State
- **Pipeline ID:** `pipeline_989200953cc3`
- **Status:** `running` (should be `completed` or `failed`)
- **Current Stage:** `analysis`
- **Current Job Index:** 0
- **Created:** 2026-02-03 13:03:02
- **Started:** 2026-02-03 13:03:02
- **Completed:** NULL (still running after 12+ minutes)
- **Error Message:** None (pipeline hasn't detected failure yet)

### Generation Stage ✅ SUCCESS
All 3 generation jobs completed successfully:

| Job | Model | Template | App # | Status |
|-----|-------|----------|-------|--------|
| 0 | google_gemini-3-flash-preview-20251217 | api_url_shortener | 29 | ✅ SUCCESS |
| 1 | google_gemini-3-flash-preview-20251217 | api_weather_display | 30 | ✅ SUCCESS |
| 2 | google_gemini-3-flash-preview-20251217 | auth_user_login | 31 | ✅ SUCCESS |

### Analysis Stage ⚠️ PARTIAL FAILURE
- **Total Tasks:** 12 (3 apps × 4 analyzers)
- **Completed:** 4 (33%)
- **Failed:** 8 (67%)
- **Status:** `in_progress` (stuck waiting for failed tasks)

---

## Detailed Analysis Task Results

### App 29 (api_url_shortener)
| Analyzer | Task ID | Status | Error |
|----------|---------|--------|-------|
| static-analyzer | task_5975dbb89982 | ✅ COMPLETED | - |
| dynamic-analyzer | task_b2c5de9e57fd | ❌ FAILED | "Failed to complete request to static-analyzer after 3 attempts" |
| performance-tester | task_db9b4c501e71 | ❌ FAILED | "Failed to complete request to performance-tester after 3 attempts" |
| ai-analyzer | task_4b531100c33f | ✅ COMPLETED | - |

### App 30 (api_weather_display)
| Analyzer | Task ID | Status | Error |
|----------|---------|--------|-------|
| static-analyzer | task_7a48df36b438 | ❌ FAILED | "Analysis service temporarily unavailable - event loop error" |
| dynamic-analyzer | task_b60bf2e7294c | ❌ FAILED | "Analysis service temporarily unavailable - event loop error" |
| performance-tester | task_abbaeaff03c9 | ❌ FAILED | "Analysis service temporarily unavailable - event loop error" |
| ai-analyzer | task_219a0a99307d | ❌ FAILED | "Analysis service temporarily unavailable - event loop error" |

### App 31 (auth_user_login)
| Analyzer | Task ID | Status | Error |
|----------|---------|--------|-------|
| static-analyzer | task_2ac828a8f691 | ✅ COMPLETED | - |
| dynamic-analyzer | task_d18b6709d4d0 | ❌ FAILED | "No response from service" |
| performance-tester | task_e9d5bb696445 | ✅ COMPLETED | - |
| ai-analyzer | task_3ba355ee4983 | ✅ COMPLETED | - |

---

## Root Cause Analysis

### 1. WebSocket Connection Timeouts ⚠️

**Evidence from Celery Logs:**
```
[13:10:49] ERROR/ForkPoolWorker-11 Pooled request to performance-tester failed:
           Failed to complete request to performance-tester after 3 attempts

[13:13:16] ERROR/ForkPoolWorker-5 Pooled request to static-analyzer failed:
           Failed to complete request to static-analyzer after 3 attempts

[13:15:25] ERROR/ForkPoolWorker-6 Pooled request to dynamic-analyzer failed:
           Failed to complete request to dynamic-analyzer after 3 attempts
```

**Analysis:**
- Tasks are taking 325-601 seconds (5-10 minutes) to execute
- WebSocket connections are closing before results are transmitted
- Retry mechanism exhausts all 3 attempts before giving up
- Connection closes with: "Connection closed before result received"

**Current Timeout Configuration (`analyzer_pool.py`):**
```python
request_timeout: int = 600       # 10 minutes
message_timeout: int = 600       # 10 minutes
connection_timeout: int = 10     # 10 seconds
ping_timeout: int = 10           # 10 seconds
max_retries: int = 3             # 3 attempts
```

### 2. Event Loop Errors 🔴

**All 4 tasks for App 30 failed with:**
```
"Analysis service temporarily unavailable - event loop error"
```

**Possible Causes:**
- Asyncio event loop conflicts in the Celery worker
- Race condition when multiple tasks access the same event loop
- Event loop closed prematurely before tasks complete
- Threading issues between Celery's prefork workers and asyncio

### 3. Long-Running Analysis Tasks ⏱️

**Execution Times (from Celery logs):**
- Task 28 (static): 471.77 seconds (~8 minutes)
- Task 30 (performance): 325.06 seconds (~5 minutes)
- Task 29 (dynamic): 601.42 seconds (~10 minutes)

**Why So Long?**
- **Static Analysis:** Running 14 tools (bandit, pylint, semgrep, mypy, safety, pip-audit, vulture, ruff, radon, detect-secrets, eslint, npm-audit, stylelint, html-validator)
- **Dynamic Analysis:** OWASP ZAP security scans take 8-10 minutes per app
- **Performance Testing:** Load testing with multiple tools (locust, ab, aiohttp)

### 4. Pipeline Service Not Detecting Failures 🐛

**Issue:**
- Pipeline status is still `running` after 12+ minutes
- Should have transitioned to `partial_success` or `failed`
- Pipeline service is not checking task status frequently enough

**Evidence from Web Container Logs:**
```
[13:05:24] INFO Pipeline execution service disabled (ENABLE_PIPELINE_SERVICE=false)
```

**Critical Configuration Issue:**
- Pipeline service is **DISABLED** in the web container
- Only enabled in celery-worker container
- Web container can't monitor or update pipeline status

---

## Infrastructure Health Check

### Docker Services Status ✅ ALL HEALTHY

| Service | Replicas | Status | Ports |
|---------|----------|--------|-------|
| static-analyzer | 4 | 🟢 Healthy | 2001, 2051, 2052, 2056 |
| dynamic-analyzer | 3 | 🟢 Healthy | 2002, 2053, 2057 |
| performance-tester | 2 | 🟢 Healthy | 2003, 2054 |
| ai-analyzer | 2 | 🟢 Healthy | 2004, 2055 |
| analyzer-gateway | 1 | 🟢 Healthy | 8765 |
| web | 1 | 🟢 Healthy | 5000 |
| celery-worker | 1 | 🟢 Healthy | - |
| redis | 1 | 🟢 Healthy | 6379 |
| nginx | 1 | 🟢 Healthy | 80, 443 |

### Analyzer Resource Usage 📊

All analyzers have normal CPU/memory usage:
- Static analyzers: 60-65 MiB / 1 GiB (6%), 0% CPU
- Dynamic analyzers: 444-497 MiB / 1 GiB (44-49%), 0.26-5.10% CPU
- AI analyzers: 34-35 MiB / 2 GiB (1.7%), 0% CPU
- Gateway: 177 MiB / 256 MiB (69%), 0% CPU

**No resource exhaustion detected.**

### Analyzer Logs Show Successful Execution ✅

**Example from static-analyzer-3:**
```
INFO:static-analyzer:✅ STATIC ANALYSIS COMPLETE
   📊 Total Issues: 167
   🔧 Tools Run: 14
   📝 Tools Used: bandit, pylint, semgrep, mypy, safety, pip-audit,
                  vulture, ruff, radon, detect-secrets, eslint,
                  npm-audit, stylelint, html-validator
Static analysis completed for google_gemini-3-flash-preview-20251217 app 29
```

**The analyzers ARE working correctly** - the issue is in the communication layer.

---

## Why Pipeline Is Stuck

### Failure Propagation Issue

1. **Analysis tasks fail** due to WebSocket timeouts/event loop errors
2. **Task status updates** to `failed` in database
3. **Pipeline service should detect** failed tasks and transition pipeline to `partial_success`
4. **But pipeline service is disabled** in web container (ENABLE_PIPELINE_SERVICE=false)
5. **Celery worker's pipeline service** should be handling it, but appears to be stuck

### Celery Worker Pipeline Logs

Repeated logging every 3 seconds:
```
[13:12:30] INFO [pipeline_989200953cc3:ANAL] Streaming mode=True, gen_mode=generate
[13:12:33] INFO [pipeline_989200953cc3:ANAL] Streaming mode=True, gen_mode=generate
[13:12:36] INFO [pipeline_989200953cc3:ANAL] Streaming mode=True, gen_mode=generate
...
(repeats for 10+ minutes)
```

**This indicates:**
- Pipeline execution service IS running in celery-worker
- But it's in a loop without detecting task failures
- Possibly waiting for streaming results that never arrive
- Or checking wrong task status fields

---

## Immediate Actions Required

### 1. Manually Update Pipeline Status 🛠️

```sql
UPDATE pipeline_executions
SET status = 'partial_success',
    current_stage = 'completed',
    completed_at = datetime('now'),
    error_message = 'Analysis stage partially completed: 4/12 tasks succeeded, 8/12 tasks failed due to WebSocket timeout and event loop errors'
WHERE pipeline_id = 'pipeline_989200953cc3';
```

### 2. Increase WebSocket Timeouts ⏱️

Edit `src/app/services/analyzer_pool.py`:
```python
@dataclass
class AnalyzerPoolConfig:
    request_timeout: int = 900      # Increase to 15 minutes (was 10)
    message_timeout: int = 900      # Increase to 15 minutes (was 10)
    max_retries: int = 5            # Increase to 5 attempts (was 3)
    max_consecutive_failures: int = 10  # More tolerance (was 5)
```

### 3. Fix Event Loop Errors 🔧

**Option A: Use ThreadPoolExecutor for Celery Tasks**
```python
# In celery_worker.py or task execution
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

@shared_task
def execute_analysis_task(task_id):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(async_analysis_function(task_id))
        return result
    finally:
        loop.close()
```

**Option B: Use Celery Worker Pool Type**
```bash
# In docker-compose.yml celery-worker command:
celery -A app.celery_worker.celery worker --pool=solo --loglevel=info
```

### 4. Improve Pipeline Monitoring 📊

Add timeout detection in `pipeline_execution_service.py`:
```python
# Check if pipeline has been running too long
if pipeline.status == 'running':
    elapsed = datetime.now(timezone.utc) - pipeline.started_at
    if elapsed.total_seconds() > 1800:  # 30 minutes
        logger.warning(f"Pipeline {pipeline.pipeline_id} running for {elapsed.total_seconds()}s - checking for stuck state")
        # Check if all tasks are complete/failed
        all_done = check_all_tasks_complete(pipeline)
        if all_done:
            finalize_pipeline(pipeline)
```

### 5. Add Circuit Breaker for Failed Analyzers ⚡

Temporarily disable analyzers that repeatedly fail:
```python
if endpoint.consecutive_failures >= 3:
    logger.warning(f"Circuit breaker: {endpoint.service_name} has {endpoint.consecutive_failures} consecutive failures")
    endpoint.is_healthy = False
    # Try next replica instead of retrying same one
```

---

## Long-Term Recommendations

### 1. Implement Progress Streaming 📡

Instead of waiting for complete result:
- Analyzers send progress updates every 30 seconds
- Pipeline tracks partial progress
- Detect stalled tasks earlier
- Resume from last checkpoint on failure

### 2. Split Long-Running Analyses 🔀

Break monolithic analysis into smaller chunks:
- **Quick scan** (30 seconds): Basic security + linting
- **Standard scan** (2 minutes): + performance testing
- **Deep scan** (10 minutes): + ZAP + comprehensive tools

### 3. Implement Task Timeouts at Multiple Levels ⏲️

- **WebSocket timeout:** 15 minutes (increased)
- **Task execution timeout:** 20 minutes (Celery soft_time_limit)
- **Pipeline stage timeout:** 30 minutes (force completion)

### 4. Add Dead Letter Queue 📮

Failed tasks go to DLQ for retry:
- Preserve task context
- Retry with increased timeout
- Alert operator after 3 DLQ failures

### 5. Improve Error Handling 🚨

Better error messages:
```python
if isinstance(error, asyncio.TimeoutError):
    return {
        'status': 'timeout',
        'error': f'Analysis exceeded {timeout}s timeout',
        'suggestion': 'Consider using fewer tools or increasing timeout',
        'partial_results': collected_results
    }
```

---

## Verification Steps

After implementing fixes, verify:

```bash
# 1. Check pipeline status
docker exec thesisapprework-web-1 python -c "
from app import create_app
from app.models import PipelineExecution
app = create_app()
with app.app_context():
    p = PipelineExecution.query.filter_by(pipeline_id='pipeline_989200953cc3').first()
    print(f'Status: {p.status}')
"

# 2. Start new test pipeline with reduced tool set
curl -X POST http://localhost:5000/automation/api/pipeline/start \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "generation": {
      "mode": "generate",
      "models": ["google_gemini-3-flash-preview-20251217"],
      "templates": ["api_url_shortener"]
    },
    "analysis": {
      "enabled": true,
      "tools": ["bandit", "eslint", "curl"],
      "options": {"parallel": false}
    }
  }'

# 3. Monitor Celery worker logs
docker logs -f thesisapprework-celery-worker-1

# 4. Check analyzer pool health
docker exec thesisapprework-web-1 python -c "
from app.services.analyzer_pool import AnalyzerPool
import asyncio
pool = AnalyzerPool()
asyncio.run(pool.initialize())
print('Pool initialized successfully')
"
```

---

## Files to Review/Edit

1. **`src/app/services/analyzer_pool.py`** - Increase timeouts, add circuit breaker
2. **`src/app/services/pipeline_execution_service.py`** - Add stuck detection, improve error handling
3. **`src/app/services/task_execution_service.py`** - Fix event loop issues
4. **`docker-compose.yml`** - Consider using `--pool=solo` for celery-worker
5. **`src/app/models/pipeline.py`** - Add timeout fields

---

## Summary

**The pipeline failed due to a perfect storm of issues:**

1. ❌ WebSocket connections timing out on long-running analyses (8-10 min)
2. ❌ Event loop errors causing batch task failures (app 30)
3. ❌ Retry mechanism exhausting attempts before success
4. ❌ Pipeline service not detecting failures fast enough
5. ❌ No circuit breaker to skip failing analyzers

**But the good news:**

✅ All infrastructure is healthy
✅ Analyzers ARE completing work successfully
✅ Generation stage works perfectly
✅ 33% of analysis tasks succeeded

**The communication layer needs hardening, not the analyzers themselves.**

---

## Conclusion

This is a **solvable architectural issue**, not a fundamental flaw. With the recommended timeout increases, event loop fixes, and better error handling, the pipeline should be reliable for production use.

**Estimated Fix Time:** 2-3 hours
**Priority:** HIGH (blocks automation workflows)
**Difficulty:** MEDIUM (requires careful async/threading changes)
