"""
Dynamic Analysis Orchestrator
============================

Orchestrates analysis runs using the new dynamic tool system.
Replaces the old rigid type-based analysis engines.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .base import (
    get_tool_registry, ToolConfig, Finding,
    ToolStatus, parse_file_extensions
)
from ..utils.json_results_manager import JsonResultsManager
from ..utils.helpers import get_app_directory
from ..paths import GENERATED_APPS_DIR, PROJECT_ROOT
from ..services import analyzer_integration as analyzer_bridge
import socket

logger = logging.getLogger(__name__)

class AnalysisOrchestrator:
    """Orchestrates analysis runs using dynamic tool selection."""
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize analysis orchestrator.
        
        Args:
            base_path: Base path for results storage (deprecated, will use PROJECT_ROOT)
        """
        self.registry = get_tool_registry()
        # Always use PROJECT_ROOT to ensure consistent results location
        self.base_path = PROJECT_ROOT
        # Store under project-root results directory
        self.results_manager = JsonResultsManager(PROJECT_ROOT / "results", "analysis")
        
    def discover_tools(self) -> Dict[str, Any]:
        """Discover available tools on the system."""
        return {
            'available_tools': self.registry.get_available_tools(),
            'all_tools': self.registry.get_all_tools_info(),
            'discovery_results': self.registry.discover_tools()
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
        
        # Get tools by language
        for language in languages:
            tools = self.registry.get_tools_for_language(language)
            recommended_tools.update(tools)
        
        # Get tools by tags if specified
        if tags:
            tools = self.registry.get_tools_by_tags(tags)
            recommended_tools.update(tools)
        
        # Filter to only available tools
        available_tools = set(self.registry.get_available_tools())
        return list(recommended_tools.intersection(available_tools))
    
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
        
        try:
            # Resolve target path
            if target_path is None:
                target_path = self._resolve_target_path(model_slug, app_number)
            
            if not target_path.exists():
                return {
                    'success': False,
                    'error': f"Target path does not exist: {target_path}",
                    'model_slug': model_slug,
                    'app_number': app_number
                }
            
            # Determine tools to run
            if tools is None:
                tools = self.get_tools_for_context(target_path, tags)

            logger.info(f"Analysis orchestrator: initial tools={tools}, tags={tags}")

            # Normalize tool names (aliases -> canonical)
            def _canonical(name: str) -> str:
                alias_map = {
                    # Keep performance tool names as-is for proper mapping
                    'locust-performance': 'locust-performance',
                    'ab-load-test': 'ab-load-test',
                }
                key = (name or '').strip().lower()
                return alias_map.get(key, key)

            tools = [
                _canonical(t) for t in (tools or [])
                if isinstance(t, str) and t.strip()
            ]
            
            logger.info(f"Analysis orchestrator: normalized tools={tools}")
            
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
            availability: Dict[str, bool] = {}
            service_groups: Dict[str, List[str]] = {}
            service_for_tool: Dict[str, Optional[str]] = {}

            for tool_name in tools:
                # Map database tool names to dynamic registry names for availability check
                mapped_tool_name = self._map_tool_name_to_dynamic_registry(tool_name)
                
                # Prepare instance for local availability check
                config = self._build_tool_config(mapped_tool_name, tool_configs)
                tool = self.registry.get_tool(mapped_tool_name, config)
                available = tool.is_available() if tool else False
                availability[tool_name] = bool(available)
                svc = self._map_tool_to_service(tool_name)
                service_for_tool[tool_name] = svc
                if svc:
                    service_groups.setdefault(svc, []).append(tool_name)

            # Decide delegation per service: if service up and any tool in group not locally available
            delegated_tools: Set[str] = set()
            for svc, svc_tools in service_groups.items():
                service_up = self._analyzer_service_up(svc)
                any_unavailable = any(not availability.get(t, False) for t in svc_tools)
                
                logger.info(f"Service delegation check: {svc} | service_up={service_up} | tools={svc_tools} | availability={[availability.get(t, False) for t in svc_tools]} | any_unavailable={any_unavailable}")
                
                if service_up and any_unavailable:
                    # Delegate this group to analyzer containers
                    logger.info(f"Delegating tools {svc_tools} to container service {svc}")
                    try:
                        svc_result = self._run_via_container(svc, model_slug, app_number, svc_tools)
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
                        logger.warning(f"Container delegation failed for {svc}: {e}")
                        # Mark tools as not available to preserve previous behavior
                        for t in svc_tools:
                            if t not in tool_results:
                                tool_results[t] = {
                                    'status': ToolStatus.NOT_AVAILABLE.value,
                                    'error': f'Container delegation failed: {str(e)}'
                                }
                                failed_tools += 1
                else:
                    logger.info(f"Not delegating tools {svc_tools} to {svc}: service_up={service_up}, any_unavailable={any_unavailable}")

            # Run remaining tools locally
            for tool_name in tools:
                if tool_name in delegated_tools:
                    continue
                logger.info(f"Running tool locally: {tool_name}")
                try:
                    config = self._build_tool_config(tool_name, tool_configs)
                    tool = self.registry.get_tool(tool_name, config)
                    if tool is None:
                        logger.warning(f"Tool not found: {tool_name}")
                        failed_tools += 1
                        continue
                    if not tool.is_available():
                        logger.warning(f"Tool not available: {tool_name}")
                        tool_results[tool_name] = {
                            'status': ToolStatus.NOT_AVAILABLE.value,
                            'error': 'Tool not available on system'
                        }
                        failed_tools += 1
                        continue
                    result = tool.run_analysis(target_path, **kwargs)
                    tool_results[tool_name] = result.to_dict()
                    all_findings.extend(result.findings)
                    if result.error:
                        failed_tools += 1
                    else:
                        successful_tools += 1
                except Exception as e:
                    logger.error(f"Error running tool {tool_name}: {e}")
                    tool_results[tool_name] = {
                        'status': ToolStatus.ERROR.value,
                        'error': str(e)
                    }
                    failed_tools += 1
            
            # Build comprehensive results
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
                'summary': self._build_summary(all_findings, tool_results),
                'findings': [f.to_dict() for f in all_findings],
                'metadata': {
                    'analysis_timestamp': __import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),
                    'detected_languages': list(self._detect_languages(target_path)),
                    'file_count': len(list(target_path.rglob('*'))),
                    'orchestrator_version': '2.0.0'
                }
            }
            
            # Save results under folder named after the analyzer container service
            try:
                # If we delegated to multiple services, treat as comprehensive
                used_services = {self._map_tool_to_service(t) for t in tools if self._map_tool_to_service(t)}
                container_dir = 'comprehensive' if len(used_services) > 1 else (next(iter(used_services)) if used_services else None)
                self.results_manager.save_results(
                    model_slug,
                    app_number,
                    results,
                    analysis_type=container_dir or 'analysis'
                )
            except Exception as e:
                logger.warning(f"Failed to save results: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Analysis orchestration failed: {e}")
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
            app_number,
            f"{analysis_type}_results.json"
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
            'ai-code-review': 'ai-review',
            # Add other mappings as needed
        }
        return name_mapping.get(tool_name, tool_name)

    def _map_tool_to_service(self, tool_name: str) -> Optional[str]:
        """Map a tool name to its analyzer service."""
        mapping = {
            # Static analyzer container tools (port 2001)
            'bandit': 'static-analyzer', 'safety': 'static-analyzer', 'pylint': 'static-analyzer',
            'mypy': 'static-analyzer', 'flake8': 'static-analyzer', 'semgrep': 'static-analyzer',
            'snyk': 'static-analyzer', 'eslint': 'static-analyzer', 'jshint': 'static-analyzer',
            'stylelint': 'static-analyzer', 'vulture': 'static-analyzer',
            
            # Dynamic analyzer container tools (port 2002)
            'curl': 'dynamic-analyzer', 'wget': 'dynamic-analyzer', 'nmap': 'dynamic-analyzer',
            
            # Performance tester container tools (port 2003)
            'ab': 'performance-tester', 'ab-load-test': 'performance-tester', 'apache-bench': 'performance-tester',
            'artillery': 'performance-tester', 'aiohttp': 'performance-tester', 
            'locust': 'performance-tester', 'locust-performance': 'performance-tester',
            
            # AI analyzer container tools (port 2004)
            'ai-review': 'ai-analyzer', 'ai': 'ai-analyzer', 'ai-code-review': 'ai-analyzer',
            'ai-requirements': 'ai-analyzer'
        }
        return mapping.get((tool_name or '').lower())

    def _run_via_container(self, service_name: str, model_slug: str, app_number: int, tools: List[str]) -> Dict[str, Any]:
        """Delegate execution to analyzer containers via analyzer_integration subprocess bridge."""
        # Route based on service name
        if service_name == 'static-analyzer':
            return analyzer_bridge.analysis_executor.run_static_analysis(model_slug, app_number, tools=tools)
        if service_name == 'dynamic-analyzer':
            return analyzer_bridge.analysis_executor.run_dynamic_analysis(model_slug, app_number, tools=tools)
        if service_name == 'performance-tester':
            return analyzer_bridge.analysis_executor.run_performance_test(model_slug, app_number, tools=tools)
        if service_name == 'ai-analyzer':
            return analyzer_bridge.analysis_executor.run_ai_analysis(model_slug, app_number, tools=tools)
        raise ValueError(f"Unknown analyzer service: {service_name}")

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

        # If we found per-tool results, map them through
        if isinstance(tool_results_obj, dict):
            for t in requested_tools:
                tr = tool_results_obj.get(t)
                if isinstance(tr, dict):
                    per_tool[t] = tr
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
            
            # Dynamic analyzer container tools
            'curl': 'dynamic-analyzer', 'wget': 'dynamic-analyzer', 'nmap': 'dynamic-analyzer',
            
            # Performance tester container tools
            'ab': 'performance-tester', 'artillery': 'performance-tester', 'aiohttp': 'performance-tester', 
            'locust': 'performance-tester', 'apache-bench': 'performance-tester',
            
            # AI analyzer container tools
            'ai-review': 'ai-analyzer', 'ai': 'ai-analyzer', 'ai-requirements': 'ai-analyzer'
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
        return 'comprehensive'
    
    def _resolve_target_path(self, model_slug: str, app_number: int) -> Path:
        """Resolve target path for analysis.

        Priority order:
          1) New unified path: src/generated/apps/<model_slug>/appN
          2) Legacy path: misc/models/<model_slug>/appN
          3) Heuristic fallback using helpers.get_app_directory
          4) Last-resort: return canonical generated path (may not exist)
        """
        # 1) Prefer new unified generated/apps structure (project-root anchored)
        try:
            gen_candidate = GENERATED_APPS_DIR / model_slug / f"app{app_number}"
            if gen_candidate.exists():
                return gen_candidate
        except Exception:
            pass

        # 2) Legacy misc/models path relative to project root
        legacy_candidate = (Path(__file__).resolve().parents[3] / "misc" / "models" / model_slug / f"app{app_number}")
        if legacy_candidate.exists():
            return legacy_candidate

        # 3) Use helpers (handles variations and fuzzy matching)
        try:
            helper_path = get_app_directory(model_slug, app_number)
            if helper_path.exists():
                return helper_path
        except Exception:
            pass

        # 4) Return canonical new path even if missing (callers will validate)
        return GENERATED_APPS_DIR / model_slug / f"app{app_number}"
    
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