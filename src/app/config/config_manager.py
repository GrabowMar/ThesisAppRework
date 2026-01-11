"""
Centralized Configuration Manager
=================================

Manages all configuration for the thesis application, replacing hardcoded values
with configurable settings from JSON files and environment variables.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class AnalyzerServiceConfig:
    """Configuration for analyzer services."""
    host: str
    port: int
    name: str
    websocket_url: str

@dataclass
class AnalyzerConfig:
    """Complete analyzer configuration."""
    services: Dict[str, AnalyzerServiceConfig]
    source_mount: str
    local_generated: str
    results_dir: str
    default_tools: Dict[str, List[str]]
    valid_tools: Dict[str, List[str]]
    timeouts: Dict[str, int]


@dataclass
class GenerationSettings:
    """Configuration for code generation behavior.
    
    Controls token limits, validation strictness, and retry behavior
    to improve generation success rate and cross-model comparison fairness.
    """
    # Token limit mode: 'uniform' uses same limit for all models, 'model_specific' uses per-model limits
    token_limit_mode: str = 'uniform'
    # Token limit when using uniform mode
    uniform_token_limit: int = 32000
    # Whether validation is enabled (syntax and structure checks)
    validation_enabled: bool = True
    # Validation strictness: 'strict' fails on missing patterns, 'lenient' only logs warnings
    validation_strictness: str = 'strict'
    # Whether to retry when truncation is detected
    retry_on_truncation: bool = True
    # Maximum retries for truncation
    max_truncation_retries: int = 2
    # Whether to retry when validation fails
    retry_on_validation_failure: bool = True
    # Maximum retries for validation failures
    max_validation_retries: int = 3
    # Default temperature for generation
    temperature: float = 0.3
    # Whether to track generation metrics
    enable_metrics_tracking: bool = True
    # Per-model token limits (used when token_limit_mode='model_specific')
    model_token_limits: Dict[str, int] = None
    # Validation rules for each query type
    validation_rules: Dict[str, Any] = None
    # Truncation detection settings
    truncation_threshold_percentage: int = 90
    truncation_token_reduction_factor: float = 0.8
    
    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.model_token_limits is None:
            self.model_token_limits = {}
        if self.validation_rules is None:
            self.validation_rules = {}
    
    def get_token_limit(self, model_slug: str) -> int:
        """Get token limit for a model based on current mode.
        
        Args:
            model_slug: The model identifier (e.g., 'openai/gpt-4o')
            
        Returns:
            Token limit to use for this model
        """
        if self.token_limit_mode == 'uniform':
            return self.uniform_token_limit
        
        # Model-specific mode - look up limit
        # Try exact match first
        if model_slug in self.model_token_limits:
            return self.model_token_limits[model_slug]
        
        # Try lowercase match
        model_lower = model_slug.lower()
        for key, limit in self.model_token_limits.items():
            if key.lower() == model_lower:
                return limit
        
        # Try partial match (provider/model-name pattern)
        for key, limit in self.model_token_limits.items():
            if model_lower.startswith(key.lower().split('/')[0]):
                return limit
        
        # Fallback to default
        return self.model_token_limits.get('default', 32000)
    
    def get_validation_rules(self, generation_mode: str, query_type: str) -> Dict[str, Any]:
        """Get validation rules for a specific generation mode and query type.
        
        Args:
            generation_mode: 'guarded' or 'unguarded'
            query_type: For guarded: 'backend_user', 'backend_admin', 'frontend_user', 'frontend_admin'
                       For unguarded: 'backend', 'frontend'
        
        Returns:
            Dictionary with validation rules (required_files, forbidden_patterns, etc.)
        """
        mode_rules = self.validation_rules.get(generation_mode, {})
        return mode_rules.get(query_type, {})

class ConfigManager:
    """Centralized configuration manager."""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or 'src/config')
        self._analyzer_config: Optional[AnalyzerConfig] = None
        self._generation_config: Optional[GenerationSettings] = None
        self._load_configs()
    
    def _load_configs(self):
        """Load all configuration files."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Load analyzer configuration
        try:
            analyzer_config_path = self.config_dir / 'analyzer_config.json'
            if analyzer_config_path.exists():
                with open(analyzer_config_path) as f:
                    analyzer_data = json.load(f)
                self._analyzer_config = self._parse_analyzer_config(analyzer_data)
            else:
                # Fallback to defaults if config file doesn't exist
                self._analyzer_config = self._get_default_analyzer_config()
        except Exception as e:
            logger.warning(f"Could not load analyzer configuration: {e}")
            self._analyzer_config = self._get_default_analyzer_config()
        
        # Load generation configuration
        try:
            generation_config_path = self.config_dir / 'generation_config.json'
            if generation_config_path.exists():
                with open(generation_config_path) as f:
                    generation_data = json.load(f)
                self._generation_config = self._parse_generation_config(generation_data)
                logger.info(f"Loaded generation config: token_limit_mode={self._generation_config.token_limit_mode}, "
                           f"validation_strictness={self._generation_config.validation_strictness}")
            else:
                # Fallback to defaults if config file doesn't exist
                self._generation_config = self._get_default_generation_config()
                logger.info("Using default generation configuration")
        except Exception as e:
            logger.warning(f"Could not load generation configuration: {e}")
            self._generation_config = self._get_default_generation_config()
    
    def _parse_analyzer_config(self, data: Dict[str, Any]) -> AnalyzerConfig:
        """Parse analyzer configuration from JSON data."""
        services_data = data.get('analyzer_services', {})
        host = services_data.get('host', 'localhost')
        
        services = {}
        for service_type, service_info in services_data.get('services', {}).items():
            port = service_info.get('port', 2001)
            name = service_info.get('name', f'{service_type}-analyzer')
            websocket_url = f"ws://{host}:{port}"
            
            services[service_type] = AnalyzerServiceConfig(
                host=host,
                port=port,
                name=name,
                websocket_url=websocket_url
            )
        
        paths = data.get('analyzer_paths', {})
        tools = data.get('default_tools', {})
        valid_tools = data.get('valid_tools', {})
        timeouts = data.get('analysis_timeouts', {})
        
        return AnalyzerConfig(
            services=services,
            source_mount=paths.get('source_mount', '/app/sources'),
            local_generated=paths.get('local_generated', 'generated/apps'),
            results_dir=paths.get('results_dir', 'results'),
            default_tools=tools,
            valid_tools=valid_tools,
            timeouts=timeouts
        )
    
    def _get_default_analyzer_config(self) -> AnalyzerConfig:
        """Get default analyzer configuration as fallback."""
        host = os.environ.get('ANALYZER_HOST', 'localhost')
        base_port = int(os.environ.get('ANALYZER_BASE_PORT', '2001'))
        
        services = {
            'static': AnalyzerServiceConfig(
                host=host, port=base_port, name='static-analyzer',
                websocket_url=f"ws://{host}:{base_port}"
            ),
            'security': AnalyzerServiceConfig(
                host=host, port=base_port, name='static-analyzer',  # Security uses static service
                websocket_url=f"ws://{host}:{base_port}"
            ),
            'dynamic': AnalyzerServiceConfig(
                host=host, port=base_port + 1, name='dynamic-analyzer',
                websocket_url=f"ws://{host}:{base_port + 1}"
            ),
            'performance': AnalyzerServiceConfig(
                host=host, port=base_port + 2, name='performance-tester',
                websocket_url=f"ws://{host}:{base_port + 2}"
            ),
            'ai': AnalyzerServiceConfig(
                host=host, port=base_port + 3, name='ai-analyzer',
                websocket_url=f"ws://{host}:{base_port + 3}"
            ),
        }
        
        return AnalyzerConfig(
            services=services,
            source_mount=os.environ.get('ANALYZER_SOURCE_MOUNT', '/app/sources'),
            local_generated=os.environ.get('LOCAL_GENERATED_PATH', 'generated/apps'),
            results_dir=os.environ.get('ANALYZER_RESULTS_DIR', 'results'),
            default_tools={
                'security': ['bandit', 'safety', 'pylint'],
                'static': ['pylint', 'mypy', 'flake8'],
                'performance': ['ab', 'wrk'],
                'dynamic': ['selenium', 'playwright']
            },
            valid_tools={
                'all': ['bandit', 'safety', 'pylint', 'eslint', 'npm_audit', 'semgrep', 'snyk', 'mypy', 'flake8', 'ab', 'wrk', 'selenium', 'playwright'],
                'security': ['bandit', 'safety', 'pylint', 'eslint', 'npm_audit', 'semgrep', 'snyk'],
                'static': ['pylint', 'mypy', 'flake8', 'eslint'],
                'performance': ['ab', 'wrk'],
                'dynamic': ['selenium', 'playwright']
            },
            timeouts={
                'default': 300,
                'security': 600,
                'performance': 900,
                'dynamic': 1200
            }
        )
    
    def _parse_generation_config(self, data: Dict[str, Any]) -> GenerationSettings:
        """Parse generation configuration from JSON data."""
        settings = data.get('generation_settings', {})
        model_limits = data.get('model_token_limits', {})
        validation_rules = data.get('validation_rules', {})
        truncation = data.get('truncation_detection', {})
        
        return GenerationSettings(
            token_limit_mode=settings.get('token_limit_mode', 'uniform'),
            uniform_token_limit=settings.get('uniform_token_limit', 32000),
            validation_strictness=settings.get('validation_strictness', 'strict'),
            retry_on_truncation=settings.get('retry_on_truncation', True),
            max_truncation_retries=settings.get('max_truncation_retries', 2),
            retry_on_validation_failure=settings.get('retry_on_validation_failure', True),
            max_validation_retries=settings.get('max_validation_retries', 3),
            temperature=settings.get('temperature', 0.3),
            enable_metrics_tracking=settings.get('enable_metrics_tracking', True),
            model_token_limits=model_limits,
            validation_rules=validation_rules,
            truncation_threshold_percentage=truncation.get('threshold_percentage', 90),
            truncation_token_reduction_factor=truncation.get('token_reduction_factor', 0.8)
        )
    
    def _get_default_generation_config(self) -> GenerationSettings:
        """Get default generation configuration as fallback."""
        # Allow environment variable overrides for key settings
        token_mode = os.environ.get('GENERATION_TOKEN_LIMIT_MODE', 'uniform')
        uniform_limit = int(os.environ.get('GENERATION_UNIFORM_TOKEN_LIMIT', '32000'))
        validation = os.environ.get('GENERATION_VALIDATION_STRICTNESS', 'strict')
        temperature = float(os.environ.get('GENERATION_TEMPERATURE', '0.3'))
        
        # Default model token limits (used in model_specific mode)
        default_model_limits = {
            'default': 32000,
            'openai/gpt-4o': 32768,
            'openai/gpt-4-turbo': 32768,
            'anthropic/claude-3-opus': 16384,
            'anthropic/claude-3-sonnet': 16384,
            'anthropic/claude-3-5-sonnet': 16384,
            'google/gemini-pro': 16384,
            'google/gemini-2.0-flash': 65536,
            'deepseek/deepseek-coder': 16384,
            'meta-llama/llama-3.1-70b': 16384,
        }
        
        # Default validation rules for guarded mode
        default_validation_rules = {
            'guarded': {
                'backend_user': {
                    'required_files': ['models.py', 'services.py', 'routes/user.py'],
                    'required_patterns': ['class.*Model', 'def '],
                    'forbidden_patterns': []
                },
                'backend_admin': {
                    'required_files': ['routes/admin.py'],
                    'required_patterns': ['def '],
                    'forbidden_patterns': []
                },
                'frontend_user': {
                    'required_files': ['pages/UserPage.jsx'],
                    'required_patterns': ['export', 'function.*\\(', 'return.*<'],
                    'forbidden_patterns': []
                },
                'frontend_admin': {
                    'required_files': ['pages/AdminPage.jsx'],
                    'required_patterns': ['export', 'function.*\\(', 'return.*<'],
                    'forbidden_patterns': []
                }
            },
            'unguarded': {
                'backend': {
                    'required_files': ['app.py'],
                    'required_patterns': ['Flask', 'def '],
                    'forbidden_files': ['routes/', 'services.py', 'models.py'],
                    'forbidden_patterns': ['from routes import', 'from services import']
                },
                'frontend': {
                    'required_files': ['App.jsx'],
                    'required_patterns': ['export', 'function'],
                    'forbidden_files': ['pages/', 'hooks/'],
                    'forbidden_patterns': ['import.*from.*pages', 'import.*from.*hooks']
                }
            }
        }
        
        return GenerationSettings(
            token_limit_mode=token_mode,
            uniform_token_limit=uniform_limit,
            validation_strictness=validation,
            retry_on_truncation=True,
            max_truncation_retries=2,
            retry_on_validation_failure=True,
            max_validation_retries=3,
            temperature=temperature,
            enable_metrics_tracking=True,
            model_token_limits=default_model_limits,
            validation_rules=default_validation_rules,
            truncation_threshold_percentage=90,
            truncation_token_reduction_factor=0.8
        )
    
    def get_queue_config(self) -> Dict[str, int]:
        """Get queue concurrency configuration from environment.
        
        Returns:
            Dictionary with queue limits (max_concurrent_tasks, max_concurrent_per_type)
        """
        return {
            'max_concurrent_tasks': int(os.environ.get('QUEUE_MAX_CONCURRENT_TASKS', '10')),
            'max_concurrent_per_type': int(os.environ.get('QUEUE_MAX_CONCURRENT_PER_TYPE', '5'))
        }
    
    @property
    def analyzer(self) -> AnalyzerConfig:
        """Get analyzer configuration."""
        if self._analyzer_config is None:
            self._analyzer_config = self._get_default_analyzer_config()
        return self._analyzer_config
    
    @property
    def generation(self) -> GenerationSettings:
        """Get generation configuration."""
        if self._generation_config is None:
            self._generation_config = self._get_default_generation_config()
        return self._generation_config
    
    def get_analyzer_service_url(self, service_type: str) -> str:
        """Get WebSocket URL for analyzer service."""
        service = self.analyzer.services.get(service_type)
        if service:
            return service.websocket_url
        
        # Fallback for unknown service types
        base_service = self.analyzer.services.get('static')
        if base_service:
            return base_service.websocket_url
        
        # Ultimate fallback - respect ANALYZER_HOST env var for Docker networking
        fallback_host = os.environ.get('ANALYZER_HOST', 'localhost')
        return f"ws://{fallback_host}:2001"
    
    def get_default_tools(self, analysis_type: str) -> List[str]:
        """Get default tools for analysis type."""
        return self.analyzer.default_tools.get(analysis_type, ['bandit', 'safety', 'pylint'])
    
    def get_valid_tools(self, analysis_type: Optional[str] = None) -> List[str]:
        """Get valid tools for analysis type, or all valid tools if no type specified."""
        if analysis_type is None:
            return self.analyzer.valid_tools.get('all', ['bandit', 'safety', 'pylint', 'eslint', 'npm_audit', 'semgrep', 'snyk'])
        return self.analyzer.valid_tools.get(analysis_type, ['bandit', 'safety', 'pylint'])
    
    def get_analysis_timeout(self, analysis_type: str) -> int:
        """Get timeout for analysis type."""
        return self.analyzer.timeouts.get(analysis_type, self.analyzer.timeouts.get('default', 300))
    
    def get_source_path(self, model_slug: str, app_number: int) -> str:
        """Get source path for model and app."""
        return f"{self.analyzer.source_mount}/{model_slug}/app{app_number}"
    
    def get_local_app_path(self, model_slug: str, app_number: int) -> Path:
        """Get local path to generated app."""
        return Path(self.analyzer.local_generated) / model_slug / f"app{app_number}"

# Global configuration instance
_config_manager: Optional[ConfigManager] = None

def get_config() -> ConfigManager:
    """Get global configuration manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager

def reload_config():
    """Reload configuration from files."""
    global _config_manager
    _config_manager = None
    _config_manager = ConfigManager()