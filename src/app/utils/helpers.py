"""
Utility Functions for Celery App

Common utility functions used throughout the application.
"""

import json
import logging
from datetime import datetime, UTC
from pathlib import Path
import re
from typing import Dict, Any, Optional, Union

try:  # Import path constants; keep optional to avoid circular issues in early migrations
    from app.paths import GENERATED_APPS_DIR
except Exception:  # pragma: no cover - fallback if paths not ready
    GENERATED_APPS_DIR = Path(__file__).resolve().parents[3] / 'generated' / 'apps'

logger = logging.getLogger(__name__)


# Common chat/completions parameter metadata for OpenAI-compatible APIs (incl. OpenRouter)
# Defaults are typical values; actual model/provider defaults may vary.
PARAMETER_METADATA: Dict[str, Dict[str, Any]] = {
    'temperature': {
        'type': 'number',
        'default': 1.0,
        'range': [0.0, 2.0],
        'notes': 'Controls randomness. Lower is more deterministic.'
    },
    'top_p': {
        'type': 'number',
        'default': 1.0,
        'range': [0.0, 1.0],
        'notes': 'Nucleus sampling; consider adjusting either temperature or top_p, not both.'
    },
    'top_k': {
        'type': 'integer',
        'default': None,
        'range': [1, 1000],
        'notes': 'Controls candidate pool size for some models; ignored by others.'
    },
    'max_tokens': {
        'type': 'integer',
        'default': None,
        'range': [1, None],
        'notes': 'Maximum output tokens; capped by model max and context limits.'
    },
    'presence_penalty': {
        'type': 'number',
        'default': 0.0,
        'range': [-2.0, 2.0],
        'notes': 'Penalizes new tokens based on whether they appear in text so far.'
    },
    'frequency_penalty': {
        'type': 'number',
        'default': 0.0,
        'range': [-2.0, 2.0],
        'notes': 'Penalizes new tokens based on frequency in text so far.'
    },
    'stop': {
        'type': 'string|string[]',
        'default': None,
        'notes': 'Up to 4 sequences where API will stop generating further tokens.'
    },
    'logit_bias': {
        'type': 'object',
        'default': None,
        'notes': 'Mapping of token ID to bias; support varies by model/provider.'
    },
    'tools': {
        'type': 'object[]',
        'default': None,
        'notes': 'Tool/function definitions for tool calling; schema depends on provider.'
    },
    'response_format': {
        'type': 'object',
        'default': None,
        'notes': 'e.g., {"type":"json_object"} to request structured JSON where supported.'
    },
    'stream': {
        'type': 'boolean',
        'default': False,
        'notes': 'Enable Server-Sent Events (SSE) streaming of tokens.'
    },
}


def get_parameter_metadata(param_names: Optional[list[str]]) -> Dict[str, Dict[str, Any]]:
    """Return metadata for a subset of parameter names.

    If param_names is None or empty, returns the full registry.
    """
    if not param_names:
        return PARAMETER_METADATA
    return {p: PARAMETER_METADATA.get(p, {'type': 'unknown', 'notes': 'No metadata available'}) for p in param_names}


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


def _project_root_from_helpers() -> Path:
    """Resolve project root relative to this helpers module (src/app/utils/helpers.py)."""
    return Path(__file__).resolve().parents[4]


def get_models_base_path() -> Path:
    """Absolute path to the misc/models directory in the project."""
    return _project_root_from_helpers() / "misc" / "models"


def _normalize_slug_for_match(s: str) -> str:
    """Normalize slugs for fuzzy matching: lowercase and remove non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def utc_now() -> datetime:
    """Return a timezone-aware UTC datetime.

    Central helper to avoid direct use of deprecated utcnow() and to
    provide a single place to adjust time source if we later introduce
    clock abstraction (e.g., for testing or monotonic sequencing).
    """
    return datetime.now(UTC)


def now() -> datetime:
    """Return current timezone-aware datetime for Jinja templates.
    
    This function is registered as a Jinja global to provide current time
    in templates without needing to pass it from every route.
    """
    return datetime.now(UTC)


def make_safe_dom_id(value: str, prefix: Optional[str] = None) -> str:
    """Create a DOM-safe id from an arbitrary string.

    Replaces characters that are invalid in CSS selectors (spaces, dots, colons,
    brackets, etc.) with hyphens and ensures the id starts with a letter or
    underscore (prefixing with 'id-' when necessary).
    """
    if value is None:
        value = ""

    # Replace sequences of invalid characters with a single hyphen
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", value)

    # IDs must not start with a digit in CSS selectors for some older browsers;
    # ensure it starts with a letter or underscore.
    if not re.match(r"^[A-Za-z_].*", safe):
        safe = f"id-{safe}"

    # Optionally add a prefix (e.g., 'model-')
    if prefix:
        return f"{prefix}{safe}"

    return safe


def _resolve_model_directory(model_slug: str, base_path: Optional[Path] = None) -> Path:
    """Resolve the directory for a model slug, trying common variations.

    Heuristics:
    - Exact match under base_path
    - Hyphen/underscore/dot variations
    - Case-insensitive and punctuation-insensitive match among existing dirs
    """
    base_dir = base_path or get_models_base_path()

    # 1) Exact match
    exact = base_dir / model_slug
    if exact.exists() and exact.is_dir():
        return exact

    # 2) Try direct variations
    variations = {
        model_slug.replace("-", "_"),
        model_slug.replace("_", "-"),
        model_slug.replace(".", "-"),
        model_slug.replace(".", "_")
    }
    for v in variations:
        cand = base_dir / v
        if cand.exists() and cand.is_dir():
            return cand

    # 3) Fuzzy match among existing directories
    try:
        target_norm = _normalize_slug_for_match(model_slug)
        for child in base_dir.iterdir():
            if not child.is_dir():
                continue
            name = child.name
            if name.startswith("_"):
                # skip special folders like _logs
                continue
            if _normalize_slug_for_match(name) == target_norm:
                return child
    except Exception:
        # fall through to default
        pass

    # 4) As a final fallback, return the exact path (may not exist)
    return exact


def get_app_directory(model_slug: str, app_number: int, base_path: Optional[Path] = None) -> Path:
    """Return path to generated app directory.

    Resolution order (non‑destructive, backwards compatible):
      1. New unified path: generated/apps/<model_slug>/appN
      2. Template-based structure: generated/apps/<model_slug>/<template>/appN
      3. Legacy misc/models path (older layout)
      4. Fallback to resolved model directory heuristic (for unusual cases)
    """
    # 1) Prefer new generated/apps structure (flat layout)
    try:
        gen_model_dir = GENERATED_APPS_DIR / model_slug
        if gen_model_dir.exists():
            candidate = gen_model_dir / f"app{app_number}"
            if candidate.exists():
                return candidate
            # Some generations used app_# pattern
            alt = gen_model_dir / f"app_{app_number}"
            if alt.exists():
                return alt
            
            # 2) Search template subdirectories (template-based layout)
            for template_dir in gen_model_dir.iterdir():
                if template_dir.is_dir() and not template_dir.name.startswith('.'):
                    template_candidate = template_dir / f"app{app_number}"
                    if template_candidate.exists():
                        return template_candidate
                    # Check app_# pattern in template dirs too
                    template_alt = template_dir / f"app_{app_number}"
                    if template_alt.exists():
                        return template_alt
            
            # Even if not present, return canonical expected path for creation
            return candidate
    except Exception:
        pass

    # 2) Legacy misc/models path
    legacy_base = _project_root_from_helpers() / "misc" / "models" / model_slug
    legacy_candidate = legacy_base / f"app{app_number}"
    if legacy_candidate.exists():
        return legacy_candidate
    legacy_alt = legacy_base / f"app_{app_number}"
    if legacy_alt.exists():
        return legacy_alt

    # 3) Fallback heuristic (may not exist)
    model_dir = _resolve_model_directory(model_slug, base_path or (_project_root_from_helpers() / "misc" / "models"))
    return model_dir / f"app{app_number}"


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


def create_error_response(error: str, code: int = 500, details: Optional[Dict[str, Any]] = None, error_type: Optional[str] = None, **extra: Any) -> Dict[str, Any]:
    """Create standardized error response (backward compatible).

    Migration Notes:
    - Legacy keys: success, error, code, timestamp, details retained.
    - New unified schema keys added: status, status_code, message, error_id, path.
    - Prefer using build_error_payload directly for new endpoints.
    """
    try:
        from app.utils.errors import build_error_payload  # local import to avoid cycles
        payload = build_error_payload(
            error,
            status=code,
            error=error_type or error,
            details=details if details else None,
            **extra
        )
        # Backward compatibility fields
        payload.setdefault('success', False)
        payload.setdefault('code', code)
        payload.setdefault('error', error_type or error)
        if details:
            payload.setdefault('details', details)
        return payload
    except Exception:  # pragma: no cover - fallback path
        response = {
            'success': False,
            'error': error_type or error,
            'code': code,
            'timestamp': datetime.now().isoformat()
        }
        if details:
            response['details'] = details
        response.update(extra)
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


def dicts_to_csv(rows: list[dict], fieldnames: Optional[list[str]] = None) -> str:
    """Convert list of dictionaries to CSV string.

    Args:
        rows: List of dictionaries with uniform keys.
        fieldnames: Optional explicit header order.

    Returns:
        CSV content as string (including header row).
    """
    import csv
    from io import StringIO

    output = StringIO()
    if not rows:
        # Emit minimal header if none provided
        writer = csv.writer(output)
        writer.writerow(fieldnames or ["provider", "model_name", "slug"])
        return output.getvalue()

    if fieldnames is None:
        # Preserve insertion order of first row
        fieldnames = list(rows[0].keys())

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return output.getvalue()


def json_success(data: Any = None, message: str = "Success", **kwargs) -> tuple[Dict[str, Any], int]:
    """Create a standardized JSON success response (adds unified keys)."""
    response = {
        'success': True,
        'status': 'success',
        'status_code': 200,
        'message': message,
        'timestamp': datetime.now(UTC).isoformat(),
    }
    if data is not None:
        response['data'] = data
    response.update(kwargs)
    return response, 200


def json_error(message: str, code: int = 400, details: Optional[Dict[str, Any]] = None, error_type: Optional[str] = None, **kwargs) -> tuple[Dict[str, Any], int]:
    """Create a standardized JSON error response (delegates to unified builder).

    Parameters:
        message: Human readable message
        code: HTTP status code
        details: Optional extra detail structure
        error_type: Machine readable error identifier (falls back to message)
    """
    payload = create_error_response(message, code=code, details=details, error_type=error_type, **kwargs)
    return payload, code
