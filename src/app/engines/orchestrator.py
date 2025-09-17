"""
Dynamic Analysis Orchestrator
============================

Orchestrates analysis runs using the new dynamic tool system.
Replaces the old rigid type-based analysis engines.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .base import (
    get_tool_registry, ToolConfig, Finding,
    ToolStatus, parse_file_extensions
)
from ..utils.json_results_manager import JsonResultsManager
from ..utils.helpers import get_app_directory
from ..paths import GENERATED_APPS_DIR

logger = logging.getLogger(__name__)

class AnalysisOrchestrator:
    """Orchestrates analysis runs using dynamic tool selection."""
    
    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize analysis orchestrator.
        
        Args:
            base_path: Base path for results storage
        """
        self.registry = get_tool_registry()
        self.base_path = base_path or Path.cwd()
        # Store under project-root results directory
        self.results_manager = JsonResultsManager(self.base_path / "results", "analysis")
        
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
            
            if not tools:
                return {
                    'success': False,
                    'error': "No suitable tools found for analysis",
                    'model_slug': model_slug,
                    'app_number': app_number,
                    'target_path': str(target_path)
                }
            
            # Run tools
            tool_results = {}
            all_findings = []
            successful_tools = 0
            failed_tools = 0
            
            for tool_name in tools:
                logger.info(f"Running tool: {tool_name}")
                
                try:
                    # Get tool instance with configuration
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
                    
                    # Run tool analysis
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
                container_dir = self._infer_container_dir(tools)
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
    def _infer_container_dir(self, tools: Optional[List[str]]) -> Optional[str]:
        """Infer container service name directory from selected tools.

        Returns one of: 'static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer'
        If multiple categories detected, returns 'comprehensive'. If none, returns None.
        """
        mapping = {
            # static
            'bandit': 'static-analyzer', 'safety': 'static-analyzer', 'pylint': 'static-analyzer',
            'mypy': 'static-analyzer', 'flake8': 'static-analyzer', 'semgrep': 'static-analyzer',
            'snyk': 'static-analyzer', 'eslint': 'static-analyzer', 'jshint': 'static-analyzer',
            'stylelint': 'static-analyzer', 'vulture': 'static-analyzer',
            # dynamic
            'curl': 'dynamic-analyzer', 'wget': 'dynamic-analyzer', 'nmap': 'dynamic-analyzer', 'zap': 'dynamic-analyzer',
            # performance
            'ab': 'performance-tester', 'artillery': 'performance-tester', 'aiohttp': 'performance-tester', 'locust': 'performance-tester',
            # ai
            'ai-review': 'ai-analyzer', 'ai': 'ai-analyzer'
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