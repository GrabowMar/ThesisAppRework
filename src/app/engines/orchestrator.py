"""
Dynamic Analysis Orchestrator
============================

Orchestrates analysis runs using the new dynamic tool system.
Replaces the old rigid type-based analysis engines.
"""

import json
import logging
import asyncio
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import (
    ToolConfig, Finding, ToolStatus, parse_file_extensions
)
from .unified_registry import get_unified_tool_registry
from ..utils.json_results_manager import JsonResultsManager
from ..utils.helpers import get_app_directory
from ..paths import GENERATED_APPS_DIR, PROJECT_ROOT
from ..extensions import get_components, get_analyzer_integration
import socket

logger = logging.getLogger(__name__)


def _freeze_for_dedup(value: Any) -> str:
    """Create a stable representation for deduplication comparisons."""
    try:
        return json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return repr(value)


def _deduplicate_nested(value: Any) -> Any:
    """Recursively remove duplicate entries from nested lists while preserving order."""
    if isinstance(value, list):
        seen = set()
        deduped: List[Any] = []
        for item in value:
            normalized = _deduplicate_nested(item)
            key = _freeze_for_dedup(normalized)
            if key not in seen:
                seen.add(key)
                deduped.append(normalized)
        return deduped
    if isinstance(value, dict):
        return {k: _deduplicate_nested(v) for k, v in value.items()}
    return value


class AnalysisOrchestrator:
    """Orchestrates analysis runs using dynamic tool selection."""
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize analysis orchestrator.
        
        Args:
            base_path: Base path for results storage (deprecated, will use PROJECT_ROOT)
        """
        # Unified registry provides canonical tool metadata & availability
        self.unified = get_unified_tool_registry()
        # Always use PROJECT_ROOT to ensure consistent results location
        self.base_path = PROJECT_ROOT
        # Store under project-root results directory
        self.results_manager = JsonResultsManager(PROJECT_ROOT / "results", "analysis")
        
    def discover_tools(self) -> Dict[str, Any]:
        """Unified discovery report."""
        info = self.unified.info_summary()
        return {
            'unified': info,
            'tools': self.unified.list_tools_detailed()
        }
    
    def get_tools_for_context(
        self,
        target_path: Path,
        tags: Optional[Set[str]] = None,
        languages: Optional[Set[str]] = None
    ) -> List[str]:
        """
        Get recommended tools for analysis context.
        
        Args:
            target_path: Path to analyze
            tags: Desired tool tags
            languages: Target languages
            
        Returns:
            List of recommended tool names
        """
        recommended_tools = set()
        
        # Auto-detect languages if not provided
        if languages is None:
            languages = self._detect_languages(target_path)
        
        # Tools by language
        for language in languages:
            recommended_tools.update(self.unified.by_language(language))
        # Tools by tags
        if tags:
            recommended_tools.update(self.unified.by_tags(tags))
        # Filter to available (unified metadata has availability flag)
        filtered: List[str] = []
        for t in recommended_tools:
            ut = self.unified.get(t)
            if ut and getattr(ut, 'available', False):
                filtered.append(t)
        return filtered
    
    def run_analysis(
        self,
        model_slug: str,
        app_number: int,
        target_path: Optional[Path] = None,
        tools: Optional[List[str]] = None,
        tags: Optional[Set[str]] = None,
        tool_configs: Optional[Dict[str, Dict[str, Any]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run analysis with dynamic tool selection.
        
        Args:
            model_slug: Model identifier
            app_number: App number
            target_path: Path to analyze (optional, will be derived)
            tools: Specific tools to run (optional)
            tags: Tool tags to filter by (optional)
            tool_configs: Per-tool configuration overrides
            **kwargs: Additional parameters passed to tools
            
        Returns:
            Comprehensive analysis results
        """
        start_time = __import__('time').time()
        
        logger.info(
            "[ORCH] Starting run_analysis: model=%s, app=%s, tools=%s, tags=%s, target_path=%s",
            model_slug, app_number, tools, tags, target_path
        )
        
        try:
            # Resolve target path
            if target_path is None:
                logger.debug("[ORCH] Target path not provided, resolving...")
                target_path = self._resolve_target_path(model_slug, app_number)
                logger.info("[ORCH] Resolved target_path: %s", target_path)
            else:
                logger.debug("[ORCH] Using provided target_path: %s", target_path)
            
            if not target_path.exists():
                error_msg = f"Target path does not exist: {target_path}"
                logger.error(
                    "[ORCH] PATH VALIDATION FAILED - %s (model=%s, app=%s)",
                    error_msg, model_slug, app_number
                )
                return {
                    'success': False,
                    'error': error_msg,
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            logger.info("[ORCH] Path validation SUCCESS: %s exists", target_path)
            
            # Determine tools to run
            if tools is None:
                logger.debug("[ORCH] No tools provided, detecting from context...")
                tools = self.get_tools_for_context(target_path, tags)
                logger.info("[ORCH] Context-detected tools: %s", tools)

            logger.info("[ORCH] Initial tools (before normalization): %s, tags=%s", tools, tags)

            # Alias resolution via unified registry
            tools = self.unified.resolve(tools or [])
            
            logger.info("[ORCH] Normalized tools (after alias resolution): %s", tools)
            
            if not tools:
                return {
                    'success': False,
                    'error': "No suitable tools found for analysis",
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'target_path': str(target_path)
                }
            
            # Run tools (with container delegation when available)
            tool_results: Dict[str, Any] = {}
            all_findings: List[Finding] = []
            successful_tools = 0
            failed_tools = 0

            # Determine local availability and group by service
            service_groups: Dict[str, List[str]] = {}
            service_for_tool: Dict[str, Optional[str]] = {}

            logger.debug("[ORCH] Grouping tools by service for delegation...")
            for tool_name in tools:
                ut = self.unified.get(tool_name)
                svc = self._map_tool_to_service(tool_name)
                service_for_tool[tool_name] = svc
                if svc:
                    service_groups.setdefault(svc, []).append(tool_name)
            
            logger.info(
                "[ORCH] Service groups: %s (total_services=%s, total_tools=%s)",
                {k: len(v) for k, v in service_groups.items()},
                len(service_groups), len(tools)
            )

            # Decide delegation: unified model delegates any tool whose container != 'local'
            delegated_tools: Set[str] = set()
            for svc, svc_tools in service_groups.items():
                service_up = self._analyzer_service_up(svc)
                logger.info(
                    "[ORCH] Service %s: up=%s, tools=%s",
                    svc, service_up, svc_tools
                )
                if service_up:
                    # Delegate this group to analyzer containers
                    logger.info(
                        "[ORCH] DELEGATING to container: service=%s, model=%s, app=%s, tools=%s",
                        svc, model_slug, app_number, svc_tools
                    )
                    try:
                        svc_result = self._run_via_container(svc, model_slug, app_number, svc_tools)
                        logger.debug(
                            "[ORCH] Container %s returned: success=%s, has_data=%s",
                            svc, svc_result.get('success'), bool(svc_result.get('data'))
                        )
                        extracted, svc_findings = self._extract_container_tool_results(svc, svc_result, svc_tools)
                        tool_results.update(extracted)
                        all_findings.extend(svc_findings)
                        for t in svc_tools:
                            delegated_tools.add(t)
                            status = (extracted.get(t, {}) or {}).get('status', '')
                            if status and status.startswith('❌'):
                                failed_tools += 1
                            else:
                                successful_tools += 1
                    except Exception as e:
                        logger.warning(
                            "[ORCH] Container delegation FAILED for %s: %s",
                            svc, e, exc_info=True
                        )
                        # Mark tools as not available to preserve previous behavior
                        for t in svc_tools:
                            if t not in tool_results:
                                tool_results[t] = {
                                    'status': ToolStatus.NOT_AVAILABLE.value,
                                    'error': f'Container delegation failed: {str(e)}'
                                }
                                failed_tools += 1
                else:
                    logger.info(f"Not delegating tools {svc_tools} to {svc}: service_up={service_up}")

            # Run remaining tools locally
            # Local execution path now only for legacy 'local' tools (if any)
            for tool_name in tools:
                if tool_name in delegated_tools:
                    continue
                ut = self.unified.get(tool_name)
                if not ut or ut.container != 'local':
                    continue  # skip, handled by container
                logger.info(f"Running local legacy tool: {tool_name}")
                try:
                    # Legacy execution path (optional): reuse old registry if still needed
                    from .base import get_tool_registry
                    legacy = get_tool_registry()
                    config = self._build_tool_config(tool_name, tool_configs)
                    tool = legacy.get_tool(tool_name, config)
                    if not tool or not tool.is_available():
                        tool_results[tool_name] = {
                            'status': ToolStatus.NOT_AVAILABLE.value,
                            'error': 'Legacy tool unavailable'
                        }
                        failed_tools += 1
                        continue
                    result = tool.run_analysis(target_path, **kwargs)
                    tool_results[tool_name] = result.to_dict()
                    all_findings.extend(result.findings)
                    successful_tools += 1
                except Exception as e:
                    logger.exception(f"Legacy tool error {tool_name}: {e}")
                    tool_results[tool_name] = {'status': ToolStatus.ERROR.value, 'error': str(e)}
                    failed_tools += 1
            
            # Build comprehensive results with raw outputs preserved
            raw_tool_outputs: Dict[str, Any] = {}
            for tool_name, tool_result in tool_results.items():
                if isinstance(tool_result, dict):
                    # Extract any raw output fields from tool results
                    output_data: Dict[str, Any] = {}
                    for field in ['raw_output', 'output', 'stdout', 'stderr', 'command_line', 'exit_code', 'error']:
                        if field in tool_result and tool_result[field] is not None:
                            output_data[field] = tool_result[field]
                    if output_data:
                        raw_tool_outputs[tool_name] = _deduplicate_nested(output_data)

            deduped_tool_results: Dict[str, Any] = {}
            for tool_name, tool_result in tool_results.items():
                if isinstance(tool_result, dict):
                    deduped_tool_results[tool_name] = _deduplicate_nested(tool_result)
                else:
                    deduped_tool_results[tool_name] = tool_result

            tool_results = deduped_tool_results
            raw_tool_outputs = _deduplicate_nested(raw_tool_outputs)

            finding_dicts = [_deduplicate_nested(f.to_dict()) for f in all_findings]
            finding_dicts = _deduplicate_nested(finding_dicts)

            results = {
                'success': True,
                'model_slug': model_slug,
                'app_number': app_number,
                'target_path': str(target_path),
                'analysis_duration': __import__('time').time() - start_time,
                'tools_requested': tools,
                'tools_successful': successful_tools,
                'tools_failed': failed_tools,
                'tool_results': tool_results,
                'raw_outputs': raw_tool_outputs,  # NEW: Include raw outputs at top level
                'summary': self._build_summary(all_findings, tool_results),
                'findings': finding_dicts,
                'metadata': {
                    'analysis_timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                    'detected_languages': list(self._detect_languages(target_path)),
                    'file_count': len(list(target_path.rglob('*'))),
                    'orchestrator_version': '2.0.0'
                }
            }
            
            # Save results unless caller suppressed persistence (used by unified aggregation)
            persist = kwargs.get('persist', True)
            # ALWAYS write per-service files for debugging (override env var)
            single_file_mode = False  # CHANGED: Force file writes even if env says otherwise
            if persist and not single_file_mode:
                try:
                    # Determine analysis type based on tools used
                    used_services = {self._map_tool_to_service(t) for t in tools if self._map_tool_to_service(t)}
                    analysis_type = 'comprehensive' if len(used_services) > 1 else (next(iter(used_services)) if used_services else 'analysis')
                    self.results_manager.save_results(
                        model_slug,
                        app_number,
                        results,
                        analysis_type=analysis_type
                    )
                except Exception as e:
                    logger.warning(f"Failed to save results: {e}")
            
            return results
            
        except Exception as e:
            logger.exception(f"Analysis orchestration failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_duration': __import__('time').time() - start_time
            }
    
    def run_tagged_analysis(
        self,
        model_slug: str,
        app_number: int,
        tags: Set[str],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Run analysis for specific tags (e.g., 'security', 'performance').
        
        Args:
            model_slug: Model identifier
            app_number: App number
            tags: Required tool tags
            **kwargs: Additional parameters
            
        Returns:
            Analysis results for tagged tools
        """
        return self.run_analysis(
            model_slug=model_slug,
            app_number=app_number,
            tags=tags,
            **kwargs
        )
    
    def run_security_analysis(
        self,
        model_slug: str,
        app_number: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Run security-focused analysis."""
        return self.run_tagged_analysis(
            model_slug=model_slug,
            app_number=app_number,
            tags={'security'},
            **kwargs
        )
    
    def run_performance_analysis(
        self,
        model_slug: str,
        app_number: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Run performance-focused analysis."""
        return self.run_tagged_analysis(
            model_slug=model_slug,
            app_number=app_number,
            tags={'performance'},
            **kwargs
        )
    
    def run_quality_analysis(
        self,
        model_slug: str,
        app_number: int,
        **kwargs
    ) -> Dict[str, Any]:
        """Run code quality analysis."""
        return self.run_tagged_analysis(
            model_slug=model_slug,
            app_number=app_number,
            tags={'quality'},
            **kwargs
        )
    
    def get_analysis_results(
        self,
        model_slug: str,
        app_number: int,
        analysis_type: str = 'comprehensive'
    ) -> Optional[Dict[str, Any]]:
        """Load saved analysis results."""
        return self.results_manager.load_results(
            model_slug,
            app_number
        )
    
    def list_analysis_results(
        self,
        model_slug: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List available analysis results."""
        return self.results_manager.list_available_results(model_slug)
    
    # Private methods
    def _analyzer_service_up(self, service_name: str) -> bool:
        """Check if an analyzer container service is reachable on localhost."""
        ports = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002,
            'performance-tester': 2003,
            'ai-analyzer': 2004,
        }
        port = ports.get(service_name)
        if not port:
            return False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.5)
                return s.connect_ex(('localhost', port)) == 0
        except Exception:
            return False

    def _map_tool_name_to_dynamic_registry(self, tool_name: str) -> str:
        """Map database tool names to dynamic registry tool names."""
        name_mapping = {
            'locust-performance': 'locust',
            'ab-load-test': 'apache-bench',
            'zap-baseline': 'zap',
            'requirements-analyzer': 'requirements-scanner',
            'ai-requirements': 'requirements-scanner',
            # Add other mappings as needed
        }
        return name_mapping.get(tool_name, tool_name)

    def _map_tool_to_service(self, tool_name: str) -> Optional[str]:
        """Map a tool name to its analyzer service using container registry.
        
        Returns the service name that should handle this tool,
        or None if tool is not recognized.
        """
        if not tool_name:
            return None
        
        try:
            # Use unified tool registry to determine which container provides this tool
            from app.engines.unified_registry import get_unified_tool_registry
            registry = get_unified_tool_registry()
            tool = registry.get(tool_name)  # Returns UnifiedTool or None
            
            if tool:
                logger.debug(f"[TOOL-MAPPING] Tool '{tool_name}' -> container '{tool.container}'")
                return tool.container
            
            # Tool not in registry - log warning and use safe default
            logger.warning(
                f"[TOOL-MAPPING] Tool '{tool_name}' not found in registry, defaulting to static-analyzer"
            )
            return 'static-analyzer'
            
        except Exception as e:
            logger.warning(f"[TOOL-MAPPING] Error mapping tool '{tool_name}': {e}")
            return 'static-analyzer'  # Safe fallback

    def _run_via_container(self, service_name: str, model_slug: str, app_number: int, tools: List[str]) -> Dict[str, Any]:
        """Delegate execution to analyzer containers via analyzer integration service.
        
        Uses the analyzer_integration service which handles WebSocket communication.
        """
        
        # For dynamic analysis, provide default tools if none specified
        if service_name == 'dynamic-analyzer' and not tools:
            # Default to available dynamic tools: curl for connectivity, nmap for ports, zap for security
            tools = ['curl', 'nmap', 'zap']
            logger.info(f"Dynamic analysis: no tools specified, using default tools: {tools}")
        
        logger.info(f"[ORCH] Delegating to analyzer integration: service={service_name}, model={model_slug}, app={app_number}, tools={tools}")
        
        # Use analyzer integration for execution
        try:
            analyzer_int = get_analyzer_integration()
            
            if not analyzer_int:
                logger.error("[ORCH] Analyzer integration not available")
                return {
                    'status': 'error',
                    'error': 'Analyzer integration service not initialized',
                    'tool_results': {t: {'status': 'error', 'error': 'Service not available'} for t in tools}
                }
            
            # Call appropriate analyzer integration method based on service
            if service_name == 'static-analyzer':
                result = analyzer_int.run_static_analysis(model_slug, app_number, tools=tools)
            elif service_name == 'dynamic-analyzer':
                result = analyzer_int.run_dynamic_analysis(model_slug, app_number, tools=tools)
            elif service_name == 'performance-tester':
                result = analyzer_int.run_performance_test(model_slug, app_number, tools=tools)
            elif service_name == 'ai-analyzer':
                result = analyzer_int.run_ai_analysis(model_slug, app_number, tools=tools)
            else:
                logger.error(f"[ORCH] Unknown service: {service_name}")
                return {
                    'status': 'error',
                    'error': f'Unknown analyzer service: {service_name}',
                    'tool_results': {t: {'status': 'error', 'error': 'Unknown service'} for t in tools}
                }
            
            return result
            
        except Exception as e:
            logger.exception(f"[ORCH] Error executing {service_name}: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'tool_results': {t: {'status': 'error', 'error': str(e)} for t in tools}
            }

    def _extract_container_tool_results(self, service_name: str, container_result: Dict[str, Any], requested_tools: List[str]) -> Tuple[Dict[str, Any], List[Finding]]:
        """Extract per-tool results and findings from container response, resilient to schema variations."""
        per_tool: Dict[str, Any] = {}
        findings: List[Finding] = []
        if not isinstance(container_result, dict):
            # Fallback: mark all as error
            for t in requested_tools:
                per_tool[t] = {'status': ToolStatus.ERROR.value, 'error': 'Invalid container result'}
            return per_tool, findings

        # Potential locations of tool_results
        candidates = [
            container_result,
            container_result.get('results') if isinstance(container_result.get('results'), dict) else None,
            container_result.get('data') if isinstance(container_result.get('data'), dict) else None,
        ]
        tool_results_obj: Optional[Dict[str, Any]] = None
        for obj in candidates:
            if isinstance(obj, dict) and isinstance(obj.get('tool_results'), dict):
                tool_results_obj = obj.get('tool_results')
                break

        # If we found per-tool results, map them through and preserve raw outputs
        if isinstance(tool_results_obj, dict):
            for t in requested_tools:
                tr = tool_results_obj.get(t)
                if isinstance(tr, dict):
                    # Preserve all tool result data including raw outputs
                    tool_result = tr.copy()  # Make a copy to preserve original data
                    
                    # Ensure we capture various output formats
                    if 'raw_output' not in tool_result:
                        # Try to extract from various output fields
                        for output_field in ['output', 'stdout', 'stderr', 'result', 'response']:
                            if output_field in tr and tr[output_field]:
                                tool_result['raw_output'] = tr[output_field]
                                break
                    
                    # Preserve command information if available
                    for field in ['command_line', 'command', 'cmd', 'exit_code', 'returncode']:
                        if field in tr:
                            tool_result[field] = tr[field]
                    
                    per_tool[t] = tool_result
                else:
                    per_tool[t] = {'status': ToolStatus.ERROR.value, 'error': 'No result from container'}
        else:
            # No per-tool details available; set generic status
            status = container_result.get('status') or container_result.get('state') or 'unknown'
            for t in requested_tools:
                per_tool[t] = {'status': status if isinstance(status, str) else ToolStatus.ERROR.value}

        # Attempt to map any top-level findings if present
        # Look for 'findings' at any level and try to coerce minimal Finding objects
        for key in ('findings',):
            for obj in candidates:
                try:
                    items = obj.get(key)
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict):
                                findings.append(Finding(
                                    tool=it.get('tool') or it.get('tool_name') or service_name,
                                    severity=str(it.get('severity', 'low')).lower(),
                                    confidence=str(it.get('confidence', 'low')).lower(),
                                    title=it.get('title') or it.get('message') or 'Finding',
                                    description=it.get('description') or it.get('message') or '',
                                    file_path=it.get('file_path') or '',
                                    line_number=it.get('line_number'),
                                    category=it.get('category') or '',
                                    rule_id=it.get('rule_id') or ''
                                ))
                except Exception:
                    continue

        return per_tool, findings
    def _infer_container_dir(self, tools: Optional[List[str]]) -> Optional[str]:
        """Infer container service name directory from selected tools.

        Returns one of: 'static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer'
        If multiple categories detected, returns 'comprehensive'. If none, returns None.
        """
        mapping = {
            # Static analyzer container tools
            'bandit': 'static-analyzer', 'safety': 'static-analyzer', 'pylint': 'static-analyzer',
            'mypy': 'static-analyzer', 'flake8': 'static-analyzer', 'semgrep': 'static-analyzer',
            'snyk': 'static-analyzer', 'eslint': 'static-analyzer', 'jshint': 'static-analyzer',
            'stylelint': 'static-analyzer', 'vulture': 'static-analyzer',
            
            # Dynamic analyzer container tools (includes integrated ZAP)
            'curl': 'dynamic-analyzer', 'wget': 'dynamic-analyzer', 'nmap': 'dynamic-analyzer',
            'zap': 'dynamic-analyzer', 'zap-baseline': 'dynamic-analyzer',
            
            # Performance tester container tools
            'ab': 'performance-tester', 'artillery': 'performance-tester', 'aiohttp': 'performance-tester', 
            'locust': 'performance-tester', 'apache-bench': 'performance-tester',
            
            # AI analyzer container tools
            'ai-requirements': 'ai-analyzer',
            'requirements-scanner': 'ai-analyzer',
            'requirements-analyzer': 'ai-analyzer'
        }
        if not tools:
            return None
        services = {mapping.get(t.lower()) for t in tools if mapping.get(t.lower())}
        services.discard(None)  # type: ignore[arg-type]
        if not services:
            return None
        if len(services) == 1:
            return next(iter(services))
        return 'comprehensive'
    
    def _resolve_target_path(self, model_slug: str, app_number: int) -> Path:
        """Resolve target path for analysis.

        Priority order:
          1) New unified path: generated/apps/<model_slug>/appN (project root)
          2) Legacy path: misc/models/<model_slug>/appN
          3) Heuristic fallback using helpers.get_app_directory
          4) Last-resort: return canonical generated path (may not exist)
        """
        logger.debug(
            "[ORCH] Resolving target path for model=%s, app=%s",
            model_slug, app_number
        )
        
        # 1) Prefer new unified generated/apps structure (project-root anchored)
        try:
            gen_candidate = GENERATED_APPS_DIR / model_slug / f"app{app_number}"
            logger.debug(
                "[ORCH] Path attempt #1 (generated/apps): %s - exists=%s",
                gen_candidate, gen_candidate.exists()
            )
            if gen_candidate.exists():
                logger.info("[ORCH] Resolved via generated/apps: %s", gen_candidate)
                return gen_candidate
        except Exception as e:
            logger.debug("[ORCH] Path attempt #1 exception: %s", e)

        # 2) Legacy misc/models path relative to project root
        legacy_candidate = (Path(__file__).resolve().parents[3] / "misc" / "models" / model_slug / f"app{app_number}")
        logger.debug(
            "[ORCH] Path attempt #2 (misc/models): %s - exists=%s",
            legacy_candidate, legacy_candidate.exists()
        )
        if legacy_candidate.exists():
            logger.info("[ORCH] Resolved via misc/models (legacy): %s", legacy_candidate)
            return legacy_candidate

        # 3) Use helpers (handles variations and fuzzy matching)
        try:
            helper_path = get_app_directory(model_slug, app_number)
            logger.debug(
                "[ORCH] Path attempt #3 (helper fuzzy match): %s - exists=%s",
                helper_path, helper_path.exists() if helper_path else False
            )
            if helper_path and helper_path.exists():
                logger.info("[ORCH] Resolved via helper (fuzzy): %s", helper_path)
                return helper_path
        except Exception as e:
            logger.debug("[ORCH] Path attempt #3 exception: %s", e)

        # 4) Return canonical new path even if missing (callers will validate)
        fallback = GENERATED_APPS_DIR / model_slug / f"app{app_number}"
        logger.warning(
            "[ORCH] All path attempts FAILED - returning fallback (may not exist): %s",
            fallback
        )
        logger.info(
            "[ORCH] TIP: Generate the application first - it doesn't exist in filesystem. "
            "DB record may exist but files are missing."
        )
        return fallback
    
    def _detect_languages(self, target_path: Path) -> Set[str]:
        """Detect programming languages in target path."""
        extensions = parse_file_extensions(target_path)
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.vue': 'vue',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.less': 'less'
        }
        
        languages = set()
        for ext in extensions:
            if ext in language_map:
                languages.add(language_map[ext])
        
        return languages
    
    def _build_tool_config(
        self,
        tool_name: str,
        tool_configs: Optional[Dict[str, Dict[str, Any]]]
    ) -> ToolConfig:
        """Build configuration for a specific tool."""
        config = ToolConfig()
        
        if tool_configs and tool_name in tool_configs:
            user_config = tool_configs[tool_name]
            
            # Update config with user values
            for key, value in user_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        return config
    
    def _build_summary(
        self,
        all_findings: List[Finding],
        tool_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build analysis summary from results."""
        summary = {
            'total_findings': len(all_findings),
            'severity_breakdown': {},
            'tools_breakdown': {},
            'categories': set(),
            'tags': set()
        }
        
        # Count findings by severity
        for finding in all_findings:
            severity = finding.severity
            summary['severity_breakdown'][severity] = summary['severity_breakdown'].get(severity, 0) + 1
            summary['categories'].add(finding.category)
            summary['tags'].update(finding.tags)
        
        # Count findings by tool
        for finding in all_findings:
            tool = finding.tool
            summary['tools_breakdown'][tool] = summary['tools_breakdown'].get(tool, 0) + 1
        
        # Convert sets to lists for JSON serialization
        summary['categories'] = list(summary['categories'])
        summary['tags'] = list(summary['tags'])
        
        # Add tool status summary
        summary['tool_status'] = {}
        for tool_name, result in tool_results.items():
            summary['tool_status'][tool_name] = result.get('status', 'unknown')
        
        return summary

# Global orchestrator instance
_orchestrator = None

def get_analysis_orchestrator(base_path: Optional[Path] = None) -> AnalysisOrchestrator:
    """Get global analysis orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AnalysisOrchestrator(base_path)
    return _orchestrator

def reset_analysis_orchestrator():
    """Reset the global orchestrator instance to force reinitialization."""
    global _orchestrator
    _orchestrator = None