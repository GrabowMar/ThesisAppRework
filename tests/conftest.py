"""
Configuration for pytest
"""

import os
import sys
import tempfile
import warnings
from pathlib import Path
import pytest

# Ensure src/ is on sys.path for test imports
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Also ensure PYTHONPATH env var includes src for subprocesses / plugin imports
_pp = os.environ.get('PYTHONPATH', '')
if str(SRC) not in _pp.split(os.pathsep):
    os.environ['PYTHONPATH'] = f"{str(SRC)}{os.pathsep}{_pp}" if _pp else str(SRC)

try:
    listing = [p.name for p in list(SRC.iterdir())[:10]]
except Exception:
    listing = []
print('DEBUG SRC path:', SRC)
print('DEBUG SRC exists:', SRC.exists(), 'entries:', listing)

print('DEBUG sys.path first entries:', sys.path[:5])  # temporary debug

from app import create_app  # noqa: E402
from app.models import db  # noqa: E402


@pytest.fixture
def app():
    """Create application for testing."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()

    # Suppress noisy Celery duplicate node name warnings in test output
    warnings.filterwarnings(
        "ignore",
        category=Warning,
        message=r"Received multiple replies from node name: worker@"
    )
    
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': f'sqlite:///{db_path}'
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
    
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test runner."""
    return app.test_cli_runner()
