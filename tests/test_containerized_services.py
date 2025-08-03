"""
Tests for containerized testing services integration.
"""

import pytest
import requests
from unittest.mock import Mock, patch
from src.core_services import TestingServiceClient


class TestContainerizedServices:
    """Test containerized testing services integration."""
    
    def test_testing_service_client_init(self):
        """Test TestingServiceClient initialization."""
        client = TestingServiceClient()
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30
        
    def test_testing_service_client_with_custom_config(self):
        """Test TestingServiceClient with custom configuration."""
        client = TestingServiceClient(
            base_url="http://custom:9000",
            timeout=60
        )
        assert client.base_url == "http://custom:9000"
        assert client.timeout == 60
        
    @patch('requests.post')
    def test_submit_security_test_success(self, mock_post):
        """Test successful security test submission."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'test_id': 'test-123',
            'status': 'submitted',
            'estimated_duration': 60
        }
        mock_post.return_value = mock_response
        
        client = TestingServiceClient()
        result = client.submit_security_test(
            model="test_model",
            app_num=1,
            test_type="security_backend"
        )
        
        assert result['test_id'] == 'test-123'
        assert result['status'] == 'submitted'
        
    @patch('requests.post')
    def test_submit_security_test_failure(self, mock_post):
        """Test security test submission failure."""
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        client = TestingServiceClient()
        result = client.submit_security_test(
            model="test_model",
            app_num=1,
            test_type="security_backend"
        )
        
        assert result is None
        
    @patch('requests.get')
    def test_get_test_status_success(self, mock_get):
        """Test successful test status retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'test_id': 'test-123',
            'status': 'completed',
            'progress': 100
        }
        mock_get.return_value = mock_response
        
        client = TestingServiceClient()
        result = client.get_test_status('test-123')
        
        assert result['status'] == 'completed'
        assert result['progress'] == 100
        
    @patch('requests.get')
    def test_get_test_result_success(self, mock_get):
        """Test successful test result retrieval."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'test_id': 'test-123',
            'status': 'completed',
            'result': {
                'total_issues': 5,
                'categories': ['backend_security'],
                'issues': []
            }
        }
        mock_get.return_value = mock_response
        
        client = TestingServiceClient()
        result = client.get_test_result('test-123')
        
        assert result['status'] == 'completed'
        assert result['result']['total_issues'] == 5
        
    def test_health_check_with_mock_services(self):
        """Test health check functionality."""
        client = TestingServiceClient()
        
        # This will fail in test environment, which is expected
        health_status = client.health_check()
        
        # Should return False when services are not running
        assert health_status is False
        
    @patch('src.core_services.TestingServiceClient')
    def test_scan_manager_containerized_integration(self, mock_client_class):
        """Test ScanManager integration with containerized services."""
        from src.core_services import ScanManager
        
        # Mock the client
        mock_client = Mock()
        mock_client.submit_security_test.return_value = {
            'test_id': 'test-123',
            'status': 'submitted'
        }
        mock_client_class.return_value = mock_client
        
        # Test ScanManager with mocked client
        scan_manager = ScanManager()
        result = scan_manager.run_security_analysis(
            model="test_model",
            app_num=1,
            enabled_tools={
                'bandit': True,
                'safety': True,
                'semgrep': False
            }
        )
        
        # Should attempt containerized analysis first
        assert mock_client.submit_security_test.called


class TestServiceFallbacks:
    """Test service fallback mechanisms."""
    
    def test_fallback_to_mock_when_services_unavailable(self):
        """Test fallback to mock results when containerized services are unavailable."""
        from src.core_services import ScanManager
        
        scan_manager = ScanManager()
        
        # This should fallback to mock since services aren't running
        result = scan_manager.run_security_analysis(
            model="test_model",
            app_num=1,
            enabled_tools={'bandit': True}
        )
        
        assert result['success'] is True
        assert 'data' in result
        assert result['data']['mode'] in ['mock', 'legacy']
        
    def test_mock_security_analysis(self):
        """Test mock security analysis response."""
        from src.core_services import ScanManager
        
        scan_manager = ScanManager()
        result = scan_manager._mock_security_analysis(
            model="test_model",
            app_num=1,
            enabled_tools={'bandit': True}
        )
        
        assert result['success'] is True
        assert result['data']['mode'] == 'mock'
        assert isinstance(result['data']['issues'], list)
        assert isinstance(result['data']['total_issues'], int)


if __name__ == '__main__':
    pytest.main([__file__])
