"""
Dynamic Analysis Tools
=====================

Container-based dynamic analysis tools that run in the dynamic-analyzer container.
All tool implementations are now delegated to containerized services.
"""

import logging
from typing import Dict, Any

from .container_tool_registry import (
    get_container_tool_registry,
    AnalyzerContainer,
    container_tool_detail_dict,
    container_tool_summary_dict,
)

try:
    from app.services.analysis_engines import DynamicAnalysisEngine as _DynamicAnalysisEngine  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _DynamicAnalysisEngine = None  # type: ignore

logger = logging.getLogger(__name__)


def get_dynamic_analyzer_tools() -> Dict[str, Any]:
    """Get all dynamic analyzer tools from the container registry."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.DYNAMIC)
    
    return {
        'tools': [tool.name for tool in tools],
        'tool_details': {tool.name: container_tool_summary_dict(tool) for tool in tools}
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
    
    return container_tool_detail_dict(tool)


if _DynamicAnalysisEngine is not None:
    class DynamicAnalysisEngine(_DynamicAnalysisEngine):  # type: ignore[misc]
        """Compatibility wrapper mirroring the legacy class location."""

        def analyze_runtime_behavior(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy analyze_runtime_behavior is no longer supported; use run() with orchestrator tags")

        def profile_memory(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy profile_memory is no longer supported; use run() with orchestrator tags")
else:  # pragma: no cover
    class DynamicAnalysisEngine:
        """Stub implementation used when analysis engines are unavailable."""

        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def analyze_runtime_behavior(self, *args, **kwargs):
            raise NotImplementedError("Dynamic analysis orchestrator unavailable in this environment")

        def profile_memory(self, *args, **kwargs):
            raise NotImplementedError("Dynamic analysis orchestrator unavailable in this environment")


__all__ = ['get_dynamic_analyzer_tools', 'get_available_dynamic_tools', 'get_dynamic_tool_info', 'DynamicAnalysisEngine']


