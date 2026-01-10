import sys
from pathlib import Path

# Ensure the application package under src/ is importable when running tests
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / 'src'
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

import pytest
import os
import uuid
import tempfile
from app.factory import create_app
from app.extensions import db as _db


@pytest.fixture(scope='session')
def isolation_id():
    """Generate unique isolation ID for this test session.

    This ID is used to isolate:
    - Container names and ports
    - Redis keys and databases
    - File system paths
    - Database instances

    The isolation prevents conflicts when running tests in parallel.
    """
    test_id = str(uuid.uuid4())[:8]  # Short ID like "a3f2b1c4"
    os.environ['ANALYSIS_ISOLATION_ID'] = test_id
    yield test_id
    # Cleanup
    os.environ.pop('ANALYSIS_ISOLATION_ID', None)


@pytest.fixture(scope='session')
def app(isolation_id):
    """Create application for the tests with isolated database."""
    # Set testing environment variables
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'true'
    os.environ['ANALYZER_AUTO_START'] = 'false'
    os.environ['MAINTENANCE_AUTO_START'] = 'false'
    os.environ['WEBSOCKET_SERVICE'] = 'mock'

    # Create temporary database file per test session for isolation
    temp_dir = Path(tempfile.gettempdir()) / 'thesis_tests' / isolation_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    db_path = temp_dir / 'test_db.sqlite'

    app = create_app('testing')
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}',
        'WTF_CSRF_ENABLED': False,
        'ANALYZER_AUTO_START': False,
        'MAINTENANCE_AUTO_START': False
    })

    # Create tables
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

    # Cleanup temp database
    try:
        if db_path.exists():
            db_path.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()
    except Exception:
        pass  # Best effort cleanup

@pytest.fixture(scope='function')
def client(app):
    """Create a test client."""
    return app.test_client()

@pytest.fixture(scope='function')
def isolated_app(app, isolation_id):
    """Provide app with isolation context for the test.

    This fixture ensures the Flask 'g' object has the isolation_id
    for any test that needs isolation-aware behavior.
    """
    with app.app_context():
        # Set isolation context for this test
        from flask import g
        g.isolation_id = isolation_id
        yield app


@pytest.fixture(scope='function')
def db_session(app, isolation_id):
    """Create a fresh database session for a test with isolation."""
    with app.app_context():
        connection = _db.engine.connect()
        transaction = connection.begin()

        # Bind session to isolated transaction
        options = dict(bind=connection, binds={})
        session = _db.create_scoped_session(options=options)
        _db.session = session

        yield session

        # Rollback and cleanup
        transaction.rollback()
        connection.close()
        session.remove()
