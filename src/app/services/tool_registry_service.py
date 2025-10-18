"""Compatibility layer for tool registry lookups.

Legacy routes expect ``get_tool_registry_service`` which previously returned a
singleton object. The new container-based registry already exposes the desired
API, so this module simply forwards the call.
"""
from __future__ import annotations

from app.engines.container_tool_registry import get_container_tool_registry


def get_tool_registry_service():
    """Return the shared container tool registry instance."""
    return get_container_tool_registry()
