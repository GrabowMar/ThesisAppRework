# Fix: Tool Collection and Metadata Filtering

**Date:** November 16, 2025  
**Status:** ✅ Completed and Tested

## Problem Summary

The analyzer system was incorrectly treating metadata fields as analysis tools, causing:

1. **Metadata appearing as tools**: Fields like `tool_status`, `file_counts`, `security_files`, `total_files`, and `status` were being parsed as if they were analysis tools
2. **Incorrect tool status**: Tools that executed successfully were showing status `Skipped` instead of `success`/`no_issues`
3. **Missing tools map**: The consolidated results sometimes lacked the `tools` map entirely
4. **Confusing UI**: Users saw non-tool entries in the tools list alongside actual analysis tools

## Root Causes

### 1. Insufficient Metadata Filtering
**File:** `analyzer/analyzer_manager.py:_collect_normalized_tools()`

The function only checked for `tool_status` explicitly:
```python
if tname == 'tool_status':  # Skip metadata keys
    continue
```

**Issues:**
- Only filtered one specific key (`tool_status`)
- Case-sensitive matching (missed `Tool_status`)
- Didn't account for other metadata fields (`file_counts`, `security_files`, etc.)

### 2. Metadata in Service Output
**File:** `analyzer/services/static-analyzer/main.py`

The static analyzer service placed metadata at the same nesting level as tool results:
```python
results['tool_status'] = summary  # Metadata mixed with tool results
```

**Issues:**
- `tool_status` dictionary appeared alongside actual tool results
- `file_counts`, `security_files`, `total_files` from `analyze_project_structure()` were at same level as tools
- No clear separation between metadata and tool results

### 3. Missing Tool Validation
The code didn't verify that an object was actually a tool result before adding it to the tools map.

## Solutions Implemented

### 1. Comprehensive Metadata Filtering
**File:** `analyzer/analyzer_manager.py`

Added a comprehensive set of metadata keys to skip:
```python
METADATA_KEYS = {
    'tool_status', '_metadata', 'status', 'file_counts', 'security_files', 
    'total_files', 'message', 'error', 'analysis_time', 'model_slug', 
    'app_number', 'tools_used', 'configuration_applied', 'results',
    '_project_metadata'
}

# Case-insensitive filtering
if tname.lower() in METADATA_KEYS:
    continue
```

**Changes:**
- ✅ Expanded metadata key list to cover all known metadata fields
- ✅ Case-insensitive matching using `.lower()`
- ✅ Applied filtering in both primary and fallback code paths
- ✅ Added tool validation: check for `tool`, `executed`, or `status` fields

### 2. Renamed Service Metadata Keys
**File:** `analyzer/services/static-analyzer/main.py`

Changed metadata keys to use underscore prefix convention:
```python
# Python analyzer metadata
results['_metadata'] = summary  # Was: results['tool_status'] = summary

# Project structure metadata  
return {
    'status': 'success',
    '_project_metadata': {  # Was: flat fields at root level
        'file_counts': file_counts,
        'security_files': security_files,
        'total_files': sum(file_counts.values())
    }
}
```

**Benefits:**
- Underscore prefix (`_metadata`) signals internal/metadata use
- Prevents accidental parsing as tools
- Maintains backward compatibility (old results still work)
- Clearer separation of concerns

### 3. Tool Result Validation
Added validation to ensure entries are actual tool results:
```python
# Verify this looks like a tool result (has expected tool fields)
if not ('tool' in tdata or 'executed' in tdata or 'status' in tdata):
    continue
```

## Testing

### Integration Tests Created
**File:** `tests/integration/analyzer/test_tool_collection.py`

Created comprehensive test suite covering:

1. **`test_tool_collection_filters_metadata`**  
   Verifies metadata fields are excluded from tools map

2. **`test_executed_tools_show_correct_status`**  
   Ensures tools that executed show correct status (not `Skipped`)

3. **`test_tools_have_required_fields`**  
   Validates all tools have required fields (`status`, `executed`, `total_issues`)

4. **`test_service_metadata_remains_in_services`**  
   Confirms metadata stays in services section, not promoted to tools

5. **`test_metadata_keys_list_is_comprehensive`**  
   Guards against forgetting to add new metadata fields to filter list

### Test Results
```bash
$ pytest tests/integration/analyzer/test_tool_collection.py -v
============================== 5 passed in 1.31s ==============================
```

### Real-World Validation
Ran comprehensive analysis on `anthropic_claude-4.5-haiku-20251001/app1`:

**Before Fix:**
- Tools map missing or incomplete
- Metadata fields appearing as tools: `Tool_status`, `File_counts`, `Status`
- Most tools showing status: `Skipped`

**After Fix:**
- ✅ Tools map present with 14 tools
- ✅ No metadata fields in tools map
- ✅ All tools show correct execution status:
  - `bandit`: `no_issues` (executed: true, total_issues: 1)
  - `pylint`: `success` (executed: true, total_issues: 71)
  - `semgrep`: `success` (executed: true, total_issues: 2)
  - `mypy`: `completed` (executed: true)
  - `safety`: `no_issues` (executed: true)
  - And 9 more tools all with correct status

## Files Modified

1. **`analyzer/analyzer_manager.py`**
   - Enhanced `_collect_normalized_tools()` with comprehensive metadata filtering
   - Added case-insensitive matching
   - Added tool result validation
   - Applied filtering in fallback path

2. **`analyzer/services/static-analyzer/main.py`**
   - Renamed `tool_status` → `_metadata` in Python analyzer
   - Wrapped project structure metadata in `_project_metadata`
   - Updated documentation/comments

3. **`pytest.ini`**
   - Added `unit` marker to markers list

4. **`tests/integration/analyzer/test_tool_collection.py`** (NEW)
   - Created comprehensive integration test suite

## Backward Compatibility

✅ **Fully backward compatible**

- Old result files still parse correctly (metadata simply ignored)
- New underscore-prefixed keys won't conflict with existing data
- Filter list includes both old (`tool_status`) and new (`_metadata`) keys
- Case-insensitive matching handles variations in existing data

## Monitoring

To verify the fix is working in production:

1. **Check tools map exists:**
   ```python
   assert 'tools' in results['results']
   ```

2. **Verify no metadata in tools:**
   ```python
   tool_names = set(results['results']['tools'].keys())
   metadata_keys = {'tool_status', '_metadata', 'status', 'file_counts', ...}
   assert not (tool_names & metadata_keys)
   ```

3. **Confirm executed tools show correct status:**
   ```python
   for name, tool in results['results']['tools'].items():
       if tool['executed']:
           assert tool['status'] not in ('skipped', 'Skipped')
   ```

## Future Considerations

1. **Service Output Schema Standardization**  
   Consider enforcing a standard structure across all services with explicit `metadata` vs `tool_results` sections

2. **Status Value Normalization**  
   Standardize all status values to lowercase for consistency across services

3. **Schema Validation**  
   Add JSON schema validation to catch metadata/tool confusion at the service level

## References

- Original issue: User screenshot showing tools being skipped and metadata appearing as tools
- Related docs: `analyzer/README.md`, `docs/guides/RESULT_STRUCTURE.md`
- Test suite: `tests/integration/analyzer/test_tool_collection.py`
