"""
Common utility functions to reduce code duplication.
"""

import logging
from typing import Any, Callable, Dict, Optional, Union
from functools import wraps

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


def deduplicate_list(items: list, key_func: Optional[Callable] = None) -> list:
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