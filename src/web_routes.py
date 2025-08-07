"""
Flask Web Routes - Thesis Research App (Refactored)
==================================================

This module has been refactored to use a modular route structure.
The original 5700+ line file has been split into focused modules:

- routes/main_routes.py: Dashboard and main application routes
- routes/api_routes.py: RESTful API endpoints
- routes/docker_routes.py: Docker container management
- routes/utils.py: Shared utilities and classes

This file now serves as a compatibility layer, importing and re-exporting
the necessary components to maintain backward compatibility with existing code.

Version: 4.0.0 (Refactored)
"""

import logging

# Import the new modular routes
try:
    from .routes import register_blueprints
except ImportError:
    from routes import register_blueprints

# Import key components for backward compatibility
try:
    from .routes.blueprint_registry import (
        main_bp, api_bp, simple_api_bp, models_bp, containers_bp, 
        docker_bp, get_settings, statistics_bp, testing_bp, analysis_bp,
        batch_bp, files_bp
    )
    from .routes.utils import (
        ResponseHandler, ServiceLocator, AppDataProvider, DockerOperations,
        log_performance
    )
except ImportError:
    from routes.blueprint_registry import (
        main_bp, api_bp, simple_api_bp, models_bp, containers_bp, 
        docker_bp, get_settings, statistics_bp, testing_bp, analysis_bp,
        batch_bp, files_bp
    )
    from routes.utils import (
        ResponseHandler, ServiceLocator, AppDataProvider, DockerOperations,
        log_performance
    )

# Legacy imports that tests and other modules might expect - now imported above
# statistics_bp, testing_bp, analysis_bp, batch_bp, files_bp are now available

# Import specific testing route for unified_cli_analyzer compatibility
try:
    from .unified_cli_analyzer import UnifiedCLIAnalyzer, ToolCategory
except ImportError:
    UnifiedCLIAnalyzer = None
    ToolCategory = None

logger = logging.getLogger(__name__)

def get_unified_cli_analyzer():
    """Get unified CLI analyzer service - compatibility function."""
    try:
        if UnifiedCLIAnalyzer:
            return UnifiedCLIAnalyzer()
        return None
    except Exception as e:
        logger.warning(f"Could not get unified CLI analyzer: {e}")
        return None


# Additional helper functions for backward compatibility
def get_app_status(model: str, app_num: int) -> dict:
    """Get application status - compatibility function."""
    try:
        return AppDataProvider.get_app_info(model, app_num)
    except Exception as e:
        logger.error(f"Error getting app status: {e}")
        return {'status': 'error', 'error': str(e)}


def get_container_logs(model: str, app_num: int, container_type: str = 'backend') -> str:
    """Get container logs - compatibility function."""
    try:
        return DockerOperations.get_logs(model, app_num, container_type)
    except Exception as e:
        logger.error(f"Error getting container logs: {e}")
        return f"Error getting logs: {str(e)}"


def get_app_files(model: str, app_num: int) -> list:
    """Get application files - compatibility function."""
    try:
        # Mock implementation for now
        return []
    except Exception as e:
        logger.error(f"Error getting app files: {e}")
        return []


def get_file_content(file_path: str) -> str:
    """Get file content - compatibility function."""
    try:
        # Mock implementation for now
        return ""
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return ""


# Export all the key blueprint and function names for backward compatibility
__all__ = [
    'main_bp', 'api_bp', 'simple_api_bp', 'statistics_bp', 'models_bp', 
    'containers_bp', 'analysis_bp', 'batch_bp', 'testing_bp', 'files_bp',
    'docker_bp', 'register_blueprints', 'get_settings', 'ResponseHandler',
    'ServiceLocator', 'AppDataProvider', 'DockerOperations', 'log_performance',
    'get_unified_cli_analyzer', 'get_app_status', 'get_container_logs',
    'get_app_files', 'get_file_content'
]