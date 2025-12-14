"""Legacy Tool Registry shim routes.

These endpoints exist for backward compatibility with clients that still call the
former ``/api/tool-registry/*`` paths. They now proxy to the consolidated
``/api/container-tools`` handlers so the authoritative logic lives in a single
place.
"""

from __future__ import annotations

from typing import Any, Tuple

from flask import Blueprint, current_app

from .common import api_success, api_error

tool_registry_bp = Blueprint('tool_registry', __name__)


def _call_container_endpoint(endpoint_name: str, *args: Any, **kwargs: Any) -> Tuple[dict[str, Any], int]:
    """Invoke a handler from the container tools blueprint and return its payload."""
    view_name = f'container_tools.{endpoint_name}'
    view_func = current_app.view_functions.get(view_name)
    if view_func is None:
        raise LookupError(f"Container tools endpoint '{endpoint_name}' is not registered")

    response = view_func(*args, **kwargs)

    if isinstance(response, tuple):
        response_obj, status_code = response
    else:
        response_obj = response
        status_code = response.status_code

    payload = response_obj.get_json() if hasattr(response_obj, 'get_json') else response_obj
    return payload or {}, status_code


@tool_registry_bp.route('/tool-registry/tools')
def api_tool_registry_tools():
    """Return all tools via the unified container tools endpoint."""
    try:
        payload, status_code = _call_container_endpoint('get_all_tools')
    except LookupError as err:
        current_app.logger.error(f"Container tools endpoint not available: {err}")
        return api_error("Container tool registry is not available", status=503)
    except Exception as err:  # pragma: no cover - unexpected failure
        current_app.logger.exception("Unexpected error invoking container tools endpoint", exc_info=err)
        return api_error("Failed to load tools", status=500)

    if status_code >= 400 or not payload.get('success', True):
        message = payload.get('error') or 'Failed to load tools'
        return api_error(message, status=status_code)

    tools_list = []
    for idx, tool in enumerate(payload.get('data', [])):
        tags = set(tool.get('tags') or [])
        tools_list.append({
            'id': idx + 1,
            'name': tool.get('name'),
            'display_name': tool.get('display_name'),
            'description': tool.get('description'),
            'container': tool.get('container'),
            'available': tool.get('available', True),
            'enabled': tool.get('available', True),
            'category': 'security' if 'security' in tags else 'quality'
        })

    return api_success(tools_list)