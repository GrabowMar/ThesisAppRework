"""
API Routes Package
==================

Modular API endpoints organized by functionality.
"""

from flask import Blueprint
import logging

from ..response_utils import json_error

# Create the main API blueprint
api_bp = Blueprint('api', __name__)

logger = logging.getLogger(__name__)


@api_bp.app_errorhandler(Exception)
def api_global_exception_handler(exc):  # pylint: disable=unused-argument
    """Return standardized JSON errors for unhandled exceptions within /api.* routes.

    This keeps API responses consistent even if a view forgot to decorate.
    """
    logger.exception("Unhandled exception in API layer")
    # Avoid leaking internal messages broadly; include class name only.
    return json_error("Internal server error", status=500, error_type=exc.__class__.__name__)


# Register all API sub-routes
def register_api_routes(app):
    """Register all API routes with the Flask application.

    Previous implementation registered the blueprint *before* importing the
    route modules. Flask 3.x forbids adding routes to a blueprint after it has
    been registered (raises 'setup method route can no longer be called').

    We now:
        1. Import route modules first so their decorators attach endpoints.
        2. Register the blueprint only once afterwards.
        3. Guard against accidental double-registration across multiple factory calls.
        4. Always ensure the WebSocket API blueprint is registered, even if the
           main 'api' blueprint already exists.
    """

    # Register main API blueprint (once)
    if 'api' not in app.blueprints:
        # Import route modules so @api_bp.route decorators execute before registration
        from . import core  # noqa: F401
        from . import models  # noqa: F401
        from . import statistics  # noqa: F401
        from . import dashboard  # noqa: F401
        from . import applications  # noqa: F401
        from . import analysis  # noqa: F401
        from . import system  # noqa: F401
        from . import misc  # noqa: F401
        from . import results  # noqa: F401

        # Now safe to register blueprint with all routes bound
        app.register_blueprint(api_bp, url_prefix='/api')
        logger.info("API blueprint registered successfully")
    else:
        logger.debug("API blueprint already registered; skipping re-registration")

    # Register WebSocket API blueprint separately (ensure it's present)
    try:
        from .websocket import websocket_api
        if 'websocket_api' not in app.blueprints:
            app.register_blueprint(websocket_api)
            logger.info("WebSocket API registered successfully")
        else:
            logger.debug("WebSocket API already registered; skipping re-registration")
    except Exception as e:
        logger.warning(f"Failed to register WebSocket API: {e}")


__all__ = ['api_bp', 'register_api_routes']

# Note: route modules are imported lazily in register_api_routes()
