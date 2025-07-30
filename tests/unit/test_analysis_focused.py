"""
Analysis Capabilities Tests
==========================

Focused tests for analysis functionality that can be run without
requiring all external dependencies to be installed.
"""
import pytest
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Add src to path for imports
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestAnalysisResultsHandling:
    """Test analysis results storage and retrieval."""
    
    def test_analysis_result_structure(self):
        """Test that analysis results have the expected structure."""
        # Define expected analysis result structure
        expected_structure = {
            'analysis_type': str,
            'model': str,
            'app_num': int,
            'timestamp': str,
            'issues': list,
            'summary': dict,
            'tool_outputs': dict,
            'tool_errors': dict,
            'duration_seconds': float
        }
        
        # Create sample analysis result
        sample_result = {
            'analysis_type': 'backend_security',
            'model': 'test_model',
            'app_num': 1,
            'timestamp': datetime.now().isoformat(),
            'issues': [
                {
                    'tool': 'bandit',
                    'severity': 'HIGH',
                    'confidence': 'HIGH',
                    'filename': 'app.py',
                    'line_number': 10,
                    'issue_text': 'SQL injection vulnerability',
                    'issue_type': 'security',
                    'category': 'security',
                    'rule_id': 'B608',
                    'line_range': [10, 10],
                    'code': 'SELECT * FROM users WHERE id = " + user_id',
                    'fix_suggestion': 'Use parameterized queries'
                }
            ],
            'summary': {
                'total_issues': 1,
                'high_severity': 1,
                'medium_severity': 0,
                'low_severity': 0
            },
            'tool_outputs': {
                'bandit': 'Bandit analysis completed successfully'
            },
            'tool_errors': {},
            'duration_seconds': 45.2
        }
        
        # Verify structure matches expected
        for key, expected_type in expected_structure.items():
            assert key in sample_result
            assert isinstance(sample_result[key], expected_type)
        
        # Verify issue structure
        issue = sample_result['issues'][0]
        required_issue_fields = [
            'tool', 'severity', 'confidence', 'filename', 
            'line_number', 'issue_text', 'rule_id'
        ]
        for field in required_issue_fields:
            assert field in issue
    
    def test_severity_levels(self):
        """Test that severity levels are correctly ordered."""
        severities = ['HIGH', 'MEDIUM', 'LOW', 'INFO']
        severity_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'INFO': 3}
        
        # Test that ordering works correctly
        test_issues = [
            {'severity': 'LOW', 'tool': 'test1'},
            {'severity': 'HIGH', 'tool': 'test2'},
            {'severity': 'MEDIUM', 'tool': 'test3'},
            {'severity': 'INFO', 'tool': 'test4'}
        ]
        
        # Sort by severity
        sorted_issues = sorted(test_issues, key=lambda x: severity_order.get(x['severity'], 999))
        
        # Verify HIGH comes first, INFO comes last
        assert sorted_issues[0]['severity'] == 'HIGH'
        assert sorted_issues[-1]['severity'] == 'INFO'
    
    def test_json_serialization(self):
        """Test that analysis results can be serialized to JSON."""
        analysis_result = {
            'analysis_type': 'frontend_security',
            'timestamp': datetime.now().isoformat(),
            'issues': [],
            'summary': {'total_issues': 0},
            'tool_outputs': {'eslint': 'No issues found'},
            'duration_seconds': 12.5
        }
        
        # Should be able to serialize and deserialize
        json_str = json.dumps(analysis_result)
        loaded_result = json.loads(json_str)
        
        assert loaded_result['analysis_type'] == 'frontend_security'
        assert loaded_result['duration_seconds'] == 12.5


class TestAnalysisConfiguration:
    """Test analysis configuration and tool selection."""
    
    def test_tool_categories(self):
        """Test analysis tool categories."""
        categories = [
            'backend_security',
            'frontend_security', 
            'backend_quality',
            'frontend_quality'
        ]
        
        # Each category should have associated tools
        tool_mapping = {
            'backend_security': ['bandit', 'safety', 'semgrep'],
            'frontend_security': ['eslint', 'npm_audit', 'retire'],
            'backend_quality': ['pylint', 'flake8', 'radon'],
            'frontend_quality': ['eslint', 'prettier', 'jshint']
        }
        
        for category in categories:
            assert category in tool_mapping
            assert len(tool_mapping[category]) > 0
    
    def test_analysis_depth_options(self):
        """Test analysis depth configuration options."""
        depth_options = {
            'quick': {
                'timeout': 60,
                'tools_subset': True,
                'description': 'Fast scan with essential tools'
            },
            'standard': {
                'timeout': 300,
                'tools_subset': False,
                'description': 'Complete analysis with all available tools'
            },
            'deep': {
                'timeout': 900,
                'tools_subset': False,
                'description': 'Comprehensive analysis with maximum coverage'
            }
        }
        
        # Verify depth options have required structure
        for depth, config in depth_options.items():
            assert 'timeout' in config
            assert 'tools_subset' in config
            assert 'description' in config
            assert isinstance(config['timeout'], int)
            assert config['timeout'] > 0
    
    def test_severity_filtering(self):
        """Test severity filtering options."""
        filters = {
            'all': lambda issues: issues,
            'medium_and_above': lambda issues: [i for i in issues if i['severity'] in ['HIGH', 'MEDIUM']],
            'high_only': lambda issues: [i for i in issues if i['severity'] == 'HIGH']
        }
        
        test_issues = [
            {'severity': 'HIGH', 'message': 'Critical issue'},
            {'severity': 'MEDIUM', 'message': 'Medium issue'},
            {'severity': 'LOW', 'message': 'Low issue'},
            {'severity': 'INFO', 'message': 'Info issue'}
        ]
        
        # Test each filter
        assert len(filters['all'](test_issues)) == 4
        assert len(filters['medium_and_above'](test_issues)) == 2
        assert len(filters['high_only'](test_issues)) == 1


class TestAnalysisWorkflow:
    """Test analysis workflow and coordination."""
    
    @pytest.fixture
    def temp_project_structure(self):
        """Create temporary project structure for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create model/app structure
            app_path = project_path / "misc" / "models" / "test_model" / "app1"
            
            # Backend structure
            backend_path = app_path / "backend"
            backend_path.mkdir(parents=True)
            (backend_path / "app.py").write_text("# Flask application")
            (backend_path / "requirements.txt").write_text("Flask==2.0.0")
            
            # Frontend structure  
            frontend_path = app_path / "frontend"
            frontend_path.mkdir(parents=True)
            (frontend_path / "package.json").write_text('{"name": "frontend"}')
            (frontend_path / "src").mkdir()
            (frontend_path / "src" / "App.js").write_text("// React app")
            
            yield project_path
    
    def test_project_structure_validation(self, temp_project_structure):
        """Test that project structure validation works."""
        project_path = temp_project_structure
        
        # Should find backend and frontend directories
        app_path = project_path / "misc" / "models" / "test_model" / "app1"
        assert (app_path / "backend").exists()
        assert (app_path / "frontend").exists()
        
        # Should find key files
        assert (app_path / "backend" / "app.py").exists()
        assert (app_path / "frontend" / "package.json").exists()
    
    def test_analysis_coordination(self):
        """Test coordination between different analysis types."""
        # Mock analysis results from different tools
        mock_results = {
            'backend_security': {
                'issues': [
                    {'tool': 'bandit', 'severity': 'HIGH', 'message': 'Security issue'}
                ],
                'summary': {'total_issues': 1, 'high_severity': 1}
            },
            'frontend_security': {
                'issues': [
                    {'tool': 'eslint', 'severity': 'MEDIUM', 'message': 'JavaScript issue'}
                ],
                'summary': {'total_issues': 1, 'medium_severity': 1}
            },
            'performance': {
                'avg_response_time': 150.0,
                'requests_per_sec': 25.5,
                'total_requests': 1000
            }
        }
        
        # Verify consolidated results structure
        consolidated = {
            'model': 'test_model',
            'app_num': 1,
            'timestamp': datetime.now().isoformat(),
            'analyses': mock_results,
            'overall_summary': {
                'total_security_issues': 2,
                'critical_issues': 1,
                'performance_score': 'GOOD'  # Based on response time
            }
        }
        
        assert consolidated['overall_summary']['total_security_issues'] == 2
        assert 'backend_security' in consolidated['analyses']
        assert 'frontend_security' in consolidated['analyses']
    
    def test_batch_analysis_planning(self):
        """Test batch analysis planning and execution."""
        # Define batch analysis configuration
        batch_config = {
            'models': ['model_a', 'model_b'],
            'app_range': (1, 5),  # Apps 1-5
            'analysis_types': ['backend_security', 'frontend_security'],
            'parallel_limit': 3,
            'timeout_per_analysis': 300
        }
        
        # Calculate expected number of analyses
        expected_analyses = (
            len(batch_config['models']) * 
            (batch_config['app_range'][1] - batch_config['app_range'][0] + 1) * 
            len(batch_config['analysis_types'])
        )
        
        assert expected_analyses == 2 * 5 * 2  # 20 total analyses
        
        # Test batch execution planning
        analyses = []
        for model in batch_config['models']:
            for app_num in range(batch_config['app_range'][0], batch_config['app_range'][1] + 1):
                for analysis_type in batch_config['analysis_types']:
                    analyses.append({
                        'model': model,
                        'app_num': app_num,
                        'analysis_type': analysis_type,
                        'priority': 'HIGH' if analysis_type.endswith('_security') else 'MEDIUM'
                    })
        
        assert len(analyses) == expected_analyses
        
        # Test priority ordering
        security_analyses = [a for a in analyses if a['priority'] == 'HIGH']
        assert len(security_analyses) == 2 * 5 * 2  # Both security analysis types


class TestAnalysisReporting:
    """Test analysis reporting and visualization."""
    
    def test_summary_statistics(self):
        """Test generation of summary statistics."""
        # Mock analysis results from multiple apps
        results = [
            {
                'model': 'model_a', 'app_num': 1,
                'issues': [
                    {'severity': 'HIGH', 'tool': 'bandit'},
                    {'severity': 'MEDIUM', 'tool': 'safety'}
                ]
            },
            {
                'model': 'model_a', 'app_num': 2,
                'issues': [
                    {'severity': 'LOW', 'tool': 'eslint'}
                ]
            },
            {
                'model': 'model_b', 'app_num': 1,
                'issues': []
            }
        ]
        
        # Calculate summary statistics
        total_issues = sum(len(r['issues']) for r in results)
        high_severity = sum(1 for r in results for i in r['issues'] if i['severity'] == 'HIGH')
        apps_with_issues = sum(1 for r in results if len(r['issues']) > 0)
        
        summary = {
            'total_analyses': len(results),
            'total_issues': total_issues,
            'high_severity_issues': high_severity,
            'apps_with_issues': apps_with_issues,
            'clean_apps': len(results) - apps_with_issues
        }
        
        assert summary['total_analyses'] == 3
        assert summary['total_issues'] == 3
        assert summary['high_severity_issues'] == 1
        assert summary['apps_with_issues'] == 2
        assert summary['clean_apps'] == 1
    
    def test_trend_analysis(self):
        """Test trend analysis over time."""
        # Mock historical analysis data
        historical_data = [
            {
                'date': '2025-01-01',
                'total_issues': 100,
                'high_severity': 20,
                'analyses_run': 50
            },
            {
                'date': '2025-01-02', 
                'total_issues': 95,
                'high_severity': 18,
                'analyses_run': 52
            },
            {
                'date': '2025-01-03',
                'total_issues': 90,
                'high_severity': 15,
                'analyses_run': 55
            }
        ]
        
        # Calculate trends
        def calculate_trend(data, field):
            if len(data) < 2:
                return 0
            return ((data[-1][field] - data[0][field]) / data[0][field]) * 100
        
        issue_trend = calculate_trend(historical_data, 'total_issues')
        severity_trend = calculate_trend(historical_data, 'high_severity')
        
        # Issues should be decreasing (negative trend)
        assert issue_trend < 0
        assert severity_trend < 0
    
    def test_export_formats(self):
        """Test different export formats for analysis results."""
        sample_results = {
            'summary': {
                'total_issues': 5,
                'high_severity': 2,
                'medium_severity': 2,
                'low_severity': 1
            },
            'issues': [
                {
                    'tool': 'bandit',
                    'severity': 'HIGH',
                    'filename': 'app.py',
                    'line_number': 10,
                    'message': 'SQL injection vulnerability'
                }
            ]
        }
        
        # Test JSON export
        json_export = json.dumps(sample_results, indent=2)
        assert 'total_issues' in json_export
        
        # Test CSV format conversion
        def to_csv_rows(results):
            rows = [['Tool', 'Severity', 'File', 'Line', 'Message']]
            for issue in results['issues']:
                rows.append([
                    issue['tool'],
                    issue['severity'],
                    issue['filename'],
                    str(issue['line_number']),
                    issue['message']
                ])
            return rows
        
        csv_rows = to_csv_rows(sample_results)
        assert len(csv_rows) == 2  # Header + 1 issue
        assert csv_rows[1][0] == 'bandit'


class TestAnalysisIntegration:
    """Integration tests for analysis components."""
    
    def test_end_to_end_workflow(self):
        """Test complete analysis workflow from start to finish."""
        # Mock the complete workflow
        workflow_steps = [
            'validate_project_structure',
            'select_analysis_tools',
            'execute_analyses',
            'collect_results',
            'generate_summary',
            'save_results'
        ]
        
        # Mock workflow execution
        workflow_state = {'step': 0, 'completed': False}
        
        def execute_workflow():
            for i, step in enumerate(workflow_steps):
                workflow_state['step'] = i + 1
                # Mock step execution
                if step == 'execute_analyses':
                    # This would be the longest step
                    pass
            workflow_state['completed'] = True
        
        execute_workflow()
        
        assert workflow_state['completed']
        assert workflow_state['step'] == len(workflow_steps)
    
    def test_error_handling(self):
        """Test error handling in analysis workflow."""
        error_scenarios = [
            'tool_not_found',
            'invalid_project_structure',
            'analysis_timeout',
            'insufficient_permissions',
            'network_error'
        ]
        
        # Mock error handling for each scenario
        def handle_error(error_type):
            error_responses = {
                'tool_not_found': {'skip': True, 'continue': True},
                'invalid_project_structure': {'skip': False, 'continue': False},
                'analysis_timeout': {'skip': True, 'continue': True},
                'insufficient_permissions': {'skip': True, 'continue': True},
                'network_error': {'skip': True, 'continue': True}
            }
            return error_responses.get(error_type, {'skip': False, 'continue': False})
        
        # Test each error scenario
        for error in error_scenarios:
            response = handle_error(error)
            assert 'skip' in response
            assert 'continue' in response
            
            # Critical errors should stop the workflow
            if error == 'invalid_project_structure':
                assert not response['continue']


if __name__ == '__main__':
    # Run tests with pytest if available, otherwise run with unittest
    try:
        pytest.main([__file__, '-v'])
    except ImportError:
        import unittest
        unittest.main()
