"""
Container-Based Tool Registry
============================

Enhanced tool registry that groups tools by analyzer containers and provides
individual tool configuration schemas and metadata.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class AnalyzerContainer(str, Enum):
    """Analyzer container types."""
    STATIC = "static-analyzer"
    DYNAMIC = "dynamic-analyzer"
    PERFORMANCE = "performance-tester"
    AI = "ai-analyzer"


@dataclass
class ToolParameter:
    """Represents a tool configuration parameter."""
    name: str
    type: str  # 'string', 'integer', 'float', 'boolean', 'array', 'object'
    description: str
    default: Any = None
    required: bool = False
    options: Optional[List[Any]] = None  # For enum/select types
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    pattern: Optional[str] = None  # For string validation


@dataclass
class ToolConfigSchema:
    """Configuration schema for a tool."""
    parameters: List[ToolParameter] = field(default_factory=list)
    examples: Dict[str, Any] = field(default_factory=dict)
    documentation_url: Optional[str] = None


@dataclass
class ContainerTool:
    """Enhanced tool information with container context."""
    name: str
    display_name: str
    description: str
    container: AnalyzerContainer
    tags: Set[str]
    supported_languages: Set[str]
    available: bool = False
    version: Optional[str] = None
    config_schema: Optional[ToolConfigSchema] = None
    cli_flags: List[str] = field(default_factory=list)
    output_formats: List[str] = field(default_factory=list)


class ContainerToolRegistry:
    """Enhanced tool registry grouped by analyzer containers."""
    
    def __init__(self):
        self._tools: Dict[str, ContainerTool] = {}
        self._initialized = False
        
    def initialize(self) -> None:
        """Initialize the registry with all available tools."""
        if self._initialized:
            return
            
        self._register_static_analyzer_tools()
        self._register_dynamic_analyzer_tools()
        self._register_performance_tester_tools()
        self._register_ai_analyzer_tools()
        
        self._initialized = True
        logger.info(f"Initialized container tool registry with {len(self._tools)} tools")
    
    def _register_static_analyzer_tools(self) -> None:
        """Register tools from the static-analyzer container."""
        
        # Bandit - Python security scanner
        bandit_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("format", "string", "Output format", "json", 
                            options=["json", "csv", "txt", "html", "xml"]),
                ToolParameter("severity_level", "string", "Minimum severity level", "low",
                            options=["low", "medium", "high"]),
                ToolParameter("confidence_level", "string", "Minimum confidence level", "low",
                            options=["low", "medium", "high"]),
                ToolParameter("exclude_dirs", "array", "Directories to exclude", 
                            ["tests", "__pycache__", ".git"]),
                ToolParameter("skips", "array", "Test IDs to skip", ["B101"]),
                ToolParameter("tests", "array", "Specific test IDs to run", []),
                ToolParameter("baseline_file", "string", "Baseline file for comparison", ""),
                ToolParameter("context_lines", "integer", "Lines of context around findings", 3,
                            min_value=0, max_value=10)
            ],
            examples={
                "security_focused": {
                    "severity_level": "medium",
                    "confidence_level": "high",
                    "skips": ["B101", "B601"]
                },
                "comprehensive": {
                    "format": "json",
                    "exclude_dirs": ["tests", "migrations", "__pycache__"]
                }
            },
            documentation_url="https://bandit.readthedocs.io/"
        )
        
        self._tools["bandit"] = ContainerTool(
            name="bandit",
            display_name="Bandit Security Scanner",
            description="Python security vulnerability scanner",
            container=AnalyzerContainer.STATIC,
            tags={"security", "python", "vulnerability"},
            supported_languages={"python"},
            available=True,
            config_schema=bandit_schema,
            cli_flags=["-r", "-f", "-x", "-s", "-t", "-l", "-i", "-c"],
            output_formats=["json", "csv", "txt", "html", "xml"]
        )
        
        # Pylint - Python code quality
        pylint_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("disable", "array", "Messages to disable", 
                            ["missing-docstring", "too-few-public-methods"]),
                ToolParameter("enable", "array", "Messages to enable", []),
                ToolParameter("max_line_length", "integer", "Maximum line length", 100,
                            min_value=50, max_value=200),
                ToolParameter("max_module_lines", "integer", "Maximum module lines", 1000,
                            min_value=100, max_value=5000),
                ToolParameter("output_format", "string", "Output format", "json",
                            options=["json", "text", "parseable", "colorized"]),
                ToolParameter("errors_only", "boolean", "Show only errors", False),
                ToolParameter("jobs", "integer", "Number of parallel jobs", 0,
                            min_value=0, max_value=8),
                ToolParameter("max_files", "integer", "Maximum files to analyze", 10,
                            min_value=1, max_value=100),
                ToolParameter("good_names", "array", "Good variable names", 
                            ["i", "j", "k", "ex", "Run", "_", "id", "pk"]),
                ToolParameter("bad_names", "array", "Bad variable names",
                            ["foo", "bar", "baz", "toto", "tutu", "tata"])
            ],
            examples={
                "strict": {
                    "max_line_length": 88,
                    "disable": ["missing-docstring"],
                    "errors_only": False
                },
                "errors_only": {
                    "errors_only": True,
                    "max_files": 50
                }
            },
            documentation_url="https://pylint.pycqa.org/"
        )
        
        self._tools["pylint"] = ContainerTool(
            name="pylint",
            display_name="Pylint Code Quality",
            description="Python static code analysis tool",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "python", "linting"},
            supported_languages={"python"},
            available=True,
            config_schema=pylint_schema,
            cli_flags=["--rcfile", "--disable", "--enable", "--errors-only", "-j"],
            output_formats=["json", "text", "parseable", "colorized"]
        )
        
        # ESLint - JavaScript/TypeScript linter
        eslint_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("extends", "array", "Configuration presets to extend",
                            ["eslint:recommended"]),
                ToolParameter("env", "object", "Environment settings",
                            {"browser": True, "es2021": True, "node": True}),
                ToolParameter("rules", "object", "Rule configuration", {
                    "no-eval": "error",
                    "no-console": "warn",
                    "no-debugger": "error"
                }),
                ToolParameter("format", "string", "Output format", "json",
                            options=["json", "stylish", "compact", "unix"]),
                ToolParameter("fix", "boolean", "Auto-fix issues", False),
                ToolParameter("max_warnings", "integer", "Maximum warnings allowed", None,
                            min_value=0),
                ToolParameter("ignore_patterns", "array", "Patterns to ignore",
                            ["node_modules", "dist", "build"]),
                ToolParameter("parser_options", "object", "Parser options", {
                    "ecmaVersion": 2021,
                    "sourceType": "module"
                })
            ],
            examples={
                "strict": {
                    "extends": ["eslint:recommended", "@typescript-eslint/recommended"],
                    "rules": {"no-console": "error", "no-debugger": "error"}
                },
                "relaxed": {
                    "rules": {"no-console": "warn", "no-unused-vars": "warn"}
                }
            },
            documentation_url="https://eslint.org/"
        )
        
        self._tools["eslint"] = ContainerTool(
            name="eslint",
            display_name="ESLint JavaScript Linter",
            description="JavaScript and TypeScript static analysis tool",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "javascript", "typescript", "linting"},
            supported_languages={"javascript", "typescript"},
            available=True,
            config_schema=eslint_schema,
            cli_flags=["--format", "--config", "--fix", "--max-warnings"],
            output_formats=["json", "stylish", "compact", "unix"]
        )
        
        # Add more static analyzer tools...
        self._add_more_static_tools()
    
    def _add_more_static_tools(self) -> None:
        """Add remaining static analyzer tools."""
        
        # Safety - Python dependency scanner
        safety_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("packages", "array", "Specific packages to check", []),
                ToolParameter("ignore", "array", "Vulnerability IDs to ignore", []),
                ToolParameter("key", "string", "Safety API key", ""),
                ToolParameter("output_format", "string", "Output format", "json",
                            options=["json", "text", "bare"])
            ],
            documentation_url="https://pyup.io/safety/"
        )
        
        self._tools["safety"] = ContainerTool(
            name="safety",
            display_name="Safety Dependency Scanner",
            description="Python dependency vulnerability scanner",
            container=AnalyzerContainer.STATIC,
            tags={"security", "python", "dependencies"},
            supported_languages={"python"},
            available=True,
            config_schema=safety_schema
        )
        
        # Semgrep - Multi-language security scanner
        semgrep_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("config", "string", "Configuration preset", "auto",
                            options=["auto", "p/security-audit", "p/owasp-top-ten", "p/javascript"]),
                ToolParameter("rules", "array", "Specific rule sets", []),
                ToolParameter("severity", "string", "Minimum severity", "INFO",
                            options=["ERROR", "WARNING", "INFO"]),
                ToolParameter("exclude", "array", "Paths to exclude", []),
                ToolParameter("timeout", "integer", "Analysis timeout in seconds", 30,
                            min_value=10, max_value=300),
                ToolParameter("max_memory", "integer", "Maximum memory usage in MB", 5000,
                            min_value=1000, max_value=10000),
                ToolParameter("sarif_output", "boolean", "Output in SARIF format", False)
            ],
            documentation_url="https://semgrep.dev/"
        )
        
        self._tools["semgrep"] = ContainerTool(
            name="semgrep",
            display_name="Semgrep Security Scanner",
            description="Multi-language static analysis security scanner",
            container=AnalyzerContainer.STATIC,
            tags={"security", "multi-language", "sast"},
            supported_languages={"python", "javascript", "typescript", "java", "go"},
            available=True,
            config_schema=semgrep_schema
        )
        
        # MyPy - Python type checker
        mypy_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("strict", "boolean", "Enable strict mode", False),
                ToolParameter("ignore_missing_imports", "boolean", "Ignore missing imports", True),
                ToolParameter("config_file", "string", "Custom config file path", ""),
                ToolParameter("max_files", "integer", "Maximum files to check", 10,
                            min_value=1, max_value=100)
            ],
            documentation_url="https://mypy.readthedocs.io/"
        )
        
        self._tools["mypy"] = ContainerTool(
            name="mypy",
            display_name="MyPy Type Checker",
            description="Static type checker for Python",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "python", "typing"},
            supported_languages={"python"},
            available=True,
            config_schema=mypy_schema
        )
        
        # JSHint - JavaScript quality tool
        jshint_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("esversion", "integer", "ECMAScript version", 6,
                            options=[5, 6, 7, 8, 9, 10, 11]),
                ToolParameter("strict", "boolean", "Require strict mode", True),
                ToolParameter("undef", "boolean", "Require variable declarations", True),
                ToolParameter("unused", "boolean", "Check for unused variables", True),
                ToolParameter("browser", "boolean", "Browser environment", True),
                ToolParameter("node", "boolean", "Node.js environment", True),
                ToolParameter("max_files", "integer", "Maximum files to analyze", 30,
                            min_value=1, max_value=100)
            ],
            documentation_url="https://jshint.com/"
        )
        
        self._tools["jshint"] = ContainerTool(
            name="jshint",
            display_name="JSHint Code Quality",
            description="JavaScript code quality tool",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "javascript", "linting"},
            supported_languages={"javascript"},
            available=True,
            config_schema=jshint_schema
        )
        
        # Vulture - Dead code detector
        vulture_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("min_confidence", "integer", "Minimum confidence level", 80,
                            min_value=0, max_value=100),
                ToolParameter("exclude", "array", "Patterns to exclude", []),
                ToolParameter("ignore_decorators", "array", "Decorators to ignore", []),
                ToolParameter("ignore_names", "array", "Names to ignore", []),
                ToolParameter("sort_by_size", "boolean", "Sort results by size", False),
                ToolParameter("verbose", "boolean", "Verbose output", False)
            ],
            documentation_url="https://pypi.org/project/vulture/"
        )
        
        self._tools["vulture"] = ContainerTool(
            name="vulture",
            display_name="Vulture Dead Code Detector",
            description="Finds unused code in Python programs",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "python", "dead-code"},
            supported_languages={"python"},
            available=True,
            config_schema=vulture_schema
        )
    
    def _register_dynamic_analyzer_tools(self) -> None:
        """Register tools from the dynamic-analyzer container."""
        
        # ZAP-style security scanner
        zap_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("scan_types", "array", "Types of scans to perform",
                            ["ssl_security", "security_headers", "common_vulnerabilities"]),
                ToolParameter("timeout", "integer", "Request timeout in seconds", 10,
                            min_value=5, max_value=60),
                ToolParameter("max_redirects", "integer", "Maximum redirects to follow", 5,
                            min_value=0, max_value=20)
            ],
            documentation_url="https://www.zaproxy.org/"
        )
        
        self._tools["zap"] = ContainerTool(
            name="zap",
            display_name="ZAP Security Scanner",
            description="Web application security scanner (ZAP-style)",
            container=AnalyzerContainer.DYNAMIC,
            tags={"security", "web", "dynamic"},
            supported_languages={"web"},
            available=True,
            config_schema=zap_schema
        )
        
        # Curl - HTTP client
        curl_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("timeout", "integer", "Connection timeout", 10,
                            min_value=1, max_value=120),
                ToolParameter("max_time", "integer", "Maximum request time", 30,
                            min_value=1, max_value=300),
                ToolParameter("follow_redirects", "boolean", "Follow HTTP redirects", True),
                ToolParameter("verify_ssl", "boolean", "Verify SSL certificates", True),
                ToolParameter("user_agent", "string", "Custom User-Agent header", "")
            ],
            documentation_url="https://curl.se/docs/"
        )
        
        self._tools["curl"] = ContainerTool(
            name="curl",
            display_name="cURL HTTP Client",
            description="HTTP client for connectivity and response testing",
            container=AnalyzerContainer.DYNAMIC,
            tags={"connectivity", "http", "testing"},
            supported_languages={"web"},
            available=True,
            config_schema=curl_schema
        )
        
        # Nmap - Network scanner
        nmap_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("scan_type", "string", "Type of scan", "basic",
                            options=["basic", "stealth", "service", "os"]),
                ToolParameter("ports", "array", "Specific ports to scan", 
                            [80, 443, 22, 21, 25, 53, 110, 993, 995]),
                ToolParameter("timing", "string", "Timing template", "T4",
                            options=["T0", "T1", "T2", "T3", "T4", "T5"]),
                ToolParameter("timeout", "integer", "Scan timeout in seconds", 60,
                            min_value=10, max_value=300)
            ],
            documentation_url="https://nmap.org/"
        )
        
        self._tools["nmap"] = ContainerTool(
            name="nmap",
            display_name="Nmap Network Scanner",
            description="Network discovery and security auditing tool",
            container=AnalyzerContainer.DYNAMIC,
            tags={"network", "security", "scanning"},
            supported_languages={"network"},
            available=True,
            config_schema=nmap_schema
        )
    
    def _register_performance_tester_tools(self) -> None:
        """Register tools from the performance-tester container."""
        
        # Locust - Load testing
        locust_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("users", "integer", "Number of concurrent users", 50,
                            min_value=1, max_value=1000),
                ToolParameter("spawn_rate", "float", "User spawn rate per second", 2.0,
                            min_value=0.1, max_value=100.0),
                ToolParameter("run_time", "string", "Test duration", "30s",
                            pattern=r"^\d+[smh]$"),
                ToolParameter("host", "string", "Target host URL", "",
                            pattern=r"^https?://.*"),
                ToolParameter("headless", "boolean", "Run without web UI", True),
                ToolParameter("csv_output", "boolean", "Generate CSV reports", True),
                ToolParameter("failure_threshold", "float", "Failure rate threshold", 1.0,
                            min_value=0.0, max_value=100.0)
            ],
            examples={
                "light_load": {
                    "users": 10,
                    "spawn_rate": 1.0,
                    "run_time": "60s"
                },
                "stress_test": {
                    "users": 100,
                    "spawn_rate": 5.0,
                    "run_time": "300s"
                }
            },
            documentation_url="https://docs.locust.io/"
        )
        
        self._tools["locust"] = ContainerTool(
            name="locust",
            display_name="Locust Load Testing",
            description="Modern load testing framework",
            container=AnalyzerContainer.PERFORMANCE,
            tags={"performance", "load_testing", "web"},
            supported_languages={"web"},
            available=True,
            config_schema=locust_schema
        )
        
        # Apache Bench - Simple load testing
        ab_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("requests", "integer", "Total number of requests", 100,
                            min_value=1, max_value=10000),
                ToolParameter("concurrency", "integer", "Number of concurrent requests", 10,
                            min_value=1, max_value=100),
                ToolParameter("timeout", "integer", "Request timeout in seconds", 30,
                            min_value=1, max_value=300),
                ToolParameter("keep_alive", "boolean", "Use HTTP keep-alive", False)
            ],
            examples={
                "quick_test": {
                    "requests": 50,
                    "concurrency": 5
                },
                "load_test": {
                    "requests": 1000,
                    "concurrency": 20
                }
            },
            documentation_url="https://httpd.apache.org/docs/current/programs/ab.html"
        )
        
        self._tools["ab"] = ContainerTool(
            name="ab",
            display_name="Apache Bench",
            description="Simple HTTP load testing tool",
            container=AnalyzerContainer.PERFORMANCE,
            tags={"performance", "load_testing", "simple"},
            supported_languages={"web"},
            available=True,
            config_schema=ab_schema
        )
        
        # aiohttp - Built-in async testing
        aiohttp_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("requests", "integer", "Total number of requests", 50,
                            min_value=1, max_value=1000),
                ToolParameter("concurrency", "integer", "Concurrent connections", 5,
                            min_value=1, max_value=50),
                ToolParameter("timeout", "integer", "Request timeout in seconds", 30,
                            min_value=1, max_value=120)
            ],
            documentation_url="https://docs.aiohttp.org/"
        )
        
        self._tools["aiohttp"] = ContainerTool(
            name="aiohttp",
            display_name="aiohttp Load Test",
            description="Built-in async HTTP load testing",
            container=AnalyzerContainer.PERFORMANCE,
            tags={"performance", "async", "built-in"},
            supported_languages={"web"},
            available=True,
            config_schema=aiohttp_schema
        )
    
    def _register_ai_analyzer_tools(self) -> None:
        """Register tools from the ai-analyzer container."""
        
        # Requirements analyzer
        requirements_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("ai_model", "string", "AI model to use", "anthropic/claude-3-haiku",
                            options=["anthropic/claude-3-haiku", "openai/gpt-4", "local/llama"]),
                ToolParameter("temperature", "float", "AI model temperature", 0.1,
                            min_value=0.0, max_value=1.0),
                ToolParameter("max_tokens", "integer", "Maximum response tokens", 500,
                            min_value=100, max_value=2000),
                ToolParameter("confidence_threshold", "float", "Minimum confidence for results", 0.7,
                            min_value=0.0, max_value=1.0),
                ToolParameter("analysis_depth", "string", "Analysis depth level", "standard",
                            options=["basic", "standard", "detailed"])
            ],
            documentation_url="https://docs.anthropic.com/"
        )
        
        self._tools["requirements-scanner"] = ContainerTool(
            name="requirements-scanner",
            display_name="AI Requirements Scanner",
            description="AI-powered requirements analysis and validation",
            container=AnalyzerContainer.AI,
            tags={"ai", "requirements", "analysis", "security"},
            supported_languages={"documentation", "code"},
            available=True,
            config_schema=requirements_schema
        )
    
    def get_tools_by_container(self, container: AnalyzerContainer) -> List[ContainerTool]:
        """Get all tools for a specific container."""
        self.initialize()
        return [tool for tool in self._tools.values() if tool.container == container]
    
    def get_tool(self, name: str) -> Optional[ContainerTool]:
        """Get a specific tool by name."""
        self.initialize()
        return self._tools.get(name)
    
    def get_all_tools(self) -> Dict[str, ContainerTool]:
        """Get all registered tools."""
        self.initialize()
        return self._tools.copy()
    
    def get_tools_by_tags(self, tags: Set[str]) -> List[ContainerTool]:
        """Get tools that have any of the specified tags."""
        self.initialize()
        matching_tools = []
        for tool in self._tools.values():
            if tool.tags.intersection(tags):
                matching_tools.append(tool)
        return matching_tools
    
    def get_tools_for_language(self, language: str) -> List[ContainerTool]:
        """Get tools that support a specific language."""
        self.initialize()
        matching_tools = []
        for tool in self._tools.values():
            if language.lower() in [lang.lower() for lang in tool.supported_languages]:
                matching_tools.append(tool)
        return matching_tools
    
    def get_containers(self) -> List[AnalyzerContainer]:
        """Get all analyzer containers."""
        return list(AnalyzerContainer)

    def get_all_profiles(self) -> List[Dict[str, Any]]:
        """Return available tool execution profiles (compatibility shim)."""
        # Legacy code expects a list of profile dictionaries with optional
        # ``to_dict`` methods. Profiles have not yet been ported to the container
        # registry, so provide an empty list instead of raising AttributeError.
        return []
    
    def get_container_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all containers and their tools."""
        self.initialize()
        container_info = {}
        
        for container in AnalyzerContainer:
            tools = self.get_tools_by_container(container)
            container_info[container.value] = {
                "name": container.value,
                "display_name": container.value.replace("-", " ").title(),
                "description": self._get_container_description(container),
                "tool_count": len(tools),
                "tools": [tool.name for tool in tools],
                "tags": list(set().union(*[tool.tags for tool in tools])),
                "languages": list(set().union(*[tool.supported_languages for tool in tools]))
            }
        
        return container_info
    
    def _get_container_description(self, container: AnalyzerContainer) -> str:
        """Get description for a container."""
        descriptions = {
            AnalyzerContainer.STATIC: "Static code analysis tools for security and quality",
            AnalyzerContainer.DYNAMIC: "Dynamic analysis tools for running applications",
            AnalyzerContainer.PERFORMANCE: "Performance testing and load testing tools",
            AnalyzerContainer.AI: "AI-powered analysis and requirements validation tools"
        }
        return descriptions.get(container, "Analysis tools")
    
    def update_tool_availability(self, availability_results: Dict[str, bool]) -> None:
        """Update tool availability based on runtime checks."""
        self.initialize()
        for tool_name, available in availability_results.items():
            if tool_name in self._tools:
                self._tools[tool_name].available = available


# Global container tool registry instance
_container_registry = ContainerToolRegistry()


def get_container_tool_registry() -> ContainerToolRegistry:
    """Get the global container tool registry."""
    return _container_registry