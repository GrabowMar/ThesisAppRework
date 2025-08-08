"""
Flask Application Factory
========================

Main application entry point that uses the new HTMX-based routes.
Integrates with database models and configuration from JSON files.
"""

import os
import json
import logging
import logging.handlers
import threading
import time
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple

# Suppress Locust monkey patching warnings during app startup
warnings.filterwarnings("ignore", message=".*MonkeyPatchWarning.*")
warnings.filterwarnings("ignore", message=".*Monkey-patching.*")

from flask import Flask, render_template, jsonify

# Import database components
try:
    # Try relative imports first (when run as module)
    from .extensions import init_extensions, db
    from .models import ModelCapability, PortConfiguration, GeneratedApplication
    from .core_services import AppConfig
    from .service_manager import ServiceManager
    from .constants import AppDefaults, Paths
except ImportError:
    # Fall back to absolute imports (when run as script)
    from extensions import init_extensions, db
    from models import ModelCapability, PortConfiguration, GeneratedApplication
    from core_services import AppConfig
    from service_manager import ServiceManager
    from constants import AppDefaults, Paths

class Config:
    """Application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    # Resolve absolute path for database
    app_dir = Path(__file__).parent
    data_dir = app_dir / 'data'
    data_dir.mkdir(exist_ok=True)
    db_path = data_dir / 'thesis_app.db'
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or f'sqlite:///{db_path.absolute()}'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQLite performance optimizations
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'check_same_thread': False,
            'timeout': 30,
            'isolation_level': None,
        }
    }
    
    APPLICATION_ROOT = '/'  # Fix for Flask test client
    PREFERRED_URL_SCHEME = 'http'


class DatabasePopulator:
    """Handles database population with proper error handling and retry logic."""
    
    def __init__(self, app: Flask) -> None:
        self.app: Flask = app
        self.logger: logging.Logger = app.logger
        self._lock: threading.Lock = threading.Lock()
        
    def populate_models_from_json(self, capabilities_data: Dict[str, Any]) -> int:
        """
        Populate ModelCapability table from JSON data.
        
        Args:
            capabilities_data: Dictionary containing model capabilities data
            
        Returns:
            Number of models created
        """
        with self._lock:
            try:
                models_data: Optional[Dict[str, Any]] = self._extract_models_data(capabilities_data)
                if not models_data:
                    self.logger.error("Could not find model data in JSON structure")
                    return 0
                
                models_created: int = 0
                errors: List[str] = []
                
                for model_id, model_data in models_data.items():
                    if not self._is_valid_model_data(model_data):
                        continue
                    
                    try:
                        if self._create_model_capability(model_id, model_data):
                            models_created += 1
                    except Exception as e:
                        errors.append(f"Model {model_id}: {str(e)}")
                        continue
                
                db.session.commit()
                
                if errors:
                    self.logger.warning(f"Errors during model population: {len(errors)} errors")
                    for error in errors[:5]:  # Log first 5 errors
                        self.logger.error(error)
                
                self.logger.info(f"Successfully populated {models_created} model capabilities")
                return models_created
                
            except Exception as e:
                self.logger.error(f"Error populating models from JSON: {e}")
                db.session.rollback()
                return 0
    
    def _extract_models_data(self, capabilities_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract actual models data from nested JSON structure."""
        models_data = capabilities_data.get('models', {})
        
        # Check different nested structures
        if isinstance(models_data, dict):
            # Direct model_id keys
            for key, value in models_data.items():
                if isinstance(value, dict) and value.get('model_id'):
                    return models_data
            
            # Try nested models
            for nested_key in ['models', 'data']:
                nested = models_data.get(nested_key, {})
                if isinstance(nested, dict):
                    for key, value in nested.items():
                        if isinstance(value, dict) and value.get('model_id'):
                            return nested
        
        return None
    
    def _is_valid_model_data(self, model_data: Any) -> bool:
        """Check if model data is valid."""
        return (isinstance(model_data, dict) and 
                model_data.get('model_id') is not None)
    
    def _create_model_capability(self, model_id: str, model_data: Dict[str, Any]) -> bool:
        """Create a ModelCapability record if it doesn't exist."""
        # Check if model already exists
        existing: Optional[ModelCapability] = ModelCapability.query.filter_by(
            model_id=model_data.get('model_id')
        ).first()
        
        if existing:
            return False
        
        # Create new model capability record
        # Note: Using the actual column names from the ModelCapability model
        model_capability: ModelCapability = ModelCapability()
        model_capability.model_id = model_data.get('model_id')
        model_capability.canonical_slug = model_data.get('canonical_slug', model_data.get('model_id'))
        model_capability.provider = model_data.get('provider', 'unknown')
        model_capability.model_name = model_data.get('model_name', model_data.get('model_id'))
        model_capability.is_free = model_data.get('is_free', False)
        model_capability.context_window = model_data.get('context_window', 0)
        model_capability.max_output_tokens = model_data.get('max_output_tokens', 0)
        model_capability.supports_function_calling = model_data.get('supports_function_calling', False)
        model_capability.supports_vision = model_data.get('supports_vision', False)
        model_capability.supports_streaming = model_data.get('supports_streaming', True)
        model_capability.supports_json_mode = model_data.get('supports_json_mode', False)
        model_capability.input_price_per_token = float(model_data.get('pricing', {}).get('prompt_tokens', 0) or 0)
        model_capability.output_price_per_token = float(model_data.get('pricing', {}).get('completion_tokens', 0) or 0)
        model_capability.cost_efficiency = model_data.get('performance_metrics', {}).get('cost_efficiency', 0.0)
        model_capability.safety_score = model_data.get('quality_metrics', {}).get('safety', 0.0)
        
        # Set JSON fields using setter methods if they exist
        if hasattr(model_capability, 'set_capabilities'):
            model_capability.set_capabilities(model_data.get('capabilities', {}))
        else:
            model_capability.capabilities_json = json.dumps(model_data.get('capabilities', {}))
            
        if hasattr(model_capability, 'set_metadata'):
            model_capability.set_metadata({
                'description': model_data.get('description', ''),
                'architecture': model_data.get('architecture', {}),
                'quality_metrics': model_data.get('quality_metrics', {}),
                'performance_metrics': model_data.get('performance_metrics', {}),
                'last_updated': model_data.get('last_updated', '')
            })
        else:
            model_capability.metadata_json = json.dumps({
                'description': model_data.get('description', ''),
                'architecture': model_data.get('architecture', {}),
                'quality_metrics': model_data.get('quality_metrics', {}),
                'performance_metrics': model_data.get('performance_metrics', {}),
                'last_updated': model_data.get('last_updated', '')
            })
        
        db.session.add(model_capability)
        return True
    
    def populate_ports_from_json(self, port_data: List[Dict[str, Any]]) -> int:
        """
        Populate PortConfiguration table from JSON data.
        
        Args:
            port_data: List of port configuration dictionaries
            
        Returns:
            Number of port configurations created
        """
        with self._lock:
            try:
                ports_created: int = 0
                batch_size: int = 100
                
                for i, port_entry in enumerate(port_data):
                    try:
                        if self._create_port_configuration(port_entry):
                            ports_created += 1
                        
                        # Commit in batches for performance
                        if ports_created % batch_size == 0:
                            db.session.commit()
                            
                    except Exception as e:
                        self.logger.error(f"Error processing port entry {i}: {e}")
                        continue
                
                db.session.commit()
                self.logger.info(f"Successfully populated {ports_created} port configurations")
                return ports_created
                
            except Exception as e:
                self.logger.error(f"Error populating ports from JSON: {e}")
                db.session.rollback()
                return 0
    
    def _create_port_configuration(self, port_entry: Dict[str, Any]) -> bool:
        """Create a PortConfiguration record if valid and doesn't exist."""
        frontend_port: Optional[int] = port_entry.get('frontend_port')
        backend_port: Optional[int] = port_entry.get('backend_port')
        
        if not frontend_port or not backend_port:
            return False
        
        # Check if port configuration already exists
        existing: Optional[PortConfiguration] = PortConfiguration.query.filter_by(
            model=port_entry.get('model_name', ''),
            app_num=port_entry.get('app_number', 0)
        ).first()
        
        if existing:
            return False
        
        # Create new port configuration using attribute assignment
        port_config: PortConfiguration = PortConfiguration()
        port_config.model = port_entry.get('model_name', '')
        port_config.app_num = port_entry.get('app_number', 0)
        port_config.frontend_port = frontend_port
        port_config.backend_port = backend_port
        port_config.is_available = True
        
        # Set metadata JSON field
        if hasattr(port_config, 'set_metadata'):
            port_config.set_metadata({
                'app_type': port_entry.get('app_type', ''),
                'source': 'initial_load'
            })
        else:
            port_config.metadata_json = json.dumps({
                'app_type': port_entry.get('app_type', ''),
                'source': 'initial_load'
            })
        
        db.session.add(port_config)
        return True


def setup_logging(app: Flask) -> None:
    """Initialize comprehensive application logging with improved structure."""
    # Use the centralized LoggingService from core_services
    try:
        from core_services import LoggingService
        LoggingService.setup(app)
        app.logger.info("Advanced logging system initialized")
        return
    except ImportError:
        app.logger.warning("LoggingService not available, using fallback logging setup")
    
    # Fallback logging setup
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Enhanced logging format with request correlation
    detailed_format = '%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s: %(message)s'
    simple_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Create context filter for request correlation
    class ContextFilter(logging.Filter):
        def filter(self, record):
            from flask import g, has_request_context
            record.request_id = getattr(g, 'request_id', '-') if has_request_context() else '-'
            record.component = record.name.split('.')[0] if '.' in record.name else record.name
            return True
    
    context_filter = ContextFilter()
    
    # Setup file handlers with rotation
    # Main application log
    app_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log", maxBytes=10*1024*1024, backupCount=10
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(logging.Formatter(detailed_format, date_format))
    app_handler.addFilter(context_filter)
    
    # Error-only log
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "errors.log", maxBytes=5*1024*1024, backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter(detailed_format, date_format))
    error_handler.addFilter(context_filter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(simple_format, date_format))
    console_handler.addFilter(context_filter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Configure werkzeug logger with filtering
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.setLevel(logging.INFO)
    werkzeug_logger.propagate = False
    
    # Request filter to reduce noise
    class RequestFilter(logging.Filter):
        EXCLUDED_PATHS = {'/api/status', '/static/', '/favicon.ico', '/health'}
        
        def filter(self, record):
            if record.name != 'werkzeug':
                return True
            
            try:
                if hasattr(record, 'args') and record.args and len(record.args) > 0:
                    args_list = list(record.args)
                    request_line = str(args_list[0]) if args_list else ""
                    parts = request_line.split()
                    if len(parts) >= 2:
                        path = parts[1]
                        if any(excluded in path for excluded in self.EXCLUDED_PATHS):
                            return False
            except Exception:
                pass
            return True
    
    request_handler = logging.handlers.RotatingFileHandler(
        log_dir / "requests.log", maxBytes=5*1024*1024, backupCount=3
    )
    request_handler.addFilter(RequestFilter())
    request_handler.setFormatter(logging.Formatter(simple_format, date_format))
    werkzeug_logger.addHandler(request_handler)
    
    # Setup request middleware for correlation IDs
    @app.before_request
    def before_request() -> None:
        from flask import g
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
    
    @app.after_request  
    def after_request(response: Any) -> Any:
        from flask import g
        if hasattr(g, 'start_time'):
            duration: float = (time.time() - g.start_time) * 1000
            app.logger.info(f"Request completed in {duration:.2f}ms - {response.status_code}")
        return response
    
    app.logger.info("Enhanced logging initialized with request correlation")


def load_model_integration_data(app: Flask) -> None:
    """Load model capabilities and port configurations from database with caching."""
    # Check if data is already loaded using app.config instead of custom attributes
    if app.config.get('_data_loaded', False):
        app.logger.info("Model integration data already loaded, skipping...")
        return
    
    try:
        integration_data: Dict[str, Any] = {}
        
        # Load data from database using ModelCapability and PortConfiguration models
        from models import ModelCapability, PortConfiguration
        
        with app.app_context():
            # Load model capabilities from database
            model_capabilities = ModelCapability.query.all()
            if model_capabilities:
                capabilities_data = {'models': {}}
                
                for model in model_capabilities:
                    capabilities_data['models'][model.model_id] = {
                        'provider': model.provider,
                        'context_window': model.context_window,
                        'max_output_tokens': model.max_output_tokens,
                        'supports_function_calling': model.supports_function_calling,
                        'supports_vision': model.supports_vision,
                        'supports_streaming': model.supports_streaming,
                        'supports_json_mode': model.supports_json_mode,
                        'input_price_per_token': model.input_price_per_token,
                        'output_price_per_token': model.output_price_per_token,
                        'is_free': model.is_free,
                        'cost_efficiency': model.cost_efficiency,
                        'safety_score': model.safety_score,
                        'capabilities': model.get_capabilities(),
                        'metadata': model.get_metadata()
                    }
                
                integration_data['CAPABILITIES_DATA'] = capabilities_data
                app.logger.info(f"Loaded capabilities for {len(model_capabilities)} models from database")
            else:
                app.logger.warning("No model capabilities found in database")
            
            # Load port configurations from database
            port_configs = PortConfiguration.query.all()
            if port_configs:
                port_data = []
                for config in port_configs:
                    port_data.append({
                        'model_name': config.model,
                        'app_number': config.app_num,
                        'backend_port': config.backend_port,
                        'frontend_port': config.frontend_port
                    })
                
                integration_data['PORT_CONFIG'] = port_data
                app.logger.info(f"Loaded {len(port_configs)} port configurations from database")
            else:
                app.logger.warning("No port configurations found in database")
                integration_data['PORT_CONFIG'] = []
            
            # Generate models summary from database data
            if model_capabilities:
                models_list = []
                providers_seen = set()
                
                for model in model_capabilities:
                    providers_seen.add(model.provider)
                    
                    # Generate color based on provider
                    color_map = {
                        'anthropic': '#FF6B6B',
                        'openai': '#4ECDC4', 
                        'google': '#45B7D1',
                        'deepseek': '#9333EA',
                        'mistralai': '#8B5CF6',
                        'cognitivecomputations': '#666666',
                        'featherless': '#F59E0B',
                        'minimax': '#EF4444',
                        'nvidia': '#0D9488',
                        'qwen': '#F43F5E'
                    }
                    color = color_map.get(model.provider, '#666666')
                    
                    models_list.append({
                        'name': model.model_id,
                        'color': color,
                        'provider': model.provider
                    })
                
                models_summary = {
                    'extraction_timestamp': datetime.now().isoformat(),
                    'total_models': len(models_list),
                    'apps_per_model': 30,
                    'models': models_list
                }
                
                integration_data['MODELS_SUMMARY'] = models_summary
                app.logger.info(f"Generated models summary with {len(models_list)} models from database")
            else:
                app.logger.warning("No models found for summary generation")
        
        # Apply the integration data
        app.config.update(integration_data)
        # Use app.config to track loading state
        app.config['_data_loaded'] = True
        
        app.logger.info("Model integration data loaded successfully from database")
        
    except Exception as e:
        app.logger.error(f"Failed to load model integration data from database: {e}")
        app.config['PORT_CONFIG'] = []
        raise
        
    except Exception as e:
        app.logger.error(f"Failed to load model integration data: {e}")
        app.config['PORT_CONFIG'] = []
        raise


def ensure_database_populated(app: Flask) -> None:
    """Ensure database is populated with data on first access."""
    with app.app_context():
        populator = DatabasePopulator(app)
        
        # Check if we need to populate models
        if not app.config.get('_capabilities_loaded', True):
            try:
                if ModelCapability.query.count() == 0:
                    capabilities_data = app.config.get('CAPABILITIES_DATA')
                    if capabilities_data:
                        app.logger.info("Populating database with model data...")
                        populator.populate_models_from_json(capabilities_data)
                app.config['_capabilities_loaded'] = True
            except Exception as e:
                app.logger.error(f"Failed to populate models: {e}")
        
        # Check if we need to populate ports
        if not app.config.get('_ports_loaded', True):
            try:
                if PortConfiguration.query.count() == 0:
                    port_data = app.config.get('PORT_CONFIG', [])
                    if port_data:
                        app.logger.info("Populating database with port configurations...")
                        populator.populate_ports_from_json(port_data)
                app.config['_ports_loaded'] = True
            except Exception as e:
                app.logger.error(f"Failed to populate ports: {e}")


def create_minimal_routes(app: Flask) -> None:
    """Create minimal fallback routes when blueprints fail to load."""
    @app.route('/')
    def index():
        return render_template('pages/error.html',
                             error="Application is running but blueprints failed to load. Check logs for import errors.",
                             error_code=500)
    
    @app.route('/api/status')
    def api_status():
        return jsonify({
            'status': 'degraded',
            'message': 'Blueprints failed to load',
            'services': {
                'database': 'connected' if db else 'disconnected',
                'docker': False,
                'container_batch_service': True
            }
        })


def register_template_globals(app: Flask) -> None:
    """Register template global functions."""
    from datetime import datetime, timezone
    
    @app.template_global()
    def get_app_config() -> Dict[str, Any]:
        """Make app config available in templates."""
        return app.config
    
    @app.template_global()
    def debug_mode() -> bool:
        """Check if app is in debug mode."""
        return app.debug
    
    @app.template_global()
    def get_model_count() -> int:
        """Get total number of models in database."""
        try:
            return ModelCapability.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def get_app_count() -> int:
        """Get total number of generated applications."""
        try:
            return GeneratedApplication.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def now() -> datetime:
        """Get current datetime for templates."""
        return datetime.now()
    
    @app.template_global()
    def utcnow() -> datetime:
        """Get current UTC datetime for templates."""
        return datetime.now(timezone.utc)


def register_error_handlers(app: Flask) -> None:
    """Register custom error handlers with HTMX support."""
    
    @app.errorhandler(404)
    def not_found(error: Any) -> Tuple[str, int]:
        from flask import request
        if request.headers.get('HX-Request'):
            try:
                return render_template('partials/error_message.html', 
                                     error="Page not found"), 404
            except Exception:
                return '<div class="alert error">Page not found</div>', 404
        try:
            return render_template('pages/error.html', 
                                 error="The requested page could not be found.",
                                 error_code=404), 404
        except Exception:
            return "404 - Page not found", 404
    
    @app.errorhandler(500)
    def internal_error(error: Any) -> Tuple[str, int]:
        from flask import request
        app.logger.error(f"Internal server error: {error}")
        if request.headers.get('HX-Request'):
            try:
                return render_template('partials/error_message.html', 
                                     error="Internal server error"), 500
            except Exception:
                return '<div class="alert error">Internal server error</div>', 500
        try:
            return render_template('pages/error.html', 
                                 error="An internal server error occurred.",
                                 error_code=500), 500
        except Exception:
            return "500 - Internal server error", 500


def create_app(config_name: Optional[str] = None) -> Flask:
    """
    Application factory pattern for creating Flask app instances.
    
    Args:
        config_name: Configuration name (development, production, etc.)
    
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load configuration
    if config_name:
        app.config.from_object(config_name)
    else:
        app.config.from_object(Config)
    
    # Set up AppConfig for services
    app_config = AppConfig()
    app.config['APP_CONFIG'] = app_config
    
    # Ensure required directories exist
    app_root = Path(__file__).parent.parent
    directories = [
        app_root / "logs",
        app_root / "src" / "data",
        app_root / "src" / "templates",
        app_root / "src" / "static"
    ]
    for directory in directories:
        directory.mkdir(exist_ok=True)
    
    # Initialize logging
    setup_logging(app)
    
    # Initialize extensions (database, cache, etc.)
    init_extensions(app)
    
    # Load model integration data
    with app.app_context():
        try:
            load_model_integration_data(app)
        except Exception as e:
            app.logger.error(f"Failed to load model integration data: {e}")
            # Continue with empty data
            app.config['PORT_CONFIG'] = []
    
    # Initialize service manager and core services
    with app.app_context():
        try:
            # Check if services are already initialized using app.config
            if app.config.get('_services_initialized', False):
                app.logger.info("Services already initialized, skipping...")
                return app
            
            # Create service manager  
            service_manager = ServiceManager(app)
            
            # Unified CLI analyzer provides batch operations and testing infrastructure
            app.logger.info("Unified CLI analyzer services available")
            
            # Use app.config to track initialization state
            app.config['_services_initialized'] = True
            app.logger.info("Core services initialized successfully")
            
        except Exception as e:
            app.logger.error(f"Failed to initialize core services: {e}")
            # Set up minimal fallback services - but keep the existing service_manager
            if 'service_manager' not in app.config:
                app.config['service_manager'] = ServiceManager(app)
            app.config['docker_manager'] = None
    
    # Register blueprints with HTMX routes
    try:
        try:
            from .web_routes import register_blueprints
        except (ImportError, ValueError):
            from web_routes import register_blueprints
        register_blueprints(app)
        app.logger.info("All blueprints registered successfully")
    except ImportError as e:
        app.logger.error(f"Failed to import blueprints from web_routes: {e}")
        # Create minimal fallback routes
        create_minimal_routes(app)
    except Exception as e:
        app.logger.error(f"Failed to register blueprints: {e}")
        create_minimal_routes(app)
    
    # Register template globals
    register_template_globals(app)
    
    # Add context processor for common template variables
    @app.context_processor
    def inject_template_vars() -> Dict[str, Union[str, bool]]:
        """Inject common variables into all templates."""
        return {
            'app_name': 'Thesis Research App',
            'app_version': '2.0.0-htmx',
            'htmx_enabled': True
        }
    
    # Register error handlers
    register_error_handlers(app)
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Simple health check endpoint."""
        return jsonify({
            'status': 'healthy',
            'service': 'thesis-research-app',
            'version': '2.0.0-htmx',
            'database': 'connected' if db else 'disconnected',
            'services': {
                'unified_cli_analyzer': True,  # Always available via unified CLI analyzer
                'docker_manager': app.config.get('docker_manager') is not None,
                'service_manager': app.config.get('service_manager') is not None
            }
        })
    
    app.logger.info("Flask application created successfully with HTMX routes")
    return app


def main() -> int:
    """Main entry point for running the application."""
    # Create the application
    app = create_app()
    
    # Get configuration from environment
    host: str = os.getenv('FLASK_HOST', '127.0.0.1')
    port: int = int(os.getenv('FLASK_PORT', '5000'))
    debug: bool = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Print a cleaner application banner
    print(f"""
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃            Thesis Research App 2.0              ┃
    ┃                HTMX Edition                     ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    
    🚀 Server running at: http://{host}:{port}
    🔧 Mode: {'Development' if debug else 'Production'}
    ⚡ Features: HTMX Integration, Docker Manager, Batch Processing
    
    📊 Available Tools:
       • Security Analysis & Scanning
       • Performance Testing
       • AI Model Integration
       • Docker Container Management
    
    💡 {'Auto-reload enabled' if debug else 'Running in optimized mode'}
    """)
    
    try:
        # Run the application with optimized settings
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True,
            use_reloader=debug  # Only use reloader in debug mode
        )
    except KeyboardInterrupt:
        print("\n\n👋 Application stopped by user")
        print("Docker connection refreshed on restart")
        return 0
    except Exception as e:
        print(f"\n❌ Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


def create_test_app() -> Flask:
    """
    Create a Flask app specifically configured for testing.
    
    This function provides a clean way to create test instances
    that are compatible with pytest fixtures.
    
    Returns:
        Flask application instance configured for testing
    """
    from pathlib import Path
    
    class TestConfig(Config):
        TESTING = True
        SECRET_KEY = 'test-secret-key-that-is-long-enough-to-be-secure-for-testing'
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        APPLICATION_ROOT = '/'
        PREFERRED_URL_SCHEME = 'http'
        SERVER_NAME = 'localhost'
        PORT_CONFIG: List[Dict[str, Any]] = []
    
    # Create Flask app manually to ensure config is properly loaded
    src_dir: Path = Path(__file__).parent
    app: Flask = Flask(__name__, 
                template_folder=str(src_dir / "templates"),
                static_folder=str(src_dir / "static"))
    app.config.from_object(TestConfig)
    
    # Explicitly ensure required config for Flask 3.x compatibility
    app.config.update({
        'APPLICATION_ROOT': '/',
        'TESTING': True,
        'SERVER_NAME': 'localhost',
        'PREFERRED_URL_SCHEME': 'http',
        'SECRET_KEY': 'test-secret-key-that-is-long-enough-to-be-secure-for-testing',
        'WTF_CSRF_ENABLED': False
    })
    
    # Set up AppConfig for services
    app_config: AppConfig = AppConfig()
    app.config['APP_CONFIG'] = app_config
    
    # Initialize logging (minimal for tests)
    setup_logging(app)
    
    # Initialize extensions
    init_extensions(app)
    
    # Load minimal test data
    app.config['PORT_CONFIG'] = []
    app.config['CAPABILITIES_DATA'] = {}
    app.config['MODELS_SUMMARY'] = {}
    
    # Register template globals for tests
    register_template_globals(app)
    
    return app


if __name__ == '__main__':
    exit(main())
