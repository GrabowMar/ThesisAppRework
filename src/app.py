"""
Flask Application Factory
========================

Main application entry point that uses the new HTMX-based routes.
Integrates with database models and configuration from JSON files.
"""

import os
import json
import logging
from pathlib import Path

from flask import Flask

# Import database components
from extensions import init_extensions, db
from models import ModelCapability, PortConfiguration, GeneratedApplication

# Import service management components
from core_services import ServiceManager, ServiceInitializer


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


def setup_logging(app):
    """Initialize application logging."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.FileHandler(log_dir / "thesis_app.log"),
            logging.StreamHandler()
        ]
    )
    
    app.logger.setLevel(logging.INFO)
    app.logger.info("Logging initialized")


def load_model_integration_data(app):
    """Load model capabilities and port configurations from JSON files."""
    project_root = Path(__file__).parent.parent
    misc_dir = project_root / "misc"
    
    try:
        integration_data = {}
        
        # Load model capabilities with lazy initialization
        capabilities_file = misc_dir / "model_capabilities.json"
        if capabilities_file.exists():
            with open(capabilities_file) as f:
                capabilities_data = json.load(f)
                models_count = len(capabilities_data.get('models', {}))
                app.logger.info(f"Loaded capabilities for {models_count} models")
                integration_data['CAPABILITIES_DATA'] = capabilities_data
                
                # Defer database population to first access
                integration_data['_capabilities_loaded'] = False
        else:
            app.logger.warning(f"Model capabilities file not found: {capabilities_file}")
        
        # Load port configurations with lazy initialization
        port_file = misc_dir / "port_config.json"
        if port_file.exists():
            with open(port_file) as f:
                port_data = json.load(f)
                integration_data['PORT_CONFIG'] = port_data
                app.logger.info(f"Loaded {len(port_data)} port configurations")
                
                # Defer database population to first access
                integration_data['_ports_loaded'] = False
        else:
            app.logger.warning(f"Port config file not found: {port_file}")
            integration_data['PORT_CONFIG'] = []
        
        # Load models summary (lightweight)
        models_file = misc_dir / "models_summary.json"
        if models_file.exists():
            with open(models_file) as f:
                models_data = json.load(f)
                models_count = len(models_data.get('models', []))
                integration_data['MODELS_SUMMARY'] = models_data
                app.logger.info(f"Loaded models summary with {models_count} models")
        else:
            app.logger.warning(f"Models summary file not found: {models_file}")
            
        # Apply the integration data
        app.config.update(integration_data)
        
        app.logger.info("Model integration data loaded successfully")
            
    except Exception as e:
        app.logger.error(f"Failed to load model integration data: {e}")
        app.config['PORT_CONFIG'] = []


def ensure_database_populated(app):
    """Ensure database is populated with data on first access."""
    with app.app_context():
        from models import ModelCapability, PortConfiguration
        
        # Check if we need to populate models
        if not getattr(app.config, '_capabilities_loaded', True):
            if ModelCapability.query.count() == 0:
                capabilities_data = app.config.get('CAPABILITIES_DATA')
                if capabilities_data:
                    app.logger.info("Populating database with model data...")
                    populate_models_from_json(app, capabilities_data)
            app.config['_capabilities_loaded'] = True
        
        # Check if we need to populate ports
        if not getattr(app.config, '_ports_loaded', True):
            if PortConfiguration.query.count() == 0:
                port_data = app.config.get('PORT_CONFIG', [])
                if port_data:
                    app.logger.info("Populating database with port configurations...")
                    populate_ports_from_json(app, port_data)
            app.config['_ports_loaded'] = True


def populate_models_from_json(app, capabilities_data):
    """Populate ModelCapability table from JSON data."""
    from models import ModelCapability
    from extensions import db
    
    try:
        # Navigate the nested JSON structure
        models_data = capabilities_data.get('models', {})
        
        # Try different structures - sometimes it's nested
        actual_models = None
        if isinstance(models_data, dict):
            # Check if this level contains model_id keys directly
            for key, value in models_data.items():
                if isinstance(value, dict) and value.get('model_id'):
                    actual_models = models_data
                    break
                # Check if it's another nested structure
                elif key == 'models' or (isinstance(value, dict) and 'models' in value):
                    continue
            
            # If not found at this level, try nested models
            if not actual_models:
                nested = models_data.get('models', {})
                if isinstance(nested, dict):
                    for key, value in nested.items():
                        if isinstance(value, dict) and value.get('model_id'):
                            actual_models = nested
                            break
                        elif key == 'models':
                            deeper_nested = nested.get('models', {})
                            if isinstance(deeper_nested, dict):
                                actual_models = deeper_nested
                                break
        
        if not actual_models:
            app.logger.error("Could not find model data in JSON structure")
            return
        
        models_created = 0
        for model_id, model_data in actual_models.items():
            if not isinstance(model_data, dict) or not model_data.get('model_id'):
                continue
                
            try:
                # Check if model already exists
                existing = ModelCapability.query.filter_by(
                    model_id=model_data.get('model_id')
                ).first()
                
                if existing:
                    continue
                
                # Create new model capability record
                model_capability = ModelCapability(
                    model_id=model_data.get('model_id'),
                    canonical_slug=model_data.get('canonical_slug', model_data.get('model_id')),
                    provider=model_data.get('provider', 'unknown'),
                    model_name=model_data.get('model_name', model_data.get('model_id')),
                    is_free=model_data.get('is_free', False),
                    context_window=model_data.get('context_window', 0),
                    max_output_tokens=model_data.get('max_output_tokens', 0),
                    supports_function_calling=model_data.get('supports_function_calling', False),
                    supports_vision=model_data.get('supports_vision', False),
                    supports_streaming=model_data.get('supports_streaming', True),
                    supports_json_mode=model_data.get('supports_json_mode', False),
                    input_price_per_token=float(model_data.get('pricing', {}).get('prompt_tokens', 0) or 0),
                    output_price_per_token=float(model_data.get('pricing', {}).get('completion_tokens', 0) or 0),
                    cost_efficiency=model_data.get('performance_metrics', {}).get('cost_efficiency', 0.0),
                    safety_score=model_data.get('quality_metrics', {}).get('safety', 0.0),
                    capabilities_json=json.dumps(model_data.get('capabilities', {})),
                    metadata_json=json.dumps({
                        'description': model_data.get('description', ''),
                        'architecture': model_data.get('architecture', {}),
                        'quality_metrics': model_data.get('quality_metrics', {}),
                        'performance_metrics': model_data.get('performance_metrics', {}),
                        'last_updated': model_data.get('last_updated', '')
                    })
                )
                
                db.session.add(model_capability)
                models_created += 1
                
            except Exception as e:
                app.logger.error(f"Error processing model {model_id}: {e}")
                continue
        
        db.session.commit()
        app.logger.info(f"Successfully populated {models_created} model capabilities")
        
    except Exception as e:
        app.logger.error(f"Error populating models from JSON: {e}")
        db.session.rollback()


def populate_ports_from_json(app, port_data):
    """Populate PortConfiguration table from JSON data."""
    from models import PortConfiguration
    from extensions import db
    
    try:
        ports_created = 0
        for i, port_entry in enumerate(port_data):
            try:
                frontend_port = port_entry.get('frontend_port')
                backend_port = port_entry.get('backend_port')
                
                if not frontend_port or not backend_port:
                    continue
                
                # Check if port configuration already exists
                existing = PortConfiguration.query.filter_by(
                    frontend_port=frontend_port
                ).first()
                
                if existing:
                    continue
                
                # Create new port configuration
                port_config = PortConfiguration(
                    frontend_port=frontend_port,
                    backend_port=backend_port,
                    is_available=True,
                    metadata_json=json.dumps({
                        'model_name': port_entry.get('model_name', ''),
                        'app_number': port_entry.get('app_number', 0),
                        'app_type': port_entry.get('app_type', ''),
                        'source': 'initial_load'
                    })
                )
                
                db.session.add(port_config)
                ports_created += 1
                
                if ports_created % 100 == 0:  # Commit in batches
                    db.session.commit()
                
            except Exception as e:
                app.logger.error(f"Error processing port entry {i}: {e}")
                continue
        
        db.session.commit()
        app.logger.info(f"Successfully populated {ports_created} port configurations")
        
    except Exception as e:
        app.logger.error(f"Error populating ports from JSON: {e}")
        db.session.rollback()


def create_app(config_name=None):
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
    
    # Ensure required directories exist
    app_root = Path(__file__).parent.parent
    (app_root / "logs").mkdir(exist_ok=True)
    (app_root / "src" / "data").mkdir(exist_ok=True)
    (app_root / "src" / "templates").mkdir(exist_ok=True)
    (app_root / "src" / "static").mkdir(exist_ok=True)
    
    # Initialize logging
    setup_logging(app)
    
    # Initialize extensions (database, cache, etc.)
    init_extensions(app)
    
    # Load model integration data first (before services need it)
    with app.app_context():
        try:
            load_model_integration_data(app)
            app.logger.info("Model integration data loaded successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize services: {e}")
    
    # Initialize service manager and core services with deferred loading
    with app.app_context():
        try:
            # Create service manager
            service_manager = ServiceManager(app)
            app.config['service_manager'] = service_manager
            
            # Initialize core services asynchronously (docker, scan manager, etc.)
            service_initializer = ServiceInitializer(app, service_manager)
            
            # Use background thread for heavy service initialization
            import threading
            def initialize_services():
                try:
                    service_initializer.initialize_all()
                    app.logger.info("Background service initialization completed")
                except Exception as e:
                    app.logger.error(f"Background service initialization failed: {e}")
            
            # Start service initialization in background
            service_thread = threading.Thread(target=initialize_services, daemon=True)
            service_thread.start()
            
            # Initialize essential services only (batch service can be deferred)
            try:
                from core_services import BatchAnalysisService
                batch_service = BatchAnalysisService()
                batch_service.init_app(app)
                app.batch_service = batch_service
                app.logger.info("Batch analysis service initialized successfully")
            except Exception as e:
                app.logger.warning(f"Batch service initialization deferred: {e}")
                app.batch_service = None
            
            app.logger.info("Core services initialized successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize core services: {e}")
            # Set up minimal fallback services
            app.config['docker_manager'] = None
            app.config['service_manager'] = ServiceManager(app)
            app.batch_service = None
    
    # Register blueprints with HTMX routes
    try:
        from web_routes import register_blueprints
        register_blueprints(app)
        app.logger.info("All blueprints registered successfully")
    except ImportError as e:
        app.logger.error(f"Failed to import blueprints from web_routes: {e}")
        # Create minimal fallback routes
        @app.route('/')
        def index():
            return "Application is running but blueprints failed to load. Check logs for import errors."
    
    # Add template globals for HTMX integration
    @app.template_global()
    def get_app_config():
        """Make app config available in templates."""
        return app.config
    
    @app.template_global()
    def debug_mode():
        """Check if app is in debug mode."""
        return app.debug
    
    @app.template_global()
    def get_model_count():
        """Get total number of models in database."""
        try:
            return ModelCapability.query.count()
        except Exception:
            return 0
    
    @app.template_global()
    def get_app_count():
        """Get total number of generated applications."""
        try:
            return GeneratedApplication.query.count()
        except Exception:
            return 0
    
    # Add context processor for common template variables
    @app.context_processor
    def inject_template_vars():
        """Inject common variables into all templates."""
        return {
            'app_name': 'Thesis Research App',
            'app_version': '2.0.0-htmx',
            'htmx_enabled': True
        }
    
    # Add custom error handlers
    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template, request
        if request.headers.get('HX-Request'):
            try:
                return render_template('partials/error_message.html', 
                                     error="Page not found"), 404
            except Exception:
                return '<div class="alert error">Page not found</div>', 404
        return render_template('pages/error.html', 
                             error="The requested page could not be found.",
                             error_code=404), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template, request
        app.logger.error(f"Internal server error: {error}")
        if request.headers.get('HX-Request'):
            try:
                return render_template('partials/error_message.html', 
                                     error="Internal server error"), 500
            except Exception:
                return '<div class="alert error">Internal server error</div>', 500
        return render_template('pages/error.html', 
                             error="An internal server error occurred.",
                             error_code=500), 500
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        """Simple health check endpoint."""
        from flask import jsonify
        return jsonify({
            'status': 'healthy',
            'service': 'thesis-research-app',
            'version': '2.0.0-htmx',
            'database': 'connected' if db else 'disconnected'
        })
    
    app.logger.info("Flask application created successfully with HTMX routes")
    return app


def main():
    """Main entry point for running the application."""
    # Create the application
    app = create_app()
    
    # Get configuration from environment
    host = os.getenv('FLASK_HOST', '127.0.0.1')
    port = int(os.getenv('FLASK_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
    
    print(f"""
    ╔════════════════════════════════════════════════════════════════════════════════════════╗
    ║                              Thesis Research App - HTMX Edition                        ║
    ║                                                                                        ║
    ║  🚀 Application starting...                                                           ║
    ║  📡 Server: http://{host}:{port}                                                    ║
    ║  🔧 Debug Mode: {'Enabled' if debug else 'Disabled'}                                                       ║
    ║  ⚡ HTMX Integration: Active                                                          ║
    ║                                                                                        ║
    ║  📊 Features Available:                                                               ║
    ║  • Interactive Dashboard with live updates                                            ║
    ║  • Security Analysis (CLI Tools Integration)                                          ║
    ║  • Performance Testing (Locust Integration)                                           ║
    ║  • ZAP Security Scanning                                                              ║
    ║  • OpenRouter Requirements Analysis                                                    ║
    ║  • Batch Processing                                                                    ║
    ║  • Docker Container Management                                                         ║
    ║                                                                                        ║
    ║  🎯 Access the dashboard at: http://{host}:{port}                                   ║
    ╚════════════════════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Run the application
        app.run(
            host=host,
            port=port,
            debug=debug,
            threaded=True,
            use_reloader=debug
        )
    except KeyboardInterrupt:
        print("\n\n👋 Application stopped by user")
        print("Docker connection refreshed on restart")
    except Exception as e:
        print(f"\n❌ Failed to start application: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
