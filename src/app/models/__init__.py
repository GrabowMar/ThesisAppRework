"""
Database Models for Thesis Research App

This module defines SQLAlchemy models for the thesis research application
that analyzes AI-generated applications across multiple models.

Models include:
- ModelCapability: AI model metadata and capabilities
- PortConfiguration: Docker port allocations
- GeneratedApplication: AI-generated app instances
- SecurityAnalysis: Security analysis results
- PerformanceTest: Performance testing results
- BatchAnalysis: Batch processing records
- AnalysisConfig: Analyzer configuration settings
- ConfigPreset: Predefined configuration presets
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Import centralized constants and enums
from ..constants import AnalysisStatus, JobStatus, ContainerState
from ..extensions import db

# Import analysis configuration models
from .analysis import AnalysisConfig, ConfigPreset

def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)

class ModelCapability(db.Model):
    """Model for storing AI model capabilities and metadata."""
    __tablename__ = 'model_capabilities'
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    canonical_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    provider = db.Column(db.String(100), nullable=False, index=True)
    model_name = db.Column(db.String(200), nullable=False)
    
    # Capabilities
    is_free = db.Column(db.Boolean, default=False)
    context_window = db.Column(db.Integer, default=0)
    max_output_tokens = db.Column(db.Integer, default=0)
    supports_function_calling = db.Column(db.Boolean, default=False)
    supports_vision = db.Column(db.Boolean, default=False)
    supports_streaming = db.Column(db.Boolean, default=False)
    supports_json_mode = db.Column(db.Boolean, default=False)
    
    # Pricing
    input_price_per_token = db.Column(db.Float, default=0.0)
    output_price_per_token = db.Column(db.Float, default=0.0)
    
    # Performance metrics
    cost_efficiency = db.Column(db.Float, default=0.0)
    safety_score = db.Column(db.Float, default=0.0)
    
    # JSON fields for detailed data
    capabilities_json = db.Column(db.Text)  # Detailed capabilities
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities as dictionary."""
        if self.capabilities_json:
            try:
                return json.loads(self.capabilities_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_capabilities(self, capabilities_dict: Dict[str, Any]) -> None:
        """Set capabilities from dictionary."""
        self.capabilities_json = json.dumps(capabilities_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'canonical_slug': self.canonical_slug,
            'provider': self.provider,
            'model_name': self.model_name,
            'is_free': self.is_free,
            'context_window': self.context_window,
            'max_output_tokens': self.max_output_tokens,
            'supports_function_calling': self.supports_function_calling,
            'supports_vision': self.supports_vision,
            'supports_streaming': self.supports_streaming,
            'supports_json_mode': self.supports_json_mode,
            'input_price_per_token': self.input_price_per_token,
            'output_price_per_token': self.output_price_per_token,
            'cost_efficiency': self.cost_efficiency,
            'safety_score': self.safety_score,
            'capabilities': self.get_capabilities(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ModelCapability {self.model_id}>'


class PortConfiguration(db.Model):
    """Model for storing Docker port configurations."""
    __tablename__ = 'port_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(200), nullable=False, index=True)  # Model name/ID
    app_num = db.Column(db.Integer, nullable=False, index=True)    # App number
    frontend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    backend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    is_available = db.Column(db.Boolean, default=True, index=True)
    
    # JSON field for additional metadata
    metadata_json = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Unique constraint for model + app combination
    __table_args__ = (db.UniqueConstraint('model', 'app_num', name='unique_model_app_port'),)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model': self.model,
            'app_num': self.app_num,
            'frontend_port': self.frontend_port,
            'backend_port': self.backend_port,
            'is_available': self.is_available,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<PortConfiguration {self.model}/app{self.app_num}>'


class GeneratedApplication(db.Model):
    """Model for storing information about AI-generated applications."""
    __tablename__ = 'generated_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), nullable=False, index=True)
    app_number = db.Column(db.Integer, nullable=False)
    app_type = db.Column(db.String(50), nullable=False)
    provider = db.Column(db.String(100), nullable=False, index=True)  # Added provider field
    generation_status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    has_backend = db.Column(db.Boolean, default=False)
    has_frontend = db.Column(db.Boolean, default=False)
    has_docker_compose = db.Column(db.Boolean, default=False)
    backend_framework = db.Column(db.String(50))
    frontend_framework = db.Column(db.String(50))
    container_status = db.Column(db.String(50), default='stopped')
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())
    
    # Relationships
    security_analyses = db.relationship('SecurityAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    performance_tests = db.relationship('PerformanceTest', backref='application', lazy=True, cascade='all, delete-orphan')
    zap_analyses = db.relationship('ZAPAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    openrouter_analyses = db.relationship('OpenRouterAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('model_slug', 'app_number', name='unique_model_app'),)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def get_directory_path(self) -> str:
        """Get the directory path for this application."""
        return f"{self.model_slug}/app_{self.app_number}"
    
    def get_ports(self) -> Dict[str, Any]:
        """Get port configuration for this application."""
        return {}  # Implement based on port configuration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'app_type': self.app_type,
            'provider': self.provider,
            'generation_status': self.generation_status.value if self.generation_status else None,
            'has_backend': self.has_backend,
            'has_frontend': self.has_frontend,
            'has_docker_compose': self.has_docker_compose,
            'backend_framework': self.backend_framework,
            'frontend_framework': self.frontend_framework,
            'container_status': self.container_status,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<GeneratedApplication {self.model_slug}/app{self.app_number}>'


class SecurityAnalysis(db.Model):
    """Model for storing security analysis results with comprehensive tool configurations."""
    __tablename__ = 'security_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis status and configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    analysis_name = db.Column(db.String(200), default='Security Analysis')
    description = db.Column(db.Text)
    
    # Tool enablement with detailed configuration
    bandit_enabled = db.Column(db.Boolean, default=True)
    bandit_config_json = db.Column(db.Text)  # Bandit-specific configuration
    
    safety_enabled = db.Column(db.Boolean, default=True)
    safety_config_json = db.Column(db.Text)  # Safety-specific configuration
    
    pylint_enabled = db.Column(db.Boolean, default=True)
    pylint_config_json = db.Column(db.Text)  # PyLint-specific configuration
    
    eslint_enabled = db.Column(db.Boolean, default=True)
    eslint_config_json = db.Column(db.Text)  # ESLint-specific configuration
    
    npm_audit_enabled = db.Column(db.Boolean, default=True)
    npm_audit_config_json = db.Column(db.Text)  # npm audit configuration
    
    snyk_enabled = db.Column(db.Boolean, default=False)
    snyk_config_json = db.Column(db.Text)  # Snyk-specific configuration
    
    zap_enabled = db.Column(db.Boolean, default=False)
    zap_config_json = db.Column(db.Text)  # OWASP ZAP configuration
    
    semgrep_enabled = db.Column(db.Boolean, default=False)
    semgrep_config_json = db.Column(db.Text)  # Semgrep configuration
    
    # Global analysis settings
    severity_threshold = db.Column(db.String(20), default='low')  # critical, high, medium, low
    max_issues_per_tool = db.Column(db.Integer, default=1000)
    timeout_minutes = db.Column(db.Integer, default=30)
    exclude_patterns = db.Column(db.Text)  # JSON array of file/directory patterns to exclude
    include_patterns = db.Column(db.Text)  # JSON array of file/directory patterns to include
    
    # Results summary
    total_issues = db.Column(db.Integer, default=0)
    critical_severity_count = db.Column(db.Integer, default=0)
    high_severity_count = db.Column(db.Integer, default=0)
    medium_severity_count = db.Column(db.Integer, default=0)
    low_severity_count = db.Column(db.Integer, default=0)
    tools_run_count = db.Column(db.Integer, default=0)
    tools_failed_count = db.Column(db.Integer, default=0)
    
    # Performance metrics
    analysis_duration = db.Column(db.Float)  # Duration in seconds
    
    # JSON fields for detailed results and configuration
    results_json = db.Column(db.Text)       # Detailed analysis results
    metadata_json = db.Column(db.Text)      # Analysis metadata
    global_config_json = db.Column(db.Text) # Global analysis configuration
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self) -> Dict[str, Any]:
        """Get results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict: Dict[str, Any]) -> None:
        """Set results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def get_bandit_config(self) -> Dict[str, Any]:
        """Get Bandit configuration as dictionary."""
        if self.bandit_config_json:
            try:
                return json.loads(self.bandit_config_json)
            except json.JSONDecodeError:
                return {}
        return self._get_default_bandit_config()
    
    def set_bandit_config(self, config_dict: Dict[str, Any]) -> None:
        """Set Bandit configuration from dictionary."""
        self.bandit_config_json = json.dumps(config_dict)
    
    def _get_default_bandit_config(self) -> Dict[str, Any]:
        """Get default Bandit configuration."""
        return {
            "tests": [],  # Empty = run all tests
            "skips": ["B101"],  # Skip assert_used by default
            "exclude_dirs": ["tests", "test", "__pycache__", ".git"],
            "confidence": "low",  # low, medium, high
            "severity": "low",  # low, medium, high  
            "format": "json",
            "recursive": True,
            "aggregate": "file",
            "context_lines": 3,
            "msg_template": "{abspath}:{line}: {test_id}[bandit]: {severity}: {msg}",
            "baseline": None,  # Path to baseline file
            "ini_path": None   # Path to custom .bandit file
        }
    
    def get_safety_config(self) -> Dict[str, Any]:
        """Get Safety configuration as dictionary."""
        if self.safety_config_json:
            try:
                return json.loads(self.safety_config_json)
            except json.JSONDecodeError:
                return {}
        return self._get_default_safety_config()
    
    def set_safety_config(self, config_dict: Dict[str, Any]) -> None:
        """Set Safety configuration from dictionary."""
        self.safety_config_json = json.dumps(config_dict)
    
    def _get_default_safety_config(self) -> Dict[str, Any]:
        """Get default Safety configuration."""
        return {
            "api_key": None,  # PyUp API key for commercial use
            "db": None,  # Custom vulnerability database path
            "ignore": [],  # List of vulnerability IDs to ignore
            "severity": ["critical", "high", "medium", "low"],  # Severity levels to report
            "output": "json",  # json, text, bare
            "full_report": True,
            "stdin": False,
            "files": [],  # Specific files to check
            "continue_on_error": True,
            "policy_file": None,  # Path to Safety policy file
            "audit_and_monitor": False,  # Enable audit mode
            "proxy_host": None,
            "proxy_port": None,
            "timeout": 60
        }
    
    def get_eslint_config(self) -> Dict[str, Any]:
        """Get ESLint configuration as dictionary."""
        if self.eslint_config_json:
            try:
                return json.loads(self.eslint_config_json)
            except json.JSONDecodeError:
                return {}
        return self._get_default_eslint_config()
    
    def set_eslint_config(self, config_dict: Dict[str, Any]) -> None:
        """Set ESLint configuration from dictionary."""
        self.eslint_config_json = json.dumps(config_dict)
    
    def _get_default_eslint_config(self) -> Dict[str, Any]:
        """Get default ESLint configuration."""
        return {
            "extends": ["eslint:recommended", "plugin:security/recommended"],
            "plugins": ["security"],
            "parserOptions": {
                "ecmaVersion": 2020,
                "sourceType": "module"
            },
            "env": {
                "browser": True,
                "node": True,
                "es6": True
            },
            "rules": {
                "no-eval": "error",
                "no-implied-eval": "error", 
                "no-new-func": "error",
                "no-script-url": "error",
                "security/detect-eval-with-expression": "error",
                "security/detect-non-literal-regexp": "warn",
                "security/detect-non-literal-require": "warn",
                "security/detect-object-injection": "warn",
                "security/detect-possible-timing-attacks": "warn",
                "security/detect-pseudoRandomBytes": "warn",
                "security/detect-unsafe-regex": "error",
                "no-console": "warn",
                "no-debugger": "error",
                "no-alert": "warn"
            },
            "format": "json",
            "max_warnings": 50,
            "cache": True,
            "cache_location": ".eslintcache",
            "ignore_pattern": ["node_modules/**", "dist/**", "build/**"]
        }
    
    def get_pylint_config(self) -> Dict[str, Any]:
        """Get PyLint configuration as dictionary."""
        if self.pylint_config_json:
            try:
                return json.loads(self.pylint_config_json)
            except json.JSONDecodeError:
                return {}
        return self._get_default_pylint_config()
    
    def set_pylint_config(self, config_dict: Dict[str, Any]) -> None:
        """Set PyLint configuration from dictionary."""
        self.pylint_config_json = json.dumps(config_dict)
    
    def _get_default_pylint_config(self) -> Dict[str, Any]:
        """Get default PyLint configuration."""
        return {
            "disable": ["R0903", "R0913", "C0103"],  # too-few-public-methods, too-many-arguments, invalid-name
            "enable": [],  # Additional checks to enable
            "rcfile": None,  # Path to custom .pylintrc file
            "output_format": "json",
            "reports": False,
            "score": True,
            "confidence": ["HIGH", "CONTROL_FLOW", "INFERENCE", "INFERENCE_FAILURE", "UNDEFINED"],
            "load_plugins": [],  # Additional pylint plugins
            "fail_under": 5.0,  # Minimum score to pass
            "good_names": ["i", "j", "k", "ex", "Run", "_"],
            "bad_names": ["foo", "bar", "baz", "toto", "tutu", "tata"],
            "include_naming_hint": True,
            "max_line_length": 100,
            "max_module_lines": 1000,
            "max_args": 5,
            "max_locals": 15,
            "max_returns": 6,
            "max_branches": 12,
            "max_statements": 50,
            "max_parents": 7,
            "max_attributes": 7,
            "min_public_methods": 2,
            "max_public_methods": 20,
            "max_bool_expr": 5
        }
    
    def get_zap_config(self) -> Dict[str, Any]:
        """Get OWASP ZAP configuration as dictionary."""
        if self.zap_config_json:
            try:
                return json.loads(self.zap_config_json)
            except json.JSONDecodeError:
                return {}
        return self._get_default_zap_config()
    
    def set_zap_config(self, config_dict: Dict[str, Any]) -> None:
        """Set OWASP ZAP configuration from dictionary."""
        self.zap_config_json = json.dumps(config_dict)
    
    def _get_default_zap_config(self) -> Dict[str, Any]:
        """Get default OWASP ZAP configuration."""
        return {
            "target_url": "",  # Target URL for scanning
            "scan_type": "active",  # active, passive, spider, ajax_spider
            "scan_policy": "Default Policy",
            "context_name": "Default Context",
            "authentication": {
                "enabled": False,
                "method": "form",  # form, script, http
                "username": "",
                "password": "",
                "login_url": "",
                "username_field": "",
                "password_field": "",
                "submit_field": ""
            },
            "spider_config": {
                "max_depth": 5,
                "max_duration": 10,  # minutes
                "max_children": 0,  # 0 = unlimited
                "recurse": True,
                "subtree_only": True,
                "thread_count": 2
            },
            "active_scan_config": {
                "concurrent_hosts": 1,
                "threads_per_host": 2,
                "max_rule_duration": 5,  # minutes
                "max_scan_duration": 30,  # minutes
                "delay_between_requests": 0,  # milliseconds
                "handle_anti_csrf": True,
                "inject_plugin_id": False,
                "strength": "medium",  # low, medium, high, insane
                "threshold": "medium"  # off, low, medium, high
            },
            "reporting": {
                "include_false_positives": False,
                "include_confidence_1": True,  # False positive
                "include_confidence_2": True,  # Low
                "include_confidence_3": True,  # Medium
                "include_confidence_4": True,  # High
                "include_confidence_5": True   # Confirmed
            }
        }
    
    def get_exclude_patterns(self) -> List[str]:
        """Get exclude patterns as list."""
        if self.exclude_patterns:
            try:
                return json.loads(self.exclude_patterns)
            except json.JSONDecodeError:
                return []
        return ["tests/**", "test/**", "**/test_*", "**/*_test.py", "__pycache__/**", ".git/**", "node_modules/**"]
    
    def set_exclude_patterns(self, patterns_list: List[str]) -> None:
        """Set exclude patterns from list."""
        self.exclude_patterns = json.dumps(patterns_list)
    
    def get_include_patterns(self) -> List[str]:
        """Get include patterns as list."""
        if self.include_patterns:
            try:
                return json.loads(self.include_patterns)
            except json.JSONDecodeError:
                return []
        return ["**/*.py", "**/*.js", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.vue"]
    
    def set_include_patterns(self, patterns_list: List[str]) -> None:
        """Set include patterns from list."""
        self.include_patterns = json.dumps(patterns_list)
    
    def get_global_config(self) -> Dict[str, Any]:
        """Get global analysis configuration."""
        if self.global_config_json:
            try:
                return json.loads(self.global_config_json)
            except json.JSONDecodeError:
                return {}
        return {
            "parallel_execution": True,
            "fail_on_first_error": False,
            "generate_reports": True,
            "report_formats": ["json", "html"],
            "save_intermediate_results": True,
            "cleanup_temp_files": True
        }
    
    def set_global_config(self, config_dict: Dict[str, Any]) -> None:
        """Set global configuration from dictionary."""
        self.global_config_json = json.dumps(config_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'analysis_name': self.analysis_name,
            'description': self.description,
            'bandit_enabled': self.bandit_enabled,
            'bandit_config': self.get_bandit_config(),
            'safety_enabled': self.safety_enabled,
            'safety_config': self.get_safety_config(),
            'pylint_enabled': self.pylint_enabled,
            'pylint_config': self.get_pylint_config(),
            'eslint_enabled': self.eslint_enabled,
            'eslint_config': self.get_eslint_config(),
            'npm_audit_enabled': self.npm_audit_enabled,
            'snyk_enabled': self.snyk_enabled,
            'zap_enabled': self.zap_enabled,
            'zap_config': self.get_zap_config(),
            'semgrep_enabled': self.semgrep_enabled,
            'severity_threshold': self.severity_threshold,
            'max_issues_per_tool': self.max_issues_per_tool,
            'timeout_minutes': self.timeout_minutes,
            'exclude_patterns': self.get_exclude_patterns(),
            'include_patterns': self.get_include_patterns(),
            'total_issues': self.total_issues,
            'critical_severity_count': self.critical_severity_count,
            'high_severity_count': self.high_severity_count,
            'medium_severity_count': self.medium_severity_count,
            'low_severity_count': self.low_severity_count,
            'tools_run_count': self.tools_run_count,
            'tools_failed_count': self.tools_failed_count,
            'analysis_duration': self.analysis_duration,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'global_config': self.get_global_config(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<SecurityAnalysis {self.id}>'


class PerformanceTest(db.Model):
    """Model for storing performance test results."""
    __tablename__ = 'performance_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Test configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    test_type = db.Column(db.String(50), default='load')  # load, stress, spike
    users = db.Column(db.Integer, default=10)
    spawn_rate = db.Column(db.Float, default=1.0)
    test_duration = db.Column(db.Integer, default=60)  # seconds
    
    # Results
    requests_per_second = db.Column(db.Float)
    average_response_time = db.Column(db.Float)  # milliseconds
    p95_response_time = db.Column(db.Float)
    p99_response_time = db.Column(db.Float)
    error_rate = db.Column(db.Float)  # percentage
    total_requests = db.Column(db.Integer)
    failed_requests = db.Column(db.Integer)
    
    # JSON fields
    results_json = db.Column(db.Text)       # Detailed test results
    metadata_json = db.Column(db.Text)      # Test metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self) -> Dict[str, Any]:
        """Get results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict: Dict[str, Any]) -> None:
        """Set results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'test_type': self.test_type,
            'users': self.users,
            'spawn_rate': self.spawn_rate,
            'test_duration': self.test_duration,
            'requests_per_second': self.requests_per_second,
            'average_response_time': self.average_response_time,
            'p95_response_time': self.p95_response_time,
            'p99_response_time': self.p99_response_time,
            'error_rate': self.error_rate,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<PerformanceTest {self.id}>'


class ZAPAnalysis(db.Model):
    """Model for storing ZAP security analysis results."""
    __tablename__ = 'zap_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # ZAP specific configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    target_url = db.Column(db.String(500), nullable=False)
    scan_type = db.Column(db.String(50), default='active')  # active, passive, spider
    
    # Results summary
    high_risk_alerts = db.Column(db.Integer, default=0)
    medium_risk_alerts = db.Column(db.Integer, default=0)
    low_risk_alerts = db.Column(db.Integer, default=0)
    informational_alerts = db.Column(db.Integer, default=0)
    
    # JSON fields
    zap_report_json = db.Column(db.Text)    # Full ZAP report
    metadata_json = db.Column(db.Text)      # Scan metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_zap_report(self) -> Dict[str, Any]:
        """Get ZAP report as dictionary."""
        if self.zap_report_json:
            try:
                return json.loads(self.zap_report_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_zap_report(self, report_dict: Dict[str, Any]) -> None:
        """Set ZAP report from dictionary."""
        self.zap_report_json = json.dumps(report_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'target_url': self.target_url,
            'scan_type': self.scan_type,
            'high_risk_alerts': self.high_risk_alerts,
            'medium_risk_alerts': self.medium_risk_alerts,
            'low_risk_alerts': self.low_risk_alerts,
            'informational_alerts': self.informational_alerts,
            'zap_report': self.get_zap_report(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ZAPAnalysis {self.id}>'


class OpenRouterAnalysis(db.Model):
    """Model for storing OpenRouter AI analysis results."""
    __tablename__ = 'openrouter_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    analyzer_model = db.Column(db.String(200))  # Which AI model was used
    analysis_prompt = db.Column(db.Text)
    
    # Results
    overall_score = db.Column(db.Float)  # 0-100
    code_quality_score = db.Column(db.Float)
    security_score = db.Column(db.Float)
    maintainability_score = db.Column(db.Float)
    
    # Token usage and cost
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    cost_usd = db.Column(db.Float)
    
    # JSON fields
    findings_json = db.Column(db.Text)      # Structured findings
    recommendations_json = db.Column(db.Text)  # AI recommendations
    summary = db.Column(db.Text)            # Analysis summary
    metadata_json = db.Column(db.Text)      # Analysis metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_findings(self) -> Dict[str, Any]:
        """Get findings as dictionary."""
        if self.findings_json:
            try:
                return json.loads(self.findings_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_findings(self, findings_dict: Dict[str, Any]) -> None:
        """Set findings from dictionary."""
        self.findings_json = json.dumps(findings_dict)
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations as list."""
        if self.recommendations_json:
            try:
                return json.loads(self.recommendations_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_recommendations(self, recommendations_list: List[str]) -> None:
        """Set recommendations from list."""
        self.recommendations_json = json.dumps(recommendations_list)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'analyzer_model': self.analyzer_model,
            'analysis_prompt': self.analysis_prompt,
            'overall_score': self.overall_score,
            'code_quality_score': self.code_quality_score,
            'security_score': self.security_score,
            'maintainability_score': self.maintainability_score,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cost_usd': self.cost_usd,
            'findings': self.get_findings(),
            'recommendations': self.get_recommendations(),
            'summary': self.summary,
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<OpenRouterAnalysis {self.id}>'


class ContainerizedTest(db.Model):
    """Model for tracking containerized test services."""
    __tablename__ = 'containerized_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    container_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    service_type = db.Column(db.String(100), nullable=False)  # security, performance, zap
    
    # Container information
    container_id = db.Column(db.String(100))
    image_name = db.Column(db.String(200))
    port = db.Column(db.Integer)
    status = db.Column(db.String(50), default=ContainerState.STOPPED.value)
    
    # Health monitoring
    last_health_check = db.Column(db.DateTime)
    health_status = db.Column(db.String(50))  # healthy, unhealthy, unknown
    
    # Usage statistics
    total_requests = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    # JSON fields
    config_json = db.Column(db.Text)        # Container configuration
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration from dictionary."""
        self.config_json = json.dumps(config_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'container_name': self.container_name,
            'service_type': self.service_type,
            'container_id': self.container_id,
            'image_name': self.image_name,
            'port': self.port,
            'status': self.status,
            'last_health_check': self.last_health_check,
            'health_status': self.health_status,
            'total_requests': self.total_requests,
            'last_used': self.last_used,
            'config': self.get_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ContainerizedTest {self.container_name}>'


class OpenRouterModelCache(db.Model):
    """Model for caching OpenRouter API model data to reduce API calls."""
    __tablename__ = 'openrouter_model_cache'
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    
    # Cached data from OpenRouter API
    model_data_json = db.Column(db.Text, nullable=False)  # Full OpenRouter model data
    
    # Cache metadata
    cache_expires_at = db.Column(db.DateTime, nullable=False, index=True)
    fetch_duration = db.Column(db.Float)  # Time taken to fetch from API
    api_response_status = db.Column(db.Integer)  # HTTP status code
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    last_accessed = db.Column(db.DateTime, default=utc_now)  # Track usage
    
    def get_model_data(self) -> Dict[str, Any]:
        """Get cached model data as dictionary."""
        if self.model_data_json:
            try:
                return json.loads(self.model_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_model_data(self, model_dict: Dict[str, Any]) -> None:
        """Set model data from dictionary."""
        self.model_data_json = json.dumps(model_dict)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return utc_now() > self.cache_expires_at
    
    def mark_accessed(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = utc_now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'model_data': self.get_model_data(),
            'cache_expires_at': self.cache_expires_at,
            'fetch_duration': self.fetch_duration,
            'api_response_status': self.api_response_status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_accessed': self.last_accessed,
            'is_expired': self.is_expired()
        }
    
    def __repr__(self) -> str:
        return f'<OpenRouterModelCache {self.model_id}>'


class ExternalModelInfoCache(db.Model):
    """Cache for external model info (primarily OpenRouter).

    Keyed by canonical model slug, stores JSON payload and expiry.
    """
    __tablename__ = 'external_model_info_cache'

    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Cached merged JSON payload
    merged_json = db.Column(db.Text, nullable=False)

    # Cache metadata
    cache_expires_at = db.Column(db.DateTime, nullable=False, index=True)
    last_refreshed = db.Column(db.DateTime, default=utc_now)
    source_notes = db.Column(db.String(200))  # e.g., "openrouter+hf"

    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)

    def get_data(self) -> Dict[str, Any]:
        try:
            return json.loads(self.merged_json) if self.merged_json else {}
        except json.JSONDecodeError:
            return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        self.merged_json = json.dumps(data)

    def is_expired(self) -> bool:
        return utc_now() > self.cache_expires_at

    def mark_refreshed(self, ttl_hours: int) -> None:
        self.last_refreshed = utc_now()
        self.cache_expires_at = utc_now().replace(microsecond=0) + timedelta(hours=ttl_hours)

    def __repr__(self) -> str:
        return f'<ExternalModelInfoCache {self.model_slug}>'


class BatchAnalysis(db.Model):
    """Model for tracking batch analysis jobs."""
    __tablename__ = 'batch_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Job configuration
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING, index=True)
    analysis_types = db.Column(db.Text)     # JSON array of analysis types
    
    # Progress tracking
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    failed_tasks = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Configuration filters
    model_filter = db.Column(db.Text)       # JSON array of model patterns
    app_filter = db.Column(db.Text)         # JSON array of app number patterns
    
    # Results summary
    results_summary = db.Column(db.Text)    # JSON summary of results
    
    # Timing
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    estimated_completion = db.Column(db.DateTime)
    
    # JSON fields
    config_json = db.Column(db.Text)        # Full job configuration
    metadata_json = db.Column(db.Text)      # Job metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_analysis_types(self) -> List[str]:
        """Get analysis types as list."""
        if self.analysis_types:
            try:
                return json.loads(self.analysis_types)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_analysis_types(self, types_list: List[str]) -> None:
        """Set analysis types from list."""
        self.analysis_types = json.dumps(types_list)
    
    def get_model_filter(self) -> List[str]:
        """Get model filter as list."""
        if self.model_filter:
            try:
                return json.loads(self.model_filter)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_model_filter(self, filter_list: List[str]) -> None:
        """Set model filter from list."""
        self.model_filter = json.dumps(filter_list)
    
    def get_app_filter(self) -> List[int]:
        """Get app filter as list."""
        if self.app_filter:
            try:
                return json.loads(self.app_filter)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_app_filter(self, filter_list: List[int]) -> None:
        """Set app filter from list."""
        self.app_filter = json.dumps(filter_list)
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get results summary as dictionary."""
        if self.results_summary:
            try:
                return json.loads(self.results_summary)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results_summary(self, summary_dict: Dict[str, Any]) -> None:
        """Set results summary from dictionary."""
        self.results_summary = json.dumps(summary_dict)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration from dictionary."""
        self.config_json = json.dumps(config_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def update_progress(self) -> None:
        """Update progress percentage based on task counts."""
        if self.total_tasks > 0:
            self.progress_percentage = (self.completed_tasks / self.total_tasks) * 100.0
        else:
            self.progress_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'status': self.status.value if self.status else None,
            'analysis_types': self.get_analysis_types(),
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'progress_percentage': self.progress_percentage,
            'model_filter': self.get_model_filter(),
            'app_filter': self.get_app_filter(),
            'results_summary': self.get_results_summary(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'estimated_completion': self.estimated_completion,
            'config': self.get_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<BatchAnalysis {self.batch_id}>'


# Initialize database function
def init_db():
    """Create all database tables."""
    db.create_all()

# Export all models for easy import
__all__ = [
    'db',
    'utc_now',
    'init_db',
    'ModelCapability',
    'PortConfiguration', 
    'GeneratedApplication',
    'SecurityAnalysis',
    'PerformanceTest',
    'ZAPAnalysis',
    'OpenRouterAnalysis',
    'OpenRouterModelCache',
    'ExternalModelInfoCache',
    'ContainerizedTest',
    'BatchAnalysis',
    'AnalysisConfig',
    'ConfigPreset'
]
