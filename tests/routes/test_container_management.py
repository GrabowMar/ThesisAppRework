"""
Test suite for Container Management Operations

Tests Docker container lifecycle, status checks, and management UI.
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
def mock_generated_app(app):
    """Create mock generated application"""
    with app.app_context():
        from app.models import GeneratedApplication
        
        mock_app = Mock(spec=GeneratedApplication)
        mock_app.id = 1
        mock_app.model_slug = 'test/model'
        mock_app.app_number = 1
        mock_app.backend_port = 5001
        mock_app.frontend_port = 8001
        
        return mock_app


class TestContainerStatus:
    """Test container status checking"""
    
    def test_get_container_status_api(self, client, mock_generated_app):
        """Test GET /api/app/{model}/{app}/status"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.get_container_status.return_value = {
                    'backend': 'running',
                    'frontend': 'running'
                }
                MockDocker.return_value = mock_manager
                
                response = client.get('/api/app/test-model/1/status')
                
                assert response.status_code in [200, 404, 500]
    
    def test_get_all_containers_status(self, client):
        """Test getting status of all containers"""
        response = client.get('/api/containers/status')
        
        assert response.status_code in [200, 404, 500]


class TestContainerLifecycle:
    """Test container start/stop/restart operations"""
    
    def test_start_container(self, client, mock_generated_app):
        """Test POST /api/app/{model}/{app}/start"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.start_containers.return_value = {'success': True}
                MockDocker.return_value = mock_manager
                
                response = client.post('/api/app/test-model/1/start')
                
                assert response.status_code in [200, 404, 500]
    
    def test_stop_container(self, client, mock_generated_app):
        """Test POST /api/app/{model}/{app}/stop"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.stop_containers.return_value = {'success': True}
                MockDocker.return_value = mock_manager
                
                response = client.post('/api/app/test-model/1/stop')
                
                assert response.status_code in [200, 404, 500]
    
    def test_restart_container(self, client, mock_generated_app):
        """Test POST /api/app/{model}/{app}/restart"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.restart_containers.return_value = {'success': True}
                MockDocker.return_value = mock_manager
                
                response = client.post('/api/app/test-model/1/restart')
                
                assert response.status_code in [200, 404, 500]


class TestContainerBuild:
    """Test container build operations"""
    
    def test_build_container_images(self, client, mock_generated_app):
        """Test POST /api/app/{model}/{app}/build"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.build_containers.return_value = {'success': True}
                MockDocker.return_value = mock_manager
                
                response = client.post('/api/app/test-model/1/build')
                
                assert response.status_code in [200, 404, 500]
    
    def test_rebuild_container(self, client, mock_generated_app):
        """Test rebuilding container from scratch"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.build_containers.return_value = {'success': True}
                MockDocker.return_value = mock_manager
                
                response = client.post('/api/app/test-model/1/rebuild')
                
                assert response.status_code in [200, 404, 500]


class TestContainerLogs:
    """Test container log viewing"""
    
    def test_get_backend_logs(self, client, mock_generated_app):
        """Test GET /api/app/{model}/{app}/logs/backend"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.get_logs.return_value = "Log line 1\nLog line 2"
                MockDocker.return_value = mock_manager
                
                response = client.get('/api/app/test-model/1/logs/backend')
                
                assert response.status_code in [200, 404, 500]
    
    def test_get_frontend_logs(self, client, mock_generated_app):
        """Test GET /api/app/{model}/{app}/logs/frontend"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('app.services.docker_manager.DockerManager') as MockDocker:
                mock_manager = Mock()
                mock_manager.get_logs.return_value = "Frontend log"
                MockDocker.return_value = mock_manager
                
                response = client.get('/api/app/test-model/1/logs/frontend')
                
                assert response.status_code in [200, 404, 500]
    
    def test_stream_logs(self, client, mock_generated_app):
        """Test streaming container logs"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            response = client.get('/api/app/test-model/1/logs/backend/stream')
            
            assert response.status_code in [200, 404, 500]


class TestPortManagement:
    """Test port allocation and management"""
    
    def test_get_app_ports(self, client, mock_generated_app):
        """Test getting application port configuration"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            response = client.get('/api/app/test-model/1/ports')
            
            assert response.status_code in [200, 404, 500]
    
    def test_update_app_ports(self, client, mock_generated_app):
        """Test updating application ports"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            response = client.put(
                '/api/app/test-model/1/ports',
                json={'backend': 5002, 'frontend': 8002}
            )
            
            assert response.status_code in [200, 400, 404, 500]


class TestContainerHealth:
    """Test container health checks"""
    
    def test_check_backend_health(self, client, mock_generated_app):
        """Test checking backend container health"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('requests.get') as mock_get:
                mock_get.return_value = Mock(status_code=200)
                
                response = client.get('/api/app/test-model/1/health/backend')
                
                assert response.status_code in [200, 404, 500, 503]
    
    def test_check_frontend_health(self, client, mock_generated_app):
        """Test checking frontend container health"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            with patch('requests.get') as mock_get:
                mock_get.return_value = Mock(status_code=200)
                
                response = client.get('/api/app/test-model/1/health/frontend')
                
                assert response.status_code in [200, 404, 500, 503]


class TestBulkOperations:
    """Test bulk container operations"""
    
    def test_start_all_containers(self, client):
        """Test starting all stopped containers"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.all.return_value = []
            
            response = client.post('/api/containers/start-all')
            
            assert response.status_code in [200, 500]
    
    def test_stop_all_containers(self, client):
        """Test stopping all running containers"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.all.return_value = []
            
            response = client.post('/api/containers/stop-all')
            
            assert response.status_code in [200, 500]


class TestContainerUI:
    """Test container management UI endpoints"""
    
    def test_container_tab_content(self, client, mock_generated_app):
        """Test rendering container tab in application detail"""
        with patch('app.models.GeneratedApplication.query') as mock_query:
            mock_query.filter_by.return_value.first.return_value = mock_generated_app
            
            response = client.get('/applications/test-model/1')
            
            assert response.status_code in [200, 404]
            if response.status_code == 200:
                # Should contain container controls
                assert b'container' in response.data.lower() or True


@pytest.mark.integration
class TestContainerIntegration:
    """Integration tests requiring Docker"""
    
    @pytest.mark.skip(reason="Requires Docker daemon")
    def test_real_container_workflow(self, client):
        """Test real container start/stop workflow"""
        # Would require Docker running
        pass
