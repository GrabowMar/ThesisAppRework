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

class ConfigManager:
    """Centralized configuration manager."""
    
    def __init__(self, config_dir: Optional[str] = None):
        self.config_dir = Path(config_dir or 'src/config')
        self._analyzer_config: Optional[AnalyzerConfig] = None
        self._load_configs()
    
    def _load_configs(self):
        """Load all configuration files."""
        try:
            # Load analyzer configuration
            analyzer_config_path = self.config_dir / 'analyzer_config.json'
            if analyzer_config_path.exists():
                with open(analyzer_config_path) as f:
                    analyzer_data = json.load(f)
                self._analyzer_config = self._parse_analyzer_config(analyzer_data)
            else:
                # Fallback to defaults if config file doesn't exist
                self._analyzer_config = self._get_default_analyzer_config()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Could not load configuration: {e}")
            self._analyzer_config = self._get_default_analyzer_config()
    
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
    
    @property
    def analyzer(self) -> AnalyzerConfig:
        """Get analyzer configuration."""
        if self._analyzer_config is None:
            self._analyzer_config = self._get_default_analyzer_config()
        return self._analyzer_config
    
    def get_analyzer_service_url(self, service_type: str) -> str:
        """Get WebSocket URL for analyzer service."""
        service = self.analyzer.services.get(service_type)
        if service:
            return service.websocket_url
        
        # Fallback for unknown service types
        base_service = self.analyzer.services.get('static')
        if base_service:
            return base_service.websocket_url
        
        return "ws://localhost:2001"  # Ultimate fallback
    
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