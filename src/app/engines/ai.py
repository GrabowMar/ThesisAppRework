"""
AI Analysis Tools
================

Container-based AI analysis tools that run in the ai-analyzer container.
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
    from app.services.analysis_engines import AIAnalysisEngine as _AIAnalysisEngine  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    _AIAnalysisEngine = None  # type: ignore

logger = logging.getLogger(__name__)


def get_ai_analyzer_tools() -> Dict[str, Any]:
    """Get all AI analyzer tools from the container registry."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.AI)
    
    return {
        'tools': [tool.name for tool in tools],
        'tool_details': {tool.name: container_tool_summary_dict(tool) for tool in tools}
    }


def get_available_ai_tools() -> list[str]:
    """Get list of available AI analysis tool names."""
    registry = get_container_tool_registry()
    tools = registry.get_tools_by_container(AnalyzerContainer.AI)
    return [tool.name for tool in tools if tool.available]


def get_ai_tool_info(tool_name: str) -> Dict[str, Any]:
    """Get detailed information about a specific AI tool."""
    registry = get_container_tool_registry()
    tool = registry.get_tool(tool_name)
    
    if not tool or tool.container != AnalyzerContainer.AI:
        return {}
    
    return container_tool_detail_dict(tool)


if _AIAnalysisEngine is not None:
    class AIAnalysisEngine(_AIAnalysisEngine):  # type: ignore[misc]
        """Compatibility wrapper mirroring the legacy class location."""

        def review_code(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy review_code is no longer supported; use run() with orchestrator tags")

        def suggest_improvements(self, *args, **kwargs):  # type: ignore[override]
            raise NotImplementedError("Legacy suggest_improvements is no longer supported; use run() with orchestrator tags")
else:  # pragma: no cover
    class AIAnalysisEngine:
        """Stub implementation used when analysis engines are unavailable."""

        def __init__(self, *args, **kwargs) -> None:
            self.args = args
            self.kwargs = kwargs

        def review_code(self, *args, **kwargs):
            raise NotImplementedError("AI analysis orchestrator unavailable in this environment")

        def suggest_improvements(self, *args, **kwargs):
            raise NotImplementedError("AI analysis orchestrator unavailable in this environment")


__all__ = ['get_ai_analyzer_tools', 'get_available_ai_tools', 'get_ai_tool_info', 'AIAnalysisEngine']