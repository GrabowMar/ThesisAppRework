"""
Service Management for Thesis Research App
==========================================

Unified service management system that consolidates ServiceManager and ServiceLocator
patterns into a single, consistent interface.
"""

import logging
import threading
from typing import Any, Dict, Optional, Type, TypeVar
from flask import Flask, current_app, has_app_context

try:
    from .constants import ServiceNames
except ImportError:
    from constants import ServiceNames

T = TypeVar("T")


class ServiceRegistry:
    """Thread-safe service registry with singleton pattern."""

    _instance: Optional["ServiceRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ServiceRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self.services: Dict[str, Any] = {}
            self.service_factories: Dict[str, callable] = {}
            self._service_lock = threading.RLock()
            self.logger = logging.getLogger(__name__)
            self._initialized = True

    def register_service(self, name: str, service: Any) -> None:
        """Register a service instance."""
        with self._service_lock:
            self.services[name] = service
            self.logger.info(f"Registered service: {name}")

    def register_factory(self, name: str, factory: callable) -> None:
        """Register a service factory for lazy initialization."""
        with self._service_lock:
            self.service_factories[name] = factory
            self.logger.info(f"Registered service factory: {name}")

    def get_service(self, name: str) -> Optional[Any]:
        """Get a service by name, creating it if a factory is registered."""
        with self._service_lock:
            # Return existing service if available
            if name in self.services:
                return self.services[name]

            # Create service using factory if available
            if name in self.service_factories:
                try:
                    service = self.service_factories[name]()
                    self.services[name] = service
                    self.logger.info(f"Created service from factory: {name}")
                    return service
                except Exception as e:
                    self.logger.error(f"Failed to create service {name}: {e}")
                    return None

            return None

    def unregister_service(self, name: str) -> bool:
        """Unregister a service."""
        with self._service_lock:
            removed = name in self.services
            self.services.pop(name, None)
            self.service_factories.pop(name, None)
            if removed:
                self.logger.info(f"Unregistered service: {name}")
            return removed

    def list_services(self) -> Dict[str, bool]:
        """List all services and their availability."""
        with self._service_lock:
            return {
                name: name in self.services
                for name in set(self.services.keys())
                | set(self.service_factories.keys())
            }

    def clear(self) -> None:
        """Clear all services (for testing)."""
        with self._service_lock:
            self.services.clear()
            self.service_factories.clear()
            self.logger.info("Cleared all services")


class ServiceManager:
    """Application service manager for Flask integration."""

    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.registry = ServiceRegistry()

        if app is not None:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Initialize service manager with Flask app."""
        self.app = app
        app.config["service_manager"] = self

        # Register core service factories
        self._register_core_factories()

        # Initialize services asynchronously
        threading.Thread(target=self._initialize_services_async, daemon=True).start()

    def _register_core_factories(self) -> None:
        """Register factory functions for core services."""

        def docker_manager_factory():
            try:
                from .core_services import DockerManager
            except (ImportError, ValueError):
                try:
                    from core_services import DockerManager
                except ImportError:
                    self.logger.warning("Could not import DockerManager")
                    return None
            return DockerManager()

        def scan_manager_factory():
            try:
                from .core_services import ScanManager
            except (ImportError, ValueError):
                try:
                    from core_services import ScanManager
                except ImportError:
                    self.logger.warning("Could not import ScanManager")
                    return None
            return ScanManager()

        def model_service_factory():
            try:
                from .core_services import ModelIntegrationService
            except (ImportError, ValueError):
                try:
                    from core_services import ModelIntegrationService
                except ImportError:
                    self.logger.warning("Could not import ModelIntegrationService")
                    return None
            # Initialize with Flask app for database access
            service = ModelIntegrationService(self.app)
            return service

        def port_manager_factory():
            try:
                from .core_services import PortManager
            except (ImportError, ValueError):
                try:
                    from core_services import PortManager
                except ImportError:
                    self.logger.warning("Could not import PortManager")
                    return None
            # Load port configuration
            import json

            try:
                from .constants import Paths
            except (ImportError, ValueError):
                try:
                    from constants import Paths
                except ImportError:
                    self.logger.warning("Could not import Paths from constants")
                    return PortManager([])

            try:
                with open(Paths.PORT_CONFIG) as f:
                    port_config = json.load(f)
                return PortManager(port_config)
            except Exception as e:
                self.logger.warning(f"Failed to load port config: {e}")
                return PortManager([])

        def batch_service_factory():
            try:
                from .core_services import BatchAnalysisService
            except (ImportError, ValueError):
                try:
                    from core_services import BatchAnalysisService
                except ImportError:
                    self.logger.warning("Could not import BatchAnalysisService")
                    return None
            return BatchAnalysisService()

        def performance_service_factory():
            # Simplified factory - just return a lightweight service
            class PerformanceServiceStub:
                def __init__(self):
                    self.name = "performance_service"

                def get_stats(self):
                    return {"available": True, "type": "performance"}

            return PerformanceServiceStub()

        def zap_service_factory():
            # Simplified factory - just return a lightweight service
            class ZapServiceStub:
                def __init__(self):
                    self.name = "zap_service"

                def get_stats(self):
                    return {"available": True, "type": "zap"}

            return ZapServiceStub()

        def security_service_factory():
            # Simplified factory - just return a lightweight service
            class SecurityServiceStub:
                def __init__(self):
                    self.name = "security_service"

                def get_stats(self):
                    return {"available": True, "type": "security"}

            return SecurityServiceStub()

        def openrouter_service_factory():
            """Factory for OpenRouter analysis service."""
            try:
                from .core_services import OpenRouterAnalysisService
            except (ImportError, ValueError):
                try:
                    from core_services import OpenRouterAnalysisService
                except ImportError:
                    self.logger.warning("Could not import OpenRouterAnalysisService")
                    return None
            return OpenRouterAnalysisService()

        def model_validation_service_factory():
            """Factory for model validation service."""
            try:
                import sqlite3
                from pathlib import Path

                class ModelValidationService:
                    """Service to validate and retrieve real models."""

                    def __init__(self):
                        self.db_path = Path("src/data/thesis_app.db")
                        self.logger = logging.getLogger(__name__)

                    def get_real_models(self):
                        """Get all real models from database."""
                        try:
                            if not self.db_path.exists():
                                self.logger.warning("Database not found")
                                return []

                            conn = sqlite3.connect(str(self.db_path))
                            cursor = conn.cursor()

                            cursor.execute(
                                "SELECT provider, model_name, canonical_slug FROM model_capabilities "
                                "ORDER BY provider, model_name;"
                            )
                            models = cursor.fetchall()
                            conn.close()

                            return [
                                {
                                    "provider": provider,
                                    "model_name": model_name,
                                    "canonical_slug": canonical_slug,
                                    "display_name": f"{provider}/{model_name}",
                                }
                                for provider, model_name, canonical_slug in models
                            ]
                        except Exception as e:
                            self.logger.error(f"Failed to get models: {e}")
                            return []

                    def validate_model(self, model_slug):
                        """Validate if a model exists in the database."""
                        try:
                            if not self.db_path.exists():
                                return False

                            conn = sqlite3.connect(str(self.db_path))
                            cursor = conn.cursor()

                            cursor.execute(
                                "SELECT COUNT(*) FROM model_capabilities WHERE canonical_slug = ?",
                                (model_slug,),
                            )
                            count = cursor.fetchone()[0]
                            conn.close()

                            return count > 0
                        except Exception as e:
                            self.logger.error(
                                f"Failed to validate model {model_slug}: {e}"
                            )
                            return False

                    def get_popular_models(self):
                        """Get a subset of popular/recommended models."""
                        all_models = self.get_real_models()

                        # Priority order for popular models
                        popular_providers = [
                            "anthropic",
                            "openai",
                            "google",
                            "deepseek",
                            "mistralai",
                        ]
                        popular_models = []

                        for provider in popular_providers:
                            provider_models = [
                                m for m in all_models if m["provider"] == provider
                            ]
                            if provider_models:
                                # Add the first model from each popular provider
                                popular_models.append(provider_models[0])

                        return popular_models[:10]  # Return top 10

                return ModelValidationService()
            except Exception as e:
                self.logger.warning(f"Could not create ModelValidationService: {e}")
                return None

        # Register factories
        self.registry.register_factory(
            ServiceNames.DOCKER_MANAGER, docker_manager_factory
        )
        self.registry.register_factory(ServiceNames.SCAN_MANAGER, scan_manager_factory)
        self.registry.register_factory(
            ServiceNames.MODEL_SERVICE, model_service_factory
        )
        self.registry.register_factory(ServiceNames.PORT_MANAGER, port_manager_factory)
        self.registry.register_factory(
            ServiceNames.BATCH_SERVICE, batch_service_factory
        )
        self.registry.register_factory(
            ServiceNames.PERFORMANCE_SERVICE, performance_service_factory
        )
        self.registry.register_factory(ServiceNames.ZAP_SERVICE, zap_service_factory)
        self.registry.register_factory(
            ServiceNames.SECURITY_SERVICE, security_service_factory
        )
        self.registry.register_factory("OPENROUTER_SERVICE", openrouter_service_factory)
        self.registry.register_factory(
            "MODEL_VALIDATION_SERVICE", model_validation_service_factory
        )

    def _initialize_services_async(self) -> None:
        """Initialize services asynchronously to prevent blocking startup."""
        try:
            with self.app.app_context():
                # Pre-load critical services
                critical_services = [
                    ServiceNames.DOCKER_MANAGER,
                    ServiceNames.MODEL_SERVICE,
                ]

                for service_name in critical_services:
                    try:
                        service = self.registry.get_service(service_name)
                        if service:
                            self.logger.info(
                                f"Initialized critical service: {service_name}"
                            )
                    except Exception as e:
                        self.logger.error(f"Failed to initialize {service_name}: {e}")

                self.logger.info("Core services initialization completed")
        except Exception as e:
            self.logger.error(f"Service initialization failed: {e}")

    def get_service(self, name: str) -> Optional[Any]:
        """Get a service by name."""
        return self.registry.get_service(name)

    def register_service(self, name: str, service: Any) -> None:
        """Register a service instance."""
        self.registry.register_service(name, service)

    def register_factory(self, name: str, factory: callable) -> None:
        """Register a service factory."""
        self.registry.register_factory(name, factory)

    def get_all_services(self) -> Dict[str, bool]:
        """Get status of all services."""
        return self.registry.list_services()


class ServiceLocator:
    """Simplified service locator for easy access to services."""

    @staticmethod
    def get_service(service_name: str) -> Optional[Any]:
        """Get a service by name from current app context."""
        if has_app_context():
            service_manager = current_app.config.get("service_manager")
            if service_manager:
                return service_manager.get_service(service_name)

        # Fallback to global registry
        registry = ServiceRegistry()
        return registry.get_service(service_name)

    @staticmethod
    def get_docker_manager():
        """Get Docker manager service."""
        return ServiceLocator.get_service(ServiceNames.DOCKER_MANAGER)

    @staticmethod
    def get_scan_manager():
        """Get scan manager service."""
        return ServiceLocator.get_service(ServiceNames.SCAN_MANAGER)

    @staticmethod
    def get_model_service():
        """Get model integration service."""
        return ServiceLocator.get_service(ServiceNames.MODEL_SERVICE)

    @staticmethod
    def get_port_manager():
        """Get port manager service."""
        return ServiceLocator.get_service(ServiceNames.PORT_MANAGER)

    @staticmethod
    def get_batch_service():
        """Get batch analysis service."""
        return ServiceLocator.get_service(ServiceNames.BATCH_SERVICE)

    @staticmethod
    def get_performance_service():
        """Get performance testing service."""
        return ServiceLocator.get_service(ServiceNames.PERFORMANCE_SERVICE)

    @staticmethod
    def get_zap_service():
        """Get ZAP scanning service."""
        return ServiceLocator.get_service(ServiceNames.ZAP_SERVICE)

    @staticmethod
    def get_security_service():
        """Get security analysis service."""
        return ServiceLocator.get_service(ServiceNames.SECURITY_SERVICE)

    @staticmethod
    def get_openrouter_service():
        """Get OpenRouter analysis service."""
        return ServiceLocator.get_service("OPENROUTER_SERVICE")

    @staticmethod
    def get_model_validation_service():
        """Get model validation service."""
        return ServiceLocator.get_service("MODEL_VALIDATION_SERVICE")


def get_service(name: str, service_type: Type[T] = None) -> Optional[T]:
    """
    Convenience function to get a service with optional type checking.

    Args:
        name: Service name
        service_type: Expected service type for type hints

    Returns:
        Service instance or None
    """
    return ServiceLocator.get_service(name)


def register_external_service(name: str, service: Any) -> None:
    """Register an external service in the global registry."""
    registry = ServiceRegistry()
    registry.register_service(name, service)


# Initialize global registry
_global_registry = ServiceRegistry()
