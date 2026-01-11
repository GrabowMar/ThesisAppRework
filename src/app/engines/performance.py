"""
Performance Analysis Tools
=========================

Container-based performance testing tools that run in the performance-tester container.
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
    from app.services.analysis_engines import PerformanceAnalysisEngine as _PerformanceAnalysisEngine  # type: ignore[attr-defined]
except Exception:  # pragma: no cover - fallback when services unavailable
    _PerformanceAnalysisEngine = None  # type: ignore

logger = logging.getLogger(__name__)


def get_performance_analyzer_tools() -> Dict[str, Any]:
    """Get all performance analyzer tools from the container registry."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.PERFORMANCE)
    
    return {
        'tools': [tool.name for tool in tools],
        'tool_details': {tool.name: container_tool_summary_dict(tool) for tool in tools}
    }


def get_available_performance_tools() -> list[str]:
    """Get list of available performance testing tool names."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.PERFORMANCE)
    return [tool.name for tool in tools if tool.available]


def get_performance_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific performance tool."""
    registry = get_container_tool_registry()
    tool = registry.get_tool(tool_name)
    
    if not tool or tool.container != AnalyzerContainer.PERFORMANCE:
        return {}
    
    return container_tool_detail_dict(tool)


if _PerformanceAnalysisEngine is not None:
    class PerformanceAnalysisEngine(_PerformanceAnalysisEngine):  # type: ignore[misc]
        """Compatibility wrapper mirroring the legacy class location."""

        def run_load_test(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy run_load_test is no longer supported; use run() with orchestrator tags")

        def measure_response_time(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy measure_response_time is no longer supported; use run() with orchestrator tags")
else:  # pragma: no cover - fallback during docs/static analysis builds
    class PerformanceAnalysisEngine:  # type: ignore[too-many-ancestors]
        """Stub implementation used when analysis engines are unavailable."""

        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def run_load_test(self, *args, **kwargs):
            raise NotImplementedError("Performance analysis orchestrator unavailable in this environment")

        def measure_response_time(self, *args, **kwargs):
            raise NotImplementedError("Performance analysis orchestrator unavailable in this environment")


__all__ = ['get_performance_analyzer_tools', 'get_available_performance_tools', 'get_performance_tool_info', 'PerformanceAnalysisEngine']


