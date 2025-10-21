# Static Analyzer Tool Parsers

## Overview
The `parsers.py` module provides tool-specific output parsers that standardize JSON output from various static analysis tools into a consistent format for the ThesisAppRework platform.

## Supported Tools

### Python Tools
- **Bandit** - Security vulnerability scanner
- **Pylint** - Code quality and style checker
- **Safety** - Dependency vulnerability scanner
- **Flake8** - Style guide enforcement (requires `flake8-json` plugin)

### JavaScript/TypeScript Tools
- **ESLint** - JavaScript/TypeScript linter

### Multi-Language Tools
- **Semgrep** - Pattern-based security scanner

## Standard Output Format

All parsers produce output in this standardized structure:

```python
{
    'tool': str,                # Tool name (e.g., 'bandit', 'eslint')
    'executed': bool,           # Whether the tool ran successfully
    'status': str,              # 'success' | 'error' | 'no_issues'
    'issues': list[dict],       # Standardized issue objects
    'total_issues': int,        # Count of issues found
    'severity_breakdown': dict, # Counts by severity level
    'config_used': dict,        # Configuration passed to the tool
    'metrics': dict,            # Optional: Additional metrics (bandit)
    'error': str                # Optional: Error message if status='error'
}
```

### Standard Issue Object

Each issue in the `issues` array follows this structure:

```python
{
    'file': str,           # File path
    'line': int,           # Line number
    'column': int,         # Column number (if available)
    'end_line': int,       # End line (if available)
    'end_column': int,     # End column (if available)
    'severity': str,       # 'high' | 'medium' | 'low'
    'message': str,        # Issue description
    'rule': str,           # Rule/check ID (e.g., 'B201', 'no-unused-vars')
    # Tool-specific additional fields...
}
```

## Tool-Specific Details

### Bandit Parser
**Input Format**: Bandit JSON with `results` and `metrics` keys

**Severity Mapping**:
- HIGH → high
- MEDIUM → medium
- LOW → low

**Additional Fields**:
- `confidence`: 'high' | 'medium' | 'low'
- `rule_name`: Human-readable rule name
- `code_snippet`: Code excerpt
- `more_info`: Documentation URL
- `cwe`: CWE information

**Example**:
```bash
bandit -r ./app -f json
```

### Safety Parser
**Input Format**: Safety 3.x JSON with `vulnerabilities` array

**Severity Mapping**: Based on CVSS score
- score >= 7.0 → high
- 4.0 <= score < 7.0 → medium
- score < 4.0 → low

**Additional Fields**:
- `package`: Package name
- `installed_version`: Current version
- `affected_versions`: Vulnerable version specs
- `fixed_versions`: Patched versions
- `vulnerability_id`: Safety ID
- `cve`: CVE identifier
- `cvss_score`: CVSS base score
- `is_transitive`: Whether it's a transitive dependency

**Example**:
```bash
safety scan --output json
```

### Pylint Parser
**Input Format**: Pylint JSON array of message objects

**Severity Mapping**:
- fatal, error → high
- warning → medium
- refactor, convention, info → low

**Additional Fields**:
- `type`: Original Pylint message type
- `symbol`: Rule symbol (e.g., 'line-too-long')
- `module`: Python module name
- `obj`: Function or class name

**Example**:
```bash
pylint --output-format=json ./app/*.py
```

### Flake8 Parser
**Input Format**: Flake8 JSON dict with filename keys (requires `flake8-json` plugin)

**Severity Mapping**: Based on error code prefix
- E (errors), F (fatal) → high
- W (warnings) → medium
- Other → low

**Additional Fields**:
- `source`: Source tool (e.g., 'pycodestyle', 'pyflakes')
- `physical_line`: Actual code line

**Example**:
```bash
pip install flake8-json
flake8 --format=json ./app
```

### ESLint Parser
**Input Format**: ESLint JSON array of file result objects

**Severity Mapping**:
- severity=2 (error) → high
- severity=1 (warning) → medium

**Additional Fields**:
- `node_type`: AST node type
- `message_id`: Internal message ID

**Example**:
```bash
eslint --format json ./src
```

### Semgrep Parser
**Input Format**: Semgrep JSON with `results` and `errors` arrays

**Severity Mapping**:
- ERROR → high
- WARNING → medium
- INFO → low

**Additional Fields**:
- `code_snippet`: Matched code
- `metadata`: Rule metadata

**Example**:
```bash
semgrep scan --json --config=auto ./app
```

## Usage in Code

### Direct Parser Usage
```python
from parsers import parse_tool_output

# After running a tool and capturing JSON output
raw_output = json.loads(tool_stdout)
parsed_result = parse_tool_output('bandit', raw_output, config={'enabled': True})

print(f"Found {parsed_result['total_issues']} issues")
for issue in parsed_result['issues']:
    print(f"{issue['file']}:{issue['line']} - {issue['severity']} - {issue['message']}")
```

### Integrated with _run_tool
The `StaticAnalyzer._run_tool()` method automatically applies parsers:

```python
# In analyzer service
results['bandit'] = await self._run_tool(
    cmd=['bandit', '-r', './app', '-f', 'json'],
    tool_name='bandit',
    config=bandit_config,
    success_exit_codes=[0, 1]
)
# Result is already parsed and standardized
```

## Adding New Parsers

To add support for a new tool:

1. **Create Parser Class**:
```python
class MyToolParser:
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        # Extract issues from raw_output
        # Map to standard format
        return {
            'tool': 'mytool',
            'executed': True,
            'status': 'success',
            'issues': [...],
            'total_issues': len(issues),
            'severity_breakdown': {...},
            'config_used': config or {}
        }
```

2. **Register in PARSERS Dict**:
```python
PARSERS = {
    'bandit': BanditParser,
    'mytool': MyToolParser,  # Add here
    # ...
}
```

3. **Use in Tool Execution**:
```python
results['mytool'] = await self._run_tool(
    cmd=['mytool', '--json'],
    tool_name='mytool',
    config=mytool_config
)
```

## Testing Parsers

Create test JSON files and verify parsing:

```python
import json
from parsers import parse_tool_output

# Load sample output
with open('test_data/bandit_output.json') as f:
    raw_output = json.load(f)

# Parse and validate
result = parse_tool_output('bandit', raw_output)
assert result['status'] == 'success'
assert result['total_issues'] > 0
assert all('severity' in issue for issue in result['issues'])
```

## Benefits

1. **Consistency**: All tools report issues in the same format
2. **Maintainability**: Parser logic isolated from tool execution
3. **Extensibility**: Easy to add new tools
4. **Type Safety**: Predictable data structure for frontend/database
5. **Error Handling**: Centralized error parsing and fallback logic

## Web Search References

- **Bandit JSON Output**: https://bandit.readthedocs.io/en/latest/formatters/json.html
- **Safety JSON Format**: https://docs.safetycli.com/safety-docs/output/json-output
- **Pylint JSON**: https://pylint.pycqa.org/en/latest/user_guide/usage/output.html
- **ESLint Formatters**: https://eslint.org/docs/latest/use/formatters/
- **Flake8 JSON Plugin**: https://pypi.org/project/flake8-json/
- **Semgrep Output**: https://semgrep.dev/docs/cli-usage/

## Future Enhancements

- [ ] Add parsers for remaining tools (MyPy, Vulture, JSHint, Snyk, Stylelint)
- [ ] Implement parser validation tests
- [ ] Add parser benchmark suite
- [ ] Support for incremental/diff analysis
- [ ] Caching of parsed results
- [ ] Parser plugins system for custom tools
