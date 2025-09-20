"""
Analysis Engines Package
========================

Container-based analysis system with tool-based architecture.
Organized by analyzer containers: static, dynamic, ai, and performance.
"""

# Import the orchestrator for easy access
from .orchestrator import AnalysisOrchestrator, get_analysis_orchestrator

# Import base classes and registry
from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolConfig, ToolStatus,
    Severity, Confidence, get_tool_registry, register_tool, analysis_tool
)

# Import container-based tool implementations to trigger registration
from . import static      # Static analyzer container tools  # noqa: F401
from . import dynamic     # Dynamic analyzer container tools  # noqa: F401
from . import ai          # AI analyzer container tools  # noqa: F401
from . import performance # Performance tester container tools  # noqa: F401

__all__ = [
    # Main orchestrator
    'AnalysisOrchestrator',
    'get_analysis_orchestrator',
    
    # Base classes
    'BaseAnalysisTool',
    'ToolResult', 
    'Finding',
    'ToolConfig',
    'ToolStatus',
    'Severity',
    'Confidence',
    
    # Registry functions
    'get_tool_registry',
    'register_tool',
    'analysis_tool'
]