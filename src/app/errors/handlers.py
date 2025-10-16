"""Centralized error handlers with HTML + JSON negotiation.

Provides informative error pages using template 'pages/errors/errors_main.html'
while returning structured JSON for API/AJAX requests.
"""
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    g,
)
from werkzeug.exceptions import HTTPException
from app.utils.errors import AppError, build_error_payload, map_service_exception

error_bp = Blueprint("errors", __name__)

# Mapping of HTTP codes to default metadata
ERROR_META = {
    400: {"title": "Bad Request", "icon": "fas fa-exclamation-circle", "subtitle": "The request could not be understood."},
    401: {"title": "Unauthorized", "icon": "fas fa-lock", "subtitle": "Authentication is required or has failed."},
    403: {"title": "Forbidden", "icon": "fas fa-ban", "subtitle": "You do not have permission to access this resource."},
    404: {"title": "Page Not Found", "icon": "fas fa-search", "subtitle": "The requested resource could not be found."},
    405: {"title": "Method Not Allowed", "icon": "fas fa-hand-paper", "subtitle": "The method is not allowed for this endpoint."},
    409: {"title": "Conflict", "icon": "fas fa-exclamation-triangle", "subtitle": "The request conflicts with current state."},
    415: {"title": "Unsupported Media Type", "icon": "fas fa-file", "subtitle": "The media type is not supported."},
    429: {"title": "Too Many Requests", "icon": "fas fa-tachometer-alt", "subtitle": "Rate limit exceeded."},
    500: {"title": "Internal Server Error", "icon": "fas fa-exclamation-triangle", "subtitle": "Something went wrong on our end."},
    503: {"title": "Service Unavailable", "icon": "fas fa-cogs", "subtitle": "The service is temporarily unavailable."},
}

SAFE_ERROR_FIELDS = ["code", "name", "description"]

def wants_json_response() -> bool:
    """Decide if JSON should be returned based on headers/path.
    Priority:
      - Explicit Accept header with application/json
      - XMLHttpRequest / fetch (X-Requested-With)
      - API prefix (/api/)
    """
    if request.path.startswith("/api/"):
        return True
    accept = request.headers.get("Accept", "")
    if "application/json" in accept:
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    return False


def _base_payload(status_code: int, message: str, extra: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = {
        "status": "error",
        "status_code": status_code,
        "message": message,
        "error_id": getattr(g, "request_id", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.path,
    }
    if extra:
        payload.update(extra)
    return payload


def render_error(status_code: int, error: Exception | None = None):  # type: ignore[override]
    meta = ERROR_META.get(status_code, {"title": "Error", "icon": "fas fa-exclamation-circle"})

    # Build safe message
    default_message = meta.get("subtitle") or meta.get("title") or "Error"
    debug = current_app.debug or current_app.config.get("SHOW_ERROR_DETAILS", False)

    if isinstance(error, AppError):
        description = error.message or default_message
        status_code = getattr(error, 'http_status', status_code) or status_code
    elif isinstance(error, HTTPException):
        description = getattr(error, "description", default_message)
    else:
        description = default_message

    # Extended debug info
    debug_info: Dict[str, Any] = {}
    if debug and error:
        debug_info = {
            "exception_type": type(error).__name__,
            "stacktrace": traceback.format_exc() if not isinstance(error, HTTPException) else None,
        }

    if wants_json_response():
        if isinstance(error, AppError):
            payload = build_error_payload(description, status=status_code, error=meta.get("title"), code=error.code, details=error.details, **({"debug": debug_info} if debug_info else {}))
        else:
            # Map service_base style exceptions (imported indirectly) by name if not HTTP/AppError
            if error and not isinstance(error, HTTPException):
                status_code_local = map_service_exception(error)
                if status_code_local != status_code:
                    status_code = status_code_local
            payload = _base_payload(status_code, description, {"error": meta.get("title"), **({"debug": debug_info} if debug_info else {})})
        return make_response(jsonify(payload), status_code)

    return make_response(render_template(
        "pages/errors/errors_main.html",
        error_code=status_code,
        error_title=meta.get("title"),
        error_icon=meta.get("icon"),
        error_subtitle=meta.get("subtitle"),
        error_message=description,
        debug=debug,
        debug_info=debug_info,
        python_version=current_app.config.get("PYTHON_VERSION"),
        request_id=getattr(g, "request_id", None),
    ), status_code)


# Generic catch-all for HTTPException via blueprint route
@error_bp.app_errorhandler(HTTPException)  # type: ignore[misc]
def handle_http_exception(exc: HTTPException):  # pragma: no cover - integration
    return render_error(getattr(exc, "code", 500) or 500, exc)


@error_bp.app_errorhandler(Exception)  # type: ignore[misc]
def handle_uncaught_exception(exc: Exception):  # pragma: no cover - integration
    current_app.logger.exception("Unhandled exception: %s", exc)
    return render_error(500, exc)


def register_error_handlers(app):
    """Register handlers & attach request id generation."""
    # Request ID middleware
    @app.before_request  # type: ignore[misc]
    def _assign_request_id():  # pragma: no cover - simple
        g.request_id = uuid.uuid4().hex

    # Simple route to test 500 in debug
    if app.debug:
        @app.route("/trigger-error")  # type: ignore[misc]
        def _trigger_error():  # pragma: no cover - debug only
            raise RuntimeError("Intentional test error")

    app.register_blueprint(error_bp)

    # Explicit handlers for selected status codes to ensure proper metadata
    for sc in [400,401,403,404,405,409,415,429,500,503]:
        def _make(sc_code):
            def _handler(e):
                return render_error(sc_code, e)
            return _handler
        app.register_error_handler(sc, _make(sc))

    return app
