"""
Consolidated Flask Application for Thesis Research
==================================================

This module combines all services, utilities, and application components into a single file.
Provides security analysis, performance testing, ZAP scanning, batch processing, and more.
"""

# ===========================
# IMPORTS
# ===========================

import atexit
import enum
import json
import logging
import logging.handlers
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple, Type, Union

import docker
from docker.errors import NotFound
from docker.models.containers import Container
from dotenv import load_dotenv
from flask import (
    Blueprint, Flask, Response, current_app, g, has_request_context,
    jsonify, redirect, render_template, request, url_for, flash
)
from werkzeug.exceptions import BadRequest, HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

# Load environment variables
load_dotenv()

# Optional imports
try:
    import coloredlogs
    HAS_COLOREDLOGS = True
except ImportError:
    HAS_COLOREDLOGS = False

# Generation lookup service will be initialized later
generation_lookup_service = None

# ===========================
# LOGGING SERVICE
# ===========================

class ContextFilter(logging.Filter):
    """Add request context information to log records."""
    
    def filter(self, record):
        try:
            if has_request_context():
                record.request_id = getattr(g, 'request_id', '-')
            else:
                record.request_id = '-'
        except RuntimeError:
            record.request_id = '-'
        
        if '.' in record.name:
            record.component = record.name.split('.', 1)[0]
        else:
            record.component = record.name if record.name != 'root' else 'app'
        
        return True


class RequestFilter(logging.Filter):
    """Filter out noisy requests from werkzeug logs."""
    
    EXCLUDED_PATHS = {'/api/status', '/static/', '/favicon.ico'}
    
    def filter(self, record):
        if record.name != 'werkzeug':
            return True
        
        try:
            if hasattr(record, 'args') and record.args:
                request_line = str(record.args[0])
                parts = request_line.split()
                if len(parts) >= 2:
                    path = parts[1]
                    if any(excluded in path for excluded in self.EXCLUDED_PATHS):
                        status_code = record.args[1] if len(record.args) > 1 else 200
                        return status_code >= 400
        except (IndexError, ValueError, TypeError):
            pass
        
        return True


def create_file_handler(filename: Path, level: int, format_str: str) -> logging.Handler:
    """Create a rotating file handler."""
    filename.parent.mkdir(parents=True, exist_ok=True)
    
    handler = logging.handlers.RotatingFileHandler(
        filename=filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str, '%Y-%m-%d %H:%M:%S'))
    
    return handler


def setup_console_logging(logger: logging.Logger, level: int, debug_mode: bool):
    """Setup console logging with optional colors."""
    format_str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    
    if debug_mode and HAS_COLOREDLOGS:
        try:
            coloredlogs.install(
                level=level,
                logger=logger,
                fmt=format_str,
                datefmt='%Y-%m-%d %H:%M:%S',
                level_styles={
                    'debug': {'color': 'blue'},
                    'info': {'color': 'green'},
                    'warning': {'color': 'yellow'},
                    'error': {'color': 'red'},
                    'critical': {'color': 'red', 'bold': True}
                }
            )
            return
        except Exception:
            pass
    
    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(format_str, '%Y-%m-%d %H:%M:%S'))
    logger.addHandler(handler)


def initialize_logging(app: Flask):
    """Initialize logging for a Flask application."""
    log_level_name = app.config.get('LOG_LEVEL', os.getenv('LOG_LEVEL', 'INFO'))
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)
    log_dir = Path(app.config.get('LOG_DIR', 'logs'))
    
    context_filter = ContextFilter()
    request_filter = RequestFilter()
    
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    
    app_handler = create_file_handler(
        log_dir / 'app.log',
        log_level,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s: %(message)s"
    )
    app_handler.addFilter(context_filter)
    root_logger.addHandler(app_handler)
    
    error_handler = create_file_handler(
        log_dir / 'errors.log',
        logging.ERROR,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s.%(funcName)s:%(lineno)d - %(message)s"
    )
    error_handler.addFilter(context_filter)
    root_logger.addHandler(error_handler)
    
    setup_console_logging(root_logger, log_level, app.debug)
    
    werkzeug_logger = logging.getLogger('werkzeug')
    werkzeug_logger.handlers.clear()
    werkzeug_logger.setLevel(log_level)
    werkzeug_logger.propagate = False
    
    request_handler = create_file_handler(
        log_dir / 'requests.log',
        log_level,
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(message)s"
    )
    request_handler.addFilter(context_filter)
    request_handler.addFilter(request_filter)
    werkzeug_logger.addHandler(request_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", 
        '%Y-%m-%d %H:%M:%S'
    ))
    console_handler.addFilter(context_filter)
    console_handler.addFilter(request_filter)
    werkzeug_logger.addHandler(console_handler)
    
    component_levels = {
        "docker": logging.INFO,
        "zap_scanner": logging.INFO,
        "performance": logging.INFO,
        "security": logging.INFO,
    }
    
    for component, level in component_levels.items():
        logging.getLogger(component).setLevel(level)
    
    setup_request_middleware(app)
    
    logging.info(f"Logging initialized. Level: {log_level_name}, Directory: {log_dir}")


def setup_request_middleware(app: Flask):
    """Setup request logging and ID generation."""
    QUIET_PATHS = {'/static/', '/api/status', '/favicon.ico'}
    
    @app.before_request
    def before_request():
        g.request_id = str(uuid.uuid4())[:8]
        g.start_time = time.time()
        g.is_quiet = any(quiet in request.path for quiet in QUIET_PATHS)
        if not g.is_quiet:
            logging.info(f"Request: {request.method} {request.path} from {request.remote_addr}")
    
    @app.after_request
    def after_request(response):
        response.headers['X-Request-ID'] = getattr(g, 'request_id', '-')
        start_time = getattr(g, 'start_time', time.time())
        duration = time.time() - start_time
        is_quiet = getattr(g, 'is_quiet', False)
        is_error = response.status_code >= 400
        is_slow = duration > 1.0
        if is_error or is_slow or not is_quiet:
            level = logging.WARNING if is_error else logging.INFO
            status_info = f"{response.status_code}"
            if is_slow:
                status_info += " [SLOW]"
            logging.log(level, f"Response: {request.method} {request.path} - "
                             f"Status: {status_info} - Duration: {duration:.3f}s")
        return response
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        duration = time.time() - getattr(g, 'start_time', time.time())
        logging.exception(f"Unhandled exception: {request.method} {request.path} - "
                         f"Error: {e} - Duration: {duration:.3f}s")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            status_code = getattr(e, 'code', 500)
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'An error occurred'
            }), status_code
        raise e


def create_logger_for_component(component_name: str) -> logging.Logger:
    """Create a logger for a specific component."""
    return logging.getLogger(component_name)


# Initialize logger after function definition
logger = create_logger_for_component('routes')


# ===========================
# CONFIGURATION AND UTILITIES
# ===========================

def safe_int_env(key: str, default: int) -> int:
    """Safely parse an integer from environment variables."""
    value = os.getenv(key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger = create_logger_for_component('utils')
        logger.warning(f"Invalid integer value for {key}: '{value}', using default: {default}")
        return default


class Config:
    """Configuration constants for services."""
    DOCKER_TIMEOUT = safe_int_env("DOCKER_TIMEOUT", 10)


@dataclass(frozen=True)
class AppDefaults:
    """Application default configuration values."""
    CLEANUP_INTERVAL: int = 300  # 5 minutes
    IDLE_SCAN_TIMEOUT: int = 3600  # 1 hour
    MAX_ZAP_SCANS: int = 10
    HOST: str = "127.0.0.1"
    PORT: int = 5000
    MAX_THREADS: int = 50
    REQUEST_TIMEOUT: int = 30


@dataclass
class AppConfig:
    """Configuration class for application settings."""
    DEBUG: bool = os.getenv("FLASK_ENV", "development") != "production"
    SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")
    BASE_DIR: Path = Path(__file__).parent
    DOCKER_TIMEOUT: int = safe_int_env("DOCKER_TIMEOUT", 10)
    HOST: str = "0.0.0.0" if os.getenv("FLASK_ENV") == "production" else "127.0.0.1"
    PORT: int = safe_int_env("PORT", 5000)
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO" if os.getenv("FLASK_ENV") == "production" else "DEBUG")
    MODELS_BASE_DIR: Optional[str] = os.getenv("MODELS_BASE_DIR")

    def __post_init__(self):
        log_path = Path(self.LOG_DIR)
        if not log_path.is_absolute():
            log_path = self.BASE_DIR.parent / log_path
        log_path.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR = str(log_path)

        if self.SECRET_KEY == "your-secret-key-here" and not self.DEBUG:
            logger = create_logger_for_component('config')
            logger.warning("SECURITY WARNING: FLASK_SECRET_KEY is not set in production!")

        if self.MODELS_BASE_DIR is None:
            self.MODELS_BASE_DIR = str(self.BASE_DIR.parent / "models")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Create configuration instance from environment variables."""
        return cls()


# ===========================
# ENUMS AND DATA CLASSES
# ===========================

class ScanStatus(enum.Enum):
    """Enumeration of possible scan statuses."""
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    STOPPED = "Stopped"
    ERROR = "Error"


class JobStatus(enum.Enum):
    """Status of a batch job."""
    PENDING = "pending"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELLING = "cancelling"
    ARCHIVED = "archived"
    ERROR = "error"


class TaskStatus(enum.Enum):
    """Status of a batch task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class AnalysisType(enum.Enum):
    """Types of analysis that can be performed."""
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_SECURITY = "backend_security"
    PERFORMANCE = "performance"
    ZAP = "zap"
    GPT4ALL = "gpt4all"
    CODE_QUALITY = "code_quality"


@dataclass
class DockerStatus:
    """Docker container status information."""
    exists: bool = False
    running: bool = False
    health: str = "unknown"
    status: str = "unknown"
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "exists": self.exists,
            "running": self.running,
            "health": self.health,
            "status": self.status,
            "details": self.details
        }


@dataclass
class EnhancedModelInfo:
    """Enhanced model information combining all three JSON sources."""
    name: str
    color: str = "#666666"
    provider: str = "unknown"
    port_configs: List[Dict[str, Any]] = field(default_factory=list)
    context_length: int = 0
    pricing: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_reasoning: bool = False
    max_tokens: int = 0
    description: str = ""
    apps_per_model: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'name': self.name,
            'color': self.color,
            'provider': self.provider,
            'port_configs': self.port_configs,
            'context_length': self.context_length,
            'pricing': self.pricing,
            'capabilities': self.capabilities,
            'supports_vision': self.supports_vision,
            'supports_function_calling': self.supports_function_calling,
            'supports_reasoning': self.supports_reasoning,
            'max_tokens': self.max_tokens,
            'description': self.description,
            'apps_per_model': self.apps_per_model,
            'total_apps': len(self.port_configs)
        }


@dataclass
class AIModel:
    """Class representing an AI model with comprehensive information from JSON files."""
    name: str
    color: str = "#666666"
    provider: str = "unknown"
    context_length: int = 0
    pricing: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_function_calling: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return asdict(self)


@dataclass
class BatchTask:
    """Represents a single task within a batch job."""
    id: str
    job_id: str
    model: str
    app_num: int
    analysis_type: str
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, str]] = None
    issues_count: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "model": self.model,
            "app_num": self.app_num,
            "analysis_type": self.analysis_type,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "result": self.result,
            "error": self.error,
            "issues_count": self.issues_count
        }


@dataclass
class BatchJob:
    """Represents a batch analysis job."""
    id: str
    name: str
    description: str
    status: JobStatus
    analysis_types: List[AnalysisType]
    models: List[str]
    app_range: Dict[str, Any]
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Dict[str, int] = field(default_factory=lambda: {"total": 0, "completed": 0, "failed": 0})
    results: List[Dict] = field(default_factory=list)
    error_message: Optional[str] = None
    auto_start: bool = True

    @property
    def created_at_formatted(self) -> str:
        """Format created_at for display."""
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value if hasattr(self.status, 'value') else str(self.status),
            "analysis_types": [at.value if hasattr(at, 'value') else str(at) for at in self.analysis_types],
            "models": self.models,
            "app_range": self.app_range,
            "created_at": self.created_at.isoformat(),
            "created_at_formatted": self.created_at_formatted,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "results": self.results,
            "error_message": self.error_message,
            "auto_start": self.auto_start
        }


@dataclass
class GenerationMetadata:
    """Metadata for a generation run"""
    timestamp: str
    filename: str
    models_count: int
    apps_count: int
    total_successful: int
    total_failed: int
    generation_time: float
    fastest_model: str
    slowest_model: str
    most_successful_app: int
    least_successful_app: int


@dataclass
class ModelAppDetails:
    """Details for a specific model-app combination"""
    model: str
    display_name: str
    provider: str
    is_free: bool
    app_num: int
    app_name: str
    success_rate: float
    frontend_success: bool
    backend_success: bool
    total_tokens: int
    response_quality: float
    generation_time: Optional[float]
    markdown_files: List[str]
    extracted_files: List[str]
    requirements: List[str]


# ===========================
# CACHE MANAGEMENT
# ===========================

# Global cache for container status and names
_container_cache = {}
_docker_project_names_cache = {}
_cache_lock = threading.Lock()
_docker_cache_lock = threading.RLock()
_cache_timeout = 30  # Cache timeout in seconds

# Docker operation locks to prevent concurrent operations on the same project
_docker_operation_locks = {}
_docker_locks_lock = threading.RLock()

# Request deduplication to prevent multiple simultaneous requests
_active_requests = {}
_active_requests_lock = threading.RLock()

# Docker configuration
DOCKER_AVAILABLE = None
DOCKER_COMPOSE_AVAILABLE = None


def get_docker_operation_lock(project_name: str):
    """Get or create a lock for Docker operations on a specific project."""
    with _docker_locks_lock:
        if project_name not in _docker_operation_locks:
            _docker_operation_locks[project_name] = threading.RLock()
        return _docker_operation_locks[project_name]


def is_request_active(model: str, app_num: int, action: str) -> bool:
    """Check if a request for the same action on the same app is already active."""
    request_key = f"{model}_{app_num}_{action}"
    with _active_requests_lock:
        return request_key in _active_requests


def mark_request_active(model: str, app_num: int, action: str) -> str:
    """Mark a request as active and return the request key."""
    request_key = f"{model}_{app_num}_{action}"
    with _active_requests_lock:
        _active_requests[request_key] = {
            'timestamp': time.time(),
            'model': model,
            'app_num': app_num,
            'action': action
        }
    return request_key


def mark_request_complete(request_key: str):
    """Mark a request as completed."""
    with _active_requests_lock:
        _active_requests.pop(request_key, None)


def cleanup_stale_requests(max_age: int = 300):
    """Clean up stale requests that are older than max_age seconds."""
    current_time = time.time()
    with _active_requests_lock:
        stale_keys = [key for key, info in _active_requests.items() 
                     if current_time - info['timestamp'] > max_age]
        for key in stale_keys:
            _active_requests.pop(key, None)
        if stale_keys:
            logger = create_logger_for_component('utils')
            logger.debug(f"Cleaned up {len(stale_keys)} stale requests")


def cleanup_docker_operation_locks():
    """Clean up unused Docker operation locks to prevent memory leaks."""
    with _docker_locks_lock:
        if len(_docker_operation_locks) > 100:
            logger = create_logger_for_component('utils')
            logger.debug(f"Cleaning up Docker operation locks (current count: {len(_docker_operation_locks)})")
            _docker_operation_locks.clear()
            logger.debug("Docker operation locks cleared")
            return
        
        active_locks = {}
        for project_name, lock in _docker_operation_locks.items():
            if lock.acquire(blocking=False):
                lock.release()
            else:
                active_locks[project_name] = lock
        
        _docker_operation_locks.clear()
        _docker_operation_locks.update(active_locks)
        
        logger = create_logger_for_component('utils')
        logger.debug(f"Cleaned up Docker locks. Active locks: {len(active_locks)}")


def clear_container_cache(model: Optional[str] = None, app_num: Optional[int] = None) -> None:
    """Clear container cache for specific app or all apps."""
    logger = create_logger_for_component('utils')
    with _cache_lock:
        if model and app_num:
            keys_to_remove = []
            prefix = f"{model}:{app_num}:"
            for key in _container_cache:
                if key.startswith(prefix):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del _container_cache[key]
                
            logger.debug(f"Cleared cache for {model}/app{app_num}")
        else:
            _container_cache.clear()
            logger.debug("Cleared all container cache")
    
    if model and app_num:
        with _docker_cache_lock:
            docker_key = f"{model}:{app_num}"
            _docker_project_names_cache.pop(docker_key, None)
    elif model is None and app_num is None:
        with _docker_cache_lock:
            _docker_project_names_cache.clear()


def clear_docker_caches() -> None:
    """Clear all Docker-related caches."""
    global DOCKER_AVAILABLE, DOCKER_COMPOSE_AVAILABLE
    
    with _cache_lock:
        _container_cache.clear()
    
    with _docker_cache_lock:
        _docker_project_names_cache.clear()
    
    DOCKER_AVAILABLE = None
    DOCKER_COMPOSE_AVAILABLE = None
    
    logger = create_logger_for_component('utils')
    logger.info("Cleared all Docker caches and reset availability flags")


def cleanup_expired_cache() -> None:
    """Clean up expired cache entries from both container and Docker name caches."""
    logger = create_logger_for_component('utils')
    current_time = time.time()
    
    with _cache_lock:
        expired_keys = []
        
        for key, cached_data in _container_cache.items():
            if current_time - cached_data['timestamp'] >= _cache_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _container_cache[key]
        
        container_cleaned = len(expired_keys)
    
    with _docker_cache_lock:
        expired_keys = []
        
        for key, cached_data in _docker_project_names_cache.items():
            if current_time - cached_data['timestamp'] >= _cache_timeout:
                expired_keys.append(key)
        
        for key in expired_keys:
            del _docker_project_names_cache[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")


# ===========================
# DOCKER UTILITIES
# ===========================

def is_docker_available() -> bool:
    """Check if Docker is available and running."""
    global DOCKER_AVAILABLE
    logger = create_logger_for_component('utils')
    
    if DOCKER_AVAILABLE is not None:
        return DOCKER_AVAILABLE
    
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Client.Version}}"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        DOCKER_AVAILABLE = result.returncode == 0
        if DOCKER_AVAILABLE:
            logger.info("Docker is available and running")
        else:
            logger.warning("Docker is not available or not running")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.warning(f"Docker availability check failed: {e}")
        DOCKER_AVAILABLE = False
    
    return DOCKER_AVAILABLE


def is_docker_compose_available() -> bool:
    """Check if Docker Compose is available."""
    global DOCKER_COMPOSE_AVAILABLE
    logger = create_logger_for_component('utils')
    
    if DOCKER_COMPOSE_AVAILABLE is not None:
        return DOCKER_COMPOSE_AVAILABLE
    
    try:
        result = subprocess.run(
            ["docker-compose", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        DOCKER_COMPOSE_AVAILABLE = result.returncode == 0
        if DOCKER_COMPOSE_AVAILABLE:
            logger.info("Docker Compose is available")
        else:
            logger.warning("Docker Compose is not available")
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError) as e:
        logger.warning(f"Docker Compose availability check failed: {e}")
        DOCKER_COMPOSE_AVAILABLE = False
    
    return DOCKER_COMPOSE_AVAILABLE


def sanitize_docker_project_name(name: str) -> str:
    """Sanitize a string to be a valid Docker project name."""
    if not name:
        return "default"
    
    sanitized = name.lower()
    sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
    sanitized = re.sub(r'[_-]+', '_', sanitized)
    sanitized = sanitized.strip('_-')
    
    if not sanitized:
        sanitized = "default"
    elif len(sanitized) > 63:
        sanitized = sanitized[:63].rstrip('_-')
    
    return sanitized


def get_docker_project_name(model: str, app_num: int) -> str:
    """Get a sanitized Docker project name with caching."""
    logger = create_logger_for_component('utils')
    
    if not model or app_num < 1:
        raise ValueError("Invalid model name or app number")
    
    cache_key = f"{model}:{app_num}"
    
    with _docker_cache_lock:
        if cache_key in _docker_project_names_cache:
            cached_data = _docker_project_names_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                logger.debug(f"Using cached Docker project name for {model}/app{app_num}")
                return cached_data['project_name']
    
    raw_name = f"{model}_app{app_num}"
    sanitized_name = sanitize_docker_project_name(raw_name)
    
    with _docker_cache_lock:
        _docker_project_names_cache[cache_key] = {
            'project_name': sanitized_name,
            'timestamp': time.time()
        }
    
    logger.debug(f"Generated Docker project name for {model}/app{app_num}: {sanitized_name}")
    return sanitized_name


def stop_conflicting_containers(project_name: str) -> Tuple[bool, str]:
    """Comprehensive container cleanup with improved error handling and conflict resolution."""
    logger = create_logger_for_component('utils')
    
    try:
        output_parts = []
        
        with get_docker_operation_lock(project_name):
            logger.info(f"Attempting docker-compose down for project: {project_name}")
            
            down_success = False
            try:
                down_result = subprocess.run(
                    ["docker-compose", "-p", project_name, "down", "--remove-orphans", "--timeout", "15"],
                    capture_output=True,
                    text=True,
                    timeout=45,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if down_result.returncode == 0:
                    output_parts.append(f"Successfully ran docker-compose down for project: {project_name}")
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {output_parts[-1]}")
                    down_success = True
                else:
                    error_msg = down_result.stderr.strip() if down_result.stderr else "Unknown error"
                    logger.debug(f"Docker-compose down failed for {project_name}: {error_msg}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Docker-compose down timed out for {project_name}")
            except Exception as e:
                logger.debug(f"Docker-compose down error for {project_name}: {e}")
            
            container_patterns = [
                f"^{project_name}_.*",
                f"^{project_name}-.*",
                f"^.*{project_name}.*",
                f"^{project_name}$"
            ]
            
            all_containers = set()
            for pattern in container_patterns:
                try:
                    result = subprocess.run(
                        ["docker", "ps", "-a", "--format", "{{.Names}}"],
                        capture_output=True,
                        text=True,
                        timeout=20,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    if result.returncode == 0 and result.stdout.strip():
                        all_names = result.stdout.strip().split('\n')
                        matching_containers = [name.strip() for name in all_names 
                                             if name.strip() and re.search(pattern, name.strip())]
                        all_containers.update(matching_containers)
                        
                except Exception as e:
                    logger.debug(f"Error finding containers with pattern {pattern}: {e}")
                    continue
            
            if not all_containers:
                output_parts.append("No conflicting containers found")
                logger.debug(f"No containers found for project {project_name}")
                return True, "\n".join(output_parts)
            
            logger.info(f"Stopping conflicting containers: {', '.join(all_containers)}")
            container_list = list(all_containers)
            
            stop_success = 0
            for container_name in container_list:
                try:
                    stop_result = subprocess.run(
                        ["docker", "stop", "-t", "5", container_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if stop_result.returncode == 0:
                        stop_success += 1
                        logger.info(f"Stopped conflicting container: {container_name}")
                except Exception as e:
                    logger.debug(f"Error stopping container {container_name}: {e}")
            
            if stop_success > 0:
                time.sleep(1)
            
            removed_count = 0
            for container_name in container_list:
                try:
                    rm_result = subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    if rm_result.returncode == 0:
                        removed_count += 1
                        logger.debug(f"Removed container: {container_name}")
                except Exception as e:
                    logger.debug(f"Error removing container {container_name}: {e}")
            
            if removed_count > 0:
                output_parts.append(f"Forcefully removed {removed_count} conflicting containers")
            
            try:
                network_result = subprocess.run(
                    ["docker", "network", "ls", "--filter", f"name={project_name}", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if network_result.returncode == 0 and network_result.stdout.strip():
                    networks = [name.strip() for name in network_result.stdout.strip().split('\n') if name.strip()]
                    project_networks = [net for net in networks if project_name in net]
                    
                    network_removed = 0
                    for network_name in project_networks:
                        try:
                            subprocess.run(
                                ["docker", "network", "rm", network_name],
                                capture_output=True,
                                text=True,
                                timeout=10,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            )
                            network_removed += 1
                            logger.debug(f"Removed network: {network_name}")
                        except Exception:
                            pass
                    
                    if network_removed > 0:
                        output_parts.append(f"Cleaned up {network_removed} networks")
            except Exception:
                pass
            
            try:
                volume_result = subprocess.run(
                    ["docker", "volume", "ls", "-f", "dangling=true", "--format", "{{.Name}}"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if volume_result.returncode == 0 and volume_result.stdout.strip():
                    volumes = [name.strip() for name in volume_result.stdout.strip().split('\n') if name.strip()]
                    project_volumes = [vol for vol in volumes if project_name in vol]
                    
                    if project_volumes:
                        try:
                            subprocess.run(
                                ["docker", "volume", "rm"] + project_volumes,
                                capture_output=True,
                                text=True,
                                timeout=30,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                            )
                            output_parts.append(f"Removed {len(project_volumes)} orphaned volumes")
                        except Exception:
                            pass
            except Exception:
                pass
            
            time.sleep(0.5)
            
        logger.info(f"Cleanup completed for project: {project_name}")
        return True, "\n".join(output_parts)
        
    except Exception as e:
        error_msg = f"Error during cleanup for {project_name}: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


# ===========================
# SERVICE CLASSES
# ===========================

class DockerManager:
    """Docker container management service."""
    
    def __init__(self, client: Optional[docker.DockerClient] = None) -> None:
        self.logger = create_logger_for_component('docker')
        self.client = client or self._create_docker_client()
        self._lock = threading.RLock()

    def _create_docker_client(self) -> Optional[docker.DockerClient]:
        """Create a Docker client instance."""
        try:
            default_host = (
                "npipe:////./pipe/docker_engine" if os.name == 'nt'
                else "unix://var/run/docker.sock"
            )
            docker_host = os.getenv("DOCKER_HOST", default_host)
            client = docker.DockerClient(base_url=docker_host, timeout=Config.DOCKER_TIMEOUT)
            client.ping()
            self.logger.info("Docker client created and verified")
            return client
        except Exception as e:
            self.logger.error(f"Docker client creation failed: {e}")
            return None

    def get_container_status(self, container_name: str) -> DockerStatus:
        if not container_name or not isinstance(container_name, str):
            return DockerStatus(exists=False, status="invalid", details="Invalid container name")
        if not self.client:
            return DockerStatus(exists=False, status="error", details="Docker client unavailable")
        try:
            with self._lock:
                container = self.client.containers.get(container_name)
            container_status = container.status
            is_running = container_status == "running"
            state = container.attrs.get("State", {})
            health_info = state.get("Health")
            if health_info and isinstance(health_info, dict):
                health_status = health_info.get("Status", "checking")
            elif is_running:
                health_status = "healthy"
            else:
                health_status = container_status
            return DockerStatus(
                exists=True,
                running=is_running,
                health=health_status,
                status=container_status,
                details=state.get("Status", "unknown"),
            )
        except NotFound:
            return DockerStatus(exists=False, status="no_container", details="Container not found")
        except Exception as e:
            self.logger.error(f"Error fetching status for {container_name}: {e}")
            return DockerStatus(exists=False, status="error", details=str(e))

    def get_container(self, container_name: str) -> Optional[Container]:
        if not self.client:
            return None
        try:
            with self._lock:
                return self.client.containers.get(container_name)
        except NotFound:
            return None
        except Exception as e:
            self.logger.error(f"Error getting container {container_name}: {e}")
            return None

    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        if not self.client:
            return "Docker client unavailable"
        container = self.get_container(container_name)
        if not container:
            return f"Container '{container_name}' not found"
        try:
            logs = container.logs(tail=tail).decode("utf-8", errors="replace")
            return logs
        except Exception as e:
            self.logger.error(f"Log retrieval failed for {container_name}: {e}")
            return f"Log retrieval error: {e}"

    def cleanup_containers(self) -> None:
        if not self.client:
            return
        try:
            result = self.client.containers.prune(filters={"until": "24h"})
            containers_deleted = result.get('ContainersDeleted', [])
            if containers_deleted:
                self.logger.info(f"Removed {len(containers_deleted)} old containers")
            else:
                self.logger.debug("No old containers to remove")
        except Exception as e:
            self.logger.error(f"Container cleanup failed: {e}")

    def restart_container(self, container_name: str, timeout: int = 10) -> Tuple[bool, str]:
        if not self.client:
            return False, "Docker client unavailable"
        container = self.get_container(container_name)
        if not container:
            return False, f"Container '{container_name}' not found"
        try:
            container.restart(timeout=timeout)
            self.logger.info(f"Container {container_name} restarted successfully")
            return True, f"Container {container_name} restarted successfully"
        except Exception as e:
            self.logger.error(f"Error restarting container {container_name}: {e}")
            return False, f"Error restarting container: {str(e)}"

    def is_docker_available(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def get_docker_version(self) -> str:
        if not self.client:
            return None
        try:
            version_info = self.client.version()
            return version_info.get("Version", "Unknown")
        except Exception as e:
            self.logger.error(f"Error fetching Docker version: {e}")
            return None

    def get_compose_version(self) -> str:
        """Get Docker Compose version by running docker-compose --version command."""
        try:
            commands = [
                ["docker", "compose", "version", "--short"],
                ["docker-compose", "--version"],
                ["docker", "compose", "--version"]
            ]
            
            for cmd in commands:
                try:
                    result = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True, 
                        timeout=5,
                        shell=True if os.name == 'nt' else False
                    )
                    if result.returncode == 0:
                        output = result.stdout.strip()
                        if "version" in output.lower():
                            version_match = re.search(r'v?(\d+\.\d+\.\d+)', output)
                            if version_match:
                                return version_match.group(1)
                        return output.split('\n')[0]
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                    continue
            
            self.logger.warning("Could not determine Docker Compose version")
            return None
        except Exception as e:
            self.logger.error(f"Error fetching Docker Compose version: {e}")
            return None


class SystemHealthMonitor:
    @staticmethod
    def check_docker_connection(docker_client: Optional[docker.DockerClient]) -> bool:
        if not docker_client:
            return False
        try:
            docker_client.ping()
            return True
        except Exception:
            return False

    @classmethod
    def check_health(cls, docker_client: Optional[docker.DockerClient]) -> bool:
        logger = create_logger_for_component('health')
        docker_ok = cls.check_docker_connection(docker_client)
        if docker_ok:
            logger.info("System health check passed")
        else:
            logger.warning("System health check failed - Docker unavailable")
        return docker_ok


class PortManager:
    def __init__(self, port_config: List[Dict[str, Any]]):
        self.logger = create_logger_for_component('port_manager')
        self.port_config = port_config
        self._model_app_cache = {}
        self._build_cache()

    def _build_cache(self) -> None:
        self._model_app_cache = {}
        for config in self.port_config:
            model_name = config.get('model_name')
            app_number = config.get('app_number')
            if model_name and app_number:
                key = f"{model_name}-{app_number}"
                self._model_app_cache[key] = config
        self.logger.info(f"Built port cache with {len(self._model_app_cache)} entries")

    def get_app_config(self, model_name: str, app_number: int) -> Optional[Dict[str, Any]]:
        key = f"{model_name}-{app_number}"
        return self._model_app_cache.get(key)

    def get_app_ports(self, model_name: str, app_number: int) -> Optional[Dict[str, int]]:
        config = self.get_app_config(model_name, app_number)
        if not config:
            return None
        return {
            "backend": config.get('backend_port'),
            "frontend": config.get('frontend_port')
        }

    def get_model_apps(self, model_name: str) -> List[Dict[str, Any]]:
        return [
            config for config in self.port_config
            if config.get('model_name') == model_name
        ]

    def get_all_models(self) -> List[str]:
        return list(set(
            config.get('model_name') for config in self.port_config
            if config.get('model_name')
        ))

    def get_port_ranges(self) -> Dict[str, Dict[str, int]]:
        if not self.port_config:
            return {"backend": {"min": 0, "max": 0}, "frontend": {"min": 0, "max": 0}}
        backend_ports = [
            config.get('backend_port') for config in self.port_config
            if config.get('backend_port')
        ]
        frontend_ports = [
            config.get('frontend_port') for config in self.port_config
            if config.get('frontend_port')
        ]
        return {
            "backend": {
                "min": min(backend_ports) if backend_ports else 0,
                "max": max(backend_ports) if backend_ports else 0
            },
            "frontend": {
                "min": min(frontend_ports) if frontend_ports else 0,
                "max": max(frontend_ports) if frontend_ports else 0
            }
        }

    def is_port_in_use(self, port: int) -> bool:
        for config in self.port_config:
            if (config.get('backend_port') == port or
                config.get('frontend_port') == port):
                return True
        return False

    def validate_config(self) -> List[str]:
        issues = []
        used_ports = set()
        for i, config in enumerate(self.port_config):
            required_fields = ['model_name', 'app_number', 'backend_port', 'frontend_port']
            missing_fields = [field for field in required_fields if not config.get(field)]
            if missing_fields:
                issues.append(f"Configuration {i}: Missing fields {missing_fields}")
                continue
            backend_port = config.get('backend_port')
            frontend_port = config.get('frontend_port')
            if backend_port in used_ports:
                issues.append(f"Configuration {i}: Backend port {backend_port} already in use")
            else:
                used_ports.add(backend_port)
            if frontend_port in used_ports:
                issues.append(f"Configuration {i}: Frontend port {frontend_port} already in use")
            else:
                used_ports.add(frontend_port)
            if not (1 <= backend_port <= 65535):
                issues.append(f"Configuration {i}: Invalid backend port {backend_port}")
            if not (1 <= frontend_port <= 65535):
                issues.append(f"Configuration {i}: Invalid frontend port {frontend_port}")
        return issues

    def get_statistics(self) -> Dict[str, Any]:
        if not self.port_config:
            return {
                "total_apps": 0,
                "total_models": 0,
                "port_ranges": self.get_port_ranges(),
                "apps_per_model": {}
            }
        models = {}
        for config in self.port_config:
            model_name = config.get('model_name')
            if model_name:
                models[model_name] = models.get(model_name, 0) + 1
        return {
            "total_apps": len(self.port_config),
            "total_models": len(models),
            "port_ranges": self.get_port_ranges(),
            "apps_per_model": models
        }


class ScanManager:
    def __init__(self):
        self.logger = create_logger_for_component('scan_manager')
        self.scans: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_scan(self, model: str, app_num: int, options: dict) -> str:
        scan_id = f"{model}-{app_num}-{int(time.time())}"
        with self._lock:
            self.scans[scan_id] = {
                "status": ScanStatus.STARTING.value,
                "progress": 0,
                "scanner": None,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "options": options,
                "model": model,
                "app_num": app_num,
                "results": None,
            }
        self.logger.info(f"Created scan '{scan_id}' for {model}/app{app_num}")
        return scan_id

    def get_scan_details(self, scan_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.scans.get(scan_id)

    def get_latest_scan_for_app(self, model: str, app_num: int) -> Optional[Tuple[str, Dict[str, Any]]]:
        with self._lock:
            matching_scans = [
                (sid, scan) for sid, scan in self.scans.items()
                if sid.startswith(f"{model}-{app_num}-")
            ]
            if not matching_scans:
                return None
            try:
                latest_scan_id, latest_scan_data = max(
                    matching_scans,
                    key=lambda item: int(item[0].split('-')[-1])
                )
                return latest_scan_id, latest_scan_data
            except (ValueError, IndexError) as e:
                self.logger.error(f"Error parsing scan IDs for {model}/app{app_num}: {e}")
                return None

    def update_scan(self, scan_id: str, **kwargs: Any) -> bool:
        with self._lock:
            if scan_id in self.scans:
                if 'status' in kwargs and kwargs['status'] in (
                    ScanStatus.COMPLETE.value, ScanStatus.FAILED.value,
                    ScanStatus.STOPPED.value, ScanStatus.ERROR.value
                ):
                    kwargs.setdefault('end_time', datetime.now().isoformat())
                self.scans[scan_id].update(kwargs)
                return True
            return False

    def cleanup_old_scans(self, max_age_hours: int = 1) -> int:
        cleanup_count = 0
        current_time = datetime.now()
        max_age = timedelta(hours=max_age_hours)
        terminal_statuses = {
            ScanStatus.COMPLETE.value, ScanStatus.FAILED.value,
            ScanStatus.STOPPED.value, ScanStatus.ERROR.value
        }
        with self._lock:
            scan_ids_to_remove = []
            for scan_id, scan in self.scans.items():
                if scan.get("status") in terminal_statuses:
                    try:
                        completion_time_str = scan.get("end_time") or scan.get("start_time")
                        if completion_time_str:
                            completion_time = datetime.fromisoformat(completion_time_str)
                            if current_time - completion_time > max_age:
                                scan_ids_to_remove.append(scan_id)
                    except (ValueError, TypeError):
                        continue
            for scan_id in scan_ids_to_remove:
                del self.scans[scan_id]
                cleanup_count += 1
        if cleanup_count > 0:
            self.logger.info(f"Cleaned up {cleanup_count} old scans")
        return cleanup_count


class ModelIntegrationService:
    """Service for integrating model information from JSON files."""
    
    def __init__(self, base_path: Optional[Path] = None):
        self.logger = create_logger_for_component('model_integration')
        self.base_path = base_path or Path.cwd()
        self.models_data = {}
        self._raw_data = {
            'port_config': [],
            'model_capabilities': {},
            'models_summary': {}
        }
        self.load_all_data()
    
    def load_all_data(self) -> bool:
        """Load all model data from the three JSON files."""
        success = True
        
        try:
            port_config_path = self.base_path / "port_config.json"
            if port_config_path.exists():
                with open(port_config_path, 'r', encoding='utf-8') as f:
                    self._raw_data['port_config'] = json.load(f)
                self.logger.info(f"Loaded {len(self._raw_data['port_config'])} port configurations")
            else:
                self.logger.warning(f"Port config file not found: {port_config_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load port_config.json: {e}")
            success = False
        
        try:
            capabilities_path = self.base_path / "model_capabilities.json"
            if capabilities_path.exists():
                with open(capabilities_path, 'r', encoding='utf-8') as f:
                    capabilities_data = json.load(f)
                    self._raw_data['model_capabilities'] = capabilities_data.get('models', {})
                self.logger.info(f"Loaded capabilities for {len(self._raw_data['model_capabilities'])} models")
            else:
                self.logger.warning(f"Capabilities file not found: {capabilities_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load model_capabilities.json: {e}")
            success = False
        
        try:
            summary_path = self.base_path / "models_summary.json"
            if summary_path.exists():
                with open(summary_path, 'r', encoding='utf-8') as f:
                    self._raw_data['models_summary'] = json.load(f)
                self.logger.info(f"Loaded models summary with {self._raw_data['models_summary'].get('total_models', 0)} models")
            else:
                self.logger.warning(f"Summary file not found: {summary_path}")
                success = False
        except Exception as e:
            self.logger.error(f"Failed to load models_summary.json: {e}")
            success = False
        
        if success:
            self._integrate_model_data()
        
        return success
    
    def _integrate_model_data(self):
        """Integrate data from all three sources into unified model objects."""
        self.models_data = {}
        
        port_configs_by_model = {}
        for config in self._raw_data['port_config']:
            model_name = config.get('model_name', '')
            if model_name:
                if model_name not in port_configs_by_model:
                    port_configs_by_model[model_name] = []
                port_configs_by_model[model_name].append(config)
        
        summary_models = {
            model['name']: model 
            for model in self._raw_data['models_summary'].get('models', [])
        }
        
        for model_name, port_configs in port_configs_by_model.items():
            model_info = EnhancedModelInfo(name=model_name)
            model_info.port_configs = port_configs
            
            if model_name in summary_models:
                summary = summary_models[model_name]
                model_info.color = summary.get('color', model_info.color)
                model_info.provider = summary.get('provider', model_info.provider)
            
            if model_name in self._raw_data['model_capabilities']:
                caps = self._raw_data['model_capabilities'][model_name]
                model_info.context_length = caps.get('context_length', 0)
                model_info.pricing = caps.get('pricing', {})
                model_info.capabilities = caps.get('capabilities', [])
                model_info.supports_vision = caps.get('supports_vision', False)
                model_info.supports_function_calling = caps.get('supports_function_calling', False)
                model_info.supports_reasoning = 'reasoning' in model_info.capabilities
                model_info.max_tokens = caps.get('max_tokens', 0)
                model_info.description = caps.get('description', '')
            
            model_info.apps_per_model = self._raw_data['models_summary'].get('apps_per_model', 0)
            
            self.models_data[model_name] = model_info
        
        self.logger.info(f"Integrated data for {len(self.models_data)} models")
    
    def get_all_models(self) -> List[EnhancedModelInfo]:
        """Get all integrated model information."""
        return list(self.models_data.values())
    
    def get_model(self, model_name: str) -> Optional[EnhancedModelInfo]:
        """Get a specific model by name."""
        return self.models_data.get(model_name)
    
    def get_models_by_provider(self, provider: str) -> List[EnhancedModelInfo]:
        """Get all models from a specific provider."""
        return [
            model for model in self.models_data.values()
            if model.provider == provider
        ]
    
    def get_models_with_capability(self, capability: str) -> List[EnhancedModelInfo]:
        """Get all models that have a specific capability."""
        return [
            model for model in self.models_data.values()
            if capability in model.capabilities
        ]
    
    def get_vision_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support vision."""
        return [
            model for model in self.models_data.values()
            if model.supports_vision
        ]
    
    def get_function_calling_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support function calling."""
        return [
            model for model in self.models_data.values()
            if model.supports_function_calling
        ]
    
    def get_reasoning_models(self) -> List[EnhancedModelInfo]:
        """Get all models that support reasoning."""
        return [
            model for model in self.models_data.values()
            if model.supports_reasoning
        ]
    
    def get_port_config_for_model(self, model_name: str, app_num: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get port configuration for a specific model and app."""
        model = self.get_model(model_name)
        if not model:
            return None
        
        if app_num is None:
            return model.port_configs[0] if model.port_configs else None
        
        for config in model.port_configs:
            if config.get('app_number') == app_num:
                return config
        
        return None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics about all models."""
        if not self.models_data:
            return {}
        
        providers = set(model.provider for model in self.models_data.values())
        all_capabilities = set()
        for model in self.models_data.values():
            all_capabilities.update(model.capabilities)
        
        return {
            'total_models': len(self.models_data),
            'unique_providers': len(providers),
            'providers': list(providers),
            'total_capabilities': len(all_capabilities),
            'capabilities': list(all_capabilities),
            'vision_models': len(self.get_vision_models()),
            'function_calling_models': len(self.get_function_calling_models()),
            'reasoning_models': len(self.get_reasoning_models()),
            'avg_context_length': (
                sum(m.context_length for m in self.models_data.values()) // len(self.models_data)
                if self.models_data else 0
            ),
            'total_port_configs': sum(len(m.port_configs) for m in self.models_data.values()),
            'apps_per_model': self._raw_data['models_summary'].get('apps_per_model', 0)
        }
    
    def export_integrated_data(self, output_path: Optional[Path] = None) -> Path:
        """Export the integrated model data to a JSON file."""
        if output_path is None:
            output_path = self.base_path / "integrated_models.json"
        
        export_data = {
            'metadata': {
                'generated_at': str(Path().cwd()),
                'total_models': len(self.models_data),
                'data_sources': ['port_config.json', 'model_capabilities.json', 'models_summary.json']
            },
            'summary_stats': self.get_summary_stats(),
            'models': {
                name: model.to_dict()
                for name, model in self.models_data.items()
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Exported integrated model data to {output_path}")
        return output_path
    
    def refresh_data(self) -> bool:
        """Refresh all data from JSON files."""
        return self.load_all_data()


class GenerationLookupService:
    """Service for looking up generation details"""
    
    def __init__(self, generated_conversations_dir: str = "generated_conversations"):
        self.conversations_dir = Path(generated_conversations_dir)
        self.logger = logging.getLogger(__name__)
    
    def list_generation_runs(self) -> List[GenerationMetadata]:
        """List all available generation runs"""
        runs = []
        
        try:
            metadata_files = list(self.conversations_dir.glob("metadata_detailed_*.json"))
            
            for metadata_file in sorted(metadata_files, reverse=True):
                try:
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    timestamp = metadata_file.stem.replace("metadata_detailed_", "")
                    perf_metrics = data.get("performance_metrics", {})
                    
                    runs.append(GenerationMetadata(
                        timestamp=timestamp,
                        filename=metadata_file.name,
                        models_count=len(data.get("models_statistics", [])),
                        apps_count=len(data.get("apps_statistics", [])),
                        total_successful=sum(1 for m in data.get("models_statistics", []) if m.get("success_rate", 0) > 0),
                        total_failed=sum(1 for m in data.get("models_statistics", []) if m.get("success_rate", 0) == 0),
                        generation_time=perf_metrics.get("avg_generation_time_per_request", 0),
                        fastest_model=perf_metrics.get("fastest_model", "Unknown"),
                        slowest_model=perf_metrics.get("slowest_model", "Unknown"),
                        most_successful_app=perf_metrics.get("most_successful_app", 1),
                        least_successful_app=perf_metrics.get("least_successful_app", 1)
                    ))
                    
                except Exception as e:
                    self.logger.warning(f"Failed to parse metadata file {metadata_file}: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Failed to list generation runs: {e}")
        
        return runs
    
    def get_generation_details(self, timestamp: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific generation run"""
        try:
            metadata_file = self.conversations_dir / f"metadata_detailed_{timestamp}.json"
            
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        except Exception as e:
            self.logger.error(f"Failed to get generation details for {timestamp}: {e}")
            return None
    
    def get_model_app_details(self, timestamp: str, model: str, app_num: int) -> Optional[ModelAppDetails]:
        """Get detailed information for a specific model-app combination"""
        try:
            gen_data = self.get_generation_details(timestamp)
            if not gen_data:
                return None
            
            model_stats = None
            for stats in gen_data.get("models_statistics", []):
                if stats.get("model") == model:
                    model_stats = stats
                    break
            
            if not model_stats:
                return None
            
            app_stats = None
            for stats in gen_data.get("apps_statistics", []):
                if stats.get("app_num") == app_num:
                    app_stats = stats
                    break
            
            attempted_apps = model_stats.get("apps_attempted", [])
            successful_apps = model_stats.get("successful_apps", [])
            
            if app_num not in attempted_apps:
                return None
            
            model_safe = model.replace('/', '_').replace(':', '_')
            model_dir = self.conversations_dir / model_safe
            markdown_files = []
            extracted_files = []
            
            if model_dir.exists():
                for md_file in model_dir.glob(f"app_{app_num}_*.md"):
                    markdown_files.append(str(md_file.relative_to(self.conversations_dir)))
                
                app_dir = model_dir / f"app{app_num}"
                if app_dir.exists():
                    for extracted_file in app_dir.rglob("*"):
                        if extracted_file.is_file():
                            extracted_files.append(str(extracted_file.relative_to(self.conversations_dir)))
            
            return ModelAppDetails(
                model=model,
                display_name=model_stats.get("display_name", model),
                provider=model_stats.get("provider", "unknown"),
                is_free=model_stats.get("is_free", False),
                app_num=app_num,
                app_name=app_stats.get("name", f"App {app_num}") if app_stats else f"App {app_num}",
                success_rate=model_stats.get("success_rate", 0),
                frontend_success=app_num in successful_apps,
                backend_success=app_num in successful_apps,
                total_tokens=model_stats.get("total_tokens_estimated", 0),
                response_quality=model_stats.get("avg_response_quality", 0),
                generation_time=None,
                markdown_files=markdown_files,
                extracted_files=extracted_files,
                requirements=app_stats.get("requirements", []) if app_stats else []
            )
        
        except Exception as e:
            self.logger.error(f"Failed to get model app details: {e}")
            return None
    
    def get_model_performance_summary(self, timestamp: str) -> Dict[str, Any]:
        """Get performance summary for all models in a generation run"""
        try:
            gen_data = self.get_generation_details(timestamp)
            if not gen_data:
                return {}
            
            models = gen_data.get("models_statistics", [])
            
            total_models = len(models)
            successful_models = sum(1 for m in models if m.get("success_rate", 0) > 0)
            free_models = sum(1 for m in models if m.get("is_free", False))
            paid_models = total_models - free_models
            
            avg_success_rate = sum(m.get("success_rate", 0) for m in models) / max(total_models, 1)
            avg_tokens = sum(m.get("total_tokens_estimated", 0) for m in models) / max(total_models, 1)
            avg_quality = sum(m.get("avg_response_quality", 0) for m in models if m.get("avg_response_quality", 0) > 0)
            avg_quality = avg_quality / max(sum(1 for m in models if m.get("avg_response_quality", 0) > 0), 1)
            
            providers = {}
            for model in models:
                provider = model.get("provider", "unknown")
                if provider not in providers:
                    providers[provider] = {"total": 0, "successful": 0, "free": 0}
                providers[provider]["total"] += 1
                if model.get("success_rate", 0) > 0:
                    providers[provider]["successful"] += 1
                if model.get("is_free", False):
                    providers[provider]["free"] += 1
            
            return {
                "total_models": total_models,
                "successful_models": successful_models,
                "failed_models": total_models - successful_models,
                "free_models": free_models,
                "paid_models": paid_models,
                "avg_success_rate": avg_success_rate,
                "avg_tokens": avg_tokens,
                "avg_quality": avg_quality,
                "providers": providers,
                "performance_metrics": gen_data.get("performance_metrics", {})
            }
        
        except Exception as e:
            self.logger.error(f"Failed to get model performance summary: {e}")
            return {}
    
    def search_generations(self, model_filter: Optional[str] = None, app_filter: Optional[int] = None, 
                          success_only: bool = False) -> List[Tuple[str, str, int, bool]]:
        """Search for generations matching criteria"""
        results = []
        
        try:
            for run in self.list_generation_runs():
                gen_data = self.get_generation_details(run.timestamp)
                if not gen_data:
                    continue
                
                for model_stats in gen_data.get("models_statistics", []):
                    model = model_stats.get("model", "")
                    
                    if model_filter and model_filter.lower() not in model.lower():
                        continue
                    
                    for app_num in model_stats.get("apps_attempted", []):
                        if app_filter is not None and app_num != app_filter:
                            continue
                        
                        is_successful = app_num in model_stats.get("successful_apps", [])
                        
                        if success_only and not is_successful:
                            continue
                        
                        results.append((run.timestamp, model, app_num, is_successful))
        
        except Exception as e:
            self.logger.error(f"Failed to search generations: {e}")
        
        return results
    
    def get_file_content(self, relative_path: str) -> Optional[str]:
        """Get content of a generated file"""
        try:
            file_path = self.conversations_dir / relative_path
            
            if not file_path.exists() or not file_path.is_file():
                return None
            
            if not str(file_path.resolve()).startswith(str(self.conversations_dir.resolve())):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        
        except Exception as e:
            self.logger.error(f"Failed to get file content for {relative_path}: {e}")
            return None


class BatchTaskWorker:
    """Worker class for executing batch analysis tasks."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.logger = create_logger_for_component('batch_worker')
    
    def execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single analysis task."""
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            with self.app.app_context():
                result = self._run_analysis(task)
                task.result = result
                task.status = TaskStatus.COMPLETED
                if result and 'issues' in result:
                    task.issues_count = len(result.get('issues', []))
                elif result and 'issues_count' in result:
                    task.issues_count = result['issues_count']
                else:
                    task.issues_count = 0
                
        except Exception as e:
            self.logger.error(f"Task {task.id} failed: {str(e)}", exc_info=True)
            task.status = TaskStatus.FAILED
            task.error = {
                "message": str(e),
                "category": type(e).__name__
            }
        
        finally:
            task.completed_at = datetime.now()
            task.duration_seconds = time.time() - start_time
        
        return task
    
    def _run_analysis(self, task: BatchTask) -> Dict[str, Any]:
        """Run the specific analysis for the task."""
        analysis_type = task.analysis_type
        model = task.model
        app_num = task.app_num
        
        self.logger.info(f"Running {analysis_type} analysis for {model} app {app_num}")
        
        use_mock = current_app.config.get('USE_MOCK_ANALYSIS', False)
        
        if use_mock:
            return self._generate_mock_result(analysis_type, model, app_num)
        
        if analysis_type == AnalysisType.FRONTEND_SECURITY.value:
            analyzer = getattr(current_app, 'frontend_security_analyzer', None)
            if not analyzer:
                raise ValueError("Frontend security analyzer not available")
            
            issues, status, outputs = analyzer.run_security_analysis(
                model, app_num, use_all_tools=True
            )
            
            return {
                "issues": issues,
                "tool_status": status,
                "outputs": outputs,
                "summary": f"Found {len(issues)} security issues"
            }
            
        elif analysis_type == AnalysisType.BACKEND_SECURITY.value:
            analyzer = getattr(current_app, 'backend_security_analyzer', None)
            if not analyzer:
                raise ValueError("Backend security analyzer not available")
            
            issues, status, outputs = analyzer.run_security_analysis(
                model, app_num, use_all_tools=True
            )
            
            return {
                "issues": issues,
                "tool_status": status,
                "outputs": outputs,
                "summary": f"Found {len(issues)} security issues"
            }
            
        elif analysis_type == AnalysisType.PERFORMANCE.value:
            analyzer = getattr(current_app, 'performance_analyzer', None)
            if not analyzer:
                raise ValueError("Performance analyzer not available")
            
            result = analyzer.run_performance_test(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.ZAP.value:
            scanner = getattr(current_app, 'zap_scanner', None)
            if not scanner:
                raise ValueError("ZAP scanner not available")
            
            result = scanner.scan_app(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.GPT4ALL.value:
            analyzer = getattr(current_app, 'gpt4all_analyzer', None)
            if not analyzer:
                raise ValueError("GPT4All analyzer not available")
            
            result = analyzer.analyze_app(model, app_num)
            return result
            
        elif analysis_type == AnalysisType.CODE_QUALITY.value:
            analyzer = getattr(current_app, 'code_quality_analyzer', None)
            if not analyzer:
                raise ValueError("Code quality analyzer not available")
            
            result = analyzer.analyze_app(model, app_num)
            return result
            
        else:
            raise ValueError(f"Unknown analysis type: {analysis_type}")
    
    def _generate_mock_result(self, analysis_type: str, model: str, app_num: int, 
                            error_msg: Optional[str] = None) -> Dict[str, Any]:
        """Generate mock results for testing."""
        if error_msg:
            return {
                "error": error_msg,
                "summary": f"Mock {analysis_type} analysis failed",
                "issues": []
            }
        
        if analysis_type in [AnalysisType.FRONTEND_SECURITY.value, AnalysisType.BACKEND_SECURITY.value]:
            return {
                "issues": [
                    {
                        "id": f"mock-issue-1-{model}-{app_num}",
                        "severity": "HIGH",
                        "issue_type": "Mock Security Issue",
                        "issue_text": f"This is a mock {analysis_type} issue for {model} app {app_num}",
                        "filename": f"mock_file_{app_num}.js",
                        "line_number": 42
                    },
                    {
                        "id": f"mock-issue-2-{model}-{app_num}", 
                        "severity": "MEDIUM",
                        "issue_type": "Mock Warning",
                        "issue_text": f"This is a mock medium severity issue for {model}",
                        "filename": f"another_file_{app_num}.py",
                        "line_number": 100
                    }
                ],
                "tool_status": {
                    "mock_tool": "Completed with mock data"
                },
                "summary": "Found 2 mock issues"
            }
        
        elif analysis_type == AnalysisType.PERFORMANCE.value:
            return {
                "requests_per_sec": 150.5 + (app_num * 10),
                "avg_response_time": 45.2 + (app_num * 5),
                "median_response_time": 40.0 + (app_num * 4),
                "percentile_95": 120.0 + (app_num * 10),
                "total_requests": 1000,
                "total_failures": 5,
                "summary": "Mock performance test completed"
            }
        
        else:
            return {
                "status": "completed",
                "summary": f"Mock {analysis_type} analysis completed for {model} app {app_num}",
                "data": {
                    "timestamp": datetime.now().isoformat(),
                    "model": model,
                    "app_num": app_num
                }
            }


class BatchAnalysisService:
    """Service for managing batch analysis jobs."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.jobs: Dict[str, BatchJob] = {}
        self.tasks: Dict[str, BatchTask] = {}
        self.app: Optional[Flask] = app
        self.worker_pool: Optional[ThreadPoolExecutor] = None
        self.job_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
        self.logger = create_logger_for_component('batch_service')
        self._lock = threading.Lock()
        
        if app:
            self.init_app(app)

    def init_app(self, app: Flask):
        """Initialize the service with Flask app."""
        self.app = app
        max_workers = app.config.get('BATCH_MAX_WORKERS', 4)
        self.worker_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.logger.info(f"Batch analysis service initialized with {max_workers} workers")

    def create_job(self, name: str, description: str, analysis_types: List[str],
                   models: List[str], app_range_str: str, 
                   auto_start: bool = True) -> BatchJob:
        """Create a new batch job."""
        app_range = self._parse_app_range(app_range_str)
        
        if not analysis_types:
            raise ValueError("At least one analysis type must be selected")
        if not models:
            raise ValueError("At least one model must be selected")
        if not app_range['apps']:
            raise ValueError("Invalid app range specified")
        
        analysis_type_enums = []
        for at_str in analysis_types:
            try:
                analysis_type_enums.append(AnalysisType(at_str))
            except ValueError:
                self.logger.warning(f"Unknown analysis type: {at_str}")
                continue
        
        if not analysis_type_enums:
            raise ValueError("No valid analysis types specified")
        
        job_id = str(uuid.uuid4())
        job = BatchJob(
            id=job_id,
            name=name,
            description=description or "",
            status=JobStatus.PENDING,
            analysis_types=analysis_type_enums,
            models=models,
            app_range=app_range,
            created_at=datetime.now(),
            auto_start=auto_start
        )
        
        total_tasks = len(models) * len(app_range['apps']) * len(analysis_type_enums)
        job.progress['total'] = total_tasks
        
        for model in models:
            for app_num in app_range['apps']:
                for analysis_type in analysis_type_enums:
                    task_id = str(uuid.uuid4())
                    task = BatchTask(
                        id=task_id,
                        job_id=job_id,
                        model=model,
                        app_num=app_num,
                        analysis_type=analysis_type.value
                    )
                    self.tasks[task_id] = task
        
        with self._lock:
            self.jobs[job_id] = job
        
        self.logger.info(f"Created batch job {job_id} with {total_tasks} tasks")
        
        if auto_start:
            self.start_job(job_id)
        
        return job

    def _parse_app_range(self, app_range_str: str) -> Dict[str, Any]:
        """Parse app range string into list of app numbers."""
        apps = []
        parts = app_range_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    start = int(start.strip())
                    end = int(end.strip())
                    if start <= end:
                        apps.extend(range(start, end + 1))
                except ValueError:
                    self.logger.warning(f"Invalid range format: {part}")
            else:
                try:
                    apps.append(int(part))
                except ValueError:
                    self.logger.warning(f"Invalid app number: {part}")
        
        apps = sorted(list(set(apps)))
        
        return {
            "raw": app_range_str,
            "apps": apps
        }

    def get_all_jobs(self) -> List[BatchJob]:
        """Get all jobs."""
        with self._lock:
            return list(self.jobs.values())

    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a specific job."""
        return self.jobs.get(job_id)

    def get_job_tasks(self, job_id: str) -> List[BatchTask]:
        """Get all tasks for a job."""
        return [task for task in self.tasks.values() if task.job_id == job_id]

    def get_task(self, task_id: str) -> Optional[BatchTask]:
        """Get a specific task."""
        return self.tasks.get(task_id)

    def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            "total": len(self.jobs),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0
        }
        
        for job in self.jobs.values():
            status = job.status.value if hasattr(job.status, 'value') else str(job.status)
            if status in stats:
                stats[status] += 1
        
        return stats

    def start_job(self, job_id: str) -> bool:
        """Start executing a job."""
        job = self.get_job(job_id)
        if not job or job.status != JobStatus.PENDING:
            return False
        
        thread = threading.Thread(
            target=self._execute_job,
            args=(job_id,),
            name=f"BatchJob-{job_id[:8]}"
        )
        
        with self._lock:
            self.job_threads[job_id] = thread
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()
        
        thread.start()
        self.logger.info(f"Started batch job: {job_id}")
        return True

    def _execute_job(self, job_id: str):
        """Execute a job by running all its tasks."""
        job = self.get_job(job_id)
        if not job:
            return
        
        try:
            tasks = self.get_job_tasks(job_id)
            worker = BatchTaskWorker(self.app)
            
            futures = []
            for task in tasks:
                if self.shutdown_event.is_set():
                    break
                    
                future = self.worker_pool.submit(worker.execute_task, task)
                futures.append((future, task))
            
            for future, task in futures:
                if self.shutdown_event.is_set():
                    future.cancel()
                    continue
                
                try:
                    completed_task = future.result(timeout=300)
                    self.tasks[task.id] = completed_task
                    
                    if completed_task.status == TaskStatus.COMPLETED:
                        job.progress["completed"] += 1
                    elif completed_task.status == TaskStatus.FAILED:
                        job.progress["failed"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Task {task.id} execution failed: {str(e)}")
                    task.status = TaskStatus.FAILED
                    task.error = {"message": str(e), "category": "ExecutionError"}
                    self.tasks[task.id] = task
                    job.progress["failed"] = job.progress.get("failed", 0) + 1
            
            failed_count = job.progress.get("failed", 0)
            if failed_count == 0:
                job.status = JobStatus.COMPLETED
            elif failed_count == len(tasks):
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED
            
        except Exception as e:
            self.logger.error(f"Job {job_id} execution failed: {str(e)}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
        
        finally:
            job.completed_at = datetime.now()
            with self._lock:
                if job_id in self.job_threads:
                    del self.job_threads[job_id]

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.PENDING, JobStatus.RUNNING]:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            
            for task in self.get_job_tasks(job_id):
                if task.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                    task.status = TaskStatus.CANCELLED
                    task.completed_at = datetime.now()
                    self.tasks[task.id] = task
            
            self.logger.info(f"Cancelled batch job: {job_id}")
            return True
        return False

    def delete_job(self, job_id: str) -> bool:
        """Delete a job and its tasks."""
        with self._lock:
            if job_id in self.jobs:
                task_ids_to_remove = [task_id for task_id, task in self.tasks.items() 
                                    if task.job_id == job_id]
                for task_id in task_ids_to_remove:
                    del self.tasks[task_id]
                
                del self.jobs[job_id]
                self.logger.info(f"Deleted batch job: {job_id}")
                return True
        return False

    def archive_job(self, job_id: str) -> bool:
        """Archive a completed job."""
        job = self.get_job(job_id)
        if job and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            job.status = JobStatus.ARCHIVED
            self.logger.info(f"Archived batch job: {job_id}")
            return True
        return False

    def clean_corrupted_jobs(self):
        """Clean up any corrupted jobs."""
        with self._lock:
            corrupted_job_ids = []
            for job_id, job in self.jobs.items():
                try:
                    _ = job.status
                    _ = job.created_at
                except Exception as e:
                    self.logger.warning(f"Found corrupted job {job_id}: {str(e)}")
                    corrupted_job_ids.append(job_id)
            
            for job_id in corrupted_job_ids:
                del self.jobs[job_id]
                task_ids_to_remove = [task_id for task_id, task in self.tasks.items() 
                                    if task.job_id == job_id]
                for task_id in task_ids_to_remove:
                    del self.tasks[task_id]

    def shutdown(self):
        """Shutdown the batch service."""
        self.shutdown_event.set()
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True)
        
        for thread in self.job_threads.values():
            thread.join(timeout=5)


# ===========================
# GLOBAL SERVICE INSTANCES
# ===========================

_global_service: Optional[ModelIntegrationService] = None


def get_model_service() -> ModelIntegrationService:
    """Get the global model integration service instance."""
    global _global_service
    if _global_service is None:
        _global_service = ModelIntegrationService()
    return _global_service


def initialize_model_service(base_path: Optional[Path] = None) -> ModelIntegrationService:
    """Initialize the global model integration service."""
    global _global_service
    _global_service = ModelIntegrationService(base_path)
    return _global_service


def create_scanner(base_path):
    logger = create_logger_for_component('zap_init')
    try:
        from zap_scanner import create_scanner as zap_create_scanner
        return zap_create_scanner(base_path)
    except ImportError as e:
        logger.error(f"Failed to import ZAP scanner module: {e}")
        return None
    except Exception as e:
        logger.error(f"Error creating ZAP scanner: {e}")
        return None


# ===========================
# UTILITY FUNCTIONS
# ===========================

def load_port_config(app_root_path: Union[str, Path]) -> List[Dict[str, Any]]:
    """Load port configuration from JSON file."""
    logger = create_logger_for_component('utils')
    config_path = Path(app_root_path) / "port_config.json"
    
    if not config_path.exists():
        logger.warning(f"Port configuration file not found: {config_path}")
        return []
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            logger.info(f"Loaded {len(config)} port configurations")
            return config
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in port configuration: {e}")
        return []
    except Exception as e:
        logger.error(f"Error loading port configuration: {e}")
        return []


def load_models_from_json_files() -> Dict[str, Any]:
    """Load comprehensive model information from the three JSON files."""
    logger = create_logger_for_component('model_loader')
    models_data = {
        'port_config': [],
        'model_capabilities': {},
        'models_summary': {}
    }
    
    try:
        with open('port_config.json', 'r', encoding='utf-8') as f:
            models_data['port_config'] = json.load(f)
        logger.info(f"Loaded {len(models_data['port_config'])} port configurations")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load port_config.json: {e}")
    
    try:
        with open('model_capabilities.json', 'r', encoding='utf-8') as f:
            capabilities_data = json.load(f)
            models_data['model_capabilities'] = capabilities_data.get('models', {})
        logger.info(f"Loaded capabilities for {len(models_data['model_capabilities'])} models")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load model_capabilities.json: {e}")
    
    try:
        with open('models_summary.json', 'r', encoding='utf-8') as f:
            models_data['models_summary'] = json.load(f)
        logger.info(f"Loaded models summary with {models_data['models_summary'].get('total_models', 0)} models")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load models_summary.json: {e}")
    
    return models_data


def get_ai_models_from_config(port_config: List[Dict[str, Any]]) -> List[AIModel]:
    """Extract unique AI models from port configuration, enhanced with JSON data."""
    if not port_config:
        return []
    
    models_data = load_models_from_json_files()
    models_summary = models_data['models_summary'].get('models', [])
    model_capabilities = models_data['model_capabilities']
    
    summary_lookup = {model['name']: model for model in models_summary}
    
    default_color_mappings = {
        'anthropic': '#D97706',
        'openai': '#14B8A6', 
        'mistralai': '#8B5CF6',
        'google': '#3B82F6',
        'meta-llama': '#F59E0B',
        'nousresearch': '#EC4899',
        'microsoft': '#6366F1',
        'qwen': '#F43F5E',
        'x-ai': '#EF4444',
        'inception': '#A855F7',
        'deepseek': '#F97316',
        'opengvlab': '#808080',
        'thudm': '#808080',
        'agentica-org': '#10B981',
        'rekaai': '#60A5FA',
        'open-r1': '#FBBF24'
    }
    
    unique_models = {}
    for config in port_config:
        model_name = config.get('model_name', '')
        if model_name and model_name not in unique_models:
            color = '#666666'
            provider = 'unknown'
            
            if model_name in summary_lookup:
                summary_data = summary_lookup[model_name]
                color = summary_data.get('color', color)
                provider = summary_data.get('provider', provider)
            else:
                for prefix, model_color in default_color_mappings.items():
                    if model_name.startswith(prefix):
                        color = model_color
                        provider = prefix
                        break
            
            ai_model = AIModel(name=model_name, color=color)
            
            if model_name in model_capabilities:
                caps = model_capabilities[model_name]
                ai_model.provider = caps.get('provider', provider)
                ai_model.context_length = caps.get('context_length', 0)
                ai_model.pricing = caps.get('pricing', {})
                ai_model.capabilities = caps.get('capabilities', [])
                ai_model.supports_vision = caps.get('supports_vision', False)
                ai_model.supports_function_calling = caps.get('supports_function_calling', False)
            
            unique_models[model_name] = ai_model
    
    return list(unique_models.values())


def get_port_config() -> List[Dict[str, Any]]:
    """Get port configuration from current app context."""
    return current_app.config.get('PORT_CONFIG', [])


def get_ai_models() -> List[AIModel]:
    """Get AI models from current app context."""
    return current_app.config.get('AI_MODELS', [])


def get_model_by_name(model_name: str) -> Optional[AIModel]:
    """Get a specific model by name from the loaded models."""
    models = get_ai_models()
    for model in models:
        if model.name == model_name:
            return model
    return None


def get_models_by_provider(provider: str) -> List[AIModel]:
    """Get all models from a specific provider."""
    models = get_ai_models()
    return [model for model in models if model.provider == provider]


def get_models_with_capability(capability: str) -> List[AIModel]:
    """Get all models that have a specific capability."""
    models = get_ai_models()
    return [model for model in models if capability in model.capabilities]


def get_vision_models() -> List[AIModel]:
    """Get all models that support vision."""
    models = get_ai_models()
    return [model for model in models if model.supports_vision]


def get_function_calling_models() -> List[AIModel]:
    """Get all models that support function calling."""
    models = get_ai_models()
    return [model for model in models if model.supports_function_calling]


def get_enhanced_models() -> List[Any]:
    """Get enhanced models from current app context."""
    return current_app.config.get('ENHANCED_MODELS', [])


def get_model_stats() -> Dict[str, Any]:
    """Get model statistics from current app context."""
    config_stats = current_app.config.get('MODEL_STATS')
    if config_stats:
        return config_stats
    
    models = get_ai_models()
    if not models:
        return {}
    
    providers = set(model.provider for model in models)
    capabilities = set()
    for model in models:
        capabilities.update(model.capabilities)
    
    return {
        'total_models': len(models),
        'unique_providers': len(providers),
        'providers': list(providers),
        'total_capabilities': len(capabilities),
        'capabilities': list(capabilities),
        'vision_models': len([m for m in models if m.supports_vision]),
        'function_calling_models': len([m for m in models if m.supports_function_calling]),
        'avg_context_length': sum(m.context_length for m in models) // len(models) if models else 0
    }


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle complex types."""
    def default(self, o: Any) -> Any:
        if hasattr(o, 'to_dict') and callable(o.to_dict):
            return o.to_dict()
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, Path):
            return str(o)
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


def create_api_response(success: bool = True, data: Any = None, error: Optional[str] = None, 
                       message: Optional[str] = None, code: int = 200) -> Tuple[Response, int]:
    """Create a standardized API response."""
    response_data: Dict[str, Any] = {"success": success}
    if message:
        response_data["message"] = message
    if data is not None:
        response_data["data"] = data
    if error:
        response_data["error"] = error
    return jsonify(response_data), code


def get_app_info(model: str, app_num: int) -> Optional[Dict[str, Any]]:
    """Get information about a specific app."""
    logger = create_logger_for_component('utils')
    port_config = get_port_config()
    
    for config in port_config:
        if config.get('model_name') == model and config.get('app_number') == app_num:
            backend_port = config.get('backend_port')
            frontend_port = config.get('frontend_port')
            if backend_port is None or frontend_port is None:
                logger.warning(f"Missing port configuration for {model}/app{app_num}")
                return None
            return {
                "model": model,
                "app_num": app_num,
                "backend_port": backend_port,
                "frontend_port": frontend_port,
                "backend_url": f"http://localhost:{backend_port}",
                "frontend_url": f"http://localhost:{frontend_port}"
            }
    
    return None


def get_app_config_by_model_and_number(model: str, app_num: int) -> Optional[Dict[str, Any]]:
    """Get app configuration by model name and app number."""
    port_config = get_port_config()
    
    for config in port_config:
        if config.get('model_name') == model and config.get('app_number') == app_num:
            return config
    
    return None


def get_apps_for_model(model: str) -> List[Dict[str, Any]]:
    """Get all apps for a specific model."""
    port_config = get_port_config()
    apps = []
    
    for config in port_config:
        if config.get('model_name') == model:
            app_number = config.get('app_number')
            if app_number is not None:
                app_info = get_app_info(model, app_number)
                if app_info:
                    apps.append(app_info)
    
    return apps


def get_models_base_dir() -> Path:
    """Get the base directory for models."""
    config = current_app.config.get('APP_CONFIG')
    if config and config.MODELS_BASE_DIR:
        return Path(config.MODELS_BASE_DIR)
    
    return Path(__file__).parent.parent / "models"


def get_app_directory(model: str, app_num: int) -> Path:
    """Get the directory path for a specific application."""
    models_base_dir = get_models_base_dir()
    model_app_path = models_base_dir / model / f"app{app_num}"
    
    if not model_app_path.is_dir():
        raise FileNotFoundError(f"Application directory not found: {model_app_path}")
    
    return model_app_path


def get_all_apps() -> List[Dict[str, Any]]:
    """Get all applications from port configuration."""
    port_config = get_port_config()
    
    all_apps = []
    for config in port_config:
        model_name = config.get('model_name')
        app_num = config.get('app_number')
        
        if not model_name or not app_num:
            continue
        
        app_info = get_app_info(model_name, app_num)
        if app_info:
            all_apps.append(app_info)
    
    return all_apps


def get_docker_manager() -> DockerManager:
    """Get the Docker manager instance from the Flask app."""
    docker_manager = current_app.config.get("docker_manager")
    if not docker_manager:
        raise RuntimeError("Docker manager is not available")
    return docker_manager


def run_docker_compose(command: List[str], model: str, app_num: int, 
                      timeout: int = 60) -> Tuple[bool, str]:
    """Run a docker-compose command for a specific application with comprehensive error handling."""
    logger = create_logger_for_component('utils')
    
    if not is_docker_available():
        return False, "Docker is not available or not running"
    
    if not is_docker_compose_available():
        return False, "Docker Compose is not available"
    
    try:
        app_dir = get_app_directory(model, app_num)
        
        compose_file = None
        for filename in ["docker-compose.yml", "docker-compose.yaml"]:
            potential_path = app_dir / filename
            if potential_path.exists():
                compose_file = potential_path
                break
                
        if not compose_file:
            return False, f"No docker-compose file found in {app_dir}"
        
        project_name = get_docker_project_name(model, app_num)
        
        if "up" in command:
            logger.info(f"Checking for container conflicts for project: {project_name}")
            
            try:
                status_check = subprocess.run(
                    ["docker-compose", "-p", project_name, "-f", str(compose_file), "ps", "--services", "--filter", "status=running"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                if status_check.returncode == 0 and status_check.stdout.strip():
                    running_services = status_check.stdout.strip().split('\n')
                    logger.debug(f"Found running services for {project_name}: {running_services}")
                    
                    logger.info(f"Attempting docker-compose down for project: {project_name}")
                    conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
                else:
                    logger.info(f"Attempting docker-compose down for project: {project_name}")
                    conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                    logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
                
            except Exception as e:
                logger.debug(f"Pre-cleanup check failed for {project_name}, proceeding with cleanup: {e}")
                conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                logger.info(f"Pre-emptively cleaned up potential conflicts: {conflict_output}")
        
        cmd = ["docker-compose", "-p", project_name, "-f", str(compose_file)] + command
        
        logger.info(f"Running Docker Compose command: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        output = result.stdout
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr
            
        success = result.returncode == 0
        
        if not success:
            error_output = output.lower()
            
            if any(pattern in error_output for pattern in [
                "already in use", "conflict", "port is already allocated",
                "address already in use", "name is already in use"
            ]):
                logger.warning(f"Container name conflict detected for {project_name}")
                return False, f"Container conflict detected:\n{output}"
            
            elif any(pattern in error_output for pattern in [
                "no such container", "container not found", 
                "cannot kill container", "cannot start container"
            ]):
                logger.warning(f"Container reference issue for {project_name}, attempting cleanup and retry")
                return False, f"Container reference issue detected:\n{output}"
            
            elif any(pattern in error_output for pattern in [
                "network", "endpoint", "driver failed programming external connectivity"
            ]):
                logger.warning(f"Network conflict detected for {project_name}")
                return False, f"Network issue detected:\n{output}"
            
            elif "timeout" in error_output or "timed out" in error_output:
                logger.error(f"Docker command timed out for {project_name}")
                return False, f"Docker operation timed out:\n{output}"
            
            else:
                logger.error(f"Docker Compose command failed for {model}/app{app_num}: {output}")
                return False, output.strip()
        else:
            logger.info(f"Docker Compose command succeeded for {model}/app{app_num}")
            return True, output.strip()
            
    except subprocess.TimeoutExpired:
        error_msg = f"Docker Compose command timed out after {timeout}s"
        logger.error(error_msg)
        return False, error_msg
    except FileNotFoundError:
        error_msg = "docker-compose command not found. Please install Docker Compose."
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error running Docker Compose: {e}"
        logger.exception(error_msg)
        return False, error_msg


def handle_docker_action(action: str, model: str, app_num: int) -> Tuple[bool, str]:
    """Handle Docker actions with comprehensive error handling and intelligent retry logic."""
    logger = create_logger_for_component('utils')
    
    valid_actions = {"start", "stop", "restart", "build", "rebuild", "cleanup"}
    if action not in valid_actions:
        return False, f"Invalid action: {action}. Valid actions: {', '.join(valid_actions)}"
    
    cleanup_stale_requests()
    
    if is_request_active(model, app_num, action):
        return False, f"Request for '{action}' on {model}/app{app_num} is already in progress"
    
    request_key = mark_request_active(model, app_num, action)
    
    try:
        if not is_docker_available():
            return False, "Docker is not available or not running. Please start Docker Desktop."
        
        if not is_docker_compose_available():
            return False, "Docker Compose is not available. Please install Docker Compose."
        
        project_name = get_docker_project_name(model, app_num)
        
        with get_docker_operation_lock(project_name):
            logger.info(f"Executing '{action}' for {model}/app{app_num} (project: {project_name})")
            
            clear_container_cache(model, app_num)
            
            action_commands = {
                "start": [["up", "-d", "--remove-orphans"]],
                "stop": [["down", "--timeout", "30"]],
                "restart": [["restart"]],
                "build": [["build", "--no-cache", "--pull"]],
                "rebuild": [
                    ["down", "--timeout", "30"],
                    ["build", "--no-cache", "--pull"],
                    ["up", "-d", "--remove-orphans"]
                ],
                "cleanup": [
                    ["down", "--volumes", "--remove-orphans", "--timeout", "30"],
                    ["system", "prune", "-f", "--volumes"]
                ]
            }
            
            commands = action_commands[action]
            full_output = []
            max_retries = 2
            
            for i, cmd in enumerate(commands):
                if any(keyword in cmd for keyword in ["build", "pull"]):
                    timeout = 900
                elif any(keyword in cmd for keyword in ["up"]):
                    timeout = 300
                elif any(keyword in cmd for keyword in ["down", "prune"]):
                    timeout = 180
                else:
                    timeout = 120
                
                step_info = f"Step {i+1}/{len(commands)}: {' '.join(cmd)}"
                logger.info(f"Running {step_info}")
                full_output.append(f"--- {step_info} ---")
                
                retry_count = 0
                step_success = False
                
                while retry_count <= max_retries and not step_success:
                    success, output = run_docker_compose(cmd, model, app_num, timeout)
                    full_output.append(output)
                    
                    if success:
                        step_success = True
                        logger.info(f"Step completed successfully: {step_info}")
                        break
                        
                    retry_count += 1
                    error_output = output.lower()
                    should_retry = False
                    retry_action = None
                    
                    if retry_count <= max_retries:
                        if any(pattern in error_output for pattern in [
                            "already in use", "conflict", "container name", "address already in use"
                        ]):
                            should_retry = True
                            retry_action = "cleanup"
                            logger.warning(f"Container conflict detected for {project_name} (attempt {retry_count}/{max_retries}), attempting cleanup")
                            
                        elif any(pattern in error_output for pattern in [
                            "no such container", "container not found", "cannot kill container"
                        ]):
                            should_retry = True
                            retry_action = "cleanup"
                            logger.warning(f"Container reference issue for {project_name} (attempt {retry_count}/{max_retries}), attempting cleanup and retry")
                            
                        elif any(pattern in error_output for pattern in [
                            "network", "endpoint", "driver failed programming external connectivity"
                        ]):
                            should_retry = True
                            retry_action = "network_cleanup"
                            logger.warning(f"Network issue detected for {project_name} (attempt {retry_count}/{max_retries}), attempting network cleanup")
                            
                        elif "timeout" in error_output and "up" in cmd:
                            should_retry = True
                            retry_action = "extend_timeout"
                            timeout = min(timeout * 2, 1800)
                            logger.warning(f"Timeout detected for {project_name} (attempt {retry_count}/{max_retries}), extending timeout to {timeout}s")
                    
                    if should_retry:
                        if retry_action in ["cleanup", "network_cleanup"]:
                            logger.info(f"Attempting comprehensive cleanup for project: {project_name}")
                            conflict_handled, conflict_output = stop_conflicting_containers(project_name)
                            full_output.append(f"\n--- Retry {retry_count} Cleanup ---\n{conflict_output}")
                            
                            if conflict_handled:
                                time.sleep(2)
                                logger.info(f"Retrying after cleanup (attempt {retry_count}): {' '.join(cmd)}")
                            else:
                                logger.warning(f"Cleanup failed for {project_name}, retrying anyway")
                                time.sleep(1)
                        
                        elif retry_action == "extend_timeout":
                            time.sleep(1)
                            logger.info(f"Retrying with extended timeout (attempt {retry_count}): {' '.join(cmd)}")
                        
                        continue
                    else:
                        break
                
                if not step_success:
                    error_msg = f"Action '{action}' failed at {step_info} after {retry_count} attempts"
                    return False, f"{error_msg}\n\n{''.join(full_output)}"
            
            logger.info(f"Successfully completed '{action}' for {model}/app{app_num}")
            return True, f"Action '{action}' completed successfully.\n\n{''.join(full_output)}"
            
    finally:
        mark_request_complete(request_key)


def verify_container_health(docker_manager: DockerManager, model: str, app_num: int,
                          max_retries: int = 15, retry_delay: int = 5) -> Tuple[bool, str]:
    """Verify the health of containers for a specific application."""
    logger = create_logger_for_component('utils')
    
    try:
        backend_name, frontend_name = get_container_names_cached(model, app_num)
    except ValueError as e:
        return False, f"Invalid model/app: {e}"
        
    logger.info(f"Verifying health for {model}/app{app_num}")
    
    for attempt in range(1, max_retries + 1):
        try:
            backend = docker_manager.get_container_status(backend_name)
            frontend = docker_manager.get_container_status(frontend_name)
            
            backend_healthy = backend.running and backend.health == "healthy"
            frontend_healthy = frontend.running and frontend.health == "healthy"
            
            if backend_healthy and frontend_healthy:
                logger.info(f"Containers healthy for {model}/app{app_num}")
                return True, "All containers healthy"
                
        except Exception as e:
            logger.error(f"Health check error on attempt {attempt}: {e}")
            
        if attempt < max_retries:
            time.sleep(retry_delay)
    
    return False, "Containers failed to become healthy"


def get_app_container_statuses_cached(model: str, app_num: int, 
                                    docker_manager: DockerManager) -> Dict[str, Any]:
    """Get container statuses for a specific application with caching."""
    logger = create_logger_for_component('utils')
    cache_key = f"{model}:{app_num}:status"
    
    with _cache_lock:
        if cache_key in _container_cache:
            cached_data = _container_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                logger.debug(f"Using cached status for {model}/app{app_num}")
                return cached_data['data']
    
    try:
        backend_name, frontend_name = get_container_names_cached(model, app_num)
        
        backend_status = docker_manager.get_container_status(backend_name)
        frontend_status = docker_manager.get_container_status(frontend_name)
        
        result = {
            "backend": backend_status.to_dict() if backend_status else {},
            "frontend": frontend_status.to_dict() if frontend_status else {},
            "success": True
        }
        
        with _cache_lock:
            _container_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }
        
        logger.debug(f"Cached fresh status for {model}/app{app_num}")
        return result
        
    except Exception as e:
        logger.error(f"Error getting container statuses: {e}")
        result = {
            "backend": {},
            "frontend": {},
            "success": False,
            "error": str(e)
        }
        return result


def get_app_container_statuses(model: str, app_num: int, 
                             docker_manager: DockerManager) -> Dict[str, Any]:
    """Get container statuses for a specific application."""
    return get_app_container_statuses_cached(model, app_num, docker_manager)


def save_analysis_results(model: str, app_num: int, results, filename: str = "performance_results.json"):
    """Save analysis results as JSON in the centralized reports directory."""
    logger = create_logger_for_component('utils')
    
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    reports_dir.mkdir(parents=True, exist_ok=True)
    file_path = reports_dir / filename
    
    if hasattr(results, "to_dict"):
        data = results.to_dict()
    elif hasattr(results, "__dict__"):
        data = results.__dict__
    else:
        data = results
        
    if isinstance(data, dict):
        data["_metadata"] = {
            "model": model,
            "app_num": app_num,
            "saved_at": datetime.now().isoformat(),
            "filename": filename
        }
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved analysis results to {file_path}")
    return file_path


def load_analysis_results(model: str, app_num: int, filename: str = "performance_results.json"):
    """Load analysis results from JSON in the centralized reports directory."""
    logger = create_logger_for_component('utils')
    
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    file_path = reports_dir / filename
    
    if not file_path.exists():
        base_dir = get_models_base_dir()
        old_file_path = Path(base_dir) / model / f"app{app_num}" / filename
        if old_file_path.exists():
            logger.info(f"Found results in old location, migrating to reports directory: {old_file_path}")
            with open(old_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            save_analysis_results(model, app_num, data, filename)
            return data
        return None
        
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    logger.debug(f"Loaded analysis results from {file_path}")
    return data


def get_container_names(model: str, app_num: int) -> Tuple[str, str]:
    """Get standardized container names for an application using proper sanitization."""
    logger = create_logger_for_component('utils')
    
    if not model or app_num < 1:
        raise ValueError("Invalid model or app number")
    
    cache_key = f"{model}:{app_num}:names"
    with _cache_lock:
        if cache_key in _container_cache:
            cached_data = _container_cache[cache_key]
            if time.time() - cached_data['timestamp'] < _cache_timeout:
                return cached_data['data']
    
    app_config = get_app_config_by_model_and_number(model, app_num)
    if not app_config:
        raise ValueError(f"No configuration found for model '{model}' app {app_num}")
    
    backend_port = app_config.get('backend_port')
    frontend_port = app_config.get('frontend_port')
    
    if not backend_port or not frontend_port:
        raise ValueError(f"Missing port configuration for model '{model}' app {app_num}")
    
    project_name = get_docker_project_name(model, app_num)
    
    backend_name = f"{project_name}_backend_{backend_port}"
    frontend_name = f"{project_name}_frontend_{frontend_port}"
    
    result = (backend_name, frontend_name)
    
    with _cache_lock:
        _container_cache[cache_key] = {
            'data': result,
            'timestamp': time.time()
        }
    
    logger.debug(f"Generated container names for {model}/app{app_num}: {result}")
    return result


@lru_cache(maxsize=128)
def get_container_names_cached(model: str, app_num: int) -> Tuple[str, str]:
    """Get standardized container names for an application with LRU caching."""
    return get_container_names(model, app_num)


def process_security_analysis(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    """Process security analysis results for display."""
    return analysis_result


def stop_zap_scanners(app) -> None:
    """Stop all active ZAP scanners."""
    logger = create_logger_for_component('utils')
    try:
        if hasattr(app, 'config') and 'ZAP_SCANS' in app.config:
            scans = app.config['ZAP_SCANS']
            for scan_id in list(scans.keys()):
                try:
                    if hasattr(app, 'zap_scanner') and app.zap_scanner:
                        app.zap_scanner.stop_scan(scan_id)
                except Exception as e:
                    logger.error(f"Error stopping ZAP scan {scan_id}: {e}")
                finally:
                    scans.pop(scan_id, None)
    except Exception as e:
        logger.error(f"Error in stop_zap_scanners: {e}")


class JsonResultsManager:
    """Centralized results manager for all analysis types."""
    
    def __init__(self, base_path: Path, module_name: str):
        self.module_name = module_name
        self.project_root = Path(__file__).parent.parent
        self.reports_dir = self.project_root / "reports"
        logger = create_logger_for_component('utils')
        logger.info(f"JsonResultsManager initialized for {module_name} with reports directory: {self.reports_dir}")
    
    def save_results(self, model: str, app_num: int, results: Any, 
                    file_name: Optional[str] = None, **kwargs) -> Path:
        """Save analysis results to JSON file in the centralized reports directory."""
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        results_dir = self.reports_dir / model / f"app{app_num}"
        results_dir.mkdir(parents=True, exist_ok=True)
        results_path = results_dir / file_name
        
        data_to_save = results
        if hasattr(results, 'to_dict'):
            data_to_save = results.to_dict()
        elif hasattr(results, '__dict__'):
            data_to_save = results.__dict__
        elif isinstance(results, (list, tuple)) and all(hasattr(item, 'to_dict') for item in results):
            data_to_save = [item.to_dict() for item in results]
        
        if isinstance(data_to_save, dict):
            data_to_save["_metadata"] = {
                "module": self.module_name,
                "model": model,
                "app_num": app_num,
                "saved_at": datetime.now().isoformat(),
                "filename": file_name
            }
        
        with open(results_path, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2)
        
        logger = create_logger_for_component('utils')
        logger.info(f"Saved {self.module_name} results for {model}/app{app_num} to {results_path}")
        return results_path
    
    def load_results(self, model: str, app_num: int, 
                    file_name: Optional[str] = None, **kwargs) -> Optional[Any]:
        """Load analysis results from JSON file in the centralized reports directory."""
        logger = create_logger_for_component('utils')
        
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        results_path = self.reports_dir / model / f"app{app_num}" / file_name
        
        if not results_path.exists():
            old_paths = [
                self.project_root / "models" / model / f"app{app_num}" / "z_interface_app" / "results" / model / f"app{app_num}" / file_name,
                self.project_root / "models" / model / f"app{app_num}" / file_name
            ]
            
            for old_path in old_paths:
                if old_path.exists():
                    logger.info(f"Found {self.module_name} results in old location, migrating: {old_path}")
                    with open(old_path, "r", encoding='utf-8') as f:
                        data = json.load(f)
                    self.save_results(model, app_num, data, file_name)
                    return data
            
            logger.debug(f"No {self.module_name} results found for {model}/app{app_num}")
            return None
        
        with open(results_path, "r", encoding='utf-8') as f:
            data = json.load(f)
        
        logger.debug(f"Loaded {self.module_name} results for {model}/app{app_num} from {results_path}")
        return data


def load_json_results_for_template(model: str, app_num: int, analysis_type: Optional[str] = None) -> Dict[str, Any]:
    """Load JSON results from the centralized reports directory for template display."""
    logger = create_logger_for_component('utils')
    results = {}
    
    analysis_files = {
        'backend_security': '.backend_security_results.json',
        'frontend_security': '.frontend_security_results.json',
        'zap_scan': 'zap_results.json',
        'performance': 'performance_results.json',
        'gpt4all': '.openrouter_requirements.json',
        'code_quality': '.code_quality_results.json'
    }
    
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    if not reports_dir.exists():
        logger.debug(f"No results directory found for {model}/app{app_num}")
        return results
    
    if analysis_type and analysis_type in analysis_files:
        file_path = reports_dir / analysis_files[analysis_type]
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    results[analysis_type] = json.load(f)
                logger.debug(f"Loaded {analysis_type} results for {model}/app{app_num}")
            except Exception as e:
                logger.error(f"Error loading {analysis_type} results for {model}/app{app_num}: {e}")
                results[analysis_type] = {'error': str(e)}
    else:
        for analysis_name, file_name in analysis_files.items():
            file_path = reports_dir / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        results[analysis_name] = json.load(f)
                    logger.debug(f"Loaded {analysis_name} results for {model}/app{app_num}")
                except Exception as e:
                    logger.error(f"Error loading {analysis_name} results for {model}/app{app_num}: {e}")
                    results[analysis_name] = {'error': str(e)}
    
    return results


def get_available_analysis_results(model: str, app_num: int) -> List[str]:
    """Get list of available analysis results for a model/app combination."""
    analysis_files = {
        'backend_security': '.backend_security_results.json',
        'frontend_security': '.frontend_security_results.json',
        'zap_scan': 'zap_results.json',
        'performance': 'performance_results.json',
        'gpt4all': '.openrouter_requirements.json',
        'code_quality': '.code_quality_results.json'
    }
    
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    available = []
    if reports_dir.exists():
        for analysis_name, file_name in analysis_files.items():
            file_path = reports_dir / file_name
            if file_path.exists():
                available.append(analysis_name)
    
    return available


def get_latest_analysis_timestamp(model: str, app_num: int) -> Optional[str]:
    """Get the timestamp of the most recent analysis for a model/app."""
    project_root = Path(__file__).parent.parent
    reports_dir = project_root / "reports" / model / f"app{app_num}"
    
    if not reports_dir.exists():
        return None
    
    latest_time = None
    for file_path in reports_dir.glob("*.json"):
        try:
            stat = file_path.stat()
            if latest_time is None or stat.st_mtime > latest_time:
                latest_time = stat.st_mtime
        except Exception:
            continue
    
    if latest_time:
        return datetime.fromtimestamp(latest_time).isoformat()
    return None


def get_bulk_container_statuses(apps: List[Dict[str, Any]], 
                               docker_manager: DockerManager) -> Dict[str, Dict[str, Any]]:
    """Get container statuses for multiple applications efficiently."""
    logger = create_logger_for_component('utils')
    results = {}
    
    apps_by_model = {}
    for app in apps:
        model = app.get('model')
        if model not in apps_by_model:
            apps_by_model[model] = []
        apps_by_model[model].append(app)
    
    for model, model_apps in apps_by_model.items():
        for app in model_apps:
            app_num = app.get('app_num')
            if app_num:
                key = f"{model}:{app_num}"
                try:
                    status = get_app_container_statuses_cached(model, app_num, docker_manager)
                    results[key] = status
                except Exception as e:
                    logger.error(f"Error getting status for {model}/app{app_num}: {e}")
                    results[key] = {
                        "backend": {},
                        "frontend": {},
                        "success": False,
                        "error": str(e)
                    }
    
    return results


def refresh_container_cache_background(apps: List[Dict[str, Any]], 
                                     docker_manager: DockerManager) -> None:
    """Refresh container cache in the background."""
    logger = create_logger_for_component('utils')
    
    def refresh_worker():
        try:
            logger.info("Starting background cache refresh")
            clear_container_cache()
            refresh_cache_directly(apps, docker_manager)
            logger.info("Background cache refresh completed")
        except Exception as e:
            logger.error(f"Background cache refresh failed: {e}")
    
    thread = threading.Thread(target=refresh_worker, daemon=True)
    thread.start()


def refresh_cache_directly(apps: List[Dict[str, Any]], docker_manager: DockerManager) -> None:
    """Refresh cache directly without Flask application context dependencies."""
    logger = create_logger_for_component('utils')
    
    for app in apps:
        model = app.get('model')
        app_num = app.get('app_num')
        
        if not model or not app_num:
            continue
            
        try:
            cache_key = f"{model}:{app_num}:status"
            
            backend_port = app.get('backend_port')
            frontend_port = app.get('frontend_port')
            
            if backend_port and frontend_port:
                project_name = get_docker_project_name(model, app_num)
                backend_name = f"{project_name}_backend_{backend_port}"
                frontend_name = f"{project_name}_frontend_{frontend_port}"
                
                backend_status = docker_manager.get_container_status(backend_name)
                frontend_status = docker_manager.get_container_status(frontend_name)
                
                result = {
                    "backend": backend_status.to_dict() if backend_status else {},
                    "frontend": frontend_status.to_dict() if frontend_status else {},
                    "success": True
                }
                
                with _cache_lock:
                    _container_cache[cache_key] = {
                        'data': result,
                        'timestamp': time.time()
                    }
                
                logger.debug(f"Cached status for {model}/app{app_num} in background")
            
        except Exception as e:
            logger.warning(f"Failed to cache status for {model}/app{app_num}: {e}")


def get_dashboard_data_optimized(docker_manager: DockerManager) -> Dict[str, Any]:
    """Get optimized dashboard data with caching and bulk operations."""
    logger = create_logger_for_component('utils')
    
    try:
        all_apps = get_all_apps()
        container_statuses = get_bulk_container_statuses(all_apps, docker_manager)
        
        enhanced_apps = []
        for app in all_apps:
            app_key = f"{app['model']}:{app['app_num']}"
            status_data = container_statuses.get(app_key, {})
            
            app_enhanced = app.copy()
            app_enhanced['backend_status'] = status_data.get('backend', {})
            app_enhanced['frontend_status'] = status_data.get('frontend', {})
            app_enhanced['container_success'] = status_data.get('success', False)
            
            enhanced_apps.append(app_enhanced)
        
        models = get_ai_models()
        
        try:
            warm_container_cache_safe(all_apps, docker_manager)
        except Exception as e:
            logger.warning(f"Background cache warming failed: {e}")
        
        return {
            'apps': enhanced_apps,
            'models': models,
            'cache_used': True,
            'total_apps': len(enhanced_apps)
        }
        
    except Exception as e:
        logger.error(f"Error getting optimized dashboard data: {e}")
        return {
            'apps': [],
            'models': [],
            'cache_used': False,
            'error': str(e)
        }


def warm_container_cache(docker_manager: DockerManager) -> bool:
    """Warm up the container cache by pre-loading all app statuses."""
    logger = create_logger_for_component('utils')
    
    try:
        logger.info("Warming up container cache...")
        
        try:
            from flask import has_app_context
            if has_app_context():
                all_apps = get_all_apps()
            else:
                logger.warning("No Flask app context available, skipping cache warming")
                return True
        except ImportError:
            logger.warning("Flask not available, skipping cache warming")
            return True
        
        refresh_container_cache_background(all_apps, docker_manager)
        
        logger.info(f"Cache warming initiated for {len(all_apps)} apps")
        return True
        
    except Exception as e:
        logger.error(f"Error warming container cache: {e}")
        return False


def warm_container_cache_safe(apps: List[Dict[str, Any]], docker_manager: DockerManager) -> bool:
    """Safely warm up the container cache with provided app data."""
    logger = create_logger_for_component('utils')
    
    try:
        logger.info(f"Safely warming up container cache for {len(apps)} apps...")
        refresh_container_cache_background(apps, docker_manager)
        logger.info(f"Safe cache warming initiated for {len(apps)} apps")
        return True
        
    except Exception as e:
        logger.error(f"Error in safe cache warming: {e}")
        return False


def get_cache_stats() -> Dict[str, Any]:
    """Get container cache statistics including Docker-specific caches."""
    current_time = time.time()
    
    with _cache_lock:
        active_entries = 0
        expired_entries = 0
        
        for key, cached_data in _container_cache.items():
            if current_time - cached_data['timestamp'] < _cache_timeout:
                active_entries += 1
            else:
                expired_entries += 1
    
    with _docker_cache_lock:
        docker_active = 0
        docker_expired = 0
        
        for key, cached_data in _docker_project_names_cache.items():
            if current_time - cached_data['timestamp'] < _cache_timeout:
                docker_active += 1
            else:
                docker_expired += 1
    
    return {
        'container_cache': {
            'total_entries': len(_container_cache),
            'active_entries': active_entries,
            'expired_entries': expired_entries,
        },
        'docker_names_cache': {
            'total_entries': len(_docker_project_names_cache),
            'active_entries': docker_active,
            'expired_entries': docker_expired,
        },
        'cache_timeout': _cache_timeout,
        'docker_available': DOCKER_AVAILABLE,
        'docker_compose_available': DOCKER_COMPOSE_AVAILABLE
    }


def get_docker_system_status() -> Dict[str, Any]:
    """Get comprehensive Docker system status."""
    status = {
        'docker_available': is_docker_available(),
        'docker_compose_available': is_docker_compose_available(),
        'cache_stats': get_cache_stats(),
        'timestamp': datetime.now().isoformat()
    }
    
    if status['docker_available']:
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                docker_info = json.loads(result.stdout)
                status['docker_version'] = {
                    'client': docker_info.get('Client', {}).get('Version', 'Unknown'),
                    'server': docker_info.get('Server', {}).get('Version', 'Unknown')
                }
        except Exception as e:
            status['docker_version_error'] = str(e)
        
        try:
            result = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0:
                running_containers = len([line.strip() for line in result.stdout.strip().split('\n') if line.strip()])
                status['running_containers'] = running_containers
        except Exception as e:
            status['container_count_error'] = str(e)
    
    return status


def diagnose_docker_issues(model: str, app_num: int) -> Dict[str, Any]:
    """Diagnose common Docker issues for a specific application."""
    logger = create_logger_for_component('utils')
    
    diagnostics = {
        'model': model,
        'app_num': app_num,
        'timestamp': datetime.now().isoformat(),
        'issues': [],
        'suggestions': [],
        'status': 'healthy'
    }
    
    try:
        if not is_docker_available():
            diagnostics['issues'].append('Docker is not available or not running')
            diagnostics['suggestions'].append('Start Docker Desktop and ensure it is running properly')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        if not is_docker_compose_available():
            diagnostics['issues'].append('Docker Compose is not available')
            diagnostics['suggestions'].append('Install Docker Compose or ensure it is in your PATH')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        try:
            app_dir = get_app_directory(model, app_num)
            diagnostics['app_directory'] = str(app_dir)
        except FileNotFoundError:
            diagnostics['issues'].append(f'Application directory not found for {model}/app{app_num}')
            diagnostics['suggestions'].append('Verify the model name and app number are correct')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        compose_file = None
        for filename in ["docker-compose.yml", "docker-compose.yaml"]:
            potential_path = app_dir / filename
            if potential_path.exists():
                compose_file = potential_path
                break
        
        if not compose_file:
            diagnostics['issues'].append('No docker-compose file found')
            diagnostics['suggestions'].append('Ensure docker-compose.yml exists in the application directory')
            diagnostics['status'] = 'critical'
            return diagnostics
        
        diagnostics['compose_file'] = str(compose_file)
        
        project_name = get_docker_project_name(model, app_num)
        diagnostics['project_name'] = project_name
        
        try:
            result = subprocess.run(
                ["docker", "ps", "-a", "--filter", f"name={project_name}", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                containers = []
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        parts = line.strip().split('\t')
                        containers.append({
                            'name': parts[0],
                            'status': parts[1] if len(parts) > 1 else 'unknown'
                        })
                
                diagnostics['existing_containers'] = containers
                
                stopped_containers = [c for c in containers if 'Exited' in c['status']]
                if stopped_containers:
                    diagnostics['issues'].append(f'Found {len(stopped_containers)} stopped containers that may cause conflicts')
                    diagnostics['suggestions'].append('Run cleanup action to remove stopped containers')
                    if diagnostics['status'] == 'healthy':
                        diagnostics['status'] = 'warning'
        
        except Exception as e:
            diagnostics['issues'].append(f'Could not check for container conflicts: {e}')
            diagnostics['suggestions'].append('Docker may be experiencing issues')
            if diagnostics['status'] == 'healthy':
                diagnostics['status'] = 'warning'
        
        app_config = get_app_config_by_model_and_number(model, app_num)
        if app_config:
            backend_port = app_config.get('backend_port')
            frontend_port = app_config.get('frontend_port')
            
            diagnostics['ports'] = {
                'backend': backend_port,
                'frontend': frontend_port
            }
            
            if not backend_port or not frontend_port:
                diagnostics['issues'].append('Port configuration is incomplete')
                diagnostics['suggestions'].append('Check port_config.json for missing port assignments')
                if diagnostics['status'] == 'healthy':
                    diagnostics['status'] = 'warning'
        
        if not diagnostics['issues']:
            diagnostics['suggestions'].append('Docker setup appears to be healthy')
        
    except Exception as e:
        diagnostics['issues'].append(f'Unexpected error during diagnosis: {e}')
        diagnostics['suggestions'].append('Check application logs for more details')
        diagnostics['status'] = 'error'
    
    return diagnostics


def reset_docker_environment() -> Tuple[bool, str]:
    """Reset Docker environment by clearing caches and checking availability."""
    logger = create_logger_for_component('utils')
    
    try:
        logger.info("Resetting Docker environment...")
        
        clear_docker_caches()
        
        docker_available = is_docker_available()
        compose_available = is_docker_compose_available()
        
        cleanup_expired_cache()
        
        system_status = get_docker_system_status()
        
        if docker_available and compose_available:
            message = "Docker environment reset successfully. Docker and Docker Compose are available."
        elif docker_available:
            message = "Docker environment reset. Docker is available but Docker Compose is not."
        else:
            message = "Docker environment reset. Docker is not available - please start Docker Desktop."
        
        logger.info(message)
        return True, message
        
    except Exception as e:
        error_msg = f"Error resetting Docker environment: {e}"
        logger.error(error_msg)
        return False, error_msg


# ===========================
# BATCH ANALYSIS HELPERS
# ===========================

def _create_safe_job_dict(job: BatchJob) -> Dict[str, Any]:
    """Create a template-safe job dictionary."""
    logger = create_logger_for_component('batch_analysis')
    try:
        return job.to_dict()
    except Exception as e:
        logger.error(f"Error creating safe job dict: {str(e)}")
        return {
            'id': str(job.id) if hasattr(job, 'id') else 'unknown',
            'name': str(job.name) if hasattr(job, 'name') else 'Unknown Job',
            'description': '',
            'status': 'error',
            'created_at_formatted': 'Unknown',
            'progress': {'total': 0, 'completed': 0, 'failed': 0}
        }


def _create_safe_task_dict(task: BatchTask) -> Dict[str, Any]:
    """Create a template-safe task dictionary."""
    logger = create_logger_for_component('batch_analysis')
    try:
        return task.to_dict()
    except Exception as e:
        logger.error(f"Error creating safe task dict: {str(e)}")
        return {
            'id': str(task.id) if hasattr(task, 'id') else 'unknown',
            'model': str(task.model) if hasattr(task, 'model') else 'unknown',
            'app_num': int(task.app_num) if hasattr(task, 'app_num') else 0,
            'analysis_type': str(task.analysis_type) if hasattr(task, 'analysis_type') else 'unknown',
            'status': 'error',
            'issues_count': None,
            'duration_seconds': None
        }


def _calculate_progress_stats(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate progress statistics from tasks."""
    stats = {
        'progress': {
            'total': len(tasks),
            'completed': 0,
            'running': 0,
            'pending': 0,
            'failed': 0,
            'cancelled': 0
        }
    }
    
    for task in tasks:
        status = task.get('status', 'unknown')
        if status in stats['progress']:
            stats['progress'][status] += 1
    
    return stats


# ===========================
# APPLICATION FACTORY AND HELPERS
# ===========================

class AnalyzerProtocol(Protocol):
    """Protocol for analyzer classes."""
    
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the analyzer."""
        ...


class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(self, message: str, code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InitializationError(AppError):
    """Exception raised during application initialization."""
    pass


class ServiceManager:
    """Manages application services and their lifecycle."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.logger = create_logger_for_component('service_manager')
        self._services: Dict[str, Any] = {}
        self._cleanup_lock = threading.RLock()
        
        if not hasattr(app, 'extensions'):
            app.extensions = {}
    
    def register_service(self, name: str, service: Any) -> None:
        """Register a service with the manager."""
        with self._cleanup_lock:
            self._services[name] = service
            setattr(self.app, name, service)
            self.app.extensions[name] = service
            self.logger.info(f"Registered service: {name}")
    
    def get_service(self, name: str) -> Optional[Any]:
        """Get a registered service."""
        return self._services.get(name)
    
    def cleanup_services(self) -> None:
        """Clean up all registered services."""
        with self._cleanup_lock:
            for name, service in self._services.items():
                try:
                    if hasattr(service, 'cleanup'):
                        service.cleanup()
                    self.logger.info(f"Cleaned up service: {name}")
                except Exception as e:
                    self.logger.error(f"Error cleaning up service {name}: {e}")


class HostPortValidator:
    """Validates host and port configuration."""
    
    @staticmethod
    def validate(host: Optional[str], port: Optional[int]) -> Tuple[str, int]:
        """Validate and return host and port configuration."""
        defaults = AppDefaults()
        
        if not host or not isinstance(host, str) or not host.strip():
            validated_host = defaults.HOST
        else:
            validated_host = host.strip()
        
        if port is None or not isinstance(port, int) or not (1 <= port <= 65535):
            validated_port = defaults.PORT
        else:
            validated_port = port
            
        return validated_host, validated_port


class ErrorResponseGenerator:
    """Generates appropriate error responses for different request types."""
    
    @staticmethod
    def generate(error_code: int, error_name: str, error_message: str) -> Tuple[Any, int]:
        """Generate an appropriate error response based on request type."""
        if request.path.startswith('/api/'):
            response = jsonify({
                'error': {
                    'code': error_code,
                    'name': error_name,
                    'message': error_message,
                    'timestamp': time.time()
                }
            })
        else:
            try:
                debug_mode = current_app.config.get("DEBUG", False)
            except RuntimeError:
                debug_mode = False
            response = render_template(
                'error.html',
                error_code=error_code,
                error_name=error_name,
                error_message=error_message,
                debug=debug_mode
            )
        return response, error_code


class ScanCleanupManager:
    """Manages cleanup of old ZAP scans."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.logger = create_logger_for_component('cleanup.scans')
        self._cleanup_lock = threading.RLock()
        self._running = True
        self.defaults = AppDefaults()
    
    def start_cleanup_thread(self) -> None:
        """Start the background cleanup thread."""
        cleanup_thread = threading.Thread(
            target=self._cleanup_task,
            daemon=True,
            name="ScanCleanup"
        )
        cleanup_thread.start()
        self.logger.info("Scan cleanup thread started")
    
    def stop(self) -> None:
        """Stop the cleanup manager."""
        self._running = False
    
    def _cleanup_task(self) -> None:
        """Periodically clean up old ZAP scans."""
        while self._running:
            try:
                time.sleep(self.defaults.CLEANUP_INTERVAL)
                self._perform_cleanup()
            except Exception as e:
                self.logger.error(f"Error in scan cleanup: {e}")
    
    def _perform_cleanup(self) -> None:
        """Perform the actual cleanup operation."""
        with self._cleanup_lock:
            if not hasattr(self.app, 'config') or 'ZAP_SCANS' not in self.app.config:
                return
            
            scans = self.app.config['ZAP_SCANS']
            current_time = time.time()
            
            self._remove_idle_scans(scans, current_time)
            self._limit_total_scans(scans)
    
    def _remove_idle_scans(self, scans: Dict[str, Any], current_time: float) -> None:
        """Remove scans that have been idle too long."""
        to_remove = [
            scan_id for scan_id, scan_data in scans.items()
            if current_time - scan_data.get('last_update', 0) > self.defaults.IDLE_SCAN_TIMEOUT
        ]
        
        for scan_id in to_remove:
            self.logger.info(f"Removing idle scan: {scan_id}")
            scans.pop(scan_id, None)
    
    def _limit_total_scans(self, scans: Dict[str, Any]) -> None:
        """Limit the total number of scans to prevent memory issues."""
        if len(scans) <= self.defaults.MAX_ZAP_SCANS:
            return
        
        oldest_scans = sorted(
            scans.items(),
            key=lambda x: x[1].get('last_update', 0)
        )
        
        excess_count = len(scans) - self.defaults.MAX_ZAP_SCANS
        for scan_id, _ in oldest_scans[:excess_count]:
            self.logger.info(f"Removing excess scan: {scan_id}")
            scans.pop(scan_id, None)


class AnalyzerInitializer:
    """Handles initialization of various analyzers."""
    
    def __init__(self, app: Flask, service_manager: ServiceManager) -> None:
        self.app = app
        self.service_manager = service_manager
        self.logger = create_logger_for_component('init.analyzers')
    
    def initialize_all(self, project_root_path: Path, app_base_dir: Path) -> None:
        """Initialize all analyzers used by the application."""
        models_dir = project_root_path / "models"
        
        self._initialize_security_analyzers(models_dir)
        self._initialize_quality_analyzers(models_dir)
        self._initialize_openrouter_analyzer(project_root_path)
        self._initialize_performance_tester(app_base_dir)
        self._initialize_gpt4all_analyzer()
        self._initialize_zap_scanner(app_base_dir)
        
        self.logger.info("All analyzers initialized")
    
    def _initialize_analyzer(
        self,
        analyzer_class: Type[AnalyzerProtocol],
        service_name: str,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Initialize a single analyzer."""
        try:
            self.logger.info(f"Initializing {analyzer_class.__name__}")
            analyzer = analyzer_class(*args, **kwargs)
            self.service_manager.register_service(service_name, analyzer)
            self.logger.info(f"{analyzer_class.__name__} initialized successfully")
        except Exception as e:
            self.logger.exception(f"Failed to initialize {analyzer_class.__name__}: {e}")
            self.service_manager.register_service(service_name, None)
    
    def _initialize_security_analyzers(self, models_dir: Path) -> None:
        """Initialize security analyzers."""
        try:
            from cli_tools_analysis import BackendSecurityAnalyzer, FrontendSecurityAnalyzer
            
            self._initialize_analyzer(
                BackendSecurityAnalyzer,
                'backend_security_analyzer',
                models_dir
            )
            self._initialize_analyzer(
                FrontendSecurityAnalyzer,
                'frontend_security_analyzer',
                models_dir
            )
        except ImportError as e:
            self.logger.error(f"Security analyzers not available: {e}")
    
    def _initialize_quality_analyzers(self, models_dir: Path) -> None:
        """Initialize code quality analyzers."""
        try:
            from cli_tools_analysis import BackendQualityAnalyzer, FrontendQualityAnalyzer
            
            self._initialize_analyzer(
                BackendQualityAnalyzer,
                'backend_quality_analyzer',
                models_dir
            )
            self._initialize_analyzer(
                FrontendQualityAnalyzer,
                'frontend_quality_analyzer',
                models_dir
            )
        except ImportError as e:
            self.logger.error(f"Quality analyzers not available: {e}")
    
    def _initialize_openrouter_analyzer(self, project_root_path: Path) -> None:
        """Initialize OpenRouter analyzer."""
        try:
            from openrouter_analyzer import OpenRouterAnalyzer
            
            openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
            if not openrouter_api_key:
                self.logger.warning("OPENROUTER_API_KEY not found in environment")
            self._initialize_analyzer(
                OpenRouterAnalyzer,
                'openrouter_analyzer',
                str(project_root_path)
            )
        except ImportError as e:
            self.logger.error(f"OpenRouter analyzer not available: {e}")
    
    def _initialize_performance_tester(self, app_base_dir: Path) -> None:
        """Initialize performance tester with lazy loading to avoid monkey-patching issues."""
        performance_report_dir = app_base_dir / "performance_reports"
        performance_report_dir.mkdir(exist_ok=True)
        
        try:
            from performance_analysis import LocustPerformanceTester
            self._initialize_analyzer(
                LocustPerformanceTester,
                'performance_tester',
                performance_report_dir
            )
            
            performance_tester = self.service_manager.get_service('performance_tester')
            if performance_tester:
                self.service_manager.register_service('performance_analyzer', performance_tester)
        except Exception as init_error:
            error_message = f"Performance testing unavailable: {init_error}"
            self.logger.warning(f"Performance tester initialization failed: {init_error}")
            
            class PlaceholderPerformanceTester:
                def __init__(self, *args, **kwargs):
                    self.available = False
                    self.error_message = error_message
                
                def run_test_library(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def run_test_cli(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def run_performance_test(self, model, app_num):
                    raise RuntimeError(self.error_message)
            
            self.service_manager.register_service('performance_tester', PlaceholderPerformanceTester())
            
            placeholder = self.service_manager.get_service('performance_tester')
            if placeholder:
                self.service_manager.register_service('performance_analyzer', placeholder)
    
    def _initialize_gpt4all_analyzer(self) -> None:
        """Initialize GPT4All analyzer for batch processing."""
        try:
            # Try to import from the gpt4all_analyzer file if it exists
            import importlib.util
            spec = importlib.util.find_spec('gpt4all_analyzer')
            if spec is not None:
                from gpt4all_analyzer import create_gpt4all_analyzer
                analyzer = create_gpt4all_analyzer()
                self.service_manager.register_service('gpt4all_analyzer', analyzer)
                self.logger.info("GPT4All analyzer initialized successfully")
                return
            
            # If module doesn't exist, create a placeholder
            raise ImportError("gpt4all_analyzer module not found")
            
        except Exception as e:
            self.logger.warning(f"GPT4All analyzer initialization failed: {e}")
            error_msg = f"GPT4All analyzer unavailable: {e}"
            
            class PlaceholderGPT4AllAnalyzer:
                def __init__(self):
                    self.available = False
                    self.error_message = error_msg
                
                def analyze_app(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def is_available(self):
                    return False
            
            self.service_manager.register_service('gpt4all_analyzer', PlaceholderGPT4AllAnalyzer())
    
    def _initialize_zap_scanner(self, app_base_dir: Path) -> None:
        """Initialize ZAP scanner with better error handling and logging."""
        try:
            self.logger.info("[ZAP INIT] Starting ZAP scanner initialization")
            self.logger.info(f"[ZAP INIT] App base directory: {app_base_dir}")
            
            zap_scanner = create_scanner(app_base_dir)
            
            if zap_scanner:
                self.logger.info("[ZAP INIT] ZAP scanner instance created successfully")
                self.service_manager.register_service('zap_scanner', zap_scanner)
                self.app.config["ZAP_SCANS"] = {}
                
                if hasattr(zap_scanner, 'is_ready'):
                    ready = zap_scanner.is_ready()
                    self.logger.info(f"[ZAP INIT] Scanner ready status: {ready}")
                else:
                    self.logger.warning("[ZAP INIT] Scanner does not have is_ready method")
                    
                self.logger.info("[ZAP INIT] ZAP scanner initialization complete")
            else:
                self.logger.error("[ZAP INIT] create_zap_scanner returned None")
                
                class PlaceholderZAPScanner:
                    def __init__(self):
                        self.available = False
                        self.error_message = "ZAP scanner not available - zapv2 module not installed"
                    
                    def start_scan(self, *args, **kwargs):
                        raise RuntimeError(self.error_message)
                    
                    def scan_app(self, model, app_num):
                        raise RuntimeError(self.error_message)
                    
                    def is_ready(self):
                        return False
                
                self.service_manager.register_service('zap_scanner', PlaceholderZAPScanner())
                self.app.config["ZAP_SCANS"] = {}
                
        except Exception as zap_init_error:
            self.logger.exception(f"[ZAP INIT ERROR] Failed to initialize ZAP scanner: {zap_init_error}")
            
            class ZAPErrorPlaceholder:
                def __init__(self, error_msg):
                    self.available = False
                    self.error_message = f"ZAP scanner initialization failed: {error_msg}"
                
                def start_scan(self, *args, **kwargs):
                    raise RuntimeError(self.error_message)
                
                def scan_app(self, model, app_num):
                    raise RuntimeError(self.error_message)
                
                def is_ready(self):
                    return False
            
            self.service_manager.register_service('zap_scanner', ZAPErrorPlaceholder(str(zap_init_error)))
            self.app.config["ZAP_SCANS"] = {}


class ServiceInitializer:
    """Handles initialization of application services."""
    
    def __init__(self, app: Flask, service_manager: ServiceManager) -> None:
        self.app = app
        self.service_manager = service_manager
        self.logger = create_logger_for_component('init.services')
    
    def initialize_all(self) -> None:
        """Initialize all services used by the application."""
        self._initialize_docker_manager()
        self._initialize_scan_manager()
        self._initialize_port_manager()
        self._initialize_health_monitor()
    
    def _initialize_docker_manager(self) -> None:
        """Initialize Docker Manager."""
        try:
            docker_manager = DockerManager()
            self.service_manager.register_service('docker_manager', docker_manager)
            self.app.config["docker_manager"] = docker_manager
            self.logger.info("DockerManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize DockerManager: {e}")
            self.service_manager.register_service('docker_manager', None)
            self.app.config["docker_manager"] = None
    
    def _initialize_scan_manager(self) -> None:
        """Initialize Scan Manager."""
        try:
            scan_manager = ScanManager()
            self.service_manager.register_service('scan_manager', scan_manager)
            self.logger.info("ScanManager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize ScanManager: {e}")
            self.service_manager.register_service('scan_manager', None)
    
    def _initialize_port_manager(self) -> None:
        """Initialize Port Manager."""
        try:
            port_config = self.app.config.get('PORT_CONFIG', [])
            port_manager = PortManager(port_config)
            self.service_manager.register_service('port_manager', port_manager)
            self.logger.info(f"PortManager initialized with {len(port_config)} configurations")
        except Exception as e:
            self.logger.error(f"Failed to initialize PortManager: {e}")
            self.service_manager.register_service('port_manager', None)
    
    def _initialize_health_monitor(self) -> None:
        """Initialize System Health Monitor."""
        try:
            health_monitor = SystemHealthMonitor()
            self.service_manager.register_service('health_monitor', health_monitor)
            self.logger.info("SystemHealthMonitor initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SystemHealthMonitor: {e}")
            self.service_manager.register_service('health_monitor', None)


class ErrorHandlerRegistry:
    """Registers error handlers for the Flask application."""
    
    @staticmethod
    def register_all(app: Flask) -> None:
        """Register all error handlers for the application."""
        app.register_error_handler(HTTPException, ErrorHandlerRegistry._handle_http_exception)
        app.register_error_handler(BadRequest, ErrorHandlerRegistry._handle_bad_request)
        app.register_error_handler(Exception, ErrorHandlerRegistry._handle_generic_exception)
    
    @staticmethod
    def _handle_http_exception(e: HTTPException) -> Tuple[Response, int]:
        """Handle HTTP exceptions."""
        return ErrorResponseGenerator.generate(
            e.code or 500,
            e.name,
            e.description or "An error occurred"
        )
    
    @staticmethod
    def _handle_bad_request(e: BadRequest) -> Tuple[Response, int]:
        """Handle bad request exceptions."""
        return ErrorResponseGenerator.generate(
            400,
            "Bad Request",
            e.description or "The request could not be understood by the server."
        )
    
    @staticmethod
    def _handle_generic_exception(e: Exception) -> Tuple[Response, int]:
        """Handle generic exceptions."""
        logger = create_logger_for_component('error_handler')
        logger.exception(f"Unhandled exception: {e}")
        
        if current_app.config.get("DEBUG"):
            error_message = f"{type(e).__name__}: {str(e)}"
        else:
            error_message = "An internal server error occurred."
        
        return ErrorResponseGenerator.generate(500, "Internal Server Error", error_message)


class ContextProcessorRegistry:
    """Registers context processors for template rendering."""
    
    @staticmethod
    def register_all(app: Flask) -> None:
        """Register template context processors."""
        @app.context_processor
        def inject_global_context() -> Dict[str, Any]:
            return {
                'port_config': app.config.get('PORT_CONFIG', []),
                'ai_models': app.config.get('AI_MODELS', []),
                'HAS_BATCH_ANALYSIS': app.config.get('HAS_BATCH_ANALYSIS', False),
                'get_apps_for_model': get_apps_for_model,
                'load_json_results': load_json_results_for_template
            }


class ConfigurationLoader:
    """Loads and validates application configuration."""
    
    def __init__(self, app_base_dir: Path) -> None:
        self.app_base_dir = app_base_dir
        self.logger = create_logger_for_component('config_loader')
    
    def load_configuration(self, app: Flask) -> None:
        """Load all configuration for the application."""
        config = AppConfig.from_env()
        app.config.from_object(config)
        app.config['APP_CONFIG'] = config
        
        self._load_port_configuration(app)
        self._load_batch_analysis_configuration(app)
        
        app.config['JSON_SORT_KEYS'] = False
    
    def _load_port_configuration(self, app: Flask) -> None:
        """Load port configuration and initialize model integration service."""
        self.logger.info("Loading port configuration")
        project_root = self.app_base_dir.parent
        port_config = load_port_config(project_root)
        app.config['PORT_CONFIG'] = port_config
        
        self.logger.info(f"Initializing model integration service with path: {project_root}")
        model_service = initialize_model_service(project_root)
        app.config['MODEL_SERVICE'] = model_service
        
        app.config['AI_MODELS'] = get_ai_models_from_config(port_config)
        
        all_models = model_service.get_all_models()
        app.config['ENHANCED_MODELS'] = all_models
        app.config['MODEL_STATS'] = model_service.get_summary_stats()
        
        self.logger.info(f"Loaded {len(port_config)} port configurations")
        self.logger.info(f"Integrated {len(all_models)} enhanced models with full capabilities")
    
    def _load_batch_analysis_configuration(self, app: Flask) -> None:
        """Load batch analysis configuration."""
        app.config['HAS_BATCH_ANALYSIS'] = True
        self.logger.info("Batch analysis module enabled")


class CacheCleanupManager:
    """Manager for periodic cache cleanup."""
    
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.cleanup_interval = 300
        self.cleanup_thread = None
        self.shutdown_event = threading.Event()
        self.logger = create_logger_for_component('cache_cleanup')
    
    def start_cleanup_thread(self) -> None:
        """Start the cache cleanup thread."""
        if self.cleanup_thread is None or not self.cleanup_thread.is_alive():
            self.cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True,
                name="CacheCleanup"
            )
            self.cleanup_thread.start()
            self.logger.info("Cache cleanup thread started")
    
    def stop_cleanup_thread(self) -> None:
        """Stop the cache cleanup thread."""
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.shutdown_event.set()
            self.cleanup_thread.join(timeout=5)
            self.logger.info("Cache cleanup thread stopped")
    
    def _cleanup_worker(self) -> None:
        """Background worker for cache cleanup."""
        while not self.shutdown_event.is_set():
            try:
                if self.shutdown_event.wait(self.cleanup_interval):
                    break
                
                try:
                    cleanup_expired_cache()
                    self.logger.debug("Performed periodic cache cleanup")
                except Exception as cleanup_error:
                    self.logger.warning(f"Cache cleanup failed: {cleanup_error}")
                    
            except Exception as e:
                self.logger.error(f"Error in cache cleanup worker: {e}")
                time.sleep(60)
    
    def cleanup(self) -> None:
        """Cleanup method called on application shutdown."""
        self.stop_cleanup_thread()


class FlaskApplicationFactory:
    """Factory for creating and configuring Flask applications."""
    
    def __init__(self) -> None:
        self.logger = None
        self.service_manager = None
        self.cleanup_manager = None
        self.cache_cleanup_manager = None
    
    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        try:
            app_base_dir = Path(__file__).parent.resolve()
            project_root_path = app_base_dir.parent.resolve()
            
            app = self._create_flask_instance(app_base_dir)
            
            initialize_logging(app)
            self.logger = create_logger_for_component('app_startup')
            
            self._configure_application(app, app_base_dir, project_root_path)
            
            self.logger.info("Application initialization complete")
            return app
            
        except Exception as e:
            if self.logger:
                self.logger.exception(f"Failed to create application: {e}")
            raise InitializationError(f"Application initialization failed: {e}")
    
    def _create_flask_instance(self, app_base_dir: Path) -> Flask:
        """Create the basic Flask instance."""
        return Flask(
            __name__,
            template_folder=str(app_base_dir / "templates"),
            static_folder=str(app_base_dir / "static")
        )
    
    def _configure_application(
        self,
        app: Flask,
        app_base_dir: Path,
        project_root_path: Path
    ) -> None:
        """Configure the Flask application with all necessary components."""
        config_loader = ConfigurationLoader(app_base_dir)
        config_loader.load_configuration(app)
        
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=1, x_proto=1, x_host=1, x_prefix=1
        )
        
        self.service_manager = ServiceManager(app)
        self.cleanup_manager = ScanCleanupManager(app)
        self.cache_cleanup_manager = CacheCleanupManager(app)
        
        app.extensions['service_manager'] = self.service_manager
        app.extensions['cleanup_manager'] = self.cleanup_manager
        app.extensions['cache_cleanup_manager'] = self.cache_cleanup_manager
        
        service_initializer = ServiceInitializer(app, self.service_manager)
        service_initializer.initialize_all()
        
        analyzer_initializer = AnalyzerInitializer(app, self.service_manager)
        analyzer_initializer.initialize_all(project_root_path, app_base_dir)
        
        self.cleanup_manager.start_cleanup_thread()
        self.cache_cleanup_manager.start_cleanup_thread()
        
        self._register_blueprints(app)
        self._initialize_batch_analysis(app)
        
        ErrorHandlerRegistry.register_all(app)
        ContextProcessorRegistry.register_all(app)
        
        self._register_cleanup_handlers(app)
    
    def _register_blueprints(self, app: Flask) -> None:
        """Register all application blueprints."""
        if self.logger:
            self.logger.info("Registering blueprints")
        
        try:
            if BLUEPRINTS_AVAILABLE:
                # Use the register_blueprints function from web_routes
                register_blueprints(app)
                if self.logger:
                    self.logger.info("Blueprints registered via web_routes.register_blueprints()")
            else:
                # Fallback to manual registration with available blueprints
                blueprints = [main_bp, api_bp, analysis_bp, performance_bp, 
                             zap_bp, generation_bp, batch_bp, openrouter_bp, docker_bp]
                for blueprint in blueprints:
                    app.register_blueprint(blueprint)
                    if self.logger:
                        self.logger.debug(f"Registered blueprint: {blueprint.name}")
                if self.logger:
                    self.logger.warning("Used fallback blueprint registration")
                    
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to register blueprints: {e}")
                self.logger.error(f"BLUEPRINTS_AVAILABLE: {BLUEPRINTS_AVAILABLE}")
            raise
    
    def _initialize_batch_analysis(self, app: Flask) -> None:
        """Initialize batch analysis module."""
        try:
            batch_service = BatchAnalysisService()
            batch_service.init_app(app)
            
            app.batch_service = batch_service
            
            # batch_analysis_bp is now an alias for batch_bp, which is already registered in _register_blueprints
            if self.logger:
                self.logger.info("Batch analysis module initialized successfully")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Failed to initialize batch analysis module: {str(e)}")
    
    def _register_cleanup_handlers(self, app: Flask) -> None:
        """Register cleanup handlers for application shutdown."""
        def cleanup():
            logger = create_logger_for_component('cleanup')
            logger.info("Starting application cleanup")
            
            try:
                stop_zap_scanners(app)
            except Exception as e:
                logger.error(f"Error stopping ZAP scanners: {e}")
            
            extensions = getattr(app, 'extensions', {})
            
            if 'cleanup_manager' in extensions:
                try:
                    extensions['cleanup_manager'].stop()
                except Exception as e:
                    logger.error(f"Error stopping cleanup manager: {e}")
            
            if 'cache_cleanup_manager' in extensions:
                try:
                    extensions['cache_cleanup_manager'].cleanup()
                except Exception as e:
                    logger.error(f"Error stopping cache cleanup manager: {e}")
            
            if 'service_manager' in extensions:
                try:
                    extensions['service_manager'].cleanup_services()
                except Exception as e:
                    logger.error(f"Error cleaning up services: {e}")
            
            logger.info("Application cleanup completed")
        
        atexit.register(cleanup)


# ===========================
# FLASK ROUTES AND BLUEPRINTS
# ===========================

# Import blueprints from web_routes module
try:
    from web_routes import (
        main_bp, api_bp, analysis_bp, performance_bp, zap_bp,
        openrouter_bp, batch_bp, generation_bp, docker_bp,
        register_blueprints
    )
    BLUEPRINTS_AVAILABLE = True
except ImportError as e:
    logger = create_logger_for_component('blueprint_import')
    logger.error(f"Failed to import blueprints from web_routes: {e}")
    BLUEPRINTS_AVAILABLE = False
    # Create empty blueprints as fallback
    main_bp = Blueprint("main", __name__)
    api_bp = Blueprint("api", __name__, url_prefix="/api")
    analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")
    performance_bp = Blueprint("performance", __name__, url_prefix="/performance")
    zap_bp = Blueprint("zap", __name__, url_prefix="/zap")
    generation_bp = Blueprint("generation", __name__, url_prefix="/generation")
    batch_bp = Blueprint("batch", __name__, url_prefix="/batch")
    openrouter_bp = Blueprint("openrouter", __name__, url_prefix="/openrouter")
    docker_bp = Blueprint("docker", __name__, url_prefix="/docker")
    
    def register_blueprints(app):
        """Fallback blueprint registration."""
        pass

# Legacy blueprint aliases for backward compatibility
batch_analysis_bp = batch_bp  # batch_analysis_bp -> batch_bp
quality_bp = analysis_bp      # quality_bp -> analysis_bp  
gpt4all_bp = openrouter_bp   # gpt4all_bp -> openrouter_bp


class ScanState(Enum):
    """Enumeration of possible ZAP scan states."""
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    ERROR = "Error"
    STOPPED = "Stopped"


def get_scan_manager():
    """Get scan manager from app context."""
    if not hasattr(current_app, 'scan_manager'):
        # ScanManager is defined in this module
        current_app.scan_manager = ScanManager()
    return current_app.scan_manager


def filter_apps(apps, search=None, model=None, status=None):
    """Filter apps based on search criteria."""
    filtered = apps
    
    if search:
        search_lower = search.lower()
        filtered = [app for app in filtered if 
                   search_lower in app['model'].lower() or 
                   search_lower in str(app['app_num'])]
    
    if model:
        filtered = [app for app in filtered if app['model'] == model]
    
    if status:
        def get_app_status(app):
            try:
                docker_manager = get_docker_manager()
                container_statuses = get_app_container_statuses(app['model'], app['app_num'], docker_manager)
                backend_running = container_statuses.get('backend', {}).get('running', False)
                frontend_running = container_statuses.get('frontend', {}).get('running', False)
                
                if backend_running and frontend_running:
                    return 'running'
                elif backend_running or frontend_running:
                    return 'partial'
                else:
                    return 'stopped'
            except Exception:
                return 'unknown'
        
        filtered = [app for app in filtered if get_app_status(app) == status]
    
    return filtered



def create_app() -> Flask:
    """
    Create and configure the Flask application.
    
    Returns:
        Configured Flask application instance
    """
    factory = FlaskApplicationFactory()
    return factory.create_app()


def main() -> None:
    """Main entry point for the application."""
    logger = create_logger_for_component('main')
    
    try:
        app = create_app()
        
        config = app.config.get('APP_CONFIG')
        if not config:
            raise RuntimeError("Application configuration not loaded")
        
        host, port = HostPortValidator.validate(config.HOST, config.PORT)
        
        logger.info(f"Starting Flask application on {host}:{port}")
        logger.info(f"Debug mode: {config.DEBUG}")
        
        app.run(
            host=host,
            port=port,
            debug=config.DEBUG,
            threaded=True
        )
        
    except Exception as e:
        logger.exception(f"Failed to start application: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()