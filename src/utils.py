"""
Common utility functions to reduce code duplication.
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling utilities."""

    @staticmethod
    def handle_database_error(operation: str, error: Exception) -> dict[str, Any]:
        """Standard database error handling."""
        logger.error(f"Database error during {operation}: {error}")
        return {
            'success': False,
            'error': f'Database error: {str(error)}',
            'operation': operation
        }

    @staticmethod
    def handle_docker_error(operation: str, model: str, app_num: int, error: Exception) -> dict[str, Any]:
        """Standard Docker operation error handling."""
        logger.error(f"Docker error during {operation} for {model}/app{app_num}: {error}")

        # Provide user-friendly error messages
        error_msg = str(error)
        if "Nie można odnaleźć określonego pliku" in error_msg or "dockerDesktopLinuxEngine" in error_msg:
            error_msg = "Docker Desktop is not running. Please start Docker Desktop and try again."
        elif "unable to get image" in error_msg:
            error_msg = "Docker image not found. Please ensure the application is properly built."
        elif "No such container" in error_msg:
            error_msg = "Container not found. Please start the application first."

        return {
            'success': False,
            'error': error_msg,
            'operation': operation,
            'model': model,
            'app_num': app_num
        }

    @staticmethod
    def safe_execute(func: Callable, default_return: Any = None, operation: str = "operation") -> Any:
        """Safely execute a function with error logging."""
        try:
            return func()
        except Exception as e:
            logger.error(f"Error during {operation}: {e}")
            return default_return


class ModelValidator:
    """Common model validation utilities."""

    @staticmethod
    def get_model_by_slug(model_slug: str, error_response_handler=None):
        """Get model by canonical slug with standard error handling."""
        try:
            # Import here to avoid circular imports
            from models import ModelCapability

            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if not model and error_response_handler:
                return error_response_handler("Model not found", 404)
            return model
        except Exception as e:
            logger.error(f"Error fetching model {model_slug}: {e}")
            if error_response_handler:
                return error_response_handler("Database error", 500)
            return None

    @staticmethod
    def validate_app_number(app_num: Any, min_val: int = 1, max_val: int = 30) -> tuple[bool, int | None]:
        """Validate app number is within valid range."""
        try:
            app_number = int(app_num)
            if min_val <= app_number <= max_val:
                return True, app_number
            return False, None
        except (ValueError, TypeError):
            return False, None


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert a value to integer."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_dict_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value."""
    current = data
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def deduplicate_list(items: list, key_func: Callable | None = None) -> list:
    """Remove duplicates from a list, optionally using a key function."""
    if key_func is None:
        return list(dict.fromkeys(items))

    seen = set()
    result = []
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
