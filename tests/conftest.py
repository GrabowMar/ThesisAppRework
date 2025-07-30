"""
Test configuration and fixtures for Thesis Research App tests.

This module provides pytest fixtures and configuration for testing
the Flask application routes, models, and services.
"""
import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import create_app
from extensions import db
from models import (
    ModelCapability, PortConfiguration, GeneratedApplication,
    SecurityAnalysis, PerformanceTest, BatchAnalysis, AnalysisStatus
)


class TestConfig:
    """Test configuration."""
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    APPLICATION_ROOT = '/'  # Fix for Flask test client
    PORT_CONFIG = []  # Will be populated by fixtures


@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    # Import here to avoid circular imports
    from app import Config, setup_logging, load_model_integration_data
    from extensions import init_extensions, db
    from flask import Flask
    from pathlib import Path
    
    # Create a test config class
    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = 'test-secret-key-that-is-long-enough-to-be-secure'  # Longer secret key
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        APPLICATION_ROOT = '/'  # Must be set at class level
        PREFERRED_URL_SCHEME = 'http'
        SERVER_NAME = 'localhost'
        PORT_CONFIG = []
    
    # Create Flask app manually to ensure config is properly loaded
    # Get the absolute path to the src directory where templates are located
    src_dir = Path(__file__).parent.parent / "src"
    app = Flask(__name__, 
                template_folder=str(src_dir / "templates"),
                static_folder=str(src_dir / "static"))
    app.config.from_object(TestConfig)
    
    # Ensure required directories exist
    from pathlib import Path
    app_root = Path(__file__).parent.parent
    (app_root / "logs").mkdir(exist_ok=True)
    (app_root / "src" / "data").mkdir(exist_ok=True)
    (app_root / "src" / "templates").mkdir(exist_ok=True)
    (app_root / "src" / "static").mkdir(exist_ok=True)
    
    # Initialize logging
    setup_logging(app)
    
    # Initialize extensions (database, cache, etc.)
    init_extensions(app)
    
    # Load model integration data first (before services need it)
    with app.app_context():
        try:
            load_model_integration_data(app)
            app.logger.info("Model integration data loaded successfully")
        except Exception as e:
            app.logger.error(f"Failed to load model integration data: {e}")
    
    # Initialize service manager and core services
    with app.app_context():
        try:
            from core_services import ServiceManager, ServiceInitializer
            # Create service manager
            service_manager = ServiceManager(app)
            app.config['service_manager'] = service_manager
            
            # Initialize core services (docker, scan manager, etc.)
            service_initializer = ServiceInitializer(app, service_manager)
            service_initializer.initialize_all()
            
            app.logger.info("Core services initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize services: {e}")
    
    # Register blueprints
    with app.app_context():
        try:
            from web_routes import register_blueprints
            register_blueprints(app)
            app.logger.info("All blueprints registered successfully")
        except Exception as e:
            app.logger.error(f"Failed to register blueprints: {e}")
    
    # Register template globals that are missing in test environment
    @app.template_global()
    def get_model_count():
        """Get total number of models in database."""
        try:
            from models import ModelCapability
            return ModelCapability.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def get_app_count():
        """Get total number of generated applications."""
        try:
            from models import GeneratedApplication
            return GeneratedApplication.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def get_running_container_count():
        """Get number of running containers."""
        return 0  # Mock for tests
    
    @app.template_global()
    def get_analysis_count():
        """Get number of completed analyses."""
        try:
            from models import SecurityAnalysis
            return SecurityAnalysis.query.count()
        except Exception:
            return 0
    
    # Debug print to verify config
    print(f"DEBUG: APPLICATION_ROOT = {app.config.get('APPLICATION_ROOT')}")
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture(scope='function')
def runner(app):
    """Create a test runner for the Flask application's Click commands."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def init_database(app):
    """Initialize database with fresh tables for each test."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db
        db.drop_all()


@pytest.fixture
def sample_model_capability():
    """Create a sample ModelCapability instance."""
    return ModelCapability(
        model_id='test-model-1',
        canonical_slug='test_model_1',
        provider='test_provider',
        model_name='Test Model 1',
        is_free=True,
        context_window=8192,
        max_output_tokens=4096,
        supports_function_calling=True,
        supports_vision=False,
        input_price_per_token=0.001,
        output_price_per_token=0.002,
        cost_efficiency=0.8,
        safety_score=0.9
    )


@pytest.fixture
def sample_port_configuration():
    """Create a sample PortConfiguration instance."""
    return PortConfiguration(
        frontend_port=9051,
        backend_port=6051,
        is_available=True
    )


@pytest.fixture
def sample_generated_application():
    """Create a sample GeneratedApplication instance."""
    return GeneratedApplication(
        model_slug='test_model_1',
        app_number=1,
        app_type='login_system',
        provider='test_provider',
        generation_status='completed',
        has_backend=True,
        has_frontend=True,
        has_docker_compose=True,
        backend_framework='Flask',
        frontend_framework='React'
    )


@pytest.fixture
def sample_security_analysis():
    """Create a sample SecurityAnalysis instance."""
    return SecurityAnalysis(
        status=AnalysisStatus.COMPLETED,
        bandit_enabled=True,
        safety_enabled=True,
        pylint_enabled=True,
        eslint_enabled=True,
        npm_audit_enabled=True,
        total_issues=5,
        critical_severity_count=1,
        high_severity_count=2,
        medium_severity_count=1,
        low_severity_count=1,
        analysis_duration=45.2
    )


@pytest.fixture
def sample_performance_test():
    """Create a sample PerformanceTest instance."""
    return PerformanceTest(
        status=AnalysisStatus.COMPLETED,
        test_type='load_test',
        target_users=10,
        duration_seconds=30,
        requests_per_second=150.5,
        average_response_time=200.3,
        error_rate_percent=0.5,
        cpu_usage_percent=45.2,
        memory_usage_mb=128.7
    )


@pytest.fixture
def sample_batch_analysis():
    """Create a sample BatchAnalysis instance."""
    import uuid
    return BatchAnalysis(
        id=str(uuid.uuid4()),
        name='Test Batch Analysis',
        analysis_type='security',
        status=AnalysisStatus.COMPLETED,
        total_applications=10,
        completed_applications=8,
        failed_applications=2,
        batch_duration=300.5
    )


@pytest.fixture
def populated_database(init_database, sample_model_capability, sample_port_configuration,
                      sample_generated_application, sample_security_analysis,
                      sample_performance_test, sample_batch_analysis):
    """Create a database populated with sample data."""
    # Add model capability
    db.session.add(sample_model_capability)
    db.session.commit()
    
    # Add port configuration
    db.session.add(sample_port_configuration)
    db.session.commit()
    
    # Add generated application
    db.session.add(sample_generated_application)
    db.session.commit()
    
    # Link security analysis to application
    sample_security_analysis.application_id = sample_generated_application.id
    db.session.add(sample_security_analysis)
    
    # Link performance test to application
    sample_performance_test.application_id = sample_generated_application.id
    db.session.add(sample_performance_test)
    
    # Add batch analysis
    db.session.add(sample_batch_analysis)
    
    db.session.commit()
    
    return {
        'model_capability': sample_model_capability,
        'port_configuration': sample_port_configuration,
        'generated_application': sample_generated_application,
        'security_analysis': sample_security_analysis,
        'performance_test': sample_performance_test,
        'batch_analysis': sample_batch_analysis
    }


@pytest.fixture
def mock_docker_manager():
    """Create a mock Docker manager."""
    mock = MagicMock()
    mock.get_container_status.return_value = {'backend': 'running', 'frontend': 'running'}
    mock.start_containers.return_value = {'success': True}
    mock.stop_containers.return_value = {'success': True}
    mock.restart_containers.return_value = {'success': True}
    mock.get_container_logs.return_value = {'backend': 'Backend logs...', 'frontend': 'Frontend logs...'}
    return mock


@pytest.fixture
def mock_scan_manager():
    """Create a mock scan manager."""
    mock = MagicMock()
    mock.start_scan.return_value = {'scan_id': 'test-scan-123', 'status': 'started'}
    mock.get_scan_status.return_value = {'status': 'completed', 'progress': 100}
    mock.get_scan_results.return_value = {
        'vulnerabilities': [
            {'severity': 'high', 'title': 'Test vulnerability', 'description': 'Test description'}
        ]
    }
    return mock


@pytest.fixture
def mock_service_manager(mock_docker_manager, mock_scan_manager):
    """Create a mock service manager with mocked services."""
    mock = MagicMock()
    mock.get_service.side_effect = lambda name: {
        'docker_manager': mock_docker_manager,
        'scan_manager': mock_scan_manager
    }.get(name)
    return mock


@pytest.fixture
def mock_performance_tester():
    """Create a mock performance tester."""
    mock = MagicMock()
    mock.run_performance_test.return_value = {
        'status': 'success',
        'summary': {
            'total_requests': 1000,
            'total_failures': 5,
            'avg_response_time': 250.5,
            'requests_per_sec': 33.3,
            'duration': 30.0
        }
    }
    mock.load_performance_results.return_value = None
    return mock


@pytest.fixture
def mock_security_analyzer():
    """Create a mock security analyzer."""
    mock = MagicMock()
    mock.analyze_application.return_value = {
        'status': 'completed',
        'results': {
            'bandit': {'issues': []},
            'safety': {'vulnerabilities': []},
            'pylint': {'score': 8.5}
        }
    }
    return mock


@pytest.fixture
def sample_port_config():
    """Create sample port configuration data."""
    return [
        {
            'model': 'test_model_1',
            'app_num': 1,
            'frontend_port': 9051,
            'backend_port': 6051
        },
        {
            'model': 'test_model_1',
            'app_num': 2,
            'frontend_port': 9053,
            'backend_port': 6053
        },
        {
            'model': 'test_model_2',
            'app_num': 1,
            'frontend_port': 9055,
            'backend_port': 6055
        }
    ]


@pytest.fixture
def temp_config_files():
    """Create temporary configuration files for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create model capabilities file
        model_capabilities = {
            'models': {
                'test-model-1': {
                    'provider': 'test_provider',
                    'name': 'Test Model 1',
                    'capabilities': ['text_generation', 'function_calling']
                }
            }
        }
        
        capabilities_file = temp_path / 'model_capabilities.json'
        with open(capabilities_file, 'w') as f:
            json.dump(model_capabilities, f)
        
        # Create port config file
        port_config = [
            {'model': 'test_model_1', 'app_num': 1, 'frontend_port': 9051, 'backend_port': 6051}
        ]
        
        port_file = temp_path / 'port_config.json'
        with open(port_file, 'w') as f:
            json.dump(port_config, f)
        
        # Create models summary file
        models_summary = {
            'models': [
                {'slug': 'test_model_1', 'name': 'Test Model 1', 'provider': 'test_provider'}
            ]
        }
        
        summary_file = temp_path / 'models_summary.json'
        with open(summary_file, 'w') as f:
            json.dump(models_summary, f)
        
        yield {
            'temp_dir': temp_path,
            'capabilities_file': capabilities_file,
            'port_file': port_file,
            'summary_file': summary_file
        }


@pytest.fixture(autouse=True)
def patch_services(app, mock_service_manager):
    """Automatically patch service manager for all tests."""
    with patch.object(app, 'config') as config_mock:
        config_mock.__getitem__.side_effect = lambda key: {
            'service_manager': mock_service_manager,
            'PORT_CONFIG': []
        }.get(key, app.config.get(key))
        # Store original config values to avoid recursion
        original_config = dict(app.config)
        config_mock.get.side_effect = lambda key, default=None: {
            'service_manager': mock_service_manager,
            'PORT_CONFIG': []
        }.get(key, original_config.get(key, default))
        yield


@pytest.fixture
def auth_headers():
    """Create authentication headers for API requests."""
    return {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }


@pytest.fixture
def htmx_headers():
    """Create HTMX request headers."""
    return {
        'HX-Request': 'true',
        'Content-Type': 'application/x-www-form-urlencoded'
    }


# Utility functions for testing
def assert_json_response(response, expected_status=200):
    """Assert that response is valid JSON with expected status."""
    assert response.status_code == expected_status
    assert response.content_type == 'application/json'
    return response.get_json()


def assert_htmx_response(response, expected_status=200):
    """Assert that response is valid HTMX response."""
    assert response.status_code == expected_status
    assert 'text/html' in response.content_type
    return response.get_data(as_text=True)


def create_test_user_with_roles(*roles):
    """Create a test user with specified roles (placeholder for future auth)."""
    # This is a placeholder for when authentication is implemented
    return {'username': 'testuser', 'roles': list(roles)}
