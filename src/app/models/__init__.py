"""
Database Models for Thesis Research App

This module defines SQLAlchemy models for the thesis research application
that analyzes AI-generated applications across multiple models.

Models include:
- ModelCapability: AI model metadata and capabilities
- PortConfiguration: Docker port allocations
- GeneratedApplication: AI-generated app instances
- SecurityAnalysis: Security analysis results
- PerformanceTest: Performance testing results
- BatchAnalysis: Batch processing records
- AnalyzerConfiguration: Analyzer runtime configuration profiles
- AnalysisTask: Individual analysis tasks with lifecycle tracking
- AnalysisResult: Stored findings from analyzer runs
"""

from __future__ import annotations

# Import centralized constants and enums so they can be accessed from app.models
from ..constants import AnalysisStatus, JobStatus, ContainerState, AnalysisType, JobPriority, SeverityLevel

# Import the database instance
from ..extensions import db

# Import all models from their new locations to make them available under the app.models namespace
from .analysis_models import AnalyzerConfiguration, AnalysisTask, AnalysisResult

# Import other models that were already in __init__.py or are fundamental
from .core import ModelCapability, PortConfiguration, GeneratedApplication, GeneratedCodeResult
from .analysis import SecurityAnalysis, PerformanceTest, ZAPAnalysis, OpenRouterAnalysis
from .container import ContainerizedTest
from .cache import OpenRouterModelCache, ExternalModelInfoCache
from .batch import BatchAnalysis
from .process import ProcessTracking
from .results_cache import AnalysisResultsCache
from .simple_tool_results import ToolResult, ToolSummary
from .user import User
from .report import Report

from ..utils.time import utc_now

# Define what gets imported with a 'from app.models import *'
__all__ = [
    # Enums & Constants
    'AnalysisStatus', 'JobStatus', 'ContainerState', 'AnalysisType', 'JobPriority', 'SeverityLevel',
    
    # DB instance
    'db',

    # Models from current schema
    'AnalyzerConfiguration', 'AnalysisTask', 'AnalysisResult',

    'ModelCapability', 'PortConfiguration', 'GeneratedApplication', 'GeneratedCodeResult',
    'SecurityAnalysis', 'PerformanceTest', 'ZAPAnalysis', 'OpenRouterAnalysis',
    'ContainerizedTest',
    'OpenRouterModelCache', 'ExternalModelInfoCache',
    'BatchAnalysis',
    'ProcessTracking',
    'AnalysisResultsCache',
    'ToolResult', 'ToolSummary',
    'User',
    'Report',

    # Utility function
    'utc_now'
]
