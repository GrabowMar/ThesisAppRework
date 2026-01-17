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


def tool_config_schema_to_dict(schema: ToolConfigSchema) -> Dict[str, Any]:
    """Convert a ToolConfigSchema to a JSON-serializable dict."""
    return {
        'parameters': [
            {
                'name': p.name,
                'type': p.type,
                'description': p.description,
                'default': p.default,
                'required': p.required,
                'options': p.options,
                'min_value': p.min_value,
                'max_value': p.max_value,
                'pattern': p.pattern,
            }
            for p in (schema.parameters or [])
        ],
        'examples': schema.examples,
        'documentation_url': schema.documentation_url,
    }


def container_tool_summary_dict(tool: ContainerTool) -> Dict[str, Any]:
    """Serialize tool metadata for list-style views (no container/CLI/output fields)."""
    return {
        'name': tool.name,
        'display_name': tool.display_name,
        'description': tool.description,
        'tags': list(tool.tags),
        'supported_languages': list(tool.supported_languages),
        'available': tool.available,
        'version': tool.version,
        'config_schema': tool.config_schema,
    }


def container_tool_detail_dict(tool: ContainerTool, *, schema_as_dict: bool = False) -> Dict[str, Any]:
    """Serialize tool metadata for detail/API responses."""
    data: Dict[str, Any] = {
        'name': tool.name,
        'display_name': tool.display_name,
        'description': tool.description,
        'container': tool.container.value,
        'tags': list(tool.tags),
        'supported_languages': list(tool.supported_languages),
        'available': tool.available,
        'version': tool.version,
        'cli_flags': tool.cli_flags,
        'output_formats': tool.output_formats,
    }

    if tool.config_schema:
        data['config_schema'] = (
            tool_config_schema_to_dict(tool.config_schema)
            if schema_as_dict
            else tool.config_schema
        )

    return data


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
        
        # Ruff - Fast Python linter
        ruff_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("select", "array", "Rules to enable", []),
                ToolParameter("ignore", "array", "Rules to ignore", []),
                ToolParameter("fix", "boolean", "Auto-fix issues", False),
                ToolParameter("line_length", "integer", "Maximum line length", 88,
                            min_value=50, max_value=200),
                ToolParameter("target_version", "string", "Python version", "py311",
                            options=["py37", "py38", "py39", "py310", "py311", "py312"]),
                ToolParameter("respect_gitignore", "boolean", "Respect .gitignore", True)
            ],
            documentation_url="https://docs.astral.sh/ruff/"
        )
        
        self._tools["ruff"] = ContainerTool(
            name="ruff",
            display_name="Ruff Fast Linter",
            description="Extremely fast Python linter (10-100x faster than pylint/flake8)",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "python", "linting", "fast"},
            supported_languages={"python"},
            available=True,
            config_schema=ruff_schema
        )
        
        # pip-audit - Python dependency vulnerability scanner
        pip_audit_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("format", "string", "Output format", "json",
                            options=["json", "text", "cyclonedx-json", "cyclonedx-xml"]),
                ToolParameter("vulnerability_service", "string", "Vulnerability service to use", "pypi",
                            options=["pypi", "osv"]),
                ToolParameter("ignore_vulns", "array", "Vulnerability IDs to ignore", []),
                ToolParameter("require_hashes", "boolean", "Require package hashes", False),
                ToolParameter("no_deps", "boolean", "Skip dependency resolution", False),
                ToolParameter("cache_dir", "string", "Custom cache directory", "")
            ],
            examples={
                "comprehensive": {
                    "format": "json",
                    "vulnerability_service": "osv",
                    "require_hashes": False
                },
                "quick_scan": {
                    "format": "json",
                    "no_deps": True
                }
            },
            documentation_url="https://pypi.org/project/pip-audit/"
        )
        
        self._tools["pip-audit"] = ContainerTool(
            name="pip-audit",
            display_name="pip-audit CVE Scanner",
            description="Python dependency CVE and vulnerability scanner",
            container=AnalyzerContainer.STATIC,
            tags={"security", "python", "dependencies", "cve"},
            supported_languages={"python"},
            available=True,
            config_schema=pip_audit_schema,
            cli_flags=["-f", "--format", "-s", "--vulnerability-service", "--ignore-vuln"],
            output_formats=["json", "text", "cyclonedx-json", "cyclonedx-xml"]
        )
        
        # npm-audit - JavaScript/Node.js dependency vulnerability scanner
        npm_audit_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("audit_level", "string", "Minimum severity level", "low",
                            options=["info", "low", "moderate", "high", "critical"]),
                ToolParameter("production_only", "boolean", "Audit production dependencies only", False),
                ToolParameter("omit", "array", "Dependency types to omit",
                            options=["dev", "optional", "peer"]),
                ToolParameter("registry", "string", "Custom npm registry URL", ""),
                ToolParameter("format", "string", "Output format", "json",
                            options=["json"])
            ],
            examples={
                "production_only": {
                    "production_only": True,
                    "audit_level": "moderate"
                },
                "comprehensive": {
                    "audit_level": "low",
                    "production_only": False
                }
            },
            documentation_url="https://docs.npmjs.com/cli/v9/commands/npm-audit"
        )
        
        self._tools["npm-audit"] = ContainerTool(
            name="npm-audit",
            display_name="npm-audit CVE Scanner",
            description="JavaScript/Node.js dependency CVE and vulnerability scanner",
            container=AnalyzerContainer.STATIC,
            tags={"security", "javascript", "dependencies", "cve"},
            supported_languages={"javascript", "typescript"},
            available=True,
            config_schema=npm_audit_schema,
            cli_flags=["--audit-level", "--production", "--omit", "--registry", "--json"],
            output_formats=["json"]
        )
        
        # flake8 - Python style guide enforcer
        flake8_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("max_line_length", "integer", "Maximum line length", 79,
                            min_value=50, max_value=200),
                ToolParameter("max_complexity", "integer", "Maximum McCabe complexity", 10,
                            min_value=1, max_value=50),
                ToolParameter("ignore", "array", "Error codes to ignore", ["E501", "W503"]),
                ToolParameter("select", "array", "Error codes to select", []),
                ToolParameter("format", "string", "Output format", "default",
                            options=["default", "pylint", "json"]),
                ToolParameter("show_source", "boolean", "Show source code", False),
                ToolParameter("statistics", "boolean", "Show statistics", False),
                ToolParameter("count", "boolean", "Print total number of errors", False)
            ],
            examples={
                "strict": {
                    "max_line_length": 88,
                    "max_complexity": 10,
                    "ignore": []
                },
                "relaxed": {
                    "max_line_length": 120,
                    "ignore": ["E501", "W503", "E203"]
                }
            },
            documentation_url="https://flake8.pycqa.org/"
        )
        
        self._tools["flake8"] = ContainerTool(
            name="flake8",
            display_name="Flake8 Style Checker",
            description="Python style guide enforcement tool combining PyFlakes, pycodestyle, and McCabe",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "python", "style", "linting"},
            supported_languages={"python"},
            available=True,
            config_schema=flake8_schema,
            cli_flags=["--max-line-length", "--max-complexity", "--ignore", "--select", "--format"],
            output_formats=["default", "pylint", "json"]
        )
        
        # stylelint - CSS/SCSS linter
        stylelint_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("config", "string", "Configuration preset", "stylelint-config-standard",
                            options=["stylelint-config-standard", "stylelint-config-recommended"]),
                ToolParameter("fix", "boolean", "Auto-fix issues", False),
                ToolParameter("formatter", "string", "Output format", "json",
                            options=["json", "string", "verbose", "compact"]),
                ToolParameter("ignore_disables", "boolean", "Ignore inline disable comments", False),
                ToolParameter("max_warnings", "integer", "Maximum warnings allowed", None,
                            min_value=0),
                ToolParameter("quiet", "boolean", "Only report errors", False),
                ToolParameter("allow_empty_input", "boolean", "Allow empty input", False)
            ],
            examples={
                "standard": {
                    "config": "stylelint-config-standard",
                    "fix": False
                },
                "auto_fix": {
                    "config": "stylelint-config-standard",
                    "fix": True
                }
            },
            documentation_url="https://stylelint.io/"
        )
        
        self._tools["stylelint"] = ContainerTool(
            name="stylelint",
            display_name="Stylelint CSS Linter",
            description="Modern CSS/SCSS linter for style guide enforcement",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "css", "scss", "style", "linting"},
            supported_languages={"css", "scss", "sass", "less"},
            available=True,
            config_schema=stylelint_schema,
            cli_flags=["--config", "--fix", "--formatter", "--max-warnings", "--quiet"],
            output_formats=["json", "string", "verbose", "compact"]
        )
        
        # JSHint - JavaScript code quality tool
        jshint_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("esversion", "integer", "ECMAScript version", 6,
                            options=[3, 5, 6, 7, 8, 9, 10, 11]),
                ToolParameter("node", "boolean", "Enable Node.js environment", False),
                ToolParameter("browser", "boolean", "Enable browser environment", True),
                ToolParameter("globals", "object", "Predefined globals", {}),
                ToolParameter("strict", "string", "Strict mode", "implied",
                            options=["global", "implied", "false"]),
                ToolParameter("undef", "boolean", "Prohibit undefined variables", True),
                ToolParameter("unused", "boolean", "Warn about unused variables", True),
                ToolParameter("reporter", "string", "Output format", "jslint",
                            options=["jslint", "checkstyle", "unix"])
            ],
            examples={
                "modern": {
                    "esversion": 11,
                    "browser": True,
                    "node": False
                },
                "node_app": {
                    "esversion": 9,
                    "node": True,
                    "browser": False
                }
            },
            documentation_url="https://jshint.com/docs/"
        )
        
        self._tools["jshint"] = ContainerTool(
            name="jshint",
            display_name="JSHint Code Quality",
            description="JavaScript code quality tool for detecting errors and potential problems",
            container=AnalyzerContainer.STATIC,
            tags={"quality", "javascript", "linting"},
            supported_languages={"javascript"},
            available=True,
            config_schema=jshint_schema,
            cli_flags=["--config", "--reporter", "--extract", "--verbose"],
            output_formats=["jslint", "checkstyle", "unix"]
        )
    
    def _register_dynamic_analyzer_tools(self) -> None:
        """Register tools from the dynamic-analyzer container."""
        
        # ZAP-style security scanner
        zap_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("scan_types", "array", "Types of scans to perform",
                            ["ssl_security", "security_headers", "common_vulnerabilities"]),
                ToolParameter(
                    "run_ajax_spider",
                    "boolean",
                    "Enable ZAP AJAX Spider (discovers JS-rendered routes; may require browser dependencies)",
                    False,
                ),
                ToolParameter("timeout", "integer", "Request timeout in seconds", 10,
                            min_value=5, max_value=60),
                ToolParameter("max_redirects", "integer", "Maximum redirects to follow", 5,
                            min_value=0, max_value=20)
            ],
            examples={
                "baseline_safe": {
                    "run_ajax_spider": False
                },
                "with_ajax_spider": {
                    "run_ajax_spider": True
                }
            },
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
        
        # Artillery - Modern load testing toolkit
        artillery_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("duration", "integer", "Test duration in seconds", 60,
                            min_value=10, max_value=600),
                ToolParameter("arrival_rate", "integer", "New virtual users per second", 10,
                            min_value=1, max_value=100),
                ToolParameter("ramp_to", "integer", "Ramp up to this many users", None,
                            min_value=1, max_value=1000),
                ToolParameter("phases", "array", "Test phases configuration", []),
                ToolParameter("target", "string", "Target URL", "",
                            pattern=r"^https?://.*"),
                ToolParameter("timeout", "integer", "Request timeout in seconds", 10,
                            min_value=1, max_value=120),
                ToolParameter("output_format", "string", "Output format", "json",
                            options=["json", "text"]),
                ToolParameter("scenarios", "array", "Test scenarios", [])
            ],
            examples={
                "warm_up": {
                    "duration": 60,
                    "arrival_rate": 5,
                    "timeout": 10
                },
                "load_test": {
                    "duration": 120,
                    "arrival_rate": 10,
                    "ramp_to": 50
                },
                "stress_test": {
                    "duration": 300,
                    "arrival_rate": 20,
                    "ramp_to": 100
                }
            },
            documentation_url="https://www.artillery.io/docs"
        )
        
        self._tools["artillery"] = ContainerTool(
            name="artillery",
            display_name="Artillery Load Testing",
            description="Modern, powerful, and easy-to-use load testing toolkit",
            container=AnalyzerContainer.PERFORMANCE,
            tags={"performance", "load_testing", "modern", "scenarios"},
            supported_languages={"web"},
            available=True,
            config_schema=artillery_schema,
            cli_flags=["--target", "--output", "--overrides", "--config"],
            output_formats=["json", "text"]
        )
    
    def _register_ai_analyzer_tools(self) -> None:
        """Register tools from the ai-analyzer container."""
        import os
        has_openrouter_key = bool(os.getenv('OPENROUTER_API_KEY'))
        
        # Requirements Scanner - AI-powered requirements validation
        requirements_scanner_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("template_id", "integer", "Requirements template ID", 1,
                            min_value=1, max_value=100),
                ToolParameter("gemini_model", "string", "AI model for analysis", "anthropic/claude-3-5-haiku",
                            options=["anthropic/claude-3-5-haiku", "anthropic/claude-3-5-sonnet", 
                                   "openai/gpt-4o-mini", "openai/gpt-4o"]),
                ToolParameter("scan_mode", "string", "Analysis scope", "full",
                            options=["backend_only", "frontend_only", "admin_only", "full"]),
                ToolParameter("include_endpoint_tests", "boolean", "Also run curl endpoint tests", False)
            ],
            examples={
                "default": {
                    "template_id": 1,
                    "gemini_model": "anthropic/claude-3-5-haiku",
                    "scan_mode": "full",
                    "include_endpoint_tests": False
                },
                "high_quality": {
                    "template_id": 1,
                    "gemini_model": "anthropic/claude-3-5-sonnet",
                    "scan_mode": "full",
                    "include_endpoint_tests": False
                },
                "with_endpoints": {
                    "template_id": 1,
                    "gemini_model": "anthropic/claude-3-5-haiku",
                    "scan_mode": "full",
                    "include_endpoint_tests": True
                }
            },
            documentation_url="https://github.com/GrabowMar/ThesisAppRework/blob/main/docs/features/ANALYSIS.md"
        )
        
        self._tools["requirements-scanner"] = ContainerTool(
            name="requirements-scanner",
            display_name="Requirements Scanner",
            description="AI-powered requirements validation: analyzes backend API, frontend UI, and admin functionality with code review",
            container=AnalyzerContainer.AI,
            tags={"ai", "requirements", "functional", "backend", "frontend", "admin", "code-analysis"},
            supported_languages={"python", "javascript", "typescript", "react"},
            available=has_openrouter_key,
            config_schema=requirements_scanner_schema
        )
        
        # Curl Endpoint Tester - Pure HTTP endpoint validation (no AI required)
        curl_tester_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("template_id", "integer", "Requirements template ID (defines endpoints)", 1,
                            min_value=1, max_value=100),
                ToolParameter("backend_port", "integer", "Application backend port", 5000,
                            min_value=1024, max_value=65535),
                ToolParameter("frontend_port", "integer", "Application frontend port", 8000,
                            min_value=1024, max_value=65535),
                ToolParameter("test_admin_endpoints", "boolean", "Test admin endpoints with auth", True),
                ToolParameter("timeout_seconds", "integer", "Request timeout in seconds", 10,
                            min_value=1, max_value=60)
            ],
            examples={
                "default": {
                    "template_id": 1,
                    "backend_port": 5000,
                    "frontend_port": 8000,
                    "test_admin_endpoints": True,
                    "timeout_seconds": 10
                },
                "quick": {
                    "template_id": 1,
                    "backend_port": 5000,
                    "test_admin_endpoints": False,
                    "timeout_seconds": 5
                }
            },
            documentation_url="https://github.com/GrabowMar/ThesisAppRework/blob/main/docs/features/ANALYSIS.md"
        )
        
        self._tools["curl-endpoint-tester"] = ContainerTool(
            name="curl-endpoint-tester",
            display_name="Curl Endpoint Tester",
            description="HTTP endpoint validation: tests API endpoints with curl requests, checks response codes and availability (no AI required)",
            container=AnalyzerContainer.AI,
            tags={"testing", "endpoints", "curl", "http", "api", "functional"},
            supported_languages={"web", "api"},
            available=True,  # Always available - doesn't require AI API key
            config_schema=curl_tester_schema
        )
        
        # Code Quality Analyzer - Measures actual code quality metrics
        quality_schema = ToolConfigSchema(
            parameters=[
                ToolParameter("template_id", "integer", "Requirements template ID", 1,
                            min_value=1, max_value=100),
                ToolParameter("gemini_model", "string", "AI model for analysis", "anthropic/claude-3-5-haiku",
                            options=["anthropic/claude-3-5-haiku", "anthropic/claude-3-5-sonnet",
                                   "openai/gpt-4o-mini", "openai/gpt-4o"]),
                ToolParameter("full_scan", "boolean", "Scan entire codebase (vs backend+frontend only)", False)
            ],
            examples={
                "focused": {
                    "template_id": 1,
                    "full_scan": False,
                    "gemini_model": "anthropic/claude-3-5-haiku"
                },
                "comprehensive": {
                    "template_id": 1,
                    "full_scan": True,
                    "gemini_model": "anthropic/claude-3-5-sonnet"
                }
            },
            documentation_url="https://github.com/GrabowMar/ThesisAppRework/blob/main/docs/features/ANALYSIS.md"
        )
        
        self._tools["code-quality-analyzer"] = ContainerTool(
            name="code-quality-analyzer",
            display_name="Code Quality Analyzer",
            description="AI-powered code quality analysis measuring 8 metrics: error handling, type safety, code organization, documentation, anti-patterns, security practices, performance patterns, and testing readiness",
            container=AnalyzerContainer.AI,
            tags={"ai", "quality", "metrics", "patterns", "best-practices", "code-quality"},
            supported_languages={"python", "javascript", "typescript", "react"},
            available=has_openrouter_key,
            config_schema=quality_schema
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