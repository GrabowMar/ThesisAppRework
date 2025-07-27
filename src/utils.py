"""
Utility Functions and Classes
============================

Common utilities, configuration, and helper functions for the Thesis Research App.
Provides configuration management, Docker operations, and data handling utilities.
"""

import json
import os
import re
import subprocess
import time
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from functools import lru_cache

from flask import Response, current_app, jsonify
from logging_service import create_logger_for_component
from services import DockerManager

# Initialize logger
logger = create_logger_for_component('utils')

# Global cache for container status and names
_container_cache = {}
_docker_project_names_cache = {}
_cache_lock = threading.Lock()
_docker_cache_lock = threading.RLock()
_cache_timeout = 30  # Cache timeout in seconds

# Docker operation locks to prevent concurrent operations on the same project
_docker_operation_locks = {}
_docker_locks_lock = threading.RLock()

# Request deduplication to prevent multiple simultaneous requests
_active_requests = {}
_active_requests_lock = threading.RLock()

# Docker configuration
DOCKER_AVAILABLE = None
DOCKER_COMPOSE_AVAILABLE = None


def get_docker_operation_lock(project_name: str):
    """Get or create a lock for Docker operations on a specific project."""
    with _docker_locks_lock:
        if project_name not in _docker_operation_locks:
            _docker_operation_locks[project_name] = threading.RLock()
        return _docker_operation_locks[project_name]


def is_request_active(model: str, app_num: int, action: str) -> bool:
    """Check if a request for the same action on the same app is already active."""
    request_key = f"{model}_{app_num}_{action}"
    with _active_requests_lock:
        return request_key in _active_requests


def mark_request_active(model: str, app_num: int, action: str) -> str:
    """Mark a request as active and return the request key."""
    request_key = f"{model}_{app_num}_{action}"
    with _active_requests_lock:
        _active_requests[request_key] = {
            'timestamp': time.time(),
            'model': model,
            'app_num': app_num,
            'action': action
        }
    return request_key


def mark_request_complete(request_key: str):
    """Mark a request as completed."""
    with _active_requests_lock:
        _active_requests.pop(request_key, None)


def cleanup_stale_requests(max_age: int = 300):
    """Clean up stale requests that are older than max_age seconds."""
    current_time = time.time()
    with _active_requests_lock:
        stale_keys = [key for key, info in _active_requests.items() 
                     if current_time - info['timestamp'] > max_age]
        for key in stale_keys:
            _active_requests.pop(key, None)
        if stale_keys:
            logger.debug(f"Cleaned up {len(stale_keys)} stale requests")


def cleanup_docker_operation_locks():
    """Clean up unused Docker operation locks to prevent memory leaks."""
    # FIXED: Removed nested lock acquisition - only use one with block
    with _docker_locks_lock:
        # Keep only locks that are currently being used
        if len(_docker_operation_locks) > 100:  # Arbitrary threshold
            logger.debug(f"Cleaning up Docker operation locks (current count: {len(_docker_operation_locks)})")
            # Clear all locks - they'll be recreated as needed
            _docker_operation_locks.clear()
            logger.debug("Docker operation locks cleared")
            return  # Exit early if we cleared everything
        
        # Only keep locks that are currently held
        active_locks = {}
        for project_name, lock in _docker_operation_locks.items():
            # Try to acquire the lock without blocking
            if lock.acquire(blocking=False):
                # If we can acquire it, it's not in use, so we can remove it
                lock.release()
            else:
                # If we can't acquire it, it's in use, so keep it
                active_locks[project_name] = lock
        
        _docker_operation_locks.clear()
        _docker_operation_locks.update(active_locks)
        
        logger.debug(f"Cleaned up Docker locks. Active locks: {len(active_locks)}")


def safe_int_env(key: str, default: int) -> int:
    """Safely parse an integer from environment variables."""
    value = os.getenv(key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer value for {key}: '{value}', using default: {default}")
        return default


def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    global DOCKER_AVAILABLE
    
    if DOCKER_AVAILABLE is not None:
        return DOCKER_AVAILABLE
    
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Client.Version}}"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        DOCKER_AVAILABLE = result.returncode == 0
        if DOCKER_AVAILABLE:
            logger.info("Docker is available and running")
        else:
            logger.warning("Docker is not available or not running")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.warning(f"Docker availability check failed: {e}")
        DOCKER_AVAILABLE = False
    
    return DOCKER_AVAILABLE


def is_docker_compose_available() -> bool:
    """Check if Docker Compose is available."""
    global DOCKER_COMPOSE_AVAILABLE
    
    if DOCKER_COMPOSE_AVAILABLE is not None:
        return DOCKER_COMPOSE_AVAILABLE
    
    try:
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        DOCKER_COMPOSE_AVAILABLE = result.returncode == 0
        if DOCKER_COMPOSE_AVAILABLE:
            logger.info("Docker Compose is available")
        else:
            logger.warning("Docker Compose is not available")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.warning(f"Docker Compose availability check failed: {e}")
        DOCKER_COMPOSE_AVAILABLE = False
    
    return DOCKER_COMPOSE_AVAILABLE


def sanitize_docker_project_name(name: str) -> str:
    """
    Sanitize a string to be a valid Docker project name.
    Docker project names must:
    - Be lowercase
    - Contain only letters, numbers, hyphens, and underscores
    - Not start or end with separator characters
    - Not contain consecutive separators
    """
    if not name:
        return "default"
    
    # Convert to lowercase
    sanitized = name.lower()
    
    # FIXED: Removed redundant import - re is already imported at module level
    # Replace invalid characters with underscores
    sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
    
    # Remove consecutive separators
    sanitized = re.sub(r'[_-]+', '_', sanitized)
    
    # Remove leading/trailing separators
    sanitized = sanitized.strip('_-')
    
    # Ensure it's not empty and not too long
    if not sanitized:
        sanitized = "default"
    elif len(sanitized) > 63:  # Docker has length limits
        sanitized = sanitized[:63].rstrip('_-')
    
    return sanitized


def get_docker_project_name(model: str, app_num: int) -> str:
    """
    Get a sanitized Docker project name with caching.
    Only sanitizes when actually needed for Docker operations.
    """
    if not model or app_num < 1:
        raise ValueError("Invalid model name or app number")
    
    cache_key = f"{model}:{app_num}"
    
    # Check cache first with proper thread safety
    with _docker_cache_lock:
        if cache_key in _docker_project_names_cache:
            cached_data = _docker_project_names_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                logger.debug(f"Using cached Docker project name for {model}/app{app_num}")
                return cached_data['project_name']
    
    # Generate and sanitize project name
    raw_name = f"{model}_app{app_num}"
    sanitized_name = sanitize_docker_project_name(raw_name)
    
    # Cache the result with proper thread safety
    with _docker_cache_lock:
        _docker_project_names_cache[cache_key] = {
            'project_name': sanitized_name,
            'timestamp': time.time()
        }
    
    logger.debug(f"Generated Docker project name for {model}/app{app_num}: {sanitized_name}")
    return sanitized_name


def stop_conflicting_containers(project_name: str) -> Tuple[bool, str]:
    """
    Comprehensive container cleanup with improved error handling and conflict resolution.
    """
    try:
        output_parts = []
        
        # Use a lock to prevent concurrent cleanup of the same project
        with get_docker_operation_lock(project_name):
            logger.info(f"Attempting docker-compose down for project: {project_name}")
            
            # Step 1: Try docker-compose down first (most reliable method)
            down_success = False
            try:
                down_result = subprocess.run(
                    ["docker-compose", "-p", project_name, "down", "--remove-orphans", "--timeout", "15"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if down_result.returncode == 0:
                    output_parts.append(f"Successfully ran docker-compose down for project: {project_name}")
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {output_parts[-1]}")
                    down_success = True
                else:
                    error_msg = down_result.stderr.strip() if down_result.stderr else "Unknown error"
                    logger.debug(f"Docker-compose down failed for {project_name}: {error_msg}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Docker-compose down timed out for {project_name}")
            except Exception as e:
                logger.debug(f"Docker-compose down error for {project_name}: {e}")
            
            # Step 2: Find and forcefully remove any remaining containers
            # Use more comprehensive search patterns
            container_patterns = [
                f"^{project_name}_.*",      # Standard compose naming (exact prefix)
                f"^{project_name}-.*",      # Alternative naming
                f"^.*{project_name}.*",     # Contains project name
                f"^{project_name}$"         # Exact match
            ]
            
            all_containers = set()
            for pattern in container_patterns:
                try:
                    # Use grep-like filtering for better matches
                    result = subprocess.run(
                        ["docker", "ps", "-a", "--format", "{{.Names}}"],
                        capture_output=True,
                        text=True,
                        timeout=20,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        all_names = result.stdout.strip().split('\n')
                        # Filter names that match our pattern
                        matching_containers = [name.strip() for name in all_names 
                                             if name.strip() and re.search(pattern, name.strip())]
                        all_containers.update(matching_containers)
                        
                except Exception as e:
                    logger.debug(f"Error finding containers with pattern {pattern}: {e}")
                    continue
            
            if not all_containers:
                output_parts.append("No conflicting containers found")
                logger.debug(f"No containers found for project {project_name}")
                return True, "\n".join(output_parts)
            
            # Step 3: Stop containers first, then remove them
            logger.info(f"Stopping conflicting containers: {', '.join(all_containers)}")
            container_list = list(all_containers)
            
            # First, try to stop all containers
            stop_success = 0
            for container_name in container_list:
                try:
                    stop_result = subprocess.run(
                        ["docker", "stop", "-t", "5", container_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if stop_result.returncode == 0:
                        stop_success += 1
                        logger.info(f"Stopped conflicting container: {container_name}")
                except Exception as e:
                    logger.debug(f"Error stopping container {container_name}: {e}")
            
            # Brief pause to allow Docker to process stops
            if stop_success > 0:
                time.sleep(1)
            
            # Then remove all containers (force removal)
            removed_count = 0
            for container_name in container_list:
                try:
                    rm_result = subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if rm_result.returncode == 0:
                        removed_count += 1
                        logger.debug(f"Removed container: {container_name}")
                except Exception as e:
                    logger.debug(f"Error removing container {container_name}: {e}")
            
            if removed_count > 0:
                output_parts.append(f"Forcefully removed {removed_count} conflicting containers")
            
            # Step 4: Network cleanup (best effort)
            try:
                # Remove networks associated with this project
                network_result = subprocess.run(
                    ["docker", "network", "ls", "--filter", f"name={project_name}", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if network_result.returncode == 0 and network_result.stdout.strip():
                    networks = [name.strip() for name in network_result.stdout.strip().split('\n') if name.strip()]
                    # Only remove our project networks
                    project_networks = [net for net in networks if project_name in net]
                    
                    network_removed = 0
                    for network_name in project_networks:
                        try:
                            subprocess.run(
                                ["docker", "network", "rm", network_name],
                                capture_output=True,
                                text=True,
                                timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            )
                            network_removed += 1
                            logger.debug(f"Removed network: {network_name}")
                        except Exception:
                            pass  # Network cleanup is optional
                    
                    if network_removed > 0:
                        output_parts.append(f"Cleaned up {network_removed} networks")
            except Exception:
                pass  # Network cleanup is optional
            
            # Step 5: Volume cleanup (very careful, only orphaned volumes)
            try:
                # Only remove volumes that are definitely orphaned and related to this project
                volume_result = subprocess.run(
                    ["docker", "volume", "ls", "-f", "dangling=true", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if volume_result.returncode == 0 and volume_result.stdout.strip():
                    volumes = [name.strip() for name in volume_result.stdout.strip().split('\n') if name.strip()]
                    project_volumes = [vol for vol in volumes if project_name in vol]
                    
                    if project_volumes:
                        try:
                            subprocess.run(
                                ["docker", "volume", "rm"] + project_volumes,
                                capture_output=True,
                                text=True,
                                timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            )
                            output_parts.append(f"Removed {len(project_volumes)} orphaned volumes")
                        except Exception:
                            pass  # Volume cleanup is optional
            except Exception:
                pass  # Volume cleanup is optional
            
            # Brief pause to let Docker process the changes
            time.sleep(0.5)
            
        logger.info(f"Cleanup completed for project: {project_name}")
        return True, "\n".join(output_parts)
        
    except Exception as e:
        error_msg = f"Error during cleanup for {project_name}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


@dataclass
class AppConfig:
    """Configuration class for application settings."""
    DEBUG: bool = os.getenv("FLASK_ENV", "development") != "production"
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")
    BASE_DIR: Path = Path(__file__).parent
    DOCKER_TIMEOUT: int = safe_int_env("DOCKER_TIMEOUT", 10)
    HOST: str = "0.0.0.0" if os.getenv("FLASK_ENV") == "production" else "127.0.0.1"
    PORT: int = safe_int_env("PORT", 5000)
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO" if os.getenv("FLASK_ENV") == "production" else "DEBUG")
    MODELS_BASE_DIR: Optional[str] = os.getenv("MODELS_BASE_DIR")

    def __post_init__(self):
        # Set up log directory
        log_path = Path(self.LOG_DIR)
        if not log_path.is_absolute():
            log_path = self.BASE_DIR.parent / log_path
        log_path.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR = str(log_path)

        # Validate secret key
        if self.SECRET_KEY == "your-secret-key-here" and not self.DEBUG:
            logger.warning("SECURITY WARNING: FLASK_SECRET_KEY is not set in production!")

        # Set default models directory
        if self.MODELS_BASE_DIR is None:
            self.MODELS_BASE_DIR = str(self.BASE_DIR.parent / "models")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration instance from environment variables."""
        return cls()


@dataclass
class AIModel:
    """Class representing an AI model with comprehensive information from JSON files."""
    name: str
    color: str = "#666666"
    provider: str = "unknown"
    context_length: int = 0
    pricing: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_function_calling: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return asdict(self)


def load_port_config(app_root_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load port configuration from JSON file."""
    config_path = Path(app_root_path) / "port_config.json"
    
    if not config_path.exists():
        logger.warning(f"Port configuration file not found: {config_path}")
        return []
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded {len(config)} port configurations")
            return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in port configuration: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading port configuration: {e}")
        return []


def load_models_from_json_files() -> Dict[str, Any]:
    """Load comprehensive model information from the three JSON files."""
    logger = create_logger_for_component('model_loader')
    models_data = {
        'port_config': [],
        'model_capabilities': {},
        'models_summary': {}
    }
    
    # Load port_config.json
    try:
        with open('port_config.json', 'r', encoding='utf-8') as f:
            models_data['port_config'] = json.load(f)
        logger.info(f"Loaded {len(models_data['port_config'])} port configurations")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load port_config.json: {e}")
    
    # Load model_capabilities.json
    try:
        with open('model_capabilities.json', 'r', encoding='utf-8') as f:
            capabilities_data = json.load(f)
            models_data['model_capabilities'] = capabilities_data.get('models', {})
        logger.info(f"Loaded capabilities for {len(models_data['model_capabilities'])} models")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load model_capabilities.json: {e}")
    
    # Load models_summary.json
    try:
        with open('models_summary.json', 'r', encoding='utf-8') as f:
            models_data['models_summary'] = json.load(f)
        logger.info(f"Loaded models summary with {models_data['models_summary'].get('total_models', 0)} models")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load models_summary.json: {e}")
    
    return models_data


def get_ai_models_from_config(port_config: List[Dict[str, Any]]) -> List[AIModel]:
    """Extract unique AI models from port configuration, enhanced with JSON data."""
    if not port_config:
        return []
    
    # Load comprehensive model data from JSON files
    models_data = load_models_from_json_files()
    models_summary = models_data['models_summary'].get('models', [])
    model_capabilities = models_data['model_capabilities']
    
    # Create a lookup for models_summary data
    summary_lookup = {model['name']: model for model in models_summary}
    
    # Default color mappings (fallback)
    default_color_mappings = {
        'anthropic': '#D97706',
        'openai': '#14B8A6', 
        'mistralai': '#8B5CF6',
        'google': '#3B82F6',
        'meta-llama': '#F59E0B',
        'nousresearch': '#EC4899',
        'microsoft': '#6366F1',
        'qwen': '#F43F5E',
        'x-ai': '#EF4444',
        'inception': '#A855F7',
        'deepseek': '#F97316',
        'opengvlab': '#808080',
        'thudm': '#808080',
        'agentica-org': '#10B981',
        'rekaai': '#60A5FA',
        'open-r1': '#FBBF24'
    }
    
    unique_models = {}
    for config in port_config:
        model_name = config.get('model_name', '')
        if model_name and model_name not in unique_models:
            # Get color from models_summary.json first, then fallback to defaults
            color = '#666666'  # default color
            provider = 'unknown'
            
            if model_name in summary_lookup:
                summary_data = summary_lookup[model_name]
                color = summary_data.get('color', color)
                provider = summary_data.get('provider', provider)
            else:
                # Fallback to prefix-based color mapping
                for prefix, model_color in default_color_mappings.items():
                    if model_name.startswith(prefix):
                        color = model_color
                        provider = prefix
                        break
            
            # Create enhanced AIModel with capabilities data
            ai_model = AIModel(name=model_name, color=color)
            
            # Add capabilities if available
            if model_name in model_capabilities:
                caps = model_capabilities[model_name]
                ai_model.provider = caps.get('provider', provider)
                ai_model.context_length = caps.get('context_length', 0)
                ai_model.pricing = caps.get('pricing', {})
                ai_model.capabilities = caps.get('capabilities', [])
                ai_model.supports_vision = caps.get('supports_vision', False)
                ai_model.supports_function_calling = caps.get('supports_function_calling', False)
            
            unique_models[model_name] = ai_model
    
    return list(unique_models.values())


def get_port_config() -> List[Dict[str, Any]]:
    """Get port configuration from current app context."""
    return current_app.config.get('PORT_CONFIG', [])


def get_ai_models() -> List[AIModel]:
    """Get AI models from current app context."""
    return current_app.config.get('AI_MODELS', [])


def get_model_by_name(model_name: str) -> Optional[AIModel]:
    """Get a specific model by name from the loaded models."""
    models = get_ai_models()
    for model in models:
        if model.name == model_name:
            return model
    return None


def get_models_by_provider(provider: str) -> List[AIModel]:
    """Get all models from a specific provider."""
    models = get_ai_models()
    return [model for model in models if model.provider == provider]


def get_models_with_capability(capability: str) -> List[AIModel]:
    """Get all models that have a specific capability."""
    models = get_ai_models()
    return [model for model in models if capability in model.capabilities]


def get_vision_models() -> List[AIModel]:
    """Get all models that support vision."""
    models = get_ai_models()
    return [model for model in models if model.supports_vision]


def get_function_calling_models() -> List[AIModel]:
    """Get all models that support function calling."""
    models = get_ai_models()
    return [model for model in models if model.supports_function_calling]


def get_enhanced_models() -> List[Any]:
    """Get enhanced models from current app context."""
    return current_app.config.get('ENHANCED_MODELS', [])


def get_model_service():
    """Get the model integration service from current app context."""
    return current_app.config.get('MODEL_SERVICE')


def get_model_stats() -> Dict[str, Any]:
    """Get model statistics from current app context."""
    # FIXED: First check if stats are available in app config
    config_stats = current_app.config.get('MODEL_STATS')
    if config_stats:
        return config_stats
    
    # FIXED: If not in config, generate stats from loaded models
    models = get_ai_models()
    if not models:
        return {}
    
    providers = set(model.provider for model in models)
    capabilities = set()
    for model in models:
        capabilities.update(model.capabilities)
    
    return {
        'total_models': len(models),
        'unique_providers': len(providers),
        'providers': list(providers),
        'total_capabilities': len(capabilities),
        'capabilities': list(capabilities),
        'vision_models': len([m for m in models if m.supports_vision]),
        'function_calling_models': len([m for m in models if m.supports_function_calling]),
        'avg_context_length': sum(m.context_length for m in models) // len(models) if models else 0
    }


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle complex types."""
    def default(self, o: Any) -> Any:
        if hasattr(o, 'to_dict') and callable(o.to_dict):
            return o.to_dict()
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


def create_api_response(success: bool = True, data: Any = None, error: Optional[str] = None, 
                       message: Optional[str] = None, code: int = 200) -> Tuple[Response, int]:
    """Create a standardized API response."""
    response_data: Dict[str, Any] = {"success": success}
    if message:
        response_data["message"] = message
    if data is not None:
        response_data["data"] = data
    if error:
        response_data["error"] = error
    return jsonify(response_data), code


def get_app_info(model: str, app_num: int) -> Optional[Dict[str, Any]]:
    """Get information about a specific app."""
    port_config = get_port_config()
    
    for config in port_config:
        if config.get('model_name') == model and config.get('app_number') == app_num:
            backend_port = config.get('backend_port')
            frontend_port = config.get('frontend_port')
            if backend_port is None or frontend_port is None:
                logger.warning(f"Missing port configuration for {model}/app{app_num}")
                return None
            return {
                "model": model,
                "app_num": app_num,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "backend_url": f"http://localhost:{backend_port}",
                "frontend_url": f"http://localhost:{frontend_port}"
            }
    
    return None


def get_app_config_by_model_and_number(model: str, app_num: int) -> Optional[Dict[str, Any]]:
    """Get app configuration by model name and app number."""
    port_config = get_port_config()
    
    for config in port_config:
        if config.get('model_name') == model and config.get('app_number') == app_num:
            return config
    
    return None


def get_apps_for_model(model: str) -> List[Dict[str, Any]]:
    """Get all apps for a specific model."""
    port_config = get_port_config()
    apps = []
    
    for config in port_config:
        if config.get('model_name') == model:
            app_number = config.get('app_number')
            if app_number is not None:
                app_info = get_app_info(model, app_number)
                if app_info:
                    apps.append(app_info)
    
    return apps


def get_models_base_dir() -> Path:
    """Get the base directory for models."""
    config = current_app.config.get('APP_CONFIG')
    if config and config.MODELS_BASE_DIR:
        return Path(config.MODELS_BASE_DIR)
    
    # Fallback to default
    return Path(__file__).parent.parent / "models"


def get_app_directory(model: str, app_num: int) -> Path:
    """Get the directory path for a specific application."""
    models_base_dir = get_models_base_dir()
    model_app_path = models_base_dir / model / f"app{app_num}"
    
    if not model_app_path.is_dir():
        raise FileNotFoundError(f"Application directory not found: {model_app_path}")
    
    return model_app_path


def get_all_apps() -> List[Dict[str, Any]]:
    """
    Get all applications from port configuration.
    
    Returns:
        List of application configurations
    """
    port_config = get_port_config()
    
    all_apps = []
    for config in port_config:
        model_name = config.get('model_name')
        app_num = config.get('app_number')
        
        if not model_name or not app_num:
            continue
        
        app_info = get_app_info(model_name, app_num)
        if app_info:
            all_apps.append(app_info)
    
    return all_apps


def get_docker_manager() -> DockerManager:
    """Get the Docker manager instance from the Flask app."""
    docker_manager = current_app.config.get("docker_manager")
    if not docker_manager:
        raise RuntimeError("Docker manager is not available")
    return docker_manager


def run_docker_compose(command: List[str], model: str, app_num: int, 
                      timeout: int = 60) -> Tuple[bool, str]:
    """Run a docker-compose command for a specific application with comprehensive error handling."""
    
    # Check Docker availability first
    if not is_docker_available():
        return False, "Docker is not available or not running"
    
    if not is_docker_compose_available():
        return False, "Docker Compose is not available"
    
    try:
        app_dir = get_app_directory(model, app_num)
        
        # Find compose file
        compose_file = None
        for filename in ["docker-compose.yml", "docker-compose.yaml"]:
            potential_path = app_dir / filename
            if potential_path.exists():
                compose_file = potential_path
                break
                
        if not compose_file:
            return False, f"No docker-compose file found in {app_dir}"
        
        # Get sanitized project name
        project_name = get_docker_project_name(model, app_num)
        
        # Pre-emptive cleanup for "up" commands to avoid conflicts
        if "up" in command:
            logger.info(f"Checking for container conflicts for project: {project_name}")
            
            # First check if compose project is already running cleanly
            try:
                status_check = subprocess.run(
                    ["docker-compose", "-p", project_name, "-f", str(compose_file), "ps", "--services", "--filter", "status=running"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if status_check.returncode == 0 and status_check.stdout.strip():
                    # Services are running, check if they're healthy
                    running_services = status_check.stdout.strip().split('\n')
                    logger.debug(f"Found running services for {project_name}: {running_services}")
                    
                    # For now, do cleanup anyway to ensure fresh start
                    logger.info(f"Attempting docker-compose down for project: {project_name}")
                    conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
                else:
                    # No running services, but do a safety cleanup anyway
                    logger.info(f"Attempting docker-compose down for project: {project_name}")
                    conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
                
            except Exception as e:
                logger.debug(f"Pre-cleanup check failed for {project_name}, proceeding with cleanup: {e}")
                conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
        
        # Build and execute command
        cmd = ["docker-compose", "-p", project_name, "-f", str(compose_file)] + command
        
        logger.info(f"Running Docker Compose command: {' '.join(cmd)}")
        
        # Run command with improved error handling
        result = subprocess.run(
            cmd,
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        output = result.stdout
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr
            
        success = result.returncode == 0
        
        # Enhanced error detection and handling
        if not success:
            error_output = output.lower()
            
            # Check for specific error patterns that we can handle
            if any(pattern in error_output for pattern in [
                "already in use", "conflict", "port is already allocated",
                "address already in use", "name is already in use"
            ]):
                logger.warning(f"Container name conflict detected for {project_name}")
                return False, f"Container conflict detected:\n{output}"
            
            elif any(pattern in error_output for pattern in [
                "no such container", "container not found", 
                "cannot kill container", "cannot start container"
            ]):
                logger.warning(f"Container reference issue for {project_name}, attempting cleanup and retry")
                return False, f"Container reference issue detected:\n{output}"
            
            elif any(pattern in error_output for pattern in [
                "network", "endpoint", "driver failed programming external connectivity"
            ]):
                logger.warning(f"Network conflict detected for {project_name}")
                return False, f"Network issue detected:\n{output}"
            
            elif "timeout" in error_output or "timed out" in error_output:
                logger.error(f"Docker command timed out for {project_name}")
                return False, f"Docker operation timed out:\n{output}"
            
            else:
                # Generic failure
                logger.error(f"Docker Compose command failed for {model}/app{app_num}: {output}")
                return False, output.strip()
        else:
            logger.info(f"Docker Compose command succeeded for {model}/app{app_num}")
            return True, output.strip()
            
    except subprocess.TimeoutExpired:
        error_msg = f"Docker Compose command timed out after {timeout}s"
        logger.error(error_msg)
        return False, error_msg
    except FileNotFoundError:
        error_msg = "docker-compose command not found. Please install Docker Compose."
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error running Docker Compose: {e}"
        logger.exception(error_msg)
        return False, error_msg


def handle_docker_action(action: str, model: str, app_num: int) -> Tuple[bool, str]:
    """Handle Docker actions with comprehensive error handling and intelligent retry logic."""
    
    valid_actions = {"start", "stop", "restart", "build", "rebuild", "cleanup"}
    if action not in valid_actions:
        return False, f"Invalid action: {action}. Valid actions: {', '.join(valid_actions)}"
    
    # Clean up any stale requests first
    cleanup_stale_requests()
    
    # Check for duplicate requests
    if is_request_active(model, app_num, action):
        return False, f"Request for '{action}' on {model}/app{app_num} is already in progress"
    
    # Mark this request as active
    request_key = mark_request_active(model, app_num, action)
    
    try:
        # Check Docker availability before proceeding
        if not is_docker_available():
            return False, "Docker is not available or not running. Please start Docker Desktop."
        
        if not is_docker_compose_available():
            return False, "Docker Compose is not available. Please install Docker Compose."
        
        # Get sanitized project name for locking
        project_name = get_docker_project_name(model, app_num)
        
        # Use a lock to prevent concurrent operations on the same project
        with get_docker_operation_lock(project_name):
            logger.info(f"Executing '{action}' for {model}/app{app_num} (project: {project_name})")
            
            # Clear cache for this specific app
            clear_container_cache(model, app_num)
            
            # Define commands for each action with intelligent sequencing
            action_commands = {
                "start": [["up", "-d", "--remove-orphans"]],
                "stop": [["down", "--timeout", "30"]],
                "restart": [["restart"]],
                "build": [["build", "--no-cache", "--pull"]],
                "rebuild": [
                    ["down", "--timeout", "30"],
                    ["build", "--no-cache", "--pull"],
                    ["up", "-d", "--remove-orphans"]
                ],
                "cleanup": [
                    ["down", "--volumes", "--remove-orphans", "--timeout", "30"],
                    ["system", "prune", "-f", "--volumes"]
                ]
            }
            
            commands = action_commands[action]
            full_output = []
            max_retries = 2  # Maximum number of retries for each step
            
            for i, cmd in enumerate(commands):
                # Set appropriate timeout for different operations
                if any(keyword in cmd for keyword in ["build", "pull"]):
                    timeout = 900  # 15 minutes for build/pull operations
                elif any(keyword in cmd for keyword in ["up"]):
                    timeout = 300  # 5 minutes for up operations
                elif any(keyword in cmd for keyword in ["down", "prune"]):
                    timeout = 180   # 3 minutes for cleanup operations  
                else:
                    timeout = 120  # 2 minutes for other operations
                
                step_info = f"Step {i+1}/{len(commands)}: {' '.join(cmd)}"
                logger.info(f"Running {step_info}")
                full_output.append(f"--- {step_info} ---")
                
                # Retry logic with intelligent error handling
                retry_count = 0
                step_success = False
                
                while retry_count <= max_retries and not step_success:
                    success, output = run_docker_compose(cmd, model, app_num, timeout)
                    full_output.append(output)
                    
                    if success:
                        step_success = True
                        logger.info(f"Step completed successfully: {step_info}")
                        break
                        
                    # Analyze the failure and decide on retry strategy
                    retry_count += 1
                    error_output = output.lower()
                    should_retry = False
                    retry_action = None
                    
                    if retry_count <= max_retries:
                        # Check for recoverable errors
                        if any(pattern in error_output for pattern in [
                            "already in use", "conflict", "container name", "address already in use"
                        ]):
                            should_retry = True
                            retry_action = "cleanup"
                            logger.warning(f"Container conflict detected for {project_name} (attempt {retry_count}/{max_retries}), attempting cleanup")
                            
                        elif any(pattern in error_output for pattern in [
                            "no such container", "container not found", "cannot kill container"
                        ]):
                            should_retry = True
                            retry_action = "cleanup"
                            logger.warning(f"Container reference issue for {project_name} (attempt {retry_count}/{max_retries}), attempting cleanup and retry")
                            
                        elif any(pattern in error_output for pattern in [
                            "network", "endpoint", "driver failed programming external connectivity"
                        ]):
                            should_retry = True
                            retry_action = "network_cleanup"
                            logger.warning(f"Network issue detected for {project_name} (attempt {retry_count}/{max_retries}), attempting network cleanup")
                            
                        elif "timeout" in error_output and "up" in cmd:
                            # For timeout on 'up' command, try with longer timeout
                            should_retry = True
                            retry_action = "extend_timeout"
                            timeout = min(timeout * 2, 1800)  # Double timeout, max 30 minutes
                            logger.warning(f"Timeout detected for {project_name} (attempt {retry_count}/{max_retries}), extending timeout to {timeout}s")
                    
                    if should_retry:
                        # Perform the appropriate retry action
                        if retry_action in ["cleanup", "network_cleanup"]:
                            logger.info(f"Attempting comprehensive cleanup for project: {project_name}")
                            conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                            full_output.append(f"\n--- Retry {retry_count} Cleanup ---\n{conflict_output}")
                            
                            if conflict_handled:
                                # Wait a bit longer after cleanup
                                time.sleep(2)
                                logger.info(f"Retrying after cleanup (attempt {retry_count}): {' '.join(cmd)}")
                            else:
                                logger.warning(f"Cleanup failed for {project_name}, retrying anyway")
                                time.sleep(1)
                        
                        elif retry_action == "extend_timeout":
                            # Just wait a moment before retry with extended timeout
                            time.sleep(1)
                            logger.info(f"Retrying with extended timeout (attempt {retry_count}): {' '.join(cmd)}")
                        
                        # Continue to retry with updated parameters
                        continue
                    else:
                        # No more retries or unrecoverable error
                        break
                
                # Check if step ultimately failed
                if not step_success:
                    error_msg = f"Action '{action}' failed at {step_info} after {retry_count} attempts"
                    return False, f"{error_msg}\n\n{''.join(full_output)}"
            
            logger.info(f"Successfully completed '{action}' for {model}/app{app_num}")
            return True, f"Action '{action}' completed successfully.\n\n{''.join(full_output)}"
            
    finally:
        # Always mark the request as complete
        mark_request_complete(request_key)


def verify_container_health(docker_manager: DockerManager, model: str, app_num: int,
                          max_retries: int = 15, retry_delay: int = 5) -> Tuple[bool, str]:
    """Verify the health of containers for a specific application."""
    try:
        backend_name, frontend_name = get_container_names_cached(model, app_num)
    except ValueError as e:
        return False, f"Invalid model/app: {e}"
        
    logger.info(f"Verifying health for {model}/app{app_num}")
    
    for attempt in range(1, max_retries + 1):
        try:
            backend = docker_manager.get_container_status(backend_name)
            frontend = docker_manager.get_container_status(frontend_name)
            
            backend_healthy = backend.running and backend.health == "healthy"
            frontend_healthy = frontend.running and frontend.health == "healthy"
            
            if backend_healthy and frontend_healthy:
                logger.info(f"Containers healthy for {model}/app{app_num}")
                return True, "All containers healthy"
                
        except Exception as e:
            logger.error(f"Health check error on attempt {attempt}: {e}")
            
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    return False, "Containers failed to become healthy"


def get_app_container_statuses_cached(model: str, app_num: int, 
                                    docker_manager: DockerManager) -> Dict[str, Any]:
    """
    Get container statuses for a specific application with caching.
    
    Args:
        model: Model name
        app_num: Application number
        docker_manager: DockerManager instance
        
    Returns:
        Dictionary containing container statuses
    """
    cache_key = f"{model}:{app_num}:status"
    
    # Check cache first with improved thread safety
    with _cache_lock:
        if cache_key in _container_cache:
            cached_data = _container_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                logger.debug(f"Using cached status for {model}/app{app_num}")
                return cached_data['data']
    
    # Get fresh status
    try:
        backend_name, frontend_name = get_container_names_cached(model, app_num)
        
        backend_status = docker_manager.get_container_status(backend_name)
        frontend_status = docker_manager.get_container_status(frontend_name)
        
        result = {
            "backend": backend_status.to_dict() if backend_status else {},
            "frontend": frontend_status.to_dict() if frontend_status else {},
            "success": True
        }
        
        # Cache the result with improved thread safety
        with _cache_lock:
            _container_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
        
        logger.debug(f"Cached fresh status for {model}/app{app_num}")
        return result
        
    except Exception as e:
        logger.error(f"Error getting container statuses: {e}")
        result = {
            "backend": {},
            "frontend": {},
            "success": False,
            "error": str(e)
        }
        return result


def get_app_container_statuses(model: str, app_num: int, 
                             docker_manager: DockerManager) -> Dict[str, Any]:
    """
    Get container statuses for a specific application.
    This now uses the cached version by default.
    """
    return get_app_container_statuses_cached(model, app_num, docker_manager)


def save_analysis_results(model: str, app_num: int, results, filename: str = "performance_results.json"):
    """
    Save analysis results as JSON in the centralized reports directory.
    
    Args:
        model: Model name
        app_num: Application number
        results: Results to save
        filename: Output filename
        
    Returns:
        Path to saved file
    """
    # Get the project root directory and create reports path
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    reports_dir.mkdir(parents=True, exist_ok=True)
    file_path = reports_dir / filename
    
    # Convert results to dict if necessary
    if hasattr(results, "to_dict"):
        data = results.to_dict()
    elif hasattr(results, "__dict__"):
        data = results.__dict__
    else:
        data = results
        
    # Add metadata to the saved results
    if isinstance(data, dict):
        data["_metadata"] = {
            "model": model,
            "app_num": app_num,
            "saved_at": datetime.now().isoformat(),
            "filename": filename
        }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved analysis results to {file_path}")
    return file_path


def load_analysis_results(model: str, app_num: int, filename: str = "performance_results.json"):
    """
    Load analysis results from JSON in the centralized reports directory.
    
    Args:
        model: Model name
        app_num: Application number
        filename: Input filename
        
    Returns:
        Loaded data or None if file doesn't exist
    """
    # Get the project root directory and create reports path
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    file_path = reports_dir / filename
    
    if not file_path.exists():
        # Try to find the file in the old location for backward compatibility
        base_dir = get_models_base_dir()
        old_file_path = Path(base_dir) / model / f"app{app_num}" / filename
        if old_file_path.exists():
            logger.info(f"Found results in old location, migrating to reports directory: {old_file_path}")
            # Load from old location
            with open(old_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Save to new location
            save_analysis_results(model, app_num, data, filename)
            return data
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.debug(f"Loaded analysis results from {file_path}")
    return data


def get_container_names(model: str, app_num: int) -> Tuple[str, str]:
    """
    Get standardized container names for an application using proper sanitization.
    
    Args:
        model: Model name
        app_num: Application number
        
    Returns:
        Tuple of (backend_name, frontend_name)
        
    Raises:
        ValueError: If model is invalid or app_num < 1
    """
    if not model or app_num < 1:
        raise ValueError("Invalid model or app number")
    
    # Check cache first with improved thread safety
    cache_key = f"{model}:{app_num}:names"
    with _cache_lock:
        if cache_key in _container_cache:
            cached_data = _container_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                return cached_data['data']
    
    # Get the app configuration to get port numbers
    app_config = get_app_config_by_model_and_number(model, app_num)
    if not app_config:
        raise ValueError(f"No configuration found for model '{model}' app {app_num}")
    
    backend_port = app_config.get('backend_port')
    frontend_port = app_config.get('frontend_port')
    
    if not backend_port or not frontend_port:
        raise ValueError(f"Missing port configuration for model '{model}' app {app_num}")
    
    # Use sanitized project name
    project_name = get_docker_project_name(model, app_num)
    
    # Generate container names with port numbers as used by docker-compose
    backend_name = f"{project_name}_backend_{backend_port}"
    frontend_name = f"{project_name}_frontend_{frontend_port}"
    
    result = (backend_name, frontend_name)
    
    # Cache the result with improved thread safety
    with _cache_lock:
        _container_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
    
    logger.debug(f"Generated container names for {model}/app{app_num}: {result}")
    return result


@lru_cache(maxsize=128)
def get_container_names_cached(model: str, app_num: int) -> Tuple[str, str]:
    """
    Get standardized container names for an application with LRU caching.
    This is a cached version of get_container_names for better performance.
    """
    return get_container_names(model, app_num)


def process_security_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process security analysis results for display.
    
    Args:
        analysis_result: Raw analysis results
        
    Returns:
        Processed analysis results
    """
    # Simplified processing for non-AJAX display
    return analysis_result


def stop_zap_scanners(app) -> None:
    """
    Stop all active ZAP scanners.
    
    Args:
        app: Flask application instance
    """
    try:
        if hasattr(app, 'config') and 'ZAP_SCANS' in app.config:
            scans = app.config['ZAP_SCANS']
            for scan_id in list(scans.keys()):
                try:
                    if hasattr(app, 'zap_scanner') and app.zap_scanner:
                        app.zap_scanner.stop_scan(scan_id)
                except Exception as e:
                    logger.error(f"Error stopping ZAP scan {scan_id}: {e}")
                finally:
                    scans.pop(scan_id, None)
    except Exception as e:
        logger.error(f"Error in stop_zap_scanners: {e}")


class JsonResultsManager:
    """Centralized results manager for all analysis types."""
    
    def __init__(self, base_path: Path, module_name: str):
        """
        Initialize the JsonResultsManager.
        
        Args:
            base_path: Base path for the application (not used in centralized approach)
            module_name: Name of the module for identification
        """
        self.module_name = module_name
        self.project_root = Path(__file__).parent.parent
        self.reports_dir = self.project_root / "reports"
        logger.info(f"JsonResultsManager initialized for {module_name} with reports directory: {self.reports_dir}")
    
    def save_results(self, model: str, app_num: int, results: Any, 
                    file_name: Optional[str] = None, **kwargs) -> Path:
        """
        Save analysis results to JSON file in the centralized reports directory.
        
        Args:
            model: Model name
            app_num: Application number
            results: Results to save
            file_name: Output filename (defaults to module-specific name)
            **kwargs: Additional parameters (for compatibility)
            
        Returns:
            Path to saved file
        """
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        # Create directory structure
        results_dir = self.reports_dir / model / f"app{app_num}"
        results_dir.mkdir(parents=True, exist_ok=True)
        results_path = results_dir / file_name
        
        # Convert results to dict if necessary
        data_to_save = results
        if hasattr(results, 'to_dict'):
            data_to_save = results.to_dict()
        elif hasattr(results, '__dict__'):
            data_to_save = results.__dict__
        elif isinstance(results, (list, tuple)) and all(hasattr(item, 'to_dict') for item in results):
            data_to_save = [item.to_dict() for item in results]
        
        # Add metadata
        if isinstance(data_to_save, dict):
            data_to_save["_metadata"] = {
                "module": self.module_name,
                "model": model,
                "app_num": app_num,
                "saved_at": datetime.now().isoformat(),
                "filename": file_name
            }
        
        # Save to file
        with open(results_path, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2)
        
        logger.info(f"Saved {self.module_name} results for {model}/app{app_num} to {results_path}")
        return results_path
    
    def load_results(self, model: str, app_num: int, 
                    file_name: Optional[str] = None, **kwargs) -> Optional[Any]:
        """
        Load analysis results from JSON file in the centralized reports directory.
        
        Args:
            model: Model name
            app_num: Application number
            file_name: Input filename (defaults to module-specific name)
            **kwargs: Additional parameters (for compatibility)
            
        Returns:
            Loaded data or None if file doesn't exist
        """
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        # Check new location first
        results_path = self.reports_dir / model / f"app{app_num}" / file_name
        
        if not results_path.exists():
            # Try to find in old locations for backward compatibility
            old_paths = [
                # Old security analysis location
                self.project_root / "models" / model / f"app{app_num}" / "z_interface_app" / "results" / model / f"app{app_num}" / file_name,
                # Old models location
                self.project_root / "models" / model / f"app{app_num}" / file_name
            ]
            
            for old_path in old_paths:
                if old_path.exists():
                    logger.info(f"Found {self.module_name} results in old location, migrating: {old_path}")
                    # Load from old location
                    with open(old_path, "r", encoding='utf-8') as f:
                        data = json.load(f)
                    # Save to new location
                    self.save_results(model, app_num, data, file_name)
                    return data
            
            logger.debug(f"No {self.module_name} results found for {model}/app{app_num}")
            return None
        
        # Load from new location
        with open(results_path, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"Loaded {self.module_name} results for {model}/app{app_num} from {results_path}")
        return data


def load_json_results_for_template(model: str, app_num: int, analysis_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Load JSON results from the centralized reports directory for template display.
    
    Args:
        model: Model name
        app_num: Application number
        analysis_type: Type of analysis results to load (optional)
        
    Returns:
        Dictionary containing all available analysis results
    """
    results = {}
    
    # Define mapping of analysis types to file names
    analysis_files = {
        'backend_security': '.backend_security_results.json',
        'frontend_security': '.frontend_security_results.json',
        'zap_scan': 'zap_results.json',  # Updated to match actual file pattern
        'performance': 'performance_results.json',
        'gpt4all': '.openrouter_requirements.json',
        'code_quality': '.code_quality_results.json'
    }
    
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    if not reports_dir.exists():
        logger.debug(f"No results directory found for {model}/app{app_num}")
        return results
    
    # Load specific analysis type if requested
    if analysis_type and analysis_type in analysis_files:
        file_path = reports_dir / analysis_files[analysis_type]
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    results[analysis_type] = json.load(f)
                logger.debug(f"Loaded {analysis_type} results for {model}/app{app_num}")
            except Exception as e:
                logger.error(f"Error loading {analysis_type} results for {model}/app{app_num}: {e}")
                results[analysis_type] = {'error': str(e)}
    else:
        # Load all available analysis results
        for analysis_name, file_name in analysis_files.items():
            file_path = reports_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        results[analysis_name] = json.load(f)
                    logger.debug(f"Loaded {analysis_name} results for {model}/app{app_num}")
                except Exception as e:
                    logger.error(f"Error loading {analysis_name} results for {model}/app{app_num}: {e}")
                    results[analysis_name] = {'error': str(e)}
    
    return results


def get_available_analysis_results(model: str, app_num: int) -> List[str]:
    """
    Get list of available analysis results for a model/app combination.
    
    Args:
        model: Model name
        app_num: Application number
        
    Returns:
        List of available analysis types
    """
    analysis_files = {
        'backend_security': '.backend_security_results.json',
        'frontend_security': '.frontend_security_results.json',
        'zap_scan': 'zap_results.json',  # Updated to match actual file pattern
        'performance': 'performance_results.json',
        'gpt4all': '.openrouter_requirements.json',
        'code_quality': '.code_quality_results.json'
    }
    
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    available = []
    if reports_dir.exists():
        for analysis_name, file_name in analysis_files.items():
            file_path = reports_dir / file_name
            if file_path.exists():
                available.append(analysis_name)
    
    return available


def get_latest_analysis_timestamp(model: str, app_num: int) -> Optional[str]:
    """
    Get the timestamp of the most recent analysis for a model/app.
    
    Args:
        model: Model name
        app_num: Application number
        
    Returns:
        ISO timestamp string or None if no results found
    """
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    if not reports_dir.exists():
        return None
    
    latest_time = None
    for file_path in reports_dir.glob("*.json"):
        try:
            stat = file_path.stat()
            if latest_time is None or stat.st_mtime > latest_time:
                latest_time = stat.st_mtime
        except Exception:
            continue
    
    if latest_time:
        return datetime.fromtimestamp(latest_time).isoformat()
    return None


def clear_container_cache(model: Optional[str] = None, app_num: Optional[int] = None) -> None:
    """
    Clear container cache for specific app or all apps.
    
    Args:
        model: Model name (optional, clears all if None)
        app_num: Application number (optional, clears all if None)
    """
    with _cache_lock:
        if model and app_num:
            # Clear specific app cache
            keys_to_remove = []
            prefix = f"{model}:{app_num}:"
            for key in _container_cache:
                if key.startswith(prefix):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del _container_cache[key]
                
            logger.debug(f"Cleared cache for {model}/app{app_num}")
        else:
            # Clear all cache
            _container_cache.clear()
            logger.debug("Cleared all container cache")
    
    # Also clear Docker project names cache if requested
    if model and app_num:
        with _docker_cache_lock:
            docker_key = f"{model}:{app_num}"
            _docker_project_names_cache.pop(docker_key, None)
    elif model is None and app_num is None:
        with _docker_cache_lock:
            _docker_project_names_cache.clear()


def clear_docker_caches() -> None:
    """Clear all Docker-related caches."""
    global DOCKER_AVAILABLE, DOCKER_COMPOSE_AVAILABLE
    
    with _cache_lock:
        _container_cache.clear()
    
    with _docker_cache_lock:
        _docker_project_names_cache.clear()
    
    # Reset Docker availability flags to force re-check
    DOCKER_AVAILABLE = None
    DOCKER_COMPOSE_AVAILABLE = None
    
    logger.info("Cleared all Docker caches and reset availability flags")


def get_bulk_container_statuses(apps: List[Dict[str, Any]], 
                               docker_manager: DockerManager) -> Dict[str, Dict[str, Any]]:
    """
    Get container statuses for multiple applications efficiently.
    
    Args:
        apps: List of app dictionaries with 'model' and 'app_num' keys
        docker_manager: DockerManager instance
        
    Returns:
        Dictionary mapping "model:app_num" to status data
    """
    results = {}
    
    # Group apps by model for more efficient processing
    apps_by_model = {}
    for app in apps:
        model = app.get('model')
        if model not in apps_by_model:
            apps_by_model[model] = []
        apps_by_model[model].append(app)
    
    # Process each model's apps
    for model, model_apps in apps_by_model.items():
        for app in model_apps:
            app_num = app.get('app_num')
            if app_num:
                key = f"{model}:{app_num}"
                try:
                    status = get_app_container_statuses_cached(model, app_num, docker_manager)
                    results[key] = status
                except Exception as e:
                    logger.error(f"Error getting status for {model}/app{app_num}: {e}")
                    results[key] = {
                        "backend": {},
                        "frontend": {},
                        "success": False,
                        "error": str(e)
                    }
    
    return results


def refresh_container_cache_background(apps: List[Dict[str, Any]], 
                                     docker_manager: DockerManager) -> None:
    """
    Refresh container cache in the background.
    
    Args:
        apps: List of app dictionaries
        docker_manager: DockerManager instance
    """
    def refresh_worker():
        try:
            logger.info("Starting background cache refresh")
            
            # Clear old cache
            clear_container_cache()
            
            # Pre-populate cache directly without using Flask context-dependent functions
            refresh_cache_directly(apps, docker_manager)
            
            logger.info("Background cache refresh completed")
        except Exception as e:
            logger.error(f"Background cache refresh failed: {e}")
    
    # Start refresh in background thread
    thread = threading.Thread(target=refresh_worker, daemon=True)
    thread.start()


def refresh_cache_directly(apps: List[Dict[str, Any]], docker_manager: DockerManager) -> None:
    """
    Refresh cache directly without Flask application context dependencies.
    Uses proper sanitization for container name generation.
    
    Args:
        apps: List of app dictionaries
        docker_manager: DockerManager instance
    """
    for app in apps:
        model = app.get('model')
        app_num = app.get('app_num')
        
        if not model or not app_num:
            continue
            
        try:
            # Use direct cache approach without Flask context
            cache_key = f"{model}:{app_num}:status"
            
            # Get container names using sanitized project name generation
            backend_port = app.get('backend_port')
            frontend_port = app.get('frontend_port')
            
            if backend_port and frontend_port:
                # Generate container names using proper sanitization
                project_name = get_docker_project_name(model, app_num)
                backend_name = f"{project_name}_backend_{backend_port}"
                frontend_name = f"{project_name}_frontend_{frontend_port}"
                
                # Get container statuses
                backend_status = docker_manager.get_container_status(backend_name)
                frontend_status = docker_manager.get_container_status(frontend_name)
                
                result = {
                    "backend": backend_status.to_dict() if backend_status else {},
                    "frontend": frontend_status.to_dict() if frontend_status else {},
                    "success": True
                }
                
                # Cache the result
                with _cache_lock:
                    _container_cache[cache_key] = {
                        'data': result,
                        'timestamp': time.time()
                    }
                
                logger.debug(f"Cached status for {model}/app{app_num} in background")
            
        except Exception as e:
            logger.warning(f"Failed to cache status for {model}/app{app_num}: {e}")


def get_dashboard_data_optimized(docker_manager: DockerManager) -> Dict[str, Any]:
    """
    Get optimized dashboard data with caching and bulk operations.
    
    Args:
        docker_manager: DockerManager instance
        
    Returns:
        Dictionary containing all dashboard data
    """
    try:
        # Get basic app info
        all_apps = get_all_apps()
        
        # Get bulk container statuses efficiently
        container_statuses = get_bulk_container_statuses(all_apps, docker_manager)
        
        # Enhance app data with container statuses
        enhanced_apps = []
        for app in all_apps:
            app_key = f"{app['model']}:{app['app_num']}"
            status_data = container_statuses.get(app_key, {})
            
            # Add container status to app data
            app_enhanced = app.copy()
            app_enhanced['backend_status'] = status_data.get('backend', {})
            app_enhanced['frontend_status'] = status_data.get('frontend', {})
            app_enhanced['container_success'] = status_data.get('success', False)
            
            enhanced_apps.append(app_enhanced)
        
        # Get models
        models = get_ai_models()
        
        # Start background cache warming (non-blocking) - use safe version
        try:
            warm_container_cache_safe(all_apps, docker_manager)
        except Exception as e:
            logger.warning(f"Background cache warming failed: {e}")
        
        return {
            'apps': enhanced_apps,
            'models': models,
            'cache_used': True,
            'total_apps': len(enhanced_apps)
        }
        
    except Exception as e:
        logger.error(f"Error getting optimized dashboard data: {e}")
        return {
            'apps': [],
            'models': [],
            'cache_used': False,
            'error': str(e)
        }


def warm_container_cache(docker_manager: DockerManager) -> bool:
    """
    Warm up the container cache by pre-loading all app statuses.
    
    Args:
        docker_manager: DockerManager instance
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Warming up container cache...")
        
        # Get all apps - but handle the context issue
        try:
            from flask import has_app_context
            if has_app_context():
                all_apps = get_all_apps()
            else:
                # If no app context, skip warming and return success
                logger.warning("No Flask app context available, skipping cache warming")
                return True
        except ImportError:
            # Fallback if Flask is not available
            logger.warning("Flask not available, skipping cache warming")
            return True
        
        # Pre-load cache in background
        refresh_container_cache_background(all_apps, docker_manager)
        
        logger.info(f"Cache warming initiated for {len(all_apps)} apps")
        return True
        
    except Exception as e:
        logger.error(f"Error warming container cache: {e}")
        return False


def warm_container_cache_safe(apps: List[Dict[str, Any]], docker_manager: DockerManager) -> bool:
    """
    Safely warm up the container cache with provided app data.
    This version doesn't require Flask application context.
    
    Args:
        apps: List of app dictionaries
        docker_manager: DockerManager instance
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Safely warming up container cache for {len(apps)} apps...")
        
        # Pre-load cache in background
        refresh_container_cache_background(apps, docker_manager)
        
        logger.info(f"Safe cache warming initiated for {len(apps)} apps")
        return True
        
    except Exception as e:
        logger.error(f"Error in safe cache warming: {e}")
        return False


def get_cache_stats() -> Dict[str, Any]:
    """
    Get container cache statistics including Docker-specific caches.
    
    Returns:
        Dictionary with cache statistics
    """
    current_time = time.time()
    
    with _cache_lock:
        active_entries = 0
        expired_entries = 0
        
        for key, cached_data in _container_cache.items():
            if current_time - cached_data['timestamp'] < _cache_timeout:
                active_entries += 1
            else:
                expired_entries += 1
    
    with _docker_cache_lock:
        docker_active = 0
        docker_expired = 0
        
        for key, cached_data in _docker_project_names_cache.items():
            if current_time - cached_data['timestamp'] < _cache_timeout:
                docker_active += 1
            else:
                docker_expired += 1
    
    return {
        'container_cache': {
            'total_entries': len(_container_cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
        },
        'docker_names_cache': {
            'total_entries': len(_docker_project_names_cache),
            'active_entries': docker_active,
            'expired_entries': docker_expired,
        },
        'cache_timeout': _cache_timeout,
        'docker_available': DOCKER_AVAILABLE,
        'docker_compose_available': DOCKER_COMPOSE_AVAILABLE
    }


def get_docker_system_status() -> Dict[str, Any]:
    """
    Get comprehensive Docker system status.
    
    Returns:
        Dictionary with Docker system information
    """
    status = {
        'docker_available': is_docker_available(),
        'docker_compose_available': is_docker_compose_available(),
        'cache_stats': get_cache_stats(),
        'timestamp': datetime.now().isoformat()
    }
    
    if status['docker_available']:
        try:
            # Get Docker version info
            result = subprocess.run(
                ["docker", "version", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                docker_info = json.loads(result.stdout)
                status['docker_version'] = {
                    'client': docker_info.get('Client', {}).get('Version', 'Unknown'),
                    'server': docker_info.get('Server', {}).get('Version', 'Unknown')
                }
        except Exception as e:
            status['docker_version_error'] = str(e)
        
        # Get running containers count
        try:
            result = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                running_containers = len([line.strip() for line in result.stdout.strip().split('\n') if line.strip()])
                status['running_containers'] = running_containers
        except Exception as e:
            status['container_count_error'] = str(e)
    
    return status


def cleanup_expired_cache() -> None:
    """
    Clean up expired cache entries from both container and Docker name caches.
    """
    current_time = time.time()
    
    # Clean container cache
    with _cache_lock:
        expired_keys = []
        
        for key, cached_data in _container_cache.items():
            if current_time - cached_data['timestamp'] >= _cache_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _container_cache[key]
        
        container_cleaned = len(expired_keys)
    
    # Clean Docker names cache
    with _docker_cache_lock:
        expired_keys = []
        
        for key, cached_data in _docker_project_names_cache.items():
            if current_time - cached_data['timestamp'] >= _cache_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _docker_project_names_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


def diagnose_docker_issues(model: str, app_num: int) -> Dict[str, Any]:
    """
    Diagnose common Docker issues for a specific application.
    
    Args:
        model: Model name
        app_num: Application number
        
    Returns:
        Dictionary with diagnostic information and suggested fixes
    """
    diagnostics = {
        'model': model,
        'app_num': app_num,
        'timestamp': datetime.now().isoformat(),
        'issues': [],
        'suggestions': [],
        'status': 'healthy'
    }
    
    try:
        # Check Docker availability
        if not is_docker_available():
            diagnostics['issues'].append('Docker is not available or not running')
            diagnostics['suggestions'].append('Start Docker Desktop and ensure it is running properly')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        if not is_docker_compose_available():
            diagnostics['issues'].append('Docker Compose is not available')
            diagnostics['suggestions'].append('Install Docker Compose or ensure it is in your PATH')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        # Check application directory
        try:
            app_dir = get_app_directory(model, app_num)
            diagnostics['app_directory'] = str(app_dir)
        except FileNotFoundError:
            diagnostics['issues'].append(f'Application directory not found for {model}/app{app_num}')
            diagnostics['suggestions'].append('Verify the model name and app number are correct')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        # Check for compose file
        compose_file = None
        for filename in ["docker-compose.yml", "docker-compose.yaml"]:
            potential_path = app_dir / filename
            if potential_path.exists():
                compose_file = potential_path
                break
        
        if not compose_file:
            diagnostics['issues'].append('No docker-compose file found')
            diagnostics['suggestions'].append('Ensure docker-compose.yml exists in the application directory')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        diagnostics['compose_file'] = str(compose_file)
        
        # Check project name and potential conflicts
        project_name = get_docker_project_name(model, app_num)
        diagnostics['project_name'] = project_name
        
        # Check for conflicting containers
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={project_name}", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip().split('\t')
                        containers.append({
                            'name': parts[0],
                            'status': parts[1] if len(parts) > 1 else 'unknown'
                        })
                
                diagnostics['existing_containers'] = containers
                
                # Check for stopped containers that might cause conflicts
                stopped_containers = [c for c in containers if 'Exited' in c['status']]
                if stopped_containers:
                    diagnostics['issues'].append(f'Found {len(stopped_containers)} stopped containers that may cause conflicts')
                    diagnostics['suggestions'].append('Run cleanup action to remove stopped containers')
                    if diagnostics['status'] == 'healthy':
                        diagnostics['status'] = 'warning'
        
        except Exception as e:
            diagnostics['issues'].append(f'Could not check for container conflicts: {e}')
            diagnostics['suggestions'].append('Docker may be experiencing issues')
            if diagnostics['status'] == 'healthy':
                diagnostics['status'] = 'warning'
        
        # Check port availability
        app_config = get_app_config_by_model_and_number(model, app_num)
        if app_config:
            backend_port = app_config.get('backend_port')
            frontend_port = app_config.get('frontend_port')
            
            diagnostics['ports'] = {
                'backend': backend_port,
                'frontend': frontend_port
            }
            
            # Simple port check (this is basic, real port checking would need socket operations)
            if not backend_port or not frontend_port:
                diagnostics['issues'].append('Port configuration is incomplete')
                diagnostics['suggestions'].append('Check port_config.json for missing port assignments')
                if diagnostics['status'] == 'healthy':
                    diagnostics['status'] = 'warning'
        
        # If no issues found, everything looks good
        if not diagnostics['issues']:
            diagnostics['suggestions'].append('Docker setup appears to be healthy')
        
    except Exception as e:
        diagnostics['issues'].append(f'Unexpected error during diagnosis: {e}')
        diagnostics['suggestions'].append('Check application logs for more details')
        diagnostics['status'] = 'error'
    
    return diagnostics


def reset_docker_environment() -> Tuple[bool, str]:
    """
    Reset Docker environment by clearing caches and checking availability.
    
    Returns:
        Tuple of (success, message)
    """
    try:
        logger.info("Resetting Docker environment...")
        
        # Clear all caches
        clear_docker_caches()
        
        # Force re-check of Docker availability
        docker_available = is_docker_available()
        compose_available = is_docker_compose_available()
        
        # Cleanup any expired cache entries
        cleanup_expired_cache()
        
        # Get fresh system status
        system_status = get_docker_system_status()
        
        if docker_available and compose_available:
            message = "Docker environment reset successfully. Docker and Docker Compose are available."
        elif docker_available:
            message = "Docker environment reset. Docker is available but Docker Compose is not."
        else:
            message = "Docker environment reset. Docker is not available - please start Docker Desktop."
        
        logger.info(message)
        return True, message
        
    except Exception as e:
        error_msg = f"Error resetting Docker environment: {e}"
        logger.error(error_msg)
        return False, error_msg