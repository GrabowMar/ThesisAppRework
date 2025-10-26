"""
Flask Application Factory
=========================

Factory pattern for creating Flask application instances with
Celery integration and proper initialization.
"""

import os
import logging
from pathlib import Path
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
    
    # Prefer Flask app configuration when available; fallback to CeleryConfig
    _backend = None
    _broker = None
    if app is not None:
        try:
            _backend = app.config.get('CELERY_RESULT_BACKEND', None)
            _broker = app.config.get('CELERY_BROKER_URL', None)
        except Exception:
            _backend = None
            _broker = None
    celery = Celery(
        app.import_name if app else 'thesis_app',
        backend=_backend or CeleryConfig.result_backend,
        broker=_broker or CeleryConfig.broker_url,
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
    
    # Load .env early (if python-dotenv installed) so OPENROUTER_API_KEY & LOG_LEVEL present
    try:  # pragma: no cover - lightweight
        from dotenv import load_dotenv  # type: ignore
        # Look for .env in project root (parent of src directory)
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / '.env'
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"Loaded .env from {env_path}")
        else:
            logger.warning(f".env not found at {env_path}")
    except Exception as e:
        logger.warning(f"Failed to load .env with dotenv: {e}")
        # Fallback: very small .env loader (KEY=VALUE per line, ignores comments)
        try:
            project_root = Path(__file__).parent.parent.parent
            env_path = project_root / '.env'
            if env_path.exists():
                for line in env_path.read_text(encoding='utf-8').splitlines():
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        k, v = line.split('=', 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        # Do not overwrite existing explicit environment values
                        if k and (k not in os.environ):
                            os.environ[k] = v
                logger.info(f"Loaded .env manually from {env_path}")
        except Exception as e2:
            logger.warning(f"Failed to load .env manually: {e2}")

    # Apply LOG_LEVEL early
    _lvl = os.getenv('LOG_LEVEL')
    if _lvl:
        try:
            logging.getLogger().setLevel(getattr(logging, _lvl.upper(), logging.INFO))
        except Exception:  # pragma: no cover
            pass

    # Set template and static folders relative to src directory
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
    # Use the same path structure as settings.py: src/data/
    src_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(src_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Database path in data folder (consistent with settings.py)
    default_db_path = f'sqlite:///{os.path.join(data_dir, "thesis_app.db")}'
    
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', default_db_path),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # Ensure templates are always reloaded to avoid stale caches in tests/dev
        TEMPLATES_AUTO_RELOAD=True,
        
        # Session configuration
        SESSION_COOKIE_SECURE=os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        PERMANENT_SESSION_LIFETIME=int(os.environ.get('SESSION_LIFETIME', '86400')),  # 24 hours
        
        # Authentication configuration
        REGISTRATION_ENABLED=os.environ.get('REGISTRATION_ENABLED', 'false').lower() == 'true',
        
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

    # Surface OpenRouter key in app config if present (without logging)
    try:  # pragma: no cover - simple wiring
        _ork = os.getenv('OPENROUTER_API_KEY')
        if _ork and not app.config.get('OPENROUTER_API_KEY'):
            app.config['OPENROUTER_API_KEY'] = _ork
    except Exception:
        pass

    # Normalize Redis configuration early: if REDIS_URL missing but host/port present, synthesize it
    try:  # pragma: no cover - configuration wiring
        if not os.environ.get('REDIS_URL'):
            _r_host = os.environ.get('REDIS_HOST')
            _r_port = os.environ.get('REDIS_PORT')
            if _r_host and _r_port:
                _constructed = f"redis://{_r_host}:{_r_port}/0"
                os.environ['REDIS_URL'] = _constructed
                # Mark that REDIS_URL was synthesized from host/port, not an explicit URL
                os.environ['REDIS_URL_SYNTHETIC'] = '1'
        # Propagate to app config if still missing
        if not app.config.get('REDIS_URL') and os.environ.get('REDIS_URL'):
            app.config['REDIS_URL'] = os.environ['REDIS_URL']
            if os.environ.get('REDIS_URL_SYNTHETIC'):
                app.config['REDIS_URL_SYNTHETIC'] = True
        # Ensure Celery URLs align when using Redis
        if str(app.config.get('CELERY_BROKER_URL', '')).startswith('redis') is False and os.environ.get('REDIS_URL'):
            app.config['CELERY_BROKER_URL'] = os.environ['REDIS_URL']
        if str(app.config.get('CELERY_RESULT_BACKEND', '')).startswith('redis') is False and os.environ.get('REDIS_URL'):
            app.config['CELERY_RESULT_BACKEND'] = os.environ['REDIS_URL']
    except Exception:
        pass
    
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
    
    # Register custom Jinja filters
    from datetime import datetime, timezone
    
    def timeago_filter(dt):
        """Convert datetime to human-readable relative time."""
        if not dt:
            return 'Never'
        
        if not isinstance(dt, datetime):
            return str(dt)
            
        # Ensure timezone awareness
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
            
        now = datetime.now(timezone.utc)
        diff = now - dt
        
        seconds = diff.total_seconds()
        
        if seconds < 60:
            return 'just now'
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f'{minutes} minute{"s" if minutes != 1 else ""} ago'
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f'{hours} hour{"s" if hours != 1 else ""} ago'
        elif seconds < 2592000:  # 30 days
            days = int(seconds // 86400)
            return f'{days} day{"s" if days != 1 else ""} ago'
        elif seconds < 31536000:  # 365 days
            months = int(seconds // 2592000)
            return f'{months} month{"s" if months != 1 else ""} ago'
        else:
            years = int(seconds // 31536000)
            return f'{years} year{"s" if years != 1 else ""} ago'
    
    app.jinja_env.filters['timeago'] = timeago_filter
    
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
        from app.services.task_service import AnalysisTaskService as TaskManager  # local import to break cycles
        task_manager = TaskManager()
        components.set_task_manager(task_manager)
        logger.info("Task manager initialized")
        
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

        # Initialize lightweight in-process task execution to advance AnalysisTask
        # objects from pending -> running -> completed for development and tests.
        try:  # pragma: no cover - wiring
            from app.services.task_execution_service import init_task_execution_service
            init_task_execution_service(app=app)
            logger.info("Task execution service initialized")
        except Exception as _exec_err:  # pragma: no cover
            logger.warning(f"Task execution service not started: {_exec_err}")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        # In strict mode, abort app creation when WS service selection fails
        if app.config.get('WEBSOCKET_STRICT_CELERY', False):
            raise
    
    # Register rich error handlers (HTML + JSON negotiation)
    try:  # pragma: no cover - simple wiring
        from app.errors import register_error_handlers
        register_error_handlers(app)
    except Exception as _err_reg:
        logger.warning(f"Custom error handlers not registered: {_err_reg}")

    # Request / Response logging middleware (after error handlers so request_id is present)
    try:  # pragma: no cover - wiring
        import time
        from flask import request, g

        @app.before_request  # type: ignore[misc]
        def _req_start_timer():
            g._req_start = time.perf_counter()

        @app.after_request  # type: ignore[misc]
        def _log_response(resp):
            try:
                duration_ms = None
                if hasattr(g, '_req_start'):
                    duration_ms = (time.perf_counter() - g._req_start) * 1000.0
                req_id = getattr(g, 'request_id', None)
                size = resp.calculate_content_length() or len(resp.get_data() or b'')
                logger.info(
                    "request", extra={
                        'event': 'http_request',
                        'request_id': req_id,
                        'method': request.method,
                        'path': request.path,
                        'status': resp.status_code,
                        'duration_ms': round(duration_ms, 2) if duration_ms is not None else None,
                        'size': size,
                        'content_type': resp.content_type,
                    }
                )
            except Exception as _log_err:  # pragma: no cover
                logger.debug(f"Request logging failed: {_log_err}")
            return resp
    except Exception as _mw_err:  # pragma: no cover
        logger.warning(f"Request logging middleware not active: {_mw_err}")
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Application health check endpoint."""
        from app.services.service_locator import ServiceLocator
        health_service = ServiceLocator.get_health_service()
        
        if not health_service:
            return {
                "status": "unhealthy",
                "message": "HealthService not available"
            }, 500

        health_status = health_service.check_all()
        
        # Determine overall status
        is_healthy = all(
            component["status"] == "healthy"
            for component in health_status.values()
        )
        
        overall_status = "healthy" if is_healthy else "degraded"
        
        # If database is down, the whole system is unhealthy
        if health_status.get("database", {}).get("status") != "healthy":
            overall_status = "unhealthy"

        return {
            'status': overall_status,
            'components': health_status,
            'timestamp': datetime.now(timezone.utc).isoformat()
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
    # Use the same path structure as settings.py: src/data/
    src_dir = os.path.dirname(os.path.dirname(__file__))
    data_dir = os.path.join(src_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # Database path in data folder (consistent with settings.py)
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
