"""
Flask Extensions Configuration

This module initializes Flask extensions used throughout the application.
Extensions are created here and then initialized in the app factory.
"""

from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import requests
import logging
from typing import Optional

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()

class AppComponents:
    """Centralized component manager for Flask app."""
    
    def __init__(self):
        self.celery = None
        self.task_manager = None
        self.analyzer_integration = None
        self.background_service = None
    
    def init_app(self, app: Flask):
        """Initialize components with Flask app."""
        app.extensions['app_components'] = self
    
    def set_celery(self, celery):
        """Set Celery instance."""
        self.celery = celery
    
    def set_task_manager(self, task_manager):
        """Set task manager instance."""
        self.task_manager = task_manager
    
    def set_analyzer_integration(self, analyzer_integration):
        """Set analyzer integration instance."""
        self.analyzer_integration = analyzer_integration
    
    def set_background_service(self, background_service):
        """Set background service instance."""
        self.background_service = background_service

def get_components() -> Optional[AppComponents]:
    """Get components from current Flask app."""
    return current_app.extensions.get('app_components')

def get_celery():
    """Get Celery instance from app components."""
    components = get_components()
    return components.celery if components else None

def get_task_manager():
    """Get task manager from app components."""
    components = get_components()
    return components.task_manager if components else None

def get_analyzer_integration():
    """Get analyzer integration from app components."""
    components = get_components()
    return components.analyzer_integration if components else None

def get_background_service():
    """Get background service from app components."""
    components = get_components()
    return components.background_service if components else None

# Configure requests for containerized services
requests_session = requests.Session()
# Note: timeout should be set per request, not on session

def init_extensions(app):
    """Initialize Flask extensions with the app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize app components
    components = AppComponents()
    components.init_app(app)
    
    # Configure logging for containerized services communication
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Set up testing services configuration
    app.config.setdefault('TESTING_SERVICES_BASE_URL', 'http://localhost:8000')
    app.config.setdefault('TESTING_SERVICES_TIMEOUT', 300)
    app.config.setdefault('TESTING_SERVICES_ENABLED', True)
    
    app.logger.info("Extensions initialized with containerized testing services support")
    
    return components

def get_session():
    """Get database session context manager."""
    class SessionManager:
        def __enter__(self):
            return db.session
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                db.session.rollback()
            else:
                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()
                    raise

    return SessionManager()

def init_db():
    """Initialize database tables."""
    db.create_all()
