"""
Utility Functions for Celery App

Common utility functions used throughout the application.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)


def safe_json_loads(json_str: Optional[str], default: Any = None) -> Any:
    """Safely load JSON string with fallback."""
    if not json_str:
        return default
    
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        logger.warning(f"Failed to parse JSON: {json_str}")
        return default


def safe_json_dumps(obj: Any, default: str = "{}") -> str:
    """Safely dump object to JSON string with fallback."""
    try:
        return json.dumps(obj, default=str)
    except (TypeError, ValueError):
        logger.warning(f"Failed to serialize object to JSON: {obj}")
        return default


def format_datetime(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime object to string."""
    if not dt:
        return "N/A"
    
    try:
        return dt.strftime(format_str)
    except (AttributeError, ValueError):
        return "Invalid date"


def parse_model_slug(model_slug: str) -> Dict[str, str]:
    """Parse model slug to extract provider and model name."""
    parts = model_slug.split('_', 1)
    if len(parts) >= 2:
        return {
            'provider': parts[0],
            'model_name': parts[1].replace('_', ' ').replace('-', ' ')
        }
    return {
        'provider': 'unknown',
        'model_name': model_slug
    }


def get_app_directory(model_slug: str, app_number: int, base_path: Optional[Path] = None) -> Path:
    """Get the directory path for a specific app."""
    if base_path is None:
        base_path = Path(__file__).parent.parent.parent.parent / "misc" / "models"
    
    return base_path / model_slug / f"app{app_number}"


def check_app_exists(model_slug: str, app_number: int, base_path: Optional[Path] = None) -> bool:
    """Check if an app directory exists."""
    app_path = get_app_directory(model_slug, app_number, base_path)
    return app_path.exists() and app_path.is_dir()


def get_docker_project_name(model_slug: str, app_number: int) -> str:
    """Generate Docker Compose project name for an app."""
    # Replace problematic characters for Docker
    safe_model = model_slug.replace('_', '-').replace('.', '-')
    return f"{safe_model}-app{app_number}"


def calculate_percentage(current: int, total: int) -> float:
    """Calculate percentage with safe division."""
    if total == 0:
        return 0.0
    return round((current / total) * 100, 2)


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length."""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def validate_model_slug(model_slug: str) -> bool:
    """Validate model slug format."""
    if not model_slug:
        return False
    
    # Check for valid pattern: provider_model-name
    parts = model_slug.split('_', 1)
    return len(parts) >= 2 and all(part.strip() for part in parts)


def validate_app_number(app_number: Union[str, int]) -> bool:
    """Validate app number is in valid range."""
    try:
        num = int(app_number)
        return 1 <= num <= 30
    except (ValueError, TypeError):
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe filesystem usage."""
    import re
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    # Strip leading/trailing underscores and dots
    sanitized = sanitized.strip('_.')
    return sanitized or 'unnamed'


def deep_merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries."""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result


def extract_error_message(exception: Exception) -> str:
    """Extract clean error message from exception."""
    error_msg = str(exception)
    if not error_msg:
        error_msg = exception.__class__.__name__
    
    # Truncate very long error messages
    return truncate_text(error_msg, 200)


def is_valid_url(url: str) -> bool:
    """Check if string is a valid URL."""
    import re
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return bool(url_pattern.match(url))


def format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    return f"{size:.1f} {units[unit_index]}"


def create_error_response(error: str, code: int = 500, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Create standardized error response."""
    response = {
        'success': False,
        'error': error,
        'code': code,
        'timestamp': datetime.now().isoformat()
    }
    
    if details:
        response['details'] = details
    
    return response


def create_success_response(data: Any = None, message: str = "Success") -> Dict[str, Any]:
    """Create standardized success response."""
    response = {
        'success': True,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    
    if data is not None:
        response['data'] = data
    
    return response


def retry_operation(operation, max_retries: int = 3, delay: float = 1.0):
    """Retry an operation with exponential backoff."""
    import time
    
    for attempt in range(max_retries):
        try:
            return operation()
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            
            logger.warning(f"Operation failed (attempt {attempt + 1}/{max_retries}): {e}")
            time.sleep(delay * (2 ** attempt))


class Timer:
    """Simple context manager for timing operations."""
    
    def __init__(self, description: str = "Operation"):
        self.description = description
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        if self.start_time:
            duration = (self.end_time - self.start_time).total_seconds()
            logger.info(f"{self.description} completed in {duration:.2f} seconds")
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration in seconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
