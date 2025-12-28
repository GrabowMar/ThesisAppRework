import sys
from pathlib import Path

# Ensure the application package under src/ is importable when running tests
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import pytest
import os
from app.factory import create_app
from app.extensions import db as _db

@pytest.fixture(scope='session')
def app():
    """Create application for the tests."""
    # Set testing environment variables
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'true'
    os.environ['ANALYZER_AUTO_START'] = 'false'
    os.environ['MAINTENANCE_AUTO_START'] = 'false'
    os.environ['WEBSOCKET_SERVICE'] = 'mock'
    
    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'ANALYZER_AUTO_START': False,
        'MAINTENANCE_AUTO_START': False
    })

    # Create tables
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture(scope='function')
def client(app):
    """Create a test client."""
    return app.test_client()

@pytest.fixture(scope='function')
def db_session(app):
    """Create a fresh database session for a test."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()
        
        options = dict(bind=connection, binds={})
        session = _db.create_scoped_session(options=options)
        _db.session = session

        yield session

        transaction.rollback()
        connection.close()
        session.remove()
