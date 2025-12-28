"""
SARIF 2.1.0 Compliant Parsers for Static Analysis Tools
=======================================================

Converts tool-specific output formats into SARIF (Static Analysis Results 
Interchange Format) 2.1.0 compliant JSON structure.

SARIF Specification: https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html

Key SARIF Concepts:
- Run: Output from a single tool execution
- Result: A single finding/issue
- Level: note (info) | warning | error
- Location: File path, line number, column
- Rule: The check/test that was violated
"""

from typing import Dict, Any, Optional, List
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Severity mapping to SARIF levels
SEVERITY_TO_LEVEL = {
    'critical': 'error',
    'high': 'error',
    'medium': 'warning',
    'low': 'warning',
    'info': 'note',
    'informational': 'note'
}


class SARIFBuilder:
    """Helper class for building SARIF 2.1.0 documents."""
    
    @staticmethod
    def create_run(tool_name: str, tool_version: str = "unknown") -> Dict[str, Any]:
        """Create a SARIF run structure."""
        return {
            "tool": {
                "driver": {
                    "name": tool_name,
                    "version": tool_version,
                    "informationUri": f"https://github.com/PyCQA/{tool_name}",
                }
            },
            "results": [],
            "invocations": [{
                "executionSuccessful": True,
                "endTimeUtc": datetime.now(timezone.utc).isoformat()
            }]
        }
    
    @staticmethod
    def create_result(
        rule_id: str,
        message: str,
        level: str,
        file_path: Optional[str] = None,
        line_number: Optional[int] = None,
        column: Optional[int] = None,
        severity: Optional[str] = None,
        confidence: Optional[str] = None,
        cwe: Optional[List[int]] = None,
        code_snippet: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a SARIF result (finding)."""
        result = {
            "ruleId": rule_id,
            "level": level,
            "message": {
                "text": message
            }
        }
        
        # Add location if available
        if file_path:
            location = {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": file_path
                    }
                }
            }
            
            if line_number or column:
                region = {}
                if line_number:
                    region["startLine"] = line_number
                if column:
                    region["startColumn"] = column
                if code_snippet:
                    region["snippet"] = {"text": code_snippet}
                location["physicalLocation"]["region"] = region
            
            result["locations"] = [location]
        
        # Add properties for tool-specific metadata
        properties = {}
        if severity:
            properties["severity"] = severity
        if confidence:
            properties["confidence"] = confidence
        if cwe:
            properties["cwe"] = cwe
        
        if properties:
            result["properties"] = properties
        
        return result


class BanditSARIFParser:
    """Parse Bandit JSON output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Bandit JSON output to SARIF 2.1.0 format.
        
        Bandit JSON structure:
        {
            "results": [{
                "filename": "path/to/file.py",
                "line_number": 10,
                "col_offset": 0,
                "test_id": "B201",
                "test_name": "flask_debug_true",
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "issue_text": "Description",
                "issue_cwe": {"id": 78},
                "code": "code snippet"
            }]
        }
        """
        if not isinstance(raw_output, dict):
            logger.error("Invalid Bandit output format")
            return SARIFBuilder.create_run("bandit")
        
        # Extract version if available
        version = raw_output.get('version', 'unknown')
        run = SARIFBuilder.create_run("bandit", version)
        
        results = raw_output.get('results', [])
        
        for issue in results:
            severity = issue.get('issue_severity', 'MEDIUM').lower()
            level = SEVERITY_TO_LEVEL.get(severity, 'warning')
            
            # Extract CWE ID
            cwe_ids = []
            issue_cwe = issue.get('issue_cwe')
            if isinstance(issue_cwe, dict) and 'id' in issue_cwe:
                cwe_ids.append(int(issue_cwe['id']))
            
            result = SARIFBuilder.create_result(
                rule_id=issue.get('test_id', 'UNKNOWN'),
                message=issue.get('issue_text', 'No description'),
                level=level,
                file_path=issue.get('filename'),
                line_number=issue.get('line_number'),
                column=issue.get('col_offset'),
                severity=severity,
                confidence=issue.get('issue_confidence', '').lower(),
                cwe=cwe_ids if cwe_ids else None,
                code_snippet=issue.get('code')
            )
            
            run["results"].append(result)
        
        return run


class PyLintSARIFParser:
    """Parse PyLint JSON output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: List[Dict[str, Any]], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert PyLint JSON output to SARIF 2.1.0 format.
        
        PyLint JSON structure (list of dicts):
        [{
            "type": "convention" | "refactor" | "warning" | "error" | "fatal",
            "module": "module_name",
            "obj": "function_name",
            "line": 10,
            "column": 5,
            "endLine": 10,
            "endColumn": 20,
            "path": "path/to/file.py",
            "symbol": "missing-docstring",
            "message": "Missing function docstring",
            "message-id": "C0116"
        }]
        """
        if not isinstance(raw_output, list):
            logger.error("Invalid PyLint output format")
            return SARIFBuilder.create_run("pylint")
        
        run = SARIFBuilder.create_run("pylint")
        
        # Map PyLint types to SARIF levels
        TYPE_TO_LEVEL = {
            'fatal': 'error',
            'error': 'error',
            'warning': 'warning',
            'refactor': 'note',
            'convention': 'note'
        }
        
        for issue in raw_output:
            issue_type = issue.get('type', 'warning')
            level = TYPE_TO_LEVEL.get(issue_type, 'warning')
            
            # Build message with context
            message = issue.get('message', 'No description')
            if issue.get('obj'):
                message = f"{issue['obj']}: {message}"
            
            result = SARIFBuilder.create_result(
                rule_id=issue.get('message-id', issue.get('symbol', 'UNKNOWN')),
                message=message,
                level=level,
                file_path=issue.get('path'),
                line_number=issue.get('line'),
                column=issue.get('column'),
                severity=issue_type
            )
            
            run["results"].append(result)
        
        return run


class ESLintSARIFParser:
    """Parse ESLint SARIF output (ESLint has native SARIF formatter)."""
    
    @staticmethod
    def parse(raw_output: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        ESLint can output SARIF natively with --format @microsoft/eslint-formatter-sarif.
        This parser handles the SARIF output and validates/normalizes it.
        """
        if not isinstance(raw_output, dict):
            logger.error("Invalid ESLint SARIF output format")
            return SARIFBuilder.create_run("eslint")
        
        # If already SARIF format, validate and return first run
        if raw_output.get('version') == '2.1.0' and 'runs' in raw_output:
            runs = raw_output.get('runs', [])
            if runs:
                return runs[0]  # Return first run
        
        # Fallback: parse standard ESLint JSON format
        if isinstance(raw_output, list):
            return ESLintSARIFParser._parse_json_format(raw_output)
        
        return SARIFBuilder.create_run("eslint")
    
    @staticmethod
    def _parse_json_format(raw_output: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parse standard ESLint JSON format to SARIF.
        
        ESLint JSON structure:
        [{
            "filePath": "path/to/file.js",
            "messages": [{
                "ruleId": "no-unused-vars",
                "severity": 1 | 2,  # 1=warning, 2=error
                "message": "Variable is defined but never used",
                "line": 10,
                "column": 5,
                "nodeType": "Identifier",
                "messageId": "unusedVar"
            }]
        }]
        """
        run = SARIFBuilder.create_run("eslint")
        
        for file_result in raw_output:
            file_path = file_result.get('filePath', '')
            messages = file_result.get('messages', [])
            
            for msg in messages:
                severity = msg.get('severity', 1)
                level = 'error' if severity == 2 else 'warning'
                
                result = SARIFBuilder.create_result(
                    rule_id=msg.get('ruleId', 'UNKNOWN'),
                    message=msg.get('message', 'No description'),
                    level=level,
                    file_path=file_path,
                    line_number=msg.get('line'),
                    column=msg.get('column'),
                    severity='high' if severity == 2 else 'medium'
                )
                
                run["results"].append(result)
        
        return run


class SafetySARIFParser:
    """Parse Safety vulnerability scanner output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: List[List], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Safety JSON output to SARIF 2.1.0 format.
        
        Safety JSON structure:
        [
            [
                "package_name",
                "version",
                [
                    "vulnerability_id",
                    "cve",
                    "affected_versions",
                    "advisory_text"
                ]
            ]
        ]
        """
        if not isinstance(raw_output, list):
            logger.error("Invalid Safety output format")
            return SARIFBuilder.create_run("safety")
        
        run = SARIFBuilder.create_run("safety")
        
        for vuln in raw_output:
            if not isinstance(vuln, list) or len(vuln) < 3:
                continue
            
            package_name = vuln[0]
            package_version = vuln[1]
            vuln_details = vuln[2] if len(vuln) > 2 else []
            
            if not isinstance(vuln_details, list) or len(vuln_details) < 4:
                continue
            
            vuln_id = vuln_details[0]
            cve = vuln_details[1] if len(vuln_details) > 1 else ""
            affected_versions = vuln_details[2] if len(vuln_details) > 2 else ""
            advisory = vuln_details[3] if len(vuln_details) > 3 else "Security vulnerability"
            
            message = f"{package_name}=={package_version}: {advisory}"
            
            # Extract CVE number for CWE mapping (if available)
            cwe_ids = []
            # Note: Safety doesn't provide CWE directly, would need CVE→CWE lookup
            
            result = SARIFBuilder.create_result(
                rule_id=vuln_id or 'SAFETY-UNKNOWN',
                message=message,
                level='error',  # All vulnerabilities are errors
                file_path='requirements.txt',  # Synthetic location
                severity='high',  # Dependencies are critical
                cwe=cwe_ids if cwe_ids else None
            )
            
            # Add vulnerability-specific properties
            result["properties"]["package"] = package_name
            result["properties"]["installed_version"] = package_version
            result["properties"]["affected_versions"] = affected_versions
            if cve:
                result["properties"]["cve"] = cve
            
            run["results"].append(result)
        
        return run


class SemgrepSARIFParser:
    """Parse Semgrep SARIF output (Semgrep has native --sarif flag)."""
    
    @staticmethod
    def parse(raw_output: Dict[str, Any], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Semgrep can output SARIF natively with --sarif flag.
        This parser validates and normalizes the output.
        """
        if not isinstance(raw_output, dict):
            logger.error("Invalid Semgrep SARIF output format")
            return SARIFBuilder.create_run("semgrep")
        
        # If already SARIF format, return first run
        if raw_output.get('version') == '2.1.0' and 'runs' in raw_output:
            runs = raw_output.get('runs', [])
            if runs:
                return runs[0]
        
        # Fallback: parse standard Semgrep JSON format
        if 'results' in raw_output:
            return SemgrepSARIFParser._parse_json_format(raw_output)
        
        return SARIFBuilder.create_run("semgrep")
    
    @staticmethod
    def _parse_json_format(raw_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Parse standard Semgrep JSON format to SARIF.
        
        Semgrep JSON structure:
        {
            "results": [{
                "check_id": "python.django.security.injection.sql-injection",
                "path": "path/to/file.py",
                "start": {"line": 10, "col": 5},
                "end": {"line": 10, "col": 30},
                "extra": {
                    "message": "SQL injection vulnerability",
                    "severity": "ERROR" | "WARNING" | "INFO",
                    "metadata": {
                        "cwe": ["CWE-89"],
                        "owasp": ["A1:2017-Injection"]
                    }
                }
            }]
        }
        """
        run = SARIFBuilder.create_run("semgrep")
        
        results = raw_output.get('results', [])
        
        for finding in results:
            extra = finding.get('extra', {})
            severity = extra.get('severity', 'WARNING')
            
            # Map Semgrep severity to SARIF level
            level_map = {
                'ERROR': 'error',
                'WARNING': 'warning',
                'INFO': 'note'
            }
            level = level_map.get(severity, 'warning')
            
            # Extract CWE from metadata
            cwe_ids = []
            metadata = extra.get('metadata', {})
            cwe_list = metadata.get('cwe', [])
            for cwe_str in cwe_list:
                # Extract number from "CWE-89" format
                if isinstance(cwe_str, str) and cwe_str.startswith('CWE-'):
                    try:
                        cwe_ids.append(int(cwe_str.split('-')[1]))
                    except (ValueError, IndexError):
                        pass
            
            start = finding.get('start', {})
            
            result = SARIFBuilder.create_result(
                rule_id=finding.get('check_id', 'UNKNOWN'),
                message=extra.get('message', 'No description'),
                level=level,
                file_path=finding.get('path'),
                line_number=start.get('line'),
                column=start.get('col'),
                severity=severity.lower(),
                cwe=cwe_ids if cwe_ids else None
            )
            
            # Add OWASP mapping if available
            if 'owasp' in metadata:
                result["properties"]["owasp"] = metadata['owasp']
            
            run["results"].append(result)
        
        return run


class Flake8SARIFParser:
    """Parse Flake8 output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Flake8 text output to SARIF 2.1.0 format.
        
        Flake8 output format (one issue per line):
        path/to/file.py:10:5: E501 line too long (82 > 79 characters)
        path/to/file.py:15:1: W293 blank line contains whitespace
        """
        run = SARIFBuilder.create_run("flake8")
        
        if not isinstance(raw_output, str):
            logger.error("Invalid Flake8 output format")
            return run
        
        lines = raw_output.strip().split('\n')
        
        for line in lines:
            if not line.strip():
                continue
            
            # Parse format: file:line:col: CODE message
            parts = line.split(':', 3)
            if len(parts) < 4:
                continue
            
            file_path = parts[0].strip()
            try:
                line_num = int(parts[1].strip())
                column = int(parts[2].strip())
            except ValueError:
                continue
            
            # Extract error code and message
            code_and_msg = parts[3].strip()
            code_parts = code_and_msg.split(' ', 1)
            error_code = code_parts[0] if code_parts else 'UNKNOWN'
            message = code_parts[1] if len(code_parts) > 1 else 'No description'
            
            # Determine level based on error code (matching parsers.py logic)
            if error_code in ['W291', 'W292', 'W293', 'W503', 'W504', 'W605']:
                level = 'note'
                severity = 'low'
            elif error_code.startswith('E') or error_code.startswith('F'):
                level = 'error'
                severity = 'high'
            elif error_code.startswith('W'):
                level = 'warning'
                severity = 'medium'
            else:
                level = 'note'
                severity = 'low'
            
            result = SARIFBuilder.create_result(
                rule_id=error_code,
                message=message,
                level=level,
                file_path=file_path,
                line_number=line_num,
                column=column,
                severity=severity
            )
            
            run["results"].append(result)
        
        return run


class RuffSARIFParser:
    """Parse Ruff JSON output to SARIF format."""
    
    @staticmethod
    def _get_ruff_severity(rule_id: str) -> tuple[str, str]:
        """
        Map Ruff rule IDs to appropriate severity levels.
        
        Returns:
            (sarif_level, severity_category) tuple
            sarif_level: 'error' | 'warning' | 'note'
            severity_category: 'critical' | 'high' | 'medium' | 'low' | 'info'
        """
        # Whitespace/formatting rules - LOW or INFO
        if rule_id in ['W291', 'W292', 'W293', 'W503', 'W504', 'W605']:
            return ('note', 'low')
        
        # Import sorting - MEDIUM
        if rule_id.startswith('I') or rule_id in ['E401', 'E402']:
            return ('warning', 'medium')
        
        # Security rules (Bandit-like) - HIGH to CRITICAL
        if rule_id.startswith('S'):
            # S1xx-S3xx: high security issues
            if rule_id in ['S104', 'S105', 'S106', 'S107', 'S108']:
                return ('error', 'high')  # Hardcoded passwords, bind all interfaces
            # S311-S324: crypto/random - high
            if rule_id in ['S311', 'S324']:
                return ('error', 'high')
            # Lower security issues
            return ('warning', 'medium')
        
        # Critical syntax/logic errors
        if rule_id in ['E999', 'F821', 'F822', 'F823']:
            return ('error', 'high')  # Syntax errors, undefined names
        
        # Unused imports/variables - MEDIUM
        if rule_id in ['F401', 'F403', 'F405', 'F841']:
            return ('warning', 'medium')
        
        # Code complexity - MEDIUM
        if rule_id.startswith('C') or rule_id in ['E501']:
            return ('warning', 'medium')
        
        # Pycodestyle errors (E7xx) - mostly MEDIUM except critical ones
        if rule_id.startswith('E7'):
            if rule_id in ['E711', 'E712', 'E721']:
                return ('warning', 'medium')  # Comparison issues
            return ('warning', 'low')
        
        # Default: E-prefixed = MEDIUM, others = LOW
        if rule_id.startswith('E'):
            return ('warning', 'medium')
        
        return ('warning', 'low')
    
    @staticmethod
    def parse(raw_output: List[Dict[str, Any]], config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Ruff JSON output to SARIF 2.1.0 format.
        
        Ruff JSON structure:
        [{
            "code": "E501",
            "message": "Line too long (100 > 88 characters)",
            "location": {
                "row": 10,
                "column": 88
            },
            "end_location": {
                "row": 10,
                "column": 100
            },
            "filename": "path/to/file.py",
            "fix": null
        }]
        """
        if not isinstance(raw_output, list):
            logger.error("Invalid Ruff output format")
            return SARIFBuilder.create_run("ruff")
        
        run = SARIFBuilder.create_run("ruff")
        
        for issue in raw_output:
            location = issue.get('location', {})
            error_code = issue.get('code', 'UNKNOWN')
            
            # Use intelligent severity mapping
            level, severity = RuffSARIFParser._get_ruff_severity(error_code)
            
            result = SARIFBuilder.create_result(
                rule_id=error_code,
                message=issue.get('message', 'No description'),
                level=level,
                file_path=issue.get('filename'),
                line_number=location.get('row'),
                column=location.get('column'),
                severity=severity
            )
            
            run["results"].append(result)
        
        return run


class MypySARIFParser:
    """Parse Mypy output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Mypy output to SARIF 2.1.0 format.
        
        Mypy can output JSON with --output=json (newline-delimited) or text format.
        
        Text format:
        path/to/file.py:10:5: error: Incompatible types
        
        JSON format (newline-delimited or single dict):
        Single finding: {"file": "...", "line": 10, "column": 5, ...}
        Multiple findings (newline-delimited):
        {"file": "path/to/file.py", "line": 10, "column": 5, "severity": "error", "message": "Incompatible types", "error_code": "assignment"}
        {"file": "path/to/other.py", "line": 20, "column": 10, "severity": "warning", "message": "...", "error_code": "..."}
        """
        run = SARIFBuilder.create_run("mypy")
        
        # Handle single JSON object (one finding)
        if isinstance(raw_output, dict):
            raw_output = [raw_output]  # Convert to list for uniform processing
        
        # Handle text or newline-delimited JSON format
        if isinstance(raw_output, str):
            findings = []
            for line in raw_output.strip().split('\n'):
                if not line.strip():
                    continue
                
                # Try to parse as JSON first
                try:
                    finding = json.loads(line)
                    if isinstance(finding, dict):
                        findings.append(finding)
                        continue
                except (json.JSONDecodeError, ValueError):
                    pass
                
                # Fallback: Parse text format: file:line:column: severity: message
                parts = line.split(':', 4)
                if len(parts) >= 4:
                    severity_str = 'high' if ' error:' in line else 'medium'
                    level = 'error' if ' error:' in line else 'warning'
                    
                    try:
                        line_num = int(parts[1])
                        col_num = int(parts[2])
                    except ValueError:
                        continue
                    
                    message = parts[3].strip() if len(parts) > 3 else 'Type check error'
                    
                    result = SARIFBuilder.create_result(
                        rule_id='type-check',
                        message=message,
                        level=level,
                        file_path=parts[0],
                        line_number=line_num,
                        column=col_num,
                        severity=severity_str
                    )
                    
                    run["results"].append(result)
            
            # If we parsed JSON findings from newline-delimited format, process them
            if findings:
                raw_output = findings
                # Continue to process JSON findings below
            else:
                # No JSON findings, return run with any text-format results we found
                return run
        
        # At this point, raw_output should be a list of JSON findings
        # Handle JSON array format (legacy or pre-parsed newline-delimited)
        if not isinstance(raw_output, list):
            logger.error("Invalid Mypy output format: expected list but got %s", type(raw_output))
            return run
        
        for finding in raw_output:
            mypy_severity = finding.get('severity', 'error')
            level = 'error' if mypy_severity == 'error' else 'warning'
            severity = 'high' if mypy_severity == 'error' else 'medium'
            
            result = SARIFBuilder.create_result(
                rule_id=finding.get('error_code', 'type-check'),
                message=finding.get('message', 'Type check error'),
                level=level,
                file_path=finding.get('file'),
                line_number=finding.get('line'),
                column=finding.get('column'),
                severity=severity
            )
            
            run["results"].append(result)
        
        return run


class VultureSARIFParser:
    """Parse Vulture text output to SARIF format."""
    
    @staticmethod
    def parse(raw_output: str, config: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Convert Vulture text output to SARIF 2.1.0 format.
        
        Vulture output format:
        app.py:10: unused variable 'x' (60% confidence)
        app.py:25: unused function 'old_function' (100% confidence)
        """
        if not isinstance(raw_output, str):
            logger.error("Invalid Vulture output format")
            return SARIFBuilder.create_run("vulture")
        
        run = SARIFBuilder.create_run("vulture")
        
        for line in raw_output.splitlines():
            if ':' in line and ('unused' in line.lower() or 'unreachable' in line.lower()):
                parts = line.split(':', 2)
                if len(parts) < 3:
                    continue
                
                file_path = parts[0]
                try:
                    line_num = int(parts[1])
                except ValueError:
                    continue
                
                # Extract confidence if present
                confidence = 60  # default
                message = parts[2].strip()
                if '(' in message and '% confidence)' in message:
                    conf_str = message.split('(')[1].split('%')[0].strip()
                    try:
                        confidence = int(conf_str)
                    except ValueError:
                        pass
                
                # Map confidence to severity and level
                if confidence >= 80:
                    severity = 'medium'
                    level = 'warning'
                else:
                    severity = 'low'
                    level = 'note'
                
                result = SARIFBuilder.create_result(
                    rule_id='dead-code',
                    message=message,
                    level=level,
                    file_path=file_path,
                    line_number=line_num,
                    severity=severity,
                    confidence=str(confidence)
                )
                
                run["results"].append(result)
        
        return run


# Parser registry for easy lookup
SARIF_PARSERS = {
    'bandit': BanditSARIFParser,
    'pylint': PyLintSARIFParser,
    'eslint': ESLintSARIFParser,
    'safety': SafetySARIFParser,
    'semgrep': SemgrepSARIFParser,
    'flake8': Flake8SARIFParser,
    'ruff': RuffSARIFParser,
    'mypy': MypySARIFParser,
    'vulture': VultureSARIFParser
}


def get_available_sarif_parsers() -> List[str]:
    """Get list of tools with SARIF parser support."""
    return list(SARIF_PARSERS.keys())


def parse_tool_output_to_sarif(
    tool_name: str,
    raw_output: Any,
    config: Optional[Dict] = None
) -> Optional[Dict[str, Any]]:
    """
    Parse tool output to SARIF format using the appropriate parser.
    
    Args:
        tool_name: Name of the tool (e.g., 'bandit', 'pylint')
        raw_output: Raw tool output (format depends on tool)
        config: Optional configuration dict
        
    Returns:
        SARIF run dict or None if parser not found
    """
    parser_class = SARIF_PARSERS.get(tool_name.lower())
    
    if not parser_class:
        logger.warning(f"No SARIF parser found for tool: {tool_name}")
        return None
    
    try:
        return parser_class.parse(raw_output, config)
    except Exception as e:
        logger.error(f"Error parsing {tool_name} output to SARIF: {e}", exc_info=True)
        return None


def build_sarif_document(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Build a complete SARIF 2.1.0 document from multiple runs.
    
    Args:
        runs: List of SARIF run objects
        
    Returns:
        Complete SARIF document
    """
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": runs
    }


def remap_ruff_sarif_severity(sarif_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Post-process Ruff SARIF output to correct severity levels.
    
    Ruff outputs all issues as "level": "error", but many should be lower severity.
    This function remaps severities based on rule IDs.
    
    Args:
        sarif_data: SARIF document from Ruff (with runs array)
        
    Returns:
        Modified SARIF document with corrected severity levels
    """
    if not isinstance(sarif_data, dict) or 'runs' not in sarif_data:
        return sarif_data
    
    for run in sarif_data.get('runs', []):
        # Only process if this is a Ruff run
        tool_name = run.get('tool', {}).get('driver', {}).get('name', '').lower()
        if 'ruff' not in tool_name:
            continue
        
        for result in run.get('results', []):
            rule_id = result.get('ruleId', '')
            
            # Get correct severity for this rule
            level, severity_category = RuffSARIFParser._get_ruff_severity(rule_id)
            
            # Update SARIF level
            result['level'] = level
            
            # Update properties.problem.severity if it exists
            if 'properties' not in result:
                result['properties'] = {}
            result['properties']['problem.severity'] = severity_category
    
    return sarif_data
