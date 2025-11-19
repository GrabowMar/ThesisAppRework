"""
Tool Parsers Utility
===================

This module provides specialized parsers for various analysis tools to extract
standardized findings/issues from their raw output. It is designed to support
the Tool Detail Modal in the frontend by converting complex nested JSON structures
into a flat list of issues that can be easily rendered in a table.

It ports and adapts logic from analyzer/analyzer_manager.py but focuses on
UI-friendly output formats.
"""

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

def normalize_severity(severity: Any) -> str:
    """Normalize severity levels to standard format (CRITICAL, HIGH, MEDIUM, LOW, INFO)."""
    if not severity:
        return 'INFO'
        
    severity_lower = str(severity).lower()
    
    if severity_lower in ['critical', 'fatal']:
        return 'CRITICAL'
    elif severity_lower in ['high', 'error', 'severe']:
        return 'HIGH'
    elif severity_lower in ['medium', 'warning', 'warn', 'moderate']:
        return 'MEDIUM'
    elif severity_lower in ['low', 'info', 'note', 'informational', 'minor']:
        return 'LOW'
    else:
        return 'INFO'

def extract_tool_findings(service_type: str, tool_name: str, analysis_block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract findings from a tool's analysis block based on service type and tool name.
    
    Args:
        service_type: The type of service (static, dynamic, performance, ai)
        tool_name: The name of the tool (bandit, zap, locust, etc.)
        analysis_block: The raw analysis dictionary containing 'results' or 'tool_results'
        
    Returns:
        List of flattened finding dictionaries suitable for UI display
    """
    if not analysis_block or not isinstance(analysis_block, dict):
        return []

    # Handle different result structures
    # Some services put results in 'results', others in 'tool_results', or directly in the block
    results_data = analysis_block.get('results', {})
    if not results_data and 'tool_results' in analysis_block:
        results_data = analysis_block.get('tool_results', {})
    
    # If results_data is empty, try using the block itself (for some formats)
    if not results_data:
        results_data = analysis_block

    tool_key = tool_name.lower()
    service_key = service_type.lower()

    try:
        if service_key == 'dynamic':
            return _extract_dynamic_findings(tool_key, results_data)
        elif service_key == 'performance':
            return _extract_performance_findings(tool_key, results_data)
        elif service_key == 'static':
            return _extract_static_findings(tool_key, results_data)
        elif service_key == 'ai':
            return _extract_ai_findings(tool_key, results_data)
            
    except Exception as e:
        logger.error(f"Error extracting findings for {tool_name} ({service_type}): {e}")
        return []

    return []

# =============================================================================
# DYNAMIC ANALYSIS PARSERS
# =============================================================================

def _extract_dynamic_findings(tool_name: str, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract findings from dynamic analysis tools (ZAP, Curl, Nmap, etc.)."""
    findings = []
    
    # ZAP (OWASP Zed Attack Proxy)
    if tool_name == 'zap':
        # Check for 'zap_security_scan' list
        zap_scans = results.get('zap_security_scan', [])
        if isinstance(zap_scans, list):
            for scan in zap_scans:
                if not isinstance(scan, dict):
                    continue
                    
                base_url = scan.get('url', 'unknown')
                
                # Format 1: vulnerabilities list
                vulnerabilities = scan.get('vulnerabilities', [])
                if isinstance(vulnerabilities, list):
                    for vuln in vulnerabilities:
                        findings.append({
                            'severity': normalize_severity(vuln.get('severity', 'medium')),
                            'rule_id': vuln.get('type', 'ZAP Alert'),
                            'file': base_url,
                            'line': '-',
                            'description': vuln.get('description', ''),
                            'message': vuln.get('type', ''),
                            'solution': vuln.get('recommendation', ''),
                            'cwe': f"CWE-{vuln.get('cweid')}" if vuln.get('cweid') else ''
                        })
                
                # Format 2: alerts_by_risk dictionary (raw ZAP output)
                alerts_by_risk = scan.get('alerts_by_risk', {})
                if isinstance(alerts_by_risk, dict):
                    for risk, alerts in alerts_by_risk.items():
                        for alert in alerts:
                            findings.append({
                                'severity': normalize_severity(risk),
                                'rule_id': alert.get('alert', 'ZAP Alert'),
                                'file': alert.get('url', base_url),
                                'line': '-',
                                'description': alert.get('description', ''),
                                'message': alert.get('name', alert.get('alert', '')),
                                'solution': alert.get('solution', ''),
                                'cwe': f"CWE-{alert.get('cweid')}" if alert.get('cweid') else '',
                                'evidence': alert.get('evidence', '')
                            })

    # Curl / Connectivity / Vulnerability Scan
    elif tool_name in ('curl', 'connectivity', 'vulnerability_scan', 'vulnscan', 'dirsearch'):
        # Connectivity checks
        connectivity_results = results.get('connectivity', [])
        if isinstance(connectivity_results, list):
            for entry in connectivity_results:
                analysis = entry.get('analysis', {})
                if not isinstance(analysis, dict):
                    continue
                    
                url = analysis.get('url', '')
                headers = analysis.get('security_headers', {})
                
                # Missing security headers
                missing_headers = [h for h, present in headers.items() if not present]
                if missing_headers:
                    findings.append({
                        'severity': 'LOW',
                        'rule_id': 'missing-security-headers',
                        'file': url,
                        'line': '-',
                        'description': f"Missing security headers: {', '.join(missing_headers)}",
                        'message': 'Missing Security Headers',
                        'solution': 'Configure the server to send these security headers.'
                    })

        # Vulnerability scans (exposed paths)
        vuln_scans = results.get('vulnerability_scan', [])
        if isinstance(vuln_scans, list):
            for scan in vuln_scans:
                url = scan.get('url', '')
                for vuln in scan.get('vulnerabilities', []):
                    # Exposed paths
                    if vuln.get('type') == 'exposed_paths':
                        for path_info in vuln.get('paths', []):
                            findings.append({
                                'severity': normalize_severity(vuln.get('severity', 'low')),
                                'rule_id': 'exposed-sensitive-path',
                                'file': path_info.get('url', url),
                                'line': str(path_info.get('status', '-')),
                                'description': f"Exposed sensitive path: {path_info.get('path')}",
                                'message': 'Exposed Path',
                                'solution': 'Restrict access to this path.'
                            })
                    else:
                        # Generic vulnerability
                        findings.append({
                            'severity': normalize_severity(vuln.get('severity', 'low')),
                            'rule_id': vuln.get('type', 'vulnerability'),
                            'file': url,
                            'line': '-',
                            'description': vuln.get('description', ''),
                            'message': vuln.get('type', 'Vulnerability'),
                            'solution': ''
                        })

    # Nmap / Port Scan
    elif tool_name in ('nmap', 'portscan', 'port-scan'):
        port_scan = results.get('port_scan', {})
        if isinstance(port_scan, dict):
            host = port_scan.get('host', 'unknown')
            open_ports = port_scan.get('open_ports', [])
            for port in open_ports:
                severity = 'MEDIUM' if port in [21, 23, 3389] else 'INFO'
                findings.append({
                    'severity': severity,
                    'rule_id': 'open-port',
                    'file': f"{host}:{port}",
                    'line': str(port),
                    'description': f"Port {port} is open.",
                    'message': f"Open Port {port}",
                    'solution': 'Verify if this port needs to be exposed.'
                })

    return findings

# =============================================================================
# PERFORMANCE ANALYSIS PARSERS
# =============================================================================

def _extract_performance_findings(tool_name: str, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract findings from performance analysis tools (Locust, etc.)."""
    findings = []
    
    # Thresholds
    THRESHOLDS = {
        'avg_response_time': 500,  # ms
        'requests_per_second': 20, # req/s (minimum)
        'failed_requests': 0
    }
    
    # Look for tool_runs
    tool_runs = results.get('tool_runs', {})
    
    # If tool_runs is empty, maybe the results are directly in the dict (legacy format)
    if not tool_runs and 'avg_response_time' in results:
        tool_runs = {tool_name: results}

    for t_name, t_result in tool_runs.items():
        # Filter by tool name if provided and matches
        if tool_name and tool_name not in t_name.lower() and t_name.lower() not in tool_name:
            continue
            
        if not isinstance(t_result, dict):
            continue

        url = t_result.get('url', 'unknown')
        
        # 1. Failed Requests
        failed = t_result.get('failed_requests', 0)
        if failed > THRESHOLDS['failed_requests']:
            findings.append({
                'severity': 'HIGH',
                'rule_id': 'high-failure-rate',
                'file': url,
                'line': '-',
                'description': f"Recorded {failed} failed requests during the test run.",
                'message': 'Request Failures',
                'solution': 'Check server logs for errors (5xx) or timeouts.',
                'metric': f"{failed} failures"
            })
            
        # 2. Slow Response Time
        avg_time = t_result.get('avg_response_time')
        if avg_time and avg_time > THRESHOLDS['avg_response_time']:
            findings.append({
                'severity': 'MEDIUM',
                'rule_id': 'slow-response-time',
                'file': url,
                'line': '-',
                'description': f"Average response time ({avg_time:.2f}ms) exceeds threshold ({THRESHOLDS['avg_response_time']}ms).",
                'message': 'Slow Response',
                'solution': 'Optimize database queries or code performance.',
                'metric': f"{avg_time:.2f}ms"
            })
            
        # 3. Low Throughput
        rps = t_result.get('requests_per_second')
        if rps is not None and rps < THRESHOLDS['requests_per_second']:
            findings.append({
                'severity': 'MEDIUM',
                'rule_id': 'low-throughput',
                'file': url,
                'line': '-',
                'description': f"Throughput ({rps:.2f} req/s) is below target ({THRESHOLDS['requests_per_second']} req/s).",
                'message': 'Low Throughput',
                'solution': 'Check for bottlenecks or resource constraints.',
                'metric': f"{rps:.2f} req/s"
            })

    return findings

# =============================================================================
# STATIC ANALYSIS PARSERS
# =============================================================================

def _extract_static_findings(tool_name: str, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract findings from static analysis tools (Bandit, ESLint, etc.)."""
    findings = []
    
    # Determine language category based on tool
    # The results structure is usually: { 'python': { 'bandit': ... }, 'javascript': { 'eslint': ... } }
    # But here 'results' might be the inner dict for the specific tool if pre-filtered,
    # or the top-level dict.
    
    # Helper to find tool data recursively
    def find_tool_data(data, t_name):
        if not isinstance(data, dict):
            return None
        if t_name in data:
            return data[t_name]
        for key, value in data.items():
            if isinstance(value, dict):
                found = find_tool_data(value, t_name)
                if found:
                    return found
        return None

    tool_data = find_tool_data(results, tool_name)
    if not tool_data:
        # Maybe 'results' IS the tool data
        tool_data = results

    # Bandit
    if tool_name == 'bandit':
        issues = tool_data.get('issues', [])
        for issue in issues:
            findings.append({
                'severity': normalize_severity(issue.get('issue_severity')),
                'rule_id': issue.get('test_id'),
                'file': issue.get('filename', '').replace('/app/sources/', ''),
                'line': issue.get('line_number'),
                'description': issue.get('issue_text'),
                'message': issue.get('test_name'),
                'cwe': f"CWE-{issue.get('issue_cwe', {}).get('id')}" if issue.get('issue_cwe') else '',
                'link': issue.get('more_info')
            })

    # ESLint
    elif tool_name == 'eslint':
        # ESLint results are usually a list of file objects
        eslint_results = tool_data.get('results', [])
        if isinstance(eslint_results, list):
            for file_result in eslint_results:
                file_path = file_result.get('filePath', '').replace('/app/sources/', '')
                for msg in file_result.get('messages', []):
                    findings.append({
                        'severity': normalize_severity('HIGH' if msg.get('severity') == 2 else 'MEDIUM'),
                        'rule_id': msg.get('ruleId'),
                        'file': file_path,
                        'line': msg.get('line'),
                        'description': msg.get('message'),
                        'message': msg.get('ruleId'),
                        'solution': 'Fix linting error'
                    })

    # Pylint
    elif tool_name == 'pylint':
        issues = tool_data.get('issues', [])
        for issue in issues:
            findings.append({
                'severity': normalize_severity(issue.get('type')),
                'rule_id': issue.get('message-id'),
                'file': issue.get('path', ''),
                'line': issue.get('line'),
                'description': issue.get('message'),
                'message': issue.get('symbol'),
                'solution': ''
            })
            
    # Semgrep
    elif tool_name == 'semgrep':
        semgrep_results = tool_data.get('results', [])
        for res in semgrep_results:
            extra = res.get('extra', {})
            findings.append({
                'severity': normalize_severity(extra.get('severity')),
                'rule_id': res.get('check_id'),
                'file': res.get('path', '').replace('/app/sources/', ''),
                'line': res.get('start', {}).get('line'),
                'description': extra.get('message'),
                'message': res.get('check_id'),
                'solution': extra.get('fix', ''),
                'cwe': (extra.get('metadata', {}).get('cwe', []) + [''])[0]
            })

    # Stylelint
    elif tool_name == 'stylelint':
        style_results = tool_data.get('results', [])
        if isinstance(style_results, list):
            for file_result in style_results:
                file_path = file_result.get('source', '').replace('/app/sources/', '')
                for warn in file_result.get('warnings', []):
                    findings.append({
                        'severity': normalize_severity(warn.get('severity')),
                        'rule_id': warn.get('rule'),
                        'file': file_path,
                        'line': warn.get('line'),
                        'description': warn.get('text'),
                        'message': warn.get('rule'),
                        'solution': ''
                    })

    return findings

# =============================================================================
# AI ANALYSIS PARSERS
# =============================================================================

def _extract_ai_findings(tool_name: str, results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract findings from AI analysis."""
    findings = []
    
    # AI Analyzer usually returns 'requirement_checks' inside 'results'
    # But sometimes 'results' is the top level dict passed here
    
    # Check if we have the 'analysis' wrapper or just the inner results
    analysis_data = results.get('analysis', results)
    inner_results = analysis_data.get('results', analysis_data)
    
    checks = inner_results.get('requirement_checks', [])
    
    for check in checks:
        result = check.get('result', {})
        if not result.get('met', True):
            findings.append({
                'severity': normalize_severity(result.get('confidence', 'MEDIUM')),
                'rule_id': 'requirement-not-met',
                'file': 'requirements.txt', # Virtual file
                'line': '-',
                'description': check.get('requirement', ''),
                'message': 'Requirement Not Met',
                'solution': result.get('explanation', ''),
                'confidence': result.get('confidence')
            })
            
    return findings
