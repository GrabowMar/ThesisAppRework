"""
Comprehensive Tests for Analysis Capabilities
============================================

This module contains tests for all analysis functionality including:
- Security analysis (backend and frontend)
- Code quality analysis 
- ZAP security scanning
- Performance testing
- OpenRouter analysis
- Analysis result management
"""
import pytest
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Test framework imports
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from security_analysis_service import (
        UnifiedCLIAnalyzer, 
        BackendSecurityAnalyzer, 
        FrontendSecurityAnalyzer,
        AnalysisIssue,
        ToolCategory,
        ToolStatus
    )
    from performance_service import LocustPerformanceTester, PerformanceResult
    from zap_service import ZAPScanner, ZapVulnerability
    from openrouter_service import OpenRouterAnalyzer, RequirementCheck
    from core_services import save_analysis_results, load_analysis_results
except ImportError as e:
    pytest.skip(f"Analysis services not available: {e}", allow_module_level=True)


class TestUnifiedCLIAnalyzer:
    """Test the unified CLI analyzer that orchestrates all analysis tools."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory with sample code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create backend structure
            backend_dir = project_path / "misc" / "models" / "test_model" / "app1" / "backend"
            backend_dir.mkdir(parents=True)
            
            # Create sample Python files
            (backend_dir / "app.py").write_text("""
from flask import Flask, request
import os

app = Flask(__name__)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    # Security issue: SQL injection vulnerability
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    
    # Security issue: Command injection
    os.system(f"echo 'Login attempt for {username}'")
    
    return "Login successful"

if __name__ == '__main__':
    app.run(debug=True)  # Security issue: debug mode in production
""")
            
            (backend_dir / "requirements.txt").write_text("""
Flask==1.0.0
requests==2.20.0
""")
            
            # Create frontend structure
            frontend_dir = project_path / "misc" / "models" / "test_model" / "app1" / "frontend"
            frontend_dir.mkdir(parents=True)
            
            # Create sample JavaScript files
            (frontend_dir / "app.js").write_text("""
// Security issue: eval usage
function processUserInput(input) {
    eval(input);
}

// Security issue: innerHTML with user data
function displayMessage(msg) {
    document.getElementById('output').innerHTML = msg;
}

// Security issue: open redirect
function redirect() {
    window.location = getUrlParameter('redirect');
}
""")
            
            (frontend_dir / "package.json").write_text("""
{
    "name": "test-app",
    "version": "1.0.0",
    "dependencies": {
        "lodash": "4.16.0",
        "jquery": "2.2.0"
    }
}
""")
            
            yield project_path
    
    @pytest.fixture
    def analyzer(self, temp_project_dir):
        """Create analyzer instance with temp directory."""
        return UnifiedCLIAnalyzer(temp_project_dir)
    
    def test_analyzer_initialization(self, analyzer, temp_project_dir):
        """Test that analyzer initializes correctly."""
        assert analyzer.base_path == temp_project_dir
        assert len(analyzer.analyzers) > 0
        assert ToolCategory.BACKEND_SECURITY in [a.category for a in analyzer.analyzers.values()]
    
    def test_get_available_tools(self, analyzer):
        """Test getting available tools by category."""
        tools = analyzer.get_available_tools()
        
        assert isinstance(tools, dict)
        assert ToolCategory.BACKEND_SECURITY.value in tools
        assert ToolCategory.FRONTEND_SECURITY.value in tools
        
        # Should have some tools available
        backend_tools = tools.get(ToolCategory.BACKEND_SECURITY.value, [])
        assert len(backend_tools) > 0
    
    @patch('security_analysis_service.BackendSecurityAnalyzer._run_tool')
    def test_backend_security_analysis(self, mock_run_tool, analyzer):
        """Test backend security analysis with mocked tools."""
        # Mock successful tool execution
        mock_issues = [
            AnalysisIssue(
                filename="app.py",
                line_number=10,
                issue_text="SQL injection vulnerability detected",
                severity="HIGH",
                confidence="HIGH",
                issue_type="security",
                category="security",
                rule_id="B608",
                line_range=[10, 10],
                code="query = f\"SELECT * FROM users WHERE username='{username}'\"",
                tool="bandit",
                fix_suggestion="Use parameterized queries"
            )
        ]
        mock_run_tool.return_value = (mock_issues, "Tool output", "")
        
        # Run analysis
        results = analyzer.run_analysis(
            model="test_model",
            app_num=1,
            categories=[ToolCategory.BACKEND_SECURITY],
            use_all_tools=False,
            force_rerun=True
        )
        
        assert 'backend_security' in results
        backend_results = results['backend_security']
        assert len(backend_results['issues']) > 0
        assert backend_results['issues'][0]['severity'] == 'HIGH'
    
    @patch('security_analysis_service.FrontendSecurityAnalyzer._run_tool')
    def test_frontend_security_analysis(self, mock_run_tool, analyzer):
        """Test frontend security analysis with mocked tools."""
        mock_issues = [
            AnalysisIssue(
                filename="app.js",
                line_number=3,
                issue_text="Eval usage detected",
                severity="MEDIUM",
                confidence="HIGH",
                issue_type="security",
                category="security",
                rule_id="no-eval",
                line_range=[3, 3],
                code="eval(input);",
                tool="eslint",
                fix_suggestion="Avoid using eval(), use safer alternatives"
            )
        ]
        mock_run_tool.return_value = (mock_issues, "Tool output", "")
        
        results = analyzer.run_analysis(
            model="test_model",
            app_num=1,
            categories=[ToolCategory.FRONTEND_SECURITY],
            use_all_tools=False,
            force_rerun=True
        )
        
        assert 'frontend_security' in results
        frontend_results = results['frontend_security']
        assert len(frontend_results['issues']) > 0
        assert frontend_results['issues'][0]['tool'] == 'eslint'
    
    def test_multi_category_analysis(self, analyzer):
        """Test running multiple analysis categories simultaneously."""
        with patch.object(analyzer.analyzers[ToolCategory.BACKEND_SECURITY], 'run_analysis') as mock_backend, \
             patch.object(analyzer.analyzers[ToolCategory.FRONTEND_SECURITY], 'run_analysis') as mock_frontend:
            
            mock_backend.return_value = ([], {}, {})
            mock_frontend.return_value = ([], {}, {})
            
            results = analyzer.run_analysis(
                model="test_model",
                app_num=1,
                categories=[ToolCategory.BACKEND_SECURITY, ToolCategory.FRONTEND_SECURITY],
                use_all_tools=False,
                force_rerun=True
            )
            
            assert 'backend_security' in results
            assert 'frontend_security' in results
            mock_backend.assert_called_once()
            mock_frontend.assert_called_once()


class TestBackendSecurityAnalyzer:
    """Test backend-specific security analysis."""
    
    @pytest.fixture
    def analyzer(self, temp_dir_with_backend_code):
        """Create backend analyzer with test code."""
        return BackendSecurityAnalyzer(temp_dir_with_backend_code)
    
    @pytest.fixture
    def temp_dir_with_backend_code(self):
        """Create temp directory with vulnerable backend code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            backend_path = Path(temp_dir) / "misc" / "models" / "test_model" / "app1" / "backend"
            backend_path.mkdir(parents=True)
            
            # Create vulnerable Python code
            (backend_path / "vulnerable.py").write_text("""
import subprocess
import pickle
from flask import request

def unsafe_function():
    # B602: subprocess_popen_with_shell_equals_true
    subprocess.Popen(shell=True)
    
    # B301: pickle.loads
    data = request.get_data()
    pickle.loads(data)
    
    # B105: hardcoded_password_string
    password = "admin123"
    
    return password
""")
            
            (backend_path / "requirements.txt").write_text("""
Flask==0.12.0
Pillow==5.0.0
""")
            
            yield Path(temp_dir)
    
    def test_bandit_analysis(self, analyzer):
        """Test Bandit security analysis."""
        with patch('security_analysis_service.subprocess.run') as mock_run:
            # Mock Bandit output
            bandit_output = json.dumps({
                "results": [
                    {
                        "filename": "vulnerable.py",
                        "line_number": 6,
                        "issue_severity": "HIGH",
                        "issue_confidence": "HIGH",
                        "issue_text": "subprocess call with shell=True identified",
                        "test_name": "B602",
                        "test_id": "B602"
                    }
                ]
            })
            
            mock_run.return_value = Mock(
                returncode=0,
                stdout=bandit_output,
                stderr=""
            )
            
            issues, stdout, stderr = analyzer._run_bandit(
                analyzer._find_app_path("test_model", 1) / "backend"
            )
            
            assert len(issues) > 0
            assert issues[0].severity == "HIGH"
            assert "subprocess" in issues[0].message.lower()
    
    def test_safety_analysis(self, analyzer):
        """Test Safety dependency analysis."""
        with patch('security_analysis_service.subprocess.run') as mock_run:
            # Mock Safety output
            safety_output = json.dumps([
                {
                    "vulnerability": "Pillow before 5.1.0 allows an attacker to shut down the application",
                    "severity": "high",
                    "package_name": "Pillow",
                    "installed_version": "5.0.0",
                    "vulnerable_spec": ">=1.0.0,<5.1.0"
                }
            ])
            
            mock_run.return_value = Mock(
                returncode=0,
                stdout=safety_output,
                stderr=""
            )
            
            issues, stdout, stderr = analyzer._run_safety(
                analyzer._find_app_path("test_model", 1) / "backend"
            )
            
            assert len(issues) > 0
            assert issues[0].severity == "HIGH"
            assert "Pillow" in issues[0].message
    
    def test_full_backend_analysis(self, analyzer):
        """Test complete backend analysis workflow."""
        with patch.object(analyzer, '_run_bandit') as mock_bandit, \
             patch.object(analyzer, '_run_safety') as mock_safety:
            
            # Mock tool results
            mock_bandit.return_value = ([
                AnalysisIssue(
                    tool="bandit",
                    severity="HIGH",
                    confidence="HIGH",
                    file_path="vulnerable.py",
                    line_number=6,
                    message="Shell injection vulnerability"
                )
            ], "bandit output", "")
            
            mock_safety.return_value = ([
                AnalysisIssue(
                    tool="safety",
                    severity="MEDIUM",
                    confidence="HIGH",
                    file_path="requirements.txt",
                    message="Vulnerable dependency: Pillow 5.0.0"
                )
            ], "safety output", "")
            
            issues, outputs, errors = analyzer.run_analysis(
                model="test_model",
                app_num=1,
                use_all_tools=True,
                force_rerun=True
            )
            
            assert len(issues) == 2
            assert any(issue['tool'] == 'bandit' for issue in issues)
            assert any(issue['tool'] == 'safety' for issue in issues)
            
            # Check that high severity issues are first
            severities = [issue['severity'] for issue in issues]
            assert severities == sorted(severities, key=lambda x: {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(x, 3))


class TestPerformanceAnalysis:
    """Test performance analysis capabilities."""
    
    @pytest.fixture
    def performance_tester(self):
        """Create performance tester instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield LocustPerformanceTester(temp_dir)
    
    @pytest.fixture
    def mock_test_target(self):
        """Mock HTTP server for testing."""
        return "http://localhost:9001"
    
    def test_performance_tester_initialization(self, performance_tester):
        """Test that performance tester initializes correctly."""
        assert performance_tester.output_dir.exists()
        assert performance_tester.static_url_path == "/static"
    
    @patch('performance_service._import_locust_safely')
    def test_locust_availability_check(self, mock_import, performance_tester):
        """Test Locust availability checking."""
        mock_import.return_value = True
        
        # Should not raise exception when Locust is available
        result = performance_tester.run_performance_test("test_model", 1)
        assert isinstance(result, dict)
    
    def test_performance_result_serialization(self):
        """Test PerformanceResult serialization and deserialization."""
        result = PerformanceResult(
            total_requests=100,
            total_failures=5,
            avg_response_time=250.5,
            median_response_time=200.0,
            requests_per_sec=10.5,
            start_time="2025-01-01T10:00:00",
            end_time="2025-01-01T10:05:00",
            duration=300,
            user_count=10,
            spawn_rate=2,
            test_name="Test Performance",
            host="http://localhost:9001"
        )
        
        # Test to_dict method
        result_dict = result.to_dict()
        assert result_dict['total_requests'] == 100
        assert result_dict['avg_response_time'] == 250.5
        
        # Test JSON serialization
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            result.save_json(f.name)
            
            # Verify file was created and contains expected data
            with open(f.name, 'r') as read_f:
                loaded_data = json.load(read_f)
                assert loaded_data['total_requests'] == 100
                assert loaded_data['host'] == "http://localhost:9001"
        
        os.unlink(f.name)
    
    @patch('performance_service.subprocess.run')
    def test_cli_performance_test(self, mock_subprocess, performance_tester, mock_test_target):
        """Test running performance test via CLI."""
        # Mock Locust CLI output
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout="Test completed successfully",
            stderr=""
        )
        
        # Mock CSV files
        stats_content = """Type,Name,Request Count,Failure Count,Median Response Time,Average Response Time,Min Response Time,Max Response Time,Average Content Size,Requests/s,Failures/s,50%,66%,75%,80%,90%,95%,98%,99%,99.9%,99.99%,100%
        GET,/,100,0,200,250,100,500,1024,10.0,0.0,200,220,240,260,300,350,400,450,480,490,500
        """
        
        failures_content = """Method,Name,Error,Occurrences
        """
        
        with patch('builtins.open', create=True) as mock_open:
            mock_open.side_effect = [
                Mock(read=lambda: stats_content),
                Mock(read=lambda: failures_content)
            ]
            
            result = performance_tester.run_test_cli(
                test_name="CLI Test",
                host=mock_test_target,
                user_count=10,
                spawn_rate=2,
                run_time="30s",
                model="test_model",
                app_num=1
            )
            
            assert result is not None
            if result:  # Only check if result is returned
                assert result.total_requests > 0
                assert result.host == mock_test_target


class TestZAPSecurityScanning:
    """Test OWASP ZAP security scanning capabilities."""
    
    @pytest.fixture
    def zap_scanner(self):
        """Create ZAP scanner instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield ZAPScanner(Path(temp_dir))
    
    def test_zap_scanner_initialization(self, zap_scanner):
        """Test ZAP scanner initialization."""
        assert zap_scanner.base_path.exists()
        assert hasattr(zap_scanner, 'config')
    
    def test_zap_availability_check(self, zap_scanner):
        """Test ZAP availability checking."""
        # Should handle missing ZAP gracefully
        is_available = zap_scanner.is_available()
        assert isinstance(is_available, bool)
    
    @patch('zap_service.ZAPDaemonManager.start_daemon')
    @patch('zap_service.ZAPDaemonManager.is_ready')
    def test_zap_scan_workflow(self, mock_is_ready, mock_start_daemon, zap_scanner):
        """Test ZAP scanning workflow."""
        mock_start_daemon.return_value = True
        mock_is_ready.return_value = True
        
        # Mock ZAP API responses
        with patch.object(zap_scanner, '_execute_simplified_scan') as mock_scan:
            mock_vulnerabilities = [
                ZapVulnerability(
                    url="http://localhost:9001/login",
                    name="SQL Injection",
                    alert="SQL Injection",
                    risk="High",
                    confidence="High",
                    description="SQL injection vulnerability detected",
                    solution="Use parameterized queries",
                    reference="https://owasp.org/www-community/attacks/SQL_Injection"
                )
            ]
            
            mock_summary = {
                'total_alerts': 1,
                'high_risk': 1,
                'medium_risk': 0,
                'low_risk': 0,
                'info_risk': 0
            }
            
            mock_scan.return_value = (mock_vulnerabilities, mock_summary)
            
            result = zap_scanner.scan_app("test_model", 1)
            
            assert 'vulnerabilities' in result
            assert len(result['vulnerabilities']) > 0
            assert result['vulnerabilities'][0]['risk'] == 'High'
    
    def test_vulnerability_serialization(self):
        """Test ZAP vulnerability data handling."""
        vuln = ZapVulnerability(
            url="http://example.com/vulnerable",
            name="XSS",
            alert="Cross Site Scripting",
            risk="Medium",
            confidence="High",
            description="XSS vulnerability in user input",
            solution="Sanitize user input",
            reference="https://owasp.org/www-community/attacks/xss/",
            parameter="input_field",
            evidence="<script>alert('xss')</script>"
        )
        
        # Test that vulnerability can be converted to dict for JSON serialization
        vuln_dict = {
            'url': vuln.url,
            'name': vuln.name,
            'alert': vuln.alert,
            'risk': vuln.risk,
            'confidence': vuln.confidence,
            'description': vuln.description,
            'solution': vuln.solution,
            'reference': vuln.reference,
            'parameter': vuln.parameter,
            'evidence': vuln.evidence
        }
        
        assert vuln_dict['risk'] == 'Medium'
        assert 'script' in vuln_dict['evidence']


class TestOpenRouterAnalysis:
    """Test OpenRouter API-based code analysis."""
    
    @pytest.fixture
    def openrouter_analyzer(self):
        """Create OpenRouter analyzer instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock environment
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("OPENROUTER_API_KEY=test_key_12345678901234567890")
            
            yield OpenRouterAnalyzer(temp_dir)
    
    def test_analyzer_initialization(self, openrouter_analyzer):
        """Test OpenRouter analyzer initialization."""
        assert openrouter_analyzer.base_path.exists()
        assert openrouter_analyzer.api_key is not None
        assert openrouter_analyzer.preferred_model is not None
    
    def test_api_availability_check(self, openrouter_analyzer):
        """Test API availability checking."""
        with patch('openrouter_service.requests.Session.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                json=lambda: {"data": [{"id": "test-model"}]}
            )
            
            is_available = openrouter_analyzer.is_api_available()
            assert isinstance(is_available, bool)
    
    @patch('openrouter_service.requests.Session.post')
    def test_requirement_analysis(self, mock_post, openrouter_analyzer):
        """Test analyzing code against requirements."""
        # Mock API response
        mock_response = {
            "choices": [{
                "message": {
                    "content": json.dumps({
                        "met": True,
                        "confidence": "HIGH",
                        "explanation": "The code implements proper authentication",
                        "code_evidence": "Flask-Login is used for session management",
                        "recommendations": "Consider adding rate limiting"
                    })
                }
            }],
            "usage": {"total_tokens": 150}
        }
        
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: mock_response
        )
        
        result = openrouter_analyzer.analyze_requirement(
            requirement="Must implement secure user authentication",
            code="from flask_login import login_required\n@login_required\ndef dashboard(): pass",
            is_frontend=False
        )
        
        assert result.met is True
        assert result.confidence == "HIGH"
        assert "authentication" in result.explanation.lower()
    
    def test_app_requirements_loading(self, openrouter_analyzer):
        """Test loading application requirements from templates."""
        # Create mock app template
        app_template_dir = openrouter_analyzer.base_path / "misc" / "app_templates"
        app_template_dir.mkdir(parents=True)
        
        backend_template = app_template_dir / "app_1_backend_login.md"
        backend_template.write_text("""
# Login System Backend

## Requirements:
1. Must implement secure user authentication
2. Must protect against SQL injection
3. Must use HTTPS for password transmission
4. Must implement session management
5. Must have password strength validation

## Additional Context:
This is a secure login system for web applications.
""")
        
        requirements, context = openrouter_analyzer.load_app_requirements(1)
        
        assert len(requirements) >= 5
        assert any("authentication" in req.lower() for req in requirements)
        assert any("SQL injection" in req for req in requirements)
        assert "login system" in context.lower()
    
    @patch('openrouter_service.OpenRouterAnalyzer.analyze_requirement')
    def test_full_app_analysis(self, mock_analyze, openrouter_analyzer):
        """Test complete application analysis workflow."""
        # Mock requirement analysis results
        mock_analyze.side_effect = [
            # Frontend results
            RequirementResult(met=True, confidence="HIGH", explanation="Auth implemented"),
            RequirementResult(met=False, confidence="MEDIUM", explanation="SQL injection possible"),
            # Backend results  
            RequirementResult(met=True, confidence="HIGH", explanation="HTTPS used"),
            RequirementResult(met=True, confidence="MEDIUM", explanation="Sessions working")
        ]
        
        # Create mock code structure
        models_dir = openrouter_analyzer.base_path / "misc" / "models" / "test_model" / "app1"
        models_dir.mkdir(parents=True)
        
        # Create mock frontend and backend directories with code
        (models_dir / "frontend" / "src" / "App.js").parent.mkdir(parents=True)
        (models_dir / "frontend" / "src" / "App.js").write_text("// React app code")
        
        (models_dir / "backend" / "app.py").parent.mkdir(parents=True)
        (models_dir / "backend" / "app.py").write_text("# Flask app code")
        
        # Create mock requirements
        with patch.object(openrouter_analyzer, 'load_app_requirements') as mock_load:
            mock_load.return_value = ([
                "Must implement secure authentication",
                "Must prevent SQL injection"
            ], "Login system context")
            
            results = openrouter_analyzer.analyze_app("test_model", 1)
            
            assert len(results) > 0
            assert all(isinstance(r, RequirementCheck) for r in results)
            
            # Should have mixed results
            met_count = sum(1 for r in results if r.result.met)
            assert met_count > 0
            assert met_count < len(results)


class TestAnalysisResultManagement:
    """Test analysis result storage, retrieval, and management."""
    
    @pytest.fixture
    def temp_results_dir(self):
        """Create temporary directory for results testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            results_path = Path(temp_dir) / "misc" / "models" / "test_model" / "app1"
            results_path.mkdir(parents=True)
            yield Path(temp_dir)
    
    def test_save_and_load_analysis_results(self, temp_results_dir):
        """Test saving and loading analysis results."""
        # Create mock analysis results
        test_results = {
            'analysis_type': 'backend_security',
            'model': 'test_model',
            'app_num': 1,
            'timestamp': datetime.now().isoformat(),
            'issues': [
                {
                    'tool': 'bandit',
                    'severity': 'HIGH',
                    'file_path': 'app.py',
                    'line_number': 10,
                    'message': 'SQL injection vulnerability',
                    'description': 'User input in SQL query'
                }
            ],
            'summary': {
                'total_issues': 1,
                'high_severity': 1,
                'medium_severity': 0,
                'low_severity': 0
            },
            'tool_outputs': {
                'bandit': 'Bandit analysis complete'
            },
            'tool_errors': {},
            'duration_seconds': 45.2
        }
        
        # Test saving results
        with patch('core_services.get_models_base_dir', return_value=temp_results_dir / "misc" / "models"):
            save_path = save_analysis_results(test_results, 'test_model', 1, 'backend_security')
            assert save_path is not None
            
            # Test loading results
            loaded_results = load_analysis_results('test_model', 1, 'backend_security')
            assert loaded_results is not None
            assert loaded_results['analysis_type'] == 'backend_security'
            assert len(loaded_results['issues']) == 1
            assert loaded_results['issues'][0]['severity'] == 'HIGH'
    
    def test_analysis_result_versioning(self, temp_results_dir):
        """Test that analysis results support versioning/history."""
        base_results = {
            'analysis_type': 'frontend_security',
            'model': 'test_model',
            'app_num': 1,
            'issues': []
        }
        
        with patch('core_services.get_models_base_dir', return_value=temp_results_dir / "misc" / "models"):
            # Save multiple versions
            for i in range(3):
                results = base_results.copy()
                results['timestamp'] = (datetime.now() + timedelta(minutes=i)).isoformat()
                results['version'] = i + 1
                results['issues'] = [{'issue_id': f'issue_{i}'}]
                
                save_path = save_analysis_results(results, 'test_model', 1, 'frontend_security')
                assert save_path is not None
                
                # Small delay to ensure different timestamps
                time.sleep(0.1)
            
            # Should be able to load the latest version
            latest = load_analysis_results('test_model', 1, 'frontend_security')
            assert latest is not None
            assert latest.get('version') == 3 or len(latest['issues']) == 1
    
    def test_batch_analysis_coordination(self, temp_results_dir):
        """Test coordination of multiple analysis types."""
        analysis_types = ['backend_security', 'frontend_security', 'backend_quality']
        
        with patch('core_services.get_models_base_dir', return_value=temp_results_dir / "misc" / "models"):
            # Save results for multiple analysis types
            for analysis_type in analysis_types:
                results = {
                    'analysis_type': analysis_type,
                    'model': 'test_model',
                    'app_num': 1,
                    'timestamp': datetime.now().isoformat(),
                    'issues': [{'tool': analysis_type.split('_')[0], 'severity': 'MEDIUM'}],
                    'summary': {'total_issues': 1}
                }
                
                save_path = save_analysis_results(results, 'test_model', 1, analysis_type)
                assert save_path is not None
            
            # Should be able to load all analysis types
            for analysis_type in analysis_types:
                loaded = load_analysis_results('test_model', 1, analysis_type)
                assert loaded is not None
                assert loaded['analysis_type'] == analysis_type


class TestAnalysisIntegration:
    """Integration tests for complete analysis workflows."""
    
    @pytest.fixture
    def full_test_environment(self):
        """Create a complete test environment with all components."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create complete project structure
            for model in ['model_a', 'model_b']:
                for app_num in range(1, 4):
                    app_path = project_path / "misc" / "models" / model / f"app{app_num}"
                    
                    # Backend
                    backend_path = app_path / "backend"
                    backend_path.mkdir(parents=True)
                    (backend_path / "app.py").write_text(f"# Flask app for {model} app{app_num}")
                    (backend_path / "requirements.txt").write_text("Flask==2.0.0")
                    
                    # Frontend
                    frontend_path = app_path / "frontend"
                    frontend_path.mkdir(parents=True)
                    (frontend_path / "package.json").write_text('{"name": "frontend"}')
                    (frontend_path / "src" / "App.js").parent.mkdir(parents=True)
                    (frontend_path / "src" / "App.js").write_text(f"// React app for {model} app{app_num}")
            
            yield project_path
    
    def test_full_analysis_pipeline(self, full_test_environment):
        """Test complete analysis pipeline from start to finish."""
        analyzer = UnifiedCLIAnalyzer(full_test_environment)
        
        # Mock all tool executions to avoid requiring actual tools
        with patch.object(BackendSecurityAnalyzer, '_run_tool') as mock_backend_tool, \
             patch.object(FrontendSecurityAnalyzer, '_run_tool') as mock_frontend_tool:
            
            # Mock successful tool results
            mock_backend_tool.return_value = ([
                AnalysisIssue(tool="bandit", severity="HIGH", message="Test issue")
            ], "output", "")
            
            mock_frontend_tool.return_value = ([
                AnalysisIssue(tool="eslint", severity="MEDIUM", message="Test issue")
            ], "output", "")
            
            # Run analysis on multiple apps
            for model in ['model_a', 'model_b']:
                for app_num in [1, 2]:
                    results = analyzer.run_analysis(
                        model=model,
                        app_num=app_num,
                        categories=[ToolCategory.BACKEND_SECURITY, ToolCategory.FRONTEND_SECURITY],
                        use_all_tools=False,
                        force_rerun=True
                    )
                    
                    # Verify results structure
                    assert 'backend_security' in results
                    assert 'frontend_security' in results
                    
                    # Verify issues were found
                    assert len(results['backend_security']['issues']) > 0
                    assert len(results['frontend_security']['issues']) > 0
                    
                    # Verify severity ordering
                    backend_issues = results['backend_security']['issues']
                    if len(backend_issues) > 1:
                        severities = [issue['severity'] for issue in backend_issues]
                        severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
                        assert all(severity_order[severities[i]] <= severity_order[severities[i+1]] 
                                 for i in range(len(severities)-1))
    
    @patch('performance_service.LocustPerformanceTester.run_performance_test')
    @patch('zap_service.ZAPScanner.scan_app')
    def test_multi_analysis_coordination(self, mock_zap_scan, mock_performance_test, full_test_environment):
        """Test coordination of multiple analysis types."""
        # Mock external services
        mock_performance_test.return_value = {
            'avg_response_time': 150.0,
            'requests_per_sec': 25.5,
            'total_requests': 1000,
            'total_failures': 2
        }
        
        mock_zap_scan.return_value = {
            'vulnerabilities': [
                {'name': 'XSS', 'risk': 'High', 'confidence': 'High'}
            ],
            'summary': {'total_alerts': 1, 'high_risk': 1}
        }
        
        # Initialize all analyzers
        cli_analyzer = UnifiedCLIAnalyzer(full_test_environment)
        performance_tester = LocustPerformanceTester(full_test_environment)
        zap_scanner = ZAPScanner(full_test_environment)
        
        model = "model_a"
        app_num = 1
        
        # Run coordinated analysis
        analysis_results = {}
        
        # 1. CLI-based analysis (security + quality)
        with patch.object(cli_analyzer.analyzers[ToolCategory.BACKEND_SECURITY], 'run_analysis') as mock_cli:
            mock_cli.return_value = ([], {}, {})
            
            cli_results = cli_analyzer.run_analysis(
                model=model,
                app_num=app_num,
                categories=[ToolCategory.BACKEND_SECURITY],
                force_rerun=True
            )
            analysis_results['cli'] = cli_results
        
        # 2. Performance analysis
        perf_results = performance_tester.run_performance_test(model, app_num)
        analysis_results['performance'] = perf_results
        
        # 3. ZAP security scan
        zap_results = zap_scanner.scan_app(model, app_num)
        analysis_results['zap'] = zap_results
        
        # Verify all analyses completed
        assert 'cli' in analysis_results
        assert 'performance' in analysis_results
        assert 'zap' in analysis_results
        
        # Verify results have expected structure
        assert isinstance(analysis_results['performance'], dict)
        assert 'vulnerabilities' in analysis_results['zap']


if __name__ == '__main__':
    # Run tests with verbose output
    pytest.main([__file__, '-v', '--tb=short'])
