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

from ..engines import get_analysis_orchestrator

logger = logging.getLogger(__name__)

__all__ = ['EngineResult', 'UniversalAnalyzerEngine', 'get_engine']


@dataclass
class EngineResult:
    """Standardized wrapper for analysis engine results."""
    status: str
    engine: str
    model_slug: str
    app_number: int
    payload: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the result to a dictionary."""
        return {
            'status': self.status,
            'engine': self.engine,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'payload': self.payload,
            'error': self.error,
        }


class UniversalAnalyzerEngine:
    """
    A single, universal engine that orchestrates analysis tasks based on a
    dynamic list of tools, completely replacing the old type-based system.
    """
    engine_name: str = 'universal'

    def __init__(self):
        self.orchestrator = get_analysis_orchestrator()

    def run(self, model_slug: str, app_number: int, **kwargs) -> EngineResult:
        """
        Executes an analysis by delegating to the central orchestrator.

        Args:
            model_slug: The identifier for the model.
            app_number: The application number.
            **kwargs: Arbitrary keyword arguments, typically including 'tools',
                      passed to the orchestrator.
        """
        try:
            # Ensure results are persisted by default
            kwargs.setdefault('persist', True)
            
            # The orchestrator handles all tool selection and execution
            result = self.orchestrator.run_analysis(
                model_slug=model_slug,
                app_number=app_number,
                **kwargs
            )
            
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
            logger.exception(f"UniversalAnalyzerEngine failed for {model_slug}-{app_number} with tools {kwargs.get('tools')}")
            return EngineResult(
                status='error',
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload={},
                error=str(e)
            )


def get_engine(name: Optional[str] = None) -> UniversalAnalyzerEngine:
    """
    Factory function that always returns an instance of the UniversalAnalyzerEngine.
    The 'name' parameter is ignored to maintain backward compatibility.
    """
    # All analysis types now use the same universal engine.
    return UniversalAnalyzerEngine()
