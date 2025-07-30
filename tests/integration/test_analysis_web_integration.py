"""
Integration Tests for Analysis Web Routes
=========================================

Tests for the web interface analysis functionality including:
- Analysis overview page
- Quick analysis execution
- Results display
- Batch analysis
- Export functionality
"""
import pytest
import json
from unittest.mock import Mock, patch
from flask import url_for

# Add src to path for imports
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestAnalysisWebRoutes:
    """Test analysis-related web routes and templates."""
    
    def test_analysis_overview_page(self, client):
        """Test the analysis overview page loads correctly."""
        response = client.get('/analysis/')
        
        assert response.status_code == 200
        assert b'Security Analysis Center' in response.data
        assert b'Quick Analysis' in response.data
        assert b'Analysis Queue' in response.data
    
    def test_analysis_overview_htmx(self, client):
        """Test analysis overview with HTMX requests."""
        headers = {'HX-Request': 'true'}
        response = client.get('/analysis/', headers=headers)
        
        assert response.status_code == 200
        # Should return partial content for HTMX
        assert b'Security Analysis Center' in response.data
    
    @patch('web_routes.UnifiedCLIAnalyzer')
    def test_quick_analysis_post(self, mock_analyzer_class, client):
        """Test starting a quick analysis via POST."""
        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer.run_analysis.return_value = {
            'backend_security': {
                'issues': [
                    {
                        'tool': 'bandit',
                        'severity': 'HIGH',
                        'filename': 'app.py',
                        'line_number': 10,
                        'issue_text': 'SQL injection vulnerability'
                    }
                ],
                'summary': {'total_issues': 1, 'high_severity': 1}
            }
        }
        mock_analyzer_class.return_value = mock_analyzer
        
        # Test POST request
        data = {
            'model_slug': 'test_model',
            'app_number': '1',
            'analysis_types': ['backend_security'],
            'analysis_depth': 'standard',
            'use_all_tools': 'false',
            'force_rerun': 'true'
        }
        
        response = client.post('/analysis/quick', data=data)
        
        assert response.status_code == 200
        # Should call the analyzer
        mock_analyzer.run_analysis.assert_called_once()
    
    def test_analysis_stats_api_endpoints(self, client):
        """Test analysis statistics API endpoints."""
        # Test total analyses
        response = client.get('/api/analysis/stats/total')
        assert response.status_code == 200
        
        # Test completed today
        response = client.get('/api/analysis/stats/today')
        assert response.status_code == 200
        
        # Test running analyses
        response = client.get('/api/analysis/stats/running')
        assert response.status_code == 200
        
        # Test critical issues
        response = client.get('/api/analysis/stats/critical')
        assert response.status_code == 200
    
    def test_analysis_queue_endpoint(self, client):
        """Test analysis queue API endpoint."""
        response = client.get('/api/analysis/queue')
        
        assert response.status_code == 200
        # Should return HTML for queue display
        assert b'analysis-queue' in response.data
    
    @patch('web_routes.load_json_results_for_template')
    def test_analysis_recent_results(self, mock_load_results, client):
        """Test recent analysis results endpoint."""
        # Mock recent results
        mock_load_results.return_value = [
            {
                'model': 'test_model',
                'app_num': 1,
                'analysis_type': 'backend_security',
                'timestamp': '2025-01-01T10:00:00',
                'summary': {'total_issues': 5, 'high_severity': 2}
            }
        ]
        
        response = client.get('/analysis/recent')
        assert response.status_code == 200
        
        # Test with filter
        response = client.get('/analysis/recent?filter=completed')
        assert response.status_code == 200
    
    def test_analysis_export_endpoints(self, client):
        """Test analysis export functionality."""
        # Test JSON export
        response = client.get('/analysis/export/test_model/1?format=json')
        assert response.status_code in [200, 404]  # May not have results
        
        # Test CSV export
        response = client.get('/analysis/export/test_model/1?format=csv')
        assert response.status_code in [200, 404]  # May not have results
    
    def test_analysis_tools_configuration(self, client):
        """Test analysis tools configuration endpoint."""
        # Test GET - load configuration form
        response = client.get('/analysis/tools/configure')
        assert response.status_code == 200
        
        # Test POST - save configuration
        data = {
            'backend_tools': ['bandit', 'safety'],
            'frontend_tools': ['eslint', 'npm_audit'],
            'bandit_severity': 'medium',
            'eslint_rules': 'security'
        }
        
        response = client.post('/analysis/tools/configure', data=data)
        assert response.status_code in [200, 302]  # Success or redirect
    
    @patch('web_routes.UnifiedCLIAnalyzer')
    def test_batch_analysis_start(self, mock_analyzer_class, client):
        """Test starting batch analysis."""
        # Mock analyzer
        mock_analyzer = Mock()
        mock_analyzer_class.return_value = mock_analyzer
        
        data = {
            'models': ['model_a', 'model_b'],
            'app_range_start': '1',
            'app_range_end': '3',
            'analysis_types': ['backend_security', 'frontend_security'],
            'parallel_limit': '2'
        }
        
        response = client.post('/analysis/batch/start', data=data)
        assert response.status_code == 200
    
    def test_analysis_control_endpoints(self, client):
        """Test analysis control endpoints (stop, pause, etc.)."""
        # Test stop analysis
        response = client.post('/analysis/stop/test_model/1')
        assert response.status_code in [200, 404]
        
        # Test pause all
        response = client.post('/analysis/pause-all')
        assert response.status_code == 200
        
        # Test clear queue
        response = client.post('/analysis/clear-queue')
        assert response.status_code == 200


class TestAnalysisTemplateRendering:
    """Test analysis template rendering and content."""
    
    def test_analysis_results_template_structure(self, client):
        """Test that analysis results template has correct structure."""
        # Create mock analysis results
        mock_results = {
            'summary': {
                'critical_count': 1,
                'high_count': 2,
                'medium_count': 3,
                'low_count': 1
            },
            'by_tool': {
                'bandit': {
                    'issues': [
                        {
                            'severity': 'HIGH',
                            'filename': 'app.py',
                            'line_number': 10,
                            'issue_text': 'SQL injection',
                            'rule_id': 'B608',
                            'fix_suggestion': 'Use parameterized queries'
                        }
                    ],
                    'output': 'Bandit scan completed'
                }
            },
            'duration_seconds': 45.2
        }
        
        # Test with mock results
        with client.application.test_request_context():
            from flask import render_template_string
            
            # Test that template can render with results
            template_content = """
            {% if results %}
                <div class="results">{{ results.summary.high_count }} high issues</div>
            {% endif %}
            """
            
            rendered = render_template_string(template_content, results=mock_results)
            assert '2 high issues' in rendered
    
    def test_severity_badge_rendering(self, client):
        """Test that severity badges render correctly."""
        with client.application.test_request_context():
            from flask import render_template_string
            
            template_content = """
            {% set severity = 'HIGH' %}
            {% if severity == 'HIGH' %}
                <span class="badge badge-danger">{{ severity }}</span>
            {% elif severity == 'MEDIUM' %}
                <span class="badge badge-warning">{{ severity }}</span>
            {% else %}
                <span class="badge badge-info">{{ severity }}</span>
            {% endif %}
            """
            
            rendered = render_template_string(template_content)
            assert 'badge-danger' in rendered
            assert 'HIGH' in rendered
    
    def test_analysis_queue_template(self, client):
        """Test analysis queue template rendering."""
        mock_queue_items = [
            {
                'id': 'analysis_1',
                'model': 'test_model',
                'app_num': 1,
                'analysis_type': 'backend_security',
                'status': 'running',
                'progress': 75,
                'elapsed_time': '45s',
                'current_tool': 'bandit'
            },
            {
                'id': 'analysis_2',
                'model': 'test_model',
                'app_num': 2,
                'analysis_type': 'frontend_security',
                'status': 'queued',
                'eta': '2m'
            }
        ]
        
        with client.application.test_request_context():
            from flask import render_template_string
            
            template_content = """
            {% for item in queue_items %}
                <div class="queue-item">
                    {{ item.model }} App {{ item.app_num }} - {{ item.status }}
                    {% if item.progress %}({{ item.progress }}%){% endif %}
                </div>
            {% endfor %}
            """
            
            rendered = render_template_string(template_content, queue_items=mock_queue_items)
            assert 'test_model App 1 - running (75%)' in rendered
            assert 'test_model App 2 - queued' in rendered


class TestAnalysisFormHandling:
    """Test analysis form handling and validation."""
    
    def test_quick_analysis_form_validation(self, client):
        """Test quick analysis form validation."""
        # Test missing required fields
        response = client.post('/analysis/quick', data={})
        assert response.status_code in [400, 422]  # Should validate and reject
        
        # Test invalid model
        data = {
            'model_slug': 'invalid_model',
            'app_number': '1',
            'analysis_types': ['backend_security']
        }
        response = client.post('/analysis/quick', data=data)
        # Should handle gracefully
        assert response.status_code in [200, 400, 404]
        
        # Test invalid app number
        data = {
            'model_slug': 'test_model',
            'app_number': '999',
            'analysis_types': ['backend_security']
        }
        response = client.post('/analysis/quick', data=data)
        assert response.status_code in [200, 400, 404]
    
    def test_analysis_configuration_form(self, client):
        """Test analysis configuration form handling."""
        # Test valid configuration
        data = {
            'backend_tools': ['bandit', 'safety'],
            'frontend_tools': ['eslint'],
            'analysis_depth': 'standard',
            'severity_filter': 'medium_and_above',
            'timeout': '300'
        }
        
        response = client.post('/analysis/tools/configure', data=data)
        assert response.status_code in [200, 302]
        
        # Test invalid timeout
        data['timeout'] = 'invalid'
        response = client.post('/analysis/tools/configure', data=data)
        # Should handle invalid input gracefully
        assert response.status_code in [200, 400]
    
    def test_batch_analysis_form_validation(self, client):
        """Test batch analysis form validation."""
        # Test valid batch configuration
        data = {
            'models': ['model_a', 'model_b'],
            'app_range_start': '1',
            'app_range_end': '5',
            'analysis_types': ['backend_security'],
            'parallel_limit': '3'
        }
        
        response = client.post('/analysis/batch/start', data=data)
        assert response.status_code == 200
        
        # Test invalid range
        data['app_range_start'] = '10'
        data['app_range_end'] = '5'  # End before start
        response = client.post('/analysis/batch/start', data=data)
        # Should validate and handle error
        assert response.status_code in [200, 400]


class TestAnalysisErrorHandling:
    """Test error handling in analysis functionality."""
    
    @patch('web_routes.UnifiedCLIAnalyzer')
    def test_analyzer_not_available(self, mock_analyzer_class, client):
        """Test handling when analyzer is not available."""
        mock_analyzer_class.side_effect = ImportError("Analyzer not available")
        
        response = client.get('/analysis/')
        assert response.status_code == 200
        # Should handle gracefully and show appropriate message
        
    @patch('web_routes.UnifiedCLIAnalyzer')
    def test_analysis_execution_error(self, mock_analyzer_class, client):
        """Test handling of analysis execution errors."""
        mock_analyzer = Mock()
        mock_analyzer.run_analysis.side_effect = Exception("Analysis failed")
        mock_analyzer_class.return_value = mock_analyzer
        
        data = {
            'model_slug': 'test_model',
            'app_number': '1',
            'analysis_types': ['backend_security']
        }
        
        response = client.post('/analysis/quick', data=data)
        # Should handle error gracefully
        assert response.status_code in [200, 500]
    
    def test_missing_analysis_results(self, client):
        """Test handling when analysis results are missing."""
        # Try to get results for non-existent analysis
        response = client.get('/analysis/results/nonexistent_model/999')
        assert response.status_code in [200, 404]
        
        # Try to export non-existent results
        response = client.get('/analysis/export/nonexistent_model/999?format=json')
        assert response.status_code in [200, 404]
    
    def test_invalid_analysis_parameters(self, client):
        """Test handling of invalid analysis parameters."""
        # Invalid model slug
        response = client.get('/analysis/details/invalid-type/invalid-model/abc')
        assert response.status_code in [200, 400, 404]
        
        # Invalid app number
        response = client.get('/analysis/details/backend_security/test_model/not_a_number')
        assert response.status_code == 404  # Should be caught by route


if __name__ == '__main__':
    # Run tests with pytest if available
    try:
        pytest.main([__file__, '-v'])
    except ImportError:
        import unittest
        unittest.main()
