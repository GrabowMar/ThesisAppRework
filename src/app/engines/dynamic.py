"""
Dynamic Analysis Tools
=====================

Container-based dynamic analysis tools that run in the dynamic-analyzer container.
All tool implementations are now delegated to containerized services.
"""

import logging
from typing import Dict, Any

from .container_tool_registry import get_container_tool_registry, AnalyzerContainer

logger = logging.getLogger(__name__)


def get_dynamic_analyzer_tools() -> Dict[str, Any]:
    """Get all dynamic analyzer tools from the container registry."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.DYNAMIC)
    
    return {
        'tools': [tool.name for tool in tools],
        'tool_details': {tool.name: {
            'name': tool.name,
            'display_name': tool.display_name,
            'description': tool.description,
            'tags': list(tool.tags),
            'supported_languages': list(tool.supported_languages),
            'available': tool.available,
            'version': tool.version,
            'config_schema': tool.config_schema
        } for tool in tools}
    }


def get_available_dynamic_tools() -> list[str]:
    """Get list of available dynamic analysis tool names."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.DYNAMIC)
    return [tool.name for tool in tools if tool.available]


def get_dynamic_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific dynamic tool."""
    registry = get_container_tool_registry()
    tool = registry.get_tool(tool_name)
    
    if not tool or tool.container != AnalyzerContainer.DYNAMIC:
        return {}
    
    return {
        'name': tool.name,
        'display_name': tool.display_name,
        'description': tool.description,
        'container': tool.container.value,
        'tags': list(tool.tags),
        'supported_languages': list(tool.supported_languages),
        'available': tool.available,
        'version': tool.version,
        'cli_flags': tool.cli_flags,
        'output_formats': tool.output_formats,
        'config_schema': tool.config_schema
    }


