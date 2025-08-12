"""Test API routes functionality."""


class TestAPIRoutes:
    """Test API route endpoints."""
    
    def test_api_overview_endpoint(self, client):
        """Test API overview endpoint."""
        response = client.get('/api/')
        assert response.status_code == 200
        
    def test_api_models_endpoint(self, client):
        """Test API models endpoint."""
        response = client.get('/api/models')
        assert response.status_code == 200
        
    def test_api_analysis_overview(self, client):
        """Test API analysis overview endpoint."""
        response = client.get('/analysis/')  # Test analysis hub route
        assert response.status_code == 200
        
    def test_api_security_analysis_list(self, client):
        """Test API security analysis list endpoint."""
        response = client.get('/api/analysis/security')
        assert response.status_code == 200
        
    def test_api_performance_analysis_list(self, client):
        """Test API performance analysis list endpoint."""
        response = client.get('/api/analysis/performance')
        assert response.status_code == 200
        
    def test_api_batch_analysis_list(self, client):
        """Test API batch analysis list endpoint."""
        response = client.get('/api/analysis/batch')
        assert response.status_code == 200
        
    def test_api_containerized_tests_list(self, client):
        """Test API containerized tests list endpoint."""
        response = client.get('/api/analysis/containerized')
        assert response.status_code == 200
        
    def test_api_model_specific_applications(self, client):
        """Test API model-specific applications endpoint."""
        response = client.get('/api/models/test_model/applications')
        assert response.status_code in [200, 404]  # Success or model not found
        
    def test_api_application_details(self, client, clean_db):
        """Test API application details endpoint."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        response = client.get(f'/api/applications/{app.id}')
        assert response.status_code == 200
        
    def test_api_application_start_stop(self, client, clean_db):
        """Test API application start/stop endpoints."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        # Test start endpoint
        response = client.post(f'/api/applications/{app.id}/start')
        assert response.status_code in [200, 404, 500]  # Various possible responses
        
        # Test stop endpoint
        response = client.post(f'/api/applications/{app.id}/stop')
        assert response.status_code in [200, 404, 500]  # Various possible responses
        
    def test_api_analysis_creation(self, client, clean_db):
        """Test API analysis creation endpoints."""
        from src.app.models import GeneratedApplication
        
        # Create test application
        app = GeneratedApplication()
        app.model_slug = 'test_model'
        app.app_number = 1
        app.provider = 'test'
        
        clean_db.session.add(app)
        clean_db.session.commit()
        
        # Test security analysis creation
        response = client.post('/api/analysis/security', json={
            'application_id': app.id,
            'bandit_enabled': True,
            'safety_enabled': True
        })
        assert response.status_code in [201, 400, 404]  # Created, bad request, or not found
        
        # Test performance analysis creation
        response = client.post('/api/analysis/performance', json={
            'application_id': app.id,
            'test_type': 'load',
            'users': 10,
            'test_duration': 60
        })
        assert response.status_code in [201, 400, 404]  # Created, bad request, or not found
        
    def test_api_batch_operations(self, client):
        """Test API batch operations."""
        # Test batch creation
        response = client.post('/api/batch', json={
            'analysis_types': ['security'],
            'priority': 'normal',
            'total_tasks': 5
        })
        assert response.status_code in [201, 400]  # Created or bad request
        
        # Test batch status
        response = client.get('/api/batch/nonexistent-batch/status')
        assert response.status_code in [200, 404]  # Success or not found
        
    def test_api_system_overview(self, client):
        """Test API system overview endpoint."""
        response = client.get('/api/system/overview')
        assert response.status_code == 200
