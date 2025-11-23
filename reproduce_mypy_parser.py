
import json
from typing import Dict, Any, Optional

class MyPyParser:
    """Parser for MyPy JSON output (mypy --output json)."""
    
    @staticmethod
    def parse(raw_output: Any, config: Optional[Dict] = None) -> Dict:
        """
        Parse MyPy JSON output.
        """
        # Handle newline-delimited JSON (mypy --output json default format)
        if isinstance(raw_output, str):
            # Try to parse as newline-delimited JSON first
            findings = []
            for line in raw_output.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    finding = json.loads(line)
                    if isinstance(finding, dict):
                        findings.append(finding)
                except json.JSONDecodeError:
                    # Fallback: handle plain text output (older mypy versions)
                    if ':' in line and (' error:' in line or ' warning:' in line or ' note:' in line):
                        parts = line.strip().split(':', 3)
                        if len(parts) >= 4:
                            severity = 'error' if ' error:' in line else ('warning' if ' warning:' in line else 'note')
                            findings.append({
                                'file': parts[0],
                                'line': int(parts[1]) if parts[1].isdigit() else 0,
                                'column': int(parts[2]) if parts[2].isdigit() else 0,
                                'message': parts[3].strip(),
                                'severity': severity,
                                'error_code': 'type-check'
                            })
            
            # If we found JSON findings, process them
            if findings:
                raw_output = findings
            else:
                # No valid output found
                return {
                    'tool': 'mypy',
                    'executed': True,
                    'status': 'success',
                    'issues': [],
                    'total_issues': 0,
                    'issue_count': 0,
                }
        
        # Handle single JSON object (when mypy outputs only one line and json.loads parses it as dict)
        if isinstance(raw_output, dict):
            raw_output = [raw_output]
        
        if not isinstance(raw_output, list):
            return {
                'tool': 'mypy',
                'executed': True,
                'status': 'error',
                'error': 'Invalid JSON output format',
                'issues': [],
                'total_issues': 0,
                'issue_count': 0,
            }
        
        issues = []
        severity_breakdown = {'high': 0, 'medium': 0, 'low': 0}
        
        for finding in raw_output:
            mypy_severity = finding.get('severity', 'error')
            severity = 'high' if mypy_severity == 'error' else ('medium' if mypy_severity == 'warning' else 'low')
            severity_breakdown[severity] += 1
            
            issues.append({
                'file': finding.get('file', ''),
                'line': finding.get('line', 0),
                'column': finding.get('column', 0),
                'severity': severity,
                'message': finding.get('message', ''),
                'rule': finding.get('error_code', 'type-check')
            })
        
        return {
            'tool': 'mypy',
            'executed': True,
            'status': 'success',
            'issues': issues,
            'total_issues': len(issues),
            'issue_count': len(issues),
            'severity_breakdown': severity_breakdown,
            'config_used': config or {}
        }

stdout = "{\"file\": \"sources/google_gemini-2.5-flash/api_url_shortener/app1/backend/app.py\", \"line\": 29, \"column\": 10, \"message\": \"Name \\\"db.Model\\\" is not defined\", \"hint\": null, \"code\": \"name-defined\", \"severity\": \"error\"}\n"

print("--- Test 1: json.loads(stdout) ---")
try:
    parsed = json.loads(stdout)
    print(f"json.loads success: {type(parsed)}")
    result = MyPyParser.parse(parsed)
    print(f"Parser result: {result['status']}")
    if result['status'] == 'error':
        print(f"Error: {result['error']}")
except json.JSONDecodeError as e:
    print(f"json.loads failed: {e}")

print("\n--- Test 2: raw string ---")
result = MyPyParser.parse(stdout)
print(f"Parser result: {result['status']}")
if result['status'] == 'error':
    print(f"Error: {result['error']}")
