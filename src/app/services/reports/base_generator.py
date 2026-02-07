"""
Base Report Generator

Abstract base class for all report generators. Defines the interface and common functionality.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


def get_tool_categories_from_registry() -> Tuple[List[Tuple[str, List[str], str, str]], List[str]]:
    """
    Get tool categories from the ContainerToolRegistry.
    
    Returns:
        Tuple of (category_list, all_known_tools):
        - category_list: List of (category_name, tool_names, icon, color) tuples
        - all_known_tools: Flat list of all tool names for "Other" category detection
    """
    try:
        from ...engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        registry.initialize()
        
        # Define display-friendly categories mapped to container types and tags
        # Format: (display_name, container_or_tags, icon, color)
        category_definitions = [
            ('Security Analysis', {'security', 'sast', 'dependency', 'cve'}, 'ti-shield-check', 'danger'),
            ('Code Quality', {'quality', 'linting', 'style'}, 'ti-code', 'info'),
            ('Type Checking & Metrics', {'typing', 'type-check', 'metrics', 'dead-code'}, 'ti-chart-dots', 'purple'),
            ('Performance Testing', {'performance', 'load_testing'}, 'ti-gauge', 'success'),
            ('AI Analysis', {'ai', 'requirements'}, 'ti-brain', 'azure'),
            ('Dynamic Analysis', {'dynamic', 'web', 'connectivity', 'network'}, 'ti-world', 'orange'),
        ]
        
        all_tools = registry.get_all_tools()
        categories = []
        all_known_tools = []
        used_tools = set()
        
        for category_name, tags, icon, color in category_definitions:
            category_tools = []
            for tool_name, tool in all_tools.items():
                # Match by tags
                if tool.tags.intersection(tags) and tool_name not in used_tools:
                    category_tools.append(tool_name)
                    used_tools.add(tool_name)
            
            if category_tools:
                categories.append((category_name, sorted(category_tools), icon, color))
                all_known_tools.extend(category_tools)
        
        # Add any remaining tools to the first matching category or create "Other"
        remaining_tools = [name for name in all_tools.keys() if name not in used_tools]
        if remaining_tools:
            categories.append(('Other Tools', sorted(remaining_tools), 'ti-puzzle', 'secondary'))
            all_known_tools.extend(remaining_tools)
        
        return categories, all_known_tools
        
    except Exception as e:
        logger.warning(f"Failed to get tool categories from registry: {e}")
        # Fallback to hardcoded categories
        return _get_fallback_tool_categories()


def _get_fallback_tool_categories() -> Tuple[List[Tuple[str, List[str], str, str]], List[str]]:
    """Fallback hardcoded tool categories if registry is unavailable."""
    categories = [
        ('Security Analysis', ['bandit', 'semgrep', 'safety', 'pip-audit', 'zap', 'nmap', 'snyk', 'detect-secrets', 'npm-audit'], 'ti-shield-check', 'danger'),
        ('Code Quality', ['pylint', 'eslint', 'jshint', 'ruff', 'flake8', 'stylelint', 'html-validator'], 'ti-code', 'info'),
        ('Type & Metrics', ['mypy', 'vulture', 'radon'], 'ti-chart-dots', 'purple'),
        ('Performance Testing', ['ab', 'aiohttp', 'locust', 'artillery', 'curl'], 'ti-gauge', 'success'),
        ('AI Analysis', ['requirements-checker', 'code-quality-analyzer', 'requirements-scanner'], 'ti-brain', 'azure'),
    ]
    
    all_known = []
    for _, tools, _, _ in categories:
        all_known.extend(tools)
    
    return categories, all_known


def get_tool_display_info() -> Dict[str, Dict[str, Any]]:
    """
    Get display information for all tools from the registry.
    
    Returns:
        Dict mapping tool_name to {display_name, description, tags, category}
    """
    try:
        from ...engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        registry.initialize()
        
        tool_info = {}
        for name, tool in registry.get_all_tools().items():
            tool_info[name] = {
                'display_name': tool.display_name,
                'description': tool.description,
                'tags': list(tool.tags),
                'container': tool.container.value,
                'available': tool.available,
                'supported_languages': list(tool.supported_languages),
            }
        
        return tool_info
    except Exception as e:
        logger.warning(f"Failed to get tool display info: {e}")
        return {}


class BaseReportGenerator(ABC):
    """Base class for all report generators."""
    
    def __init__(self, config: Dict[str, Any], reports_dir: Path):
        """
        Initialize the generator.
        
        Args:
            config: Report-specific configuration dictionary
            reports_dir: Base directory for saving report files
        """
        self.config = config
        self.reports_dir = reports_dir
        self.data: Optional[Dict[str, Any]] = None
    
    def get_tool_categories(self) -> List[Tuple[str, List[str], str, str]]:
        """
        Get tool categories for template rendering.
        
        Returns:
            List of (category_name, tool_names, icon, color) tuples
        """
        categories, _ = get_tool_categories_from_registry()
        return categories
    
    def get_all_known_tools(self) -> List[str]:
        """Get flat list of all known tool names."""
        _, all_tools = get_tool_categories_from_registry()
        return all_tools
    
    def add_tool_context(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add tool categories and display info to template context.
        
        Args:
            data: Existing template context data
            
        Returns:
            Updated data with tool_categories and tool_display_info
        """
        data['tool_categories'] = self.get_tool_categories()
        data['all_known_tools'] = self.get_all_known_tools()
        data['tool_display_info'] = get_tool_display_info()
        return data
    
    def should_include_service(self, service_name: str) -> bool:
        """
        Check if a service should be included based on filter_mode.
        
        Args:
            service_name: Name of the analyzer service (e.g., 'static', 'dynamic', 'performance', 'ai')
            
        Returns:
            True if service should be included, False otherwise
        """
        from ...constants import ReportFilterMode
        
        filter_mode = self.config.get('filter_mode', 'all')
        
        # Normalize filter_mode to enum
        if isinstance(filter_mode, str):
            try:
                filter_mode = ReportFilterMode(filter_mode)
            except ValueError:
                filter_mode = ReportFilterMode.ALL_ANALYZERS
        
        # Normalize service name
        service_name_lower = service_name.lower().replace('-', '_')
        
        if filter_mode == ReportFilterMode.ALL_ANALYZERS:
            return True
        elif filter_mode == ReportFilterMode.EXCLUDE_DYNAMIC_PERF:
            # Exclude dynamic and performance analyzers
            return service_name_lower not in ['dynamic', 'dynamic_analyzer', 'performance', 'performance_tester']
        elif filter_mode == ReportFilterMode.ONLY_DYNAMIC_PERF:
            # Include only dynamic and performance analyzers
            return service_name_lower in ['dynamic', 'dynamic_analyzer', 'performance', 'performance_tester']
        
        return True
    
    def filter_services_data(self, services: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter services dictionary based on filter_mode.
        
        Args:
            services: Dictionary of service_name -> service_data
            
        Returns:
            Filtered dictionary with only included services
        """
        if not services:
            return {}
        
        return {
            service_name: service_data
            for service_name, service_data in services.items()
            if self.should_include_service(service_name)
        }
    
    @abstractmethod
    def collect_data(self) -> Dict[str, Any]:
        """
        Collect and aggregate data for the report.
        
        This method should:
        1. Query the database for task metadata and filtering
        2. Load detailed results from consolidated JSON files
        3. Aggregate and compute statistics
        4. Return a structured data dictionary
        
        Returns:
            Dictionary containing all data needed for rendering
        """
        pass
    
    @abstractmethod
    def get_template_name(self) -> str:
        """
        Get the Jinja2 template filename for this report type.
        
        Returns:
            Template filename (e.g., 'model_analysis.html')
        """
        pass
    
    def validate_config(self) -> None:
        """
        Validate the configuration for this report type.
        
        Raises:
            ValidationError: If configuration is invalid
        """
        # Default implementation - override in subclasses for specific validation
        pass
    
    def generate_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a summary of the report data for quick display.
        
        Args:
            data: The full report data
            
        Returns:
            Dictionary with summary statistics
        """
        # Default implementation - override in subclasses for specific summaries
        return {
            'total_items': len(data.get('items', [])),
            'generated_at': data.get('timestamp')
        }
