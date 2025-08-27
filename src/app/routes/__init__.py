"""Unified Route Registration
=============================

This package centralizes blueprint registration for the Flask application.

Improvements in this refactored module:
1. Programmatic registration table instead of ad-hoc calls
2. Lazy imports inside `load_blueprints()` reduce import side effects during tooling
3. Clear documentation of each blueprint's purpose
4. Single place to toggle blueprints or adjust URL prefixes
5. Separation of concerns: blueprint discovery vs. registration logic

Extensibility: To add a new blueprint, implement it in a sibling module and
add an entry to the BLUEPRINT_SPECS list.
"""
from __future__ import annotations

import logging

from .errors import register_error_handlers
from .api import register_api_routes  # API blueprint managed separately

logger = logging.getLogger(__name__)


def load_blueprints():
    """Import and return blueprint specifications.

    Returns a list of dicts: { 'bp': Blueprint, 'url_prefix': str | None, 'name': str }
    Lazy import pattern keeps module import side effects minimal until runtime.
    """
    from .main import main_bp
    from .models import models_bp
    from .analysis import analysis_bp
    from .batch import batch_bp
    from .statistics import stats_bp
    from .advanced import advanced as advanced_bp
    from .reports import reports_bp
    from .system_api import system_api_bp, analysis_api_bp

    return [
        {"bp": main_bp, "url_prefix": None, "name": "main"},
        {"bp": models_bp, "url_prefix": "/models", "name": "models"},
        {"bp": analysis_bp, "url_prefix": "/analysis", "name": "analysis"},
        {"bp": batch_bp, "url_prefix": "/batch", "name": "batch"},
        {"bp": stats_bp, "url_prefix": "/statistics", "name": "statistics"},
        {"bp": advanced_bp, "url_prefix": "/advanced", "name": "advanced"},
    {"bp": reports_bp, "url_prefix": "/reports", "name": "reports"},
        {"bp": system_api_bp, "url_prefix": "/api/system", "name": "system_api"},
        {"bp": analysis_api_bp, "url_prefix": "/api/analysis", "name": "analysis_api"},
    ]


def register_blueprints(app):  # noqa: D401
    """Register all application blueprints and error handlers."""

    # Register non-API blueprints
    for spec in load_blueprints():
        bp = spec["bp"]
        url_prefix = spec["url_prefix"]
        app.register_blueprint(bp, url_prefix=url_prefix)
        logger.debug("Registered blueprint '%s' at prefix '%s'", spec["name"], url_prefix or "/")

    # API blueprint (handles its own lazy module imports)
    register_api_routes(app)

    # WebSocket fallback routes
    from .websocket_fallbacks import register_websocket_routes
    register_websocket_routes(app)

    # Error handlers (global)
    register_error_handlers(app)

    logger.info("All blueprints registered successfully")

__all__ = ["register_blueprints", "load_blueprints"]
