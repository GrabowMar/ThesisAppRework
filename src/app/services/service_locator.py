"""Service Locator Pattern
=========================

Centralized service registry for dependency injection.
Now intentionally minimal: deprecated services (AnalyzerService,
ContainerService, HuggingFaceService, PortService) are no longer
registered here. Shims remain only to prevent import errors.

All new services should reuse standardized exceptions from
`service_base` and keep side-effects (threads, external processes)
outside of the Flask request path when possible.
"""

from typing import Dict, Optional, TypeVar
import logging
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
        # Import services here to avoid circular imports. Keep the list short.
        from .model_service import ModelService
        try:
            from .generation import get_generation_service
        except ImportError:  # pragma: no cover
            get_generation_service = None  # type: ignore

        try:
            from .health_service import HealthService
        except ImportError:
            HealthService = None

        try:
            from .docker_manager import DockerManager
        except ImportError:
            DockerManager = None

        try:
            from .analysis_inspection_service import AnalysisInspectionService
        except ImportError:  # pragma: no cover
            AnalysisInspectionService = None  # type: ignore

        try:
            from .unified_result_service import UnifiedResultService
        except ImportError:  # pragma: no cover
            UnifiedResultService = None  # type: ignore

        try:
            from .report_generation_service import ReportGenerationService
        except ImportError:  # pragma: no cover
            ReportGenerationService = None  # type: ignore


        # Register available services
        cls.register('model_service', ModelService(app))
        
        if get_generation_service:
            try:
                cls.register('generation_service', get_generation_service())
            except Exception as e:  # pragma: no cover
                logging.warning(f"Failed to register generation service: {e}")

        # No registrations for removed legacy services
        if DockerManager:
            cls.register('docker_manager', DockerManager())
        if AnalysisInspectionService:
            cls.register('analysis_inspection_service', AnalysisInspectionService())
        if UnifiedResultService:
            cls.register('unified_result_service', UnifiedResultService())
        if ReportGenerationService:
            cls.register('report_service', ReportGenerationService(app))
        if HealthService:
            cls.register('health_service', HealthService())

        # Best-effort: ensure PortConfiguration is populated from misc/port_config.json
        # Only done outside tests to avoid slowing the suite.
        try:
            import os as _os
            is_testing = bool(app.config.get('TESTING')) or bool(_os.environ.get('PYTEST_CURRENT_TEST'))
            if not is_testing:
                from app.models import PortConfiguration  # type: ignore
                from app.extensions import db as _db  # lazy import to avoid cycles
                # Only populate if table appears empty
                if _db.session.query(PortConfiguration).count() == 0:
                    logger = logging.getLogger(__name__)
                    logger.info("PortConfiguration empty; attempting to load from misc/port_config.json ...")
                    try:
                        from .data_initialization import DataInitializationService
                        svc = DataInitializationService()
                        res = svc.load_port_config()
                        # Commit changes
                        _db.session.commit()
                        logger.info("Loaded %s port entries (created: %s, updated: %s)", res.get('loaded', 0), res.get('created', 0), res.get('updated', 0))
                    except Exception as _port_err:
                        logger.warning("Failed to auto-load port configuration: %s", _port_err)
        except Exception:
            # Non-fatal; continue startup
            pass
    
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
    @classmethod
    def get_generation_service(cls):
        """Get the generation service."""
        return cls.get('generation_service')
    
    @classmethod
    def get_analysis_inspection_service(cls):
        """Get the analysis inspection service."""
        return cls.get('analysis_inspection_service')

    @classmethod
    def get_unified_result_service(cls):
        """Get the unified result service."""
        return cls.get('unified_result_service')

    @classmethod
    def get_health_service(cls):
        """Get the health service."""
        return cls.get('health_service')
    
    @classmethod
    def get_report_service(cls):
        """Get the report generation service."""
        return cls.get('report_service')
    
    @classmethod
    def clear(cls):
        """Clear all registered services (for testing)."""
        cls._services.clear()
        cls._app = None
