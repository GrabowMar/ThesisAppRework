# Static Analyzer Severity Mapping Status

## Summary of Changes (December 26, 2025)

Fixed severity categorization issues where whitespace and formatting rules were incorrectly marked as HIGH severity.

## Tools with Fixed Severity Mappings

### ✅ Ruff (FIXED)
**Issue**: All rules marked as `"level": "error"` in native SARIF output, including trivial whitespace issues
**Fix**: Added `_get_ruff_severity()` mapping + `remap_ruff_sarif_severity()` post-processor
- **W291, W292, W293** (whitespace) → `note`/`low` ✅
- **I001** (import sorting) → `warning`/`medium`
- **S104, S311** (security) → `error`/`high`
- **E-series** (pycodestyle) → `warning`/`medium` (context-dependent)

### ✅ Flake8 (FIXED)
**Issue**: W-codes all marked as 'medium', but whitespace should be 'low'
**Fix**: Updated both `Flake8Parser` and `Flake8SARIFParser`
- **W291, W292, W293** (whitespace) → `low` ✅
- **E/F-series** (errors) → `high`
- **Other W-codes** → `medium`

## Tools with Correct SARIF Output

### ✅ Bandit
- Native SARIF output via `-f sarif`
- Severity correctly mapped from Bandit's own severity levels
- **Status**: No changes needed

### ✅ Semgrep
- Native SARIF output via `--sarif`
- Uses rule metadata for severity (ERROR/WARNING/INFO)
- **Status**: No changes needed

### ✅ ESLint
- Native SARIF output via `@microsoft/eslint-formatter-sarif`
- Severity: 1=warning, 2=error
- **Status**: No changes needed

### ✅ Pylint
- Manually converted to SARIF in main.py
- Type-based severity: fatal/error→error, warning→warning, convention/refactor→note
- **Status**: No changes needed

### ✅ MyPy
- JSON output converted to SARIF via `MypySARIFParser`
- error→error/high, warning→warning/medium
- **Status**: No changes needed

### ✅ Vulture
- Text output converted to SARIF via `VultureSARIFParser`
- Confidence-based: ≥80%→medium, <80%→low
- **Status**: No changes needed

### ✅ Radon
- JSON output parsed via `RadonParser`
- Rank-based: A/B→low, C/D→medium, E/F→high
- **Status**: Appropriate complexity-based severity

### ✅ detect-secrets
- JSON output parsed via `DetectSecretsParser`
- All secrets marked as 'high' (correct for secrets)
- **Status**: Appropriate severity for secrets

## Tools Without Severity Mapping (Output Raw JSON)

### ⚠️ Safety
**Current**: Outputs vulnerability JSON without severity in result dict
**Recommendation**: Vulnerabilities should be 'high' by default
**Impact**: Dependencies with known CVEs should be flagged prominently
**Status**: Tool output includes vulnerability data; aggregation layer should treat as high

### ⚠️ pip-audit
**Current**: Outputs CVE JSON without severity in result dict
**Recommendation**: CVEs should be 'high' by default
**Impact**: Dependencies with known CVEs should be flagged prominently
**Status**: Tool output includes vulnerability data; aggregation layer should treat as high

### ⚠️ npm-audit
**Current**: Outputs vulnerability JSON without severity in result dict
**Recommendation**: Vulnerabilities should be 'high' by default
**Impact**: Node dependencies with known CVEs should be flagged prominently
**Status**: Tool output includes vulnerability data; aggregation layer should treat as high

### ℹ️ stylelint
**Current**: Outputs JSON with warnings array, no severity field
**Recommendation**: CSS linting issues should default to 'low' or 'info'
**Impact**: Styling issues are low priority compared to security/logic errors
**Status**: Cosmetic issues; appropriate for info/low severity

### ℹ️ html-validator
**Current**: Outputs validation JSON without severity
**Recommendation**: HTML validation issues should default to 'low' or 'info'
**Impact**: Markup issues are low priority
**Status**: Cosmetic issues; appropriate for info/low severity

### ⚠️ Snyk
**Current**: May output JSON or SARIF depending on command
**Recommendation**: Security vulnerabilities should be 'high'
**Impact**: Code security issues should be prominent
**Status**: Security tool; requires high severity by default

## Severity Level Guidelines

### HIGH / ERROR
- Security vulnerabilities (Bandit S-series, Semgrep security rules)
- Syntax errors (undefined names, parse errors)
- Critical logic errors (F821, E999)
- Known CVEs in dependencies (Safety, pip-audit, npm-audit)
- Hardcoded secrets (detect-secrets)

### MEDIUM / WARNING
- Import issues (unsorted, unused)
- Code complexity (high cyclomatic complexity)
- Potential bugs (comparison issues, type mismatches)
- Non-critical linter warnings

### LOW / NOTE
- **Whitespace/formatting** (W291, W292, W293) ✅ FIXED
- Style conventions
- Dead code (low confidence)
- HTML/CSS validation issues

## Impact of Changes

### Before Fix
- Ruff: 103 issues, most marked as HIGH (including W293 whitespace)
- Flake8: W-codes all MEDIUM
- **Problem**: Inflated HIGH severity counts made it hard to identify critical issues

### After Fix
- Ruff: Whitespace issues correctly marked as LOW
- Flake8: Whitespace issues correctly marked as LOW
- **Result**: Accurate severity distribution; HIGH severity reserved for real problems

## Testing

All changes verified with unit tests:
- ✅ W293 (blank line whitespace): note/low
- ✅ W291 (trailing whitespace): note/low
- ✅ W292 (no newline at EOF): note/low
- ✅ S104 (hardcoded bind): error/high
- ✅ S311 (weak random): error/high
- ✅ SARIF remapping function works correctly

## Recommendations for Future Work

1. **Add SARIF parsers** for npm-audit, pip-audit, stylelint, html-validator
2. **Standardize severity mapping** in aggregation layer for tools without parsers
3. **Document severity expectations** in tool configuration files
4. **Add severity override** capability in analyzer configs
