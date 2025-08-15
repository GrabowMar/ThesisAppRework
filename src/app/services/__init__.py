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
from .batch_service import BatchAnalysisService, batch_service
from .security_service import SecurityService, security_service
from .task_manager import TaskManager
from .analyzer_integration import AnalyzerIntegration
from .model_service import ModelService

# Note on legacy services:
# - AnalyzerService: removed in favor of AnalyzerIntegration + Celery tasks
# - ContainerService: removed (unused stub)
# - PortService: internal only (not exported)

__all__ = [
    'ServiceLocator',
    'DockerManager',
    'BatchAnalysisService',
    'batch_service',
    'SecurityService',
    'security_service',
    'TaskManager',
    'AnalyzerIntegration',
    'ModelService',
]
