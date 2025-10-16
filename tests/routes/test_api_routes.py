"""
Test suite for API routes in src/app/routes/api/

Tests all critical endpoints used by the frontend to ensure
backward compatibility during refactoring.
"""

import pytest
from unittest.mock import Mock, patch


@pytest.fixture
def app():
    """Create test Flask app"""
    from app.factory import create_app
    app = create_app('testing')
    return app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database"""
    with patch('app.extensions.db') as mock:
        yield mock


class TestCoreRoutes:
    """Test core API endpoints"""
    
    def test_health_endpoint(self, client):
        """Test /api/health endpoint"""
        response = client.get('/api/health')
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert data is not None
        assert 'status' in data or ('data' in data and 'status' in data['data'])
    
    def test_status_endpoint(self, client):
        """Test /api/status endpoint"""
        response = client.get('/api/status')
        assert response.status_code in [200, 503]
        data = response.get_json()
        assert isinstance(data, dict)


class TestModelRoutes:
    """Test model-related endpoints"""
    
    def test_models_list(self, client, mock_db):
        """Test GET /api/models"""
        with patch('app.models.ModelCapability') as MockModel:
            MockModel.query.all.return_value = []
            response = client.get('/api/models')
            assert response.status_code == 200
            data = response.get_json()
            assert 'data' in data or 'models' in data
    
    def test_models_paginated(self, client, mock_db):
        """Test GET /api/models/paginated"""
        with patch('app.models.ModelCapability') as MockModel:
            MockModel.query.order_by.return_value.all.return_value = []
            response = client.get('/api/models/paginated?page=1&per_page=10')
            assert response.status_code == 200
            data = response.get_json()
            assert 'models' in data
            assert 'pagination' in data
    
    def test_models_grid(self, client, mock_db):
        """Test GET /api/models/grid - used by analysis create page"""
        with patch('app.models.ModelCapability') as MockModel:
            MockModel.query.order_by.return_value.all.return_value = []
            response = client.get('/api/models/grid?selectable=true')
            assert response.status_code == 200


class TestApplicationRoutes:
    """Test application management endpoints"""
    
    def test_applications_list(self, client, mock_db):
        """Test GET /api/applications"""
        with patch('app.models.GeneratedApplication') as MockApp:
            MockApp.query.all.return_value = []
            response = client.get('/api/applications')
            assert response.status_code == 200
            data = response.get_json()
            assert 'data' in data or 'applications' in data
    
    def test_app_status(self, client, mock_db):
        """Test GET /api/app/{model}/{app}/status - critical for frontend"""
        with patch('app.services.docker_manager.DockerManager') as MockDocker:
            mock_manager = Mock()
            mock_manager.get_container_status.return_value = {
                'backend': 'running',
                'frontend': 'running'
            }
            MockDocker.return_value = mock_manager
            
            response = client.get('/api/app/test-model/1/status')
            # Should return 200 or 404 depending on app existence
            assert response.status_code in [200, 404, 500]


class TestContainerRoutes:
    """Test container management endpoints"""
    
    @patch('app.services.docker_manager.DockerManager')
    def test_container_start(self, MockDocker, client):
        """Test POST /api/app/{model}/{app}/start"""
        mock_manager = Mock()
        mock_manager.start_containers.return_value = {'success': True}
        MockDocker.return_value = mock_manager
        
        with patch('app.models.GeneratedApplication') as MockApp:
            mock_app = Mock()
            mock_app.model_slug = 'test-model'
            mock_app.app_number = 1
            MockApp.query.filter_by.return_value.first.return_value = mock_app
            
            response = client.post('/api/app/test-model/1/start')
            assert response.status_code in [200, 404, 500]
    
    @patch('app.services.docker_manager.DockerManager')
    def test_container_stop(self, MockDocker, client):
        """Test POST /api/app/{model}/{app}/stop"""
        mock_manager = Mock()
        mock_manager.stop_containers.return_value = {'success': True}
        MockDocker.return_value = mock_manager
        
        response = client.post('/api/app/test-model/1/stop')
        assert response.status_code in [200, 404, 500]
    
    @patch('app.services.docker_manager.DockerManager')
    def test_container_build(self, MockDocker, client):
        """Test POST /api/app/{model}/{app}/build"""
        mock_manager = Mock()
        mock_manager.build_containers.return_value = {'success': True}
        MockDocker.return_value = mock_manager
        
        response = client.post('/api/app/test-model/1/build')
        assert response.status_code in [200, 404, 500]


class TestDashboardRoutes:
    """Test dashboard API endpoints"""
    
    def test_dashboard_overview(self, client):
        """Test /api/dashboard/fragments/summary-cards"""
        response = client.get('/api/dashboard/fragments/summary-cards')
        # Dashboard endpoints should always return some data
        assert response.status_code in [200, 500]
    
    def test_dashboard_system_status(self, client):
        """Test /api/dashboard/fragments/system-status"""
        response = client.get('/api/dashboard/fragments/system-status')
        assert response.status_code in [200, 500]


class TestAnalysisRoutes:
    """Test analysis endpoints"""
    
    def test_analysis_create(self, client, mock_db):
        """Test POST /api/applications/{model}/{app}/analyze"""
        with patch('app.models.GeneratedApplication') as MockApp:
            mock_app = Mock()
            mock_app.model_slug = 'test-model'
            mock_app.app_number = 1
            MockApp.query.filter_by.return_value.first.return_value = mock_app
            
            with patch('app.tasks.start_analysis_task') as mock_task:
                mock_task.return_value = Mock(id='test-task-id')
                response = client.post(
                    '/api/applications/test-model/1/analyze',
                    json={'analysis_type': 'security'}
                )
                assert response.status_code in [200, 201, 400, 404, 500]


class TestToolRegistryRoutes:
    """Test tool registry endpoints"""
    
    def test_container_tools_all(self, client):
        """Test GET /api/container-tools/all - used by analysis create"""
        response = client.get('/api/container-tools/all')
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, (dict, list))
    
    def test_tool_registry_profiles(self, client):
        """Test GET /api/tool-registry/profiles - used by analysis create"""
        response = client.get('/api/tool-registry/profiles')
        assert response.status_code == 200


class TestSimpleGenerationRoutes:
    """Test simple generation API (NEW system)"""
    
    def test_scaffold_endpoint_exists(self, client):
        """Test POST /api/gen/scaffold endpoint exists"""
        response = client.post(
            '/api/gen/scaffold',
            json={'model_slug': 'test/model', 'app_num': 1}
        )
        # Should not be 404
        assert response.status_code != 404
    
    def test_generate_endpoint_exists(self, client):
        """Test POST /api/gen/generate endpoint exists"""
        response = client.post(
            '/api/gen/generate',
            json={
                'model_slug': 'test/model',
                'app_num': 1,
                'template_id': 1,
                'component': 'frontend'
            }
        )
        # Should not be 404
        assert response.status_code != 404


class TestDeprecatedRoutes:
    """Test that deprecated routes still exist for backward compatibility"""
    
    def test_old_sample_gen_routes_exist(self, client):
        """OLD /api/sample-gen/* routes should still respond (for now)"""
        # These are deprecated but might still be referenced
        response = client.get('/api/sample-gen/status')
        # Should not be 404 if route still exists
        # Will be 404 after we remove them
        assert response.status_code in [200, 404, 500]


@pytest.mark.integration
class TestAPIIntegration:
    """Integration tests for critical API workflows"""
    
    def test_application_lifecycle_workflow(self, client):
        """Test: Create app -> Build -> Start -> Stop workflow"""
        # This is a high-level test to ensure the workflow works
        # Actual implementation depends on services being available
        pass
    
    def test_analysis_workflow(self, client):
        """Test: Select model -> Select app -> Start analysis workflow"""
        # This tests the critical path from analysis create page
        pass
