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

from app.services import analysis_result_store

# Import new analysis system
from ..engines import get_analysis_orchestrator

logger = logging.getLogger(__name__)

__all__ = [
    'EngineResult', 'BaseAnalyzerEngine', 'SecurityAnalyzerEngine', 
    'PerformanceAnalyzerEngine', 'StaticAnalyzerEngine', 'DynamicAnalyzerEngine',
    'AIAnalyzerEngine', 'StaticAnalysisEngine', 'PerformanceAnalysisEngine',
    'DynamicAnalysisEngine', 'AIAnalysisEngine', 'get_engine', 'ENGINE_REGISTRY'
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
            # Filter tools to only those that match this engine's tags
            tools = kwargs.get('tools', [])
            analysis_tags = getattr(self, '_analysis_tags', set())
            if tools and analysis_tags:
                filtered_tools = self._filter_tools_by_tags(tools, analysis_tags)
                if filtered_tools != tools:
                    logger.info(f"Engine {self.engine_name}: filtered tools from {tools} to {filtered_tools}")
                    kwargs = kwargs.copy()  # Don't modify original
                    kwargs['tools'] = filtered_tools
            
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
    
    def _filter_tools_by_tags(self, tools: list[str], required_tags: set[str]) -> list[str]:
        """Filter tools to only those that belong to this engine's primary container."""
        from ..engines.unified_registry import get_unified_tool_registry
        unified = get_unified_tool_registry()

        # Map engine types to their primary container name strings
        engine_containers = {
            'SecurityAnalyzerEngine': 'static-analyzer',
            'PerformanceAnalyzerEngine': 'performance-tester',
            'StaticAnalyzerEngine': 'static-analyzer',
            'DynamicAnalyzerEngine': 'dynamic-analyzer',
            'AIAnalyzerEngine': 'ai-analyzer'
        }

        expected_container = engine_containers.get(self.__class__.__name__)
        if not expected_container:
            # Fallback to tag-based filtering
            filtered: list[str] = []
            for tool_name in tools:
                ut = unified.get(tool_name)
                if ut and ut.tags.intersection(required_tags):
                    filtered.append(tool_name)
                else:
                    logger.debug(
                        "Tool %s filtered out: tags %s don't match required %s", tool_name, ut.tags if ut else 'unknown', required_tags
                    )
            return filtered

        filtered: list[str] = []
        for tool_name in tools:
            ut = unified.get(tool_name)
            if ut and ut.container == expected_container:
                filtered.append(tool_name)
            else:
                logger.debug(
                    "Tool %s filtered out: container %s doesn't match required %s", tool_name, ut.container if ut else 'unknown', expected_container
                )
        return filtered


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


class AIAnalyzerEngine(BaseAnalyzerEngine):
    """AI analysis engine - routes to AI-powered analysis tools."""
    engine_name = 'ai'
    _analysis_tags = {'ai', 'requirements'}

    def run(self, model_slug: str, app_number: int, **kwargs) -> EngineResult:  # type: ignore[override]
        """Override to always delegate directly to ai-analyzer container.

        Rationale:
        The generic BaseAnalyzerEngine.run path uses the dynamic orchestrator which
        consults the legacy (non-container) tool registry for availability. Since
        `requirements-scanner` only exists in the container registry, availability
        checks can prevent delegation and silently drop the tool (especially inside
        unified analyses), resulting in no ai-analyzer result directory being
        created even though the tool name appears in `tools_used`.

        This override guarantees:
        1. We always call the analyzer integration bridge for AI tools.
        2. We default to ['requirements-scanner'] when no explicit tools provided.
        3. We persist a result file under project-root results/<model>/appN/ai-analyzer/.
        4. We return an EngineResult payload shaped similarly to orchestrator outputs
           so downstream task code can aggregate uniformly.
        """
        try:
            # Extract requested tools (may be list of names or absent)
            tools = kwargs.get('tools') or ['requirements-scanner']
            if not isinstance(tools, list):  # Defensive: normalize
                tools = ['requirements-scanner']
            try:
                logger.info(f"AIAnalyzerEngine: starting AI run model={model_slug} app={app_number} raw_tools={tools}")
            except Exception:
                pass

            # Ensure canonical naming / de-aliasing
            canonical_map = {
                'requirements-analyzer': 'requirements-scanner',
                'ai-requirements': 'requirements-scanner'
            }
            normalized_tools = []
            for t in tools:
                if isinstance(t, str) and t.strip():
                    key = t.strip().lower()
                    normalized_tools.append(canonical_map.get(key, key))
            if not normalized_tools:
                normalized_tools = ['requirements-scanner']

            # Delegate directly via analyzer bridge (subprocess -> websocket pipeline)
            from app.services import analyzer_integration as analyzer_bridge  # lazy import to avoid cycles
            bridge_result = analyzer_bridge.analysis_executor.run_ai_analysis(
                model_slug, app_number, tools=normalized_tools
            )

            try:
                logger.debug(
                    "AIAnalyzerEngine: bridge_result keys=%s status=%s", 
                    list(bridge_result.keys()) if isinstance(bridge_result, dict) else 'non-dict',
                    bridge_result.get('status') if isinstance(bridge_result, dict) else 'n/a'
                )
            except Exception:
                pass

            # bridge_result already in transformed shape from _transform_analyzer_output_to_task_format
            tool_results = bridge_result.get('tool_results', {}) if isinstance(bridge_result, dict) else {}
            tools_requested = bridge_result.get('tools_requested', normalized_tools)

            if not tool_results:
                logger.warning(
                    "AIAnalyzerEngine: empty tool_results from bridge (tools_requested=%s). Original output keys=%s", 
                    tools_requested,
                    list(bridge_result.keys()) if isinstance(bridge_result, dict) else 'non-dict'
                )

            # Basic success heuristic: at least one tool executed with status success
            success = any(isinstance(r, dict) and r.get('status') == 'success' for r in tool_results.values())

            # Build orchestrator-style payload
            payload = {
                'success': success,
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_duration': bridge_result.get('analysis_duration'),
                'tools_requested': tools_requested,
                'tools_successful': sum(1 for r in tool_results.values() if r.get('status') == 'success'),
                'tools_failed': sum(1 for r in tool_results.values() if r.get('status') not in ('success', 'completed')),
                'tool_results': tool_results,
                'raw_outputs': bridge_result.get('original_analyzer_output', {}),  # preserve raw for debugging
                'summary': {  # Minimal summary (AI findings currently encoded in tool raw output)
                    'total_findings': sum(r.get('total_issues', 0) for r in tool_results.values()),
                    'tool_status': {k: v.get('status') for k, v in tool_results.items()}
                },
                'findings': [],  # Placeholder: AI requirement deltas could be mapped here in future
                'metadata': {
                    'analysis_timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                    'orchestrator_version': '2.0.0',
                    'engine': 'ai',
                    'delegated': True
                }
            }

            # Persist results using the SQL-backed result store when requested
            persist = kwargs.get('persist', True)
            task_id = kwargs.get('task_id')
            if persist:
                if task_id:
                    try:
                        stored = analysis_result_store.persist_analysis_payload_by_task_id(task_id, payload)
                        if not stored:
                            logger.debug(
                                "AIAnalyzerEngine: no AnalysisTask row found for task_id=%s; skipping persistence",
                                task_id,
                            )
                    except Exception as exc:  # pragma: no cover - persistence failures shouldn't abort
                        logger.warning(
                            "AIAnalyzerEngine: database persistence failed for task %s: %s",
                            task_id,
                            exc,
                        )
                else:
                    logger.debug(
                        "AIAnalyzerEngine: persistence requested but no task_id provided (model=%s app=%s)",
                        model_slug,
                        app_number,
                    )

            return EngineResult(
                status='completed' if success else 'failed',
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload=payload,
                error=None if success else 'ai_tool_execution_failed'
            )
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"AIAnalyzerEngine override failed: {e}")
            return EngineResult(
                status='error',
                engine=self.engine_name,
                model_slug=model_slug,
                app_number=app_number,
                payload={},
                error=str(e)
            )


# Registry for backward compatibility
ENGINE_REGISTRY: Dict[str, type] = {
    'security': SecurityAnalyzerEngine,
    'performance': PerformanceAnalyzerEngine,
    'static': StaticAnalyzerEngine,
    'dynamic': DynamicAnalyzerEngine,
    'ai': AIAnalyzerEngine,
}

# Backwards-compatible aliases expected by legacy imports/tests
StaticAnalysisEngine = StaticAnalyzerEngine
PerformanceAnalysisEngine = PerformanceAnalyzerEngine
DynamicAnalysisEngine = DynamicAnalyzerEngine
AIAnalysisEngine = AIAnalyzerEngine


def get_engine(name: str) -> BaseAnalyzerEngine:
    """Get an engine instance by name."""
    if name not in ENGINE_REGISTRY:
        raise KeyError(f"Engine '{name}' not found. Available engines: {list(ENGINE_REGISTRY.keys())}")
    
    cls = ENGINE_REGISTRY[name]
    return cls()
