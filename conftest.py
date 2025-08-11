"""
Pytest Configuration
====================

Configuration and fixtures for the test suite.
"""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Setup path for imports
_src_dir = Path(__file__).parent / "src"
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    # Import here to avoid issues
    from app.factory import create_app
    from app.extensions import db as _db
    
    # Create a temporary file for the test database
    db_fd, db_path = tempfile.mkstemp()
    
    # Create app with test configuration
    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'ANALYZER_ENABLED': False,  # Disable analyzer for tests
        'ANALYZER_AUTO_START': False,
    })
    
    # Create application context
    with app.app_context():
        _db.create_all()
        yield app
        
    # Cleanup
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')  
def runner(app):
    """Create CLI test runner."""
    return app.test_cli_runner()


@pytest.fixture(scope='function')
def clean_db(app):
    """Provide a clean database for each test."""
    from app.extensions import db
    
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield db
        db.session.rollback()


@pytest.fixture
def sample_model_data():
    """Sample model capability data for testing."""
    return {
        'model_id': 'test-model-id',
        'canonical_slug': 'test_provider_test-model',
        'model_name': 'Test Model',
        'provider': 'test_provider',
        'context_window': 4096,
        'max_output_tokens': 2048,
        'supports_function_calling': True,
        'supports_vision': False,
        'input_price_per_token': 0.0001,
        'output_price_per_token': 0.0002
    }


@pytest.fixture
def sample_application_data():
    """Sample generated application data for testing."""
    return {
        'model_slug': 'test_provider_test-model',
        'app_number': 1,
        'provider': 'test_provider',
        'app_type': 'web_app',
        'description': 'Test application',
        'has_backend': True,
        'has_frontend': True,
        'backend_port': 8001,
        'frontend_port': 3001
    }


@pytest.fixture
def sample_batch_data():
    """Sample batch analysis data for testing."""
    return {
        'name': 'Test Batch Analysis',
        'description': 'Test batch for pytest',
        'analysis_types': ['security', 'performance'],
        'models': ['test_provider_test-model'],
        'apps': [1, 2, 3],
        'priority': 'medium'
    }
