"""Analysis Engines - Compatibility Layer
========================================

Compatibility layer for the new dynamic analysis system.
Maintains backward compatibility while transitioning to the new tool-based architecture.

Goals:
 - Provide a consistent run(model_slug, app_number, **kwargs) contract
 - Bridge old engine interface to new orchestrator system
 - Support gradual migration from type-based to tag-based analysis
 - Maintain existing API contracts during transition

Return Schema (standardized):
 {
   "status": str,              # running|completed|failed|queued|error
   "engine": str,              # security|performance|static|dynamic
   "model_slug": str,
   "app_number": int,
   "payload": {...},           # orchestrator response
   "error": Optional[str]
 }
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

# Import new analysis system
from ..engines import get_analysis_orchestrator

logger = logging.getLogger(__name__)

__all__ = [
    'EngineResult', 'BaseAnalyzerEngine', 'SecurityAnalyzerEngine', 
    'PerformanceAnalyzerEngine', 'StaticAnalyzerEngine', 'DynamicAnalyzerEngine',
    'get_engine', 'ENGINE_REGISTRY'
]


@dataclass
class EngineResult:
    """Compatibility wrapper for engine results."""
    status: str
    engine: str
    model_slug: str
    app_number: int
    payload: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'status': self.status,
            'engine': self.engine,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'payload': self.payload,
            'error': self.error,
        }


class BaseAnalyzerEngine:
    """Base class for compatibility engines."""
    engine_name: str = 'base'

    def __init__(self):
        self.orchestrator = get_analysis_orchestrator()

    def run(self, model_slug: str, app_number: int, **kwargs) -> EngineResult:
        """Run analysis using new orchestrator system."""
        try:
            # Determine analysis type based on engine
            tags = getattr(self, '_analysis_tags', set())
            if tags:
                result = self.orchestrator.run_tagged_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    tags=tags,
                    **kwargs
                )
            else:
                result = self.orchestrator.run_analysis(
                    model_slug=model_slug,
                    app_number=app_number,
                    **kwargs
                )
            
            # Convert to old format
            status = 'completed' if result.get('success') else 'failed'
            error = result.get('error') if not result.get('success') else None
            
            return EngineResult(
                status=status,
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload=result,
                error=error
            )
            
        except Exception as e:
            logger.error(f"Engine {self.engine_name} failed: {e}")
            return EngineResult(
                status='error',
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload={},
                error=str(e)
            )


class SecurityAnalyzerEngine(BaseAnalyzerEngine):
    """Security analysis engine - routes to security tools."""
    engine_name = 'security'
    _analysis_tags = {'security'}


class PerformanceAnalyzerEngine(BaseAnalyzerEngine):
    """Performance analysis engine - routes to performance tools."""
    engine_name = 'performance'
    _analysis_tags = {'performance'}


class StaticAnalyzerEngine(BaseAnalyzerEngine):
    """Static analysis engine - routes to static analysis tools."""
    engine_name = 'static'
    _analysis_tags = {'static', 'quality'}


class DynamicAnalyzerEngine(BaseAnalyzerEngine):
    """Dynamic analysis engine - routes to dynamic analysis tools."""
    engine_name = 'dynamic'
    _analysis_tags = {'dynamic', 'security'}


# Registry for backward compatibility
ENGINE_REGISTRY: Dict[str, type] = {
    'security': SecurityAnalyzerEngine,
    'performance': PerformanceAnalyzerEngine,
    'static': StaticAnalyzerEngine,
    'dynamic': DynamicAnalyzerEngine,
}


def get_engine(name: str) -> BaseAnalyzerEngine:
    """Get an engine instance by name."""
    if name not in ENGINE_REGISTRY:
        raise KeyError(f"Engine '{name}' not found. Available engines: {list(ENGINE_REGISTRY.keys())}")
    
    cls = ENGINE_REGISTRY[name]
    return cls()
