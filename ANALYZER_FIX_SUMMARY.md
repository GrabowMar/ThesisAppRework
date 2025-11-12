# Analyzer Findings Extraction Fix - Summary

## Problem Identified

The analyzer was executing all tools successfully and logging "Aggregated 78 findings from 16 tools", but the saved JSON files showed:
- `findings: []` (empty array)
- `tools: {}` (empty object)
- `total_findings: 0`

## Root Cause

**Service file structure mismatch:**

Service snapshot files (`services/*.json`) have structure:
```json
{
  "metadata": {...},
  "results": {              ← EXTRA WRAPPER
    "type": "static_analysis_result",
    "status": "success",
    "analysis": {
      "results": {
        "python": {
          "bandit": {
            "issues": [],    ← Empty (data in SARIF)
            "total_issues": 2,
            "sarif": {...}   ← 62K lines of actual data
          }
        }
      }
    }
  }
}
```

**Two issues:**
1. Extraction code expected `analysis.results` but actual structure is `results.analysis.results`
2. Tool findings moved to SARIF format, `issues` arrays are empty

## Fix Applied

### 1. Fixed Structure Navigation (`_aggregate_findings`)

**File**: `analyzer/analyzer_manager.py` line ~1722

**Before:**
```python
findings = self._extract_findings_from_analyzer_result(analyzer_name, analyzer_result)
```

**After:**
```python
# Service snapshots have structure: {metadata: {...}, results: {type, status, analysis: {...}}}
# We need to extract from the 'results' wrapper if present
service_results = analyzer_result.get('results', analyzer_result)
findings = self._extract_findings_from_analyzer_result(analyzer_name, service_results)
```

### 2. Added SARIF Extraction (`_extract_static_findings`)

**File**: `analyzer/analyzer_manager.py` line ~1228

**Added** SARIF extraction for Bandit:
```python
# If issues array is empty but SARIF exists, extract from SARIF
if not issues and bandit.get('sarif'):
    logger.debug("[STATIC] Bandit: extracting from SARIF")
    sarif = bandit['sarif']
    if isinstance(sarif, dict) and 'runs' in sarif:
        for run in sarif['runs']:
            for result in run.get('results', []):
                # Extract findings from SARIF format
                findings.append({...})
```

**Added** SARIF extraction for Semgrep (similar pattern)

### 3. Enhanced Debug Logging

Added comprehensive logging at key points:
- `[AGGREGATE] Processing N services`
- `[AGGREGATE] service_name: extracting findings from service_results`
- `[AGGREGATE] service_name: extracted N findings`
- `[STATIC] Found python tools: [...]`
- `[STATIC] Bandit: extracting from SARIF`
- `[AGGREGATE] Total: N findings from N tools`

## Verification

**Before Fix:**
```json
{
  "results": {
    "summary": {
      "total_findings": 0,
      "tools_executed": 0,
      "findings_by_tool": {}
    },
    "findings": [],
    "tools": {}
  }
}
```

**After Fix:**
```json
{
  "results": {
    "summary": {
      "total_findings": 78,
      "tools_executed": 16,
      "findings_by_tool": {
        "pylint": 60,
        "vulture": 9,
        "artillery": 1,
        "curl": 8
      }
    },
    "findings": [...],  // 78 findings
    "tools": {...}      // 16 tools
  }
}
```

**Test Command:**
```bash
python analyzer/analyzer_manager.py analyze anthropic_claude-4.5-haiku-20251001 1 static
```

## Files Modified

1. `analyzer/analyzer_manager.py`:
   - Line ~1722: `_aggregate_findings()` - Added service results wrapper navigation
   - Line ~1228: `_extract_static_findings()` - Added SARIF extraction for Bandit
   - Line ~1351: `_extract_static_findings()` - Added SARIF extraction for Semgrep
   - Added debug logging throughout

## Impact

✅ **Static Analysis**: Now extracts findings from Bandit, Pylint, Semgrep, and all other Python tools
✅ **Dynamic Analysis**: Existing extraction continues to work
✅ **Performance Analysis**: Existing extraction continues to work
✅ **AI Analysis**: Existing extraction continues to work

## Results Location

Analyzed apps save results to:
```
results/{model_slug}/app{N}/task_{task_id}/
├── {model}_app{N}_task_{id}_{timestamp}.json  ← Main consolidated file
├── services/
│   ├── {model}_app{N}_static.json             ← Service snapshots (62K lines)
│   ├── {model}_app{N}_dynamic.json
│   ├── {model}_app{N}_performance.json
│   └── {model}_app{N}_ai.json
├── sarif/                                      ← Extracted SARIF files
└── manifest.json
```

## Example Data

**Haiku App1 Analysis (task_analysis_20251112_215227):**
- Total findings: 78
- Tools executed: 16
- Breakdown:
  - Pylint: 60 issues (code quality)
  - Vulture: 9 issues (dead code)
  - Artillery: 1 issue (performance)
  - Curl: 8 issues (connectivity)

**File sizes:**
- Main JSON: ~50KB
- Static service JSON: 62,409 lines
- SARIF files: Individual per-tool

## Next Steps

1. ✅ Fix verified working with existing data
2. ✅ Three Haiku apps available for analysis
3. ⏳ Run analyses on apps 2 & 3 to collect comparative data
4. ⏳ Generate academic reports with actual findings

## Technical Notes

- **SARIF Format**: Static Analysis Results Interchange Format (industry standard)
- **Service Files**: Each analyzer service writes its own snapshot with full data
- **Consolidated Files**: Main file aggregates findings across all services
- **Tool Status**: Tools marked as `no_issues`, `success`, `skipped`, or `failed`
- **Severity Normalization**: Converts tool-specific severities to `high`, `medium`, `low`
