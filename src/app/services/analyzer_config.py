"""
Analyzer Configuration Service
=============================

Provides comprehensive configuration management for all analyzer tools
including Bandit, Pylint, ESLint, Apache Bench, and OpenRouter API.
"""

import json
import logging
import yaml
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class BanditConfig:
    """Configuration for Bandit security analysis."""
    enabled: bool = True
    skips: Optional[List[str]] = None  # List of test IDs to skip
    tests: Optional[List[str]] = None  # List of test IDs to include
    severity_level: str = "low"  # low, medium, high
    confidence_level: str = "low"  # low, medium, high
    format: str = "json"  # json, csv, txt, xml, yaml, sarif
    recursive: bool = True
    aggregate: str = "file"  # file, vuln
    context_lines: int = 3
    exclude_dirs: Optional[List[str]] = None
    baseline_file: Optional[str] = None
    
    # Advanced options from web search
    config_file: Optional[str] = None  # YAML config file path
    ignore_nosec: bool = False  # Ignore #nosec comments
    msg_template: Optional[str] = None  # Custom message template
    number: Optional[int] = None  # Maximum number of code lines to output
    quiet: bool = False  # Only show output in case of an error
    verbose: bool = False  # Show extra information
    exclude_paths: Optional[List[str]] = None  # Exclude specific file paths
    include_paths: Optional[List[str]] = None  # Include specific file paths
    
    def __post_init__(self):
        if self.skips is None:
            self.skips = ["B101"]  # Skip assert_used by default
        if self.tests is None:
            self.tests = []
        if self.exclude_dirs is None:
            self.exclude_dirs = ["tests", "test", "__pycache__", ".git"]
        if self.exclude_paths is None:
            self.exclude_paths = []
        if self.include_paths is None:
            self.include_paths = []


@dataclass 
class PylintConfig:
    """Configuration for Pylint code quality analysis."""
    enabled: bool = True
    rcfile: Optional[str] = None
    disable: Optional[List[str]] = None
    enable: Optional[List[str]] = None
    errors_only: bool = False
    fail_under: float = 5.0
    jobs: int = 0  # 0 = auto-detect
    load_plugins: Optional[List[str]] = None
    max_line_length: int = 100
    max_module_lines: int = 1000
    max_nested_blocks: int = 5
    good_names: Optional[List[str]] = None
    bad_names: Optional[List[str]] = None
    output_format: str = "json"  # json, parseable, colorized, msvs
    reports: bool = False
    score: bool = True
    
    # Enhanced options from web search
    extension_pkg_whitelist: Optional[List[str]] = None
    unsafe_load_any_extension: bool = False
    msg_template: Optional[str] = None
    confidence: Optional[List[str]] = None  # HIGH, INFERENCE, INFERENCE_FAILURE, UNDEFINED
    persistent: bool = True
    suggestion_mode: bool = True
    
    def __post_init__(self):
        if self.disable is None:
            self.disable = [
                "missing-docstring", "too-few-public-methods", 
                "too-many-arguments", "invalid-name"
            ]
        if self.enable is None:
            self.enable = []
        if self.load_plugins is None:
            self.load_plugins = []
        if self.good_names is None:
            self.good_names = ["i", "j", "k", "ex", "Run", "_", "id", "pk"]
        if self.bad_names is None:
            self.bad_names = ["foo", "bar", "baz", "toto", "tutu", "tata"]
        if self.extension_pkg_whitelist is None:
            self.extension_pkg_whitelist = []
        if self.confidence is None:
            self.confidence = ["HIGH", "INFERENCE"]


@dataclass
class ESLintConfig:
    """Configuration for ESLint JavaScript analysis."""
    enabled: bool = True
    config_file: Optional[str] = None
    extends: Optional[List[str]] = None
    env: Optional[Dict[str, bool]] = None
    globals: Optional[Dict[str, str]] = None
    parser: str = "espree"
    parser_options: Optional[Dict[str, Any]] = None
    plugins: Optional[List[str]] = None
    rules: Optional[Dict[str, Union[str, List[Any]]]] = None
    settings: Optional[Dict[str, Any]] = None
    ignore_patterns: Optional[List[str]] = None
    fix: bool = False
    max_warnings: int = 0
    output_file: Optional[str] = None
    format: str = "json"  # json, compact, stylish, unix, visualstudio
    
    # Enhanced options from web search (2024/2025 features)
    ecma_version: int = 2025  # Up to 2025/ES17
    source_type: str = "module"  # module, script, commonjs
    allow_import_export_everywhere: bool = False
    ecma_features: Optional[Dict[str, bool]] = None  # jsx, globalReturn, impliedStrict
    cache: bool = True
    cache_location: Optional[str] = None
    ignore_path: Optional[str] = None
    
    def __post_init__(self):
        if self.extends is None:
            self.extends = ["eslint:recommended"]
        if self.env is None:
            self.env = {"browser": True, "es2021": True, "node": True}
        if self.globals is None:
            self.globals = {}
        if self.parser_options is None:
            self.parser_options = {
                "ecmaVersion": 2021,
                "sourceType": "module",
                "ecmaFeatures": {"jsx": True}
            }
        if self.plugins is None:
            self.plugins = []
        if self.rules is None:
            self.rules = {
                "no-eval": "error",
                "no-implied-eval": "error", 
                "no-new-func": "error",
                "no-script-url": "error",
                "no-alert": "warn",
                "no-console": "warn",
                "no-debugger": "error",
                "no-unused-vars": "warn"
            }
        if self.settings is None:
            self.settings = {}
        if self.ignore_patterns is None:
            self.ignore_patterns = ["node_modules/", "dist/", "build/"]
        if self.ecma_features is None:
            self.ecma_features = {"jsx": True, "globalReturn": False, "impliedStrict": True}


@dataclass
class ApacheBenchConfig:
    """Configuration for Apache Bench performance testing."""
    enabled: bool = True
    requests: int = 100
    concurrency: int = 10
    timelimit: Optional[int] = None  # seconds
    timeout: int = 30  # seconds per request
    keep_alive: bool = False
    headers: Optional[Dict[str, str]] = None
    cookies: Optional[Dict[str, str]] = None
    auth: Optional[str] = None  # "username:password"
    method: str = "GET"
    post_file: Optional[str] = None
    put_file: Optional[str] = None
    content_type: Optional[str] = None
    csv_output: bool = True
    gnuplot_output: bool = False
    verbosity: int = 1  # 0-4
    window_size: Optional[int] = None
    quiet: bool = False
    
    # Enhanced options from web search
    disable_percentiles: bool = False  # -d flag
    suppress_confidence: bool = False  # -S flag
    no_progress: bool = False  # -q flag for >150 requests
    enable_ssl: bool = False
    ssl_protocol: Optional[str] = None  # TLSv1.2, etc
    socket_timeout: Optional[int] = None
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        if self.cookies is None:
            self.cookies = {}


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter AI analysis."""
    enabled: bool = True
    model: str = "anthropic/claude-3-haiku"
    max_tokens: int = 4000
    temperature: float = 0.1
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop: Optional[List[str]] = None
    stream: bool = False
    timeout: int = 120
    retry_attempts: int = 3
    retry_delay: float = 1.0
    custom_headers: Optional[Dict[str, str]] = None
    system_prompt: Optional[str] = None
    reasoning_enabled: bool = False
    reasoning_effort: str = "medium"  # low, medium, high
    include_reasoning: bool = False
    
    # Enhanced options from web search
    http_referer: Optional[str] = None  # Site URL for rankings
    x_title: Optional[str] = None  # Site title for rankings
    response_format: Optional[str] = None  # json_object, json_schema
    seed: Optional[int] = None  # Deterministic outputs
    tools: Optional[List[Dict[str, Any]]] = None  # Function calling
    tool_choice: Optional[str] = None  # none, auto, or specific tool
    logit_bias: Optional[Dict[str, float]] = None  # Token bias
    top_k: Optional[int] = None  # Top-k sampling
    repetition_penalty: Optional[float] = None  # Repetition control
    
    def __post_init__(self):
        if self.stop is None:
            self.stop = []
        if self.custom_headers is None:
            self.custom_headers = {}
        if self.tools is None:
            self.tools = []
        if self.logit_bias is None:
            self.logit_bias = {}
        if self.system_prompt is None:
            self.system_prompt = """You are an expert code analyst. Analyze the provided code for:
1. Security vulnerabilities and concerns
2. Code quality issues and improvements  
3. Performance bottlenecks
4. Best practices violations
5. Architecture and design patterns
6. Maintainability concerns

Provide structured analysis with specific recommendations."""


@dataclass
class AnalyzerConfiguration:
    """Complete analyzer configuration container."""
    bandit: Optional[BanditConfig] = None
    pylint: Optional[PylintConfig] = None
    eslint: Optional[ESLintConfig] = None
    apache_bench: Optional[ApacheBenchConfig] = None
    openrouter: Optional[OpenRouterConfig] = None
    
    def __post_init__(self):
        if self.bandit is None:
            self.bandit = BanditConfig()
        if self.pylint is None:
            self.pylint = PylintConfig()
        if self.eslint is None:
            self.eslint = ESLintConfig()
        if self.apache_bench is None:
            self.apache_bench = ApacheBenchConfig()
        if self.openrouter is None:
            self.openrouter = OpenRouterConfig()


class AnalyzerConfigService:
    """Service for managing analyzer configurations."""
    
    def __init__(self):
        self.default_config = AnalyzerConfiguration()
        self.presets = self._load_presets()
    
    def _load_presets(self) -> Dict[str, AnalyzerConfiguration]:
        """Load predefined configuration presets."""
        presets = {
            "default": AnalyzerConfiguration(),
            "strict": self._create_strict_preset(),
            "fast": self._create_fast_preset(),
            "comprehensive": self._create_comprehensive_preset(),
            "security_focused": self._create_security_focused_preset(),
            "performance_focused": self._create_performance_focused_preset()
        }
        return presets
    
    def _create_strict_preset(self) -> AnalyzerConfiguration:
        """Create strict analysis preset with enhanced rules."""
        config = AnalyzerConfiguration()
        
        # Bandit: High security standards
        config.bandit.severity_level = "low"
        config.bandit.confidence_level = "low"
        config.bandit.skips = []  # Don't skip any tests
        
        # Pylint: Strict code quality
        config.pylint.fail_under = 8.0
        config.pylint.disable = ["fixme"]  # Only disable fixme
        config.pylint.max_line_length = 80
        config.pylint.max_nested_blocks = 3
        
        # ESLint: Strict JavaScript rules  
        config.eslint.rules.update({
            "no-var": "error",
            "prefer-const": "error",
            "no-unused-vars": "error",
            "complexity": ["error", 10],
            "max-depth": ["error", 4],
            "max-lines": ["error", 500]
        })
        
        # OpenRouter: More thorough analysis
        config.openrouter.temperature = 0.0
        config.openrouter.max_tokens = 6000
        config.openrouter.reasoning_enabled = True
        config.openrouter.reasoning_effort = "high"
        
        return config
    
    def _create_fast_preset(self) -> AnalyzerConfiguration:
        """Create fast analysis preset for quick checks."""
        config = AnalyzerConfiguration()
        
        # Bandit: Basic security checks
        config.bandit.severity_level = "medium"
        config.bandit.confidence_level = "medium"
        config.bandit.skips = ["B101", "B601", "B602"]
        
        # Pylint: Errors only
        config.pylint.errors_only = True
        config.pylint.reports = False
        config.pylint.score = False
        
        # ESLint: Essential rules only
        config.eslint.extends = ["eslint:recommended"]
        config.eslint.rules = {
            "no-eval": "error",
            "no-debugger": "error",
            "no-alert": "warn"
        }
        
        # Apache Bench: Quick performance check
        config.apache_bench.requests = 50
        config.apache_bench.concurrency = 5
        config.apache_bench.timeout = 15
        
        # OpenRouter: Faster analysis
        config.openrouter.max_tokens = 2000
        config.openrouter.temperature = 0.2
        config.openrouter.model = "anthropic/claude-3-haiku"
        
        return config
    
    def _create_comprehensive_preset(self) -> AnalyzerConfiguration:
        """Create comprehensive analysis preset."""
        config = AnalyzerConfiguration()
        
        # Bandit: All security tests
        config.bandit.skips = []
        config.bandit.aggregate = "vuln"
        config.bandit.context_lines = 5
        
        # Pylint: Full analysis with plugins
        config.pylint.load_plugins = [
            "pylint.extensions.check_elif",
            "pylint.extensions.bad_builtin", 
            "pylint.extensions.docparams",
            "pylint.extensions.for_any_all",
            "pylint.extensions.set_membership",
            "pylint.extensions.code_style",
            "pylint.extensions.overlapping_exceptions",
            "pylint.extensions.typing",
            "pylint.extensions.mccabe"
        ]
        config.pylint.reports = True
        
        # ESLint: Enhanced rules with plugins
        config.eslint.plugins = ["security", "import"]
        config.eslint.rules.update({
            "security/detect-object-injection": "warn",
            "security/detect-non-literal-regexp": "warn",
            "security/detect-unsafe-regex": "error",
            "import/no-unresolved": "error",
            "import/named": "error"
        })
        
        # Apache Bench: Thorough performance testing
        config.apache_bench.requests = 500
        config.apache_bench.concurrency = 20
        config.apache_bench.csv_output = True
        config.apache_bench.gnuplot_output = True
        
        # OpenRouter: Detailed analysis
        config.openrouter.max_tokens = 8000
        config.openrouter.reasoning_enabled = True
        config.openrouter.reasoning_effort = "high"
        config.openrouter.include_reasoning = True
        config.openrouter.model = "anthropic/claude-3-sonnet"
        
        return config
    
    def _create_security_focused_preset(self) -> AnalyzerConfiguration:
        """Create security-focused analysis preset."""
        config = AnalyzerConfiguration()
        
        # Bandit: Maximum security coverage
        config.bandit.severity_level = "low"
        config.bandit.confidence_level = "low"
        config.bandit.skips = []
        config.bandit.recursive = True
        
        # Pylint: Security-related checks
        config.pylint.enable = [
            "use-symbolic-message-instead",
            "useless-suppression"
        ]
        config.pylint.disable = [
            "missing-docstring", "too-few-public-methods"
        ]
        
        # ESLint: Security-focused rules
        config.eslint.plugins = ["security"]
        config.eslint.extends = ["plugin:security/recommended"]
        config.eslint.rules.update({
            "security/detect-buffer-noassert": "error",
            "security/detect-child-process": "error",
            "security/detect-disable-mustache-escape": "error",
            "security/detect-eval-with-expression": "error",
            "security/detect-new-buffer": "error",
            "security/detect-no-csrf-before-method-override": "error"
        })
        
        # Apache Bench: Security-aware testing
        config.apache_bench.requests = 100
        config.apache_bench.concurrency = 10
        config.apache_bench.headers = {
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Security-Test-Agent/1.0"
        }
        
        # OpenRouter: Security-focused prompts
        config.openrouter.system_prompt = """You are a cybersecurity expert. Focus your analysis on:
1. Security vulnerabilities (SQL injection, XSS, CSRF, etc.)
2. Authentication and authorization flaws
3. Input validation issues
4. Cryptographic weaknesses
5. Information disclosure risks
6. Business logic vulnerabilities
7. Infrastructure security concerns

Provide detailed security recommendations with severity ratings."""
        config.openrouter.max_tokens = 6000
        config.openrouter.temperature = 0.0
        
        return config
    
    def _create_performance_focused_preset(self) -> AnalyzerConfiguration:
        """Create performance-focused analysis preset."""
        config = AnalyzerConfiguration()
        
        # Bandit: Performance-related security checks
        config.bandit.tests = ["B102", "B103", "B104"]  # Performance-affecting tests
        
        # Pylint: Performance-related checks
        config.pylint.enable = [
            "unnecessary-comprehension",
            "consider-using-enumerate",
            "consider-using-dict-comprehension"
        ]
        
        # ESLint: Performance rules
        config.eslint.rules.update({
            "no-loop-func": "error",
            "no-inner-declarations": "error",
            "prefer-const": "error",
            "no-var": "error"
        })
        
        # Apache Bench: Stress testing
        config.apache_bench.requests = 1000
        config.apache_bench.concurrency = 50
        config.apache_bench.timelimit = 300
        config.apache_bench.keep_alive = True
        config.apache_bench.csv_output = True
        
        # OpenRouter: Performance analysis
        config.openrouter.system_prompt = """You are a performance optimization expert. Focus on:
1. Algorithmic complexity and efficiency
2. Memory usage and leaks
3. Database query optimization
4. Caching strategies
5. Network latency issues
6. Resource utilization
7. Scalability bottlenecks

Provide actionable performance improvement recommendations."""
        config.openrouter.max_tokens = 5000
        
        return config
    
    def get_preset(self, preset_name: str) -> AnalyzerConfiguration:
        """Get a configuration preset by name."""
        return self.presets.get(preset_name, self.default_config)
    
    def get_available_presets(self) -> List[str]:
        """Get list of available preset names."""
        return list(self.presets.keys())
    
    def create_custom_config(self, **kwargs) -> AnalyzerConfiguration:
        """Create a custom configuration from keyword arguments."""
        config = AnalyzerConfiguration()
        
        # Update configurations based on provided parameters
        for key, value in kwargs.items():
            if key.startswith('bandit_'):
                setattr(config.bandit, key[7:], value)
            elif key.startswith('pylint_'):
                setattr(config.pylint, key[7:], value)
            elif key.startswith('eslint_'):
                setattr(config.eslint, key[7:], value)
            elif key.startswith('ab_'):
                setattr(config.apache_bench, key[3:], value)
            elif key.startswith('openrouter_'):
                setattr(config.openrouter, key[11:], value)
        
        return config
    
    def validate_config(self, config: AnalyzerConfiguration) -> Dict[str, List[str]]:
        """Validate configuration and return any errors."""
        errors = {
            'bandit': [],
            'pylint': [],
            'eslint': [],
            'apache_bench': [],
            'openrouter': []
        }
        
        # Validate Bandit config
        if config.bandit.severity_level not in ['low', 'medium', 'high']:
            errors['bandit'].append("Invalid severity level")
        if config.bandit.confidence_level not in ['low', 'medium', 'high']:
            errors['bandit'].append("Invalid confidence level")
        
        # Validate Pylint config
        if config.pylint.fail_under < 0 or config.pylint.fail_under > 10:
            errors['pylint'].append("fail_under must be between 0 and 10")
        if config.pylint.max_line_length < 10:
            errors['pylint'].append("max_line_length too small")
        
        # Validate ESLint config
        if config.eslint.format not in ['json', 'compact', 'stylish', 'unix', 'visualstudio']:
            errors['eslint'].append("Invalid output format")
        
        # Validate Apache Bench config
        if config.apache_bench.requests <= 0:
            errors['apache_bench'].append("requests must be positive")
        if config.apache_bench.concurrency <= 0:
            errors['apache_bench'].append("concurrency must be positive")
        if config.apache_bench.concurrency > config.apache_bench.requests:
            errors['apache_bench'].append("concurrency cannot exceed requests")
        
        # Validate OpenRouter config
        if config.openrouter.temperature < 0 or config.openrouter.temperature > 2:
            errors['openrouter'].append("temperature must be between 0 and 2")
        if config.openrouter.max_tokens <= 0:
            errors['openrouter'].append("max_tokens must be positive")
        
        return {k: v for k, v in errors.items() if v}
    
    def to_dict(self, config: AnalyzerConfiguration) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return asdict(config)
    
    def from_dict(self, data: Dict[str, Any]) -> AnalyzerConfiguration:
        """Create configuration from dictionary."""
        return AnalyzerConfiguration(
            bandit=BanditConfig(**data.get('bandit', {})),
            pylint=PylintConfig(**data.get('pylint', {})),
            eslint=ESLintConfig(**data.get('eslint', {})),
            apache_bench=ApacheBenchConfig(**data.get('apache_bench', {})),
            openrouter=OpenRouterConfig(**data.get('openrouter', {}))
        )
    
    def save_config(self, config: AnalyzerConfiguration, filepath: str) -> bool:
        """Save configuration to file."""
        try:
            config_dict = self.to_dict(config)
            
            if filepath.endswith('.json'):
                with open(filepath, 'w') as f:
                    json.dump(config_dict, f, indent=2)
            elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
                with open(filepath, 'w') as f:
                    yaml.dump(config_dict, f, default_flow_style=False)
            else:
                raise ValueError("Unsupported file format")
            
            return True
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
            return False
    
    def load_config(self, filepath: str) -> Optional[AnalyzerConfiguration]:
        """Load configuration from file."""
        try:
            if not Path(filepath).exists():
                return None
            
            if filepath.endswith('.json'):
                with open(filepath, 'r') as f:
                    data = json.load(f)
            elif filepath.endswith('.yaml') or filepath.endswith('.yml'):
                with open(filepath, 'r') as f:
                    data = yaml.safe_load(f)
            else:
                raise ValueError("Unsupported file format")
            
            return self.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return None
    
    def generate_bandit_rcfile(self, config: BanditConfig) -> str:
        """Generate .bandit configuration file content."""
        bandit_config = {
            'tests': config.tests if config.tests else [],
            'skips': config.skips if config.skips else [],
            'exclude_dirs': config.exclude_dirs if config.exclude_dirs else []
        }
        
        return yaml.dump(bandit_config, default_flow_style=False)
    
    def generate_pylint_rcfile(self, config: PylintConfig) -> str:
        """Generate .pylintrc configuration file content."""
        rcfile_content = f"""[MAIN]
jobs={config.jobs}
load-plugins={','.join(config.load_plugins) if config.load_plugins else ''}

[MESSAGES CONTROL]
disable={','.join(config.disable) if config.disable else ''}
enable={','.join(config.enable) if config.enable else ''}

[REPORTS]
output-format={config.output_format}
reports={'yes' if config.reports else 'no'}
score={'yes' if config.score else 'no'}

[FORMAT]
max-line-length={config.max_line_length}
max-module-lines={config.max_module_lines}

[DESIGN]
max-args=5
max-attributes=7
max-bool-expr=5
max-branches=12
max-locals=15
max-parents=7
max-public-methods=20
max-returns=6
max-statements=50
min-public-methods=2

[BASIC]
good-names={','.join(config.good_names) if config.good_names else ''}
bad-names={','.join(config.bad_names) if config.bad_names else ''}

[REFACTORING]
max-nested-blocks={config.max_nested_blocks}
"""
        return rcfile_content
    
    def generate_eslint_config(self, config: ESLintConfig) -> str:
        """Generate .eslintrc.json configuration file content."""
        eslint_config = {
            'extends': config.extends,
            'env': config.env,
            'globals': config.globals,
            'parser': config.parser,
            'parserOptions': config.parser_options,
            'plugins': config.plugins,
            'rules': config.rules,
            'settings': config.settings
        }
        
        return json.dumps(eslint_config, indent=2)


# Global instance
analyzer_config_service = AnalyzerConfigService()
