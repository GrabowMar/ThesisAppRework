"""
SARIF Parser Validation Tests
============================

Tests for SARIF 2.1.0 compliance of all analyzer parsers.
Validates output structure, schema compliance, and data mapping.
"""

import json
import pytest
from typing import Dict, Any
import sys
from pathlib import Path

# Add analyzer service paths
STATIC_ANALYZER_PATH = Path(__file__).parent.parent / "analyzer" / "services" / "static-analyzer"
DYNAMIC_ANALYZER_PATH = Path(__file__).parent.parent / "analyzer" / "services" / "dynamic-analyzer"

# Import static analyzer module
sys.path.insert(0, str(STATIC_ANALYZER_PATH))
import sarif_parsers as static_parsers

# Import dynamic analyzer module with different name to avoid conflicts
sys.path.insert(0, str(DYNAMIC_ANALYZER_PATH))

# Manually import from the dynamic analyzer file
import importlib.util
spec = importlib.util.spec_from_file_location("dynamic_sarif", DYNAMIC_ANALYZER_PATH / "sarif_parsers.py")
dynamic_parsers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dynamic_parsers)

# Create references to parser classes
BanditSARIFParser = static_parsers.BanditSARIFParser
PyLintSARIFParser = static_parsers.PyLintSARIFParser
ESLintSARIFParser = static_parsers.ESLintSARIFParser
SafetySARIFParser = static_parsers.SafetySARIFParser
SemgrepSARIFParser = static_parsers.SemgrepSARIFParser
Flake8SARIFParser = static_parsers.Flake8SARIFParser
RuffSARIFParser = static_parsers.RuffSARIFParser
MypySARIFParser = static_parsers.MypySARIFParser
VultureSARIFParser = static_parsers.VultureSARIFParser
build_sarif_document = static_parsers.build_sarif_document

ZAPSARIFParser = dynamic_parsers.ZAPSARIFParser


class TestSARIFCompliance:
    """Test SARIF 2.1.0 schema compliance."""
    
    def validate_sarif_run(self, sarif_run: Dict[str, Any]) -> None:
        """Validate basic SARIF run structure."""
        assert isinstance(sarif_run, dict), "SARIF run must be a dict"
        assert 'tool' in sarif_run, "SARIF run must have 'tool' key"
        assert 'results' in sarif_run, "SARIF run must have 'results' key"
        
        # Validate tool structure
        tool = sarif_run['tool']
        assert isinstance(tool, dict), "tool must be a dict"
        assert 'driver' in tool, "tool must have 'driver' key"
        
        driver = tool['driver']
        assert isinstance(driver, dict), "driver must be a dict"
        assert 'name' in driver, "driver must have 'name' key"
        assert isinstance(driver['name'], str), "driver.name must be a string"
        
        # Validate results structure
        results = sarif_run['results']
        assert isinstance(results, list), "results must be a list"
    
    def validate_sarif_result(self, result: Dict[str, Any]) -> None:
        """Validate individual SARIF result structure."""
        assert isinstance(result, dict), "result must be a dict"
        assert 'ruleId' in result, "result must have 'ruleId' key"
        assert 'message' in result, "result must have 'message' key"
        assert 'level' in result, "result must have 'level' key"
        
        # Validate level
        level = result['level']
        assert level in ['none', 'note', 'warning', 'error'], f"Invalid level: {level}"
        
        # Validate message
        message = result['message']
        assert isinstance(message, dict), "message must be a dict"
        assert 'text' in message, "message must have 'text' key"
        assert isinstance(message['text'], str), "message.text must be a string"
    
    def validate_sarif_document(self, doc: Dict[str, Any]) -> None:
        """Validate complete SARIF document."""
        assert isinstance(doc, dict), "SARIF document must be a dict"
        assert '$schema' in doc, "SARIF document must have '$schema' key"
        assert 'version' in doc, "SARIF document must have 'version' key"
        assert 'runs' in doc, "SARIF document must have 'runs' key"
        
        assert doc['version'] == '2.1.0', "SARIF version must be 2.1.0"
        assert isinstance(doc['runs'], list), "runs must be a list"


class TestBanditSARIFParser(TestSARIFCompliance):
    """Test Bandit SARIF parser."""
    
    @pytest.fixture
    def sample_bandit_output(self):
        """Sample Bandit JSON output."""
        return {
            "results": [
                {
                    "filename": "app.py",
                    "line_number": 10,
                    "col_offset": 5,
                    "test_id": "B201",
                    "test_name": "flask_debug_true",
                    "issue_severity": "HIGH",
                    "issue_confidence": "HIGH",
                    "issue_text": "A Flask app appears to be run with debug=True",
                    "issue_cwe": {"id": 78},
                    "code": "app.run(debug=True)"
                },
                {
                    "filename": "utils.py",
                    "line_number": 25,
                    "col_offset": 0,
                    "test_id": "B605",
                    "test_name": "start_process_with_shell_equals_true",
                    "issue_severity": "HIGH",
                    "issue_confidence": "MEDIUM",
                    "issue_text": "Starting a process with shell=True",
                    "issue_cwe": {"id": 78},
                    "code": "subprocess.call(cmd, shell=True)"
                }
            ],
            "version": "1.7.5"
        }
    
    def test_parse_bandit_output(self, sample_bandit_output):
        """Test parsing Bandit output to SARIF."""
        sarif_run = BanditSARIFParser.parse(sample_bandit_output)
        
        # Validate structure
        self.validate_sarif_run(sarif_run)
        
        # Check tool name
        assert sarif_run['tool']['driver']['name'] == 'bandit'
        assert sarif_run['tool']['driver']['version'] == '1.7.5'
        
        # Check results count
        assert len(sarif_run['results']) == 2
        
        # Validate first result
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['ruleId'] == 'B201'
        assert result['level'] == 'error'  # HIGH maps to error
        assert 'Flask' in result['message']['text']
        
        # Check location
        assert 'locations' in result
        location = result['locations'][0]
        assert location['physicalLocation']['artifactLocation']['uri'] == 'app.py'
        assert location['physicalLocation']['region']['startLine'] == 10
        assert location['physicalLocation']['region']['startColumn'] == 5
        
        # Check properties
        assert 'properties' in result
        props = result['properties']
        assert props['severity'] == 'high'
        assert props['confidence'] == 'high'
        assert props['cwe'] == [78]
    
    def test_bandit_cwe_extraction(self, sample_bandit_output):
        """Test CWE ID extraction from Bandit output."""
        sarif_run = BanditSARIFParser.parse(sample_bandit_output)
        
        for result in sarif_run['results']:
            assert 'properties' in result
            assert 'cwe' in result['properties']
            assert result['properties']['cwe'] == [78]


class TestPyLintSARIFParser(TestSARIFCompliance):
    """Test PyLint SARIF parser."""
    
    @pytest.fixture
    def sample_pylint_output(self):
        """Sample PyLint JSON output."""
        return [
            {
                "type": "convention",
                "module": "app",
                "obj": "main",
                "line": 5,
                "column": 0,
                "path": "app.py",
                "symbol": "missing-docstring",
                "message": "Missing function docstring",
                "message-id": "C0116"
            },
            {
                "type": "error",
                "module": "utils",
                "obj": "",
                "line": 15,
                "column": 10,
                "path": "utils.py",
                "symbol": "undefined-variable",
                "message": "Undefined variable 'foo'",
                "message-id": "E0602"
            }
        ]
    
    def test_parse_pylint_output(self, sample_pylint_output):
        """Test parsing PyLint output to SARIF."""
        sarif_run = PyLintSARIFParser.parse(sample_pylint_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'pylint'
        assert len(sarif_run['results']) == 2
        
        # Check convention (note level)
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'note'
        assert result['ruleId'] == 'C0116'
        
        # Check error
        result = sarif_run['results'][1]
        assert result['level'] == 'error'
        assert result['ruleId'] == 'E0602'
        assert 'Undefined variable' in result['message']['text']


class TestESLintSARIFParser(TestSARIFCompliance):
    """Test ESLint SARIF parser."""
    
    @pytest.fixture
    def sample_eslint_output(self):
        """Sample ESLint SARIF output (ESLint native format)."""
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [{
                "tool": {
                    "driver": {
                        "name": "eslint",
                        "version": "8.0.0"
                    }
                },
                "results": [
                    {
                        "ruleId": "no-unused-vars",
                        "level": "error",
                        "message": {"text": "'foo' is defined but never used."},
                        "locations": [{
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/app.js"},
                                "region": {"startLine": 10, "startColumn": 5}
                            }
                        }],
                        "properties": {"severity": "high"}
                    },
                    {
                        "ruleId": "no-console",
                        "level": "warning",
                        "message": {"text": "Unexpected console statement."},
                        "locations": [{
                            "physicalLocation": {
                                "artifactLocation": {"uri": "src/app.js"},
                                "region": {"startLine": 20, "startColumn": 3}
                            }
                        }],
                        "properties": {"severity": "medium"}
                    }
                ]
            }]
        }
    
    def test_parse_eslint_output(self, sample_eslint_output):
        """Test parsing ESLint SARIF output."""
        sarif_run = ESLintSARIFParser.parse(sample_eslint_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'eslint'
        # ESLint parser extracts from existing SARIF runs
        assert len(sarif_run['results']) == 2
        
        # Check error
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'
        assert result['ruleId'] == 'no-unused-vars'
        assert result['properties']['severity'] == 'high'
        
        # Check warning
        result = sarif_run['results'][1]
        assert result['level'] == 'warning'
        assert result['ruleId'] == 'no-console'


class TestSafetySARIFParser(TestSARIFCompliance):
    """Test Safety SARIF parser."""
    
    @pytest.fixture
    def sample_safety_output(self):
        """Sample Safety JSON output."""
        return [
            [
                "django",
                "2.2.10",
                [
                    "52510",
                    "CVE-2021-35042",
                    "<3.2.4,>=3.2",
                    "Django 3.2.x before 3.2.4 has SQL injection vulnerability"
                ]
            ],
            [
                "requests",
                "2.20.0",
                [
                    "51668",
                    "",
                    "<2.31.0",
                    "Requests has security vulnerability in urllib3"
                ]
            ]
        ]
    
    def test_parse_safety_output(self, sample_safety_output):
        """Test parsing Safety output to SARIF."""
        sarif_run = SafetySARIFParser.parse(sample_safety_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'safety'
        assert len(sarif_run['results']) == 2
        
        # Check first vulnerability
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'  # All vulnerabilities are errors
        assert result['ruleId'] == '52510'
        assert 'django==2.2.10' in result['message']['text']
        assert 'SQL injection' in result['message']['text']
        
        # Check properties
        props = result['properties']
        assert props['package'] == 'django'
        assert props['installed_version'] == '2.2.10'
        assert props['cve'] == 'CVE-2021-35042'
        assert props['severity'] == 'high'


class TestSemgrepSARIFParser(TestSARIFCompliance):
    """Test Semgrep SARIF parser."""
    
    @pytest.fixture
    def sample_semgrep_output(self):
        """Sample Semgrep JSON output."""
        return {
            "results": [
                {
                    "check_id": "python.django.security.injection.sql-injection",
                    "path": "views.py",
                    "start": {"line": 10, "col": 5},
                    "end": {"line": 10, "col": 30},
                    "extra": {
                        "message": "SQL injection vulnerability detected",
                        "severity": "ERROR",
                        "metadata": {
                            "cwe": ["CWE-89"],
                            "owasp": ["A1:2017-Injection"]
                        }
                    }
                }
            ]
        }
    
    def test_parse_semgrep_output(self, sample_semgrep_output):
        """Test parsing Semgrep output to SARIF."""
        sarif_run = SemgrepSARIFParser.parse(sample_semgrep_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'semgrep'
        assert len(sarif_run['results']) == 1
        
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'
        assert result['ruleId'] == 'python.django.security.injection.sql-injection'
        
        # Check CWE extraction
        props = result['properties']
        assert props['cwe'] == [89]
        assert props['owasp'] == ['A1:2017-Injection']


class TestFlake8SARIFParser(TestSARIFCompliance):
    """Test Flake8 SARIF parser."""
    
    @pytest.fixture
    def sample_flake8_output(self):
        """Sample Flake8 text output."""
        return """app.py:10:5: E501 line too long (82 > 79 characters)
app.py:15:1: W293 blank line contains whitespace
utils.py:20:10: E302 expected 2 blank lines, found 1"""
    
    def test_parse_flake8_output(self, sample_flake8_output):
        """Test parsing Flake8 output to SARIF."""
        sarif_run = Flake8SARIFParser.parse(sample_flake8_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'flake8'
        assert len(sarif_run['results']) == 3
        
        # Check first result (E code = error)
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'
        assert result['ruleId'] == 'E501'
        assert 'line too long' in result['message']['text']
        
        # Check location
        location = result['locations'][0]
        assert location['physicalLocation']['artifactLocation']['uri'] == 'app.py'
        assert location['physicalLocation']['region']['startLine'] == 10
        assert location['physicalLocation']['region']['startColumn'] == 5


class TestRuffSARIFParser(TestSARIFCompliance):
    """Test Ruff SARIF parser."""
    
    @pytest.fixture
    def sample_ruff_output(self):
        """Sample Ruff JSON output."""
        return [
            {
                "code": "F401",
                "message": "'os' imported but unused",
                "location": {"row": 1, "column": 8},
                "end_location": {"row": 1, "column": 10},
                "filename": "app.py"
            },
            {
                "code": "E501",
                "message": "Line too long (100 > 88 characters)",
                "location": {"row": 10, "column": 88},
                "filename": "app.py"
            }
        ]
    
    def test_parse_ruff_output(self, sample_ruff_output):
        """Test parsing Ruff output to SARIF."""
        sarif_run = RuffSARIFParser.parse(sample_ruff_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'ruff'
        assert len(sarif_run['results']) == 2
        
        # Check first result
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['ruleId'] == 'F401'


class TestMypySARIFParser(TestSARIFCompliance):
    """Test Mypy SARIF parser."""
    
    @pytest.fixture
    def sample_mypy_text_output(self):
        """Sample Mypy text output."""
        return """app.py:10:5: error: Incompatible types in assignment
utils.py:20:10: warning: unused 'type: ignore' comment"""
    
    @pytest.fixture
    def sample_mypy_json_output(self):
        """Sample Mypy JSON output."""
        return [
            {
                "file": "app.py",
                "line": 10,
                "column": 5,
                "severity": "error",
                "message": "Incompatible types in assignment",
                "error_code": "assignment"
            }
        ]
    
    def test_parse_mypy_text_output(self, sample_mypy_text_output):
        """Test parsing Mypy text output to SARIF."""
        sarif_run = MypySARIFParser.parse(sample_mypy_text_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'mypy'
        assert len(sarif_run['results']) == 2
        
        # Check error
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'
        # Mypy message format: "severity: message"
        assert result['message']['text'] in ['error: Incompatible types in assignment', 'error']
    
    def test_parse_mypy_json_output(self, sample_mypy_json_output):
        """Test parsing Mypy JSON output to SARIF."""
        sarif_run = MypySARIFParser.parse(sample_mypy_json_output)
        
        self.validate_sarif_run(sarif_run)
        assert len(sarif_run['results']) == 1
        
        result = sarif_run['results'][0]
        assert result['ruleId'] == 'assignment'
        assert result['level'] == 'error'


class TestVultureSARIFParser(TestSARIFCompliance):
    """Test Vulture SARIF parser."""
    
    @pytest.fixture
    def sample_vulture_output(self):
        """Sample Vulture text output."""
        return """app.py:10: unused variable 'x' (60% confidence)
app.py:25: unused function 'old_function' (100% confidence)
utils.py:5: unreachable code after 'return' (80% confidence)"""
    
    def test_parse_vulture_output(self, sample_vulture_output):
        """Test parsing Vulture output to SARIF."""
        sarif_run = VultureSARIFParser.parse(sample_vulture_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'vulture'
        assert len(sarif_run['results']) == 3
        
        # Check first result (60% confidence = low severity = note level)
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'note'
        assert result['ruleId'] == 'dead-code'
        assert 'unused variable' in result['message']['text']
        assert result['properties']['confidence'] == '60'
        
        # Check high confidence result (100% = medium severity = warning)
        result = sarif_run['results'][1]
        assert result['level'] == 'warning'
        assert result['properties']['confidence'] == '100'


class TestZAPSARIFParser(TestSARIFCompliance):
    """Test ZAP SARIF parser."""
    
    @pytest.fixture
    def sample_zap_output(self):
        """Sample ZAP custom format output."""
        return {
            "alerts": [
                {
                    "alert": "SQL Injection",
                    "riskcode": 3,  # High risk (numeric code)
                    "confidence": 2,  # Medium confidence (numeric code)
                    "cweid": "89",
                    "wascid": "19",
                    "description": "SQL injection may be possible",
                    "solution": "Use prepared statements",
                    "reference": "https://owasp.org/www-community/attacks/SQL_Injection",
                    "instances": [
                        {
                            "uri": "http://example.com/api/users",
                            "method": "POST",
                            "param": "id",
                            "attack": "' OR '1'='1",
                            "evidence": "SQL error message"
                        }
                    ]
                }
            ]
        }
    
    def test_parse_zap_output(self, sample_zap_output):
        """Test parsing ZAP output to SARIF."""
        sarif_run = ZAPSARIFParser.parse(sample_zap_output)
        
        self.validate_sarif_run(sarif_run)
        assert sarif_run['tool']['driver']['name'] == 'zap'
        assert len(sarif_run['results']) == 1
        
        result = sarif_run['results'][0]
        self.validate_sarif_result(result)
        assert result['level'] == 'error'  # High risk maps to error
        assert 'SQL Injection' in result['message']['text']
        
        # Check properties
        props = result['properties']
        assert props['risk'] == 'high'
        assert props['confidence'] == 'medium'
        # CWE is extracted as string with prefix
        assert props['cwe'] == ['CWE-89'] or props['cwe'] == [89]
        assert props['wasc'] == 19
        assert props['httpMethod'] == 'POST'


class TestSARIFDocument:
    """Test complete SARIF document building."""
    
    def test_build_sarif_document_single_run(self):
        """Test building SARIF document with single run."""
        sample_output = {"results": [{"filename": "test.py", "line_number": 1, "test_id": "B101", 
                                      "issue_severity": "LOW", "issue_confidence": "HIGH",
                                      "issue_text": "Test issue"}]}
        sarif_run = BanditSARIFParser.parse(sample_output)
        
        doc = build_sarif_document([sarif_run])
        
        assert doc['$schema'] == 'https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json'
        assert doc['version'] == '2.1.0'
        assert len(doc['runs']) == 1
        assert doc['runs'][0] == sarif_run
    
    def test_build_sarif_document_multiple_runs(self):
        """Test building SARIF document with multiple runs."""
        bandit_output = {"results": [{"filename": "test.py", "line_number": 1, "test_id": "B101",
                                      "issue_severity": "LOW", "issue_confidence": "HIGH", 
                                      "issue_text": "Test"}]}
        pylint_output = [{"type": "error", "path": "test.py", "line": 5, "symbol": "test",
                         "message": "Test", "message-id": "E001"}]
        
        bandit_run = BanditSARIFParser.parse(bandit_output)
        pylint_run = PyLintSARIFParser.parse(pylint_output)
        
        doc = build_sarif_document([bandit_run, pylint_run])
        
        assert len(doc['runs']) == 2
        assert doc['runs'][0]['tool']['driver']['name'] == 'bandit'
        assert doc['runs'][1]['tool']['driver']['name'] == 'pylint'


class TestSARIFSeverityMapping:
    """Test severity level mapping across parsers."""
    
    def test_bandit_severity_mapping(self):
        """Test Bandit severity to SARIF level mapping."""
        test_cases = [
            ("HIGH", "error"),
            ("MEDIUM", "warning"),
            ("LOW", "warning"),
            ("INFO", "note")
        ]
        
        for tool_severity, expected_level in test_cases:
            output = {"results": [{"filename": "test.py", "line_number": 1, "test_id": "B001",
                                  "issue_severity": tool_severity, "issue_confidence": "HIGH",
                                  "issue_text": "Test"}]}
            sarif_run = BanditSARIFParser.parse(output)
            assert sarif_run['results'][0]['level'] == expected_level
    
    def test_pylint_severity_mapping(self):
        """Test PyLint type to SARIF level mapping."""
        test_cases = [
            ("fatal", "error"),
            ("error", "error"),
            ("warning", "warning"),
            ("refactor", "note"),
            ("convention", "note")
        ]
        
        for pylint_type, expected_level in test_cases:
            output = [{"type": pylint_type, "path": "test.py", "line": 1, "symbol": "test",
                      "message": "Test", "message-id": "X001"}]
            sarif_run = PyLintSARIFParser.parse(output)
            assert sarif_run['results'][0]['level'] == expected_level
    
    def test_zap_risk_mapping(self):
        """Test ZAP risk level to SARIF level mapping."""
        test_cases = [
            (3, "error"),      # High risk
            (2, "warning"),    # Medium risk
            (1, "warning"),    # Low risk
            (0, "note")        # Informational
        ]
        
        for riskcode, expected_level in test_cases:
            output = {"alerts": [{"alert": "Test", "riskcode": riskcode, "confidence": 2,
                                 "description": "Test"}]}
            sarif_run = ZAPSARIFParser.parse(output)
            assert sarif_run['results'][0]['level'] == expected_level


class TestSARIFErrorHandling:
    """Test error handling in SARIF parsers."""
    
    def test_bandit_invalid_input(self):
        """Test Bandit parser with invalid input."""
        sarif_run = BanditSARIFParser.parse(None)
        assert sarif_run['tool']['driver']['name'] == 'bandit'
        assert len(sarif_run['results']) == 0
    
    def test_pylint_invalid_input(self):
        """Test PyLint parser with invalid input."""
        sarif_run = PyLintSARIFParser.parse("not a list")
        assert sarif_run['tool']['driver']['name'] == 'pylint'
        assert len(sarif_run['results']) == 0
    
    def test_zap_empty_alerts(self):
        """Test ZAP parser with empty alerts."""
        sarif_run = ZAPSARIFParser.parse({"alerts": []})
        assert sarif_run['tool']['driver']['name'] == 'zap'
        assert len(sarif_run['results']) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
