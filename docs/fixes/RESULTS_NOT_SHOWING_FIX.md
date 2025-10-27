# Analysis Results Not Showing in UI - Fix Summary

## Problem

Analysis tasks were completing successfully with results stored in the database, but the UI showed tasks as "100% complete" with no findings displayed. The tasks appeared in the UI like this:

```
Task ID	Model	App	Type	Status	Progress / Findings	Time
security:anthropic_claude-4.5-haiku-20251001:1
1	security		100%	07:14:14
```

## Root Cause

The issue was a **dual-storage mismatch**:

1. **Database Storage**: Tasks completed and saved results to `task.result_summary` column containing analysis data with findings (e.g., 8 findings)
   
2. **File Storage**: The UI's `ResultFileService` expects result files on disk at `results/{model}/app{N}/task_{type}_{timestamp}/`

3. **Missing Link**: Some tasks only wrote results to the database but **did not create disk files**, so `ResultFileService.list_results()` returned 0 descriptors

## Investigation Steps

### 1. Checked Database Records

```python
# Task had completed status and result_summary in database
task.status = 'completed'
task.result_summary = '{...8 findings...}'
task.get_result_summary() = {
    'payload': {
        'summary': {
            'total_findings': 8
        }
    }
}
```

### 2. Checked Disk Files

```
results/
└── anthropic_claude-4.5-haiku-20251001/
    ├── app3/  ← Files exist for app 3
    └── app1/  ← MISSING for app 1
```

### 3. Checked ResultFileService

```python
service = ResultFileService()
descriptors = service.list_results('anthropic_claude-4.5-haiku-20251001', 1)
# Returns: [] (empty list)
```

The UI template (`tasks_table.html`) displays findings from `descriptor.total_findings`:

```html
<span class="badge bg-dark">{{ descriptor.total_findings if descriptor.total_findings is not none else '—' }}</span>
```

Since `descriptor` was `None`, no findings badge appeared.

## Solution

Created a backfill script (`backfill_results.py`) that:

1. Queries all completed tasks with database results but no disk files
2. Reads `task.result_summary` from database
3. Writes properly formatted result files to disk:
   - Main result JSON: `results/{model}/app{N}/task_{type}_{timestamp}/{model}_app{N}_task_{type}_{timestamp}.json`
   - Manifest JSON: `results/{model}/app{N}/task_{type}_{timestamp}/manifest.json`

### File Format

**Main Result File**:
```json
{
  "task_id": "task_d12057889e50",
  "model_slug": "anthropic_claude-4.5-haiku-20251001",
  "app_number": 1,
  "analysis_type": "security",
  "timestamp": "2025-10-27T08:29:25+00:00",
  "metadata": {
    "task_id": "task_d12057889e50",
    "model_slug": "anthropic_claude-4.5-haiku-20251001",
    "app_number": 1,
    "analysis_type": "security",
    "timestamp": "2025-10-27T08:29:25+00:00",
    "analyzer_version": "1.0.0",
    "module": "security",
    "version": "1.0"
  },
  "results": { ...actual results from database... },
  "summary": { ...summary with total_findings... }
}
```

**Manifest File**:
```json
{
  "task_id": "task_d12057889e50",
  "model_slug": "anthropic_claude-4.5-haiku-20251001",
  "app_number": 1,
  "primary_result": "anthropic_claude-4.5-haiku-20251001_app1_task_security_20251027_082925_20251027_082925.json",
  "services": [],
  "service_files": {},
  "created_at": "2025-10-27T08:29:25+00:00"
}
```

## Verification

After backfilling:

```python
# ResultFileService now finds the results
descriptors = service.list_results('anthropic_claude-4.5-haiku-20251001', 1)
# Returns: 1 descriptor

descriptor.total_findings = 8  # ✅ Correct!
descriptor.status = 'unknown'
descriptor.timestamp = '2025-10-27 08:29:25.712410+00:00'
```

The UI now properly displays:
- ✅ Task status: "Completed"
- ✅ Findings badge: "8" with severity breakdown
- ✅ View/Download buttons active

## Prevention

To prevent this issue in the future, ensure that **both database AND disk writes happen** when persisting analysis results:

### Current Flow

1. `AIAnalyzerEngine.run()` generates results
2. Calls `analysis_result_store.persist_analysis_payload_by_task_id(task_id, payload)`
3. This writes to database via `store_analysis_payload(task, payload)`

### Required Addition

After database persistence, also write to disk:

```python
# In AIAnalyzerEngine.run() or task completion handler
if persist and task_id:
    # Write to database (existing)
    analysis_result_store.persist_analysis_payload_by_task_id(task_id, payload)
    
    # Also write to disk for UI (NEEDED)
    from pathlib import Path
    write_task_result_file(task_id, payload)  # New helper function
```

### Long-term Solution

Consider unifying the storage:

**Option A**: Make `ResultFileService` read from database instead of disk files
**Option B**: Always write both database + disk files atomically
**Option C**: Use database as source of truth, generate disk files on-demand for downloads

## Files Modified/Created

1. **Created**: `backfill_results.py` - Script to backfill missing result files
2. **Affected**: `src/app/services/result_file_service.py` - Reads disk files
3. **Affected**: `src/app/services/analysis_result_store.py` - Writes database
4. **Affected**: `src/templates/pages/analysis/partials/tasks_table.html` - Displays findings

## Summary

- **Problem**: Tasks complete but UI shows no results
- **Cause**: Results only in database, not on disk files
- **Fix**: Backfilled disk files from database records
- **Prevention**: Ensure dual-write (database + disk) for all task results

**Status**: ✅ RESOLVED for existing tasks, requires code change to prevent recurrence
