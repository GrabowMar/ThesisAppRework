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
        
        try:
            from .analyzer_service import AnalyzerService
        except ImportError:
            AnalyzerService = None
            
        try:
            from .container_service import ContainerService
        except ImportError:
            ContainerService = None
            
        try:
            from .port_service import PortService
        except ImportError:
            PortService = None
            
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
        
        if AnalyzerService:
            cls.register('analyzer_service', AnalyzerService(app))
        if ContainerService:
            cls.register('container_service', ContainerService(app))
        if PortService:
            cls.register('port_service', PortService(app))
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
    def get_analyzer_service(cls):
        """Get the analyzer service."""
        return cls.get('analyzer_service')
    
    @classmethod
    def get_container_service(cls):
        """Get the container service."""
        return cls.get('container_service')
    
    @classmethod
    def get_port_service(cls):
        """Get the port service."""
        return cls.get('port_service')
    
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
