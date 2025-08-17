"""
Service Locator Pattern
======================

Centralized service registry for dependency injection.
Provides clean separation between service definitions and usage.
"""

from typing import Dict, Optional, TypeVar
from flask import Flask

T = TypeVar('T')


class ServiceLocator:
    """
    Central registry for application services.
    Implements dependency injection pattern for clean architecture.
    """
    
    _services: Dict[str, object] = {}
    _app: Optional[Flask] = None
    
    @classmethod
    def initialize(cls, app: Flask):
        """Initialize the service locator with Flask app context."""
        cls._app = app
        cls._services.clear()
        
        # Register core services
        cls._register_core_services(app)
    
    @classmethod
    def _register_core_services(cls, app: Flask):
        """Register all core application services."""
        # Import services here to avoid circular imports
        from .model_service import ModelService

        # Legacy services removed: AnalyzerService, ContainerService, PortService

        try:
            from .docker_manager import DockerManager
        except ImportError:
            DockerManager = None

        try:
            from .batch_service import BatchAnalysisService
        except ImportError:
            BatchAnalysisService = None

        try:
            from .security_service import SecurityService
        except ImportError:
            SecurityService = None

        # Register available services
        cls.register('model_service', ModelService(app))

        # No registrations for removed legacy services
        if DockerManager:
            cls.register('docker_manager', DockerManager())
        if BatchAnalysisService:
            cls.register('batch_service', BatchAnalysisService())
        if SecurityService:
            cls.register('security_service', SecurityService())
    
    @classmethod
    def register(cls, name: str, service: object):
        """Register a service with the locator."""
        cls._services[name] = service
    
    @classmethod
    def get(cls, name: str, default=None):
        """Get a service by name."""
        return cls._services.get(name, default)
    
    @classmethod
    def get_model_service(cls):
        """Get the model service."""
        return cls.get('model_service')
    
    @classmethod
    def get_docker_manager(cls):
        """Get the Docker manager service."""
        return cls.get('docker_manager')
    
    @classmethod
    def get_batch_service(cls):
        """Get the batch analysis service."""
        return cls.get('batch_service')
    
    @classmethod
    def get_security_service(cls):
        """Get the security analysis service."""
        return cls.get('security_service')
    
    @classmethod
    def clear(cls):
        """Clear all registered services (for testing)."""
        cls._services.clear()
        cls._app = None
