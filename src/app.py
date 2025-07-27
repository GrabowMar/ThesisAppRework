"""
Flask Application Factory
========================

Main application entry point that uses the new HTMX-based routes.
Integrates with the existing services and utilities from main.py.
"""

import os
from pathlib import Path

from flask import Flask

# Import core application components
from core_services import (
    # Service initialization
    initialize_logging, setup_request_middleware, initialize_model_service,
    ServiceInitializer, ServiceManager,
    
    # Global services (these will be available to routes)
    get_model_service, get_docker_manager,
    
    # Configuration
    Config
)

# Import the new HTMX-based routes
from web_routes import register_blueprints


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
    (app_root / "src" / "templates").mkdir(exist_ok=True)
    (app_root / "src" / "static").mkdir(exist_ok=True)
    
    # Initialize logging
    initialize_logging(app)
    
    # Setup request middleware
    setup_request_middleware(app)
    
    # Initialize services
    with app.app_context():
        try:
            # Initialize the model integration service
            service = initialize_model_service(app_root)
            app.logger.info(f"Model service initialized with {len(service.get_all_models())} models")
            
            # Initialize additional services (Docker, ZAP, etc.)
            service_manager = ServiceManager(app)
            service_initializer = ServiceInitializer(app, service_manager)
            service_initializer.initialize_all()
            app.logger.info("All application services initialized successfully")
            
        except Exception as e:
            app.logger.error(f"Failed to initialize services: {e}")
            # Continue anyway to allow the app to start
    
    # Register blueprints with HTMX routes
    register_blueprints(app)
    
    # Add template globals
    @app.template_global()
    def get_app_config():
        """Make app config available in templates."""
        return app.config
    
    @app.template_global()
    def debug_mode():
        """Check if app is in debug mode."""
        return app.debug
    
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
            'version': '2.0.0-htmx'
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
