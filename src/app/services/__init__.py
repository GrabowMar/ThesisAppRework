"""
Services Package for Celery App

This package contains all service layer components including:
- Docker container management
- Security analysis services  
- Batch processing services
- Model and analyzer integration services
- Task management services
"""

from .service_locator import ServiceLocator
from .docker_manager import DockerManager
from .task_service import BatchAnalysisService, batch_service as _core_batch_service
from .security_service import SecurityService, security_service
from .analysis_service import AnalysisService, analysis_service
# from .task_manager import TaskManager  # Module not found
# from .analyzer_integration import AnalyzerIntegration  # Temporarily disabled
from .model_service import ModelService

# Legacy services removed:
# AnalyzerService, PortService, websocket_integration_v2 legacy shim.
# ContainerService/HuggingFaceService retained only as deprecated compatibility shims.

 # Backward compatibility: tests expect batch_service to have create_job and _reset_for_test.
 # Our simplified legacy implementation lives in batch_service.py as BatchService.
try:  # pragma: no cover - defensive shim
    from .batch_service import batch_service as _legacy_batch_service  # type: ignore
    # Monkey patch missing legacy methods onto the core batch service reference if not present.
    for _attr in ('create_job', 'get_job_status', 'start_job', 'update_task_progress', '_reset_for_test'):
        if not hasattr(_core_batch_service, _attr) and hasattr(_legacy_batch_service, _attr):
            setattr(_core_batch_service, _attr, getattr(_legacy_batch_service, _attr))
except Exception:  # pragma: no cover
    pass

# Re-export unified batch_service symbol
batch_service = _core_batch_service

__all__ = [
    'ServiceLocator',
    'DockerManager',
    'BatchAnalysisService',
    'batch_service',  # unified object (core + legacy shim methods)
    'SecurityService',
    'security_service',
    'AnalysisService',
    'analysis_service',
    # 'TaskManager',  # Module not found
    'ModelService',
]
