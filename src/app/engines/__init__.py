"""
Analysis Engines Package
========================

New dynamic analysis system with tool-based architecture.
Replaces the old rigid type-based system with flexible tagging.
"""

# Import the orchestrator for easy access
from .orchestrator import AnalysisOrchestrator, get_analysis_orchestrator

# Import base classes and registry
from .base import (
    BaseAnalysisTool, ToolResult, Finding, ToolConfig, ToolStatus,
    Severity, Confidence, get_tool_registry, register_tool, analysis_tool
)

# Import tool implementations to trigger registration
from . import backend_security
from . import frontend_security  
from . import performance

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