"""
Flask Extensions Configuration

This module initializes Flask extensions used throughout the application.
Extensions are created here and then initialized in the app factory.
"""

from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
import requests
import logging
from typing import Optional

# Initialize extensions
db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# SocketIO placeholder - will be initialized if available
socketio = None
try:
    from flask_socketio import SocketIO
    # Use threading async mode for Windows compatibility and to avoid eventlet/gevent dependency
    socketio = SocketIO(cors_allowed_origins="*", async_mode='threading', logger=False, engineio_logger=False)
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False

class AppComponents:
    """Centralized component manager for Flask app."""
    
    def __init__(self):
        self.task_manager = None
        self.analyzer_integration = None
        self.websocket_service = None
    
    def init_app(self, app: Flask):
        """Initialize components with Flask app."""
        app.extensions['app_components'] = self
    
    def set_task_manager(self, task_manager):
        """Set task manager instance."""
        self.task_manager = task_manager
    
    def set_analyzer_integration(self, analyzer_integration):
        """Set analyzer integration instance."""
        self.analyzer_integration = analyzer_integration
    
    def set_websocket_service(self, websocket_service):
        """Set WebSocket service instance."""
        self.websocket_service = websocket_service

def get_components() -> Optional[AppComponents]:
    """Get components from current Flask app."""
    return current_app.extensions.get('app_components')

def get_task_manager():
    """Get task manager from app components."""
    components = get_components()
    return components.task_manager if components else None

def get_analyzer_integration():
    """Get analyzer integration from app components."""
    components = get_components()
    return components.analyzer_integration if components else None

def get_websocket_service():
    """Get WebSocket service from app components."""
    components = get_components()
    svc = components.websocket_service if components else None
    # Use mock service only
    try:
        if not components:
            return None

        # If no service initialized, create mock service
        if svc is None:
            from .extensions import SOCKETIO_AVAILABLE, socketio as _sio  # self-import safe inside function
            from app.services.mock_websocket_service import MockWebSocketService
            sio = _sio if (SOCKETIO_AVAILABLE and _sio) else None
            try:
                new_svc = MockWebSocketService(sio)
                components.set_websocket_service(new_svc)
                return new_svc
            except Exception:
                # Return None if we can't create service
                return None
    except Exception:
        # Best-effort enforcement; if anything fails, return what we have
        pass
    return svc

# Configure requests for containerized services
requests_session = requests.Session()
# Note: timeout should be set per request, not on session

def init_extensions(app):
    """Initialize Flask extensions with the app instance."""
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Load user by ID for Flask-Login."""
        from app.models import User
        return User.query.get(int(user_id))
    
    @login_manager.request_loader
    def load_user_from_request(request):
        """Load user from API token in Authorization header."""
        from app.models import User
        
        # Check for Authorization header with Bearer token
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.replace('Bearer ', '', 1)
            user = User.verify_api_token(token)
            if user:
                return user
        
        # Check for token in query parameter (less secure, but convenient)
        token = request.args.get('token')
        if token:
            user = User.verify_api_token(token)
            if user:
                return user
        
        return None
    
    @login_manager.unauthorized_handler
    def unauthorized():
        """Handle unauthorized access attempts."""
        from flask import flash, redirect, url_for, request, jsonify
        
        # If this is an API request (JSON or has Authorization header), return JSON
        if request.is_json or request.headers.get('Authorization'):
            return jsonify({'error': 'Unauthorized', 'message': 'Authentication required'}), 401
        
        # Otherwise, redirect to login page
        flash('Please log in to access this page.', 'info')
        # Preserve the original URL the user tried to access
        return redirect(url_for('auth.login', next=request.url))
    
    # Initialize SocketIO if available
    if SOCKETIO_AVAILABLE and socketio:
        try:
            # Already created with async_mode; just bind to app
            socketio.init_app(app)
            app.logger.info("SocketIO initialized successfully")
        except Exception as e:
            app.logger.warning(f"Failed to initialize SocketIO: {e}")
    else:
        app.logger.info("SocketIO not available - running without real-time features")
    
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
    """Get database session context manager that guarantees a Flask app context.

    This is safe to use from both request handlers (where an app/request context
    already exists) and background workers (Celery) where there may be no app
    context. When no app context is active, we create one using the app factory
    and tear it down on exit.
    """

    class SessionManager:
        def __init__(self):
            self._ctx = None  # Flask app context to pop on exit when we pushed it

        def __enter__(self):
            # Always push a dedicated app context for DB work to ensure scoped session binding
            try:
                from app.factory import get_flask_app as _get_flask_app
                app = _get_flask_app()
                self._ctx = app.app_context()
                self._ctx.push()
            except Exception as e:  # Best-effort: leave _ctx as None and let db.session fail if needed
                import logging
                logging.getLogger(__name__).warning(f"get_session could not push app context: {e}")
            return db.session

        def __exit__(self, exc_type, exc_val, exc_tb):
            try:
                if exc_type:
                    db.session.rollback()
                else:
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        raise
            finally:
                # Pop app context we created, if any
                if self._ctx is not None:
                    try:
                        self._ctx.pop()
                    except Exception:
                        pass

    return SessionManager()

def init_db():
    """Initialize database tables."""
    try:
        # Models should already be imported by factory.py, so no need to re-import here
        db.create_all()
    except Exception:
        # Re-raise so callers can log details
        raise


def deep_merge_dicts(base: dict, update: dict) -> dict:
    """Recursively merge update dict into base dict."""
    result = base.copy()

    for key, value in update.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def dicts_to_csv(data: list[dict], filename: Optional[str] = None) -> str:
    """Convert list of dictionaries to CSV string."""
    if not data:
        return ""

    import io
    import csv

    # Get all unique keys from all dictionaries
    fieldnames = set()
    for item in data:
        if isinstance(item, dict):
            fieldnames.update(item.keys())

    fieldnames = sorted(fieldnames)

    # Create CSV string
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for item in data:
        if isinstance(item, dict):
            writer.writerow(item)

    return output.getvalue()
