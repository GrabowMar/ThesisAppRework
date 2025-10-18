"""Compatibility wrappers for container management utilities.

The legacy dashboard endpoints import ``get_docker_manager`` from this module.
Keep a thin shim that simply forwards to the real ServiceLocator registration
so that Pylance (and older code paths) continue to work.
"""
from __future__ import annotations

from typing import Any, Optional

from .service_locator import ServiceLocator

try:  # Optional import during tests where Docker manager might be absent
    from .docker_manager import DockerManager
except Exception:  # pragma: no cover - fallback when docker manager unavailable
    DockerManager = None  # type: ignore


def get_docker_manager() -> Optional[Any]:
    """Return the registered Docker manager instance, if available."""
    manager = ServiceLocator.get_docker_manager()
    if DockerManager is not None and manager is not None:
        return manager  # type: ignore[return-value]
    return manager
