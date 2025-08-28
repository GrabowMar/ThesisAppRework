"""Analysis Engines
===================

Lightweight, standardized wrappers around concrete analyzer execution paths.

Goals:
 - Provide a consistent run(model_slug, app_number, **kwargs) contract
 - Keep orchestration logic (task dispatch / analyzer_manager bridge) centralized
 - Allow future extension (e.g., AIAnalysis, CompositeAnalysis) without bloating
 - Decouple higher-level services (analysis_service) from specific integration calls

Each engine delegates to the existing AnalyzerIntegration, translating a minimal
set of keyword arguments and normalizing the response schema.

Return Schema (best-effort normalization):
 {
   "status": str,              # running|completed|failed|queued|error
   "engine": str,              # security|performance|static|dynamic
   "model_slug": str,
   "app_number": int,
   "payload": {...},           # raw analyzer integration response
   "error": Optional[str]
 }

This file intentionally avoids importing heavy model modules to keep import
overhead low for route handlers and Celery tasks that only need execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from .analyzer_integration import get_analyzer_integration

__all__ = [
    'BaseAnalyzerEngine', 'SecurityAnalyzerEngine', 'PerformanceAnalyzerEngine',
    'StaticAnalyzerEngine', 'DynamicAnalyzerEngine', 'get_engine', 'ENGINE_REGISTRY'
]


@dataclass
class EngineResult:
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
    """Abstract base for analyzer engines."""
    engine_name: str = 'base'

    def __init__(self):
        self._integration = get_analyzer_integration()

    # Public API -----------------------------------------------------------
    def run(self, model_slug: str, app_number: int, **kwargs) -> EngineResult:
        try:
            raw = self._run_impl(model_slug, app_number, **kwargs) or {}
            status = raw.get('status') or raw.get('state') or 'completed'
            return EngineResult(
                status=status,
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload=raw,
            )
        except Exception as e:  # pragma: no cover - defensive
            return EngineResult(
                status='error',
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload={},
                error=str(e),
            )

    # Internal -------------------------------------------------------------
    def _run_impl(self, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:  # noqa: D401
        """Concrete engines must implement."""
        raise NotImplementedError


class SecurityAnalyzerEngine(BaseAnalyzerEngine):
    engine_name = 'security'

    def _run_impl(self, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:
        tools = kwargs.get('tools')  # optional list
        options = kwargs.get('options')
        return self._integration.run_security_analysis(model_slug, app_number, tools=tools, options=options)


class PerformanceAnalyzerEngine(BaseAnalyzerEngine):
    engine_name = 'performance'

    def _run_impl(self, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:
        test_config = kwargs.get('test_config') or kwargs.get('config')
        return self._integration.run_performance_test(model_slug, app_number, test_config=test_config)


class StaticAnalyzerEngine(BaseAnalyzerEngine):
    engine_name = 'static'

    def _run_impl(self, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:
        tools = kwargs.get('tools')
        options = kwargs.get('options')
        return self._integration.run_static_analysis(model_slug, app_number, tools=tools, options=options)


class DynamicAnalyzerEngine(BaseAnalyzerEngine):
    engine_name = 'dynamic'

    def _run_impl(self, model_slug: str, app_number: int, **kwargs) -> Dict[str, Any]:
        options = kwargs.get('options')
        return self._integration.run_dynamic_analysis(model_slug, app_number, options=options)


# Registry -----------------------------------------------------------------
ENGINE_REGISTRY: Dict[str, Type[BaseAnalyzerEngine]] = {
    'security': SecurityAnalyzerEngine,
    'performance': PerformanceAnalyzerEngine,
    'static': StaticAnalyzerEngine,
    'dynamic': DynamicAnalyzerEngine,
}


def get_engine(name: str) -> BaseAnalyzerEngine:
    """Get an engine instance by name.

    Raises:
        KeyError if engine not registered.
    """
    cls = ENGINE_REGISTRY[name]
    return cls()
