"""
Tool Registry API routes
========================

Lightweight JSON endpoints exposing the ToolRegistryService for the UI.

Endpoints:
- GET /api/tool-registry/tools     -> list of tools (with UI-friendly fields)
- GET /api/tool-registry/profiles  -> list of analysis profiles
"""

from __future__ import annotations

from flask import Blueprint, current_app
from typing import Any, Dict, List

from .common import api_success, api_error


tool_registry_bp = Blueprint('tool_registry', __name__)


def _massage_tool_fields(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize tool fields so the frontend can consume them consistently.

    - Ensure 'enabled' mirrors 'is_enabled'
    - Ensure 'execution_time_estimate' is present (fallback to 'estimated_duration')
    - Ensure 'service_name' key exists (fallback from 'analyzer_service')
    """
    t = dict(tool)
    # enabled alias
    if 'enabled' not in t:
        t['enabled'] = bool(t.get('is_enabled', True))
    # execution time alias (seconds)
    if 'execution_time_estimate' not in t:
        est = t.get('estimated_duration')
        try:
            t['execution_time_estimate'] = int(est) if est is not None else None
        except Exception:
            t['execution_time_estimate'] = None
    # service name normalization
    if not t.get('service_name') and t.get('analyzer_service'):
        t['service_name'] = t.get('analyzer_service')
    # ensure basic string fields present
    if 'display_name' not in t:
        t['display_name'] = t.get('name')
    # category normalization to UI buckets
    cat = (t.get('category') or '').lower()
    cat_map = {
        'code_quality': 'quality',
        'ai_analysis': 'quality',
        'dynamic_analysis': 'dynamic',
        'vulnerability': 'security',
    }
    if cat_map.get(cat):
        t['category'] = cat_map[cat]
    elif cat in {'security', 'performance', 'quality', 'dynamic'}:
        # keep as-is
        pass
    elif cat:
        # default unknowns to quality to avoid empty rendering
        t['category'] = 'quality'
    return t


@tool_registry_bp.route('/tool-registry/tools')
def api_tool_registry_tools():
    """Return all tools from ToolRegistryService with normalized fields."""
    try:
        from app.services.service_locator import ServiceLocator
        tool_service = ServiceLocator.get_tool_registry_service()
        if not tool_service:
            return api_error("Tool registry service not available")

        ts: Any = tool_service  # type: ignore[assignment]
        tools_raw: List[Dict[str, Any]] = ts.get_all_tools(enabled_only=False)
        # Keep only tools with integer IDs to match current UI expectations
        filtered: List[Dict[str, Any]] = []
        for t in tools_raw:
            tid = t.get('id')
            if isinstance(tid, int):
                filtered.append(t)
            else:
                # accept numeric strings defensively
                try:
                    _ = int(str(tid))
                    t['id'] = _
                    filtered.append(t)
                except Exception:
                    # skip dynamic/non-numeric ids for now
                    continue
        tools = [_massage_tool_fields(t) for t in filtered]
        return api_success(tools, message="Tools fetched")
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"tool-registry/tools failed: {e}")
        return api_error("Failed to load tools", details={"reason": str(e)})


@tool_registry_bp.route('/tool-registry/profiles')
def api_tool_registry_profiles():
    """Return analysis profiles from ToolRegistryService."""
    try:
        from app.services.service_locator import ServiceLocator
        tool_service = ServiceLocator.get_tool_registry_service()
        if not tool_service:
            return api_error("Tool registry service not available")

        ts: Any = tool_service  # type: ignore[assignment]
        profiles: List[Dict[str, Any]] = ts.get_analysis_profiles()
        # No strict schema required by UI beyond name/description; return as-is
        return api_success(profiles, message="Profiles fetched")
    except Exception as e:  # pragma: no cover
        current_app.logger.error(f"tool-registry/profiles failed: {e}")
        return api_error("Failed to load profiles", details={"reason": str(e)})
