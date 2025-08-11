"""
Flask Extensions Configuration

This module initializes Flask extensions used throughout the application.
Extensions are created here and then initialized in the app factory.
"""

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import requests
import logging

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

# Configure requests for containerized services
requests_session = requests.Session()
# Note: timeout should be set per request, not on session

def init_extensions(app):
    """Initialize Flask extensions with the app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Configure logging for containerized services communication
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Set up testing services configuration
    app.config.setdefault('TESTING_SERVICES_BASE_URL', 'http://localhost:8000')
    app.config.setdefault('TESTING_SERVICES_TIMEOUT', 300)
    app.config.setdefault('TESTING_SERVICES_ENABLED', True)
    
    # Initialize security settings
    app.config.setdefault('WTF_CSRF_ENABLED', True)
    app.config.setdefault('WTF_CSRF_TIME_LIMIT', 3600)  # 1 hour
    app.config.setdefault('WTF_CSRF_SSL_STRICT', not app.debug)
    
    app.logger.info("Extensions initialized with containerized testing services support")


def get_session():
    """Get database session with proper error handling."""
    return db.session
