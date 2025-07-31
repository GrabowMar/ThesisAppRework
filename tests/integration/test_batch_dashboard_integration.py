"""
Integration Tests for Batch Dashboard
===================================

Full integration tests that test the complete batch dashboard workflow
including database operations, service interactions, and UI rendering.
"""
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestBatchDashboardIntegration:
    """Integration tests for batch dashboard functionality."""
    
    def test_full_dashboard_workflow(self, client, init_database):
        """Test complete dashboard workflow from loading to job creation."""
        # Step 1: Load dashboard
        response = client.get('/batch/')
        assert response.status_code == 200
        
        # Step 2: Verify empty state
        assert b'No batch jobs found' in response.data
        
        # Step 3: Create a job
        form_data = {
            'name': 'Integration Test Job',
            'description': 'Test job for integration testing',
            'analysis_types': ['frontend_security'],
            'models': ['test_model'],
            'app_start': '1',
            'app_end': '3'
        }
        
        create_response = client.post('/batch/create', data=form_data)
        assert create_response.status_code in [200, 302]
        
        # Step 4: Verify job appears in dashboard
        dashboard_response = client.get('/batch/')
        assert dashboard_response.status_code == 200
    
    def test_dashboard_with_sample_data(self, client, populated_database):
        """Test dashboard with populated database."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Batch Analysis Dashboard' in response.data
        
        # Should show statistics
        assert b'Total Jobs' in response.data
        assert b'Running' in response.data
        assert b'Completed' in response.data
        assert b'Failed' in response.data
    
    def test_dashboard_error_handling(self, client):
        """Test dashboard error handling with service failures."""
        with patch('web_routes.ServiceLocator.get_batch_service') as mock_service:
            # Simulate service failure
            mock_service.side_effect = Exception("Database connection failed")
            
            response = client.get('/batch/')
            
            # Should still render but show error message
            assert response.status_code == 200
            assert b'Service temporarily unavailable' in response.data
    
    def test_job_creation_end_to_end(self, client, init_database):
        """Test complete job creation workflow."""
        # Get create form
        response = client.get('/batch/create')
        assert response.status_code == 200
        
        # Submit valid job
        form_data = {
            'name': 'E2E Test Job',
            'description': 'End-to-end test job',
            'analysis_types': ['backend_security', 'performance'],
            'models': ['anthropic_claude-3-sonnet'],
            'app_start': '1',
            'app_end': '2',
            'max_parallel': '2',
            'timeout': '15',
            'security_tools': ['bandit', 'safety'],
            'performance_tools': ['load_test'],
            'auto_cleanup': 'on',
            'save_logs': 'on'
        }
        
        response = client.post('/batch/create', data=form_data)
        assert response.status_code in [200, 302]
        
        # Verify redirect to dashboard
        if response.status_code == 302:
            assert '/batch' in response.location
    
    def test_ajax_updates(self, client):
        """Test AJAX refresh functionality."""
        # Test with AJAX headers
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/html'
        }
        
        response = client.get('/batch/', headers=headers)
        assert response.status_code == 200
    
    def test_dashboard_performance_with_many_jobs(self, client, init_database):
        """Test dashboard performance with many jobs."""
        import time
        
        # Simulate many jobs by mocking the service
        with patch('web_routes.ServiceLocator.get_batch_service') as mock_service:
            # Create mock jobs
            mock_jobs = []
            for i in range(50):
                mock_job = Mock()
                mock_job.id = f'job-{i}'
                mock_job.name = f'Performance Test Job {i}'
                mock_job.status.value = 'running' if i % 3 == 0 else 'completed'
                mock_job.status.lower.return_value = mock_job.status.value
                mock_job.analysis_types = ['frontend_security']
                mock_job.created_at = datetime.now()
                mock_job.duration = 120 + i
                mock_job.progress = {'completed': i, 'total': 50}
                mock_job.description = f'Performance test job {i}'
                mock_job.to_dict.return_value = {
                    'id': f'job-{i}',
                    'name': f'Performance Test Job {i}',
                    'status': mock_job.status.value,
                    'analysis_types': ['frontend_security'],
                    'created_at': datetime.now(),
                    'duration': 120 + i,
                    'progress': {'completed': i, 'total': 50}
                }
                mock_jobs.append(mock_job)
            
            mock_batch_service = Mock()
            mock_batch_service.get_all_jobs.return_value = mock_jobs
            mock_batch_service.get_job_stats.return_value = {
                'total': 50, 'running': 17, 'completed': 33, 'failed': 0
            }
            mock_service.return_value = mock_batch_service
            
            # Measure response time
            start_time = time.time()
            response = client.get('/batch/')
            end_time = time.time()
            
            assert response.status_code == 200
            assert (end_time - start_time) < 2.0  # Should load within 2 seconds
            
            # Verify all jobs are rendered
            for i in range(min(10, len(mock_jobs))):  # Check first 10 jobs
                assert f'Performance Test Job {i}'.encode() in response.data
    
    def test_responsive_design_elements(self, client):
        """Test that responsive design elements are present."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for Bootstrap responsive classes
        responsive_classes = [
            b'col-md-', b'col-lg-', b'col-sm-',
            b'd-md-', b'd-lg-', b'd-sm-',
            b'container-fluid'
        ]
        
        content = response.data
        for css_class in responsive_classes:
            if css_class in content:
                break
        else:
            # At least one responsive class should be present
            assert False, "No responsive CSS classes found"
    
    def test_accessibility_features(self, client):
        """Test accessibility features in the dashboard."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for accessibility attributes
        accessibility_features = [
            b'aria-expanded', b'aria-hidden', b'aria-controls',
            b'role=', b'tabindex', b'aria-label'
        ]
        
        content = response.data
        found_features = sum(1 for feature in accessibility_features if feature in content)
        
        # Should have at least 3 accessibility features
        assert found_features >= 3, f"Only found {found_features} accessibility features"
    
    def test_javascript_integration(self, client):
        """Test JavaScript integration in the dashboard."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for JavaScript features
        js_features = [
            b'BatchDashboard', b'addEventListener', 
            b'fetch(', b'async', b'Promise'
        ]
        
        content = response.data
        for feature in js_features:
            assert feature in content, f"JavaScript feature {feature} not found"
    
    def test_css_styling_integration(self, client):
        """Test CSS styling integration."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for custom CSS classes
        css_classes = [
            b'action-btn', b'status-badge', b'progress-container',
            b'stats-card', b'filter-group'
        ]
        
        content = response.data
        for css_class in css_classes:
            assert css_class in content, f"CSS class {css_class} not found"
    
    def test_form_validation_integration(self, client):
        """Test form validation integration."""
        # Test with invalid data
        invalid_form_data = {
            'name': '',  # Empty name
            'analysis_types': [],  # No analysis types
            'models': []  # No models
        }
        
        response = client.post('/batch/create', data=invalid_form_data)
        
        # Should handle validation errors gracefully
        assert response.status_code in [200, 302, 400]
    
    def test_real_time_features(self, client):
        """Test real-time update features."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for real-time features
        realtime_features = [
            b'autoRefreshToggle', b'refreshDashboard',
            b'connectionStatus', b'setInterval'
        ]
        
        content = response.data
        for feature in realtime_features:
            assert feature in content, f"Real-time feature {feature} not found"
    
    def test_export_functionality(self, client):
        """Test export functionality integration."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for export features
        assert b'exportJobs' in response.data
        assert b'export-job-btn' in response.data
    
    def test_bulk_operations_integration(self, client):
        """Test bulk operations integration."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for bulk operation features
        bulk_features = [
            b'selectAllJobs', b'job-checkbox',
            b'pauseAllJobs', b'resumeAllJobs', b'cancelAllJobs'
        ]
        
        content = response.data
        for feature in bulk_features:
            assert feature in content, f"Bulk operation feature {feature} not found"
    
    def test_error_handling_integration(self, client):
        """Test error handling integration across the dashboard."""
        # Test various error scenarios
        error_scenarios = [
            '/batch/job/nonexistent',  # Non-existent job
            '/batch/job/invalid-id',   # Invalid job ID
        ]
        
        for url in error_scenarios:
            response = client.get(url)
            # Should handle errors gracefully (not crash)
            assert response.status_code in [200, 404, 500]
    
    def test_security_headers(self, client):
        """Test security headers in dashboard responses."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for basic security considerations
        # (This depends on your Flask security configuration)
        headers = response.headers
        
        # Content-Type should be set
        assert 'Content-Type' in headers
        assert 'text/html' in headers['Content-Type']
    
    def test_internationalization_support(self, client):
        """Test internationalization features if implemented."""
        # Test with different language headers
        headers = {'Accept-Language': 'en-US,en;q=0.9'}
        response = client.get('/batch/', headers=headers)
        
        assert response.status_code == 200
        # Should handle language preferences gracefully
    
    def test_mobile_compatibility(self, client):
        """Test mobile compatibility features."""
        # Simulate mobile user agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15'
        }
        
        response = client.get('/batch/', headers=headers)
        
        assert response.status_code == 200
        
        # At least viewport should be present in meta tags for mobile compatibility
        assert b'viewport' in response.data
    
    def test_dashboard_state_persistence(self, client):
        """Test dashboard state persistence features."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        
        # Check for localStorage usage
        assert b'localStorage' in response.data
        assert b'batchDashboardAutoRefresh' in response.data


class TestBatchDashboardAPI:
    """Test API endpoints used by the dashboard."""
    
    def test_job_status_api(self, client):
        """Test job status API endpoints."""
        # These would be API endpoints for real-time updates
        # Placeholder tests for when API endpoints are implemented
        pass
    
    def test_bulk_action_api(self, client):
        """Test bulk action API endpoints."""
        # Tests for bulk pause, resume, cancel operations
        pass
    
    def test_export_api(self, client):
        """Test export API endpoints."""
        # Tests for job data export functionality
        pass


if __name__ == '__main__':
    # Run tests if pytest is available
    try:
        import pytest
        pytest.main([__file__, '-v'])
    except ImportError:
        print("pytest not installed. Install with: pip install pytest")
        print("Run tests with: python -m pytest " + __file__)
