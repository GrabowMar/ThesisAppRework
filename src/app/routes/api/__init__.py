"""
API Routes Package
==================

Modular API endpoints organized by functionality.
"""

from flask import Blueprint

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

# Register all API sub-routes
def register_api_routes(app):
    """Register all API routes with the Flask application."""
    
    # Register the main API blueprint
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # The sub-modules will register their routes on the api_bp blueprint

__all__ = ['api_bp', 'register_api_routes']

# Import all API modules to register their routes with the blueprint
# These imports are intentionally done at the end to register routes after blueprint creation
# pylint: disable=wrong-import-position,unused-import
from . import (
    core,
    models, 
    statistics,
    dashboard,
    applications,
    analysis,
    system,
    misc
)
