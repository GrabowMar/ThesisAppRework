"""
Dynamic Analysis Tool System
==========================

Modern tool-centric analysis system inspired by the attached files.
Replaces rigid type-based system with flexible tagging and dynamic tool discovery.

Key Features:
- Dynamic tool discovery and registration
- Flexible tagging system instead of fixed types
- Standardized tool interfaces and result formats
- Tool availability checking and configuration
- Intelligent tool selection based on context
- Rich metadata and status reporting
"""

import logging
import platform
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Status and severity enums
class ToolStatus(str, Enum):
    """Tool execution status with emoji indicators."""
    SUCCESS = "✅ Success"
    ISSUES_FOUND = "⚠️ Issues found"
    WARNING = "⚠️ Warning"
    ERROR = "❌ Error"
    TIMEOUT = "⏰ Timeout"
    NOT_FOUND = "❌ Not found"
    AUTH_REQUIRED = "🔐 Auth required"
    SKIPPED = "⚪ Skipped"
    NOT_AVAILABLE = "❓ Not available"
    RUNNING = "🔄 Running"

class Severity(str, Enum):
    """Universal issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    UNKNOWN = "unknown"

class Confidence(str, Enum):
    """Confidence levels for findings."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"

# Data classes for structured results
@dataclass
class Finding:
    """Standardized finding/issue representation."""
    tool: str
    severity: str
    confidence: str
    title: str
    description: str
    file_path: str = ""
    line_number: Optional[int] = None
    column: Optional[int] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    category: str = ""
    rule_id: str = ""
    fix_suggestion: Optional[str] = None
    references: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tool': self.tool,
            'severity': self.severity,
            'confidence': self.confidence,
            'title': self.title,
            'description': self.description,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column': self.column,
            'end_line': self.end_line,
            'end_column': self.end_column,
            'category': self.category,
            'rule_id': self.rule_id,
            'fix_suggestion': self.fix_suggestion,
            'references': self.references,
            'tags': self.tags,
            'raw_data': self.raw_data
        }

@dataclass
class ToolResult:
    """Standardized tool execution result."""
    tool_name: str
    status: str
    findings: List[Finding] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration_seconds: float = 0.0
    output: str = ""
    error: Optional[str] = None
    raw_output: Optional[str] = None  # Complete raw output from tool execution
    command_line: Optional[str] = None  # Command that was executed
    exit_code: Optional[int] = None  # Tool exit code
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'tool_name': self.tool_name,
            'status': self.status,
            'findings': [f.to_dict() for f in self.findings],
            'metadata': self.metadata,
            'duration_seconds': self.duration_seconds,
            'output': self.output,
            'error': self.error,
            'raw_output': self.raw_output,
            'command_line': self.command_line,
            'exit_code': self.exit_code,
            'findings_count': len(self.findings),
            'severity_breakdown': self._get_severity_breakdown()
        }
    
    def _get_severity_breakdown(self) -> Dict[str, int]:
        """Get breakdown of findings by severity."""
        breakdown = {severity.value: 0 for severity in Severity}
        for finding in self.findings:
            severity = finding.severity.lower()
            if severity in breakdown:
                breakdown[severity] += 1
        return breakdown

@dataclass
class ToolConfig:
    """Configuration for a specific tool."""
    enabled: bool = True
    timeout: int = 60
    max_issues: int = 1000
    severity_filter: List[str] = field(default_factory=lambda: ["critical", "high", "medium", "low"])
    exclude_patterns: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    custom_args: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'enabled': self.enabled,
            'timeout': self.timeout,
            'max_issues': self.max_issues,
            'severity_filter': self.severity_filter,
            'exclude_patterns': self.exclude_patterns,
            'include_patterns': self.include_patterns,
            'custom_args': self.custom_args,
            'environment': self.environment
        }

# Abstract base tool class
class BaseAnalysisTool(ABC):
    """Abstract base class for all analysis tools."""
    
    def __init__(self, config: Optional[ToolConfig] = None):
        self.config = config or ToolConfig()
        self.logger = logging.getLogger(f"tool.{self.name}")
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name identifier."""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable tool name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass
    
    @property
    @abstractmethod
    def tags(self) -> Set[str]:
        """Tool tags for categorization."""
        pass
    
    @property
    @abstractmethod
    def supported_languages(self) -> Set[str]:
        """Programming languages this tool supports."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if tool is available on the system."""
        pass
    
    @abstractmethod
    def get_version(self) -> Optional[str]:
        """Get tool version if available."""
        pass
    
    @abstractmethod
    def run_analysis(self, target_path: Path, **kwargs) -> ToolResult:
        """Run analysis on target path."""
        pass
    
    def check_prerequisites(self) -> List[str]:
        """Check tool prerequisites and return list of missing items."""
        missing = []
        if not self.is_available():
            missing.append(f"{self.name} executable not found")
        return missing
    
    def get_info(self) -> Dict[str, Any]:
        """Get comprehensive tool information."""
        return {
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'tags': list(self.tags),
            'supported_languages': list(self.supported_languages),
            'available': self.is_available(),
            'version': self.get_version(),
            'prerequisites': self.check_prerequisites(),
            'config': self.config.to_dict()
        }

# Utility functions
def find_executable(name: str) -> Optional[str]:
    """Find executable in PATH or (optionally) check analyzer services.

    By default we only return executables available on the host PATH to avoid
    issuing local subprocess calls that will inevitably fail with
    "Command not found" when binaries are missing. If you explicitly want to
    treat containerized tools as available (for planning/registry display), set
    ORCHESTRATOR_USE_CONTAINER_TOOLS=1 in the environment.
    """
    # First try to find locally
    if platform.system() == "Windows":
        # Try with .exe and .cmd extensions
        for ext in ['.exe', '.cmd', '']:
            full_name = f"{name}{ext}"
            path = shutil.which(full_name)
            if path:
                return path
    else:
        result = shutil.which(name)
        if result:
            return result
    
    # Optionally consider containerized tools available when services are up
    # (for UI planning or when execution is proxied through containers).
    # Disabled by default to prevent local subprocess attempts failing.
    import os
    use_container_tools = os.environ.get('ORCHESTRATOR_USE_CONTAINER_TOOLS', '0') in ('1', 'true', 'True')
    if not use_container_tools:
        return None

    # Treat a broader set of tools as available when the corresponding
    # analyzer service container is up. This keeps the UI and planner in sync
    # with what the containers can execute, even if the host lacks binaries.
    containerized_tools = {
        # Static/security/quality (2001)
        'bandit': 'static-analyzer',
        'safety': 'static-analyzer',
        'pylint': 'static-analyzer',
        'mypy': 'static-analyzer',
        'flake8': 'static-analyzer',
        'semgrep': 'static-analyzer',
        'snyk': 'static-analyzer',
        'eslint': 'static-analyzer',
        'jshint': 'static-analyzer',
        'stylelint': 'static-analyzer',
        'vulture': 'static-analyzer',

        # Dynamic (2002)
        'curl': 'dynamic-analyzer',
        'wget': 'dynamic-analyzer',
        'nmap': 'dynamic-analyzer',
        'zap': 'dynamic-analyzer',

        # Performance (2003)
        'ab': 'performance-tester',        # apache-bench
        'artillery': 'performance-tester',
        'aiohttp': 'performance-tester',   # built-in client in container
        'locust': 'performance-tester',
    }
    
    service_name = containerized_tools.get(name)
    if service_name:
        # Check if analyzer service is available
        return check_analyzer_service_availability(service_name, name)
    
    return None


def check_analyzer_service_availability(service_name: str, tool_name: str) -> Optional[str]:
    """Check if analyzer service and tool are available."""
    try:
        import socket
        
        # Map service names to ports
        service_ports = {
            'static-analyzer': 2001,
            'dynamic-analyzer': 2002, 
            'performance-tester': 2003,
            'ai-analyzer': 2004
        }
        
        port = service_ports.get(service_name)
        if not port:
            return None
            
        # Quick port check to see if service is running
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            # Service is running, assume tool is available
            return f"containerized:{service_name}:{tool_name}"
        
    except Exception:
        pass
    
    return None

def run_command(
    command: List[str], 
    cwd: Optional[Path] = None,
    timeout: int = 60,
    env: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """
    Run a command and return (return_code, stdout, stderr).
    
    Args:
        command: Command and arguments
        cwd: Working directory
        timeout: Timeout in seconds
        env: Environment variables
        
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except FileNotFoundError:
        return -1, "", f"Command not found: {command[0]}"
    except Exception as e:
        return -1, "", f"Command failed: {str(e)}"

def normalize_severity(value: Any) -> str:
    """Normalize severity value to universal standard format."""
    if value is None:
        return Severity.UNKNOWN.value
    
    # Convert to string and normalize
    value_str = str(value).lower().strip()
    
    # Handle numeric values with simple mapping
    if value_str.isdigit():
        num_val = int(value_str)
        if num_val >= 4:
            return Severity.CRITICAL.value
        elif num_val == 3:
            return Severity.HIGH.value
        elif num_val == 2:
            return Severity.MEDIUM.value
        elif num_val == 1:
            return Severity.LOW.value
        else:
            return Severity.INFO.value
    
    # Universal string mapping - accept any input, normalize to standard levels
    if any(word in value_str for word in ['critical', 'fatal', 'severe']):
        return Severity.CRITICAL.value
    elif any(word in value_str for word in ['high', 'error', 'major']):
        return Severity.HIGH.value
    elif any(word in value_str for word in ['medium', 'warn', 'warning', 'moderate']):
        return Severity.MEDIUM.value
    elif any(word in value_str for word in ['low', 'minor', 'style']):
        return Severity.LOW.value
    elif any(word in value_str for word in ['info', 'note', 'informational']):
        return Severity.INFO.value
    
    # Return as-is if it's already a valid severity, otherwise unknown
    valid_severities = {s.value for s in Severity}
    return value_str if value_str in valid_severities else Severity.UNKNOWN.value

def normalize_confidence(value: Any) -> str:
    """Normalize confidence value to standard format."""
    if value is None:
        return Confidence.UNKNOWN.value
    
    value_str = str(value).lower().strip()
    confidence_map = {
        'high': Confidence.HIGH.value,
        'medium': Confidence.MEDIUM.value,
        'low': Confidence.LOW.value
    }
    
    return confidence_map.get(value_str, value_str)

def parse_file_extensions(path: Path) -> Set[str]:
    """Get all file extensions in a directory."""
    extensions = set()
    try:
        for file_path in path.rglob('*'):
            if file_path.is_file() and file_path.suffix:
                extensions.add(file_path.suffix.lower())
    except Exception as e:
        logger.warning(f"Error scanning directory {path}: {e}")
    return extensions

def should_analyze_path(path: Path, include_patterns: List[str], exclude_patterns: List[str]) -> bool:
    """Check if path should be analyzed based on include/exclude patterns."""
    path_str = str(path)
    
    # Check exclude patterns first
    for pattern in exclude_patterns:
        if pattern in path_str:
            return False
    
    # If no include patterns, include by default
    if not include_patterns:
        return True
    
    # Check include patterns
    for pattern in include_patterns:
        if pattern in path_str:
            return True
    
    return False

# Tool registry for dynamic discovery
class ToolRegistry:
    """Registry for dynamically discovering and managing analysis tools."""
    
    def __init__(self):
        self._tools: Dict[str, BaseAnalysisTool] = {}
        self._tool_classes: Dict[str, type] = {}
        
    def register_tool(self, tool_class: type) -> None:
        """Register a tool class."""
        if not issubclass(tool_class, BaseAnalysisTool):
            raise ValueError("Tool class must inherit from BaseAnalysisTool")
        
        # Create instance to get name
        temp_instance = tool_class()
        self._tool_classes[temp_instance.name] = tool_class
        logger.debug(f"Registered tool class: {temp_instance.name}")
    
    def get_tool(self, name: str, config: Optional[ToolConfig] = None) -> Optional[BaseAnalysisTool]:
        """Get tool instance by name."""
        if name in self._tools:
            return self._tools[name]
        
        if name in self._tool_classes:
            tool = self._tool_classes[name](config)
            self._tools[name] = tool
            return tool
        
        return None
    
    def get_available_tools(self) -> List[str]:
        """Get list of available tool names."""
        available = []
        for name, tool_class in self._tool_classes.items():
            try:
                tool = tool_class()
                if tool.is_available():
                    available.append(name)
            except Exception as e:
                logger.warning(f"Error checking tool {name}: {e}")
        return available
    
    def get_tools_by_tags(self, tags: Set[str]) -> List[str]:
        """Get tools that have any of the specified tags."""
        matching_tools = []
        for name, tool_class in self._tool_classes.items():
            try:
                tool = tool_class()
                if tool.tags.intersection(tags):
                    matching_tools.append(name)
            except Exception as e:
                logger.warning(f"Error checking tool {name}: {e}")
        return matching_tools
    
    def get_tools_for_language(self, language: str) -> List[str]:
        """Get tools that support a specific language."""
        matching_tools = []
        for name, tool_class in self._tool_classes.items():
            try:
                tool = tool_class()
                if language.lower() in [lang.lower() for lang in tool.supported_languages]:
                    matching_tools.append(name)
            except Exception as e:
                logger.warning(f"Error checking tool {name}: {e}")
        return matching_tools
    
    def get_all_tools_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered tools."""
        tools_info = {}
        for name, tool_class in self._tool_classes.items():
            try:
                tool = tool_class()
                tools_info[name] = tool.get_info()
            except Exception as e:
                logger.error(f"Error getting info for tool {name}: {e}")
                tools_info[name] = {
                    'name': name,
                    'error': str(e),
                    'available': False
                }
        return tools_info
    
    def discover_tools(self) -> Dict[str, bool]:
        """Discover which tools are available on the system."""
        discovery_results = {}
        for name, tool_class in self._tool_classes.items():
            try:
                tool = tool_class()
                discovery_results[name] = tool.is_available()
            except Exception as e:
                logger.warning(f"Error discovering tool {name}: {e}")
                discovery_results[name] = False
        return discovery_results

# Global registry instance
_tool_registry = ToolRegistry()

def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry."""
    return _tool_registry

def register_tool(tool_class: type) -> None:
    """Register a tool class with the global registry."""
    _tool_registry.register_tool(tool_class)

# Tool decorator for easy registration
def analysis_tool(cls: type) -> type:
    """Decorator to automatically register analysis tools."""
    register_tool(cls)
    return cls