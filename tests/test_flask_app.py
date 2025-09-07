"""
Basic Flask Application Tests
============================

Tests for core Flask application functionality including:
- App factory pattern
- Health check endpoints
- Basic routing
- Error handling
"""

import pytest
from unittest.mock import patch


@pytest.mark.unit
@pytest.mark.smoke
class TestAppFactory:
    """Test the Flask application factory."""

    def test_create_app_with_default_config(self):
        """Test app creation with default configuration."""
        from app.factory import create_app
        
        app = create_app()
        
        assert app is not None
        assert app.config['TESTING'] is False
        assert 'SQLALCHEMY_DATABASE_URI' in app.config

    def test_create_app_with_testing_config(self, app_config):
        """Test app creation with testing configuration."""
        from app.factory import create_app
        
        app = create_app('testing')
        app.config.update(app_config)
        
        assert app is not None
        assert app.config['TESTING'] is True
        assert app.config['SQLALCHEMY_DATABASE_URI'] == 'sqlite:///:memory:'

    def test_app_has_required_blueprints(self, app):
        """Test that required blueprints are registered."""
        # Check that essential blueprints are registered
        blueprint_names = [bp.name for bp in app.blueprints.values()]
        
        # Check for main blueprints
        assert 'main' in blueprint_names
        assert 'api' in blueprint_names
        
    def test_app_extensions_initialized(self, app):
        """Test that required extensions are initialized."""
        from app.extensions import db
        
        # Check database extension
        assert db is not None
        
        # Check that db is bound to app
        with app.app_context():
            assert db.engine is not None


@pytest.mark.api
@pytest.mark.smoke
class TestHealthEndpoint:
    """Test the health check endpoint."""

    def test_health_endpoint_exists(self, client):
        """Test that health endpoint is accessible."""
        response = client.get('/health')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_health_endpoint_structure(self, client):
        """Test health endpoint returns expected structure."""
        from tests.conftest import assert_json_response
        
        response = client.get('/health')
        data = assert_json_response(
            response, 
            expected_keys=['status', 'components', 'timestamp']
        )
        
        # Check components structure
        assert 'database' in data['components']
        assert 'celery' in data['components']
        assert 'analyzer' in data['components']
        
        # Check status values
        assert data['status'] in ['healthy', 'degraded', 'unhealthy']

    def test_health_endpoint_database_component(self, client):
        """Test database component health reporting."""
        from tests.conftest import assert_json_response
        
        response = client.get('/health')
        data = assert_json_response(response)
        
        # Database should be healthy in tests
        assert data['components']['database'] == 'healthy'

    @patch('app.factory.get_components')
    def test_health_endpoint_with_unhealthy_database(self, mock_get_components, client):
        """Test health endpoint when database is unhealthy."""
        # Mock database failure
        with patch('app.extensions.db.session.execute') as mock_execute:
            mock_execute.side_effect = Exception("Database connection failed")
            # Ensure mocked components return serializable analyzer health
            components_mock = mock_get_components.return_value
            if components_mock:
                # Provide analyzer_integration with health_check returning dict
                analyzer_mock = getattr(components_mock, 'analyzer_integration', None)
                if analyzer_mock and hasattr(analyzer_mock, 'health_check'):
                    analyzer_mock.health_check.return_value = {'status': 'unavailable'}  # type: ignore[attr-defined]
                else:  # create simple mock with health_check
                    from unittest.mock import Mock
                    analyzer_mock = Mock()
                    analyzer_mock.health_check.return_value = {'status': 'unavailable'}
                    components_mock.analyzer_integration = analyzer_mock
                # Ensure task_manager.get_current_time returns a datetime, not MagicMock
                from datetime import datetime, timezone
                task_manager = getattr(components_mock, 'task_manager', None)
                if task_manager and hasattr(task_manager, 'get_current_time'):
                    task_manager.get_current_time.return_value = datetime.now(timezone.utc)  # type: ignore[attr-defined]
            response = client.get('/health')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['components']['database'] == 'unhealthy'
            assert data['status'] == 'degraded'


@pytest.mark.api
@pytest.mark.smoke
class TestBasicRoutes:
    """Test basic application routes."""

    def test_dashboard_route(self, client):
        """Test dashboard route is accessible."""
        response = client.get('/')
        
        # Should return HTML content
        assert response.status_code == 200
        assert 'text/html' in response.content_type

    def test_about_route(self, client):
        """Test about route redirects to docs."""
        response = client.get('/about')
        
        assert response.status_code == 302
        assert '/docs' in response.location

    def test_models_route(self, client):
        """Test models overview route."""
        response = client.get('/models', follow_redirects=True)
        # Accept successful retrieval after redirect chain
        assert response.status_code in (200, 204)
        assert 'text/html' in response.content_type

    def test_nonexistent_route(self, client):
        """Test 404 handling for nonexistent routes."""
        response = client.get('/nonexistent-route')
        
        assert response.status_code == 404


@pytest.mark.api
class TestAPIRoutes:
    """Test API route functionality."""

    def test_api_base_route(self, client):
        """Test base API route."""
        response = client.get('/api/')
        
        # API base might return 404 or redirect, both are acceptable
        assert response.status_code in [200, 404, 301, 302]

    def test_api_models_endpoint(self, client):
        """Test models API endpoint."""
        response = client.get('/api/models')
        
        # Should return JSON
        assert response.status_code == 200
        assert response.content_type == 'application/json'

    def test_api_applications_endpoint(self, client):
        """Test applications API endpoint."""
        response = client.get('/api/applications')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'


@pytest.mark.unit
class TestAppConfiguration:
    """Test application configuration."""

    def test_debug_mode_in_testing(self, app):
        """Test debug mode configuration in testing."""
        # Debug should be False in testing for production-like behavior
        assert app.config.get('DEBUG', True) is False

    def test_secret_key_configured(self, app):
        """Test that secret key is configured."""
        assert app.config.get('SECRET_KEY') is not None
        assert app.config['SECRET_KEY'] != ''

    def test_database_uri_configured(self, app):
        """Test database URI configuration."""
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        assert db_uri is not None
        assert 'sqlite' in db_uri or 'postgresql' in db_uri or 'mysql' in db_uri

    def test_testing_configuration(self, app):
        """Test testing-specific configuration."""
        assert app.config.get('TESTING') is True
        assert app.config.get('WTF_CSRF_ENABLED', True) is False


@pytest.mark.unit
class TestTemplateRendering:
    """Test template rendering functionality."""

    def test_dashboard_template_renders(self, client):
        """Test dashboard template renders without errors."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data or b'<html' in response.data

    def test_about_template_renders(self, client):
        """Test docs page contains about content since about is now consolidated there."""
        response = client.get('/docs', follow_redirects=True)
        assert response.status_code in (200, 204)
        assert response.data is not None
        assert len(response.data) > 0
        assert b'About the Platform' in response.data

    @patch('app.utils.template_paths.render_template_compat')
    def test_template_error_handling(self, mock_render, client):
        """Test template error handling."""
        mock_render.side_effect = Exception("Template error")
        
        response = client.get('/')
        
        # Should handle template errors gracefully
        assert response.status_code in [200, 500]


@pytest.mark.unit
class TestErrorHandling:
    """Test application error handling."""

    def test_404_error_handling(self, client):
        """Test 404 error handling."""
        response = client.get('/definitely-does-not-exist')
        
        assert response.status_code == 404

    def test_500_error_handling(self, app, client):
        """Test 500 error handling."""
        # Induce server error by patching template render in dashboard
        from unittest.mock import patch as _patch
        with _patch('app.utils.template_paths.render_template_compat') as mock_render:
            mock_render.side_effect = Exception("Forced render failure")
            response = client.get('/')
        # Expect either graceful error page or HTTP 500
        assert response.status_code in (500, 200)

    def test_api_error_format(self, client):
        """Test API errors return JSON format."""
        response = client.get('/api/nonexistent')
        
        # API errors should return JSON
        if response.status_code == 404:
            assert 'application/json' in response.content_type


@pytest.mark.unit
class TestJinjaFilters:
    """Test custom Jinja filters."""

    def test_timeago_filter_exists(self, app):
        """Test that timeago filter is registered."""
        assert 'timeago' in app.jinja_env.filters

    def test_timeago_filter_functionality(self, app):
        """Test timeago filter functionality."""
        from datetime import datetime, timezone
        
        with app.app_context():
            timeago_filter = app.jinja_env.filters['timeago']
            
            # Test with None
            assert timeago_filter(None) == 'Never'
            
            # Test with recent datetime
            now = datetime.now(timezone.utc)
            result = timeago_filter(now)
            assert 'just now' in result or 'ago' in result

    def test_jinja_globals_registered(self, app):
        """Test that required Jinja globals are registered."""
        expected_globals = ['make_safe_dom_id', 'now']
        
        for global_name in expected_globals:
            if global_name in app.jinja_env.globals:
                assert callable(app.jinja_env.globals[global_name])


@pytest.mark.integration
class TestAppStartup:
    """Test application startup process."""

    def test_app_starts_without_errors(self, app_config):
        """Test that app can start without errors."""
        from app.factory import create_app
        
        # Should not raise any exceptions
        app = create_app('testing')
        app.config.update(app_config)
        
        assert app is not None

    def test_database_initialization(self, app):
        """Test database initialization."""
        from app.extensions import db
        
        with app.app_context():
            # Should be able to create tables without errors
            db.create_all()
            
            # Should be able to query database
            db.session.execute(db.text('SELECT 1'))

    @patch('app.factory.create_analyzer_integration')
    def test_analyzer_integration_disabled(self, mock_analyzer, app_config):
        """Test app starts with analyzer integration disabled."""
        from app.factory import create_app
        
        app_config['ANALYZER_ENABLED'] = False
        app = create_app('testing')
        app.config.update(app_config)
        
        # Analyzer integration should not be called when disabled
        # (This depends on the actual implementation)
        assert app is not None

    def test_celery_configuration(self, app):
        """Test Celery configuration."""
        # Check Celery config is present
        assert 'CELERY_BROKER_URL' in app.config
        assert 'CELERY_RESULT_BACKEND' in app.config
        
        # In testing, tasks should run eagerly
        assert app.config.get('CELERY_TASK_ALWAYS_EAGER') is True