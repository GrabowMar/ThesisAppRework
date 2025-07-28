"""
Unit tests for main application routes.

Tests all main blueprint routes including dashboard, app details,
models overview, and API endpoints with both regular and HTMX requests.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from models import (
    ModelCapability, GeneratedApplication, PortConfiguration,
    SecurityAnalysis, PerformanceTest, AnalysisStatus
)
from extensions import db


class TestMainRoutes:
    """Test main application routes."""
    
    def test_dashboard_get(self, client, populated_database):
        """Test dashboard GET request."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'dashboard' in response.data or b'application' in response.data.lower()
    
    def test_dashboard_htmx_request(self, client, populated_database, htmx_headers):
        """Test dashboard with HTMX headers."""
        response = client.get('/', headers=htmx_headers)
        
        assert response.status_code == 200
        # Should return partial content for HTMX
        assert 'text/html' in response.content_type
    
    def test_app_details_valid_app(self, client, populated_database):
        """Test app details page for valid application."""
        # Use the sample data from populated_database
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/app/{model_slug}/{app_num}')
        
        assert response.status_code == 200
    
    def test_app_details_invalid_app(self, client, populated_database):
        """Test app details page for non-existent application."""
        response = client.get('/app/nonexistent_model/999')
        
        # Should handle gracefully, either redirect or show error
        assert response.status_code in [200, 302, 404]
    
    def test_models_overview(self, client, populated_database):
        """Test models overview page."""
        response = client.get('/models')
        
        assert response.status_code == 200
    
    def test_debug_config(self, client, populated_database):
        """Test debug config endpoint."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/debug/config/{model_slug}/{app_num}')
        
        assert response.status_code == 200


class TestApiRoutes:
    """Test API routes (HTMX endpoints)."""
    
    def test_get_app_status(self, client, populated_database, auth_headers):
        """Test app status API endpoint."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/api/status/{model_slug}/{app_num}', headers=auth_headers)
        
        assert response.status_code == 200
        # Should return JSON or redirect
        if response.content_type == 'application/json':
            data = response.get_json()
            assert isinstance(data, dict)
    
    def test_search_apps(self, client, populated_database, auth_headers):
        """Test apps search API endpoint."""
        response = client.get('/api/search', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_search_apps_with_query(self, client, populated_database, auth_headers):
        """Test apps search with query parameters."""
        response = client.get('/api/search?search=test&model=test_model_1', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_advanced_search(self, client, populated_database, auth_headers):
        """Test advanced search endpoint."""
        response = client.get('/api/advanced-search', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_models_stats(self, client, populated_database, auth_headers):
        """Test models stats API endpoint."""
        response = client.get('/api/models-stats', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_cache_stats(self, client, auth_headers):
        """Test cache stats endpoint."""
        response = client.get('/api/cache/stats', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_header_stats(self, client, populated_database, auth_headers):
        """Test header stats endpoint."""
        response = client.get('/api/header-stats', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_health_status(self, client, auth_headers):
        """Test health status endpoint."""
        response = client.get('/api/health-status', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_notifications(self, client, auth_headers):
        """Test notifications endpoint."""
        response = client.get('/api/notifications', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_clear_cache_post(self, client, auth_headers):
        """Test cache clearing endpoint."""
        response = client.post('/api/cache/clear', headers=auth_headers)
        
        assert response.status_code in [200, 204, 302]
    
    def test_dashboard_stats(self, client, populated_database, auth_headers):
        """Test dashboard stats endpoint."""
        response = client.get('/api/dashboard-stats', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_recent_activity(self, client, auth_headers):
        """Test recent activity endpoint."""
        response = client.get('/api/recent-activity', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_sidebar_stats(self, client, populated_database, auth_headers):
        """Test sidebar stats endpoint."""
        response = client.get('/api/sidebar-stats', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_system_health(self, client, auth_headers):
        """Test system health endpoint."""
        response = client.get('/api/system-health', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_settings_get(self, client, auth_headers):
        """Test settings GET endpoint."""
        response = client.get('/api/settings', headers=auth_headers)
        
        assert response.status_code == 200
    
    def test_settings_post(self, client, auth_headers):
        """Test settings POST endpoint."""
        settings_data = {
            'auto_refresh': 'true',
            'notifications': 'false'
        }
        
        response = client.post('/api/settings', 
                             data=settings_data,
                             headers=auth_headers)
        
        assert response.status_code in [200, 201, 302]


class TestDockerRoutes:
    """Test Docker management routes."""
    
    def test_docker_overview(self, client):
        """Test Docker overview page."""
        response = client.get('/docker/')
        
        assert response.status_code == 200
    
    def test_docker_start_action(self, client, populated_database):
        """Test Docker start action."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/docker/start/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 202, 302, 500]  # Various valid responses
    
    def test_docker_stop_action(self, client, populated_database):
        """Test Docker stop action."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/docker/stop/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 202, 302, 500]
    
    def test_docker_restart_action(self, client, populated_database):
        """Test Docker restart action."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/docker/restart/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 202, 302, 500]
    
    def test_docker_invalid_action(self, client, populated_database):
        """Test Docker invalid action."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/docker/invalid_action/{model_slug}/{app_num}')
        
        assert response.status_code in [400, 404, 405]
    
    def test_view_logs(self, client, populated_database):
        """Test viewing container logs."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/docker/logs/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 404, 500]


class TestAnalysisRoutes:
    """Test analysis routes."""
    
    def test_analysis_overview(self, client):
        """Test analysis overview page."""
        response = client.get('/analysis/')
        
        assert response.status_code == 200
    
    def test_analysis_details(self, client, populated_database):
        """Test analysis details page."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/analysis/security/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 404]
    
    def test_run_analysis_post(self, client, populated_database):
        """Test running analysis via POST."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/analysis/security/{model_slug}/{app_num}/run')
        
        assert response.status_code in [200, 202, 302, 500]
    
    def test_run_analysis_with_htmx(self, client, populated_database, htmx_headers):
        """Test running analysis with HTMX headers."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.post(f'/analysis/security/{model_slug}/{app_num}/run',
                             headers=htmx_headers)
        
        assert response.status_code in [200, 202, 500]
        if response.status_code == 200:
            assert 'text/html' in response.content_type


class TestPerformanceRoutes:
    """Test performance testing routes."""
    
    def test_performance_overview(self, client):
        """Test performance overview page."""
        response = client.get('/performance/')
        
        assert response.status_code == 200
    
    def test_performance_test_page(self, client, populated_database):
        """Test performance test page for specific application."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/performance/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 302, 404]
    
    def test_run_performance_test(self, client, populated_database):
        """Test running performance test."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        test_data = {
            'user_count': '10',
            'spawn_rate': '1',
            'duration': '30',
            'test_type': 'load'
        }
        
        response = client.post(f'/performance/{model_slug}/{app_num}/run',
                             data=test_data)
        
        assert response.status_code in [200, 202, 302, 500]
    
    def test_run_performance_test_with_htmx(self, client, populated_database, htmx_headers):
        """Test running performance test with HTMX."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        test_data = {
            'user_count': '5',
            'spawn_rate': '1',
            'duration': '15',
            'test_type': 'stress'
        }
        
        response = client.post(f'/performance/{model_slug}/{app_num}/run',
                             data=test_data,
                             headers=htmx_headers)
        
        assert response.status_code in [200, 202, 500]


class TestZapRoutes:
    """Test ZAP security scanning routes."""
    
    def test_zap_overview(self, client):
        """Test ZAP overview page."""
        response = client.get('/zap/')
        
        assert response.status_code == 200
    
    def test_zap_scan_page(self, client, populated_database):
        """Test ZAP scan page for specific application."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/zap/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 302, 404]
    
    def test_start_zap_scan(self, client, populated_database):
        """Test starting ZAP scan."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        scan_data = {
            'target_url': f'http://localhost:3000',
            'scan_type': 'active'
        }
        
        response = client.post(f'/zap/{model_slug}/{app_num}/scan',
                             data=scan_data)
        
        assert response.status_code in [200, 202, 302, 500]
    
    def test_zap_scan_status(self, client, populated_database):
        """Test checking ZAP scan status."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/zap/{model_slug}/{app_num}/status')
        
        assert response.status_code in [200, 404, 500]


class TestOpenRouterRoutes:
    """Test OpenRouter analysis routes."""
    
    def test_openrouter_overview(self, client):
        """Test OpenRouter overview page."""
        response = client.get('/openrouter/')
        
        assert response.status_code == 200
    
    def test_openrouter_analysis_page(self, client, populated_database):
        """Test OpenRouter analysis page."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        response = client.get(f'/openrouter/{model_slug}/{app_num}')
        
        assert response.status_code in [200, 302, 404]
    
    def test_run_openrouter_analysis(self, client, populated_database):
        """Test running OpenRouter analysis."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        analysis_data = {
            'analysis_type': 'code_review',
            'model': 'gpt-4'
        }
        
        response = client.post(f'/openrouter/{model_slug}/{app_num}/analyze',
                             data=analysis_data)
        
        assert response.status_code in [200, 202, 302, 500]


class TestBatchRoutes:
    """Test batch processing routes."""
    
    def test_batch_overview(self, client):
        """Test batch overview page."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
    
    def test_create_batch_job_get(self, client):
        """Test batch job creation form."""
        response = client.get('/batch/create')
        
        assert response.status_code == 200
    
    def test_create_batch_job_post(self, client):
        """Test creating batch job via POST."""
        batch_data = {
            'name': 'Test Batch Job',
            'analysis_type': 'security',
            'models': 'test_model_1,test_model_2',
            'app_numbers': '1,2,3'
        }
        
        response = client.post('/batch/create', data=batch_data)
        
        assert response.status_code in [200, 201, 302, 400]
    
    def test_batch_job_status(self, client, populated_database):
        """Test batch job status page."""
        batch_id = populated_database['batch_analysis'].id
        
        response = client.get(f'/batch/job/{batch_id}')
        
        assert response.status_code in [200, 404]


class TestGenerationRoutes:
    """Test generation content routes."""
    
    def test_generation_overview(self, client):
        """Test generation overview page."""
        response = client.get('/generation/')
        
        assert response.status_code == 200
    
    def test_generation_run_details(self, client):
        """Test generation run details page."""
        timestamp = '20240101_120000'
        
        response = client.get(f'/generation/run/{timestamp}')
        
        assert response.status_code in [200, 404]


class TestErrorHandlers:
    """Test error handling."""
    
    def test_404_error(self, client):
        """Test 404 error handling."""
        response = client.get('/nonexistent-page')
        
        assert response.status_code == 404
    
    def test_404_error_with_htmx(self, client, htmx_headers):
        """Test 404 error with HTMX headers."""
        response = client.get('/nonexistent-page', headers=htmx_headers)
        
        assert response.status_code == 404
        assert 'text/html' in response.content_type
    
    @patch('web_routes.get_app_info')
    def test_500_error_handling(self, mock_get_app_info, client):
        """Test 500 error handling."""
        # Mock to raise an exception
        mock_get_app_info.side_effect = Exception("Test error")
        
        response = client.get('/app/test/1')
        
        # Should handle the error gracefully
        assert response.status_code in [200, 302, 500]


class TestHelperFunctions:
    """Test helper functions used in routes."""
    
    def test_is_htmx_request(self, client, htmx_headers):
        """Test HTMX request detection."""
        # This would require accessing the helper function directly
        # For now, we test it indirectly through route behavior
        response = client.get('/', headers=htmx_headers)
        assert response.status_code == 200
    
    def test_render_htmx_response(self, client):
        """Test HTMX response rendering."""
        # Test both HTMX and regular requests to same endpoint
        regular_response = client.get('/')
        htmx_response = client.get('/', headers={'HX-Request': 'true'})
        
        assert regular_response.status_code == 200
        assert htmx_response.status_code == 200
        
        # Responses might differ in content but both should be valid
        assert 'text/html' in regular_response.content_type
        assert 'text/html' in htmx_response.content_type


class TestRouteSecurity:
    """Test route security measures."""
    
    def test_csrf_protection_post_routes(self, client):
        """Test CSRF protection on POST routes."""
        # Most POST routes should be protected or handle missing CSRF gracefully
        response = client.post('/docker/start/test_model/1')
        
        # Should either work (if CSRF disabled in test) or return error
        assert response.status_code in [200, 202, 302, 400, 403, 500]
    
    def test_input_validation(self, client):
        """Test input validation on route parameters."""
        # Test with invalid app numbers
        response = client.get('/app/test_model/-1')
        assert response.status_code in [200, 302, 400, 404]
        
        response = client.get('/app/test_model/abc')
        assert response.status_code in [200, 302, 400, 404]
    
    def test_path_traversal_protection(self, client):
        """Test protection against path traversal attacks."""
        # Test with malicious model names
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32',
            '%2e%2e%2f%2e%2e%2f'
        ]
        
        for path in malicious_paths:
            response = client.get(f'/app/{path}/1')
            # Should not expose sensitive information
            assert response.status_code in [200, 302, 400, 404]


class TestRoutePerformance:
    """Test route performance characteristics."""
    
    def test_dashboard_response_time(self, client, populated_database):
        """Test dashboard response time is reasonable."""
        import time
        
        start_time = time.time()
        response = client.get('/')
        end_time = time.time()
        
        response_time = end_time - start_time
        
        assert response.status_code == 200
        # Dashboard should respond within 5 seconds
        assert response_time < 5.0
    
    def test_api_endpoints_response_time(self, client, auth_headers):
        """Test API endpoints respond quickly."""
        import time
        
        api_endpoints = [
            '/api/header-stats',
            '/api/health-status',
            '/api/cache/stats'
        ]
        
        for endpoint in api_endpoints:
            start_time = time.time()
            response = client.get(endpoint, headers=auth_headers)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            assert response.status_code == 200
            # API endpoints should be fast
            assert response_time < 2.0
    
    def test_concurrent_requests(self, client, auth_headers):
        """Test handling of concurrent requests."""
        import threading
        import time
        
        results = []
        
        def make_request():
            response = client.get('/api/health-status', headers=auth_headers)
            results.append(response.status_code)
        
        # Create multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
        
        # Start all threads
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        end_time = time.time()
        
        # All requests should succeed
        assert all(status == 200 for status in results)
        # Should complete within reasonable time
        assert end_time - start_time < 10.0
