"""
Service Classes and Utilities
=============================

Core service classes for Docker management, system health monitoring,
scan management, and port configuration management.
"""

import enum
import json
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import NotFound
from docker.models.containers import Container

from logging_service import create_logger_for_component


def safe_int_env(key: str, default: int) -> int:
    """
    Safely parse an integer from environment variables.
    
    Args:
        key: Environment variable key
        default: Default value if parsing fails
        
    Returns:
        Parsed integer or default value
    """
    value = os.getenv(key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


class Config:
    """Configuration constants for services."""
    DOCKER_TIMEOUT = safe_int_env("DOCKER_TIMEOUT", 10)


class ScanStatus(enum.Enum):
    """Enumeration of possible scan statuses."""
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    STOPPED = "Stopped"
    ERROR = "Error"


@dataclass
class EnhancedModelInfo:
    """Enhanced model information combining all three JSON sources."""
    name: str
    color: str = "#666666"
    provider: str = "unknown"
    
    # From port_config.json
    port_configs: List[Dict[str, Any]] = field(default_factory=list)
    
    # From model_capabilities.json
    context_length: int = 0
    pricing: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_reasoning: bool = False
    max_tokens: int = 0
    description: str = ""
    
    # From models_summary.json
    apps_per_model: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'color': self.color,
            'provider': self.provider,
            'port_configs': self.port_configs,
            'context_length': self.context_length,
            'pricing': self.pricing,
            'capabilities': self.capabilities,
            'supports_vision': self.supports_vision,
            'supports_function_calling': self.supports_function_calling,
            'supports_reasoning': self.supports_reasoning,
            'max_tokens': self.max_tokens,
            'description': self.description,
            'apps_per_model': self.apps_per_model,
            'total_apps': len(self.port_configs)
        }


@dataclass
class DockerStatus:
    """
    Docker container status information.
    
    Attributes:
        exists: Whether the container exists
        running: Whether the container is running
        health: Container health status
        status: Container status string
        details: Additional status details
    """
    exists: bool = False
    running: bool = False
    health: str = "unknown"
    status: str = "unknown"
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "exists": self.exists,
            "running": self.running,
            "health": self.health,
            "status": self.status,
            "details": self.details
        }


class DockerManager:
    """
    Docker container management service.
    
    Provides methods for managing Docker containers, checking their status,
    and performing operations like restart and cleanup.
    """
    
    def __init__(self, client: Optional[docker.DockerClient] = None) -> None:
        """
        Initialize DockerManager.
        
        Args:
            client: Optional Docker client instance
        """
        self.logger = create_logger_for_component('docker')
        self.client = client or self._create_docker_client()
        self._lock = threading.RLock()

    def _create_docker_client(self) -> Optional[docker.DockerClient]:
        """
        Create a Docker client instance.
        
        Returns:
            Docker client or None if creation fails
        """
        try:
            default_host = (
                "npipe:////./pipe/docker_engine" if os.name == 'nt'
                else "unix://var/run/docker.sock"
            )
            docker_host = os.getenv("DOCKER_HOST", default_host)
            client = docker.DockerClient(base_url=docker_host, timeout=Config.DOCKER_TIMEOUT)
            client.ping()
            self.logger.info("Docker client created and verified")
            return client
        except Exception as e:
            self.logger.error(f"Docker client creation failed: {e}")
            return None

    def get_container_status(self, container_name: str) -> DockerStatus:
        if not container_name or not isinstance(container_name, str):
            return DockerStatus(exists=False, status="invalid", details="Invalid container name")
        if not self.client:
            return DockerStatus(exists=False, status="error", details="Docker client unavailable")
        try:
            with self._lock:
                container = self.client.containers.get(container_name)
            container_status = container.status
            is_running = container_status == "running"
            state = container.attrs.get("State", {})
            health_info = state.get("Health")
            if health_info and isinstance(health_info, dict):
                health_status = health_info.get("Status", "checking")
            elif is_running:
                health_status = "healthy"
            else:
                health_status = container_status
            return DockerStatus(
                exists=True,
                running=is_running,
                health=health_status,
                status=container_status,
                details=state.get("Status", "unknown"),
            )
        except NotFound:
            return DockerStatus(exists=False, status="no_container", details="Container not found")
        except Exception as e:
            self.logger.error(f"Error fetching status for {container_name}: {e}")
            return DockerStatus(exists=False, status="error", details=str(e))

    def get_container(self, container_name: str) -> Optional[Container]:
        if not self.client:
            return None
        try:
            with self._lock:
                return self.client.containers.get(container_name)
        except NotFound:
            return None
        except Exception as e:
            self.logger.error(f"Error getting container {container_name}: {e}")
            return None

    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        if not self.client:
            return "Docker client unavailable"
        container = self.get_container(container_name)
        if not container:
            return f"Container '{container_name}' not found"
        try:
            logs = container.logs(tail=tail).decode("utf-8", errors="replace")
            return logs
        except Exception as e:
            self.logger.error(f"Log retrieval failed for {container_name}: {e}")
            return f"Log retrieval error: {e}"

    def cleanup_containers(self) -> None:
        if not self.client:
            return
        try:
            result = self.client.containers.prune(filters={"until": "24h"})
            containers_deleted = result.get('ContainersDeleted', [])
            if containers_deleted:
                self.logger.info(f"Removed {len(containers_deleted)} old containers")
            else:
                self.logger.debug("No old containers to remove")
        except Exception as e:
            self.logger.error(f"Container cleanup failed: {e}")

    def restart_container(self, container_name: str, timeout: int = 10) -> Tuple[bool, str]:
        if not self.client:
            return False, "Docker client unavailable"
        container = self.get_container(container_name)
        if not container:
            return False, f"Container '{container_name}' not found"
        try:
            container.restart(timeout=timeout)
            self.logger.info(f"Container {container_name} restarted successfully")
            return True, f"Container {container_name} restarted successfully"
        except Exception as e:
            self.logger.error(f"Error restarting container {container_name}: {e}")
            return False, f"Error restarting container: {str(e)}"

    def is_docker_available(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def get_docker_version(self) -> str:
        if not self.client:
            return None
        try:
            version_info = self.client.version()
            return version_info.get("Version", "Unknown")
        except Exception as e:
            self.logger.error(f"Error fetching Docker version: {e}")
            return None

    def get_compose_version(self) -> str:
        """Get Docker Compose version by running docker-compose --version command."""
        try:
            import subprocess
            # Try different commands for different Docker Compose installations
            commands = [
                ["docker", "compose", "version", "--short"],
                ["docker-compose", "--version"],
                ["docker", "compose", "--version"]
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=5,
                        shell=True if os.name == 'nt' else False
                    )
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        # Extract version number from different output formats
                        if "version" in output.lower():
                            # Extract version number (e.g., "v2.29.7" or "2.29.7")
                            import re
                            version_match = re.search(r'v?(\d+\.\d+\.\d+)', output)
                            if version_match:
                                return version_match.group(1)
                        return output.split('\n')[0]  # Return first line
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            self.logger.warning("Could not determine Docker Compose version")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching Docker Compose version: {e}")
            return None


class SystemHealthMonitor:
    @staticmethod
    def check_docker_connection(docker_client: Optional[docker.DockerClient]) -> bool:
        if not docker_client:
            return False
        try:
            docker_client.ping()
            return True
        except Exception:
            return False

    @classmethod
    def check_health(cls, docker_client: Optional[docker.DockerClient]) -> bool:
        logger = create_logger_for_component('health')
        docker_ok = cls.check_docker_connection(docker_client)
        if docker_ok:
            logger.info("System health check passed")
        else:
            logger.warning("System health check failed - Docker unavailable")
        return docker_ok


class PortManager:
    def __init__(self, port_config: List[Dict[str, Any]]):
        self.logger = create_logger_for_component('port_manager')
        self.port_config = port_config
        self._model_app_cache = {}
        self._build_cache()

    def _build_cache(self) -> None:
        self._model_app_cache = {}
        for config in self.port_config:
            model_name = config.get('model_name')
            app_number = config.get('app_number')
            if model_name and app_number:
                key = f"{model_name}-{app_number}"
                self._model_app_cache[key] = config
        self.logger.info(f"Built port cache with {len(self._model_app_cache)} entries")

    def get_app_config(self, model_name: str, app_number: int) -> Optional[Dict[str, Any]]:
        key = f"{model_name}-{app_number}"
        return self._model_app_cache.get(key)

    def get_app_ports(self, model_name: str, app_number: int) -> Optional[Dict[str, int]]:
        config = self.get_app_config(model_name, app_number)
        if not config:
            return None
        return {
            "backend": config.get('backend_port'),
            "frontend": config.get('frontend_port')
        }

    def get_model_apps(self, model_name: str) -> List[Dict[str, Any]]:
        return [
            config for config in self.port_config
            if config.get('model_name') == model_name
        ]

    def get_all_models(self) -> List[str]:
        return list(set(
            config.get('model_name') for config in self.port_config
            if config.get('model_name')
        ))

    def get_port_ranges(self) -> Dict[str, Dict[str, int]]:
        if not self.port_config:
            return {"backend": {"min": 0, "max": 0}, "frontend": {"min": 0, "max": 0}}
        backend_ports = [
            config.get('backend_port') for config in self.port_config
            if config.get('backend_port')
        ]
        frontend_ports = [
            config.get('frontend_port') for config in self.port_config
            if config.get('frontend_port')
        ]
        return {
            "backend": {
                "min": min(backend_ports) if backend_ports else 0,
                "max": max(backend_ports) if backend_ports else 0
            },
            "frontend": {
                "min": min(frontend_ports) if frontend_ports else 0,
                "max": max(frontend_ports) if frontend_ports else 0
            }
        }

    def is_port_in_use(self, port: int) -> bool:
        for config in self.port_config:
            if (config.get('backend_port') == port or
                config.get('frontend_port') == port):
                return True
        return False

    def validate_config(self) -> List[str]:
        issues = []
        used_ports = set()
        for i, config in enumerate(self.port_config):
            required_fields = ['model_name', 'app_number', 'backend_port', 'frontend_port']
            missing_fields = [field for field in required_fields if not config.get(field)]
            if missing_fields:
                issues.append(f"Configuration {i}: Missing fields {missing_fields}")
                continue
            backend_port = config.get('backend_port')
            frontend_port = config.get('frontend_port')
            if backend_port in used_ports:
                issues.append(f"Configuration {i}: Backend port {backend_port} already in use")
            else:
                used_ports.add(backend_port)
            if frontend_port in used_ports:
                issues.append(f"Configuration {i}: Frontend port {frontend_port} already in use")
            else:
                used_ports.add(frontend_port)
            if not (1 <= backend_port <= 65535):
                issues.append(f"Configuration {i}: Invalid backend port {backend_port}")
            if not (1 <= frontend_port <= 65535):
                issues.append(f"Configuration {i}: Invalid frontend port {frontend_port}")
        return issues

    def get_statistics(self) -> Dict[str, Any]:
        if not self.port_config:
            return {
                "total_apps": 0,
                "total_models": 0,
                "port_ranges": self.get_port_ranges(),
                "apps_per_model": {}
            }
        models = {}
        for config in self.port_config:
            model_name = config.get('model_name')
            if model_name:
                models[model_name] = models.get(model_name, 0) + 1
        return {
            "total_apps": len(self.port_config),
            "total_models": len(models),
            "port_ranges": self.get_port_ranges(),
            "apps_per_model": models
        }


class ScanManager:
    def __init__(self):
        self.logger = create_logger_for_component('scan_manager')
        self.scans: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_scan(self, model: str, app_num: int, options: dict) -> str:
        scan_id = f"{model}-{app_num}-{int(time.time())}"
        with self._lock:
            self.scans[scan_id] = {
                "status": ScanStatus.STARTING.value,
                "progress": 0,
                "scanner": None,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "options": options,
                "model": model,
                "app_num": app_num,
                "results": None,
            }
        self.logger.info(f"Created scan '{scan_id}' for {model}/app{app_num}")
        return scan_id

    def get_scan_details(self, scan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.scans.get(scan_id)

    def get_latest_scan_for_app(self, model: str, app_num: int) -> Optional[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            matching_scans = [
                (sid, scan) for sid, scan in self.scans.items()
                if sid.startswith(f"{model}-{app_num}-")
            ]
            if not matching_scans:
                return None
            try:
                latest_scan_id, latest_scan_data = max(
                    matching_scans,
                    key=lambda item: int(item[0].split('-')[-1])
                )
                return latest_scan_id, latest_scan_data
            except (ValueError, IndexError) as e:
                self.logger.error(f"Error parsing scan IDs for {model}/app{app_num}: {e}")
                return None

    def update_scan(self, scan_id: str, **kwargs: Any) -> bool:
        with self._lock:
            if scan_id in self.scans:
                if 'status' in kwargs and kwargs['status'] in (
                    ScanStatus.COMPLETE.value, ScanStatus.FAILED.value,
                    ScanStatus.STOPPED.value, ScanStatus.ERROR.value
                ):
                    kwargs.setdefault('end_time', datetime.now().isoformat())
                self.scans[scan_id].update(kwargs)
                return True
            return False

    def cleanup_old_scans(self, max_age_hours: int = 1) -> int:
        cleanup_count = 0
        current_time = datetime.now()
        max_age = timedelta(hours=max_age_hours)
        terminal_statuses = {
            ScanStatus.COMPLETE.value, ScanStatus.FAILED.value,
            ScanStatus.STOPPED.value, ScanStatus.ERROR.value
        }
        with self._lock:
            scan_ids_to_remove = []
            for scan_id, scan in self.scans.items():
                if scan.get("status") in terminal_statuses:
                    try:
                        completion_time_str = scan.get("end_time") or scan.get("start_time")
                        if completion_time_str:
                            completion_time = datetime.fromisoformat(completion_time_str)
                            if current_time - completion_time > max_age:
                                scan_ids_to_remove.append(scan_id)
                    except (ValueError, TypeError):
                        continue
            for scan_id in scan_ids_to_remove:
                del self.scans[scan_id]
                cleanup_count += 1
        if cleanup_count > 0:
            self.logger.info(f"Cleaned up {cleanup_count} old scans")
        return cleanup_count


class ModelIntegrationService:
    """Service for integrating model information from JSON files."""
    
    def __init__(self, base_path: Optional[Path] = None):
        """Initialize the service with the base path for JSON files."""
        self.logger = create_logger_for_component('model_integration')
        self.base_path = base_path or Path.cwd()
        self.models_data = {}
        self._raw_data = {
            'port_config': [],
            'model_capabilities': {},
            'models_summary': {}
        }
        self.load_all_data()
    
    def load_all_data(self) -> bool:
        """Load all model data from the three JSON files."""
        success = True
        
        # Load port_config.json
        try:
            port_config_path = self.base_path / "port_config.json"
            if port_config_path.exists():
                with open(port_config_path, 'r', encoding='utf-8') as f:
                    self._raw_data['port_config'] = json.load(f)
                self.logger.info(f"Loaded {len(self._raw_data['port_config'])} port configurations")
            else:
                self.logger.warning(f"Port config file not found: {port_config_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load port_config.json: {e}")
            success = False
        
        # Load model_capabilities.json
        try:
            capabilities_path = self.base_path / "model_capabilities.json"
            if capabilities_path.exists():
                with open(capabilities_path, 'r', encoding='utf-8') as f:
                    capabilities_data = json.load(f)
                    self._raw_data['model_capabilities'] = capabilities_data.get('models', {})
                self.logger.info(f"Loaded capabilities for {len(self._raw_data['model_capabilities'])} models")
            else:
                self.logger.warning(f"Capabilities file not found: {capabilities_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load model_capabilities.json: {e}")
            success = False
        
        # Load models_summary.json
        try:
            summary_path = self.base_path / "models_summary.json"
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    self._raw_data['models_summary'] = json.load(f)
                self.logger.info(f"Loaded models summary with {self._raw_data['models_summary'].get('total_models', 0)} models")
            else:
                self.logger.warning(f"Summary file not found: {summary_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load models_summary.json: {e}")
            success = False
        
        if success:
            self._integrate_model_data()
        
        return success
    
    def _integrate_model_data(self):
        """Integrate data from all three sources into unified model objects."""
        self.models_data = {}
        
        # Start with port configurations to identify all models
        port_configs_by_model = {}
        for config in self._raw_data['port_config']:
            model_name = config.get('model_name', '')
            if model_name:
                if model_name not in port_configs_by_model:
                    port_configs_by_model[model_name] = []
                port_configs_by_model[model_name].append(config)
        
        # Create model lookup from summary
        summary_models = {
            model['name']: model 
            for model in self._raw_data['models_summary'].get('models', [])
        }
        
        # Integrate all data sources
        for model_name, port_configs in port_configs_by_model.items():
            model_info = EnhancedModelInfo(name=model_name)
            model_info.port_configs = port_configs
            
            # Add summary data
            if model_name in summary_models:
                summary = summary_models[model_name]
                model_info.color = summary.get('color', model_info.color)
                model_info.provider = summary.get('provider', model_info.provider)
            
            # Add capabilities data
            if model_name in self._raw_data['model_capabilities']:
                caps = self._raw_data['model_capabilities'][model_name]
                model_info.context_length = caps.get('context_length', 0)
                model_info.pricing = caps.get('pricing', {})
                model_info.capabilities = caps.get('capabilities', [])
                model_info.supports_vision = caps.get('supports_vision', False)
                model_info.supports_function_calling = caps.get('supports_function_calling', False)
                model_info.supports_reasoning = 'reasoning' in model_info.capabilities
                model_info.max_tokens = caps.get('max_tokens', 0)
                model_info.description = caps.get('description', '')
            
            # Set apps per model from summary
            model_info.apps_per_model = self._raw_data['models_summary'].get('apps_per_model', 0)
            
            self.models_data[model_name] = model_info
        
        self.logger.info(f"Integrated data for {len(self.models_data)} models")
    
    def get_all_models(self) -> List[EnhancedModelInfo]:
        """Get all integrated model information."""
        return list(self.models_data.values())
    
    def get_model(self, model_name: str) -> Optional[EnhancedModelInfo]:
        """Get a specific model by name."""
        return self.models_data.get(model_name)
    
    def get_models_by_provider(self, provider: str) -> List[EnhancedModelInfo]:
        """Get all models from a specific provider."""
        return [
            model for model in self.models_data.values()
            if model.provider == provider
        ]
    
    def get_models_with_capability(self, capability: str) -> List[EnhancedModelInfo]:
        """Get all models that have a specific capability."""
        return [
            model for model in self.models_data.values()
            if capability in model.capabilities
        ]
    
    def get_vision_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support vision."""
        return [
            model for model in self.models_data.values()
            if model.supports_vision
        ]
    
    def get_function_calling_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support function calling."""
        return [
            model for model in self.models_data.values()
            if model.supports_function_calling
        ]
    
    def get_reasoning_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support reasoning."""
        return [
            model for model in self.models_data.values()
            if model.supports_reasoning
        ]
    
    def get_port_config_for_model(self, model_name: str, app_num: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get port configuration for a specific model and app."""
        model = self.get_model(model_name)
        if not model:
            return None
        
        if app_num is None:
            return model.port_configs[0] if model.port_configs else None
        
        for config in model.port_configs:
            if config.get('app_number') == app_num:
                return config
        
        return None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about all models."""
        if not self.models_data:
            return {}
        
        providers = set(model.provider for model in self.models_data.values())
        all_capabilities = set()
        for model in self.models_data.values():
            all_capabilities.update(model.capabilities)
        
        return {
            'total_models': len(self.models_data),
            'unique_providers': len(providers),
            'providers': list(providers),
            'total_capabilities': len(all_capabilities),
            'capabilities': list(all_capabilities),
            'vision_models': len(self.get_vision_models()),
            'function_calling_models': len(self.get_function_calling_models()),
            'reasoning_models': len(self.get_reasoning_models()),
            'avg_context_length': (
                sum(m.context_length for m in self.models_data.values()) // len(self.models_data)
                if self.models_data else 0
            ),
            'total_port_configs': sum(len(m.port_configs) for m in self.models_data.values()),
            'apps_per_model': self._raw_data['models_summary'].get('apps_per_model', 0)
        }
    
    def export_integrated_data(self, output_path: Optional[Path] = None) -> Path:
        """Export the integrated model data to a JSON file."""
        if output_path is None:
            output_path = self.base_path / "integrated_models.json"
        
        export_data = {
            'metadata': {
                'generated_at': str(Path().cwd()),
                'total_models': len(self.models_data),
                'data_sources': ['port_config.json', 'model_capabilities.json', 'models_summary.json']
            },
            'summary_stats': self.get_summary_stats(),
            'models': {
                name: model.to_dict()
                for name, model in self.models_data.items()
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported integrated model data to {output_path}")
        return output_path
    
    def refresh_data(self) -> bool:
        """Refresh all data from JSON files."""
        return self.load_all_data()


# Global service instance
_global_service: Optional[ModelIntegrationService] = None


def get_model_service() -> ModelIntegrationService:
    """Get the global model integration service instance."""
    global _global_service
    if _global_service is None:
        _global_service = ModelIntegrationService()
    return _global_service


def initialize_model_service(base_path: Optional[Path] = None) -> ModelIntegrationService:
    """Initialize the global model integration service."""
    global _global_service
    _global_service = ModelIntegrationService(base_path)
    return _global_service


def create_scanner(base_path):
    logger = create_logger_for_component('zap_init')
    try:
        from zap_scanner import create_scanner as zap_create_scanner
        return zap_create_scanner(base_path)
    except ImportError as e:
        logger.error(f"Failed to import ZAP scanner module: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating ZAP scanner: {e}")
        return None