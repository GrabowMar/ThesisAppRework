"""
Pytest configuration for route tests
"""
import sys
from pathlib import Path
import pytest

# Add src directory to Python path
src_path = Path(__file__).parent.parent / 'src'
sys.path.insert(0, str(src_path))


@pytest.fixture(scope='function')
def app():
    """Create and configure a test Flask application."""
    from app.factory import create_app
    from app.extensions import db
    
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
