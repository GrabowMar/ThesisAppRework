# Comprehensive Analysis Metadata Extraction

## Overview

The enhanced Analysis Inspection Service now extracts **ALL available metadata** from security and code quality analysis tools, providing maximum detail for advanced analysis and reporting.

## Enhanced Features

### 🚀 Version 2.0 Extraction Engine
- **18+ metadata fields per finding** (vs 6-8 previously)
- **Raw tool data preservation** for advanced analysis
- **Comprehensive tool metrics** and execution statistics
- **Project structure analysis** with file type counts
- **CWE vulnerability mappings** with direct links
- **Column-level positioning** for precise code location

## Tool-Specific Metadata Extraction

### Bandit Security Analysis
**Core Fields:**
- `test_id` - Bandit test identifier (e.g., B104)
- `test_name` - Test category (e.g., hardcoded_bind_all_interfaces)
- `issue_severity` - Security severity (HIGH/MEDIUM/LOW)
- `issue_confidence` - Detection confidence level
- `issue_text` - Human-readable issue description

**Location Details:**
- `filename` - Full file path
- `line_number` - Exact line number
- `line_range` - Array of affected lines
- `col_offset` - Starting column position
- `end_col_offset` - Ending column position
- `code` - Code snippet showing the issue

**Security Metadata:**
- `issue_cwe.id` - CWE vulnerability ID
- `issue_cwe.link` - Direct link to CWE definition
- `more_info` - URL to Bandit documentation

**Metrics:**
- Per-file confidence/severity breakdowns
- Lines of code analyzed
- Skipped tests count
- nosec comments count

### PyLint Code Quality Analysis
**Core Fields:**
- `type` - Issue type (error/warning/info/convention/refactor)
- `message` - Detailed issue description
- `message-id` - PyLint message identifier (e.g., E0401)
- `symbol` - Rule symbol (e.g., import-error)

**Location Details:**
- `path` - Relative file path
- `line` - Line number
- `column` - Column position
- `endLine` - End line (for multi-line issues)
- `endColumn` - End column position

**Context:**
- `module` - Python module name
- `obj` - Object/function context

**Metrics:**
- Total issues count
- Files analyzed count
- Configuration applied

### ESLint JavaScript Analysis
**Core Fields:**
- `ruleId` - ESLint rule identifier
- `message` - Issue description
- `messageId` - Internal message ID
- `severity` - Severity level (1=warning, 2=error)

**Location Details:**
- `filePath` - JavaScript file path
- `line` - Line number
- `column` - Column position
- `endLine` - End line position
- `endColumn` - End column position

**Advanced Features:**
- `nodeType` - AST node type
- `source` - Source code excerpt
- `fix` - Automatic fix information (if available)
- `suggestions` - Alternative fix suggestions

### MyPy Type Checking
**Core Fields:**
- `message` - Type checking message
- `error_code` - MyPy error code
- `severity` - Issue severity

**Location Details:**
- `file` - Python file path
- `line` - Line number
- `column` - Column position
- `end_line` - End line position
- `end_column` - End column position

**Additional:**
- `note` - Additional notes
- `suggestion` - Fix suggestions

### StyleLint CSS Analysis
**Core Fields:**
- `rule` - StyleLint rule name
- `text` - Issue description
- `severity` - Error/warning level

**Location Details:**
- `source` - CSS file path
- `line` - Line number
- `column` - Column position

## Enhanced Data Structure

### Complete Response Format
```json
{
  "task_id": "task_ed3c5b00a9e2",
  "status": "completed",
  "analysis_type": "security",
  "model_slug": "nousresearch_hermes-4-405b",
  "app_number": 10,
  "analysis_time": "2025-09-10T11:57:11.948876",
  "tools_used": ["bandit", "pylint", "mypy", "eslint", "stylelint"],
  "configuration_applied": false,
  
  "tool_metrics": {
    "bandit": {
      "status": "success",
      "total_issues": 1,
      "metrics": {
        "per_file_stats": {...},
        "_totals": {
          "CONFIDENCE.HIGH": 0,
          "CONFIDENCE.MEDIUM": 1,
          "SEVERITY.MEDIUM": 1,
          "loc": 9,
          "nosec": 0,
          "skipped_tests": 0
        }
      }
    },
    "pylint": {
      "status": "success", 
      "total_issues": 2,
      "files_analyzed": 1
    }
  },
  
  "structure_analysis": {
    "file_counts": {
      "python": 1,
      "javascript": 2,
      "css": 0,
      "html": 1,
      "dockerfile": 2
    },
    "security_files": {
      "requirements_txt": false,
      "package_json": false,
      "dockerfile": true,
      "gitignore": false
    },
    "total_files": 8
  },
  
  "findings_preview": [
    {
      "tool": "bandit",
      "severity": "medium",
      "confidence": "medium",
      "title": "Possible binding to all interfaces.",
      "category": "hardcoded_bind_all_interfaces",
      "file_path": "app10/backend/app.py",
      "line_number": 12,
      "line_range": [12],
      "column_offset": 17,
      "end_column_offset": 26,
      "test_id": "B104",
      "test_name": "hardcoded_bind_all_interfaces",
      "code_snippet": "app.run(host='0.0.0.0', port=5159)",
      "cwe_id": 605,
      "cwe_link": "https://cwe.mitre.org/data/definitions/605.html",
      "more_info_url": "https://bandit.readthedocs.io/...",
      "raw_data": { /* Complete original tool output */ }
    }
  ],
  
  "findings_by_tool": {
    "bandit": 1,
    "pylint": 2
  },
  
  "findings_by_severity": {
    "error": 2,
    "medium": 1
  },
  
  "metadata": {
    "extraction_version": "2.0",
    "comprehensive_parsing": true,
    "raw_data_included": true
  }
}
```

## Usage Examples

### Advanced Security Analysis
```python
# Extract CWE mappings for vulnerability tracking
findings = results['findings_preview']
cwe_vulnerabilities = [
    f for f in findings 
    if f.get('tool') == 'bandit' and f.get('cwe_id')
]

# Group by severity and confidence
high_confidence_issues = [
    f for f in findings 
    if f.get('confidence') == 'high'
]
```

### Code Quality Metrics
```python
# Analyze PyLint symbol patterns
symbol_counts = {}
for finding in findings:
    if finding.get('tool') == 'pylint':
        symbol = finding.get('symbol')
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

# Most common code quality issues
sorted_issues = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)
```

### Tool Performance Analysis
```python
# Extract tool execution metrics
tool_metrics = results['tool_metrics']
for tool, metrics in tool_metrics.items():
    print(f"{tool}: {metrics['total_issues']} issues, {metrics['status']}")
    
# Project structure insights
structure = results['structure_analysis']
print(f"Total files: {structure['total_files']}")
print(f"Python files: {structure['file_counts']['python']}")
```

## Benefits

### 🎯 Maximum Information Extraction
- **Zero data loss** - All tool output preserved
- **18+ metadata fields** per finding
- **Raw data access** for custom analysis
- **Tool metrics** for performance tracking

### 🔍 Enhanced Analysis Capabilities
- **CWE vulnerability mapping** for security tracking
- **Column-level precision** for IDE integration
- **Code context preservation** with snippets
- **Confidence levels** for risk assessment

### 📊 Comprehensive Reporting
- **Tool performance metrics** 
- **Project structure analysis**
- **Severity and tool breakdowns**
- **Historical trend analysis** support

### 🚀 Future-Proof Architecture
- **Raw data preservation** enables new analysis methods
- **Extensible structure** for additional tools
- **Version tracking** of extraction logic
- **Backward compatibility** maintained

## Implementation Notes

- **Performance**: Increased limit to 50 findings per tool (vs 25 previously)
- **Memory**: Raw data preserved but accessed lazily
- **Compatibility**: All existing endpoints continue to work
- **Extensibility**: Easy to add new tools and metadata fields

## Migration

Existing code continues to work unchanged. Enhanced metadata is available via:
- `findings_preview[].raw_data` - Complete original tool output
- `tool_metrics` - Tool execution statistics  
- `structure_analysis` - Project file analysis
- Additional fields in each finding object

Version can be checked via `metadata.extraction_version` field.
