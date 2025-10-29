# Comprehensive Analyzer Logging Implementation

## Summary

Added extensive debug logging throughout the entire analyzer execution pipeline to trace task execution from creation through completion. This will help identify why tasks complete instantly with 0 findings even when applications exist on the filesystem.

## Changes Made

### 1. TaskExecutionService (`src/app/services/task_execution_service.py`)

**Added logging for:**
- `[EXEC]` - Main execution flow
  - Task start with model/app/type parameters
  - Metadata analysis (unified vs single-engine decision)
  - Engine selection and resolution
  - Tool resolution (explicit vs defaults from config)
  - Orchestrator call parameters
  - Engine execution results
  - Payload wrapping and findings count
  - Exception context with full traceback

- `[UNIFIED]` - Parallel execution flow
  - Unified analysis start
  - Tools grouped by service
  - Subtask discovery
  - Pre-flight checks (Celery + containers)
  - Service delegation
  - Exception handling

**Key logging points:**
```python
logger.info("[EXEC] Task %s: Calling engine.run(model_slug=%s, app_number=%s, tools=%s, persist=True)")
logger.info("[EXEC] Task %s: Engine.run completed with status=%s, has_payload=%s, error=%s")
logger.debug("[EXEC] Task %s: Wrapped payload - total_findings=%s, tools_executed=%s")
```

### 2. AnalysisOrchestrator (`src/app/engines/orchestrator.py`)

**Added logging for:**
- `[ORCH]` - Orchestrator operations
  - Entry point with all parameters
  - Path resolution attempts (all 4 fallback strategies)
  - Path validation success/failure
  - Tool detection from context
  - Tool normalization (alias resolution)
  - Service grouping for delegation
  - Container delegation per service
  - Container success/failure status

**Key path resolution logging:**
```python
logger.debug("[ORCH] Path attempt #1 (generated/apps): %s - exists=%s")
logger.debug("[ORCH] Path attempt #2 (misc/models): %s - exists=%s")  
logger.debug("[ORCH] Path attempt #3 (helper fuzzy match): %s - exists=%s")
logger.warning("[ORCH] All path attempts FAILED - returning fallback")
```

**Critical tip added:**
```python
logger.info(
    "[ORCH] TIP: Generate the application first - it doesn't exist in filesystem. "
    "DB record may exist but files are missing."
)
```

### 3. AnalyzerIntegration (`src/app/services/analyzer_integration.py`)

**Added logging for:**
- `[ANALYZER-SUBPROCESS]` - Subprocess bridge
  - Subprocess start with parameters
  - Command construction
  - Python executable path
  - Execution start
  - Process completion with returncode
  - Failure details with stderr

**Key subprocess logging:**
```python
logger.info("[ANALYZER-SUBPROCESS] Command: %s (cwd=%s)")
logger.debug("[ANALYZER-SUBPROCESS] Executing subprocess.run (timeout=1800s)...")
logger.info("[ANALYZER-SUBPROCESS] Process completed: returncode=%s, stdout_len=%s, stderr_len=%s")
```

### 4. Diagnostic Script (`scripts/diagnose_analysis_failure.py`)

**New utility script that checks:**
1. **Database vs Filesystem Mismatches**
   - Identifies DB records without actual files
   - Shows which apps need to be generated
   
2. **Analyzer Services Health**
   - Checks all 4 analyzer containers (ports 2001-2004)
   - Reports which services are down
   
3. **Recent Failed Tasks**
   - Shows tasks with 0 findings or failed status
   - Cross-references with filesystem existence
   - Displays error messages
   
4. **Path Resolution Check**
   - Validates generated/apps directory
   - Lists model directories and app counts

**Usage:**
```bash
# Full diagnostic
python scripts/diagnose_analysis_failure.py

# Specific app
python scripts/diagnose_analysis_failure.py --model openai_gpt-4.1-2025-04-14 --app 4
```

## Diagnostic Findings

Running the diagnostic revealed:

### Issue #1: Missing Filesystem for DB Records
```
❌ MISMATCH: openai_chatgpt-4o-latest/app1
   DB Record: ✅ (id=1, created=2025-10-29 02:41:44)
   Filesystem: ❌ MISSING
```
**Root Cause:** GeneratedApplication record exists in DB but no files on disk
**Fix:** Generate the application using API or UI

### Issue #2: Existing Apps with 0 Findings
```
✅ OK: openai_gpt-4.1-2025-04-14/app4
   Path: ...app4 ✅ EXISTS (13 files)
   
BUT: 4 analysis tasks all show 0 findings
```
**Root Cause:** UNKNOWN - files exist, services healthy, but no analysis results
**Investigation Needed:** Check logs with new logging to see execution flow

## Next Steps to Debug

1. **Restart Flask** to load new logging:
   ```bash
   cd src
   python main.py
   ```

2. **Run a test analysis** on existing app:
   ```bash
   # Via UI or API
   POST /api/analysis/run
   {
     "model_slug": "openai_gpt-4.1-2025-04-14",
     "app_number": 4,
     "analysis_type": "security",
     "tools": ["bandit"]
   }
   ```

3. **Check logs** for new debug output:
   ```bash
   # Filter for our new log prefixes
   grep "\[EXEC\]\|\[ORCH\]\|\[UNIFIED\]\|\[ANALYZER-SUBPROCESS\]" logs/flask.log
   ```

4. **Look for these critical points:**
   - `[ORCH] Path attempt #1` - Did path resolution succeed?
   - `[ORCH] DELEGATING to container` - Were tools sent to containers?
   - `[ANALYZER-SUBPROCESS] Process completed: returncode=` - Did subprocess succeed?
   - `[EXEC] Wrapped payload - total_findings=` - How many findings came back?

## Log Level Configuration

All new logging respects your `LOG_LEVEL` environment variable:
- `LOG_LEVEL=DEBUG` - See all path attempts, tool resolution, subprocess details
- `LOG_LEVEL=INFO` - See execution flow, delegation, results (recommended)
- `LOG_LEVEL=WARNING` - Only errors and warnings

## Expected Log Output (Example)

```
[EXEC] Starting analysis execution for task task_abc123: type=security, model=openai_gpt-4, app=1
[EXEC] Task task_abc123 metadata analysis: unified_flag=False, multi_service=False, is_unified=False
[EXEC] Task task_abc123 => SINGLE-ENGINE analysis path (engine=security)
[EXEC] Task task_abc123: Engine resolved to 'security' (UniversalAnalyzerEngine)
[EXEC] Task task_abc123: Using explicitly resolved tools: ['bandit', 'safety']
[EXEC] Task task_abc123: Calling engine.run(model_slug=openai_gpt-4, app_number=1, tools=['bandit', 'safety'], persist=True)

[ORCH] Starting run_analysis: model=openai_gpt-4, app=1, tools=['bandit', 'safety']
[ORCH] Target path not provided, resolving...
[ORCH] Path attempt #1 (generated/apps): C:\...\generated\apps\openai_gpt-4\app1 - exists=True
[ORCH] Resolved via generated/apps: C:\...\generated\apps\openai_gpt-4\app1
[ORCH] Path validation SUCCESS: C:\...\generated\apps\openai_gpt-4\app1 exists
[ORCH] Service groups: {'static-analyzer': 2} (total_services=1, total_tools=2)
[ORCH] Service static-analyzer: up=True, tools=['bandit', 'safety']
[ORCH] DELEGATING to container: service=static-analyzer, model=openai_gpt-4, app=1, tools=['bandit', 'safety']

[ANALYZER-SUBPROCESS] Starting subprocess: type=security, model=openai_gpt-4, app=1, tools=['bandit', 'safety']
[ANALYZER-SUBPROCESS] Command: python analyzer_manager.py analyze openai_gpt-4 1 security --tools bandit safety
[ANALYZER-SUBPROCESS] Process completed: returncode=0, stdout_len=1234, stderr_len=0

[EXEC] Task task_abc123: Engine.run completed with status=success, has_payload=True, error=False
[EXEC] Task task_abc123: Wrapped payload - total_findings=15, tools_executed=2
```

## Files Modified

- `src/app/services/task_execution_service.py` - Core execution logging
- `src/app/engines/orchestrator.py` - Path resolution + delegation logging
- `src/app/services/analyzer_integration.py` - Subprocess bridge logging
- `scripts/diagnose_analysis_failure.py` - NEW diagnostic utility

## Testing the Changes

1. Run diagnostic: `python scripts/diagnose_analysis_failure.py`
2. Restart Flask: `python src/main.py`
3. Trigger analysis via UI or API
4. Check logs: `tail -f logs/flask.log | grep "\[EXEC\]\|\[ORCH\]"`
5. Identify where execution fails or returns empty results

---

**The logging is now EXTREMELY verbose** - you will see every step of the execution pipeline. This should reveal exactly where tasks are failing or why they return 0 findings even when apps exist.
