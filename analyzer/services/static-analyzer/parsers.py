"""
Tool-specific output parsers for static analysis results.

Each parser standardizes tool output into a common format:
{
    'tool': str,
    'executed': bool,
    'status': 'success' | 'error' | 'no_issues',
    'issues': list[dict],
    'total_issues': int,
    'severity_breakdown': dict,
    'metrics': dict (optional),
    'config_used': dict (optional)
}
"""

from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class BanditParser:
    """Parser for Bandit JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse Bandit JSON output.
        
        Bandit JSON structure:
        {
            "results": [
                {
                    "code": "...",
                    "col_offset": 0,
                    "end_col_offset": 50,
                    "filename": "path/to/file.py",
                    "issue_confidence": "HIGH" | "MEDIUM" | "LOW",
                    "issue_cwe": {"id": 123, "link": "..."},
                    "issue_severity": "HIGH" | "MEDIUM" | "LOW",
                    "issue_text": "Description of the issue",
                    "line_number": 10,
                    "line_range": [10, 12],
                    "more_info": "https://...",
                    "test_id": "B201",
                    "test_name": "flask_debug_true"
                }
            ],
            "metrics": {
                "path/to/file.py": {
                    "CONFIDENCE.HIGH": 2,
                    "SEVERITY.HIGH": 1,
                    "SEVERITY.MEDIUM": 1,
                    "loc": 100,
                    "nosec": 0
                }
            }
        }
        """
        if not isinstance(raw_output, dict):
            return {
                'tool': 'bandit',
                'executed': True,
                'status': 'error',
                'error': 'Invalid output format',
                'issues': [],
                'total_issues': 0
            }
        
        results = raw_output.get('results', [])
        metrics = raw_output.get('metrics', {})
        
        # Standardize issues
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for issue in results:
            severity = issue.get('issue_severity', 'MEDIUM').lower()
            if severity in severity_breakdown:
                severity_breakdown[severity] += 1
            
            standardized = {
                'file': issue.get('filename', ''),
                'line': issue.get('line_number', 0),
                'column': issue.get('col_offset', 0),
                'severity': severity,
                'confidence': issue.get('issue_confidence', 'MEDIUM').lower(),
                'message': issue.get('issue_text', ''),
                'rule': issue.get('test_id', ''),
                'rule_name': issue.get('test_name', ''),
                'code_snippet': issue.get('code', ''),
                'more_info': issue.get('more_info', ''),
                'cwe': issue.get('issue_cwe', {})
            }
            issues.append(standardized)
        
        return {
            'tool': 'bandit',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'metrics': metrics,
            'config_used': config or {}
        }


class SafetyParser:
    """Parser for Safety JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse Safety JSON output.
        
        Safety 3.x JSON structure:
        {
            "report_meta": {...},
            "scanned_packages": [...],
            "affected_packages": [...],
            "announcements": [...],
            "vulnerabilities": [
                {
                    "vulnerability_id": "...",
                    "package_name": "django",
                    "ignored": false,
                    "ignored_reason": null,
                    "ignored_expires": null,
                    "vulnerable_spec": ["<2.2.10"],
                    "all_vulnerable_specs": [...],
                    "analyzed_version": "2.2.0",
                    "advisory": "...",
                    "is_transitive": false,
                    "published_date": "2020-02-03",
                    "fixed_versions": ["2.2.10", "3.0.3"],
                    "closest_versions_without_known_vulnerabilities": [...],
                    "resources": [...],
                    "CVE": "CVE-2020-7471",
                    "severity": {"source": "cvss", "cvssv3": {...}},
                    "affected_versions": [...],
                    "more_info_url": "..."
                }
            ]
        }
        """
        if not isinstance(raw_output, dict):
            return {
                'tool': 'safety',
                'executed': True,
                'status': 'error',
                'error': 'Invalid output format',
                'issues': [],
                'total_issues': 0
            }
        
        vulnerabilities = raw_output.get('vulnerabilities', [])
        
        # Standardize issues
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for vuln in vulnerabilities:
            # Map CVSS score to severity
            severity = 'medium'
            cvss_data = vuln.get('severity', {}).get('cvssv3', {})
            if cvss_data:
                base_score = cvss_data.get('base_score', 5.0)
                if base_score >= 7.0:
                    severity = 'high'
                elif base_score < 4.0:
                    severity = 'low'
            
            severity_breakdown[severity] += 1
            
            standardized = {
                'package': vuln.get('package_name', ''),
                'installed_version': vuln.get('analyzed_version', ''),
                'affected_versions': vuln.get('vulnerable_spec', []),
                'fixed_versions': vuln.get('fixed_versions', []),
                'vulnerability_id': vuln.get('vulnerability_id', ''),
                'cve': vuln.get('CVE', ''),
                'severity': severity,
                'cvss_score': cvss_data.get('base_score') if cvss_data else None,
                'message': vuln.get('advisory', ''),
                'published_date': vuln.get('published_date', ''),
                'more_info': vuln.get('more_info_url', ''),
                'is_transitive': vuln.get('is_transitive', False)
            }
            issues.append(standardized)
        
        return {
            'tool': 'safety',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'scanned_packages': raw_output.get('scanned_packages', []),
            'config_used': config or {}
        }


class PylintParser:
    """Parser for Pylint JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse Pylint JSON output.
        
        Pylint JSON structure (array of messages):
        [
            {
                "type": "convention" | "refactor" | "warning" | "error" | "fatal",
                "module": "module_name",
                "obj": "function_or_class_name",
                "line": 10,
                "column": 5,
                "endLine": 10,
                "endColumn": 20,
                "path": "path/to/file.py",
                "symbol": "line-too-long",
                "message": "Line too long (100/80)",
                "message-id": "C0301"
            }
        ]
        """
        if not isinstance(raw_output, list):
            raw_output = []
        
        # Map Pylint types to severity
        severity_map = {
            'fatal': 'high',
            'error': 'high',
            'warning': 'medium',
            'refactor': 'low',
            'convention': 'low',
            'info': 'low'
        }
        
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for msg in raw_output:
            msg_type = msg.get('type', 'warning')
            severity = severity_map.get(msg_type, 'medium')
            severity_breakdown[severity] += 1
            
            standardized = {
                'file': msg.get('path', ''),
                'line': msg.get('line', 0),
                'column': msg.get('column', 0),
                'end_line': msg.get('endLine'),
                'end_column': msg.get('endColumn'),
                'severity': severity,
                'type': msg_type,
                'message': msg.get('message', ''),
                'rule': msg.get('message-id', ''),
                'symbol': msg.get('symbol', ''),
                'module': msg.get('module', ''),
                'obj': msg.get('obj', '')
            }
            issues.append(standardized)
        
        return {
            'tool': 'pylint',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'config_used': config or {}
        }


class Flake8Parser:
    """Parser for Flake8 JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse Flake8 JSON output (requires flake8-json plugin).
        
        Flake8 JSON structure:
        {
            "path/to/file.py": [
                {
                    "code": "E501",
                    "filename": "path/to/file.py",
                    "line_number": 10,
                    "column_number": 80,
                    "text": "line too long (100 > 79 characters)",
                    "physical_line": "...",
                    "source": "pycodestyle"
                }
            ]
        }
        """
        if not isinstance(raw_output, dict):
            return {
                'tool': 'flake8',
                'executed': True,
                'status': 'error',
                'error': 'Invalid output format',
                'issues': [],
                'total_issues': 0
            }
        
        # Map error codes to severity
        def get_severity(code: str) -> str:
            if code.startswith('E') or code.startswith('F'):
                return 'high'  # Errors and fatal
            elif code.startswith('W'):
                return 'medium'  # Warnings
            else:
                return 'low'  # Convention, complexity
        
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for file_path, file_issues in raw_output.items():
            if not isinstance(file_issues, list):
                continue
                
            for issue in file_issues:
                code = issue.get('code', 'E999')
                severity = get_severity(code)
                severity_breakdown[severity] += 1
                
                standardized = {
                    'file': issue.get('filename', file_path),
                    'line': issue.get('line_number', 0),
                    'column': issue.get('column_number', 0),
                    'severity': severity,
                    'message': issue.get('text', ''),
                    'rule': code,
                    'source': issue.get('source', 'flake8'),
                    'physical_line': issue.get('physical_line', '')
                }
                issues.append(standardized)
        
        return {
            'tool': 'flake8',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'config_used': config or {}
        }


class ESLintParser:
    """Parser for ESLint JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse ESLint JSON output.
        
        ESLint JSON structure:
        [
            {
                "filePath": "/path/to/file.js",
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,  # 1=warning, 2=error
                        "message": "'foo' is defined but never used.",
                        "line": 5,
                        "column": 10,
                        "nodeType": "Identifier",
                        "messageId": "unusedVar",
                        "endLine": 5,
                        "endColumn": 15
                    }
                ],
                "suppressedMessages": [],
                "errorCount": 1,
                "fatalErrorCount": 0,
                "warningCount": 0,
                "fixableErrorCount": 0,
                "fixableWarningCount": 0,
                "source": "..."
            }
        ]
        """
        if not isinstance(raw_output, list):
            return {
                'tool': 'eslint',
                'executed': True,
                'status': 'error',
                'error': 'Invalid output format',
                'issues': [],
                'total_issues': 0
            }
        
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for file_result in raw_output:
            file_path = file_result.get('filePath', '')
            messages = file_result.get('messages', [])
            
            for msg in messages:
                # ESLint severity: 1=warning, 2=error
                eslint_severity = msg.get('severity', 1)
                severity = 'high' if eslint_severity == 2 else 'medium'
                severity_breakdown[severity] += 1
                
                standardized = {
                    'file': file_path,
                    'line': msg.get('line', 0),
                    'column': msg.get('column', 0),
                    'end_line': msg.get('endLine'),
                    'end_column': msg.get('endColumn'),
                    'severity': severity,
                    'message': msg.get('message', ''),
                    'rule': msg.get('ruleId', ''),
                    'node_type': msg.get('nodeType', ''),
                    'message_id': msg.get('messageId', '')
                }
                issues.append(standardized)
        
        return {
            'tool': 'eslint',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'config_used': config or {}
        }


class SemgrepParser:
    """Parser for Semgrep JSON output."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse Semgrep JSON output.
        
        Semgrep JSON structure:
        {
            "results": [
                {
                    "check_id": "python.lang.security.audit.dangerous-system-call",
                    "path": "app.py",
                    "start": {"line": 10, "col": 5, "offset": 200},
                    "end": {"line": 10, "col": 25, "offset": 220},
                    "extra": {
                        "message": "Detected dangerous system call",
                        "metadata": {...},
                        "severity": "ERROR" | "WARNING" | "INFO",
                        "lines": "os.system(user_input)"
                    }
                }
            ],
            "errors": []
        }
        """
        if not isinstance(raw_output, dict):
            return {
                'tool': 'semgrep',
                'executed': True,
                'status': 'error',
                'error': 'Invalid output format',
                'issues': [],
                'total_issues': 0
            }
        
        results = raw_output.get('results', [])
        
        # Map Semgrep severity
        severity_map = {
            'ERROR': 'high',
            'WARNING': 'medium',
            'INFO': 'low'
        }
        
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for finding in results:
            extra = finding.get('extra', {})
            semgrep_severity = extra.get('severity', 'WARNING')
            severity = severity_map.get(semgrep_severity, 'medium')
            severity_breakdown[severity] += 1
            
            start = finding.get('start', {})
            end = finding.get('end', {})
            
            standardized = {
                'file': finding.get('path', ''),
                'line': start.get('line', 0),
                'column': start.get('col', 0),
                'end_line': end.get('line'),
                'end_column': end.get('col'),
                'severity': severity,
                'message': extra.get('message', ''),
                'rule': finding.get('check_id', ''),
                'code_snippet': extra.get('lines', ''),
                'metadata': extra.get('metadata', {})
            }
            issues.append(standardized)
        
        return {
            'tool': 'semgrep',
            'executed': True,
            'status': 'success' if issues else 'no_issues',
            'issues': issues,
            'total_issues': len(issues),
            'severity_breakdown': severity_breakdown,
            'errors': raw_output.get('errors', []),
            'config_used': config or {}
        }


# Parser registry
PARSERS = {
    'bandit': BanditParser,
    'safety': SafetyParser,
    'pylint': PylintParser,
    'flake8': Flake8Parser,
    'eslint': ESLintParser,
    'semgrep': SemgrepParser
}


def parse_tool_output(tool_name: str, raw_output: Any, config: Optional[Dict] = None) -> Dict:
    """
    Parse tool output using the appropriate parser.
    
    Args:
        tool_name: Name of the tool (e.g., 'bandit', 'eslint')
        raw_output: Raw JSON output from the tool
        config: Optional configuration used for the tool
    
    Returns:
        Standardized result dictionary
    """
    parser_class = PARSERS.get(tool_name)
    
    if not parser_class:
        logger.warning(f"No parser found for tool: {tool_name}")
        return {
            'tool': tool_name,
            'executed': True,
            'status': 'error',
            'error': f'No parser available for {tool_name}',
            'issues': [],
            'total_issues': 0
        }
    
    try:
        return parser_class.parse(raw_output, config)
    except Exception as e:
        logger.error(f"Error parsing {tool_name} output: {e}")
        return {
            'tool': tool_name,
            'executed': True,
            'status': 'error',
            'error': f'Parser error: {str(e)}',
            'issues': [],
            'total_issues': 0
        }
