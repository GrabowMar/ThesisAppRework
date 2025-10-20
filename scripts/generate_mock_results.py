"""
Mock Data Generator for Dashboard Testing

Generates comprehensive mock results.json with findings from all 18 tools
for testing the dashboard system.
"""

import json
from datetime import datetime
from typing import Any, Dict, List

# Tool definitions with realistic output patterns
TOOLS_CONFIG = {
    # Static Analysis - Security
    "bandit": {
        "category": "security",
        "severities": ["high", "medium", "low"],
        "findings": [
            {
                "message": {"title": "Use of insecure MD5 hash function", "description": "MD5 is cryptographically broken and should not be used for security purposes. Use SHA256 or better.", "solution": "Replace hashlib.md5() with hashlib.sha256()"},
                "rule_id": "B303",
                "file": "app/auth/utils.py",
                "line": 45,
                "severity": "high",
                "code": "password_hash = hashlib.md5(password.encode()).hexdigest()"
            },
            {
                "message": {"title": "Hardcoded password string", "description": "Hardcoded passwords pose a security risk. Store credentials in environment variables or secure vaults.", "solution": "Use environment variables: os.getenv('DB_PASSWORD')"},
                "rule_id": "B105",
                "file": "app/config.py",
                "line": 12,
                "severity": "high",
                "code": "DB_PASSWORD = 'admin123'"
            },
            {
                "message": {"title": "SQL injection possible", "description": "String concatenation in SQL queries can lead to SQL injection vulnerabilities.", "solution": "Use parameterized queries with placeholders"},
                "rule_id": "B608",
                "file": "app/models/user.py",
                "line": 78,
                "severity": "high",
                "code": "query = f\"SELECT * FROM users WHERE id = {user_id}\""
            },
            {
                "message": {"title": "Use of insecure random module", "description": "The standard random module is not suitable for security/cryptographic purposes.", "solution": "Use secrets module: secrets.token_urlsafe(32)"},
                "rule_id": "B311",
                "file": "app/auth/tokens.py",
                "line": 23,
                "severity": "medium",
                "code": "token = ''.join(random.choices(string.ascii_letters, k=32))"
            },
        ]
    },
    "safety": {
        "category": "security",
        "severities": ["critical", "high", "medium"],
        "findings": [
            {
                "message": {"title": "Vulnerable dependency: requests 2.25.0", "description": "requests <2.31.0 contains a vulnerability (CVE-2023-32681) allowing request smuggling.", "solution": "Update to requests>=2.31.0"},
                "rule_id": "CVE-2023-32681",
                "file": "requirements.txt",
                "line": 5,
                "severity": "critical",
                "code": "requests==2.25.0"
            },
            {
                "message": {"title": "Vulnerable dependency: flask 1.1.2", "description": "Flask <2.2.5 contains security vulnerabilities in session handling.", "solution": "Update to flask>=2.3.0"},
                "rule_id": "CVE-2023-30861",
                "file": "requirements.txt",
                "line": 1,
                "severity": "high",
                "code": "flask==1.1.2"
            },
        ]
    },
    "snyk": {
        "category": "security",
        "severities": ["high", "medium", "low"],
        "findings": [
            {
                "message": {"title": "Prototype Pollution in lodash", "description": "lodash versions before 4.17.21 are vulnerable to prototype pollution.", "solution": "Update lodash to >=4.17.21"},
                "rule_id": "SNYK-JS-LODASH-1018905",
                "file": "package.json",
                "line": 8,
                "severity": "high",
                "code": "\"lodash\": \"^4.17.15\""
            },
        ]
    },
    
    # Static Analysis - Code Quality
    "pylint": {
        "category": "code_quality",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "Missing module docstring", "description": "Every module should have a docstring explaining its purpose.", "solution": "Add a docstring at the top of the file"},
                "rule_id": "C0114",
                "file": "app/utils/helpers.py",
                "line": 1,
                "severity": "low",
                "code": "# Missing docstring"
            },
            {
                "message": {"title": "Variable name doesn't conform to snake_case", "description": "Variable names should use snake_case naming convention.", "solution": "Rename 'userName' to 'user_name'"},
                "rule_id": "C0103",
                "file": "app/models/user.py",
                "line": 34,
                "severity": "low",
                "code": "userName = request.form.get('username')"
            },
            {
                "message": {"title": "Too many local variables (25/15)", "description": "Function has too many local variables, making it hard to understand.", "solution": "Refactor into smaller functions"},
                "rule_id": "R0914",
                "file": "app/views/dashboard.py",
                "line": 156,
                "severity": "medium",
                "code": "def generate_report():"
            },
            {
                "message": {"title": "Unused import 'os'", "description": "Import statement is present but never used in the code.", "solution": "Remove the unused import"},
                "rule_id": "W0611",
                "file": "app/config.py",
                "line": 3,
                "severity": "low",
                "code": "import os"
            },
        ]
    },
    "flake8": {
        "category": "code_quality",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "Line too long (98 > 79 characters)", "description": "Line exceeds the maximum recommended length.", "solution": "Break line into multiple lines"},
                "rule_id": "E501",
                "file": "app/routes/api.py",
                "line": 67,
                "severity": "low",
                "code": "return jsonify({'status': 'success', 'data': user.to_dict(), 'message': 'User retrieved successfully'})"
            },
            {
                "message": {"title": "Undefined name 'ConfigError'", "description": "Name is used but not defined in the current scope.", "solution": "Import ConfigError or define it"},
                "rule_id": "F821",
                "file": "app/config.py",
                "line": 89,
                "severity": "medium",
                "code": "raise ConfigError('Invalid configuration')"
            },
        ]
    },
    "mypy": {
        "category": "code_quality",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "Argument 1 has incompatible type", "description": "Function expects str but got Optional[str]", "solution": "Add type guard: if user_id is not None:"},
                "rule_id": "arg-type",
                "file": "app/services/user.py",
                "line": 123,
                "severity": "medium",
                "code": "result = process_user_id(user_id)"
            },
            {
                "message": {"title": "Function is missing a return type annotation", "description": "All functions should specify their return type.", "solution": "Add -> Dict[str, Any]: after function signature"},
                "rule_id": "no-untyped-def",
                "file": "app/utils/json_helper.py",
                "line": 45,
                "severity": "low",
                "code": "def parse_json(data):"
            },
        ]
    },
    "eslint": {
        "category": "code_quality",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "'console' is not defined", "description": "console is a browser/node global that should be explicitly allowed.", "solution": "Add /* eslint-env browser */ or remove console statements"},
                "rule_id": "no-undef",
                "file": "static/js/dashboard.js",
                "line": 234,
                "severity": "low",
                "code": "console.log('Data loaded:', data);"
            },
            {
                "message": {"title": "Unexpected var, use let or const instead", "description": "var has function scope, use block-scoped let/const.", "solution": "Replace 'var' with 'const' or 'let'"},
                "rule_id": "no-var",
                "file": "static/js/app.js",
                "line": 12,
                "severity": "medium",
                "code": "var userName = 'admin';"
            },
        ]
    },
    "jshint": {
        "category": "code_quality",
        "severities": ["low"],
        "findings": [
            {
                "message": {"title": "Missing semicolon", "description": "Statements should end with a semicolon.", "solution": "Add semicolon at end of line"},
                "rule_id": "W033",
                "file": "static/js/utils.js",
                "line": 56,
                "severity": "low",
                "code": "return result"
            },
        ]
    },
    "vulture": {
        "category": "code_quality",
        "severities": ["low"],
        "findings": [
            {
                "message": {"title": "Unused function 'calculate_stats'", "description": "Function is defined but never called.", "solution": "Remove unused function or add usage"},
                "rule_id": "unused-function",
                "file": "app/utils/stats.py",
                "line": 89,
                "severity": "low",
                "code": "def calculate_stats():"
            },
        ]
    },
    "semgrep": {
        "category": "security",
        "severities": ["high", "medium"],
        "findings": [
            {
                "message": {"title": "eval() usage detected", "description": "Using eval() with user input can lead to arbitrary code execution.", "solution": "Use ast.literal_eval() for safe evaluation or avoid eval entirely"},
                "rule_id": "python.lang.security.audit.dangerous-eval.dangerous-eval",
                "file": "app/api/calculator.py",
                "line": 67,
                "severity": "high",
                "code": "result = eval(user_expression)"
            },
        ]
    },
    "stylelint": {
        "category": "code_quality",
        "severities": ["low"],
        "findings": [
            {
                "message": {"title": "Unexpected duplicate selector", "description": "The same selector appears multiple times in the stylesheet.", "solution": "Combine duplicate selectors into one block"},
                "rule_id": "no-duplicate-selectors",
                "file": "static/css/style.css",
                "line": 234,
                "severity": "low",
                "code": ".btn-primary {"
            },
        ]
    },
    
    # Dynamic Analysis
    "curl": {
        "category": "performance",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "HTTP endpoint timeout", "description": "/api/slow-endpoint took 5.2s to respond (>3s threshold)", "solution": "Optimize database queries or add caching"},
                "rule_id": "timeout",
                "file": "N/A",
                "line": 0,
                "severity": "medium",
                "code": "GET /api/slow-endpoint"
            },
            {
                "message": {"title": "Missing HTTPS redirect", "description": "HTTP endpoint doesn't redirect to HTTPS", "solution": "Add HTTPS redirect in web server config"},
                "rule_id": "no-https",
                "file": "N/A",
                "line": 0,
                "severity": "low",
                "code": "GET http://example.com/api"
            },
        ]
    },
    "nmap": {
        "category": "security",
        "severities": ["high", "medium"],
        "findings": [
            {
                "message": {"title": "Unnecessary open port: 3306", "description": "MySQL port is exposed to the internet", "solution": "Close port 3306 or restrict to localhost only"},
                "rule_id": "open-port",
                "file": "N/A",
                "line": 0,
                "severity": "high",
                "code": "3306/tcp open  mysql"
            },
        ]
    },
    "zap": {
        "category": "security",
        "severities": ["high", "medium", "low"],
        "findings": [
            {
                "message": {"title": "Missing Anti-CSRF Token", "description": "Form submission without CSRF protection", "solution": "Add CSRF token to all forms"},
                "rule_id": "10202",
                "file": "N/A",
                "line": 0,
                "severity": "high",
                "code": "POST /api/users"
            },
            {
                "message": {"title": "X-Content-Type-Options header missing", "description": "Response doesn't include X-Content-Type-Options: nosniff", "solution": "Add security header in web server config"},
                "rule_id": "10021",
                "file": "N/A",
                "line": 0,
                "severity": "medium",
                "code": "GET /"
            },
        ]
    },
    
    # Performance Testing
    "aiohttp": {
        "category": "performance",
        "severities": ["medium", "low"],
        "findings": [
            {
                "message": {"title": "High response time under load", "description": "95th percentile response time: 2.8s (target: <1s)", "solution": "Add caching layer or optimize database queries"},
                "rule_id": "p95-threshold",
                "file": "N/A",
                "line": 0,
                "severity": "medium",
                "code": "GET /api/users?limit=100"
            },
        ]
    },
    "ab": {
        "category": "performance",
        "severities": ["medium"],
        "findings": [
            {
                "message": {"title": "Low requests per second", "description": "Server handles only 45 req/s (target: >100 req/s)", "solution": "Enable connection pooling and caching"},
                "rule_id": "low-rps",
                "file": "N/A",
                "line": 0,
                "severity": "medium",
                "code": "ab -n 1000 -c 10 http://localhost/"
            },
        ]
    },
    "locust": {
        "category": "performance",
        "severities": ["high", "medium"],
        "findings": [
            {
                "message": {"title": "Memory leak detected", "description": "Memory usage increased by 500MB during 10min load test", "solution": "Profile application for memory leaks"},
                "rule_id": "memory-leak",
                "file": "N/A",
                "line": 0,
                "severity": "high",
                "code": "Locust load test (100 users)"
            },
        ]
    },
    "artillery": {
        "category": "performance",
        "severities": ["medium"],
        "findings": [
            {
                "message": {"title": "Failed requests detected", "description": "12% of requests failed during load test", "solution": "Investigate error logs and increase server capacity"},
                "rule_id": "failed-requests",
                "file": "N/A",
                "line": 0,
                "severity": "medium",
                "code": "Artillery scenario: ramp-up"
            },
        ]
    },
}


def generate_finding(tool: str, finding_template: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Generate a structured finding based on template."""
    return {
        "tool": tool,
        "category": TOOLS_CONFIG[tool]["category"],
        "severity": finding_template["severity"],
        "rule_id": finding_template.get("rule_id", ""),
        "symbol": finding_template.get("rule_id", ""),
        "message": finding_template["message"],
        "file": {
            "path": finding_template.get("file", "unknown.py"),
            "line_start": finding_template.get("line", 0),
            "line_end": finding_template.get("line", 0),
        },
        "line_number": finding_template.get("line", 0),
        "evidence": {
            "code_snippet": finding_template.get("code", "")
        },
        "metadata": {
            "tool_version": "1.0.0",
            "timestamp": datetime.now().isoformat()
        }
    }


def generate_mock_results(
    model_slug: str = "test_model",
    app_number: int = 1,
    tools_to_include: List[str] = None
) -> Dict[str, Any]:
    """
    Generate comprehensive mock results.json with all 18 tools.
    
    Args:
        model_slug: The model identifier
        app_number: The app number
        tools_to_include: List of tools to include (defaults to all)
    
    Returns:
        Complete results.json structure
    """
    if tools_to_include is None:
        tools_to_include = list(TOOLS_CONFIG.keys())
    
    # Generate findings
    all_findings = []
    findings_by_tool = {}
    
    for tool in tools_to_include:
        if tool not in TOOLS_CONFIG:
            continue
            
        tool_findings = []
        for idx, finding_template in enumerate(TOOLS_CONFIG[tool]["findings"]):
            finding = generate_finding(tool, finding_template, idx)
            tool_findings.append(finding)
            all_findings.append(finding)
        
        findings_by_tool[tool] = len(tool_findings)
    
    # Calculate severity breakdown
    severity_breakdown = {
        "critical": len([f for f in all_findings if f["severity"] == "critical"]),
        "high": len([f for f in all_findings if f["severity"] == "high"]),
        "medium": len([f for f in all_findings if f["severity"] == "medium"]),
        "low": len([f for f in all_findings if f["severity"] == "low"]),
    }
    
    # Determine tool status
    tools_used = tools_to_include
    tools_failed = []  # No failures in mock
    tools_skipped = []  # No skips in mock
    
    # Build results structure matching AnalysisInspectionService format
    results = {
        "task_id": f"task_{model_slug}_{app_number}",
        "status": "completed",
        "analysis_type": "comprehensive",
        "model_slug": model_slug,
        "app_number": app_number,
        "timestamp": datetime.now().isoformat(),
        "results": {
            "summary": {
                "total_findings": len(all_findings),
                "severity_breakdown": severity_breakdown,
                "findings_by_tool": findings_by_tool,
                "tools_used": tools_used,
                "tools_failed": tools_failed,
                "tools_skipped": tools_skipped,
            },
            "findings": all_findings,
        },
        "metadata": {
            "extraction_version": "2.0",
            "generated": datetime.now().isoformat(),
            "mock_data": True
        }
    }
    
    return results


def save_mock_results(
    output_path: str,
    model_slug: str = "test_model",
    app_number: int = 1,
    tools_to_include: List[str] = None
):
    """Generate and save mock results to a file."""
    results = generate_mock_results(model_slug, app_number, tools_to_include)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Mock results saved to: {output_path}")
    print(f"📊 Statistics:")
    print(f"   - Total findings: {results['results']['summary']['total_findings']}")
    print(f"   - Tools used: {len(results['results']['summary']['tools_used'])}")
    print(f"   - Severity breakdown: {results['results']['summary']['severity_breakdown']}")
    
    return results


if __name__ == "__main__":
    import sys
    
    # Generate full mock data with all 18 tools
    output = "results/test/mock_comprehensive_results.json"
    if len(sys.argv) > 1:
        output = sys.argv[1]
    
    print("🔧 Generating comprehensive mock results with all 18 tools...")
    save_mock_results(output)
    
    print("\n🎯 To test specific tools only:")
    print("   python scripts/generate_mock_results.py output.json bandit,safety,pylint")
