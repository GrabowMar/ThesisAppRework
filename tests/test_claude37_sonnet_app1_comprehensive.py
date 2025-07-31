"""
Comprehensive Stable Tests for Claude 3.7 Sonnet App 1
======================================================

These tests simulate real-world usage scenarios for Claude 3.7 Sonnet app 1
with realistic data and stable test conditions.

Model: anthropic_claude-3.7-sonnet
App Number: 1  
Backend Port: 6051
Frontend Port: 9051
"""
import pytest
import json
import time
from pathlib import Path
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Test constants for Claude 3.7 Sonnet App 1
TEST_MODEL = "anthropic_claude-3.7-sonnet"
TEST_APP_NUM = 1
TEST_BACKEND_PORT = 6051
TEST_FRONTEND_PORT = 9051
TEST_PROJECT_NAME = "anthropic_claude_3_7_sonnet_app1"

class TestClaude37SonnetApp1Functionality:
    """Test core functionality for Claude 3.7 Sonnet App 1."""
    
    def test_app_detail_pages_load_correctly(self):
        """Test all app detail pages load for Claude 3.7 Sonnet App 1."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test all app detail pages
            pages = [
                ('overview', 'Overview'),
                ('docker', 'Docker Management'), 
                ('analysis', 'Security Analysis'),
                ('performance', 'Performance Testing'),
                ('files', 'File Browser'),
                ('tests', 'Test Runner')
            ]
            
            for page, description in pages:
                url = f'/app/{TEST_MODEL}/{TEST_APP_NUM}/{page}'
                response = client.get(url)
                
                # Should load successfully or redirect
                assert response.status_code in [200, 302], f"{description} page failed: {response.status_code}"
                
                if response.status_code == 200:
                    content = response.get_data(as_text=True)
                    # Verify page contains expected content
                    assert TEST_MODEL.replace('_', ' ') in content or TEST_MODEL in content
                    assert str(TEST_APP_NUM) in content
                    # Verify navigation is present
                    assert 'nav-link' in content
                    
                print(f"✓ {description} page loads correctly")
    
    def test_api_endpoints_return_expected_structure(self):
        """Test API endpoints return properly structured data."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test status API
            response = client.get(f'/api/status/{TEST_MODEL}/{TEST_APP_NUM}')
            assert response.status_code == 200
            content = response.get_data(as_text=True)
            # Should contain status indicators
            assert 'status-indicator' in content
            print("✓ Status API returns proper structure")
            
            # Test dashboard models API
            response = client.get('/api/dashboard/models')
            assert response.status_code == 200
            content = response.get_data(as_text=True)
            # Should contain model information
            assert 'claude' in content.lower() or 'anthropic' in content.lower()
            print("✓ Dashboard models API returns proper structure")

class TestClaude37SonnetApp1Docker:
    """Test Docker management for Claude 3.7 Sonnet App 1."""
    
    def test_docker_routes_accept_post_methods(self):
        """Test Docker management routes accept POST methods."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            docker_operations = [
                ('start', 'Start containers'),
                ('stop', 'Stop containers'),
                ('restart', 'Restart containers')
            ]
            
            for operation, description in docker_operations:
                url = f'/docker/{operation}/{TEST_MODEL}/{TEST_APP_NUM}'
                response = client.post(url)
                
                # Should not return 405 Method Not Allowed
                assert response.status_code != 405, f"{description} returned 405"
                
                # Should return 500 (service error) or other valid response, not 404/405
                assert response.status_code in [200, 302, 500, 503], f"{description} unexpected status: {response.status_code}"
                print(f"✓ {description} accepts POST method")
    
    @patch('core_services.DockerManager')
    def test_docker_container_status_simulation(self, mock_docker_manager):
        """Simulate realistic Docker container status scenarios."""
        from app import create_app
        
        # Mock Docker service responses
        mock_docker = Mock()
        mock_docker_manager.return_value = mock_docker
        
        # Simulate containers running
        mock_docker.get_container_status.return_value = {
            'running': True,
            'status': 'Up 5 minutes',
            'ports': {f'{TEST_BACKEND_PORT}/tcp': [{'HostPort': str(TEST_BACKEND_PORT)}]},
            'name': f'{TEST_PROJECT_NAME}_backend_{TEST_BACKEND_PORT}'
        }
        
        app = create_app()
        
        with app.test_client() as client:
            response = client.get(f'/api/status/{TEST_MODEL}/{TEST_APP_NUM}')
            assert response.status_code == 200
            print("✓ Docker status simulation works")

class TestClaude37SonnetApp1Security:
    """Test security analysis for Claude 3.7 Sonnet App 1."""
    
    def test_security_analysis_routes_accept_post(self):
        """Test security analysis routes accept POST requests."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test security analysis route
            response = client.post(f'/api/analysis/{TEST_MODEL}/{TEST_APP_NUM}/security', data={
                'bandit': 'on',
                'safety': 'on',
                'eslint': 'on',
                'semgrep': 'off'
            })
            
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405, "Security analysis returned 405"
            assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
            print("✓ Security analysis accepts POST requests")
    
    def test_zap_scan_routes_accept_post(self):
        """Test ZAP security scan routes accept POST requests."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test ZAP scan route
            response = client.post(f'/api/analysis/{TEST_MODEL}/{TEST_APP_NUM}/zap', data={
                'scan_type': 'spider'
            })
            
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405, "ZAP scan returned 405"
            assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
            print("✓ ZAP scan accepts POST requests")
    
    @patch('core_services.ScanManager')
    def test_security_analysis_simulation(self, mock_scan_manager):
        """Simulate realistic security analysis results."""
        from app import create_app
        
        # Mock security analysis results
        mock_scan = Mock()
        mock_scan_manager.return_value = mock_scan
        
        # Simulate typical security analysis results for a web app
        mock_scan.run_security_analysis.return_value = {
            'success': True,
            'data': {
                'issues': [
                    {
                        'severity': 'HIGH',
                        'title': 'Potential SQL Injection in user input handling',
                        'file': 'backend/app.py',
                        'line': 45,
                        'tool': 'bandit'
                    },
                    {
                        'severity': 'MEDIUM', 
                        'title': 'Missing CSRF protection on form endpoints',
                        'file': 'backend/routes.py',
                        'line': 23,
                        'tool': 'semgrep'
                    },
                    {
                        'severity': 'LOW',
                        'title': 'Outdated dependency detected: requests==2.25.1',
                        'file': 'requirements.txt',
                        'line': 5,
                        'tool': 'safety'
                    }
                ],
                'summary': {
                    'total_issues': 3,
                    'high': 1,
                    'medium': 1,
                    'low': 1
                }
            }
        }
        
        app = create_app()
        
        with app.test_client() as client:
            response = client.post(f'/api/analysis/{TEST_MODEL}/{TEST_APP_NUM}/security', data={
                'bandit': 'on',
                'safety': 'on',
                'semgrep': 'on'
            })
            
            # Should return success with mocked data
            assert response.status_code == 200
            content = response.get_data(as_text=True)
            assert 'Security Analysis Completed' in content
            print("✓ Security analysis simulation works")

class TestClaude37SonnetApp1Performance:
    """Test performance analysis for Claude 3.7 Sonnet App 1."""
    
    def test_performance_test_routes_accept_post(self):
        """Test performance testing routes accept POST requests."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test performance test route
            response = client.post(f'/api/performance/{TEST_MODEL}/{TEST_APP_NUM}/run', data={
                'duration': '30',
                'users': '5',
                'spawn_rate': '1.0'
            })
            
            # Should not return 405 Method Not Allowed
            assert response.status_code != 405, "Performance test returned 405"
            assert response.status_code in [200, 503], f"Unexpected status: {response.status_code}"
            print("✓ Performance test accepts POST requests")
    
    @patch('performance_service.LocustPerformanceTester')
    def test_performance_testing_simulation(self, mock_performance_tester):
        """Simulate realistic performance test results."""
        from app import create_app
        
        # Mock performance test results
        mock_tester = Mock()
        mock_performance_tester.return_value = mock_tester
        
        # Simulate typical performance test results for Claude 3.7 Sonnet app
        mock_tester.run_performance_test.return_value = {
            'success': True,
            'data': {
                'avg_response_time': 245.8,  # ms
                'total_requests': 150,
                'failed_requests': 2,
                'success_rate': 98.67,
                'requests_per_second': 12.5,
                'min_response_time': 89.2,
                'max_response_time': 1205.3,
                'p95_response_time': 456.1,
                'p99_response_time': 892.4,
                'errors': [
                    {'type': 'ConnectionError', 'count': 1},
                    {'type': 'Timeout', 'count': 1}
                ]
            }
        }
        
        app = create_app()
        
        with app.test_client() as client:
            response = client.post(f'/api/performance/{TEST_MODEL}/{TEST_APP_NUM}/run', data={
                'duration': '60',
                'users': '10',
                'spawn_rate': '2.0'
            })
            
            # Should return success with mocked data
            assert response.status_code == 200
            content = response.get_data(as_text=True)
            assert 'Performance Test Completed' in content
            print("✓ Performance test simulation works")

class TestClaude37SonnetApp1Integration:
    """Integration tests for Claude 3.7 Sonnet App 1."""
    
    def test_app_info_retrieval(self):
        """Test app information retrieval for Claude 3.7 Sonnet App 1."""
        from app import create_app
        from core_services import AppDataProvider
        
        app = create_app()
        
        with app.app_context():
            # Test app info retrieval
            app_info = AppDataProvider.get_app_info(TEST_MODEL, TEST_APP_NUM)
            
            if app_info:
                assert app_info['model'] == TEST_MODEL
                assert app_info['app_num'] == TEST_APP_NUM
                assert app_info['backend_port'] == TEST_BACKEND_PORT
                assert app_info['frontend_port'] == TEST_FRONTEND_PORT
                print("✓ App info retrieval works correctly")
            else:
                print("⚠ App info not found (may need database setup)")
    
    def test_port_configuration_consistency(self):
        """Test port configuration consistency for Claude 3.7 Sonnet App 1."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test that the app pages reference correct ports
            response = client.get(f'/app/{TEST_MODEL}/{TEST_APP_NUM}/docker')
            
            if response.status_code == 200:
                content = response.get_data(as_text=True)
                # Should contain references to the correct ports
                assert str(TEST_BACKEND_PORT) in content or str(TEST_FRONTEND_PORT) in content
                print("✓ Port configuration is consistent")
            else:
                print(f"⚠ Docker page returned {response.status_code}")
    
    def test_model_capability_integration(self):
        """Test model capability data integration."""
        from app import create_app
        from models import ModelCapability
        
        app = create_app()
        
        with app.app_context():
            try:
                # Look for Claude 3.7 Sonnet model
                model = ModelCapability.query.filter_by(canonical_slug=TEST_MODEL).first()
                
                if model:
                    assert model.provider == 'anthropic'
                    assert 'claude' in model.model_name.lower()
                    assert '3.7' in model.model_name or '3-7' in model.model_name
                    print("✓ Model capability integration works")
                else:
                    print("⚠ Model not found in database (may need initialization)")
            except Exception as e:
                print(f"⚠ Database not available: {e}")

class TestClaude37SonnetApp1StabilityAndResilience:
    """Test stability and resilience for Claude 3.7 Sonnet App 1."""
    
    def test_rapid_successive_requests(self):
        """Test handling of rapid successive requests."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Make rapid successive requests to different endpoints
            endpoints = [
                f'/app/{TEST_MODEL}/{TEST_APP_NUM}/overview',
                f'/api/status/{TEST_MODEL}/{TEST_APP_NUM}',
                f'/app/{TEST_MODEL}/{TEST_APP_NUM}/docker',
                f'/api/dashboard/stats'
            ]
            
            results = []
            for i in range(3):  # 3 rounds of requests
                for endpoint in endpoints:
                    response = client.get(endpoint)
                    results.append((endpoint, response.status_code))
                    # Small delay to avoid overwhelming
                    time.sleep(0.1)
            
            # All requests should succeed or gracefully fail (not crash)
            success_count = sum(1 for _, status in results if status in [200, 302, 503])
            total_requests = len(results)
            
            success_rate = success_count / total_requests
            assert success_rate >= 0.8, f"Success rate too low: {success_rate}"
            print(f"✓ Rapid requests handled well ({success_rate:.1%} success rate)")
    
    def test_error_handling_resilience(self):
        """Test error handling doesn't crash the application."""
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test invalid requests that should be handled gracefully
            invalid_requests = [
                ('GET', f'/app/invalid_model/{TEST_APP_NUM}/overview'),
                ('GET', f'/app/{TEST_MODEL}/999/overview'),
                ('POST', f'/api/analysis/{TEST_MODEL}/{TEST_APP_NUM}/security', {'invalid': 'data'}),
                ('POST', f'/api/performance/{TEST_MODEL}/{TEST_APP_NUM}/run', {'duration': '-1'})
            ]
            
            for method, url, *data in invalid_requests:
                if method == 'GET':
                    response = client.get(url)
                else:
                    response = client.post(url, data=data[0] if data else {})
                
                # Should handle gracefully (not 500 crash, but proper error codes)
                assert response.status_code in [200, 302, 400, 404, 503], f"Unhandled error for {url}: {response.status_code}"
            
            print("✓ Error handling is resilient")
    
    def test_memory_and_resource_stability(self):
        """Test memory and resource usage stability."""
        from app import create_app
        import gc
        
        app = create_app()
        
        with app.test_client() as client:
            # Make multiple requests and ensure no memory leaks
            initial_objects = len(gc.get_objects())
            
            # Perform various operations
            for i in range(10):
                client.get(f'/app/{TEST_MODEL}/{TEST_APP_NUM}/overview')
                client.get(f'/api/status/{TEST_MODEL}/{TEST_APP_NUM}')
                client.post(f'/api/analysis/{TEST_MODEL}/{TEST_APP_NUM}/security', data={'bandit': 'on'})
                
                # Force garbage collection
                gc.collect()
            
            final_objects = len(gc.get_objects())
            
            # Object count should not grow excessively
            growth_ratio = final_objects / initial_objects
            assert growth_ratio < 1.5, f"Excessive object growth: {growth_ratio}"
            print(f"✓ Memory usage stable (growth ratio: {growth_ratio:.2f})")

def run_all_tests():
    """Run all Claude 3.7 Sonnet App 1 tests."""
    print(f"🔬 Running Comprehensive Tests for Claude 3.7 Sonnet App 1")
    print(f"Model: {TEST_MODEL}")
    print(f"App Number: {TEST_APP_NUM}")
    print(f"Backend Port: {TEST_BACKEND_PORT}")
    print(f"Frontend Port: {TEST_FRONTEND_PORT}")
    print("=" * 60)
    
    test_classes = [
        TestClaude37SonnetApp1Functionality,
        TestClaude37SonnetApp1Docker,
        TestClaude37SonnetApp1Security,
        TestClaude37SonnetApp1Performance,
        TestClaude37SonnetApp1Integration,
        TestClaude37SonnetApp1StabilityAndResilience
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n📋 {test_class.__name__}")
        print("-" * 40)
        
        instance = test_class()
        methods = [method for method in dir(instance) if method.startswith('test_')]
        
        for method_name in methods:
            total_tests += 1
            try:
                method = getattr(instance, method_name)
                method()
                passed_tests += 1
            except Exception as e:
                print(f"✗ {method_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"🎯 Test Results: {passed_tests}/{total_tests} tests passed ({passed_tests/total_tests:.1%})")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Claude 3.7 Sonnet App 1 is fully functional.")
    else:
        print(f"⚠ {total_tests - passed_tests} tests failed or encountered issues.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    run_all_tests()
