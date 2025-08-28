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

# Analysis configuration models are now defined in this file below

# Import centralized enums for analysis system
from ..constants import AnalysisType, AnalysisStatus, JobPriority as Priority, JobStatus as BatchStatus, SeverityLevel

# Cleanup models for file replacement are defined below

def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)

class ModelCapability(db.Model):
    """Model for storing AI model capabilities and metadata."""
    __tablename__ = 'model_capabilities'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    canonical_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    provider = db.Column(db.String(100), nullable=False, index=True)
    model_name = db.Column(db.String(200), nullable=False)
    
    # Capabilities
    is_free = db.Column(db.Boolean, default=False)
    # Installed flag: indicates the model has local generated applications under misc/models/<slug>
    installed = db.Column(db.Boolean, default=False, index=True)
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
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(200), nullable=False, index=True)  # Model name/ID
    app_num = db.Column(db.Integer, nullable=False, index=True)    # App number
    frontend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    backend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    is_available = db.Column(db.Boolean, default=True, index=True)
    
    # JSON field for additional metadata
    metadata_json = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
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
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, 
                          onupdate=utc_now)
    
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
        # Import here to avoid circular imports at module import-time
        try:
            from app.models import PortConfiguration, ModelCapability  # type: ignore
        except Exception:
            # If imports fail (e.g. during some early import phases), return empty dict
            return {}

        # Try to find a PortConfiguration using several strategies similar to ModelService
        try:
            # exact match first
            pc = PortConfiguration.query.filter_by(model=self.model_slug, app_num=self.app_number).first()
            if not pc:
                # look up ModelCapability for alternative names
                model_cap = ModelCapability.query.filter_by(canonical_slug=self.model_slug).first()
                if model_cap and getattr(model_cap, 'model_name', None):
                    pc = PortConfiguration.query.filter_by(model=model_cap.model_name, app_num=self.app_number).first()
                if not pc and model_cap and getattr(model_cap, 'canonical_slug', None):
                    pc = PortConfiguration.query.filter_by(model=model_cap.canonical_slug, app_num=self.app_number).first()

            # try simple normalizations
            if not pc:
                candidates = set([
                    self.model_slug.replace('-', '_'),
                    self.model_slug.replace('_', '-'),
                    self.model_slug.replace(' ', '_'),
                    self.model_slug.replace(' ', '-')
                ])
                for cand in candidates:
                    if not cand:
                        continue
                    pc = PortConfiguration.query.filter_by(model=cand, app_num=self.app_number).first()
                    if pc:
                        break

            if not pc:
                return {}

            return {
                'frontend': pc.frontend_port,
                'backend': pc.backend_port,
                'is_available': bool(pc.is_available)
            }
        except Exception:
            return {}
    
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
    __table_args__ = {'extend_existing': True}
    
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
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
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
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
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
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
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
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    container_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    service_type = db.Column(db.String(100), nullable=False)  # security, performance, zap
    
    # Container information
    container_id = db.Column(db.String(100))
    image_name = db.Column(db.String(200))
    port = db.Column(db.Integer)
    status = db.Column(db.String(50), default=ContainerState.STOPPED.value)
    
    # Health monitoring
    last_health_check = db.Column(db.DateTime(timezone=True))
    health_status = db.Column(db.String(50))  # healthy, unhealthy, unknown
    
    # Usage statistics
    total_requests = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime(timezone=True))
    
    # JSON fields
    config_json = db.Column(db.Text)        # Container configuration
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    
    # Cached data from OpenRouter API
    model_data_json = db.Column(db.Text, nullable=False)  # Full OpenRouter model data
    
    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fetch_duration = db.Column(db.Float)  # Time taken to fetch from API
    api_response_status = db.Column(db.Integer)  # HTTP status code
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_accessed = db.Column(db.DateTime(timezone=True), default=utc_now)  # Track usage
    
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
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Cached merged JSON payload
    merged_json = db.Column(db.Text, nullable=False)

    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    last_refreshed = db.Column(db.DateTime(timezone=True), default=utc_now)
    source_notes = db.Column(db.String(200))  # e.g., "openrouter+hf"

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

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
    __table_args__ = {'extend_existing': True}
    
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
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    estimated_completion = db.Column(db.DateTime(timezone=True))
    
    # JSON fields
    config_json = db.Column(db.Text)        # Full job configuration
    metadata_json = db.Column(db.Text)      # Job metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
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


# ---------------------------------------------------------------------------
# Advanced Batch Orchestration Models (Queue, Scheduling, Resources, Templates)
# ---------------------------------------------------------------------------

class BatchQueue(db.Model):
    """Queue entries for batch jobs with priority scheduling.

    Separate from BatchAnalysis to allow multiple queued states, requeueing,
    and historical retention even if core batch record archived.
    """
    __tablename__ = 'batch_queues'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), db.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True)
    priority = db.Column(db.String(20), nullable=False, index=True, default='normal')  # low, normal, high, urgent
    status = db.Column(db.String(30), nullable=False, default='queued', index=True)  # queued, dispatching, running, paused, completed, cancelled, failed
    position = db.Column(db.Integer, nullable=True)  # Optional snapshot position within its priority lane
    attempt_count = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, data: Dict[str, Any]):
        self.metadata_json = json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'priority': self.priority,
            'status': self.status,
            'position': self.position,
            'attempt_count': self.attempt_count,
            'last_error': self.last_error,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f'<BatchQueue {self.batch_id} prio={self.priority} status={self.status}>'


class BatchDependency(db.Model):
    """Dependency edges between batch jobs (batch B waits for A)."""
    __tablename__ = 'batch_dependencies'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), db.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True)
    depends_on_batch_id = db.Column(db.String(100), nullable=False, index=True)
    satisfied = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        db.UniqueConstraint('batch_id', 'depends_on_batch_id', name='uq_batch_dependency'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'depends_on_batch_id': self.depends_on_batch_id,
            'satisfied': self.satisfied,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f'<BatchDependency {self.batch_id}->{self.depends_on_batch_id} satisfied={self.satisfied}>'


class BatchSchedule(db.Model):
    """Recurring batch scheduling (cron-like expressions)."""
    __tablename__ = 'batch_schedules'

    id = db.Column(db.Integer, primary_key=True)
    batch_config_json = db.Column(db.Text, nullable=False)  # Stored config to instantiate new BatchAnalysis
    cron_expression = db.Column(db.String(120), nullable=False, index=True)
    last_run = db.Column(db.DateTime(timezone=True))
    next_run = db.Column(db.DateTime(timezone=True))
    enabled = db.Column(db.Boolean, default=True, index=True)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_batch_config(self) -> Dict[str, Any]:
        try:
            return json.loads(self.batch_config_json) if self.batch_config_json else {}
        except json.JSONDecodeError:
            return {}

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, data: Dict[str, Any]):
        self.metadata_json = json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'cron_expression': self.cron_expression,
            'last_run': self.last_run,
            'next_run': self.next_run,
            'enabled': self.enabled,
            'batch_config': self.get_batch_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f'<BatchSchedule cron={self.cron_expression} enabled={self.enabled}>'


class BatchResourceUsage(db.Model):
    """Resource metrics recorded per batch & analyzer type."""
    __tablename__ = 'batch_resource_usage'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), db.ForeignKey('batch_analyses.batch_id'), nullable=False, index=True)
    analyzer_type = db.Column(db.String(50), nullable=False, index=True)
    peak_memory = db.Column(db.Float)  # MB
    peak_cpu = db.Column(db.Float)     # percentage
    duration = db.Column(db.Float)     # seconds
    sample_count = db.Column(db.Integer, default=0)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, data: Dict[str, Any]):
        self.metadata_json = json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'analyzer_type': self.analyzer_type,
            'peak_memory': self.peak_memory,
            'peak_cpu': self.peak_cpu,
            'duration': self.duration,
            'sample_count': self.sample_count,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f'<BatchResourceUsage {self.batch_id} {self.analyzer_type}>'


class BatchTemplate(db.Model):
    """Reusable saved batch configuration templates."""
    __tablename__ = 'batch_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False, index=True)
    description = db.Column(db.Text)
    batch_config_json = db.Column(db.Text, nullable=False)  # Saved payload for creating job
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_batch_config(self) -> Dict[str, Any]:
        try:
            return json.loads(self.batch_config_json) if self.batch_config_json else {}
        except json.JSONDecodeError:
            return {}

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, data: Dict[str, Any]):
        self.metadata_json = json.dumps(data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'batch_config': self.get_batch_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f'<BatchTemplate {self.name}>'


class ProcessTracking(db.Model):
    """Track running processes to replace PID files."""
    __tablename__ = 'process_tracking'
    
    # Primary identification
    id = db.Column(db.Integer, primary_key=True)
    
    # Process information
    service_name = db.Column(db.String(100), nullable=False, index=True)  # celery_beat, celery_worker, flask_app
    service_type = db.Column(db.String(50), nullable=False, index=True)   # main, analyzer
    process_id = db.Column(db.Integer, nullable=False)
    
    # Status and health
    status = db.Column(db.String(20), default='running', index=True)  # running, stopped, crashed
    host = db.Column(db.String(100), default='localhost')
    port = db.Column(db.Integer)
    
    # Process metadata
    command_line = db.Column(db.Text)
    working_directory = db.Column(db.String(500))
    environment_info_json = db.Column(db.Text)
    
    # Monitoring
    last_heartbeat = db.Column(db.DateTime(timezone=True), default=utc_now)
    resource_usage_json = db.Column(db.Text)  # CPU, memory, etc.
    
    # Timestamps
    started_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    stopped_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get environment info as dictionary."""
        if self.environment_info_json:
            try:
                return json.loads(self.environment_info_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_environment_info(self, info: Dict[str, Any]) -> None:
        """Set environment info."""
        self.environment_info_json = json.dumps(info)
    
    def get_resource_usage(self) -> Dict[str, Any]:
        """Get resource usage as dictionary."""
        if self.resource_usage_json:
            try:
                return json.loads(self.resource_usage_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_resource_usage(self, usage: Dict[str, Any]) -> None:
        """Set resource usage."""
        self.resource_usage_json = json.dumps(usage)
    
    def mark_stopped(self) -> None:
        """Mark process as stopped."""
        self.status = 'stopped'
        self.stopped_at = utc_now()
    
    def update_heartbeat(self, resource_usage: Dict[str, Any] = None) -> None:
        """Update last heartbeat and optionally resource usage."""
        self.last_heartbeat = utc_now()
        if resource_usage:
            self.set_resource_usage(resource_usage)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'service_name': self.service_name,
            'service_type': self.service_type,
            'process_id': self.process_id,
            'status': self.status,
            'host': self.host,
            'port': self.port,
            'command_line': self.command_line,
            'working_directory': self.working_directory,
            'environment_info': self.get_environment_info(),
            'resource_usage': self.get_resource_usage(),
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'stopped_at': self.stopped_at.isoformat() if self.stopped_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self) -> str:
        return f'<ProcessTracking {self.service_name}:{self.process_id}>'


class TestResults(db.Model):
    """Store test results to replace JSON result files."""
    __tablename__ = 'test_results'
    
    # Primary identification
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Test information
    test_type = db.Column(db.String(50), nullable=False, index=True)  # smoke_test, api_test, integration_test
    test_name = db.Column(db.String(200), nullable=False)
    test_suite = db.Column(db.String(100), index=True)
    
    # Target information
    target_url = db.Column(db.String(500))
    target_service = db.Column(db.String(100))
    model_slug = db.Column(db.String(200), index=True)
    app_number = db.Column(db.Integer, index=True)
    
    # Results
    status = db.Column(db.String(20), nullable=False, index=True)  # passed, failed, error, skipped
    response_time_ms = db.Column(db.Float)
    status_code = db.Column(db.Integer)
    
    # Detailed results
    request_data_json = db.Column(db.Text)
    response_data_json = db.Column(db.Text)
    error_message = db.Column(db.Text)
    assertions_json = db.Column(db.Text)  # List of assertion results
    
    # Test metadata
    test_environment_json = db.Column(db.Text)
    test_config_json = db.Column(db.Text)
    tags_json = db.Column(db.Text)
    
    # Timestamps
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    
    def get_request_data(self) -> Dict[str, Any]:
        """Get request data as dictionary."""
        if self.request_data_json:
            try:
                return json.loads(self.request_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_request_data(self, data: Dict[str, Any]) -> None:
        """Set request data."""
        self.request_data_json = json.dumps(data)
    
    def get_response_data(self) -> Dict[str, Any]:
        """Get response data as dictionary."""
        if self.response_data_json:
            try:
                return json.loads(self.response_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_response_data(self, data: Dict[str, Any]) -> None:
        """Set response data."""
        self.response_data_json = json.dumps(data)
    
    def get_assertions(self) -> List[Dict[str, Any]]:
        """Get assertions as list."""
        if self.assertions_json:
            try:
                return json.loads(self.assertions_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_assertions(self, assertions: List[Dict[str, Any]]) -> None:
        """Set assertions."""
        self.assertions_json = json.dumps(assertions)
    
    def get_test_environment(self) -> Dict[str, Any]:
        """Get test environment as dictionary."""
        if self.test_environment_json:
            try:
                return json.loads(self.test_environment_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_test_environment(self, env: Dict[str, Any]) -> None:
        """Set test environment."""
        self.test_environment_json = json.dumps(env)
    
    def get_test_config(self) -> Dict[str, Any]:
        """Get test config as dictionary."""
        if self.test_config_json:
            try:
                return json.loads(self.test_config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_test_config(self, config: Dict[str, Any]) -> None:
        """Set test config."""
        self.test_config_json = json.dumps(config)
    
    def get_tags(self) -> List[str]:
        """Get tags as list."""
        if self.tags_json:
            try:
                return json.loads(self.tags_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags: List[str]) -> None:
        """Set tags."""
        self.tags_json = json.dumps(tags)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'result_id': self.result_id,
            'test_type': self.test_type,
            'test_name': self.test_name,
            'test_suite': self.test_suite,
            'target_url': self.target_url,
            'target_service': self.target_service,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'status': self.status,
            'response_time_ms': self.response_time_ms,
            'status_code': self.status_code,
            'request_data': self.get_request_data(),
            'response_data': self.get_response_data(),
            'error_message': self.error_message,
            'assertions': self.get_assertions(),
            'test_environment': self.get_test_environment(),
            'test_config': self.get_test_config(),
            'tags': self.get_tags(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f'<TestResults {self.test_name}:{self.status}>'


class EventLog(db.Model):
    """Store system events to replace gateway_events.jsonl."""
    __tablename__ = 'event_logs'
    
    # Primary identification
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Event information
    event_type = db.Column(db.String(50), nullable=False, index=True)  # gateway, analysis, system, user
    event_name = db.Column(db.String(100), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False, index=True)  # gateway, analyzer, web_ui, api
    
    # Event context
    user_id = db.Column(db.String(100))
    session_id = db.Column(db.String(100))
    request_id = db.Column(db.String(100))
    correlation_id = db.Column(db.String(100))
    
    # Event data
    message = db.Column(db.Text)
    event_data_json = db.Column(db.Text)
    event_metadata_json = db.Column(db.Text)
    
    # Severity and categorization
    severity = db.Column(db.String(20), default='info', index=True)  # debug, info, warning, error, critical
    category = db.Column(db.String(50), index=True)  # auth, analysis, system, performance, security
    
    # Context information
    ip_address = db.Column(db.String(45))  # IPv6 compatible
    user_agent = db.Column(db.String(500))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(500))
    
    # Performance data
    duration_ms = db.Column(db.Float)
    memory_usage_mb = db.Column(db.Float)
    
    # Timestamps
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    
    def get_event_data(self) -> Dict[str, Any]:
        """Get event data as dictionary."""
        if self.event_data_json:
            try:
                return json.loads(self.event_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_event_data(self, data: Dict[str, Any]) -> None:
        """Set event data."""
        self.event_data_json = json.dumps(data)
    
    def get_event_metadata(self) -> Dict[str, Any]:
        """Get event metadata as dictionary."""
        if self.event_metadata_json:
            try:
                return json.loads(self.event_metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_event_metadata(self, metadata: Dict[str, Any]) -> None:
        """Set event metadata."""
        self.event_metadata_json = json.dumps(metadata)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'event_id': self.event_id,
            'event_type': self.event_type,
            'event_name': self.event_name,
            'source': self.source,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'request_id': self.request_id,
            'correlation_id': self.correlation_id,
            'message': self.message,
            'event_data': self.get_event_data(),
            'metadata': self.get_event_metadata(),
            'severity': self.severity,
            'category': self.category,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'request_method': self.request_method,
            'request_path': self.request_path,
            'duration_ms': self.duration_ms,
            'memory_usage_mb': self.memory_usage_mb,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self) -> str:
        return f'<EventLog {self.event_type}:{self.event_name}>'


# =============================================================================
# ANALYSIS CONFIGURATION MODELS  
# =============================================================================

class AnalysisConfig(db.Model):
    """Model for storing analysis tool configurations."""
    __tablename__ = 'analysis_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    config_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, ai
    
    # Configuration data as JSON
    config_data = db.Column(db.Text, nullable=False)
    
    # Metadata
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    tags = db.Column(db.Text)  # JSON array of tags
    
    # Version tracking
    version = db.Column(db.String(20), default='1.0.0')
    parent_config_id = db.Column(db.Integer, db.ForeignKey('analysis_configs.id'), nullable=True)
    
    # Usage tracking
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime(timezone=True))
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    # Relationships
    child_configs = db.relationship('AnalysisConfig', 
                                  backref=db.backref('parent_config', remote_side=[id]),
                                  lazy=True)
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get configuration data as dictionary."""
        if self.config_data:
            try:
                return json.loads(self.config_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config_data(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration data from dictionary."""
        self.config_data = json.dumps(config_dict, indent=2)
    
    def get_tags(self) -> list:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: list) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used = utc_now()
    
    def create_child_config(self, name: str, description: str = "") -> 'AnalysisConfig':
        """Create a child configuration based on this one."""
        child = AnalysisConfig(
            name=name,
            description=description,
            config_type=self.config_type,
            config_data=self.config_data,
            parent_config_id=self.id,
            version="1.0.0"
        )
        return child
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config_type': self.config_type,
            'config_data': self.get_config_data(),
            'is_default': self.is_default,
            'is_active': self.is_active,
            'tags': self.get_tags(),
            'version': self.version,
            'parent_config_id': self.parent_config_id,
            'usage_count': self.usage_count,
            'last_used': self.last_used,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisConfig {self.name} ({self.config_type})>'


class ConfigPreset(db.Model):
    """Model for storing predefined configuration presets."""
    __tablename__ = 'config_presets'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False, index=True)  # quick_scan, comprehensive, etc.
    config_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, ai
    
    # Preset configuration
    preset_data = db.Column(db.Text, nullable=False)
    
    # Metadata
    is_system_preset = db.Column(db.Boolean, default=True)  # System vs user-created
    is_public = db.Column(db.Boolean, default=True)
    difficulty_level = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced
    estimated_duration = db.Column(db.Integer)  # Estimated runtime in minutes
    
    # Usage tracking
    usage_count = db.Column(db.Integer, default=0)
    rating_sum = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    def get_preset_data(self) -> Dict[str, Any]:
        """Get preset data as dictionary."""
        if self.preset_data:
            try:
                return json.loads(self.preset_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_preset_data(self, preset_dict: Dict[str, Any]) -> None:
        """Set preset data from dictionary."""
        self.preset_data = json.dumps(preset_dict, indent=2)
    
    def get_average_rating(self) -> float:
        """Get average rating."""
        if self.rating_count > 0:
            return self.rating_sum / self.rating_count
        return 0.0
    
    def add_rating(self, rating: int) -> None:
        """Add a rating (1-5)."""
        if 1 <= rating <= 5:
            self.rating_sum += rating
            self.rating_count += 1
    
    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1
    
    def to_config(self) -> AnalysisConfig:
        """Convert preset to an AnalysisConfig instance."""
        return AnalysisConfig(
            name=f"{self.name} (from preset)",
            description=self.description,
            config_type=self.config_type,
            config_data=self.preset_data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'config_type': self.config_type,
            'preset_data': self.get_preset_data(),
            'is_system_preset': self.is_system_preset,
            'is_public': self.is_public,
            'difficulty_level': self.difficulty_level,
            'estimated_duration': self.estimated_duration,
            'usage_count': self.usage_count,
            'average_rating': self.get_average_rating(),
            'rating_count': self.rating_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ConfigPreset {self.name} ({self.config_type})>'


# =============================================================================
# NEW ANALYSIS SYSTEM MODELS
# =============================================================================

class AnalyzerConfiguration(db.Model):
    """Configuration profiles for different analyzer types and tools."""
    __tablename__ = 'analyzer_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text)
    analyzer_type = db.Column(db.Enum(AnalysisType), nullable=False, index=True)
    
    # Configuration settings stored as JSON
    config_data = db.Column(db.Text, nullable=False)  # Tool-specific configuration
    template_config = db.Column(db.Text)  # Reusable template settings
    
    # Metadata and categorization
    is_active = db.Column(db.Boolean, default=True, index=True)
    is_default = db.Column(db.Boolean, default=False)
    tags = db.Column(db.Text)  # JSON array of tags
    category = db.Column(db.String(100))  # e.g., "quick-scan", "comprehensive"
    
    # Usage and performance metrics
    usage_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Float, default=0.0)  # Percentage of successful runs
    avg_execution_time = db.Column(db.Float, default=0.0)  # Average time in seconds
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_used = db.Column(db.DateTime(timezone=True))
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get configuration data as dictionary."""
        if self.config_data:
            try:
                return json.loads(self.config_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config_data(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration data from dictionary."""
        self.config_data = json.dumps(config_dict)
    
    def get_template_config(self) -> Dict[str, Any]:
        """Get template configuration as dictionary."""
        if self.template_config:
            try:
                return json.loads(self.template_config)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_template_config(self, template_dict: Dict[str, Any]) -> None:
        """Set template configuration from dictionary."""
        self.template_config = json.dumps(template_dict)
    
    def get_tags(self) -> List[str]:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: List[str]) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def update_metrics(self, execution_time: float, success: bool) -> None:
        """Update usage metrics."""
        self.usage_count += 1
        self.last_used = utc_now()
        
        # Update average execution time
        if self.usage_count == 1:
            self.avg_execution_time = execution_time
        else:
            self.avg_execution_time = ((self.avg_execution_time * (self.usage_count - 1)) + execution_time) / self.usage_count
        
        # Update success rate
        if success:
            successful_runs = (self.success_rate / 100.0) * (self.usage_count - 1) + 1
        else:
            successful_runs = (self.success_rate / 100.0) * (self.usage_count - 1)
        self.success_rate = (successful_runs / self.usage_count) * 100.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'analyzer_type': self.analyzer_type.value if self.analyzer_type else None,
            'config_data': self.get_config_data(),
            'template_config': self.get_template_config(),
            'is_active': self.is_active,
            'is_default': self.is_default,
            'tags': self.get_tags(),
            'category': self.category,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate,
            'avg_execution_time': self.avg_execution_time,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_used': self.last_used
        }
    
    def __repr__(self) -> str:
        return f'<AnalyzerConfiguration {self.name} ({self.analyzer_type.value if self.analyzer_type else "unknown"})>'


class AnalysisTask(db.Model):
    """Individual analysis task tracking and management."""
    __tablename__ = 'analysis_tasks'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Task configuration
    analyzer_config_id = db.Column(db.Integer, db.ForeignKey('analyzer_configurations.id'), nullable=False)
    analysis_type = db.Column(db.Enum(AnalysisType), nullable=False, index=True)
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    priority = db.Column(db.Enum(Priority), default=Priority.NORMAL, index=True)
    
    # Target application information
    target_model = db.Column(db.String(200), nullable=False, index=True)
    target_app_number = db.Column(db.Integer, nullable=False)
    target_path = db.Column(db.String(500))
    
    # Task metadata
    task_name = db.Column(db.String(200))
    description = db.Column(db.Text)
    task_metadata = db.Column(db.Text)  # JSON metadata
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    current_step = db.Column(db.String(200))
    total_steps = db.Column(db.Integer)
    completed_steps = db.Column(db.Integer, default=0)
    
    # Batch association
    batch_id = db.Column(db.String(100), index=True)  # Optional batch association
    
    # Execution details
    assigned_worker = db.Column(db.String(100))  # Worker/analyzer instance
    execution_context = db.Column(db.Text)  # JSON execution context
    
    # Results summary
    result_summary = db.Column(db.Text)  # JSON summary of findings
    issues_found = db.Column(db.Integer, default=0)
    severity_breakdown = db.Column(db.Text)  # JSON severity count breakdown
    
    # Timing and performance
    estimated_duration = db.Column(db.Integer)  # Estimated duration in seconds
    actual_duration = db.Column(db.Float)  # Actual duration in seconds
    queue_time = db.Column(db.Float)  # Time spent in queue
    
    # Error handling
    error_message = db.Column(db.Text)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    
    # Relationships
    analyzer_config = db.relationship('AnalyzerConfiguration', backref='tasks')
    results = db.relationship('AnalysisResult', backref='task', cascade='all, delete-orphan')
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.task_metadata:
            try:
                return json.loads(self.task_metadata)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.task_metadata = json.dumps(metadata_dict)
    
    def get_execution_context(self) -> Dict[str, Any]:
        """Get execution context as dictionary."""
        if self.execution_context:
            try:
                return json.loads(self.execution_context)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_execution_context(self, context_dict: Dict[str, Any]) -> None:
        """Set execution context from dictionary."""
        self.execution_context = json.dumps(context_dict)
    
    def get_result_summary(self) -> Dict[str, Any]:
        """Get result summary as dictionary."""
        if self.result_summary:
            try:
                return json.loads(self.result_summary)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_result_summary(self, summary_dict: Dict[str, Any]) -> None:
        """Set result summary from dictionary."""
        self.result_summary = json.dumps(summary_dict)
    
    def get_severity_breakdown(self) -> Dict[str, int]:
        """Get severity breakdown as dictionary."""
        if self.severity_breakdown:
            try:
                return json.loads(self.severity_breakdown)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_severity_breakdown(self, breakdown_dict: Dict[str, int]) -> None:
        """Set severity breakdown from dictionary."""
        self.severity_breakdown = json.dumps(breakdown_dict)
    
    def update_progress(self, percentage: float, current_step: str = None) -> None:
        """Update task progress."""
        self.progress_percentage = min(100.0, max(0.0, percentage))
        if current_step:
            self.current_step = current_step
        self.updated_at = utc_now()
    
    def start_execution(self, worker: str = None) -> None:
        """Mark task as started."""
        self.status = AnalysisStatus.RUNNING
        self.started_at = utc_now()
        if worker:
            self.assigned_worker = worker
    
    def complete_execution(self, success: bool = True, error_message: str = None) -> None:
        """Mark task as completed or failed."""
        self.completed_at = utc_now()
        if success:
            self.status = AnalysisStatus.COMPLETED
            self.progress_percentage = 100.0
        else:
            self.status = AnalysisStatus.FAILED
            if error_message:
                self.error_message = error_message
        
        # Calculate actual duration
        if self.started_at:
            self.actual_duration = (self.completed_at - self.started_at).total_seconds()
    
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.retry_count < self.max_retries and self.status == AnalysisStatus.FAILED
    
    def retry(self) -> None:
        """Retry the task."""
        if self.can_retry():
            self.retry_count += 1
            self.status = AnalysisStatus.PENDING
            self.error_message = None
            self.started_at = None
            self.completed_at = None
            self.progress_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'task_id': self.task_id,
            'analyzer_config_id': self.analyzer_config_id,
            'analysis_type': self.analysis_type.value if self.analysis_type else None,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'target_model': self.target_model,
            'target_app_number': self.target_app_number,
            'target_path': self.target_path,
            'task_name': self.task_name,
            'description': self.description,
            'metadata': self.get_metadata(),
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'batch_id': self.batch_id,
            'assigned_worker': self.assigned_worker,
            'execution_context': self.get_execution_context(),
            'result_summary': self.get_result_summary(),
            'issues_found': self.issues_found,
            'severity_breakdown': self.get_severity_breakdown(),
            'estimated_duration': self.estimated_duration,
            'actual_duration': self.actual_duration,
            'queue_time': self.queue_time,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'started_at': self.started_at,
            'completed_at': self.completed_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisTask {self.task_id} ({self.analysis_type.value if self.analysis_type else "unknown"})>'


class AnalysisResult(db.Model):
    """Detailed analysis results and findings."""
    __tablename__ = 'analysis_results'
    
    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Association with task
    task_id = db.Column(db.String(100), db.ForeignKey('analysis_tasks.task_id'), nullable=False, index=True)
    
    # Result metadata
    tool_name = db.Column(db.String(100), nullable=False)  # Specific tool that generated result
    tool_version = db.Column(db.String(50))
    result_type = db.Column(db.String(50), nullable=False)  # finding, metric, summary, etc.
    
    # Finding details
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    severity = db.Column(db.Enum(SeverityLevel), nullable=False, index=True)
    confidence = db.Column(db.String(20))  # low, medium, high
    
    # Location information
    file_path = db.Column(db.String(1000))
    line_number = db.Column(db.Integer)
    column_number = db.Column(db.Integer)
    code_snippet = db.Column(db.Text)
    
    # Classification
    category = db.Column(db.String(100))  # security, performance, quality, etc.
    rule_id = db.Column(db.String(100))   # Tool-specific rule identifier
    tags = db.Column(db.Text)  # JSON array of tags
    
    # Detailed data
    raw_output = db.Column(db.Text)  # Raw tool output
    structured_data = db.Column(db.Text)  # JSON structured finding data
    recommendations = db.Column(db.Text)  # JSON array of recommendations
    
    # Impact and priority
    impact_score = db.Column(db.Float)  # 0-10 impact score
    business_impact = db.Column(db.String(20))  # low, medium, high, critical
    remediation_effort = db.Column(db.String(20))  # low, medium, high
    
    # Status tracking
    status = db.Column(db.String(20), default='new')  # new, reviewed, resolved, false_positive
    reviewed_by = db.Column(db.String(100))
    review_notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    reviewed_at = db.Column(db.DateTime(timezone=True))
    
    def get_structured_data(self) -> Dict[str, Any]:
        """Get structured data as dictionary."""
        if self.structured_data:
            try:
                return json.loads(self.structured_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_structured_data(self, data_dict: Dict[str, Any]) -> None:
        """Set structured data from dictionary."""
        self.structured_data = json.dumps(data_dict)
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations as list."""
        if self.recommendations:
            try:
                return json.loads(self.recommendations)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_recommendations(self, recommendations_list: List[str]) -> None:
        """Set recommendations from list."""
        self.recommendations = json.dumps(recommendations_list)
    
    def get_tags(self) -> List[str]:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: List[str]) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def mark_reviewed(self, reviewer: str, notes: str = None) -> None:
        """Mark result as reviewed."""
        self.status = 'reviewed'
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        if notes:
            self.review_notes = notes
    
    def mark_false_positive(self, reviewer: str, notes: str = None) -> None:
        """Mark result as false positive."""
        self.status = 'false_positive'
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        if notes:
            self.review_notes = notes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'result_id': self.result_id,
            'task_id': self.task_id,
            'tool_name': self.tool_name,
            'tool_version': self.tool_version,
            'result_type': self.result_type,
            'title': self.title,
            'description': self.description,
            'severity': self.severity.value if self.severity else None,
            'confidence': self.confidence,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column_number': self.column_number,
            'code_snippet': self.code_snippet,
            'category': self.category,
            'rule_id': self.rule_id,
            'tags': self.get_tags(),
            'raw_output': self.raw_output,
            'structured_data': self.get_structured_data(),
            'recommendations': self.get_recommendations(),
            'impact_score': self.impact_score,
            'business_impact': self.business_impact,
            'remediation_effort': self.remediation_effort,
            'status': self.status,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'reviewed_at': self.reviewed_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisResult {self.result_id} ({self.tool_name})>'


# Initialize database function
def init_db():
    """Create all database tables."""
    # Ensure models are imported before creating tables to avoid missing-table errors
    try:
        import app.models as _models  # noqa: F401
    except Exception:
        pass
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
    'ConfigPreset',
    'BatchQueue',
    'BatchDependency',
    'BatchSchedule',
    'BatchResourceUsage',
    'BatchTemplate',
    'ProcessTracking',
    'TestResults',
    'EventLog',
    # New Analysis System Models
    'AnalyzerConfiguration',
    'AnalysisTask',
    'AnalysisResult'
]
