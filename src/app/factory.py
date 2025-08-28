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
# Lazy import analyzer integration only if enabled to reduce startup coupling
try:
    from app.services.analyzer_integration import get_analyzer_integration as create_analyzer_integration  # type: ignore
except Exception:  # pragma: no cover - optional
    def create_analyzer_integration():
        return None  # fallback noop

# Import logging from utils
from app.utils.logging_config import get_logger
logger = get_logger('factory')

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

    # Attach legacy template mapping loader so Jinja {% include %} statements using
    # pre-restructure paths resolve automatically. This must occur immediately
    # after app creation so subsequent blueprint registration uses the wrapped loader.
    try:  # pragma: no cover - simple wiring
        from app.utils.template_paths import attach_legacy_mapping_loader
        attach_legacy_mapping_loader(app)
    except Exception as _loader_err:  # pragma: no cover
        logger.warning(f"Legacy template mapping loader not attached: {_loader_err}")

    # Note: No /dist static route to avoid dependency on repo-level 'dist' folder
    
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
        # Ensure templates are always reloaded to avoid stale caches in tests/dev
        TEMPLATES_AUTO_RELOAD=True,
        
        # Celery configuration
        CELERY_BROKER_URL=CeleryConfig.broker_url,
        CELERY_RESULT_BACKEND=CeleryConfig.result_backend,
        
        # Task configuration
        TASK_TIMEOUT=int(os.environ.get('TASK_TIMEOUT', '1800')),  # 30 minutes
        MAX_CONCURRENT_TASKS=int(os.environ.get('MAX_CONCURRENT_TASKS', '5')),
        
        # Analyzer configuration
        ANALYZER_ENABLED=os.environ.get('ANALYZER_ENABLED', 'true').lower() == 'true',
        ANALYZER_AUTO_START=os.environ.get('ANALYZER_AUTO_START', 'false').lower() == 'true',

    # Websocket strict mode: when true, do NOT fall back to mock service if Celery-backed init fails
    WEBSOCKET_STRICT_CELERY=os.environ.get('WEBSOCKET_STRICT_CELERY', 'false').lower() == 'true',
    )
    
    # Ensure Jinja picks up template changes without restarting the app
    try:
        app.jinja_env.auto_reload = True
        # Register useful Jinja globals and filters
        try:
            from app.utils.helpers import make_safe_dom_id as _make_safe_dom_id, format_datetime, now
            app.jinja_env.globals['make_safe_dom_id'] = _make_safe_dom_id
            app.jinja_env.globals['now'] = now
            app.jinja_env.filters['datetime'] = format_datetime
        except Exception as _reg_err:
            logger.warning(f"Could not register Jinja globals/filters: {_reg_err}")
    except Exception:
        pass

    # In test runs, aggressively clear Jinja template bytecode/cache to avoid stale templates
    try:
        import os as _os
        if _os.environ.get('PYTEST_CURRENT_TEST') or app.config.get('TESTING'):
            # Clear cache dict if present
            cache_obj = getattr(app.jinja_env, 'cache', None)
            if cache_obj is not None and hasattr(cache_obj, 'clear'):
                cache_obj.clear()
    except Exception:
        # Best-effort only; ignore any issues here
        pass

    # Initialize extensions and get components manager
    components = init_extensions(app)
    
    # Create Celery instance
    celery = create_celery(app)
    components.set_celery(celery)
    
    # Initialize database with app context
    with app.app_context():
        try:
            # Ensure models are imported before creating tables so SQLAlchemy
            # is aware of all model metadata (avoids 'no such table' errors)
            try:
                import app.models as _models  # noqa: F401
            except Exception as _imp_err:
                logger.warning(f"Could not import app.models before DB init: {_imp_err}")
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
        
        # Initialize task manager (defer import to avoid circulars during module import)
        from app.services.task_manager import TaskManager  # local import to break cycles
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

        # Initialize WebSocket/Celery bridge service
        try:
            # Always prefer the Celery-backed service unless explicitly forced to mock.
            from app.extensions import SOCKETIO_AVAILABLE, socketio
            strict_mode = app.config.get('WEBSOCKET_STRICT_CELERY', False)
            service_pref = os.environ.get('WEBSOCKET_SERVICE', 'auto').lower()
            # In strict mode, treat as explicit celery preference
            if strict_mode:
                service_pref = 'celery'
            app.config['WEBSOCKET_SERVICE_PREFERENCE'] = service_pref

            def _init_celery_ws():
                from app.services.celery_websocket_service import initialize_celery_websocket_service
                sio = socketio if (SOCKETIO_AVAILABLE and socketio) else None
                websocket_service_local = initialize_celery_websocket_service(sio)
                components.set_websocket_service(websocket_service_local)
                logger.info("WebSocket service active: celery_websocket (SocketIO=%s)", bool(sio))

            def _init_mock_ws():
                from app.services.mock_websocket_service import initialize_mock_websocket_service
                websocket_service_local = initialize_mock_websocket_service()
                components.set_websocket_service(websocket_service_local)
                logger.info("WebSocket service active: mock_websocket (forced=%s)", service_pref == 'mock')

            if service_pref == 'mock' and not strict_mode:
                _init_mock_ws()
            else:
                try:
                    _init_celery_ws()
                except Exception as ce:
                    if strict_mode or service_pref == 'celery':
                        logger.error(
                            "Celery-backed WebSocket service init failed and strict/celery mode is enabled; "
                            "mock fallback disabled. Error: %s", ce
                        )
                        raise
                    logger.warning("Celery-backed WebSocket service init failed, falling back to mock: %s", ce)
                    _init_mock_ws()

            # Sanity check in strict mode: ensure active service is celery_websocket
            if strict_mode:
                ws = components.websocket_service
                status = ws.get_status() if ws and hasattr(ws, 'get_status') else {}
                active_service = status.get('service') if isinstance(status, dict) else None
                if active_service != 'celery_websocket':
                    raise RuntimeError(f"Strict mode requires celery_websocket, got: {active_service}")

        except Exception as e:
            logger.error(f"Failed to initialize WebSocket service: {e}")
            # In strict mode, do not swallow the error
            if app.config.get('WEBSOCKET_STRICT_CELERY', False):
                raise
        
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
        # In strict mode, abort app creation when WS service selection fails
        if app.config.get('WEBSOCKET_STRICT_CELERY', False):
            raise
    
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
            if app.config.get('TESTING', False):
                # During tests, skip Celery broker calls to avoid warnings/noise
                celery_status = 'unavailable'
            else:
                components = get_components()
                celery_instance = components.celery if components else None
                if celery_instance:
                    import warnings
                    try:
                        # Filter duplicate nodename warnings that can occur if multiple nodes share the same name
                        from celery.app.control import DuplicateNodenameWarning  # type: ignore
                    except Exception:
                        DuplicateNodenameWarning = None  # type: ignore

                    try:
                        with warnings.catch_warnings():
                            if DuplicateNodenameWarning:
                                warnings.simplefilter("ignore", DuplicateNodenameWarning)  # type: ignore
                            else:
                                warnings.simplefilter("ignore")
                            # A lightweight reachability check: any ping reply implies broker/worker reachable
                            ping_result = celery_instance.control.inspect().ping()
                        celery_status = 'healthy' if ping_result else 'unavailable'
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

    # Log disabled analysis models (environment-driven gating) for operator visibility
    try:  # pragma: no cover - simple logging utility
        _disabled_env = os.getenv('DISABLED_ANALYSIS_MODELS', '')
        _disabled_set = {m.strip() for m in _disabled_env.split(',') if m.strip()}
        if _disabled_set:
            logger.warning(
                "Analysis tasks DISABLED for models: %s (set via DISABLED_ANALYSIS_MODELS)",
                ", ".join(sorted(_disabled_set))
            )
        else:
            logger.info("No models disabled for analysis (DISABLED_ANALYSIS_MODELS empty)")
    except Exception as _log_err:  # pragma: no cover
        logger.debug(f"Could not log disabled models: {_log_err}")

    # Inject current_app (and optionally config flags) into Jinja for templates that were
    # previously referencing it implicitly. This prevents UndefinedError in lean test mode.
    @app.context_processor  # type: ignore[misc]
    def inject_current_app():  # pragma: no cover - simple
        from flask import current_app as _ca
        return {
            'current_app': _ca,
            'FEATURES': {
                'codegen': False,  # flag retained for templates to feature-gate UI elements
                'batch_jobs': False,
            }
        }
    
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
            # Ensure models are imported before creating tables
            try:
                import app.models as _models  # noqa: F401
            except Exception as _imp_err:
                logger.warning(f"Could not import app.models before CLI DB init: {_imp_err}")
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
