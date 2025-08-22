"""Service Base Utilities
=========================

Provides shared exception hierarchy and light helper mixins to standardize
service layer implementations and reduce boilerplate across modules.

Usage Pattern:
    from .service_base import ServiceError, NotFoundError, ValidationError

All service modules should raise these exceptions so route / API layers can
map them uniformly to HTTP responses.
"""
from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any, Dict
import warnings

__all__ = [
    'ServiceError', 'NotFoundError', 'ValidationError', 'ConflictError', 'OperationError',
    'ensure_dataclass_dict', 'deprecation_warning'
]


class ServiceError(Exception):
    """Base class for all service layer errors."""


class NotFoundError(ServiceError):
    """Entity not found."""


class ValidationError(ServiceError):
    """Invalid input or failed validation rules."""


class ConflictError(ServiceError):
    """State or uniqueness conflict when performing operation."""


class OperationError(ServiceError):
    """Generic failure performing an operation (e.g., external dependency)."""


def ensure_dataclass_dict(obj: Any) -> Dict[str, Any]:  # pragma: no cover - trivial
    """Convert dataclass instance (nested) to dict; pass through dicts; fallback to repr."""
    if is_dataclass(obj):
        return asdict(obj)  # type: ignore[arg-type]
    if isinstance(obj, dict):
        return obj
    return {'value': repr(obj)}


def deprecation_warning(message: str, *, stacklevel: int = 2):  # pragma: no cover - simple
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel)
