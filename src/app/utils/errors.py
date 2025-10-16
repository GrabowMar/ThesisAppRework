"""Unified error response utilities and exception hierarchy for HTTP layer.

This builds atop service_base exceptions but adds HTTP semantics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from flask import g, request

# Map service layer exceptions will be augmented later
HTTP_DEFAULT_STATUS = 500

@dataclass
class AppError(Exception):
    message: str
    http_status: int = 400
    code: Optional[str] = None  # machine readable stable code
    details: Optional[Dict[str, Any]] = None

    def __str__(self):  # pragma: no cover - trivial
        return self.message

class BadRequestError(AppError):
    http_status = 400
class UnauthorizedError(AppError):
    http_status = 401
class ForbiddenError(AppError):
    http_status = 403
class NotFoundHTTPError(AppError):
    http_status = 404
class ConflictHTTPError(AppError):
    http_status = 409
class TooManyRequestsError(AppError):
    http_status = 429
class InternalServerAppError(AppError):
    http_status = 500

# Translate service_base exceptions lazily to avoid import cycle
SERVICE_EXCEPTION_HTTP_MAP = {
    'NotFoundError': 404,
    'ValidationError': 400,
    'ConflictError': 409,
    'OperationError': 500,
}

def build_error_payload(message: str, *, status: int, error: str | None = None, **extra: Any) -> Dict[str, Any]:
    payload = {
        'status': 'error',
        'status_code': status,
        'message': message,
        'error': error or message,
        'error_id': getattr(g, 'request_id', None),
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'path': request.path if request else None,
    }
    payload.update({k: v for k, v in extra.items() if v is not None})
    return payload


def map_service_exception(exc: Exception) -> int:
    name = type(exc).__name__
    return SERVICE_EXCEPTION_HTTP_MAP.get(name, HTTP_DEFAULT_STATUS)
