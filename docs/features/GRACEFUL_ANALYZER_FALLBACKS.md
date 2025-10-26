# Graceful Analyzer Service Fallbacks

**Status**: ✅ Implemented  
**Version**: 1.0.0  
**Date**: 2025-01-26

## Overview

The analyzer system now implements graceful degradation at the service level, ensuring that analysis tasks complete with partial results even when individual analyzer services (static, dynamic, performance, AI) fail, timeout, or become unavailable.

## Problem Statement

Previously, when running unified analysis across multiple services, if any single service crashed, timed out, or threw an exception, the entire task would be marked as `FAILED` even though other services succeeded. This resulted in:

- **Lost data**: Partial results from successful services were discarded
- **Poor user experience**: Users received no results when some tools worked fine
- **Debugging difficulty**: Hard to distinguish between total failure vs. partial failure

## Solution

### Service-Level Error Isolation

Each analyzer service now executes in an isolated timeout wrapper that:

1. **Catches service exceptions** without aborting the entire task
2. **Enforces configurable timeouts** (default: 10 minutes per service)
3. **Records degradation metadata** for UI display
4. **Creates synthetic error tool results** to maintain schema consistency
5. **Continues execution** with remaining services

### Configuration

#### Environment Variables

```bash
# Timeout for individual analyzer services (seconds)
# Default: 600 (10 minutes)
ANALYZER_SERVICE_TIMEOUT=600

# Whether to retry failed services (default: false for faster feedback)
# Default: false
ANALYZER_RETRY_FAILED_SERVICES=false
```

#### Application Settings

Configure in `src/config/settings.py`:

```python
class Config:
    # Timeout for individual analyzer services (seconds)
    ANALYZER_SERVICE_TIMEOUT = int(os.environ.get('ANALYZER_SERVICE_TIMEOUT', '600'))
    
    # Whether to retry failed services
    ANALYZER_RETRY_FAILED_SERVICES = os.environ.get('ANALYZER_RETRY_FAILED_SERVICES', 'false').lower() == 'true'
```

## Architecture

### Timeout Wrapper

The `_execute_service_with_timeout()` method wraps each service execution:

```python
def _execute_service_with_timeout(self, engine, model_slug, app_number, tools, service_name):
    """Execute a service with timeout protection."""
    # 1. Run service in daemon thread
    # 2. Join with timeout
    # 3. Return status dict (status, payload, error)
```

**Key Features**:
- Daemon thread for clean shutdown
- Non-blocking timeout enforcement
- Structured error reporting (status: timeout/error/failed)
- Preserves service payload on success

### Degradation Tracking

Failed services are tracked in `degraded_services` list:

```python
degraded_services.append({
    'service': 'static-analyzer',
    'status': 'timeout',
    'error': 'Service execution timed out after 600 seconds',
    'tools_affected': ['bandit', 'safety', 'pylint']
})
```

### Result Schema

The unified analysis payload includes degradation metadata:

```json
{
  "summary": {
    "services_executed": 3,
    "services_degraded": 1,
    "status": "completed_with_warnings"
  },
  "metadata": {
    "degraded_services": [
      {
        "service": "static-analyzer",
        "status": "timeout",
        "error": "Service execution timed out after 600 seconds",
        "tools_affected": ["bandit", "safety"]
      }
    ],
    "partial_results": true,
    "service_timeout_seconds": 600
  }
}
```

### Task Success Criteria

**Task completes successfully if**:
- **At least ONE tool** produces output (any service succeeds)
- Task status: `COMPLETED` with `completed_with_warnings` if degraded

**Task fails only if**:
- **ALL services fail** (no successful tools)
- Task status: `FAILED`

## User Experience

### UI Enhancements

#### 1. Warning Alert (Result Detail Page)

When `degraded_services` exists, a warning alert displays:

```
⚠️ Partial Results Available

2 services were unavailable during analysis. 
Results are shown from successfully completed services only.

• static-analyzer: timeout — Service execution timed out after 600 seconds (5 tools affected)
• ai-analyzer: error — Connection refused (1 tool affected)
```

#### 2. Services Metric Badge

The Services metric shows degradation status:

```
Services: 3
2 degraded  [warning tone]
```

#### 3. Tool Status Indicators

Failed tools show their service status:

```json
{
  "tool_name": "bandit",
  "status": "failed",
  "error": "Service execution timed out after 600 seconds",
  "service_status": "timeout"  // timeout, error, or failed
}
```

## Testing

### Manual Testing

1. **Timeout Scenario**:
   ```bash
   # Set short timeout to force degradation
   export ANALYZER_SERVICE_TIMEOUT=5
   python analyzer/analyzer_manager.py analyze model app unified
   ```

2. **Service Crash Scenario**:
   ```bash
   # Stop one service mid-analysis
   docker stop analyzer-static-analyzer-1
   python analyzer/analyzer_manager.py analyze model app unified
   ```

3. **Verify Partial Results**:
   - Check task status: `COMPLETED`
   - Verify `degraded_services` in metadata
   - Confirm successful services have results
   - Check UI warning alert displays

### Automated Testing

Add to `tests/services/test_task_execution_service.py`:

```python
def test_unified_analysis_with_service_timeout(app, db):
    """Test graceful degradation when service times out."""
    # Set very short timeout
    app.config['ANALYZER_SERVICE_TIMEOUT'] = 0.1
    
    # Create task with multiple services
    task = create_unified_task()
    
    # Execute
    executor.process_once()
    
    # Assert: task completes, has degraded_services
    assert task.status == AnalysisStatus.COMPLETED
    metadata = task.get_metadata()
    assert metadata['degraded_services']
    assert metadata['partial_results'] is True
```

## Migration Notes

### Backward Compatibility

✅ **Fully backward compatible**:
- Existing tasks use default timeout (10 minutes)
- No schema changes to database
- Old result payloads still render correctly
- No changes to tool-level error handling

### Deployment Checklist

1. ✅ Update `settings.py` with new config keys
2. ✅ Update `task_execution_service.py` with timeout wrapper
3. ✅ Update `result_detail.html` with warning UI
4. ✅ Set environment variables in `.env` (optional)
5. ⚠️ Restart Flask app to load new config
6. ⚠️ Monitor logs for timeout occurrences

## Monitoring & Debugging

### Log Patterns

**Service Timeout**:
```
WARNING: Service static-analyzer timed out after 600s - continuing with other services
```

**Service Error**:
```
ERROR: Service dynamic-analyzer failed: Connection refused - continuing with other services
```

**Degradation Summary**:
```
INFO: Unified analysis final status: completed_with_warnings 
      (successful_tools=8, failed_tools=3, degraded_services=1)
```

### Metrics to Track

- **Degradation rate**: `degraded_services / total_services`
- **Timeout frequency**: Count of `status: timeout` events
- **Partial completion rate**: Tasks with `partial_results: true`
- **Mean time to service timeout**: Distribution of timeout occurrences

## Performance Considerations

### Timeout Tuning

**Recommended timeouts by service**:
- **Static Analyzer**: 600s (10 min) — handles large codebases
- **Dynamic Analyzer**: 300s (5 min) — quick connectivity tests
- **Performance Tester**: 600s (10 min) — includes load tests
- **AI Analyzer**: 300s (5 min) — LLM API calls

**Global timeout**:
```bash
# Conservative (safe for large projects)
ANALYZER_SERVICE_TIMEOUT=900  # 15 minutes

# Balanced (recommended)
ANALYZER_SERVICE_TIMEOUT=600  # 10 minutes

# Aggressive (fast feedback)
ANALYZER_SERVICE_TIMEOUT=300  # 5 minutes
```

### Thread Safety

- ✅ Daemon threads don't block shutdown
- ✅ Each service runs in isolated thread
- ✅ No shared state between threads
- ✅ Database commits are sequential (no race conditions)

## Future Enhancements

### Retry Logic (Optional)

Currently disabled by default for faster feedback. To enable:

```python
ANALYZER_RETRY_FAILED_SERVICES = True
```

**Future implementation**:
1. Retry failed services once after all services complete
2. Exponential backoff for transient failures
3. Skip retry if error is deterministic (e.g., missing Docker container)

### Service Health Checks

**Pre-execution validation**:
1. Ping each service before dispatching tools
2. Skip unavailable services proactively
3. Provide immediate feedback: "2/4 services available"

### Circuit Breaker Pattern

**Rate-limited failure handling**:
1. Track failure rate per service (e.g., 5 failures in 10 minutes)
2. Open circuit: skip service temporarily
3. Half-open: retry after cooldown period
4. Close circuit: resume normal operation

## References

- **Main Implementation**: `src/app/services/task_execution_service.py`
- **Configuration**: `src/config/settings.py`
- **UI Template**: `src/templates/pages/analysis/result_detail.html`
- **Result Schema**: `docs/knowledge_base/analysis/result_schema.md`
- **Analysis Engines**: `src/app/services/analysis_engines.py`

## Summary

✅ **Implemented**:
- Service-level timeout protection (configurable via `ANALYZER_SERVICE_TIMEOUT`)
- Graceful degradation (tasks succeed with partial results)
- Degraded services tracking in metadata
- UI warning alerts for partial results
- Tool-level error records for failed services

✅ **Task Success**:
- Completes if **at least ONE tool** succeeds
- Fails only if **ALL services fail**

✅ **No Retry** (default):
- Fast feedback loop
- Optional retry via `ANALYZER_RETRY_FAILED_SERVICES=true`

---

**Impact**: Analysis tasks are now resilient to individual service failures, providing users with actionable partial results instead of total failure.
