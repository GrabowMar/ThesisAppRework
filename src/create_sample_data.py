#!/usr/bin/env python3
"""
Create sample security analysis results for testing the results page.
"""
import sys
sys.path.append('.')
from app.factory import create_cli_app
from app.extensions import db
from app.models import SecurityAnalysis, AnalysisStatus
import json
from datetime import datetime, timezone

def create_sample_results():
    app = create_cli_app()
    with app.app_context():
        analysis = SecurityAnalysis.query.get(6)
        if not analysis:
            print("Analysis ID 6 not found")
            return
            
        print("Updating Analysis ID 6 with sample results...")
        
        # Create comprehensive sample results
        sample_results = {
            "bandit": {
                "results": [
                    {
                        "test_id": "B101",
                        "test_name": "Test for use of assert",
                        "filename": "app.py",
                        "line_number": 42,
                        "issue_severity": "High",
                        "issue_confidence": "High",
                        "issue_text": "Use of assert detected. Assertions can be disabled and should not be used for data validation.",
                        "code": "assert user.is_authenticated",
                        "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html"
                    },
                    {
                        "test_id": "B108",
                        "test_name": "Test for insecure usage of tmp files/directories",
                        "filename": "utils.py", 
                        "line_number": 15,
                        "issue_severity": "Medium",
                        "issue_confidence": "Medium",
                        "issue_text": "Probable insecure usage of temp file/directory.",
                        "code": "temp_file = '/tmp/myapp_temp'",
                        "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b108_hardcoded_tmp_directory.html"
                    },
                    {
                        "test_id": "B605",
                        "test_name": "Test for use of shell=True",
                        "filename": "commands.py",
                        "line_number": 28,
                        "issue_severity": "Critical",
                        "issue_confidence": "High", 
                        "issue_text": "subprocess call with shell=True identified, security issue.",
                        "code": "subprocess.call(user_input, shell=True)",
                        "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b605_start_process_with_a_shell.html"
                    }
                ],
                "metrics": {
                    "files": 5,
                    "lines": 1250,
                    "skipped_tests": []
                }
            },
            "safety": {
                "report_meta": {
                    "scan_target": "environment",
                    "scanned": ["/usr/local/lib/python3.9/site-packages"],
                    "api_key": False,
                    "packages_found": 3,
                    "timestamp": "2024-01-15 10:30:00",
                    "safety_version": "2.3.4"
                },
                "scanned_packages": {
                    "requests": {"name": "requests", "version": "2.25.1"},
                    "flask": {"name": "flask", "version": "2.0.1"},
                    "jinja2": {"name": "jinja2", "version": "3.0.1"}
                },
                "affected_packages": {
                    "requests": {
                        "name": "requests",
                        "version": "2.25.1",
                        "found": "/usr/local/lib/python3.9/site-packages",
                        "insecure_versions": [],
                        "secure_versions": [],
                        "latest_version_without_known_vulnerabilities": "2.31.0",
                        "latest_version": "2.31.0",
                        "more_info_url": "https://pyup.io/vulnerabilities/CVE-2023-32681/"
                    }
                },
                "vulnerabilities": [
                    {
                        "name": "requests",
                        "ignored": False,
                        "reason": "",
                        "expires": "",
                        "vulnerable_spec": "<2.31.0",
                        "all_vulnerable_specs": ["<2.31.0"],
                        "analyzed_version": "2.25.1",
                        "advisory": "Requests verify=False does not validate TLS certificates, enabling potential MITM attacks.",
                        "vulnerability_id": "51668",
                        "is_transitive": False,
                        "published_date": "2023-05-26",
                        "fixed_versions": ["2.31.0"],
                        "closest_versions_without_known_vulnerabilities": ["2.31.0"],
                        "resources": [],
                        "CVE": {
                            "name": "CVE-2023-32681",
                            "cvssv2": None,
                            "cvssv3": "7.5"
                        },
                        "affected_versions": [],
                        "more_info_url": "https://pyup.io/vulnerabilities/CVE-2023-32681/"
                    },
                    {
                        "name": "jinja2", 
                        "ignored": False,
                        "reason": "",
                        "expires": "",
                        "vulnerable_spec": "<3.1.0",
                        "all_vulnerable_specs": ["<3.1.0"],
                        "analyzed_version": "3.0.1",
                        "advisory": "Jinja2 vulnerable to XSS via automatic escaping bypass.",
                        "vulnerability_id": "52495",
                        "is_transitive": False,
                        "published_date": "2023-01-10",
                        "fixed_versions": ["3.1.0"],
                        "CVE": {
                            "name": "CVE-2023-1234",
                            "cvssv3": "6.1"
                        },
                        "more_info_url": "https://pyup.io/vulnerabilities/CVE-2023-1234/"
                    }
                ],
                "ignored_vulnerabilities": [],
                "remediations": {
                    "requests": {
                        "vulns_found": 1,
                        "version": "2.25.1", 
                        "recommended": "2.31.0",
                        "other_recommended_versions": [],
                        "more_info_url": "https://pyup.io/vulnerabilities/CVE-2023-32681/"
                    },
                    "jinja2": {
                        "vulns_found": 1,
                        "version": "3.0.1",
                        "recommended": "3.1.0",
                        "other_recommended_versions": [],
                        "more_info_url": "https://pyup.io/vulnerabilities/CVE-2023-1234/"
                    }
                }
            },
            "zap": {
                "@version": "2.12.0",
                "@generated": "2024-01-15T10:30:00Z",
                "site": [{
                    "@name": "http://localhost:5000",
                    "@host": "localhost",
                    "@port": "5000",
                    "@ssl": "false",
                    "alerts": [
                        {
                            "pluginid": "10020",
                            "alertRef": "10020",
                            "alert": "X-Frame-Options Header Not Set",
                            "riskcode": 2,
                            "confidence": 2,
                            "riskdesc": "Medium (Medium)",
                            "desc": "X-Frame-Options header is not included in the HTTP response to protect against 'ClickJacking' attacks.",
                            "solution": "Most modern Web browsers support the X-Frame-Options HTTP header. Ensure it's set on all web pages returned by your site (if you expect the page to be framed only by pages on your server (e.g. it's part of a FRAMESET) then you'll want to use SAMEORIGIN, otherwise if you never expect the page to be framed, you should use DENY. Alternatively consider implementing Content Security Policy's \"frame-ancestors\" directive.",
                            "reference": "https://tools.ietf.org/html/rfc7034",
                            "cweid": "16",
                            "wascid": "15",
                            "instances": [
                                {
                                    "uri": "http://localhost:5000/",
                                    "method": "GET",
                                    "param": "X-Frame-Options"
                                },
                                {
                                    "uri": "http://localhost:5000/login",
                                    "method": "GET", 
                                    "param": "X-Frame-Options"
                                }
                            ]
                        },
                        {
                            "pluginid": "10016",
                            "alertRef": "10016", 
                            "alert": "Web Browser XSS Protection Not Enabled",
                            "riskcode": 1,
                            "confidence": 2,
                            "riskdesc": "Low (Medium)",
                            "desc": "Web Browser XSS Protection is not enabled, or is disabled by the configuration in the HTTP response header.",
                            "solution": "Ensure that the web browser's XSS filter is enabled, by setting the X-XSS-Protection HTTP response header to '1'.",
                            "reference": "https://owasp.org/www-community/xss-filter-evasion-cheatsheet",
                            "cweid": "933",
                            "wascid": "14",
                            "instances": [
                                {
                                    "uri": "http://localhost:5000/login",
                                    "method": "GET",
                                    "param": "X-XSS-Protection"
                                }
                            ]
                        },
                        {
                            "pluginid": "10021",
                            "alertRef": "10021",
                            "alert": "X-Content-Type-Options Header Missing",
                            "riskcode": 1,
                            "confidence": 2,
                            "riskdesc": "Low (Medium)",
                            "desc": "The Anti-MIME-Sniffing header X-Content-Type-Options was not set to 'nosniff'. This allows older versions of Internet Explorer and Chrome to perform MIME-sniffing on the response body.",
                            "solution": "Ensure that the application/web server sets the Content-Type header appropriately, and that it sets the X-Content-Type-Options header to 'nosniff' for all web pages.",
                            "reference": "http://msdn.microsoft.com/en-us/library/ie/gg622941%28v=vs.85%29.aspx",
                            "cweid": "16", 
                            "wascid": "15",
                            "instances": [
                                {
                                    "uri": "http://localhost:5000/",
                                    "method": "GET",
                                    "param": "X-Content-Type-Options"
                                }
                            ]
                        },
                        {
                            "pluginid": "90022",
                            "alertRef": "90022",
                            "alert": "Application Error Disclosure",
                            "riskcode": 1,
                            "confidence": 2,
                            "riskdesc": "Low (Medium)",
                            "desc": "This page contains an error/warning message that may disclose sensitive information like the location of the file that produced the unhandled exception.",
                            "solution": "Review the source code of this page. Implement custom error pages.",
                            "reference": "https://owasp.org/www-project-top-ten/2017/A3_2017-Sensitive_Data_Exposure",
                            "cweid": "200",
                            "wascid": "13",
                            "instances": [
                                {
                                    "uri": "http://localhost:5000/error",
                                    "method": "GET",
                                    "evidence": "Internal Server Error\\n\\nThe server encountered an internal error"
                                }
                            ]
                        }
                    ]
                }]
            },
            "pylint": [
                {
                    "type": "error",
                    "module": "app",
                    "obj": "create_app",
                    "line": 15,
                    "column": 0,
                    "message": "Unable to import 'nonexistent_module'",
                    "symbol": "import-error"
                },
                {
                    "type": "warning", 
                    "module": "utils",
                    "obj": "validate_input",
                    "line": 42,
                    "column": 4,
                    "message": "Unused variable 'temp_var'",
                    "symbol": "unused-variable"
                },
                {
                    "type": "convention",
                    "module": "models",
                    "obj": "User",
                    "line": 8,
                    "column": 0,
                    "message": "Missing class docstring",
                    "symbol": "missing-class-docstring"
                }
            ],
            "eslint": [
                {
                    "filePath": "/static/js/app.js",
                    "messages": [
                        {
                            "ruleId": "no-unused-vars",
                            "severity": 1,
                            "message": "'unused_var' is defined but never used.",
                            "line": 10,
                            "column": 5,
                            "nodeType": "Identifier"
                        },
                        {
                            "ruleId": "eqeqeq",
                            "severity": 2,
                            "message": "Expected '===' and instead saw '=='.",
                            "line": 25,
                            "column": 12,
                            "nodeType": "BinaryExpression"
                        }
                    ],
                    "errorCount": 1,
                    "warningCount": 1
                },
                {
                    "filePath": "/static/js/utils.js",
                    "messages": [
                        {
                            "ruleId": "no-console",
                            "severity": 1,
                            "message": "Unexpected console statement.",
                            "line": 5,
                            "column": 1,
                            "nodeType": "MemberExpression"
                        }
                    ],
                    "errorCount": 0,
                    "warningCount": 1
                }
            ]
        }
        
        # Update the analysis
        analysis.results_json = json.dumps(sample_results)
        analysis.status = AnalysisStatus.COMPLETED
        analysis.total_issues = 13  # Total across all tools
        analysis.critical_severity_count = 1
        analysis.high_severity_count = 2
        analysis.medium_severity_count = 5
        analysis.low_severity_count = 5
        analysis.tools_run_count = 5
        analysis.completed_at = datetime.now(timezone.utc)
        
        db.session.commit()
        print("Sample results added successfully!")
        print(f"- Total issues: {analysis.total_issues}")
        print(f"- Tools run: {analysis.tools_run_count}")
        print(f"- Status: {analysis.status}")

if __name__ == "__main__":
    create_sample_results()
