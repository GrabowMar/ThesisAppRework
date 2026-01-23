"""
Routes Package
Handles all application routes organized by type.
"""

from .jinja.main import main_bp
from .jinja.models import models_bp
from .jinja.applications import applications_bp as jinja_applications_bp
from .jinja.analysis import analysis_bp
from .jinja.stats import stats_bp
from .jinja.reports import reports_bp
from .jinja.docs import docs_bp
from .jinja.sample_generator import sample_generator_bp
from .jinja.auth import auth_bp
from .jinja.profile import profile_bp
from .jinja.automation import automation_bp
from .jinja.rankings import rankings_bp

# Refactored API blueprints - organized by domain
from .api import (
    api_bp, core_bp, models_bp as api_models_bp, system_bp, dashboard_bp,
    applications_bp, analysis_bp as api_analysis_bp, gen_bp,
    tasks_rt_bp, container_tools_bp, export_bp, reports_bp as api_reports_bp
)

# API Token management
from .api.tokens import tokens_bp

# Enhanced results API
from .api.results import results_api_bp

# Research comparison API (removed)
# from .api.research import research_bp

from .websockets import websocket_api_bp
from .shared_utils import register_template_globals_and_filters

__all__ = [
    # Jinja blueprints
    'main_bp',
    'models_bp',
    'jinja_applications_bp',
    'analysis_bp',
    'stats_bp',
    'reports_bp',
    'docs_bp',
    'sample_generator_bp',
    'auth_bp',
    'profile_bp',
    'automation_bp',
    'rankings_bp',

    # Main API orchestrator blueprint
    'api_bp',

    # Refactored API blueprints
    'core_bp',
    'api_models_bp',
    'system_bp',
    'dashboard_bp',
    'applications_bp',
    'api_analysis_bp',
    'gen_bp',
    'tasks_rt_bp',
    'container_tools_bp',
    'export_bp',

    # API token management
    'tokens_bp',

    # Enhanced results API
    'results_api_bp',

    # WebSocket blueprints and functions
    'websocket_api_bp',

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
    # Register auth blueprint first (no login required)
    app.register_blueprint(auth_bp)
    
    # Register Jinja template blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(models_bp)
    app.register_blueprint(jinja_applications_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(docs_bp)
    app.register_blueprint(sample_generator_bp)
    app.register_blueprint(profile_bp)  # User profile and settings
    app.register_blueprint(automation_bp)  # End-to-end automation pipeline
    app.register_blueprint(rankings_bp)  # AI Model rankings aggregator

    # Register refactored API blueprints under /api prefix
    app.register_blueprint(api_bp, url_prefix='/api')  # Main API orchestrator (includes all nested blueprints)

    # These already have their prefixes defined in the blueprint files
    app.register_blueprint(gen_bp)  # /api/gen (scaffolding-first generation)
    app.register_blueprint(tasks_rt_bp)   # /api/tasks
    app.register_blueprint(tokens_bp)  # /api/tokens (token management)
    app.register_blueprint(results_api_bp)  # /analysis/api
    app.register_blueprint(export_bp)  # /api/export (unified export service)

    # Register WebSocket API blueprint under the /ws-api prefix
    app.register_blueprint(websocket_api_bp)

    # Register template globals and filters
    register_template_globals_and_filters(app)