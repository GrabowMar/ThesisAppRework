"""
Analyzer Configuration Service
=============================

Service for managing and validating analyzer configurations.
Provides methods to get, set, and validate configuration options
for security, performance, and AI analysis tools.

Enhanced with database integration for models and applications,
and support for scanning apps from the misc folder structure.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import logging

from ..extensions import db
from ..models import ModelCapability, GeneratedApplication
from ..models.analysis import AnalysisConfig
from ..constants import Paths

logger = logging.getLogger(__name__)


@dataclass
class BanditConfig:
    """Configuration for Bandit security scanner with comprehensive command-line options."""
    enabled: bool = True
    # Core severity and confidence settings
    confidence_level: str = "HIGH"  # LOW, MEDIUM, HIGH
    severity_level: str = "LOW"     # LOW, MEDIUM, HIGH
    
    # Path and test filtering options
    exclude_paths: Optional[List[str]] = None
    skipped_tests: Optional[List[str]] = None  # -s B101,B601
    tests: Optional[List[str]] = None          # -t B201,B301 (include specific tests)
    
    # Configuration file options
    config_file: Optional[str] = None          # -c config.yaml
    baseline_file: Optional[str] = None        # -b baseline.json
    
    # Output and reporting options
    formats: Optional[List[str]] = None        # -f json,txt,csv,xml,html
    output_file: Optional[str] = None          # -o output.json
    verbose: bool = False                      # -v
    quiet: bool = False                        # -q
    
    # Analysis behavior options
    recursive: bool = True                     # -r
    aggregate: str = "file"                    # aggregate by file, vuln, or test
    context_lines: int = 3                     # -n 3 (context lines in output)
    number_lines: bool = True                  # -l (show line numbers)
    
    # Advanced filtering and processing
    ignore_nosec: bool = False                 # --ignore-nosec
    exclude_dirs: Optional[List[str]] = None   # --exclude-dirs
    ini_path: Optional[str] = None             # --ini path/to/setup.cfg
    
    # Performance and execution options
    timeout: int = 300
    max_lines: Optional[int] = None            # max lines to process per file
    
    def __post_init__(self):
        if self.exclude_paths is None:
            self.exclude_paths = [
                '*/tests/*', '*/test_*', '*/migrations/*', 
                '*/venv/*', '*/node_modules/*', '*/.venv/*',
                '*/build/*', '*/dist/*'
            ]
        if self.skipped_tests is None:
            self.skipped_tests = ['B101', 'B601']  # Skip assert and shell injection tests
        if self.formats is None:
            self.formats = ['json', 'txt']
        if self.tests is None:
            self.tests = []  # Empty means all tests (unless skipped)
        if self.exclude_dirs is None:
            self.exclude_dirs = ['.git', '__pycache__', '.pytest_cache']


@dataclass
class SafetyConfig:
    """Configuration for Safety dependency scanner."""
    enabled: bool = True
    database_path: Optional[str] = None
    ignore_ids: Optional[List[str]] = None
    output_format: str = "json"
    check_unpinned: bool = True
    timeout: int = 180
    
    def __post_init__(self):
        if self.ignore_ids is None:
            self.ignore_ids = []


@dataclass
class PylintConfig:
    """Configuration for Pylint code quality scanner with complete .pylintrc support."""
    enabled: bool = True
    
    # Configuration file options
    rcfile: Optional[str] = None               # Path to .pylintrc or setup.cfg
    
    # [MAIN] section options
    load_plugins: Optional[List[str]] = None   # Plugins to load
    jobs: int = 1                              # Number of processes to use (0 = auto)
    suggestion_mode: bool = True               # Suggestion mode for missing member checks
    unsafe_load: bool = False                  # Allow loading of arbitrary C extensions
    extension_pkg_allow_list: Optional[List[str]] = None  # Packages to allow C extensions
    py_version: str = "3.8"                    # Python version for compatibility checks
    
    # Analysis behavior options
    disable: Optional[List[str]] = None        # Messages to disable
    enable: Optional[List[str]] = None         # Messages to enable
    confidence: Optional[List[str]] = None     # Confidence levels: CONTROL_FLOW, INFERENCE, etc.
    
    # Output and reporting options
    output_format: str = "json"                # Output format: text, parseable, colorized, json
    reports: bool = False                      # Include reports section
    score: bool = True                         # Display score
    msg_template: Optional[str] = None         # Template for displaying messages
    
    # Code analysis thresholds
    fail_under: float = 10.0                   # Minimum code rating to pass
    evaluation: str = "max(0, 0 if fatal else 10.0 - ((float(5 * error + warning + refactor + convention) / statement) * 10))"
    
    # Code format and style options
    max_line_length: int = 100                 # Maximum line length
    max_module_lines: int = 1000               # Maximum lines in a module
    indent_string: str = "    "                # String used for indenting
    indent_after_paren: int = 4                # Indentation after parentheses
    expected_line_ending_format: Optional[str] = None  # LF, CRLF, or mixed
    
    # Complexity and design options
    max_args: int = 5                          # Maximum number of arguments
    max_locals: int = 15                       # Maximum number of local variables
    max_returns: int = 6                       # Maximum number of return statements
    max_branches: int = 12                     # Maximum number of branches
    max_statements: int = 50                   # Maximum number of statements
    max_parents: int = 7                       # Maximum number of parents for a class
    max_attributes: int = 7                    # Maximum number of attributes for a class
    min_public_methods: int = 2                # Minimum number of public methods
    max_public_methods: int = 20               # Maximum number of public methods
    max_bool_expr: int = 5                     # Maximum number of boolean expressions
    max_nested_blocks: int = 5                 # Maximum nested block depth
    
    # Import and dependency options
    deprecated_modules: Optional[List[str]] = None      # Deprecated modules to flag
    preferred_modules: Optional[Dict[str, str]] = None  # Module replacements
    import_graph: Optional[str] = None                  # Import graph output file
    int_import_graph: Optional[str] = None              # Internal import graph file
    ext_import_graph: Optional[str] = None              # External import graph file
    
    # Naming convention options
    good_names: Optional[List[str]] = None              # Good variable names
    bad_names: Optional[List[str]] = None               # Bad variable names
    name_group: Optional[Dict[str, str]] = None         # Name groups
    include_naming_hint: bool = True                    # Include naming hints in messages
    
    # Performance and execution
    timeout: int = 300
    ignore: Optional[List[str]] = None                  # Files/directories to ignore
    ignore_patterns: Optional[List[str]] = None         # Ignore patterns (regex)
    ignore_paths: Optional[List[str]] = None            # Paths to ignore
    persistent: bool = True                             # Pickle collected data for later comparisons
    
    def __post_init__(self):
        if self.disable is None:
            self.disable = [
                'C0103',  # invalid-name
                'R0903',  # too-few-public-methods
                'W0613',  # unused-argument
                'R0801',  # duplicate-code
                'C0114',  # missing-module-docstring
                'C0115',  # missing-class-docstring
                'C0116'   # missing-function-docstring
            ]
        if self.enable is None:
            self.enable = ['W0622']  # redefined-builtin
        if self.load_plugins is None:
            self.load_plugins = []
        if self.confidence is None:
            self.confidence = ['HIGH', 'CONTROL_FLOW', 'INFERENCE', 'INFERENCE_FAILURE', 'UNDEFINED']
        if self.extension_pkg_allow_list is None:
            self.extension_pkg_allow_list = []
        if self.deprecated_modules is None:
            self.deprecated_modules = ['regsub', 'TERMIOS', 'Bastion', 'rexec']
        if self.preferred_modules is None:
            self.preferred_modules = {}
        if self.good_names is None:
            self.good_names = ['i', 'j', 'k', 'ex', 'Run', '_', 'id', 'pk']
        if self.bad_names is None:
            self.bad_names = ['foo', 'bar', 'baz', 'toto', 'tutu', 'tata']
        if self.name_group is None:
            self.name_group = {}
        if self.ignore is None:
            self.ignore = ['CVS', '.git', '__pycache__', '.pytest_cache']
        if self.ignore_patterns is None:
            self.ignore_patterns = []
        if self.ignore_paths is None:
            self.ignore_paths = []


@dataclass
class ESLintConfig:
    """Configuration for ESLint JavaScript security scanner with modern flat config support."""
    enabled: bool = True
    
    # Configuration file options (flat config system)
    config_file: Optional[str] = None          # eslint.config.js or .eslintrc.json
    use_flat_config: bool = True               # Use modern flat config system
    
    # Rules and plugins configuration
    rules: Optional[Dict[str, Any]] = None     # Rule configurations with severity levels
    plugins: Optional[List[str]] = None        # ESLint plugins to load
    extends: Optional[List[str]] = None        # Configuration sets to extend
    
    # Environment and parser settings
    environments: Optional[Dict[str, bool]] = None  # Environment globals (node, browser, es6)
    parser: Optional[str] = None               # Custom parser (e.g., @babel/eslint-parser)
    parser_options: Optional[Dict[str, Any]] = None  # Parser configuration options
    
    # Output and reporting options
    output_format: str = "json"                # Output format: json, stylish, compact, etc.
    output_file: Optional[str] = None          # Output file path
    max_warnings: int = 50                     # Maximum warnings before error exit
    quiet: bool = False                        # Report errors only, ignore warnings
    
    # File processing options
    ignore_path: Optional[str] = None          # Path to .eslintignore file
    ignore_pattern: Optional[List[str]] = None # Patterns to ignore
    ext: Optional[List[str]] = None            # File extensions to process
    
    # Advanced options
    cache: bool = True                         # Enable caching for faster subsequent runs
    cache_location: Optional[str] = None       # Custom cache file location
    fix: bool = False                          # Automatically fix problems
    fix_dry_run: bool = False                  # Show fixes without applying them
    fix_type: Optional[List[str]] = None       # Types of fixes to apply (problem, suggestion, layout)
    
    # Performance and execution
    timeout: int = 240
    max_file_size: Optional[int] = None        # Skip files larger than this size (bytes)
    
    def __post_init__(self):
        if self.rules is None:
            self.rules = {
                # Security rules
                'security/detect-object-injection': 'error',
                'security/detect-non-literal-fs-filename': 'error',
                'security/detect-unsafe-regex': 'error',
                'security/detect-buffer-noassert': 'error',
                'security/detect-eval-with-expression': 'error',
                'security/detect-no-csrf-before-method-override': 'error',
                'security/detect-pseudoRandomBytes': 'error',
                'security/detect-child-process': 'warn',
                'security/detect-disable-mustache-escape': 'error',
                'security/detect-new-buffer': 'error',
                
                # Code quality rules
                'no-eval': 'error',
                'no-implied-eval': 'error',
                'no-new-func': 'error',
                'no-script-url': 'error',
                'prefer-const': 'warn',
                'no-var': 'warn',
                'no-unused-vars': 'warn',
                'no-console': 'warn',
                'complexity': ['warn', 15]
            }
        if self.plugins is None:
            self.plugins = ['security']
        if self.extends is None:
            self.extends = ['eslint:recommended']
        if self.environments is None:
            self.environments = {
                'browser': True,
                'node': True,
                'es6': True,
                'es2021': True
            }
        if self.parser_options is None:
            self.parser_options = {
                'ecmaVersion': 2021,
                'sourceType': 'module',
                'ecmaFeatures': {
                    'jsx': True,
                    'globalReturn': False,
                    'impliedStrict': True
                }
            }
        if self.ignore_pattern is None:
            self.ignore_pattern = ['node_modules/**', 'dist/**', 'build/**', '*.min.js']
        if self.ext is None:
            self.ext = ['.js', '.jsx', '.ts', '.tsx', '.vue']
        if self.fix_type is None:
            self.fix_type = ['problem', 'suggestion']


@dataclass
class ZAPConfig:
    """Configuration for OWASP ZAP web application scanner with comprehensive settings."""
    enabled: bool = True
    
    # Core ZAP configuration
    api_key: Optional[str] = None              # API key for remote access
    daemon_mode: bool = True                   # Run in daemon/headless mode
    host: str = "localhost"                    # ZAP host address
    port: int = 8080                          # ZAP proxy port
    config_file: Optional[str] = None          # Path to ZAP configuration file
    
    # Memory and performance settings
    memory_allocation: str = "1G"              # Java heap size (-Xmx)
    thread_count: Optional[int] = None         # Number of threads for active scanning
    
    # API and remote access configuration
    api_addresses: Optional[List[str]] = None  # Allowed API addresses (default: localhost)
    api_regex: bool = True                     # Enable regex for API addresses
    disable_api_key: bool = False              # Disable API key requirement
    
    # Scan configuration
    scan_types: Optional[Dict[str, Any]] = None
    scan_policies: Optional[Dict[str, Any]] = None
    
    # Authentication and session management
    authentication: Optional[Dict[str, Any]] = None
    session_management: Optional[Dict[str, Any]] = None
    
    # Context and scope configuration
    context: Optional[Dict[str, Any]] = None
    include_patterns: Optional[List[str]] = None    # URLs to include in scope
    exclude_patterns: Optional[List[str]] = None    # URLs to exclude from scope
    
    # Reporting and output configuration
    reporting: Optional[Dict[str, Any]] = None
    alert_filters: Optional[Dict[str, Any]] = None
    
    # Proxy and networking settings
    proxy_chain: Optional[Dict[str, str]] = None    # Upstream proxy configuration
    certificate_settings: Optional[Dict[str, Any]] = None
    
    # WebSocket and advanced protocol support
    websocket_enabled: bool = True             # Enable WebSocket scanning
    http2_enabled: bool = True                 # Enable HTTP/2 support
    
    # Script and extension configuration
    scripts: Optional[Dict[str, Any]] = None   # Custom scripts configuration
    extensions: Optional[List[str]] = None     # Extensions to load
    
    # Performance and timeout settings
    timeout: int = 3600                        # Overall scan timeout
    connection_timeout: int = 20               # Connection timeout for requests
    read_timeout: int = 200                    # Read timeout for requests
    
    def __post_init__(self):
        if self.scan_types is None:
            self.scan_types = {
                'spider': {
                    'enabled': True,
                    'max_depth': 5,
                    'max_duration': 600,
                    'max_children': 0,
                    'user_agent': 'ZAP/2.14.0',
                    'accept_cookies': True,
                    'handle_odata_parameters': False,
                    'parse_comments': True,
                    'parse_robots_txt': True,
                    'parse_sitemap_xml': True,
                    'parse_svn_entries': False,
                    'parse_git': False,
                    'post_form': False,
                    'process_form': True,
                    'request_wait_time': 200
                },
                'ajax_spider': {
                    'enabled': True,
                    'max_duration': 600,
                    'max_crawl_depth': 10,
                    'number_of_browsers': 1,
                    'event_wait': 1000,
                    'reload_wait': 1000,
                    'click_default_elems': True,
                    'random_inputs': True
                },
                'active_scan': {
                    'enabled': True,
                    'policy': 'Default Policy',
                    'max_duration': 1800,
                    'max_rule_duration': 300,
                    'max_scan_duration_per_host': 0,
                    'delay_in_ms': 0,
                    'threads_per_host': 2,
                    'host_per_scan': 2,
                    'max_results_to_list': 10,
                    'inject_plugin_id_in_header': False,
                    'handle_anti_csrf_tokens': False,
                    'prompt_in_attack_mode': False
                },
                'passive_scan': {
                    'enabled': True,
                    'max_alerts_per_rule': 10,
                    'scan_only_in_scope': True,
                    'auto_tag_scanners': True
                }
            }
        
        if self.scan_policies is None:
            self.scan_policies = {
                'default': {
                    'name': 'Default Policy',
                    'threshold': 'Default',
                    'strength': 'Default',
                    'attack_strength': 'MEDIUM'
                },
                'light': {
                    'name': 'Light Policy',
                    'threshold': 'HIGH',
                    'strength': 'LOW',
                    'attack_strength': 'LOW'
                },
                'full': {
                    'name': 'Full Policy',
                    'threshold': 'LOW',
                    'strength': 'INSANE',
                    'attack_strength': 'INSANE'
                }
            }
        
        if self.authentication is None:
            self.authentication = {
                'method': 'form',          # form, script, json, manual
                'login_url': None,
                'login_request_data': None,
                'username_field': 'username',
                'password_field': 'password',
                'username': None,
                'password': None,
                'extra_post_data': None,
                'logged_in_regex': None,
                'logged_out_regex': None,
                'auto_detect': True,
                'script_name': None,       # For script-based authentication
                'script_parameters': {}
            }
        
        if self.session_management is None:
            self.session_management = {
                'method': 'cookie',        # cookie, http_auth, script
                'script_name': None,
                'script_parameters': {}
            }
        
        if self.context is None:
            self.context = {
                'name': 'Default Context',
                'description': 'Default context for ZAP scanning',
                'in_scope': True,
                'include_regexs': ['.*'],
                'exclude_regexs': [
                    '.*logout.*', '.*signout.*', '.*sign-out.*',
                    '.*admin.*', '.*delete.*', '.*remove.*',
                    '.*\\.(css|js|gif|jpe?g|png|ico|woff|woff2|ttf|eot|svg)$'
                ],
                'include_technologies': [],
                'exclude_technologies': [],
                'data_driven_nodes': []
            }
        
        if self.reporting is None:
            self.reporting = {
                'formats': ['json', 'html', 'xml', 'md'],
                'template': 'traditional-html',
                'theme': 'original',
                'include_passed': False,
                'include_response_body': False,
                'risk_threshold': 'Low',      # Info, Low, Medium, High
                'confidence_threshold': 'Medium',  # False Positive, Low, Medium, High, Confirmed
                'sections': {
                    'passed_rules': False,
                    'instance_count': True,
                    'alert_details': True,
                    'chart_details': True,
                    'statistics': True
                }
            }
        
        if self.alert_filters is None:
            self.alert_filters = {
                'enabled': True,
                'global_alert_filter': True,
                'context_alert_filter': False,
                'filters': []  # List of alert filter rules
            }
        
        if self.api_addresses is None:
            self.api_addresses = ['127.0.0.1', 'localhost']
        
        if self.include_patterns is None:
            self.include_patterns = ['.*']
        
        if self.exclude_patterns is None:
            self.exclude_patterns = [
                '.*logout.*', '.*signout.*', '.*admin.*',
                '.*\\.(css|js|gif|jpe?g|png|ico|woff|woff2|ttf|eot|svg|pdf|doc|docx|xls|xlsx)$'
            ]
        
        if self.scripts is None:
            self.scripts = {
                'authentication': [],
                'httpsender': [],
                'active_rules': [],
                'passive_rules': [],
                'proxy': [],
                'standalone': [],
                'targeted': []
            }
        
        if self.extensions is None:
            self.extensions = ['websockets', 'openapi', 'soap', 'graphql']
        
        if self.proxy_chain is None:
            self.proxy_chain = {}
        
        if self.certificate_settings is None:
            self.certificate_settings = {
                'use_client_certificate': False,
                'client_certificate_location': None,
                'use_global_http_state': True
            }


@dataclass
class ApacheBenchConfig:
    """Configuration for Apache Bench (ab) performance testing with comprehensive parameters."""
    enabled: bool = True
    
    # Core testing parameters
    requests: int = 100                        # -n Total number of requests to perform
    concurrency: int = 10                      # -c Number of concurrent requests
    timelimit: Optional[int] = None            # -t Seconds to max. to spend on benchmarking
    
    # Connection and timeout options
    timeout: int = 30                          # -s Timeout for each request (seconds)
    keep_alive: bool = False                   # -k Enable HTTP KeepAlive feature
    
    # HTTP method and data options
    method: str = "GET"                        # HTTP method (GET, POST, PUT, etc.)
    post_file: Optional[str] = None            # -p File with data to POST
    put_file: Optional[str] = None             # -u File with data to PUT
    content_type: str = "text/plain"           # -T Content-type header for POSTing
    
    # Headers and authentication
    headers: Optional[Dict[str, str]] = None   # -H Additional headers to send
    auth: Optional[Dict[str, str]] = None      # -A Basic authentication (username:password)
    proxy_auth: Optional[Dict[str, str]] = None # -P Proxy authentication (username:password)
    cookie: Optional[str] = None               # -C Cookie to send with requests
    
    # SSL/TLS options
    cipher_suite: Optional[str] = None         # -Z Cipher suite for SSL connections
    ssl_protocol: Optional[str] = None         # SSL/TLS protocol version (SSLv2, SSLv3, TLSv1, etc.)
    
    # Output and reporting options
    output_format: str = "text"                # Output format: text, json, csv
    verbose_level: int = 1                     # -v Verbosity level (1-4)
    quiet: bool = False                        # -q Do not show progress meter
    csv_output: bool = False                   # -e Generate CSV output
    gnuplot_output: bool = False               # -g Generate gnuplot output
    output_file: Optional[str] = None          # File to write results to
    
    # Advanced options
    window_size: Optional[int] = None          # -b Size of TCP send/receive buffer
    proxy: Optional[str] = None                # -X Proxy server and port
    bind_address: Optional[str] = None         # -B Address to bind to when making connections
    
    # Performance tuning
    ramp_up: Optional[int] = None              # Gradually increase load over time (seconds)
    think_time: Optional[int] = None           # Think time between requests (milliseconds)
    
    def __post_init__(self):
        if self.headers is None:
            self.headers = {
                'User-Agent': 'ApacheBench/2.3',
                'Accept': '*/*'
            }
        if self.auth is None:
            self.auth = {}
        if self.proxy_auth is None:
            self.proxy_auth = {}


@dataclass
@dataclass
class SecurityAnalyzerConfig:
    """Complete security analyzer configuration."""
    bandit: Optional[BanditConfig] = None
    safety: Optional[SafetyConfig] = None
    pylint: Optional[PylintConfig] = None
    eslint: Optional[ESLintConfig] = None
    zap: Optional[ZAPConfig] = None
    apache_bench: Optional[ApacheBenchConfig] = None
    
    def __post_init__(self):
        if self.bandit is None:
            self.bandit = BanditConfig()
        if self.safety is None:
            self.safety = SafetyConfig()
        if self.pylint is None:
            self.pylint = PylintConfig()
        if self.eslint is None:
            self.eslint = ESLintConfig()
        if self.zap is None:
            self.zap = ZAPConfig()
        if self.apache_bench is None:
            self.apache_bench = ApacheBenchConfig()


class AnalyzerConfigService:
    """Service for managing analyzer configurations with database integration."""
    
    def __init__(self):
        self.default_config = SecurityAnalyzerConfig()
        self.logger = logging.getLogger(__name__)
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get all available models from database and misc folder."""
        models = []
        
        # Get models from database
        db_models = ModelCapability.query.order_by(ModelCapability.provider, ModelCapability.model_name).all()
        for model in db_models:
            models.append({
                'slug': model.canonical_slug,
                'name': model.model_name,
                'provider': model.provider,
                'source': 'database'
            })
        
        # Scan misc folder for additional models
        models_dir = Paths.MODELS_DIR
        if models_dir.exists():
            for model_dir in models_dir.iterdir():
                if model_dir.is_dir() and model_dir.name not in [m['slug'] for m in models]:
                    # Extract provider from slug
                    provider = model_dir.name.split('_')[0] if '_' in model_dir.name else 'unknown'
                    models.append({
                        'slug': model_dir.name,
                        'name': model_dir.name.replace('_', ' ').title(),
                        'provider': provider,
                        'source': 'misc_folder'
                    })
        
        return models
    
    def get_available_apps(self, model_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all available apps from database and misc folder."""
        apps = []
        
        if model_slug:
            # Get apps for specific model from database
            db_apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
            for app in db_apps:
                apps.append({
                    'model_slug': app.model_slug,
                    'app_number': app.app_number,
                    'app_type': app.app_type,
                    'has_backend': app.has_backend,
                    'has_frontend': app.has_frontend,
                    'backend_framework': app.backend_framework,
                    'frontend_framework': app.frontend_framework,
                    'source': 'database'
                })
            
            # Check misc folder for additional apps
            misc_model_dir = Paths.MODELS_DIR / model_slug
            if misc_model_dir.exists():
                for app_dir in misc_model_dir.iterdir():
                    if app_dir.is_dir() and app_dir.name.startswith('app'):
                        try:
                            app_number = int(app_dir.name.replace('app', ''))
                            # Check if this app is already in database
                            if not any(app['app_number'] == app_number for app in apps):
                                has_backend = (app_dir / 'backend').exists()
                                has_frontend = (app_dir / 'frontend').exists()
                                
                                apps.append({
                                    'model_slug': model_slug,
                                    'app_number': app_number,
                                    'app_type': 'fullstack' if has_backend and has_frontend else 'backend' if has_backend else 'frontend',
                                    'has_backend': has_backend,
                                    'has_frontend': has_frontend,
                                    'backend_framework': self._detect_backend_framework(app_dir / 'backend') if has_backend else None,
                                    'frontend_framework': self._detect_frontend_framework(app_dir / 'frontend') if has_frontend else None,
                                    'source': 'misc_folder',
                                    'path': str(app_dir)
                                })
                        except ValueError:
                            continue
        else:
            # Get all apps from database
            db_apps = GeneratedApplication.query.all()
            for app in db_apps:
                apps.append({
                    'model_slug': app.model_slug,
                    'app_number': app.app_number,
                    'app_type': app.app_type,
                    'has_backend': app.has_backend,
                    'has_frontend': app.has_frontend,
                    'backend_framework': app.backend_framework,
                    'frontend_framework': app.frontend_framework,
                    'source': 'database'
                })
            
            # Scan all models in misc folder
            models_dir = Paths.MODELS_DIR
            if models_dir.exists():
                for model_dir in models_dir.iterdir():
                    if not model_dir.is_dir():
                        continue
                        
                    model_slug = model_dir.name
                    for app_dir in model_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            try:
                                app_number = int(app_dir.name.replace('app', ''))
                                # Check if this app is already in database
                                if not any(app['model_slug'] == model_slug and app['app_number'] == app_number for app in apps):
                                    has_backend = (app_dir / 'backend').exists()
                                    has_frontend = (app_dir / 'frontend').exists()
                                    
                                    apps.append({
                                        'model_slug': model_slug,
                                        'app_number': app_number,
                                        'app_type': 'fullstack' if has_backend and has_frontend else 'backend' if has_backend else 'frontend',
                                        'has_backend': has_backend,
                                        'has_frontend': has_frontend,
                                        'backend_framework': self._detect_backend_framework(app_dir / 'backend') if has_backend else None,
                                        'frontend_framework': self._detect_frontend_framework(app_dir / 'frontend') if has_frontend else None,
                                        'source': 'misc_folder',
                                        'path': str(app_dir)
                                    })
                            except ValueError:
                                continue
        
        return sorted(apps, key=lambda x: (x['model_slug'], x['app_number']))
    
    def get_app_directory_path(self, model_slug: str, app_number: int) -> Optional[str]:
        """Get the directory path for an application."""
        # First check database
        app = GeneratedApplication.query.filter_by(
            model_slug=model_slug, 
            app_number=app_number
        ).first()
        
        if app:
            metadata = app.get_metadata()
            if 'directory_path' in metadata:
                return metadata['directory_path']
        
        # Check misc folder
        misc_app_path = Paths.MODELS_DIR / model_slug / f"app{app_number}"
        if misc_app_path.exists():
            return str(misc_app_path)
        
        return None
    
    def _detect_backend_framework(self, backend_dir: Path) -> Optional[str]:
        """Detect backend framework from directory structure."""
        if not backend_dir.exists():
            return None
            
        if (backend_dir / 'requirements.txt').exists():
            # Check for Flask/Django indicators
            try:
                with open(backend_dir / 'requirements.txt', 'r') as f:
                    content = f.read().lower()
                    if 'flask' in content:
                        return 'flask'
                    elif 'django' in content:
                        return 'django'
                    elif 'fastapi' in content:
                        return 'fastapi'
                    else:
                        return 'python'
            except Exception:
                return 'python'
        elif (backend_dir / 'package.json').exists():
            return 'node'
        elif (backend_dir / 'go.mod').exists():
            return 'go'
        elif (backend_dir / 'Cargo.toml').exists():
            return 'rust'
        
        return None
    
    def _detect_frontend_framework(self, frontend_dir: Path) -> Optional[str]:
        """Detect frontend framework from directory structure."""
        if not frontend_dir.exists():
            return None
            
        if (frontend_dir / 'package.json').exists():
            try:
                with open(frontend_dir / 'package.json', 'r') as f:
                    content = json.load(f)
                    dependencies = {**content.get('dependencies', {}), **content.get('devDependencies', {})}
                    
                    if 'react' in dependencies:
                        return 'react'
                    elif 'vue' in dependencies:
                        return 'vue'
                    elif 'angular' in dependencies or '@angular/core' in dependencies:
                        return 'angular'
                    elif 'svelte' in dependencies:
                        return 'svelte'
                    else:
                        return 'javascript'
            except Exception:
                return 'javascript'
        elif (frontend_dir / 'index.html').exists():
            return 'vanilla'
        
        return None
    
    def get_model_apps_summary(self, model_slug: str) -> Dict[str, Any]:
        """Get summary of apps for a specific model."""
        apps = self.get_available_apps(model_slug)
        
        summary = {
            'model_slug': model_slug,
            'total_apps': len(apps),
            'app_types': {},
            'frameworks': {'backend': {}, 'frontend': {}},
            'sources': {'database': 0, 'misc_folder': 0},
            'apps': apps
        }
        
        for app in apps:
            # Count app types
            app_type = app['app_type']
            summary['app_types'][app_type] = summary['app_types'].get(app_type, 0) + 1
            
            # Count frameworks
            if app['backend_framework']:
                framework = app['backend_framework']
                summary['frameworks']['backend'][framework] = summary['frameworks']['backend'].get(framework, 0) + 1
            
            if app['frontend_framework']:
                framework = app['frontend_framework']
                summary['frameworks']['frontend'][framework] = summary['frameworks']['frontend'].get(framework, 0) + 1
            
            # Count sources
            source = app['source']
            summary['sources'][source] += 1
        
        return summary
    
    def validate_model_app_combination(self, model_slug: str, app_number: int) -> bool:
        """Validate that a model/app combination exists."""
        # Check database first
        db_app = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_number
        ).first()
        
        if db_app:
            return True
        
        # Check misc folder
        misc_path = Paths.MODELS_DIR / model_slug / f"app{app_number}"
        return misc_path.exists() and misc_path.is_dir()
    
    def get_scannable_targets(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all scannable targets organized by model."""
        targets = {}
        apps = self.get_available_apps()
        
        for app in apps:
            model_slug = app['model_slug']
            if model_slug not in targets:
                targets[model_slug] = []
            
            # Add target information
            target = {
                'app_number': app['app_number'],
                'app_type': app['app_type'],
                'has_backend': app['has_backend'],
                'has_frontend': app['has_frontend'],
                'backend_framework': app['backend_framework'],
                'frontend_framework': app['frontend_framework'],
                'source': app['source']
            }
            
            # Add path if available
            path = self.get_app_directory_path(model_slug, app['app_number'])
            if path:
                target['path'] = path
            
            targets[model_slug].append(target)
        
        return targets
    
    def sync_database_from_misc_folder(self) -> Dict[str, int]:
        """Synchronize database with misc folder structure."""
        synced = {'models': 0, 'apps': 0}
        
        models_dir = Paths.MODELS_DIR
        if not models_dir.exists():
            self.logger.warning(f"Models directory not found: {models_dir}")
            return synced
        
        # Scan for models and apps
        for model_dir in models_dir.iterdir():
            if not model_dir.is_dir():
                continue
                
            model_slug = model_dir.name
            
            # Check if model exists in database
            existing_model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if not existing_model:
                # Create minimal model entry
                provider = model_slug.split('_')[0] if '_' in model_slug else 'unknown'
                model = ModelCapability()
                model.model_id = model_slug
                model.canonical_slug = model_slug
                model.provider = provider
                model.model_name = model_slug.replace('_', ' ').title()
                db.session.add(model)
                synced['models'] += 1
                self.logger.info(f"Added model to database: {model_slug}")
            
            # Scan for apps
            for app_dir in model_dir.iterdir():
                if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                    continue
                    
                try:
                    app_number = int(app_dir.name.replace('app', ''))
                except ValueError:
                    continue
                
                # Check if app exists in database
                existing_app = GeneratedApplication.query.filter_by(
                    model_slug=model_slug,
                    app_number=app_number
                ).first()
                
                if not existing_app:
                    # Create app entry
                    provider = model_slug.split('_')[0] if '_' in model_slug else 'unknown'
                    has_backend = (app_dir / 'backend').exists()
                    has_frontend = (app_dir / 'frontend').exists()
                    has_docker_compose = (app_dir / 'docker-compose.yml').exists()
                    
                    app = GeneratedApplication()
                    app.model_slug = model_slug
                    app.app_number = app_number
                    app.app_type = 'fullstack' if has_backend and has_frontend else 'backend' if has_backend else 'frontend'
                    app.provider = provider
                    app.has_backend = has_backend
                    app.has_frontend = has_frontend
                    app.has_docker_compose = has_docker_compose
                    app.backend_framework = self._detect_backend_framework(app_dir / 'backend') if has_backend else None
                    app.frontend_framework = self._detect_frontend_framework(app_dir / 'frontend') if has_frontend else None
                    app.container_status = 'stopped'
                    
                    # Store metadata with paths
                    metadata = {
                        'directory_path': str(app_dir),
                        'backend_path': str(app_dir / 'backend') if has_backend else None,
                        'frontend_path': str(app_dir / 'frontend') if has_frontend else None,
                        'docker_compose_path': str(app_dir / 'docker-compose.yml') if has_docker_compose else None,
                        'sync_source': 'misc_folder'
                    }
                    app.set_metadata(metadata)
                    
                    db.session.add(app)
                    synced['apps'] += 1
                    self.logger.info(f"Added app to database: {model_slug}/app{app_number}")
        
        try:
            db.session.commit()
            self.logger.info(f"Database sync completed: {synced['models']} models, {synced['apps']} apps")
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Failed to sync database: {e}")
            raise
        
        return synced
    
    def get_analyzer_targets_for_config(self, config: SecurityAnalyzerConfig) -> List[Dict[str, Any]]:
        """Get list of targets that can be analyzed with the given configuration."""
        targets = []
        apps = self.get_available_apps()
        
        for app in apps:
            target = {
                'model_slug': app['model_slug'],
                'app_number': app['app_number'],
                'app_type': app['app_type'],
                'analyzers': []
            }
            
            # Check which analyzers are applicable
            if app['has_backend']:
                if config.bandit and config.bandit.enabled:
                    target['analyzers'].append('bandit')
                if config.safety and config.safety.enabled:
                    target['analyzers'].append('safety')
                if config.pylint and config.pylint.enabled:
                    target['analyzers'].append('pylint')
            
            if app['has_frontend']:
                if config.eslint and config.eslint.enabled:
                    target['analyzers'].append('eslint')
            
            # ZAP can scan any web application
            if config.zap and config.zap.enabled and (app['has_frontend'] or app['has_backend']):
                target['analyzers'].append('zap')
            
            # Only include targets that have applicable analyzers
            if target['analyzers']:
                targets.append(target)
        
        return targets
    
    def generate_analysis_plan(self, model_slug: Optional[str] = None, 
                             app_numbers: Optional[List[int]] = None,
                             config: Optional[SecurityAnalyzerConfig] = None) -> Dict[str, Any]:
        """Generate a comprehensive analysis plan."""
        if not config:
            config = self.default_config
        
        # Get target apps
        if model_slug:
            if app_numbers:
                # Specific apps for a model
                apps = []
                for app_num in app_numbers:
                    if self.validate_model_app_combination(model_slug, app_num):
                        app_data = next(
                            (app for app in self.get_available_apps(model_slug) 
                             if app['app_number'] == app_num), 
                            None
                        )
                        if app_data:
                            apps.append(app_data)
            else:
                # All apps for a model
                apps = self.get_available_apps(model_slug)
        else:
            # All apps
            apps = self.get_available_apps()
        
        # Generate plan
        plan = {
            'target_count': len(apps),
            'estimated_duration': 0,
            'analysis_types': [],
            'targets': [],
            'configuration': asdict(config),
            'warnings': []
        }
        
        # Analyze each target
        for app in apps:
            target_plan = {
                'model_slug': app['model_slug'],
                'app_number': app['app_number'],
                'path': self.get_app_directory_path(app['model_slug'], app['app_number']),
                'analyses': []
            }
            
            # Plan specific analyses
            if app['has_backend']:
                if config.bandit and config.bandit.enabled:
                    target_plan['analyses'].append({
                        'type': 'bandit',
                        'estimated_duration': config.bandit.timeout,
                        'target': 'backend'
                    })
                    plan['estimated_duration'] += config.bandit.timeout
                
                if config.safety and config.safety.enabled:
                    target_plan['analyses'].append({
                        'type': 'safety',
                        'estimated_duration': config.safety.timeout,
                        'target': 'backend'
                    })
                    plan['estimated_duration'] += config.safety.timeout
                
                if config.pylint and config.pylint.enabled:
                    target_plan['analyses'].append({
                        'type': 'pylint',
                        'estimated_duration': config.pylint.timeout,
                        'target': 'backend'
                    })
                    plan['estimated_duration'] += config.pylint.timeout
            
            if app['has_frontend']:
                if config.eslint and config.eslint.enabled:
                    target_plan['analyses'].append({
                        'type': 'eslint',
                        'estimated_duration': config.eslint.timeout,
                        'target': 'frontend'
                    })
                    plan['estimated_duration'] += config.eslint.timeout
            
            if config.zap and config.zap.enabled and (app['has_frontend'] or app['has_backend']):
                target_plan['analyses'].append({
                    'type': 'zap',
                    'estimated_duration': config.zap.timeout,
                    'target': 'web_application'
                })
                plan['estimated_duration'] += config.zap.timeout
            
            # Add warnings for missing paths
            if not target_plan['path']:
                plan['warnings'].append(f"Path not found for {app['model_slug']}/app{app['app_number']}")
            
            if target_plan['analyses']:
                plan['targets'].append(target_plan)
        
        # Get unique analysis types
        all_analyses = []
        for target in plan['targets']:
            all_analyses.extend([analysis['type'] for analysis in target['analyses']])
        plan['analysis_types'] = list(set(all_analyses))
        
        return plan
    
    def get_security_config(self, config_id: Optional[int] = None) -> SecurityAnalyzerConfig:
        """Get security analyzer configuration."""
        if config_id:
            from app.extensions import get_session
            with get_session() as _s:
                config_record = _s.get(AnalysisConfig, config_id)
            if config_record and config_record.config_type == 'security':
                return self._deserialize_config(config_record.config_data, SecurityAnalyzerConfig)
        
        return self.default_config
    
    def save_security_config(self, config: SecurityAnalyzerConfig, name: str, 
                           description: str = "") -> AnalysisConfig:
        """Save security analyzer configuration to database."""
        config_data = self._serialize_config(config)
        
        config_record = AnalysisConfig(
            name=name,
            description=description,
            config_type='security',
            config_data=config_data
        )
        
        db.session.add(config_record)
        db.session.commit()
        
        return config_record
    
    def update_security_config(self, config_id: int, config: SecurityAnalyzerConfig, 
                             name: Optional[str] = None, description: Optional[str] = None) -> AnalysisConfig:
        """Update existing security analyzer configuration."""
        config_record = AnalysisConfig.query.get_or_404(config_id)
        
        if config_record.config_type != 'security':
            raise ValueError("Configuration is not a security configuration")
        
        config_record.config_data = self._serialize_config(config)
        
        if name:
            config_record.name = name
        if description is not None:
            config_record.description = description
        
        db.session.commit()
        return config_record
    
    def get_security_config_presets(self) -> List[Dict[str, Any]]:
        """Get predefined security configuration presets."""
        presets = [
            {
                'name': 'Quick Scan',
                'description': 'Fast scan with basic security checks',
                'config': SecurityAnalyzerConfig(
                    bandit=BanditConfig(
                        confidence_level="HIGH",
                        severity_level="MEDIUM",
                        timeout=120
                    ),
                    safety=SafetyConfig(timeout=60),
                    pylint=PylintConfig(enabled=False),
                    eslint=ESLintConfig(timeout=60),
                    zap=ZAPConfig(
                        scan_types={
                            'spider': {'enabled': True, 'max_duration': 300},
                            'active_scan': {'enabled': False},
                            'passive_scan': {'enabled': True}
                        },
                        timeout=600
                    )
                )
            },
            {
                'name': 'Comprehensive Scan',
                'description': 'Complete security analysis with all tools',
                'config': SecurityAnalyzerConfig()  # Uses defaults
            },
            {
                'name': 'Python Only',
                'description': 'Security analysis for Python applications only',
                'config': SecurityAnalyzerConfig(
                    bandit=BanditConfig(),
                    safety=SafetyConfig(),
                    pylint=PylintConfig(),
                    eslint=ESLintConfig(enabled=False),
                    zap=ZAPConfig(enabled=False)
                )
            },
            {
                'name': 'Web App Focus',
                'description': 'Focused on web application security',
                'config': SecurityAnalyzerConfig(
                    bandit=BanditConfig(enabled=False),
                    safety=SafetyConfig(enabled=False),
                    pylint=PylintConfig(enabled=False),
                    eslint=ESLintConfig(),
                    zap=ZAPConfig()
                )
            }
        ]
        
        return presets
    
    def validate_config(self, config: SecurityAnalyzerConfig) -> List[str]:
        """Validate security analyzer configuration and return any errors."""
        errors = []
        
        # Validate timeouts
        bandit = config.bandit or BanditConfig()
        safety = config.safety or SafetyConfig()
        pylint_cfg = config.pylint or PylintConfig()
        eslint = config.eslint or ESLintConfig()
        zap = config.zap or ZAPConfig()
        apache_bench = config.apache_bench or ApacheBenchConfig()

        if bandit.timeout < 30 or bandit.timeout > 3600:
            errors.append("Bandit timeout must be between 30 and 3600 seconds")
        if safety.timeout < 30 or safety.timeout > 1800:
            errors.append("Safety timeout must be between 30 and 1800 seconds")
        if pylint_cfg.timeout < 30 or pylint_cfg.timeout > 3600:
            errors.append("Pylint timeout must be between 30 and 3600 seconds")
        if eslint.timeout < 30 or eslint.timeout > 1800:
            errors.append("ESLint timeout must be between 30 and 1800 seconds")
        if zap.timeout < 300 or zap.timeout > 7200:
            errors.append("ZAP timeout must be between 300 and 7200 seconds")
        if apache_bench.timeout < 5 or apache_bench.timeout > 300:
            errors.append("Apache Bench timeout must be between 5 and 300 seconds")
        
        # Validate confidence levels
        valid_confidence = ['LOW', 'MEDIUM', 'HIGH']
        if bandit.confidence_level not in valid_confidence:
            errors.append(f"Bandit confidence level must be one of: {valid_confidence}")
        if bandit.severity_level not in valid_confidence:
            errors.append(f"Bandit severity level must be one of: {valid_confidence}")
        
        # Validate Apache Bench parameters
        if apache_bench.requests < 1 or apache_bench.requests > 10000:
            errors.append("Apache Bench requests must be between 1 and 10000")
        if apache_bench.concurrency < 1 or apache_bench.concurrency > 1000:
            errors.append("Apache Bench concurrency must be between 1 and 1000")
        if apache_bench.concurrency > apache_bench.requests:
            errors.append("Apache Bench concurrency cannot exceed number of requests")
        if apache_bench.timelimit and (apache_bench.timelimit < 10 or apache_bench.timelimit > 3600):
            errors.append("Apache Bench time limit must be between 10 and 3600 seconds")
        
        # Validate ZAP port
        if zap.port < 1024 or zap.port > 65535:
            errors.append("ZAP port must be between 1024 and 65535")
        
        return errors
    
    def export_config(self, config: SecurityAnalyzerConfig, format: str = 'json') -> str:
        """Export configuration to specified format."""
        if format == 'json':
            return json.dumps(asdict(config), indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def import_config(self, config_data: str, format: str = 'json') -> SecurityAnalyzerConfig:
        """Import configuration from specified format."""
        if format == 'json':
            data = json.loads(config_data)
            return self._deserialize_config(data, SecurityAnalyzerConfig)
        else:
            raise ValueError(f"Unsupported import format: {format}")
    
    def _serialize_config(self, config: SecurityAnalyzerConfig) -> str:
        """Serialize configuration to JSON string."""
        return json.dumps(asdict(config), indent=2)
    
    def _deserialize_config(self, config_data: str, config_class) -> SecurityAnalyzerConfig:
        """Deserialize configuration from JSON string."""
        if isinstance(config_data, str):
            data = json.loads(config_data)
        else:
            data = config_data
        
        # Convert nested dictionaries to dataclass instances
        if 'bandit' in data:
            data['bandit'] = BanditConfig(**data['bandit'])
        if 'safety' in data:
            data['safety'] = SafetyConfig(**data['safety'])
        if 'pylint' in data:
            data['pylint'] = PylintConfig(**data['pylint'])
        if 'eslint' in data:
            data['eslint'] = ESLintConfig(**data['eslint'])
        if 'zap' in data:
            data['zap'] = ZAPConfig(**data['zap'])
        
        return config_class(**data)
