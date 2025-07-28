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

# Import the new HTMX-based routes
from web_routes import register_blueprints


class Config:
    """Application configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///data/thesis_app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300


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
        # Load model capabilities
        capabilities_file = misc_dir / "model_capabilities.json"
        if capabilities_file.exists():
            with open(capabilities_file) as f:
                capabilities_data = json.load(f)
                models_count = len(capabilities_data.get('models', {}))
                app.logger.info(f"Loaded capabilities for {models_count} models")
        else:
            app.logger.warning(f"Model capabilities file not found: {capabilities_file}")
        
        # Load port configurations
        port_file = misc_dir / "port_config.json"
        if port_file.exists():
            with open(port_file) as f:
                port_data = json.load(f)
                app.logger.info(f"Loaded {len(port_data)} port configurations")
        else:
            app.logger.warning(f"Port config file not found: {port_file}")
        
        # Load models summary
        models_file = misc_dir / "models_summary.json"
        if models_file.exists():
            with open(models_file) as f:
                models_data = json.load(f)
                models_count = len(models_data.get('models', []))
                app.logger.info(f"Loaded models summary with {models_count} models")
        else:
            app.logger.warning(f"Models summary file not found: {models_file}")
            
    except Exception as e:
        app.logger.error(f"Failed to load model integration data: {e}")


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
    
    # Load model integration data
    with app.app_context():
        try:
            load_model_integration_data(app)
            app.logger.info("Model integration data loaded successfully")
        except Exception as e:
            app.logger.error(f"Failed to initialize services: {e}")
    
    # Register blueprints with HTMX routes
    register_blueprints(app)
    app.logger.info("All blueprints registered successfully")
    
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
        except:
            return 0
    
    @app.template_global()
    def get_app_count():
        """Get total number of generated applications."""
        try:
            return GeneratedApplication.query.count()
        except:
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
            return render_template('partials/error_message.html', 
                                 error="Page not found"), 404
        return render_template('pages/error.html', 
                             error="The requested page could not be found."), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template, request
        app.logger.error(f"Internal server error: {error}")
        if request.headers.get('HX-Request'):
            return render_template('partials/error_message.html', 
                                 error="Internal server error"), 500
        return render_template('pages/error.html', 
                             error="An internal server error occurred."), 500
    
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
    except Exception as e:
        print(f"\n❌ Failed to start application: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
