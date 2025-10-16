"""
Services Package for Celery App

This package contains core service layer components including:
- Docker container management
- Batch processing services
- Model and analyzer integration services
- Task management services
"""

from .service_locator import ServiceLocator
from .docker_manager import DockerManager
from .task_service import BatchAnalysisService, batch_service  # export core batch_service directly
from .model_service import ModelService

# Legacy services removed: AnalyzerService, analysis_orchestrator, websocket_integration, container_service,
# huggingface_service, batch_service, batch_scheduler, analyzer_config*, analysis_config_models, results_*.
# Prefer celery_websocket_service in production and mock_websocket_service in tests.

__all__ = [
    'ServiceLocator',
    'DockerManager',
    'BatchAnalysisService',
    'batch_service',
    'ModelService',
]
