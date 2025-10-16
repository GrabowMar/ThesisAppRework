"""
Routes Package
Handles all application routes organized by type.
"""

from .jinja.main import main_bp
from .jinja.models import models_bp
from .jinja.analysis import analysis_bp
from .jinja.stats import stats_bp
from .jinja.reports import reports_bp
from .jinja.docs import docs_bp
from .jinja.sample_generator import sample_generator_bp

# Refactored API blueprints - organized by domain
from .api import (
    api_bp, core_bp, models_bp as api_models_bp, system_bp, dashboard_bp,
    applications_bp, analysis_bp as api_analysis_bp, scaffold_bp, sample_gen_bp, 
    tasks_rt_bp, template_store_bp, migration_bp
)

# Enhanced results API
from .api.results_v2 import results_api_bp

# V2 Template System API
from .api.templates_v2 import templates_v2_bp

from .websockets import websocket_api_bp, register_websocket_routes, register_error_handlers
from .shared_utils import register_template_globals_and_filters

__all__ = [
    # Jinja blueprints
    'main_bp',
    'models_bp',
    'analysis_bp',
    'stats_bp',
    'reports_bp',
    'docs_bp',
    'sample_generator_bp',

    # Main API orchestrator blueprint
    'api_bp',

    # Refactored API blueprints
    'core_bp',
    'api_models_bp',
    'system_bp',
    'dashboard_bp',
    'applications_bp',
    'api_analysis_bp',
    'sample_gen_bp',
    'scaffold_bp',
    'tasks_rt_bp',
    'template_store_bp',
    'migration_bp',

    # Enhanced results API
    'results_api_bp',
    
    # V2 Template System API
    'templates_v2_bp',

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
    app.register_blueprint(reports_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(sample_generator_bp)

    # Register refactored API blueprints under /api prefix
    app.register_blueprint(api_bp, url_prefix='/api')  # Main API orchestrator (includes all nested blueprints)
    
    # Individual blueprint registration commented out since they're now nested in api_bp
    # app.register_blueprint(core_bp, url_prefix='/api')
    # app.register_blueprint(api_models_bp, url_prefix='/api/models')
    # app.register_blueprint(system_bp, url_prefix='/api/system')
    # app.register_blueprint(dashboard_bp, url_prefix='/api/dashboard')
    # app.register_blueprint(applications_bp, url_prefix='/api')
    # app.register_blueprint(api_analysis_bp, url_prefix='/api')
    # app.register_blueprint(migration_bp, url_prefix='/api')
    
    # These already have their prefixes defined in the blueprint files
    app.register_blueprint(sample_gen_bp)  # /api/sample-gen
    app.register_blueprint(scaffold_bp)   # /api/app-scaffold
    app.register_blueprint(tasks_rt_bp)   # /api/tasks
    app.register_blueprint(template_store_bp)  # /api/templates
    app.register_blueprint(results_api_bp)  # /analysis/api/v2
    app.register_blueprint(templates_v2_bp)  # /api/v2/templates

    # Register WebSocket API blueprint under both legacy (/api/websocket) and new (/ws-api) paths
    # The tests expect /api/websocket/* endpoints.
    app.register_blueprint(websocket_api_bp, url_prefix='/api/websocket')

    # Register WebSocket routes and error handlers
    register_websocket_routes(app)
    register_error_handlers(app)

    # Register template globals and filters
    register_template_globals_and_filters(app)