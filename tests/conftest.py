"""
Test Configuration and Shared Fixtures
=====================================

Central conftest.py providing modern pytest fixtures for the ThesisAppRework project.
Uses best practices for Flask testing, database isolation, and analyzer integration.
"""

import os
import sys
import tempfile
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

# Add src to Python path for imports
src_dir = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_dir))

# Test-specific environment configuration
os.environ.update({
    'FLASK_ENV': 'testing',
    'TESTING': 'true',
    'DATABASE_URL': 'sqlite:///:memory:',
    'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    'SECRET_KEY': 'test-secret-key-not-for-production',
    'CELERY_TASK_ALWAYS_EAGER': 'true',
    'CELERY_TASK_EAGER_PROPAGATES': 'true',
    'ANALYZER_ENABLED': 'false',
    'ANALYZER_AUTO_START': 'false',
    'LOG_LEVEL': 'WARNING',  # Reduce noise in tests
    'WEBSOCKET_SERVICE': 'mock',  # Use mock service in tests
    'WEBSOCKET_STRICT_CELERY': 'false',
})


@pytest.fixture(scope='session')
def app_config():
    """
    Session-scoped configuration for test app.
    
    Returns test-optimized configuration dictionary.
    """
    return {
        'TESTING': True,
        'DEBUG': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'CELERY_TASK_ALWAYS_EAGER': True,
        'CELERY_TASK_EAGER_PROPAGATES': True,
        'ANALYZER_ENABLED': False,
        'ANALYZER_AUTO_START': False,
        'WEBSOCKET_SERVICE': 'mock',
        'WEBSOCKET_STRICT_CELERY': False,
        'TEMPLATES_AUTO_RELOAD': False,  # Disable in tests for speed
        'SERVER_NAME': 'localhost.localdomain',  # For url_for() in tests
    }


@pytest.fixture(scope='session')
def app(app_config):
    """
    Session-scoped Flask application fixture.
    
    Creates a single app instance for the entire test session to improve performance.
    Uses in-memory SQLite database that's recreated for each test function.
    """
    from app.factory import create_app
    
    # Create app with test configuration
    test_app = create_app('testing')
    test_app.config.update(app_config)
    
    # Create application context
    ctx = test_app.app_context()
    ctx.push()
    
    yield test_app
    
    # Cleanup
    ctx.pop()


@pytest.fixture
def client(app):
    """
    Test client fixture for making HTTP requests.
    
    Provides Flask test client with application context.
    Function-scoped for test isolation.
    """
    return app.test_client()


@pytest.fixture
def runner(app):
    """
    CLI runner fixture for testing Click commands.
    
    Provides Flask CLI test runner.
    """
    return app.test_cli_runner()


@pytest.fixture
def db_session(app):
    """
    Database session fixture with automatic rollback.
    
    Creates fresh database tables for each test and automatically
    rolls back changes to ensure test isolation.
    """
    from app.extensions import db
    
    # Create all tables
    db.create_all()
    
    # Begin a transaction
    connection = db.engine.connect()
    transaction = connection.begin()
    
    # Configure session to use transaction
    session = db.session
    session.configure(bind=connection, binds={})
    
    yield session
    
    # Rollback transaction and close connection
    transaction.rollback()
    connection.close()
    
    # Drop all tables for clean slate
    db.drop_all()


@pytest.fixture
def auth_headers():
    """
    Authentication headers for API tests.
    
    Returns headers with API key or token for authenticated requests.
    """
    return {
        'Authorization': 'Bearer test-token',
        'Content-Type': 'application/json'
    }


@pytest.fixture
def sample_model_data():
    """
    Sample model data for tests.
    
    Returns dictionary with sample model information.
    """
    return {
        'name': 'test-model',
        'provider': 'openai',
        'model_id': 'gpt-4',
        'capabilities': ['text-generation', 'code-completion'],
        'parameters': {
            'max_tokens': 4000,
            'temperature': 0.7
        }
    }


@pytest.fixture
def sample_application_data():
    """
    Sample application data for tests.
    
    Returns dictionary with sample generated application information.
    """
    return {
        'name': 'test-app',
        'description': 'A test application',
        'model': 'gpt-4',
        'requirements': ['flask', 'sqlalchemy'],
        'features': ['authentication', 'database'],
        'status': 'generated'
    }


@pytest.fixture
def mock_celery_task():
    """
    Mock Celery task fixture.
    
    Provides a mock task for testing async operations.
    """
    mock_task = Mock()
    mock_task.id = 'test-task-id'
    mock_task.state = 'SUCCESS'
    mock_task.result = {'status': 'completed'}
    mock_task.info = {}
    
    return mock_task


@pytest.fixture
def mock_analyzer_service():
    """
    Mock analyzer service fixture.
    
    Provides a mock analyzer service for testing without external dependencies.
    """
    mock_service = Mock()
    mock_service.health_check.return_value = {'status': 'healthy'}
    mock_service.analyze_code.return_value = {
        'issues': [],
        'summary': {'total_issues': 0},
        'status': 'completed'
    }
    mock_service.get_analysis_status.return_value = 'completed'
    
    return mock_service


@pytest.fixture
def analyzer_message_factory():
    """
    Factory for creating analyzer WebSocket messages.
    
    Returns a function that creates properly formatted analyzer messages.
    """
    def _create_message(message_type, data=None, correlation_id=None):
        from analyzer.shared.protocol import WebSocketMessage, MessageType
        
        return WebSocketMessage(
            type=MessageType(message_type),
            data=data or {},
            correlation_id=correlation_id or 'test-correlation-id'
        )
    
    return _create_message


@pytest.fixture
def temp_directory():
    """
    Temporary directory fixture.
    
    Creates a temporary directory for file-based tests.
    Automatically cleaned up after test completion.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_file_system():
    """
    Mock file system fixture.
    
    Mocks file system operations for testing without actual file I/O.
    """
    with patch('os.path.exists') as mock_exists, \
         patch('os.makedirs') as mock_makedirs, \
         patch('builtins.open') as mock_open:
        
        mock_exists.return_value = True
        mock_makedirs.return_value = None
        mock_open.return_value.__enter__.return_value.read.return_value = 'mock file content'
        
        yield {
            'exists': mock_exists,
            'makedirs': mock_makedirs,
            'open': mock_open
        }


@pytest.fixture
def websocket_mock():
    """
    WebSocket mock fixture.
    
    Provides a mock WebSocket connection for testing real-time features.
    """
    mock_ws = Mock()
    mock_ws.send = Mock()
    mock_ws.recv = Mock(return_value='{"type": "response", "data": {}}')
    mock_ws.close = Mock()
    
    return mock_ws


@pytest.fixture(autouse=True)
def reset_singletons():
    """
    Reset singleton instances between tests.
    
    Automatically runs before each test to ensure clean state.
    """
    # Reset any singleton instances that might persist between tests
    try:
        from app.services.service_locator import ServiceLocator
        # Use setattr to avoid lint errors about unknown attributes
        if hasattr(ServiceLocator, '_instance'):
            setattr(ServiceLocator, '_instance', None)
        if hasattr(ServiceLocator, '_initialized'):
            setattr(ServiceLocator, '_initialized', False)
    except (ImportError, AttributeError):
        # Gracefully handle if ServiceLocator doesn't exist or doesn't have these attributes
        pass


@pytest.fixture
def capture_logs():
    """
    Log capture fixture.
    
    Captures log output during tests for assertion.
    """
    import logging
    from io import StringIO
    
    log_capture_handler = logging.StreamHandler(StringIO())
    logger = logging.getLogger()
    logger.addHandler(log_capture_handler)
    
    yield log_capture_handler.stream
    
    logger.removeHandler(log_capture_handler)


# Test utilities
def assert_json_response(response, expected_status=200, expected_keys=None):
    """
    Assert that response is valid JSON with expected status and keys.
    
    Args:
        response: Flask test response object
        expected_status: Expected HTTP status code
        expected_keys: List of keys that should be present in JSON response
    """
    assert response.status_code == expected_status
    assert response.content_type == 'application/json'
    
    json_data = response.get_json()
    assert json_data is not None
    
    if expected_keys:
        for key in expected_keys:
            assert key in json_data
    
    return json_data


def create_test_model_capability(db_session, **kwargs):
    """
    Create a test model capability in the database.
    
    Args:
        db_session: Database session fixture
        **kwargs: Model attributes
    
    Returns:
        Created model object
    """
    from app.models import ModelCapability
    
    model_data = {
        'model_name': 'test-model',
        'provider': 'openai',
        'model_id': 'gpt-4',
        'canonical_slug': 'gpt-4',
        **kwargs
    }
    
    model = ModelCapability(**model_data)
    db_session.add(model)
    db_session.commit()
    
    return model


def create_test_generated_application(db_session, **kwargs):
    """
    Create a test generated application in the database.
    
    Args:
        db_session: Database session fixture
        **kwargs: Application attributes
    
    Returns:
        Created application object
    """
    from app.models import GeneratedApplication
    from app.constants import AnalysisStatus
    
    app_data = {
        'model_slug': 'test-model',
        'app_number': 1,
        'app_type': 'web',
        'provider': 'openai',
        'generation_status': AnalysisStatus.COMPLETED,
        'has_backend': True,
        'has_frontend': True,
        **kwargs
    }
    
    app = GeneratedApplication(**app_data)
    db_session.add(app)
    db_session.commit()
    
    return app


# Pytest hooks for better test reporting
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "analyzer: mark test as analyzer-related")
    config.addinivalue_line("markers", "db: mark test as requiring database")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "api: mark test as API test")
    config.addinivalue_line("markers", "websocket: mark test as WebSocket test")
    config.addinivalue_line("markers", "smoke: mark test as smoke test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test location."""
    for item in items:
        # Add markers based on test path
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        
        # Add markers based on test name patterns
        if "test_db" in item.name or "database" in item.name:
            item.add_marker(pytest.mark.db)
        if "test_api" in item.name or "endpoint" in item.name:
            item.add_marker(pytest.mark.api)
        if "websocket" in item.name or "ws_" in item.name:
            item.add_marker(pytest.mark.websocket)
        if "analyzer" in item.name:
            item.add_marker(pytest.mark.analyzer)


# Skip tests requiring external services if not available
def pytest_runtest_setup(item):
    """Setup hook to skip tests based on markers and environment."""
    # Skip analyzer tests if analyzer is disabled
    if item.get_closest_marker("analyzer"):
        if os.getenv('ANALYZER_ENABLED', 'false').lower() != 'true':
            pytest.skip("Analyzer tests require ANALYZER_ENABLED=true")
    
    # Skip slow tests if SKIP_SLOW is set
    if item.get_closest_marker("slow"):
        if os.getenv('SKIP_SLOW', 'false').lower() == 'true':
            pytest.skip("Slow tests skipped (SKIP_SLOW=true)")