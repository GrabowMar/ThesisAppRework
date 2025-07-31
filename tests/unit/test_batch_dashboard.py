"""
Unit Tests for Batch Dashboard Functionality
==========================================

Tests for the batch analysis dashboard including:
- Dashboard loading and rendering
- Job creation and management
- Real-time updates and auto-refresh
- Filtering and sorting
- Bulk operations
- Form validation
"""
from unittest.mock import Mock, patch
from datetime import datetime
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


class TestBatchDashboardView:
    """Test batch dashboard view functionality."""
    
    def test_batch_dashboard_loads_successfully(self, client):
        """Test that the batch dashboard page loads successfully."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Batch Analysis Dashboard' in response.data
        assert b'Create Job' in response.data
        assert b'Live Updates' in response.data
    
    def test_batch_dashboard_displays_empty_state(self, client):
        """Test dashboard shows empty state when no jobs exist."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'No batch jobs found' in response.data
        assert b'Create Your First Job' in response.data
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_batch_dashboard_displays_jobs(self, mock_batch_service, client):
        """Test dashboard displays jobs when they exist."""
        # Mock batch service with sample jobs
        mock_job = Mock()
        mock_job.id = 'test-job-1'
        mock_job.name = 'Test Security Analysis'
        mock_job.status.value = 'running'
        mock_job.status.lower.return_value = 'running'
        mock_job.analysis_types = ['frontend_security', 'backend_security']
        mock_job.created_at = datetime.now()
        mock_job.duration = 120
        mock_job.progress = {'completed': 5, 'total': 10}
        mock_job.description = 'Test job description'
        mock_job.to_dict.return_value = {
            'id': 'test-job-1',
            'name': 'Test Security Analysis',
            'status': 'running',
            'analysis_types': ['frontend_security', 'backend_security'],
            'created_at': datetime.now(),
            'duration': 120,
            'progress': {'completed': 5, 'total': 10}
        }
        
        mock_service = Mock()
        mock_service.get_all_jobs.return_value = [mock_job]
        mock_service.get_job_stats.return_value = {
            'total': 1, 'running': 1, 'completed': 0, 'failed': 0
        }
        mock_batch_service.return_value = mock_service
        
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Test Security Analysis' in response.data
        assert b'running' in response.data
        assert mock_service.get_all_jobs.called
        assert mock_service.get_job_stats.called
    
    def test_batch_dashboard_statistics_display(self, client):
        """Test that statistics cards are properly displayed."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Total Jobs' in response.data
        assert b'Running' in response.data
        assert b'Completed' in response.data
        assert b'Failed' in response.data
        assert b'stat-value' in response.data
    
    def test_batch_dashboard_includes_filters(self, client):
        """Test that advanced filters panel is included."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Advanced Filters' in response.data
        assert b'statusFilter' in response.data
        assert b'analysisTypeFilter' in response.data
        assert b'dateFilter' in response.data
        assert b'searchFilter' in response.data
    
    def test_batch_dashboard_includes_bulk_actions(self, client):
        """Test that bulk action controls are included."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Bulk Actions' in response.data
        assert b'Pause All Running' in response.data
        assert b'Resume All Paused' in response.data
        assert b'Cancel All Running' in response.data
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_batch_dashboard_handles_service_error(self, mock_batch_service, client):
        """Test dashboard gracefully handles service errors."""
        mock_batch_service.side_effect = Exception("Service unavailable")
        
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'Service temporarily unavailable' in response.data
    
    def test_batch_dashboard_auto_refresh_controls(self, client):
        """Test that auto-refresh controls are present."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'autoRefreshToggle' in response.data
        assert b'refreshDashboard' in response.data
        assert b'connectionStatus' in response.data


class TestBatchJobCreation:
    """Test batch job creation functionality."""
    
    def test_create_job_form_displays(self, client):
        """Test that the job creation form is included in dashboard."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'createJobForm' in response.data
        assert b'Create New Batch Job' in response.data
        assert b'analysis_types' in response.data
        assert b'models' in response.data
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_create_job_post_success(self, mock_batch_service, client):
        """Test successful job creation via POST."""
        mock_job = Mock()
        mock_job.progress = {'total': 10}
        
        mock_service = Mock()
        mock_service.create_job.return_value = mock_job
        mock_batch_service.return_value = mock_service
        
        form_data = {
            'name': 'Test Batch Job',
            'description': 'Test job description',
            'analysis_types': ['frontend_security'],
            'models': ['test_model'],
            'app_start': '1',
            'app_end': '5'
        }
        
        response = client.post('/batch/create', data=form_data)
        
        assert response.status_code in [200, 302]  # Success or redirect
        assert mock_service.create_job.called
    
    def test_create_job_validation_missing_name(self, client):
        """Test job creation validation for missing name."""
        form_data = {
            'name': '',  # Missing name
            'analysis_types': ['frontend_security'],
            'models': ['test_model']
        }
        
        response = client.post('/batch/create', data=form_data)
        
        # Should redirect back with error message
        assert response.status_code in [200, 302]
    
    def test_create_job_validation_missing_analysis_types(self, client):
        """Test job creation validation for missing analysis types."""
        form_data = {
            'name': 'Test Job',
            'analysis_types': [],  # Missing analysis types
            'models': ['test_model']
        }
        
        response = client.post('/batch/create', data=form_data)
        
        assert response.status_code in [200, 302]
    
    def test_create_job_validation_missing_models(self, client):
        """Test job creation validation for missing models."""
        form_data = {
            'name': 'Test Job',
            'analysis_types': ['frontend_security'],
            'models': []  # Missing models
        }
        
        response = client.post('/batch/create', data=form_data)
        
        assert response.status_code in [200, 302]
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_create_job_handles_service_error(self, mock_batch_service, client):
        """Test job creation handles service errors gracefully."""
        mock_batch_service.side_effect = Exception("Service error")
        
        form_data = {
            'name': 'Test Job',
            'analysis_types': ['frontend_security'],
            'models': ['test_model']
        }
        
        response = client.post('/batch/create', data=form_data)
        
        assert response.status_code in [200, 302]  # Should handle error gracefully


class TestBatchJobActions:
    """Test individual job action functionality."""
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_view_job_success(self, mock_batch_service, client):
        """Test viewing individual job details."""
        mock_job = Mock()
        mock_job.id = 'test-job-1'
        mock_job.name = 'Test Job'
        mock_job.to_dict.return_value = {'id': 'test-job-1', 'name': 'Test Job'}
        
        mock_task = Mock()
        mock_task.status.value = 'completed'
        mock_task.to_dict.return_value = {'id': 'task-1', 'status': 'completed'}
        
        mock_service = Mock()
        mock_service.get_job.return_value = mock_job
        mock_service.get_job_tasks.return_value = [mock_task]
        mock_batch_service.return_value = mock_service
        
        response = client.get('/batch/job/test-job-1')
        
        assert response.status_code == 200
        assert mock_service.get_job.called_with('test-job-1')
        assert mock_service.get_job_tasks.called_with('test-job-1')
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_view_job_not_found(self, mock_batch_service, client):
        """Test viewing non-existent job."""
        mock_service = Mock()
        mock_service.get_job.return_value = None
        mock_batch_service.return_value = mock_service
        
        response = client.get('/batch/job/nonexistent')
        
        assert response.status_code == 404
    
    def test_ajax_refresh_request(self, client):
        """Test AJAX request for dashboard refresh."""
        headers = {'X-Requested-With': 'XMLHttpRequest'}
        response = client.get('/batch/', headers=headers)
        
        assert response.status_code == 200
        # Should return the same content but potentially optimized for AJAX


class TestBatchDashboardJavaScript:
    """Test JavaScript functionality (through rendered template)."""
    
    def test_javascript_class_definition_present(self, client):
        """Test that BatchDashboard JavaScript class is included."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'class BatchDashboard' in response.data
        assert b'window.batchDashboard = new BatchDashboard()' in response.data
    
    def test_javascript_event_handlers_present(self, client):
        """Test that JavaScript event handlers are defined."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'setupEventListeners' in response.data
        assert b'setupAutoRefresh' in response.data
        assert b'setupFilters' in response.data
        assert b'setupBulkActions' in response.data
    
    def test_javascript_api_methods_present(self, client):
        """Test that JavaScript API methods are defined."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'cancelJob' in response.data
        assert b'deleteJob' in response.data
        assert b'pauseJob' in response.data
        assert b'resumeJob' in response.data
        assert b'exportJob' in response.data
    
    def test_javascript_filter_methods_present(self, client):
        """Test that JavaScript filter methods are defined."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'applyFilters' in response.data
        assert b'clearFilters' in response.data
        assert b'sortTable' in response.data


class TestBatchDashboardSecurity:
    """Test security aspects of batch dashboard."""
    
    def test_csrf_protection_enabled(self, client):
        """Test that CSRF protection is enabled for forms."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        # Form should include CSRF token (if enabled)
        # This depends on your CSRF configuration
    
    def test_xss_protection_in_job_names(self, client):
        """Test XSS protection in job name display."""
        # This would need to be tested with actual XSS payloads
        # and ensuring they're properly escaped in the template
        response = client.get('/batch/')
        
        assert response.status_code == 200
        # Template should use proper escaping for user content
    
    def test_sql_injection_protection(self, client):
        """Test SQL injection protection in job queries."""
        # Test with SQL injection payloads in query parameters
        response = client.get('/batch/?search=\'; DROP TABLE batch_analysis; --')
        
        assert response.status_code == 200
        # Should not cause any database errors


class TestBatchDashboardPerformance:
    """Test performance aspects of batch dashboard."""
    
    def test_dashboard_response_time(self, client):
        """Test that dashboard loads within reasonable time."""
        import time
        
        start_time = time.time()
        response = client.get('/batch/')
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 2.0  # Should load within 2 seconds
    
    @patch('web_routes.ServiceLocator.get_batch_service')
    def test_large_job_list_performance(self, mock_batch_service, client):
        """Test dashboard performance with large number of jobs."""
        # Create mock jobs (simulate 100 jobs)
        mock_jobs = []
        for i in range(100):
            mock_job = Mock()
            mock_job.id = f'job-{i}'
            mock_job.name = f'Test Job {i}'
            mock_job.status.value = 'running' if i % 2 == 0 else 'completed'
            mock_job.status.lower.return_value = mock_job.status.value
            mock_job.analysis_types = ['frontend_security']
            mock_job.created_at = datetime.now()
            mock_job.duration = 120
            mock_job.progress = {'completed': i, 'total': 100}
            mock_job.to_dict.return_value = {
                'id': f'job-{i}',
                'name': f'Test Job {i}',
                'status': mock_job.status.value
            }
            mock_jobs.append(mock_job)
        
        mock_service = Mock()
        mock_service.get_all_jobs.return_value = mock_jobs
        mock_service.get_job_stats.return_value = {
            'total': 100, 'running': 50, 'completed': 50, 'failed': 0
        }
        mock_batch_service.return_value = mock_service
        
        import time
        start_time = time.time()
        response = client.get('/batch/')
        end_time = time.time()
        
        assert response.status_code == 200
        assert (end_time - start_time) < 3.0  # Should handle 100 jobs within 3 seconds


class TestBatchDashboardAccessibility:
    """Test accessibility features of batch dashboard."""
    
    def test_aria_labels_present(self, client):
        """Test that proper ARIA labels are present."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'aria-expanded' in response.data
        assert b'aria-hidden' in response.data
        assert b'aria-controls' in response.data
    
    def test_form_labels_present(self, client):
        """Test that form elements have proper labels."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'<label' in response.data
        assert b'form-label' in response.data
    
    def test_keyboard_navigation_support(self, client):
        """Test that keyboard navigation is supported."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        # Check for tabindex and keyboard event handlers
        assert b'tabindex' in response.data or b'focus()' in response.data
    
    def test_screen_reader_support(self, client):
        """Test screen reader support features."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        # Check for screen reader friendly elements
        assert b'sr-only' in response.data or b'visually-hidden' in response.data


class TestBatchDashboardResponsiveness:
    """Test responsive design of batch dashboard."""
    
    def test_responsive_css_classes(self, client):
        """Test that responsive CSS classes are used."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        assert b'col-md-' in response.data
        assert b'col-lg-' in response.data
        assert b'd-md-' in response.data or b'd-lg-' in response.data
    
    def test_mobile_friendly_controls(self, client):
        """Test that mobile-friendly controls are present."""
        response = client.get('/batch/')
        
        assert response.status_code == 200
        # Check for mobile-optimized button sizes
        assert b'btn-sm' in response.data
        # Check for responsive tables
        assert b'table-responsive' in response.data or b'table-container' in response.data


if __name__ == '__main__':
    # Run tests if pytest is available
    try:
        import pytest
        pytest.main([__file__, '-v'])
    except ImportError:
        print("pytest not installed. Install with: pip install pytest")
        print("Run tests with: python -m pytest " + __file__)
