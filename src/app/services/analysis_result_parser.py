"""Unified analysis tool result parsing utilities.

Enhanced result parsing for the new dynamic tool system.
Provides normalization helpers to turn tool results into canonical finding dictionaries
used by the UI / API.

Contract (output finding dict keys):
  tool: str              # tool name e.g. "bandit"
  severity: str          # normalized severity: critical|high|medium|low|info|unknown
  title: str             # short human readable summary
  category: str          # rule/test/category identifier
  file_path: str         # relative file path inside generated app sources
  line_number: int|None
  column: int|None
  end_line: int|None
  end_column: int|None
  message: str           # descriptive message
  confidence: str        # confidence level: high|medium|low|unknown
  tags: List[str]        # tool and context tags
  references: List[str]  # related URLs/documentation
  fix_suggestion: str|None  # suggested fix if available
  raw_data: dict         # original tool record for advanced / drill‑down

Enhanced with support for the new dynamic tool system's standardized Finding format.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List

# Import from new engine system
try:
    from ..engines.base import Finding as _Finding  # noqa: F401
    NEW_ENGINE_AVAILABLE = True
except ImportError:
    NEW_ENGINE_AVAILABLE = False

SEVERITY_MAP_GENERIC = {
    # bandit maps mixed case values; pylint numeric -> handled separately
    'CRITICAL': 'critical',
    'HIGH': 'high',
    'MEDIUM': 'medium',
    'LOW': 'low',
    'ERROR': 'high',
    'WARN': 'medium',
    'WARNING': 'medium',
    'INFO': 'low',
    'INFORMATIONAL': 'info'
}


def _normalize_severity(value: Any) -> str:
    """Normalize severity value to standard format."""
    if value is None:
        return 'unknown'
    if isinstance(value, (int, float)):
        # Pylint numeric: 0 (convention/info) -> info, 1 warning, 2 error, 3 fatal (treat as error)
        mapping = {0: 'info', 1: 'medium', 2: 'high', 3: 'critical'}
        return mapping.get(int(value), 'unknown')
    upper = str(value).strip().upper()
    return SEVERITY_MAP_GENERIC.get(upper, upper.lower() if upper else 'unknown')


def _normalize_confidence(value: Any) -> str:
    """Normalize confidence value to standard format."""
    if value is None:
        return 'unknown'
    upper = str(value).strip().upper()
    confidence_map = {
        'HIGH': 'high',
        'MEDIUM': 'medium', 
        'LOW': 'low'
    }
    return confidence_map.get(upper, upper.lower() if upper else 'unknown')


def parse_new_engine_results(analysis_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse results from the new dynamic analysis engine system.
    
    Args:
        analysis_results: Results from AnalysisOrchestrator
        
    Returns:
        List of canonical finding dictionaries
    """
    findings = []
    
    # Extract findings from new orchestrator format
    raw_findings = analysis_results.get('findings', [])
    
    for finding_data in raw_findings:
        try:
            # Findings from new system are already in canonical format
            if isinstance(finding_data, dict):
                # Ensure all required fields are present
                canonical_finding = {
                    'tool': finding_data.get('tool', 'unknown'),
                    'severity': finding_data.get('severity', 'unknown'),
                    'confidence': finding_data.get('confidence', 'unknown'),
                    'title': finding_data.get('title', ''),
                    'category': finding_data.get('category', ''),
                    'file_path': finding_data.get('file_path', ''),
                    'line_number': finding_data.get('line_number'),
                    'column': finding_data.get('column'),
                    'end_line': finding_data.get('end_line'),
                    'end_column': finding_data.get('end_column'),
                    'message': finding_data.get('description', finding_data.get('message', '')),
                    'tags': finding_data.get('tags', []),
                    'references': finding_data.get('references', []),
                    'fix_suggestion': finding_data.get('fix_suggestion'),
                    'raw_data': finding_data.get('raw_data', finding_data)
                }
                findings.append(canonical_finding)
        except Exception as e:
            # Log error but continue processing
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse finding: {e}")
            continue
    
    return findings


def parse_tool_results(tool_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse results from individual tools in the new system.
    
    Args:
        tool_results: Tool results from orchestrator
        
    Returns:
        List of canonical finding dictionaries
    """
    all_findings = []
    
    for tool_name, result in tool_results.items():
        try:
            if not isinstance(result, dict):
                continue
                
            tool_findings = result.get('findings', [])
            for finding in tool_findings:
                if isinstance(finding, dict):
                    # Ensure tool name is set
                    finding['tool'] = tool_name
                    all_findings.append(finding)
                    
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to parse results for tool {tool_name}: {e}")
            continue
    
    return all_findings


def parse_bandit_results(bandit_json: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse bandit JSON structure into canonical findings list.

    bandit_json expected structure (subset):
      {
        "results": [ { "filename": str, "issue_severity": str, ... } ],
        "metrics": { ... }
      }
    """
    findings: List[Dict[str, Any]] = []
    for issue in bandit_json.get('results', [])[:200]:  # safeguard limit
        findings.append({
            'tool': 'bandit',
            'severity': _normalize_severity(issue.get('issue_severity')),
            'confidence': _normalize_confidence(issue.get('issue_confidence')),
            'title': issue.get('issue_text', '')[:200].strip(),
            'category': issue.get('test_name') or issue.get('test_id') or 'bandit',
            'file_path': issue.get('filename', ''),
            'line_number': issue.get('line_number'),
            'column': None,
            'end_line': None,
            'end_column': None,
            'message': issue.get('issue_text', '').strip(),
            'tags': ['security', 'python'],
            'references': [issue.get('more_info')] if issue.get('more_info') else [],
            'fix_suggestion': None,
            'raw_data': issue,
        })
    return findings


def parse_pylint_messages(pylint_issues: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse iterable of pylint issue dicts.

    Expected keys (subset): 'type', 'message', 'symbol', 'path', 'line', 'column',
    plus any extras (kept in raw_data).
    """
    results: List[Dict[str, Any]] = []
    for issue in list(pylint_issues)[:400]:  # guard large lists
        severity = issue.get('type') or issue.get('message-id')
        results.append({
            'tool': 'pylint',
            'severity': _normalize_severity(severity),
            'confidence': 'high',  # Pylint is generally confident
            'title': issue.get('message', '')[:160].strip(),
            'category': issue.get('symbol') or issue.get('message-id') or 'pylint',
            'file_path': issue.get('path') or issue.get('file_path') or issue.get('filename', ''),
            'line_number': issue.get('line') or issue.get('line_number'),
            'column': issue.get('column'),
            'end_line': issue.get('endLine') or issue.get('end_line'),
            'end_column': issue.get('endColumn') or issue.get('end_column'),
            'message': issue.get('message', '').strip(),
            'tags': ['quality', 'python'],
            'references': [],
            'fix_suggestion': None,
            'raw_data': issue,
        })
    return results


def parse_eslint_results(eslint_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Parse ESLint JSON results into canonical findings list."""
    findings: List[Dict[str, Any]] = []
    
    for file_result in eslint_data:
        file_path = file_result.get('filePath', '')
        
        for message in file_result.get('messages', []):
            try:
                # Map ESLint severity to our severity
                eslint_severity = message.get('severity', 1)
                severity = 'high' if eslint_severity == 2 else 'medium'
                
                rule_id = message.get('ruleId', '')
                
                finding = {
                    'tool': 'eslint',
                    'severity': severity,
                    'confidence': 'high',
                    'title': message.get('message', '').strip(),
                    'category': rule_id,
                    'file_path': file_path,
                    'line_number': message.get('line'),
                    'column': message.get('column'),
                    'end_line': message.get('endLine'),
                    'end_column': message.get('endColumn'),
                    'message': message.get('message', '').strip(),
                    'tags': ['quality', 'javascript'],
                    'references': [],
                    'fix_suggestion': "ESLint auto-fix available" if message.get('fix') else None,
                    'raw_data': message
                }
                
                # Add security tag for security rules
                if rule_id and any(term in rule_id.lower() for term in ['security', 'xss', 'injection']):
                    finding['tags'].append('security')
                
                findings.append(finding)
                
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to parse ESLint message: {e}")
                continue
    
    return findings


def merge_findings(*lists: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge multiple finding lists into one."""
    merged: List[Dict[str, Any]] = []
    for seq in lists:
        if not seq:
            continue
        merged.extend(seq)
    return merged


def get_findings_summary(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Get summary statistics for findings."""
    summary = {
        'total_findings': len(findings),
        'severity_breakdown': {},
        'tool_breakdown': {},
        'category_breakdown': {},
        'tags': set()
    }
    
    for finding in findings:
        # Count by severity
        severity = finding.get('severity', 'unknown')
        summary['severity_breakdown'][severity] = summary['severity_breakdown'].get(severity, 0) + 1
        
        # Count by tool
        tool = finding.get('tool', 'unknown')
        summary['tool_breakdown'][tool] = summary['tool_breakdown'].get(tool, 0) + 1
        
        # Count by category
        category = finding.get('category', 'unknown')
        summary['category_breakdown'][category] = summary['category_breakdown'].get(category, 0) + 1
        
        # Collect tags
        tags = finding.get('tags', [])
        if isinstance(tags, list):
            summary['tags'].update(tags)
    
    # Convert tags set to list for JSON serialization
    summary['tags'] = list(summary['tags'])
    
    return summary


__all__ = [
    'parse_new_engine_results',
    'parse_tool_results',
    'parse_bandit_results',
    'parse_pylint_messages',
    'parse_eslint_results',
    'merge_findings',
    'get_findings_summary'
]
