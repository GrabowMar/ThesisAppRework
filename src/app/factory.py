"""
Flask Application Factory
=========================

Factory pattern for creating Flask application instances with
Celery integration and proper initialization.
"""

import os
import logging
from typing import Optional

from flask import Flask
from celery import Celery
from sqlalchemy import text

# Import extensions and configurations
from config.celery_config import CeleryConfig
from app.extensions import db, init_extensions, get_components
from app.services.task_manager import TaskManager
from app.services.analyzer_integration import get_analyzer_integration as create_analyzer_integration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def create_celery(app: Optional[Flask] = None) -> Celery:
    """
    Create and configure Celery instance.
    
    Args:
        app: Flask application instance
        
    Returns:
        Configured Celery instance
    """
    
    celery = Celery(
        app.import_name if app else 'thesis_app',
        backend=CeleryConfig.result_backend,
        broker=CeleryConfig.broker_url,
        include=['app.tasks']
    )
    
    # Apply configuration
    celery.config_from_object(CeleryConfig)
    
    if app:
        # Configure Celery to work with Flask app context
        class ContextTask(celery.Task):
            """Make celery tasks work with Flask app context."""
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)
        
        celery.Task = ContextTask
        
        # Note: Celery instance is managed by components, not direct app attribute
    
    return celery

def create_app(config_name: str = 'default') -> Flask:
    """
    Create and configure Flask application.
    
    Args:
        config_name: Configuration environment name
        
    Returns:
        Configured Flask application
    """
    
    # Set template and static folders relative to src directory
    import os
    src_dir = os.path.dirname(os.path.dirname(__file__))  # Get src directory
    template_folder = os.path.join(src_dir, 'templates')
    static_folder = os.path.join(src_dir, 'static')
    
    app = Flask(__name__, 
                template_folder=template_folder,
                static_folder=static_folder)
    
    # Configuration
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Database path in data folder
    default_db_path = f'sqlite:///{os.path.join(data_dir, "thesis_app.db")}'
    
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', default_db_path),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        
        # Celery configuration
        CELERY_BROKER_URL=CeleryConfig.broker_url,
        CELERY_RESULT_BACKEND=CeleryConfig.result_backend,
        
        # Task configuration
        TASK_TIMEOUT=int(os.environ.get('TASK_TIMEOUT', '1800')),  # 30 minutes
        MAX_CONCURRENT_TASKS=int(os.environ.get('MAX_CONCURRENT_TASKS', '5')),
        
        # Analyzer configuration
        ANALYZER_ENABLED=os.environ.get('ANALYZER_ENABLED', 'true').lower() == 'true',
        ANALYZER_AUTO_START=os.environ.get('ANALYZER_AUTO_START', 'false').lower() == 'true',
    )
    
    # Initialize extensions and get components manager
    components = init_extensions(app)
    
    # Create Celery instance
    celery = create_celery(app)
    components.set_celery(celery)
    
    # Initialize database with app context
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
    
    # Register blueprints
    from app.routes import register_blueprints
    register_blueprints(app)
    
    # Initialize services
    try:
        # Initialize service locator with all core services
        from app.services.service_locator import ServiceLocator
        ServiceLocator.initialize(app)
        logger.info("Service locator initialized with core services")
        
        # Initialize task manager
        task_manager = TaskManager()
        components.set_task_manager(task_manager)
        logger.info("Task manager initialized")
        
        # Initialize background service
        from app.services.background_service import BackgroundTaskService
        background_service = BackgroundTaskService()
        components.set_background_service(background_service)
        logger.info("Background task service initialized")
        
        # Initialize analyzer integration
        analyzer_integration = create_analyzer_integration()
        components.set_analyzer_integration(analyzer_integration)
        logger.info("Analyzer integration initialized")
        
        # Auto-start analyzer services if configured
        if app.config['ANALYZER_AUTO_START'] and analyzer_integration:
            logger.info("Auto-starting analyzer services...")
            if hasattr(analyzer_integration, 'start_analyzer_services'):
                if analyzer_integration.start_analyzer_services():
                    logger.info("Analyzer services started successfully")
                else:
                    logger.warning("Failed to auto-start analyzer services")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"Internal server error: {error}")
        return {'error': 'Internal server error'}, 500
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Application health check endpoint."""
        try:
            # Check database connection
            db.session.execute(text('SELECT 1'))
            db_status = 'healthy'
        except Exception:
            db_status = 'unhealthy'
        
        # Check Celery connection (soft requirement in tests)
        try:
            components = get_components()
            celery_instance = components.celery if components else None
            if celery_instance:
                try:
                    celery_inspect = celery_instance.control.inspect()
                    active_tasks = celery_inspect.active()
                    # If broker not reachable, treat as unavailable (not unhealthy)
                    celery_status = 'healthy' if active_tasks is not None else 'unavailable'
                except Exception:
                    celery_status = 'unavailable'
            else:
                celery_status = 'unavailable'
        except Exception:
            celery_status = 'unavailable'
        
        # Check analyzer services
        try:
            components = get_components()
            analyzer_integration = components.analyzer_integration if components else None
            if analyzer_integration and hasattr(analyzer_integration, 'health_check'):
                analyzer_health = analyzer_integration.health_check()
                analyzer_status = analyzer_health.get('status', 'available') or 'available'
            else:
                analyzer_status = 'unavailable'
        except Exception:
            analyzer_status = 'unavailable'
        
        # Overall status policy:
        # - Database must be healthy.
        # - Optional components (celery, analyzer) may be 'unavailable' without forcing degraded.
        core_healthy = (db_status == 'healthy')
        # Optional components only degrade if explicitly 'unhealthy'
        optional_problem = any(s == 'unhealthy' for s in [celery_status, analyzer_status])
        if core_healthy and not optional_problem:
            overall_status = 'healthy'
        else:
            overall_status = 'degraded'
        
        # Get timestamp from task manager
        try:
            components = get_components()
            task_manager = components.task_manager if components else None
            timestamp = task_manager.get_current_time().isoformat() if task_manager and hasattr(task_manager, 'get_current_time') else None
        except Exception:
            from datetime import datetime, timezone
            timestamp = datetime.now(timezone.utc).isoformat()
        
        return {
            'status': overall_status,
            'components': {
                'database': db_status,
                'celery': celery_status,
                'analyzer': analyzer_status
            },
            'timestamp': timestamp
        }
    
    logger.info(f"Flask application created successfully with config: {config_name}")
    
    return app

def create_cli_app() -> Flask:
    """
    Create Flask app for CLI usage (without web routes).
    
    Returns:
        Flask app configured for CLI operations
    """
    
    app = Flask(__name__)
    
    # Create data directory if it doesn't exist
    data_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Database path in data folder
    default_db_path = f'sqlite:///{os.path.join(data_dir, "thesis_app.db")}'
    
    # Minimal configuration for CLI
    app.config.update(
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', default_db_path),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    
    # Initialize database only
    db.init_app(app)
    
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database initialized for CLI")
        except Exception as e:
            logger.error(f"Failed to initialize database for CLI: {e}")
    
    return app

# Global instances for import convenience
celery_app = None
flask_app = None

def get_celery_app() -> Celery:
    """Get global Celery application instance."""
    global celery_app
    if celery_app is None:
        celery_app = create_celery()
    return celery_app

def get_flask_app() -> Flask:
    """Get global Flask application instance."""
    global flask_app
    if flask_app is None:
        flask_app = create_app()
    return flask_app
