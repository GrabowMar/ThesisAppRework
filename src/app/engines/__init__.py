"""
Analysis Engines Package
========================

Container-based analysis system with tool-based architecture.
Organized by analyzer containers: static, dynamic, ai, and performance.
"""

# Import the orchestrator for easy access
from .orchestrator import AnalysisOrchestrator, get_analysis_orchestrator, reset_analysis_orchestrator

# Import container-based tool registry
from .container_tool_registry import get_container_tool_registry, AnalyzerContainer, ContainerTool

# Import container-based tool implementations


__all__ = [
    # Main orchestrator
    'AnalysisOrchestrator',
    'get_analysis_orchestrator',
    'reset_analysis_orchestrator',
    
    # Container-based registry
    'get_container_tool_registry',
    'AnalyzerContainer',
    'ContainerTool'
]