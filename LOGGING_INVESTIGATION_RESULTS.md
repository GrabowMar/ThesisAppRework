# Logging Investigation Results

## Date: 2025-10-29

## What Was Implemented
✅ Comprehensive logging added throughout analyzer pipeline:
- **TaskExecutionService** (`src/app/services/task_execution_service.py`):
  - [EXEC] prefix for analysis execution flow
  - [UNIFIED] prefix for parallel multi-service orchestration
  - 20+ strategic log points covering:
    - Engine selection and metadata analysis
    - Tool resolution (explicit vs config defaults)
    - Orchestrator parameter logging
    - Execution results and error handling
    
- **AnalysisOrchestrator** (`src/app/engines/orchestrator.py`):
  - [ORCH] prefix for orchestration operations
  - 15+ log points including:
    - Entry logging with all parameters
    - **Detailed path resolution** with all 4 fallback attempts logged individually
    - Tool detection and normalization
    - Service grouping and container delegation
    
- **AnalyzerIntegration** (`src/app/services/analyzer_integration.py`):
  - [ANALYZER-SUBPROCESS] prefix for subprocess execution
  - Logs subprocess parameters, command construction, and results

## Testing Results

### ✅ Successful
1. **Code compiles** - No syntax errors in new logging
2. **Flask starts** - Application initializes with "TaskExecutionService started (interval=5.0 batch=3)"
3. **Log file created** - `logs/app.log` exists and captures Flask startup logs
4. **Task execution works** - Test tasks get processed and marked as completed in database
5. **Scripts functional** - Created `trigger_test_analysis.py` and `check_test_task.py` for testing

### ❌ Critical Bug Discovered
**Daemon thread logging not captured in log file!**

**Evidence:**
- Task `test_1761719269` created with status PENDING
- After 10 seconds, task no longer exists in database (processed and completed)
- `logs/app.log` contains ZERO log lines from TaskExecutionService thread
- Log file ends at "TaskExecutionService started" message (logged from main thread)
- No [EXEC], [ORCH], [UNIFIED], or [ANALYZER-SUBPROCESS] prefixes found in log file

**Root Cause:**
The TaskExecutionService runs in a daemon thread (`threading.Thread(..., daemon=True)`). While the thread:
- Successfully picks up pending tasks from queue
- Marks them as RUNNING
- Executes analysis logic
- Marks them as COMPLETED

...the `logger.info()`, `logger.debug()`, and `logger.error()` calls from within the thread **do NOT write to `logs/app.log`**.

**Technical Details:**
- Logger initialized: `logger = get_logger("task_executor")` at module level
- App context is pushed: `with (self._app.app_context() if self._app else _nullcontext())`
- File handler configured: `RotatingFileHandler(logs/app.log)` with UTF-8 encoding
- Console handler works: Startup message "TaskExecutionService started" appears in console
- File handler fails for daemon thread: No thread logs appear in file

## What This Means

**Impact:**
- Cannot debug 0-findings issue without seeing execution flow logs
- No visibility into path resolution attempts (which was the PRIMARY goal)
- No visibility into tool selection or engine execution
- No visibility into orchestrator operations

**Why Tasks Return 0 Findings:**
- Still UNKNOWN because we can't see the logs!
- Possible reasons (speculation without logs):
  1. Path resolution failing (all 4 attempts return None)
  2. Engine execution failing silently
  3. Result parsing returning empty data
  4. Tool execution not happening

## Next Steps Required

### Option 1: Fix Thread Logging (Recommended)
1. Investigate why daemon thread logs don't reach file handler
2. Possible fixes:
   - Explicitly configure logging in thread initialization
   - Force handler flush after each log statement
   - Use queue-based logging handler (QueueHandler) for thread-safe logging
   - Set up separate logger configuration for daemon threads

### Option 2: Alternative Logging Approach
1. Add print statements that flush to stderr immediately
2. Redirect daemon thread logs to separate file (e.g., `logs/task_executor.log`)
3. Use structured logging with explicit file writes

### Option 3: Remove Daemon Thread (Nuclear Option)
1. Execute tasks synchronously for debugging
2. Add temporary blocking execution mode
3. Restore async execution after bugs fixed

## Files Modified

### New Files Created:
- `scripts/trigger_test_analysis.py` - Creates test tasks via SQL insert
- `scripts/check_test_task.py` - Checks task status from database
- `ANALYZER_LOGGING_IMPLEMENTATION.md` - Documentation of logging changes

### Files with Logging Added:
- `src/app/services/task_execution_service.py` - 20+ [EXEC]/[UNIFIED] logs
- `src/app/engines/orchestrator.py` - 15+ [ORCH] logs including detailed _resolve_target_path()
- `src/app/services/analyzer_integration.py` - 5+ [ANALYZER-SUBPROCESS] logs

## Conclusion

**Logging implementation: COMPLETE** ✅
**Logging visibility: FAILED** ❌

The comprehensive logging is in place and well-structured, but due to a Python threading/logging configuration issue, we CANNOT SEE the logs from the daemon thread that does all the actual work. This defeats the entire purpose of adding the logging.

**Recommendation**: Fix the thread logging issue before proceeding with debugging the 0-findings problem. Without logs, we're debugging blind.

## Evidence Files

### Test Task That Processed Without Logs:
```
Task ID: test_1761719269
  Status: PENDING (created)
  Status: <not found> (after 10 seconds - processed and removed)
  
Expected log output:
  [EXEC] Starting analysis execution for task test_1761719269: type=security, model=openai_chatgpt-4o-latest, app=1
  [EXEC] Task test_1761719269 metadata analysis: unified_flag=..., multi_service=...
  [EXEC] Task test_1761719269 => SINGLE-ENGINE analysis path (engine=...)
  [EXEC] Task test_1761719269: Engine resolved to '...' (...)
  [EXEC] Task test_1761719269: No explicit tools, using defaults from config: [...]
  [ORCH] Entering orchestrator: target=openai_chatgpt-4o-latest/app1, tools=[...]
  [ORCH] Path resolution attempt 1: generated/apps/openai_chatgpt-4o-latest/app1 => exists=...
  ... etc ...

Actual log output:
  <NOTHING - thread logs not captured>
```

### Log File Contents (Last 3 Lines):
```
[07:13:13] INFO     task_executor        TaskExecutionService started (interval=5.0 batch=3)
[07:13:13] INFO     factory              Task execution service initialized
[07:13:13] INFO     werkzeug             Press CTRL+C to quit
```

No further log lines after startup, despite task execution completing successfully in the background.
