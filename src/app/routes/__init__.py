"""
Routes Package
Handles all application routes organized by type.
"""

from .jinja import (
    main_bp,
    models_bp,
    analysis_bp,
    stats_bp,
    tasks_bp,
    advanced_bp,
    reports_bp,
    docs_bp,
    sample_generator_bp
)
from .api import api_bp
from .api.sample_generation import sample_gen_bp
from .api.app_scaffolding import scaffold_bp
from .websockets import websocket_api_bp, register_websocket_routes, register_error_handlers
from .shared_utils import register_template_globals_and_filters

__all__ = [
    # Jinja blueprints
    'main_bp',
    'models_bp',
    'analysis_bp',
    'stats_bp',
    'tasks_bp',
    'advanced_bp',
    'reports_bp',
    'docs_bp',

    # API blueprints
    'api_bp',
    'sample_gen_bp',
    'scaffold_bp',

    # WebSocket blueprints and functions
    'websocket_api_bp',
    'register_websocket_routes',
    'register_error_handlers',

    # Shared utilities
    'register_template_globals_and_filters',

    # Blueprint registration function
    'register_blueprints'
]

def register_blueprints(app):
    """
    Register all application blueprints with the Flask app.

    Args:
        app: Flask application instance
    """
    # Register Jinja template blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(advanced_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(sample_generator_bp)

    # Register API blueprint
    app.register_blueprint(api_bp, url_prefix='/api')
    # Sample generation API (already prefixed inside file with /api/sample-gen)
    app.register_blueprint(sample_gen_bp)
    # App scaffolding API (/api/app-scaffold)
    app.register_blueprint(scaffold_bp)

    # Register WebSocket API blueprint
    app.register_blueprint(websocket_api_bp, url_prefix='/ws-api')

    # Register WebSocket routes and error handlers
    register_websocket_routes(app)
    register_error_handlers(app)

    # Register template globals and filters
    register_template_globals_and_filters(app)