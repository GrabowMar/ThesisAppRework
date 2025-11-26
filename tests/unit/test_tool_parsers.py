import pytest
from app.utils.tool_parsers import extract_tool_findings, normalize_severity

def test_normalize_severity():
    assert normalize_severity('CRITICAL') == 'CRITICAL'
    assert normalize_severity('High') == 'HIGH'
    assert normalize_severity('warn') == 'MEDIUM'
    assert normalize_severity('note') == 'LOW'
    assert normalize_severity('unknown') == 'INFO'

def test_extract_dynamic_zap():
    results = {
        'zap_security_scan': [
            {
                'url': 'http://example.com',
                'alerts_by_risk': {
                    'High': [{'alert': 'SQL Injection', 'description': 'Bad stuff'}]
                }
            }
        ]
    }
    findings = extract_tool_findings('dynamic', 'zap', results)
    assert len(findings) == 1
    assert findings[0]['rule_id'] == 'SQL Injection'
    assert findings[0]['severity'] == 'HIGH'

def test_extract_performance_locust():
    results = {
        'tool_runs': {
            'locust': {
                'url': 'http://example.com',
                'failed_requests': 10,
                'avg_response_time': 600,
                'requests_per_second': 10
            }
        }
    }
    findings = extract_tool_findings('performance', 'locust', results)
    assert len(findings) == 3
    assert any(f['rule_id'] == 'high-failure-rate' for f in findings)
    assert any(f['rule_id'] == 'slow-response-time' for f in findings)
    assert any(f['rule_id'] == 'low-throughput' for f in findings)

def test_extract_static_bandit():
    results = {
        'issues': [
            {
                'test_id': 'B101',
                'issue_severity': 'HIGH',
                'filename': '/app/sources/main.py',
                'line_number': 10,
                'issue_text': 'Assert used'
            }
        ]
    }
    findings = extract_tool_findings('static', 'bandit', results)
    assert len(findings) == 1
    assert findings[0]['rule_id'] == 'B101'
    assert findings[0]['severity'] == 'HIGH'
    assert findings[0]['file'] == 'main.py'

def test_extract_ai_requirements():
    results = {
        'analysis': {
            'results': {
                'requirement_checks': [
                    {
                        'requirement': 'Must have login',
                        'result': {'met': False, 'confidence': 'HIGH', 'explanation': 'No login found'}
                    }
                ]
            }
        }
    }
    findings = extract_tool_findings('ai', 'ai-analyzer', results)
    assert len(findings) == 1
    assert findings[0]['rule_id'] == 'ai-legacy-requirement-not-met'
    assert findings[0]['severity'] == 'HIGH'
