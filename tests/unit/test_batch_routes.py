"""
Test Batch Routes
================

Tests for batch analysis routes.
"""


def test_batch_overview(client):
    """Test batch overview page."""
    response = client.get('/batch/')
    assert response.status_code == 200


def test_batch_create_get(client):
    """Test batch create page GET request."""
    response = client.get('/batch/create')
    assert response.status_code == 200


def test_batch_create_post_invalid(client):
    """Test batch create POST with invalid data."""
    response = client.post('/batch/create', data={})
    # Should either redirect or show errors
    assert response.status_code in [200, 302, 400]


def test_batch_api_status_nonexistent(client):
    """Test batch status API for nonexistent batch."""
    response = client.get('/batch/api/status/nonexistent-id')
    assert response.status_code == 404


class TestBatchWithData:
    """Test batch routes with database data."""
    
    def test_batch_overview_with_data(self, client, clean_db):
        """Test batch overview with sample data."""
        from src.app.models import BatchAnalysis
        from src.app.constants import JobStatus, JobPriority
        
        # Create sample batch
        batch = BatchAnalysis()
        batch.batch_id = 'test-batch-id'
        batch.status = JobStatus.PENDING
        batch.priority = JobPriority.NORMAL
        batch.analysis_types = '["security"]'
        batch.model_filter = '["test_model"]'
        batch.app_filter = '[1, 2]'
        batch.total_tasks = 2
        
        clean_db.session.add(batch)
        clean_db.session.commit()
        
        response = client.get('/batch/')
        assert response.status_code == 200
        
    def test_batch_detail_view(self, client, clean_db):
        """Test batch detail view."""
        from src.app.models import BatchAnalysis
        from src.app.constants import JobStatus, JobPriority
        
        # Create sample batch
        batch = BatchAnalysis()
        batch.batch_id = 'test-batch-detail'
        batch.status = JobStatus.RUNNING
        batch.priority = JobPriority.HIGH
        batch.analysis_types = '["security", "performance"]'
        batch.model_filter = '["test_model"]'
        batch.app_filter = '[1]'
        batch.total_tasks = 2
        batch.completed_tasks = 1
        
        clean_db.session.add(batch)
        clean_db.session.commit()
        
        response = client.get('/batch/test-batch-detail')
        assert response.status_code == 200
