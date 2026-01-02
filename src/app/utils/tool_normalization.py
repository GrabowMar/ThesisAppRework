"""
Tool Normalization Utilities
============================

Shared utilities for normalizing tool results across different analyzer services.
Consolidates duplicate normalization logic from analyzer_manager.py and task_execution_service.py.

This module provides:
- Severity normalization across different tool formats
- Tool result collection and normalization
- Findings aggregation from multiple services
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ==============================================================================
# SEVERITY NORMALIZATION
# ==============================================================================

# Canonical severity levels (ordered from highest to lowest)
SEVERITY_LEVELS = ['critical', 'high', 'medium', 'low', 'info']

# Mapping from various tool severity formats to canonical format
SEVERITY_MAP = {
    # Critical
    'critical': 'critical',
    'fatal': 'critical',
    
    # High
    'high': 'high',
    'error': 'high',
    'danger': 'high',
    'severe': 'high',
    
    # Medium
    'medium': 'medium',
    'moderate': 'medium',
    'warning': 'medium',
    'warn': 'medium',
    
    # Low
    'low': 'low',
    'minor': 'low',
    'note': 'low',
    'suggestion': 'low',
    
    # Info
    'info': 'info',
    'informational': 'info',
    'none': 'info',
    'unknown': 'info',
}


def normalize_severity(severity: Any) -> str:
    """Normalize severity level to canonical format.
    
    Handles various formats:
    - String values (high, medium, error, warning, etc.)
    - Numeric ESLint severity (1=warning, 2=error)
    - SARIF levels (error, warning, note, none)
    - ZAP risk levels (High, Medium, Low, Informational)
    
    Args:
        severity: Raw severity value from tool
        
    Returns:
        Normalized severity: 'critical', 'high', 'medium', 'low', or 'info'
    """
    if severity is None:
        return 'info'
    
    # Handle numeric ESLint severity
    if isinstance(severity, (int, float)):
        if severity >= 2:
            return 'high'
        elif severity == 1:
            return 'medium'
        return 'info'
    
    # Handle string severity
    severity_str = str(severity).lower().strip()
    return SEVERITY_MAP.get(severity_str, 'medium')


def compare_severity(sev1: str, sev2: str) -> int:
    """Compare two severity levels.
    
    Returns:
        -1 if sev1 < sev2, 0 if equal, 1 if sev1 > sev2
    """
    try:
        idx1 = SEVERITY_LEVELS.index(sev1.lower())
    except ValueError:
        idx1 = len(SEVERITY_LEVELS)
    
    try:
        idx2 = SEVERITY_LEVELS.index(sev2.lower())
    except ValueError:
        idx2 = len(SEVERITY_LEVELS)
    
    # Lower index = higher severity
    if idx1 < idx2:
        return 1
    elif idx1 > idx2:
        return -1
    return 0


def get_severity_breakdown(findings: List[Dict[str, Any]]) -> Dict[str, int]:
    """Calculate severity breakdown from findings list.
    
    Args:
        findings: List of finding dicts with 'severity' key
        
    Returns:
        Dict with counts: {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
    """
    breakdown = {sev: 0 for sev in SEVERITY_LEVELS}
    
    for finding in findings:
        if not isinstance(finding, dict):
            continue
        sev = normalize_severity(finding.get('severity'))
        breakdown[sev] = breakdown.get(sev, 0) + 1
    
    return breakdown


# ==============================================================================
# TOOL STATUS NORMALIZATION
# ==============================================================================

# Canonical tool statuses
TOOL_STATUS_SUCCESS = ['success', 'completed', 'ok', 'passed', 'done', 'no_issues']
TOOL_STATUS_ERROR = ['error', 'failed', 'failure', 'crashed']
TOOL_STATUS_SKIP = ['skipped', 'not_available', 'disabled', 'n/a']


def normalize_tool_status(status: Any) -> str:
    """Normalize tool execution status to canonical format.
    
    Args:
        status: Raw status from tool
        
    Returns:
        'success', 'error', 'skipped', or 'unknown'
    """
    if status is None:
        return 'unknown'
    
    status_str = str(status).lower().strip()
    
    if status_str in TOOL_STATUS_SUCCESS:
        return 'success'
    elif status_str in TOOL_STATUS_ERROR:
        return 'error'
    elif status_str in TOOL_STATUS_SKIP:
        return 'skipped'
    
    return 'unknown'


def is_success_status(status: Any) -> bool:
    """Check if status indicates success."""
    return normalize_tool_status(status) == 'success'


# ==============================================================================
# TOOL RESULT COLLECTION
# ==============================================================================

def collect_normalized_tools(services: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Collect and normalize tool results from all services.
    
    Returns flat dict of {tool_name: {status, findings_count, service, ...}}
    
    Args:
        services: Dict of service results with structure:
            {service_name: {analysis: {tool_results: {...}, results: {...}}}}
            
    Returns:
        Normalized tool map with structure:
            {tool_name: {
                'status': 'success'|'error'|'skipped'|'unknown',
                'findings_count': int,
                'service': str,
                'exit_code': int (optional),
                'sarif_file': str (optional),
                'execution_time': float (optional)
            }}
    """
    normalized_tools: Dict[str, Dict[str, Any]] = {}
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue
        
        analysis = service_data.get('analysis', {})
        if not isinstance(analysis, dict):
            continue
        
        # Process tool_results structure (dynamic, performance, ai)
        tool_results = analysis.get('tool_results', {})
        if isinstance(tool_results, dict):
            for tool_name, tool_data in tool_results.items():
                normalized = _normalize_single_tool(tool_name, tool_data, service_name)
                normalized_tools[tool_name] = _merge_tool_data(
                    normalized_tools.get(tool_name),
                    normalized
                )
        
        # Process nested results structure (static, security)
        results = analysis.get('results', {})
        if isinstance(results, dict):
            for category, category_data in results.items():
                if not isinstance(category_data, dict):
                    continue
                
                for tool_name, tool_data in category_data.items():
                    normalized = _normalize_single_tool(tool_name, tool_data, service_name, category)
                    normalized_tools[tool_name] = _merge_tool_data(
                        normalized_tools.get(tool_name),
                        normalized
                    )
    
    return normalized_tools


def _normalize_single_tool(
    tool_name: str,
    tool_data: Any,
    service_name: str,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """Normalize a single tool's result data."""
    if not isinstance(tool_data, dict):
        return {
            'status': 'unknown',
            'findings_count': 0,
            'service': service_name
        }
    
    # Get issues count
    issues = tool_data.get('issues', [])
    findings_count = tool_data.get('total_issues')
    if findings_count is None:
        findings_count = len(issues) if isinstance(issues, list) else 0
    
    normalized = {
        'status': normalize_tool_status(tool_data.get('status', 'unknown')),
        'findings_count': findings_count,
        'service': service_name
    }
    
    # Add optional fields if present
    if category:
        normalized['category'] = category
    
    if 'exit_code' in tool_data:
        normalized['exit_code'] = tool_data['exit_code']
    
    if 'sarif_file' in tool_data:
        normalized['sarif_file'] = tool_data['sarif_file']
    elif isinstance(tool_data.get('sarif'), dict) and 'sarif_file' in tool_data['sarif']:
        normalized['sarif_file'] = tool_data['sarif']['sarif_file']
    
    if 'execution_time' in tool_data:
        normalized['execution_time'] = tool_data['execution_time']
    elif 'duration_seconds' in tool_data:
        normalized['execution_time'] = tool_data['duration_seconds']
    
    # Add severity breakdown if available
    if 'severity_breakdown' in tool_data:
        normalized['severity_breakdown'] = tool_data['severity_breakdown']
    
    return normalized


def _merge_tool_data(
    existing: Optional[Dict[str, Any]],
    new: Dict[str, Any]
) -> Dict[str, Any]:
    """Merge tool data, preserving non-empty values."""
    if not existing:
        return new
    
    merged = dict(existing)
    for key, value in new.items():
        if value is None or value == '' or value == [] or value == {}:
            continue
        
        if key == 'findings_count':
            # Sum findings counts
            merged[key] = merged.get(key, 0) + value
        elif key not in merged or merged[key] in (None, '', [], {}):
            merged[key] = value
    
    return merged


# ==============================================================================
# FINDINGS AGGREGATION
# ==============================================================================

def aggregate_findings_from_services(services: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate findings from all services into structured format.
    
    Args:
        services: Dict of service results
        
    Returns:
        Dict with:
        - findings: List of all findings (deduplicated)
        - findings_total: Total count
        - findings_by_severity: {severity: count}
        - findings_by_tool: {tool: count}
        - tools_executed: List of tool names
    """
    all_findings: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    tools_executed: Set[str] = set()
    
    for service_name, service_data in services.items():
        if not isinstance(service_data, dict):
            continue
        
        analysis = service_data.get('analysis', {})
        if not isinstance(analysis, dict):
            continue
        
        # Extract from tool_results
        tool_results = analysis.get('tool_results', {})
        if isinstance(tool_results, dict):
            for tool_name, tool_data in tool_results.items():
                tools_executed.add(tool_name)
                findings = _extract_tool_findings(tool_name, tool_data, service_name)
                _add_unique_findings(all_findings, findings, seen_ids)
        
        # Extract from nested results
        results = analysis.get('results', {})
        if isinstance(results, dict):
            for category, category_data in results.items():
                # Handle list-based results (ZAP, vulnerability scan)
                if isinstance(category_data, list):
                    for item in category_data:
                        findings = _extract_list_findings(item, service_name, category)
                        _add_unique_findings(all_findings, findings, seen_ids)
                        # Track tool if identified
                        if isinstance(item, dict) and 'alerts' in item:
                            tools_executed.add('zap')
                        elif isinstance(item, dict) and 'vulnerabilities' in item:
                            tools_executed.add('curl')
                    continue
                
                if not isinstance(category_data, dict):
                    continue
                
                for tool_name, tool_data in category_data.items():
                    tools_executed.add(tool_name)
                    findings = _extract_tool_findings(tool_name, tool_data, service_name, category)
                    _add_unique_findings(all_findings, findings, seen_ids)
    
    # Calculate aggregations
    findings_by_severity = get_severity_breakdown(all_findings)
    findings_by_tool: Dict[str, int] = {}
    for finding in all_findings:
        tool = finding.get('tool', 'unknown')
        findings_by_tool[tool] = findings_by_tool.get(tool, 0) + 1
    
    return {
        'findings': all_findings,
        'findings_total': len(all_findings),
        'findings_by_severity': findings_by_severity,
        'findings_by_tool': findings_by_tool,
        'tools_executed': sorted(list(tools_executed))
    }


def _extract_tool_findings(
    tool_name: str,
    tool_data: Any,
    service_name: str,
    category: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Extract findings from a single tool's results."""
    findings = []
    
    if not isinstance(tool_data, dict):
        return findings
    
    issues = tool_data.get('issues', [])
    if not isinstance(issues, list):
        return findings
    
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        
        # Build normalized finding
        finding = {
            'id': _generate_finding_id(tool_name, issue),
            'tool': tool_name,
            'service': service_name,
            'severity': normalize_severity(issue.get('severity')),
            'message': issue.get('message', ''),
            'file': issue.get('file', issue.get('filename', '')),
            'line': issue.get('line', issue.get('line_number', 0)),
            'rule_id': issue.get('rule_id', issue.get('test_id', ''))
        }
        
        if category:
            finding['category'] = category
        
        findings.append(finding)
    
    return findings


def _extract_list_findings(
    item: Any,
    service_name: str,
    category: str
) -> List[Dict[str, Any]]:
    """Extract findings from list-based results (ZAP, curl, etc.)."""
    findings = []
    
    if not isinstance(item, dict):
        return findings
    
    # Handle ZAP alerts
    alerts = item.get('alerts', [])
    if isinstance(alerts, list):
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            findings.append({
                'id': f"zap_{alert.get('alert', 'unknown').replace(' ', '_')}",
                'tool': 'zap',
                'service': service_name,
                'category': category,
                'severity': normalize_severity(alert.get('risk', 'info')),
                'message': alert.get('alert', ''),
                'file': alert.get('url', ''),
                'line': 0,
                'rule_id': alert.get('pluginId', '')
            })
    
    # Handle vulnerability scan results
    vulns = item.get('vulnerabilities', [])
    if isinstance(vulns, list):
        for vuln in vulns:
            if not isinstance(vuln, dict):
                continue
            findings.append({
                'id': f"curl_{vuln.get('type', 'unknown').replace(' ', '_')}",
                'tool': 'curl',
                'service': service_name,
                'category': category,
                'severity': normalize_severity(vuln.get('severity', 'info')),
                'message': f"{vuln.get('type', '')}: {vuln.get('description', '')}",
                'file': item.get('url', ''),
                'line': 0,
                'rule_id': vuln.get('type', '')
            })
    
    return findings


def _generate_finding_id(tool_name: str, issue: Dict[str, Any]) -> str:
    """Generate unique ID for a finding."""
    file_path = issue.get('file', issue.get('filename', ''))
    line = issue.get('line', issue.get('line_number', 0))
    rule = issue.get('rule_id', issue.get('test_id', ''))
    
    return f"{tool_name}_{rule}_{file_path}_{line}"


def _add_unique_findings(
    all_findings: List[Dict[str, Any]],
    new_findings: List[Dict[str, Any]],
    seen_ids: Set[str]
) -> None:
    """Add findings to list, deduplicating by ID."""
    for finding in new_findings:
        finding_id = finding.get('id', '')
        if finding_id and finding_id in seen_ids:
            continue
        if finding_id:
            seen_ids.add(finding_id)
        all_findings.append(finding)


# ==============================================================================
# SERVICE STATUS HELPERS
# ==============================================================================

def categorize_services(services: Dict[str, Any]) -> Tuple[List[str], List[str], List[str]]:
    """Categorize services by their execution status.
    
    Args:
        services: Dict of service results
        
    Returns:
        Tuple of (succeeded, partial, unreachable) service name lists
    """
    succeeded = []
    partial = []
    unreachable = []
    
    for svc_name, svc_data in services.items():
        if not isinstance(svc_data, dict):
            continue
        
        status = str(svc_data.get('status', 'unknown')).lower()
        
        if status in ('targets_unreachable', 'unreachable'):
            unreachable.append(svc_name)
        elif status in ('partial', 'partial_connectivity', 'partial_success'):
            partial.append(svc_name)
        elif status in ('success', 'completed', 'no_issues'):
            succeeded.append(svc_name)
    
    return succeeded, partial, unreachable


def determine_overall_status(
    succeeded: List[str],
    partial: List[str],
    unreachable: List[str]
) -> str:
    """Determine overall analysis status from service statuses.
    
    Returns:
        'completed', 'partial', 'targets_unreachable', or 'unknown'
    """
    if unreachable and not succeeded and not partial:
        return 'targets_unreachable'
    elif partial or (unreachable and succeeded):
        return 'partial'
    elif succeeded:
        return 'completed'
    return 'unknown'
