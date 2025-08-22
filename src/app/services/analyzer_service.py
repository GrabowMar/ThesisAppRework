"""Deprecated AnalyzerService.

This module previously contained a large stub implementation. The standardized
analysis execution path now lives in `analysis_engines.py` and higher-level
workflows integrate through `analysis_service.py` and Celery tasks.

The retained thin wrapper keeps backward compatibility for any lingering
imports while clearly signaling deprecation.
"""
from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional
from flask import Flask

from .analysis_engines import get_engine

DEPRECATION_MESSAGE = (
    "AnalyzerService is deprecated. Use analysis_engines (get_engine) or the "
    "refactored analysis_service utilities."
)


class AnalyzerService:  # pragma: no cover - legacy shim
    def __init__(self, app: Flask):  # noqa: D401
        self.app = app
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)

    def run_security_analysis(self, model_slug: str, app_number: int, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        engine = get_engine('security')
        return engine.run(model_slug, app_number, tools=tools).to_dict()

    def run_performance_test(self, model_slug: str, app_number: int, test_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        engine = get_engine('performance')
        return engine.run(model_slug, app_number, test_config=test_config).to_dict()

    def run_static_analysis(self, model_slug: str, app_number: int, tools: Optional[List[str]] = None) -> Dict[str, Any]:
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        engine = get_engine('static')
        return engine.run(model_slug, app_number, tools=tools).to_dict()

    def run_dynamic_analysis(self, model_slug: str, app_number: int, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        warnings.warn(DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=2)
        engine = get_engine('dynamic')
        return engine.run(model_slug, app_number, options=options).to_dict()

    # Legacy API methods kept as no-ops / simple passthroughs --------------
    def get_analyzer_status(self) -> Dict[str, Any]:  # noqa: D401
        return {'status': 'deprecated', 'message': DEPRECATION_MESSAGE}

    def start_analyzer_containers(self) -> Dict[str, Any]:  # noqa: D401
        return {'status': 'deprecated', 'message': DEPRECATION_MESSAGE}

    def stop_analyzer_containers(self) -> Dict[str, Any]:  # noqa: D401
        return {'status': 'deprecated', 'message': DEPRECATION_MESSAGE}

    def get_analysis_results(self, job_id: str) -> Optional[Dict[str, Any]]:  # noqa: D401
        return None

    def list_analysis_jobs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:  # noqa: D401
        return []
