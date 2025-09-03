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
from .task_service import BatchAnalysisService, batch_service
from .security_service import SecurityService, security_service
from .analysis_service import AnalysisService, analysis_service
# from .task_manager import TaskManager  # Module not found
# from .analyzer_integration import AnalyzerIntegration  # Temporarily disabled
from .model_service import ModelService

# Legacy services removed:
# AnalyzerService, PortService, websocket_integration_v2 legacy shim.
# ContainerService/HuggingFaceService retained only as deprecated compatibility shims.

__all__ = [
    'ServiceLocator',
    'DockerManager',
    'BatchAnalysisService',
    'batch_service',
    'SecurityService',
    'security_service',
    'AnalysisService',
    'analysis_service',
    # 'TaskManager',  # Module not found
    'ModelService',
]
