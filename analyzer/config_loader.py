#!/usr/bin/env python3
"""
Configuration Loader for Analyzer Services
==========================================

Dynamically loads and merges configuration files for analyzer tools.
Supports YAML, JSON, TOML, and INI formats with runtime override capability.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import logging

logger = logging.getLogger(__name__)

# Try to import optional parsers
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    logger.debug("PyYAML not installed, YAML configs will use fallback parsing")

try:
    import tomllib  # Python 3.11+
    TOML_AVAILABLE = True
except ImportError:
    try:
        import tomli as tomllib
        TOML_AVAILABLE = True
    except ImportError:
        TOML_AVAILABLE = False
        logger.debug("TOML parser not available")

try:
    import configparser
    INI_AVAILABLE = True
except ImportError:
    INI_AVAILABLE = False


class ConfigLoader:
    """
    Configuration loader with multi-format support and override capability.
    
    Priority (highest to lowest):
    1. Runtime overrides (passed via API/wizard)
    2. Custom config file path
    3. Default config files in configs/ folder
    4. Hardcoded fallback defaults
    """
    
    # Base path for config files (relative to analyzer root)
    CONFIG_BASE_PATH = Path(__file__).parent / "configs"
    
    # Fallback defaults for critical settings
    FALLBACK_DEFAULTS = {
        "semgrep": {
            "rulesets": ["p/security-audit", "p/python", "p/javascript"],
            "severity_threshold": "INFO",
            "timeout": 300
        },
        "mypy": {
            "strict": True,
            "ignore_missing_imports": True,
            "show_error_codes": True,
            "max_files": 20
        },
        "ruff": {
            "select": ["E", "F", "W", "I", "S", "B"],
            "line_length": 100
        },
        "eslint": {
            "enabled": True,
            "security_rules": True
        },
        "bandit": {
            "skips": ["B101"],
            "severity": "LOW",
            "confidence": "MEDIUM"
        },
        "vulture": {
            "min_confidence": 60
        },
        "zap": {
            "spider_depth": 10,
            "passive_scan_wait": 30,
            "ajax_spider_enabled": True,
            "scan_type": "baseline"
        },
        "nmap": {
            "service_detection": True,
            "scripts": ["vuln", "http-headers", "http-security-headers"],
            "timing_template": 4
        }
    }
    
    def __init__(self, config_base_path: Optional[Path] = None):
        """
        Initialize config loader.
        
        Args:
            config_base_path: Override base path for config files
        """
        self.config_base_path = config_base_path or self.CONFIG_BASE_PATH
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ensure_config_path()
    
    def _ensure_config_path(self):
        """Ensure config directory exists."""
        if not self.config_base_path.exists():
            logger.warning(f"Config path does not exist: {self.config_base_path}")
    
    def load_config(
        self,
        tool_name: str,
        category: str = "static",
        runtime_override: Optional[Dict[str, Any]] = None,
        custom_config_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        """
        Load configuration for a tool with override support.
        
        Args:
            tool_name: Name of the tool (e.g., 'semgrep', 'mypy', 'zap')
            category: Tool category ('static', 'dynamic', 'performance')
            runtime_override: Runtime configuration overrides from API/wizard
            custom_config_path: Path to custom config file
            
        Returns:
            Merged configuration dictionary
        """
        # Start with fallback defaults
        config = self.FALLBACK_DEFAULTS.get(tool_name, {}).copy()
        
        # Load default config file
        default_config = self._load_default_config(tool_name, category)
        if default_config:
            config = self._deep_merge(config, default_config)
        
        # Apply custom config file if specified
        if custom_config_path:
            custom_config = self._load_file(Path(custom_config_path))
            if custom_config:
                config = self._deep_merge(config, custom_config)
        
        # Apply runtime overrides (highest priority)
        if runtime_override:
            config = self._deep_merge(config, runtime_override)
        
        return config
    
    def _load_default_config(self, tool_name: str, category: str) -> Optional[Dict[str, Any]]:
        """Load default config file for a tool."""
        # Try different file extensions
        for ext in ['.yaml', '.yml', '.json', '.toml', '.ini']:
            config_path = self.config_base_path / category / f"{tool_name}{ext}"
            if config_path.exists():
                return self._load_file(config_path)
        
        # Check for config in defaults.json registry
        defaults_path = self.config_base_path / "defaults.json"
        if defaults_path.exists():
            try:
                with open(defaults_path, 'r') as f:
                    defaults = json.load(f)
                    tool_registry = defaults.get('tool_registry', {})
                    tool_info = tool_registry.get(category, {}).get(tool_name, {})
                    if tool_info.get('config_file'):
                        config_file_path = self.config_base_path / tool_info['config_file']
                        if config_file_path.exists():
                            return self._load_file(config_file_path)
            except Exception as e:
                logger.warning(f"Could not load defaults.json: {e}")
        
        return None
    
    def _load_file(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load a configuration file based on its extension."""
        try:
            suffix = path.suffix.lower()
            
            if suffix in ['.yaml', '.yml']:
                return self._load_yaml(path)
            elif suffix == '.json':
                return self._load_json(path)
            elif suffix == '.toml':
                return self._load_toml(path)
            elif suffix == '.ini':
                return self._load_ini(path)
            else:
                logger.warning(f"Unknown config file format: {suffix}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to load config file {path}: {e}")
            return None
    
    def _load_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load YAML configuration file."""
        if YAML_AVAILABLE:
            with open(path, 'r') as f:
                return yaml.safe_load(f)
        else:
            # Fallback: try to parse simple YAML-like format
            logger.warning(f"PyYAML not available, attempting basic parsing for {path}")
            return self._parse_simple_yaml(path)
    
    def _parse_simple_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Basic YAML parsing for simple key-value configs."""
        result = {}
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' in line:
                        key, value = line.split(':', 1)
                        key = key.strip()
                        value = value.strip()
                        # Basic type conversion
                        if value.lower() in ('true', 'yes'):
                            value = True
                        elif value.lower() in ('false', 'no'):
                            value = False
                        elif value.isdigit():
                            value = int(value)
                        result[key] = value
            return result
        except Exception as e:
            logger.error(f"Failed to parse simple YAML {path}: {e}")
            return None
    
    def _load_json(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load JSON configuration file."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def _load_toml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load TOML configuration file."""
        if TOML_AVAILABLE:
            with open(path, 'rb') as f:
                return tomllib.load(f)
        else:
            logger.warning(f"TOML parser not available, cannot load {path}")
            return None
    
    def _load_ini(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load INI configuration file."""
        if INI_AVAILABLE:
            parser = configparser.ConfigParser()
            parser.read(path)
            return {section: dict(parser[section]) for section in parser.sections()}
        else:
            logger.warning(f"ConfigParser not available, cannot load {path}")
            return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            override: Override dictionary (values take precedence)
            
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def get_tool_registry(self) -> Dict[str, Dict[str, Any]]:
        """Get the tool registry from defaults.json."""
        defaults_path = self.config_base_path / "defaults.json"
        if defaults_path.exists():
            try:
                with open(defaults_path, 'r') as f:
                    defaults = json.load(f)
                    return defaults.get('tool_registry', {})
            except Exception as e:
                logger.warning(f"Could not load tool registry: {e}")
        return {}
    
    def get_available_tools(self, category: Optional[str] = None) -> List[str]:
        """
        Get list of available tools.
        
        Args:
            category: Optional category filter ('static', 'dynamic', 'performance')
            
        Returns:
            List of tool names
        """
        registry = self.get_tool_registry()
        
        if category:
            return list(registry.get(category, {}).keys())
        
        tools = []
        for cat_tools in registry.values():
            if isinstance(cat_tools, dict):
                tools.extend(cat_tools.keys())
        return tools
    
    def build_semgrep_args(self, config: Dict[str, Any]) -> List[str]:
        """Build command-line arguments for Semgrep from config."""
        args = ['semgrep', 'scan', '--sarif']
        
        # Add rulesets
        rulesets = config.get('rulesets', ['p/security-audit'])
        for ruleset in rulesets:
            args.extend(['--config', ruleset])
        
        # Add severity threshold
        severity = config.get('severity', {}).get('threshold', 'INFO')
        if severity:
            args.extend(['--severity', severity])
        
        # Add timeout
        timeout = config.get('performance', {}).get('max_scan_time', 300)
        args.extend(['--timeout', str(timeout)])
        
        return args
    
    def build_mypy_args(self, config: Dict[str, Any]) -> List[str]:
        """Build command-line arguments for MyPy from config."""
        args = ['mypy', '--output', 'json', '--show-error-codes', '--no-error-summary']
        
        # Strict mode
        if config.get('strict', True):
            args.append('--strict')
        
        # Warning flags
        if config.get('warn_unused_ignores', True):
            args.append('--warn-unused-ignores')
        if config.get('warn_redundant_casts', True):
            args.append('--warn-redundant-casts')
        if config.get('warn_unreachable', True):
            args.append('--warn-unreachable')
        
        # Import handling
        if config.get('ignore_missing_imports', True):
            args.append('--ignore-missing-imports')
        
        # Performance
        args.extend(['--no-incremental', '--cache-dir', '/tmp/mypy_cache'])
        
        return args
    
    def build_ruff_args(self, config: Dict[str, Any], source_path: str) -> List[str]:
        """Build command-line arguments for Ruff from config."""
        args = ['ruff', 'check', '--output-format=sarif', '--cache-dir', '/tmp/ruff_cache']
        
        # Rule selection
        select = config.get('select', ['E', 'F', 'W', 'I', 'S', 'B'])
        if select:
            args.extend(['--select', ','.join(select)])
        
        # Line length
        line_length = config.get('line_length', 100)
        args.extend(['--line-length', str(line_length)])
        
        # Target version
        target = config.get('target-version', 'py310')
        args.extend(['--target-version', target])
        
        args.append(source_path)
        return args
    
    def build_nmap_args(self, config: Dict[str, Any], host: str, ports: List[int]) -> List[str]:
        """Build command-line arguments for Nmap from config."""
        args = ['nmap']
        
        # Timing template
        timing = config.get('timing', {}).get('template', 4)
        args.append(f'-T{timing}')
        
        # Open ports only
        if config.get('output', {}).get('open_only', True):
            args.append('--open')
        
        # Service detection
        if config.get('service_detection', {}).get('enabled', True):
            args.append('-sV')
            intensity = config.get('service_detection', {}).get('intensity', 7)
            args.extend(['--version-intensity', str(intensity)])
        
        # Scripts
        scripts = config.get('scripts', {})
        if scripts.get('enabled', True):
            script_list = scripts.get('default', ['vuln', 'http-headers', 'http-security-headers'])
            if script_list:
                args.extend(['--script', ','.join(script_list)])
        
        # Skip host discovery (assume up)
        if config.get('host_discovery', {}).get('skip_discovery', True):
            args.append('-Pn')
        
        # Ports
        port_list = ','.join(map(str, ports))
        args.extend(['-p', port_list])
        
        # Host
        args.append(host)
        
        return args


# Singleton instance for convenience
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get the singleton ConfigLoader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def load_tool_config(
    tool_name: str,
    category: str = "static",
    runtime_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Convenience function to load tool configuration.
    
    Args:
        tool_name: Name of the tool
        category: Tool category
        runtime_override: Runtime overrides
        
    Returns:
        Merged configuration
    """
    return get_config_loader().load_config(tool_name, category, runtime_override)
