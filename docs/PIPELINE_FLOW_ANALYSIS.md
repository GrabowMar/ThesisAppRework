# Pipeline Flow Analysis & Design Review

## Overview

This document analyzes the pipeline execution flow, identifies design issues, and proposes improvements.

## Pipeline Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          PIPELINE EXECUTION SERVICE                              │
│                           (Background Thread Loop)                               │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Poll Database for Running Pipelines (every 3 seconds)                          │
│  SELECT * FROM pipeline_executions WHERE status = 'running'                      │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
        ┌─────────────────────┐              ┌─────────────────────┐
        │  GENERATION STAGE   │              │   ANALYSIS STAGE    │
        │  current_stage=     │              │  current_stage=     │
        │  'generation'       │              │   'analysis'        │
        └─────────────────────┘              └─────────────────────┘
                    │                                   │
                    ▼                                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        GENERATION STAGE FLOW                                     │
│─────────────────────────────────────────────────────────────────────────────────│
│                                                                                  │
│  1. Check completed in-flight jobs (ThreadPoolExecutor futures)                  │
│                                                                                  │
│  2. Submit new jobs up to max_concurrent (default: 2)                            │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  for each available slot:                                          │      │
│     │    ├─ get_next_job() → {model_slug, template_slug, job_index}     │      │
│     │    ├─ Check duplicate: job_key in in_flight_generation?           │      │
│     │    ├─ Check completed: job_index in results?                       │      │
│     │    ├─ advance_job_index() + COMMIT ← Race fix #1                   │      │
│     │    └─ _submit_generation_job(pipeline_id, job)                    │      │
│     │          └─ ThreadPoolExecutor.submit(_execute_generation_job)    │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  3. INSIDE _execute_generation_job (Worker Thread):                              │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  ├─ Push Flask app_context                                         │      │
│     │  ├─ get_generation_service().generate_full_app(...)                │      │
│     │  │      └─ _reserve_app_number() ← SELECT FOR UPDATE + retry       │      │
│     │  │             └─ Race fix #2: Atomic app_number allocation        │      │
│     │  └─ Return result: {success, app_number, error}                   │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  4. _record_generation_result() → pipeline.add_generation_result(record)         │
│     ├─ Appends to progress['generation']['results']                              │
│     ├─ Increments completed/failed counters                                      │
│     └─ Triggers stage transition when done >= total                              │
│                                                                                  │
│  5. Stage Transition: generation → analysis                                      │
│     ├─ Reset current_job_index = 0                                               │
│     └─ Set current_stage = 'analysis'                                            │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         ANALYSIS STAGE FLOW                                      │
│─────────────────────────────────────────────────────────────────────────────────│
│                                                                                  │
│  1. Start analyzer containers (first time only)                                  │
│     ├─ Check: pipeline_id in _containers_started_for?                           │
│     ├─ _ensure_analyzers_healthy() with retry                                   │
│     └─ Mark: _containers_started_for.add(pipeline_id)                           │
│                                                                                  │
│  2. Check completed in-flight tasks                                              │
│     └─ _check_completed_analysis_tasks(pipeline)                                │
│                                                                                  │
│  3. Submit new tasks up to max_concurrent (default: 3)                           │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  for each available slot:                                          │      │
│     │    ├─ get_next_job() → {model_slug, app_number, success}          │      │
│     │    ├─ advance_job_index() + COMMIT ← Race fix #3                   │      │
│     │    ├─ Skip if job.success == False (gen failed)                   │      │
│     │    ├─ Duplicate check #1: job_key in submitted_apps?              │      │
│     │    ├─ Duplicate check #2: task exists for model:app?              │      │
│     │    └─ _submit_analysis_task(pipeline, job) ←─────────────────┐    │      │
│     └───────────────────────────────────────────────────────────────│────┘      │
│                                                                      │           │
│  4. INSIDE _submit_analysis_task:                                    │           │
│     ┌────────────────────────────────────────────────────────────────┴───┐      │
│     │  ├─ SELECT FOR UPDATE on PipelineExecution ← Race fix #4           │      │
│     │  ├─ Duplicate check: submitted_apps + existing_task_ids            │      │
│     │  ├─ Validate app exists: _validate_app_exists()                   │      │
│     │  ├─ Start app containers: _start_app_containers()                 │      │
│     │  ├─ AnalysisTaskService.create_main_task_with_subtasks(...)       │      │
│     │  │      └─ Creates: 1 MAIN task + N SUBTASKS (per service)        │      │
│     │  ├─ Query subtask IDs                                              │      │
│     │  └─ pipeline.add_analysis_task_id(task_id, ...,                   │      │
│     │         is_main_task=True, subtask_ids=[...])                      │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  5. Task tracking structure:                                                     │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  progress['analysis'] = {                                          │      │
│     │      'main_task_ids': ['task_123', 'task_456'],  # Main tasks      │      │
│     │      'subtask_ids': ['sub_1', 'sub_2', ...],     # Tool subtasks   │      │
│     │      'task_ids': ['task_123', 'task_456'],       # Legacy compat   │      │
│     │      'submitted_apps': ['model_a:1', 'model_b:2'] # Duplicate key  │      │
│     │  }                                                                 │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  6. _check_analysis_tasks_completion():                                          │
│     ├─ Use main_task_ids (NOT subtask_ids) for completion counting              │
│     ├─ Query each main task's status from DB                                    │
│     ├─ Count: COMPLETED/PARTIAL_SUCCESS → completed_count                        │
│     ├─ Count: FAILED/CANCELLED → failed_count                                   │
│     └─ When all terminal → pipeline.update_analysis_completion()                │
│                                                                                  │
│  7. Cleanup:                                                                     │
│     ├─ Stop app containers: _stop_all_app_containers_for_pipeline()             │
│     └─ Stop analyzer containers: _cleanup_pipeline_containers()                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Task Creation Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    TASK SERVICE: create_main_task_with_subtasks                  │
│─────────────────────────────────────────────────────────────────────────────────│
│                                                                                  │
│  Input: model_slug, app_number, tools=['semgrep', 'bandit', 'zap']              │
│                                                                                  │
│  1. Group tools by service container:                                            │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  tools_by_service = {                                              │      │
│     │      'static-analyzer': ['semgrep', 'bandit'],                     │      │
│     │      'dynamic-analyzer': ['zap']                                   │      │
│     │  }                                                                 │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  2. Create MAIN task (status=CREATED, is_main_task=True)                         │
│     └─ db.session.flush() → get task_id without commit                          │
│                                                                                  │
│  3. For each service, create SUBTASK:                                            │
│     ┌────────────────────────────────────────────────────────────────────┐      │
│     │  subtask = AnalysisTask(                                           │      │
│     │      parent_task_id = main_task.task_id,                           │      │
│     │      is_main_task = False,                                         │      │
│     │      service_name = 'static-analyzer',                             │      │
│     │      status = PENDING,                                              │      │
│     │      ...                                                           │      │
│     │  )                                                                 │      │
│     └────────────────────────────────────────────────────────────────────┘      │
│                                                                                  │
│  4. Set main_task.status = PENDING, then COMMIT atomically                       │
│     └─ Ensures TaskExecutionService never sees main task without subtasks       │
│                                                                                  │
│  Result: 1 main task + N subtasks created atomically                             │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Race Condition Fixes Applied

| Location | Issue | Fix Applied |
|----------|-------|-------------|
| `_reserve_app_number()` | Non-atomic check-then-insert for app number | SELECT FOR UPDATE + retry with exponential backoff |
| `_process_generation_stage()` | Job index not advanced before async work | `advance_job_index() + COMMIT` before `_submit_generation_job()` |
| `_process_analysis_stage()` | Job index not advanced before async work | `advance_job_index() + COMMIT` before `_submit_analysis_task()` |
| `_submit_analysis_task()` | Duplicate task creation during parallel polling | SELECT FOR UPDATE on pipeline + submitted_apps tracking |
| `add_analysis_task_id()` | Counting main tasks + subtasks together | Separate `main_task_ids` and `subtask_ids` arrays |
| `update_analysis_completion()` | Using total `task_ids` for completion | Use `main_task_ids.length` for accurate count |

---

## Design Issues Identified

### 🔴 Critical Issues

#### Issue 1: Inconsistent Transaction Boundaries in `_process_analysis_stage`
**Location:** [pipeline_execution_service.py](src/app/services/pipeline_execution_service.py#L900-L960)

**Status:** ✅ **FIXED**

**Problem:** The loop advances `job_index` and commits, then calls `_submit_analysis_task()` which does its own SELECT FOR UPDATE and creates tasks. If task creation fails after the commit, the job is lost.

**Solution Applied:**
- Reordered operations: job_index now advances AFTER successful task creation
- Added `mark_job_retryable()` method to allow recovery from transient failures
- Added `retryable_apps` array to track jobs that can be retried

---

#### Issue 2: SELECT FOR UPDATE Not Effective with SQLite
**Location:** [generation.py](src/app/services/generation.py#L3294) and [pipeline_execution_service.py](src/app/services/pipeline_execution_service.py#L975)

**Status:** ⚠️ **DOCUMENTED** (Known Limitation)

**Problem:** `SELECT FOR UPDATE` has **no effect in SQLite** - it's a no-op. SQLite uses database-level locking, not row-level locking. The retry mechanism helps, but it's not true pessimistic locking.

**Evidence:** SQLite documentation states row-level locking is not supported.

**Impact:** Under high concurrency, the retry mechanism is the **only** protection. With 3 retries and exponential backoff, this should be sufficient for typical loads but could fail under extreme parallel load.

**Mitigation:** 
- Class docstring updated with SQLite limitation warning
- Retry mechanism serves as protection layer
- For production with high concurrency, consider PostgreSQL

---

#### Issue 3: `main_task_ids` vs `task_ids` Inconsistency
**Location:** Multiple files

**Status:** ✅ **FIXED**

**Problem:** Two similar lists exist:
- `main_task_ids`: New list for main tasks only
- `task_ids`: Legacy list that includes main tasks (for backwards compat)

**Solution Applied:**
- `main_task_ids` marked as AUTHORITATIVE source for task counting
- `task_ids` marked as DEPRECATED (maintained for backwards compatibility only)
- Clear documentation in `add_analysis_task_id()` docstring

---

### 🟡 Medium Issues

#### Issue 4: Missing Error Recovery for `submitted_apps` Drift
**Location:** [pipeline.py](src/app/models/pipeline.py#L180-L210)

**Status:** ✅ **FIXED**

**Problem:** If a task is created and added to `submitted_apps` but then fails validation later, the entry remains preventing retry.

**Solution Applied:**
- Added `retryable_apps` array to progress structure
- Added `mark_job_retryable()` method to PipelineExecution model
- Jobs can be moved from `submitted_apps` to `retryable_apps` on transient failures
- Jobs automatically removed from `retryable_apps` when successfully resubmitted

---

#### Issue 5: Thread Pool Shutdown Race
**Location:** [pipeline_execution_service.py](src/app/services/pipeline_execution_service.py#L350-L365)

**Status:** ✅ **FIXED**

**Problem:** When `stop()` is called, in-flight tasks may never have their results recorded.

**Solution Applied:**
- Added `_shutting_down` flag and `_shutdown_event` for coordinated shutdown
- `stop()` now waits up to `GRACEFUL_SHUTDOWN_TIMEOUT` (10s) for in-flight tasks
- Added `_persist_incomplete_state()` to save state of tasks still running at shutdown
- Main loop checks `_shutdown_event` and exits gracefully

---

#### Issue 6: Health Cache Not Cleared Between Pipelines
**Location:** [pipeline_execution_service.py](src/app/services/pipeline_execution_service.py#L90-L110)

**Status:** ✅ **FIXED**

**Problem:** `_service_health_cache` persists across pipeline executions, causing stale health status.

**Solution Applied:**
- Health cache is now cleared at the start of each new pipeline's analysis stage
- `_invalidate_health_cache()` called when initializing tracking for new pipeline

---

### 🟢 Minor Issues

#### Issue 7: Logging Inconsistency
**Status:** ✅ **FIXED**

**Problem:** No consistent logging pattern across pipeline operations.

**Solution Applied:**
- Added `_log(context, message)` method with standardized prefixes
- Context prefixes: INIT, GEN, ANAL, TASK, HEALTH, CLEANUP, PIPE, SHUTDOWN
- Format: `[CONTEXT][Pipeline {id}] message`

---

#### Issue 8: Magic Numbers
**Location:** Throughout

**Status:** ✅ **FIXED**

**Solution Applied:**
Extracted to module-level constants:
```python
DEFAULT_MAX_CONCURRENT_TASKS = 3
DEFAULT_MAX_CONCURRENT_GENERATION = 2
MAX_ANALYSIS_WORKERS = 8
MAX_GENERATION_WORKERS = 4
DEFAULT_POLL_INTERVAL = 3.0
CONTAINER_STABILIZATION_DELAY = 5.0
CONTAINER_RETRY_DELAY = 30.0
GRACEFUL_SHUTDOWN_TIMEOUT = 10.0
THREAD_JOIN_TIMEOUT = 5.0
MAX_TASK_CREATION_RETRIES = 3
```

---

## Test Coverage Gaps

| Area | Current Coverage | Gap |
|------|-----------------|-----|
| Race condition in generation | ✅ Unit tests for retry logic | ❌ No integration test with actual parallel execution |
| Task counting | ✅ Unit tests for `main_task_ids` structure | ❌ No test for legacy `task_ids` migration |
| SELECT FOR UPDATE | ❌ None | Needs PostgreSQL to test properly |
| Thread pool shutdown | ❌ None | Hard to test reliably |
| `submitted_apps` recovery | ❌ None | Need test for retry after failure |

---

## Recommendations Summary

### ✅ Completed Actions

| # | Item | Status |
|---|------|--------|
| 1 | Fix job_index/task creation atomicity | ✅ Job index now advances AFTER task creation |
| 2 | Document SQLite locking limitations | ✅ Added to class docstring |
| 3 | Clear health cache on new pipeline | ✅ Cache cleared in `_process_analysis_stage` |
| 4 | Add "retryable" concept to submitted_apps | ✅ Added `retryable_apps` array |
| 5 | Unify logging format | ✅ New `_log(context, message)` method |
| 6 | Extract magic numbers to config | ✅ All timeouts/retries now constants |
| 7 | Add graceful shutdown protocol | ✅ Coordinated shutdown with state persistence |
| 8 | Deprecate `task_ids` array | ✅ Marked deprecated, `main_task_ids` is authoritative |

### Future Considerations

| # | Item | Notes |
|---|------|-------|
| 1 | Consider PostgreSQL for production | Real row-level locking support |
| 2 | Remove `task_ids` array entirely | After migration period |
| 3 | Add retry mechanism for `retryable_apps` | Currently tracked but not auto-retried |

---

## Implementation Notes

### Constants Added (pipeline_execution_service.py)

```python
# Worker pool sizes
DEFAULT_MAX_CONCURRENT_TASKS = 3
DEFAULT_MAX_CONCURRENT_GENERATION = 2
MAX_ANALYSIS_WORKERS = 8
MAX_GENERATION_WORKERS = 4

# Timing configuration
DEFAULT_POLL_INTERVAL = 3.0
CONTAINER_STABILIZATION_DELAY = 5.0
CONTAINER_RETRY_DELAY = 30.0
GRACEFUL_SHUTDOWN_TIMEOUT = 10.0
THREAD_JOIN_TIMEOUT = 5.0

# Retry limits
MAX_TASK_CREATION_RETRIES = 3

# Service ports
ANALYZER_SERVICE_PORTS = {
    'static-analyzer': 2001,
    'dynamic-analyzer': 2002,
    'performance-tester': 2003,
    'ai-analyzer': 2004
}
```

### Progress Structure Updates (pipeline.py)

```python
progress['analysis'] = {
    'main_task_ids': [],      # AUTHORITATIVE - main tasks only
    'subtask_ids': [],        # Subtask IDs for reference
    'task_ids': [],           # DEPRECATED - backwards compat only
    'submitted_apps': [],     # Track submitted model:app pairs
    'retryable_apps': [],     # NEW - Jobs that can be retried
    ...
}
```
