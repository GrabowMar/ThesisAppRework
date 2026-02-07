"""Route Response Utilities
===========================

Shared helpers and decorators to standardize API and HTMX route behavior.

Goals:
- Remove repetitive try/except + logging blocks scattered across routes
- Provide consistent JSON envelope format
- Simplify error handling with an @handle_exceptions decorator
- Support HTMX partial rendering with graceful error fallbacks

Design:
json_success(data=None, message=None, **meta) -> (dict, int)
json_error(message, status=400, **details) -> (dict, int)
handle_exceptions(logger=None, *, default_status=500, reraise=False)
    Wraps a route function. Catches exceptions, logs, returns json_error or renders an error partial

Response Envelope Standard:
{
  "ok": true/false,
  "message": str | null,
  "data": {...} | list | null,
  "error": {"type": str, "details": any} | null,
  "meta": {...}
}

The envelope keeps front-end consumption consistent.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Dict
import logging
from flask import jsonify, request, render_template

F = TypeVar("F", bound=Callable[..., Any])

# Default module-level logger
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# JSON Builders
# ---------------------------------------------------------------------------

def json_success(data: Any = None, message: Optional[str] = None, status: int = 200, **meta):
    """Build a standardized success JSON response.

    Additional keyword args become part of meta.
    """
    payload: Dict[str, Any] = {
        "ok": True,
        "message": message,
        "data": data,
        "error": None,
        "meta": meta or None,
    }
    return jsonify(payload), status


def json_error(message: str, status: int = 400, *, error_type: Optional[str] = None, **details):
    """Build a standardized error JSON response."""
    payload: Dict[str, Any] = {
        "ok": False,
        "message": message,
        "data": None,
        "error": {
            "type": error_type or "ApplicationError",
            "details": details or None,
        },
        "meta": None,
    }
    return jsonify(payload), status

# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def handle_exceptions(_func: Optional[F] = None, *, default_status: int = 500, logger_override: Optional[logging.Logger] = None, reraise: bool = False, htmx_partial: Optional[str] = None):
    """Decorator to standardize exception handling for route functions.

    Parameters:
        default_status: HTTP status when an unhandled exception occurs
        logger_override: custom logger; falls back to module logger
        reraise: if True, re-raise after logging (useful for debug/testing)
        htmx_partial: if provided and request is HTMX, render this error partial
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):  # type: ignore
            active_logger = logger_override or logger
            try:
                return func(*args, **kwargs)
            except Exception as exc:  # pylint: disable=broad-except
                active_logger.exception("Unhandled exception in %s", func.__name__)
                # HTMX request detection via HX-Request header
                if request.headers.get("HX-Request") and htmx_partial:
                    return render_template(htmx_partial, error=str(exc)), default_status
                if reraise:
                    raise
                return json_error("Internal server error", status=default_status, error_type=exc.__class__.__name__, detail=str(exc))
        return wrapper  # type: ignore
    # Support decorator w/ or w/out parentheses
    if _func is not None:
        return decorator(_func)
    return decorator

__all__ = [
    "json_success",
    "json_error",
    "handle_exceptions",
]