"""
Analyzer Configuration Service
=============================

Service for managing and validating analyzer configurations.
Provides methods to get, set, and validate configuration options
for security, performance, and AI analysis tools.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import json

from ..extensions import db
from ..models.analysis import AnalysisConfig


@dataclass
class BanditConfig:
    """Configuration for Bandit security scanner."""
    enabled: bool = True
    confidence_level: str = "HIGH"  # LOW, MEDIUM, HIGH
    severity_level: str = "LOW"     # LOW, MEDIUM, HIGH
    exclude_paths: List[str] = None
    skipped_tests: List[str] = None
    formats: List[str] = None
    baseline_file: Optional[str] = None
    timeout: int = 300
    
    def __post_init__(self):
        if self.exclude_paths is None:
            self.exclude_paths = [
                '*/tests/*', '*/test_*', '*/migrations/*', 
                '*/venv/*', '*/node_modules/*'
            ]
        if self.skipped_tests is None:
            self.skipped_tests = ['B101', 'B601']
        if self.formats is None:
            self.formats = ['json', 'txt']


@dataclass
class SafetyConfig:
    """Configuration for Safety dependency scanner."""
    enabled: bool = True
    database_path: Optional[str] = None
    ignore_ids: List[str] = None
    output_format: str = "json"
    check_unpinned: bool = True
    timeout: int = 180
    
    def __post_init__(self):
        if self.ignore_ids is None:
            self.ignore_ids = []


@dataclass
class PylintConfig:
    """Configuration for Pylint code quality scanner."""
    enabled: bool = True
    rcfile: Optional[str] = None
    disable: List[str] = None
    enable: List[str] = None
    output_format: str = "json"
    confidence: str = "HIGH"
    timeout: int = 300
    
    def __post_init__(self):
        if self.disable is None:
            self.disable = ['C0103', 'R0903', 'W0613']
        if self.enable is None:
            self.enable = ['W0622']


@dataclass
class ESLintConfig:
    """Configuration for ESLint JavaScript security scanner."""
    enabled: bool = True
    config_file: Optional[str] = None
    rules: Dict[str, str] = None
    plugins: List[str] = None
    output_format: str = "json"
    max_warnings: int = 50
    timeout: int = 240
    
    def __post_init__(self):
        if self.rules is None:
            self.rules = {
                'security/detect-object-injection': 'error',
                'security/detect-non-literal-fs-filename': 'error',
                'security/detect-unsafe-regex': 'error',
                'security/detect-buffer-noassert': 'error',
                'security/detect-eval-with-expression': 'error',
                'security/detect-no-csrf-before-method-override': 'error',
                'security/detect-pseudoRandomBytes': 'error'
            }
        if self.plugins is None:
            self.plugins = ['security']


@dataclass
class ZAPConfig:
    """Configuration for OWASP ZAP web application scanner."""
    enabled: bool = True
    api_key: Optional[str] = None
    daemon_mode: bool = True
    host: str = "localhost"
    port: int = 8080
    scan_types: Dict[str, Any] = None
    authentication: Dict[str, Any] = None
    context: Dict[str, Any] = None
    reporting: Dict[str, Any] = None
    timeout: int = 3600
    
    def __post_init__(self):
        if self.scan_types is None:
            self.scan_types = {
                'spider': {
                    'enabled': True,
                    'max_depth': 5,
                    'max_duration': 600,
                    'user_agent': 'ZAP/2.14.0'
                },
                'active_scan': {
                    'enabled': True,
                    'policy': 'Default Policy',
                    'max_duration': 1800,
                    'max_rule_duration': 300,
                    'delay_in_ms': 0
                },
                'passive_scan': {
                    'enabled': True,
                    'max_alerts_per_rule': 10
                }
            }
        if self.authentication is None:
            self.authentication = {
                'method': 'form',
                'login_url': None,
                'username_field': 'username',
                'password_field': 'password',
                'username': None,
                'password': None,
                'logged_in_regex': None,
                'logged_out_regex': None
            }
        if self.context is None:
            self.context = {
                'name': 'Default Context',
                'include_urls': ['.*'],
                'exclude_urls': ['.*logout.*', '.*signout.*', '.*admin.*']
            }
        if self.reporting is None:
            self.reporting = {
                'formats': ['json', 'html', 'xml'],
                'include_passed': False,
                'confidence_threshold': 'Medium',
                'risk_threshold': 'Low'
            }


@dataclass
class SecurityAnalyzerConfig:
    """Complete security analyzer configuration."""
    bandit: BanditConfig = None
    safety: SafetyConfig = None
    pylint: PylintConfig = None
    eslint: ESLintConfig = None
    zap: ZAPConfig = None
    
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


class AnalyzerConfigService:
    """Service for managing analyzer configurations."""
    
    def __init__(self):
        self.default_config = SecurityAnalyzerConfig()
    
    def get_security_config(self, config_id: Optional[int] = None) -> SecurityAnalyzerConfig:
        """Get security analyzer configuration."""
        if config_id:
            config_record = AnalysisConfig.query.get(config_id)
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
        if config.bandit.timeout < 30 or config.bandit.timeout > 3600:
            errors.append("Bandit timeout must be between 30 and 3600 seconds")
        
        if config.safety.timeout < 30 or config.safety.timeout > 1800:
            errors.append("Safety timeout must be between 30 and 1800 seconds")
        
        if config.pylint.timeout < 30 or config.pylint.timeout > 3600:
            errors.append("Pylint timeout must be between 30 and 3600 seconds")
        
        if config.eslint.timeout < 30 or config.eslint.timeout > 1800:
            errors.append("ESLint timeout must be between 30 and 1800 seconds")
        
        if config.zap.timeout < 300 or config.zap.timeout > 7200:
            errors.append("ZAP timeout must be between 300 and 7200 seconds")
        
        # Validate confidence levels
        valid_confidence = ['LOW', 'MEDIUM', 'HIGH']
        if config.bandit.confidence_level not in valid_confidence:
            errors.append(f"Bandit confidence level must be one of: {valid_confidence}")
        
        if config.bandit.severity_level not in valid_confidence:
            errors.append(f"Bandit severity level must be one of: {valid_confidence}")
        
        # Validate ZAP port
        if config.zap.port < 1024 or config.zap.port > 65535:
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
