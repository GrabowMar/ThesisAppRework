"""Service Base Utilities
=========================

Provides shared exception hierarchy to standardize service layer
implementations and reduce boilerplate across modules.

Usage Pattern:
    from .service_base import ServiceError, NotFoundError, ValidationError

All service modules should raise these exceptions so route / API layers can
map them uniformly to HTTP responses.
"""
from __future__ import annotations

__all__ = [
    'ServiceError', 'NotFoundError', 'ValidationError', 'ConflictError', 'OperationError',
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
