# Tool Output Parity Analysis

## Issue Summary

**Problem**: Tool outputs shown in UI may not match actual analysis results stored in filesystem JSON files.

**Root Cause**: Database `result_summary` field contains incomplete data structure compared to filesystem JSON.

## Verification Results (task_358365b03c2c)

### Filesystem JSON (Ground Truth)
✅ **Complete structure** in `results/anthropic_claude-4.5-haiku-20251001/app1/task_358365b03c2c/`:

```json
{
  "metadata": {...},
  "results": {
    "summary": {...},
    "services": {...},
    "tools": {
      "bandit": {
        "status": "success",
        "total_issues": 2,
        "executed": true
      },
      "pylint": {
        "status": "success",
        "total_issues": 61,
        "executed": true
      },
      "semgrep": {
        "status": "success",
        "total_issues": 2,
        "executed": true
      },
      // ... 16 more tools
    },
    "findings": [...]
  }
}
```

**Tool counts (expected)**:
- **Bandit**: 2 issues
- **Pylint**: 61 issues  
- **Semgrep**: 2 issues
- **Mypy**: 0 issues (error status)
- **Safety**: 0 issues
- **Pip-audit**: 0 issues
- **Vulture**: 0 issues
- **Ruff**: 0 issues
- **Flake8**: 0 issues
- **ESLint**: 0 issues
- **Npm-audit**: 0 issues
- **Stylelint**: 0 issues

### Database result_summary (Incomplete)
❌ **Missing critical data**:

```json
{
  "analysis_type": "task_358365b03c2c",
  "task_name": "task_358365b03c2c",
  "results_path": "results/...",
  "services": {
    // Raw per-service payloads (nested, not normalized)
  },
  "summary": {
    "total_findings": 74,
    "services_completed": [...],
    "overall_status": "partial"
  }
  // ❌ MISSING: results.tools
  // ❌ MISSING: results.findings
  // ❌ MISSING: metadata
}
```

## Code Analysis

### Where Data Gets Saved

#### 1. Analyzer Manager (`analyzer/analyzer_manager.py:2084`)
✅ **Saves complete structure to filesystem**:
- `metadata`
- `results.summary`
- `results.services` (with SARIF extracted)
- `results.tools` (flat normalized map across all services)
- `results.findings` (aggregated findings list)

```python
task_metadata = {
    'metadata': {...},
    'results': {
        'summary': {...},
        'services': {...},
        'tools': normalized_tools,  # ✅ Flat map
        'findings': aggregated_findings.get('findings')  # ✅ Aggregated list
    }
}
```

#### 2. Task Execution Service (`src/app/services/task_execution_service.py:544`)
❌ **Saves incomplete structure to database**:

```python
wrapped_payload = {
    'analysis_type': analysis_method,
    'task_name': task_name,
    'results_path': results_path,
    'services': services_to_process,  # ✅ Has this
    'summary': {...}  # ✅ Has this
    # ❌ MISSING: results.tools
    # ❌ MISSING: results.findings  
    # ❌ MISSING: metadata
}
```

### Why This Causes Issues

1. **UnifiedResultService** (`src/app/services/unified_result_service.py:172`) loads from **database first** (priority source)
2. UI templates expect `results.tools` map for displaying tool badges/statuses
3. When database is missing this data, templates show incorrect/incomplete information
4. Filesystem JSON has the correct data but is only used as fallback

## Recommended Fix

**File**: `src/app/services/task_execution_service.py` (line 544)

**Change**: Include full `results` structure in `wrapped_payload`:

```python
# Read the actual saved file from disk to get the complete structure
result_file = wrapper.get_latest_result_file(task.target_model, task.target_app_number, task_name)
if result_file and result_file.exists():
    with open(result_file, 'r', encoding='utf-8') as f:
        full_structure = json.load(f)
    
    # Use the complete results structure from file
    wrapped_payload = {
        'metadata': full_structure.get('metadata', {}),
        'results': full_structure.get('results', {})
        # This includes: summary, services, tools, findings
    }
else:
    # Fallback to current minimal structure
    wrapped_payload = {
        'analysis_type': analysis_method,
        'task_name': task_name,
        'results_path': results_path,
        'services': services_to_process,
        'summary': {...}
    }
```

## Workaround (Temporary)

Until fixed, force UI to load from filesystem:

```python
# In unified_result_service.py, swap priority
def load_analysis_results(self, task_id, force_refresh=False):
    # Try filesystem FIRST
    payload = self._file_load_results(task_id)
    if payload:
        return self._transform_to_analysis_results(task_id, payload)
    
    # Fallback to database
    payload = self._db_load_results(task_id)
    ...
```

## Impact

### Current Behavior
- ❌ Tool badges may show "No issues" when issues exist
- ❌ Issue counts may be incorrect or missing
- ❌ Findings list incomplete
- ❌ Tool status (success/error/timeout) may not display correctly

### After Fix
- ✅ All tool outputs match filesystem JSON (ground truth)
- ✅ Correct issue counts displayed
- ✅ Complete findings list
- ✅ Accurate tool statuses
- ✅ Database and filesystem in sync

## Testing Verification

Run verification script:

```bash
python verify_tool_outputs.py task_358365b03c2c
```

Expected output:
- All tools show `Match: ✅`
- DB Issues = FS Issues for each tool
- UI display matches actual tool execution results
