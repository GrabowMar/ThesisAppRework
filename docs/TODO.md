# Long-term TODOs

## Analyzer Improvements

### Reintegrate html-validator into reports
- **Status**: Removed from report static tools list (commit TBD)
- **Reason**: `html-validator-cli` was called with positional file args instead of `--file=<path>`, causing it to error silently with 0 findings across all 391 executions. Fixed invocation to use `--file=` per file, but existing result data still has 0 findings.
- **Action needed**: After re-running analyses with the fixed analyzer, add `'html-validator'` back to `_STATIC_TOOLS` in `report_service.py` (~line 2891).
- **Files**: `analyzer/services/static-analyzer/main.py` (fixed), `src/app/services/report_service.py` (excluded)

### Add SARIF parsers for remaining 6 tools
- **Tools without SARIF conversion**: pip-audit, radon, detect-secrets, npm-audit, stylelint, html-validator
- **Impact**: Only affects `sarif_export` document (supplementary). Severity data works correctly via `severity_breakdown` dict for all tools.
- **Priority**: Low — only needed if external SARIF interop is required.
- **File**: `analyzer/services/static-analyzer/sarif_parsers.py`

## Report Improvements

### Consider adding stylelint to report exclusion
- **Status**: Currently included but shows 0 findings for all models
- **Reason**: LLM-generated CSS consistently passes default stylelint rules
- **Decision**: Keep for now — may produce findings with stricter configs or different app templates
