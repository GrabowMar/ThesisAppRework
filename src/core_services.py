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
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache, wraps
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

# ===========================
# CONFIGURATION AND CONSTANTS
# ===========================

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
    DOCKER_TIMEOUT: int = 10


class AppConfig:
    """Unified application configuration."""
    
    def __init__(self):
        self.DEBUG = os.getenv("FLASK_ENV", "development") != "production"
        self.SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "your-secret-key-here")
        self.BASE_DIR = Path(__file__).parent
        self.DOCKER_TIMEOUT = self._safe_int_env("DOCKER_TIMEOUT", AppDefaults.DOCKER_TIMEOUT)
        self.HOST = "0.0.0.0" if os.getenv("FLASK_ENV") == "production" else "127.0.0.1"
        self.PORT = self._safe_int_env("PORT", AppDefaults.PORT)
        self.LOG_DIR = Path(os.getenv("LOG_DIR", "logs"))
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO" if not self.DEBUG else "DEBUG")
        self.MODELS_BASE_DIR = Path(os.getenv("MODELS_BASE_DIR", self.BASE_DIR.parent / "models"))
        self.BATCH_MAX_WORKERS = self._safe_int_env("BATCH_MAX_WORKERS", 4)
        
        # Ensure log directory exists
        if not self.LOG_DIR.is_absolute():
            self.LOG_DIR = self.BASE_DIR.parent / self.LOG_DIR
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        
        # Security warning
        if self.SECRET_KEY == "your-secret-key-here" and not self.DEBUG:
            logging.warning("SECURITY WARNING: FLASK_SECRET_KEY is not set in production!")
    
    @staticmethod
    def _safe_int_env(key: str, default: int) -> int:
        """Safely parse an integer from environment variables."""
        try:
            value = os.getenv(key)
            return int(value) if value else default
        except ValueError:
            logging.warning(f"Invalid integer value for {key}: '{value}', using default: {default}")
            return default


# ===========================
# LOGGING SERVICE
# ===========================

class LoggingService:
    """Centralized logging configuration service."""
    
    @staticmethod
    def setup(app: Flask) -> logging.Logger:
        """Setup logging for the application."""
        config = app.config['APP_CONFIG']
        log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        root_logger.setLevel(log_level)
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(request_id)s] %(component)s.%(name)s: %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        simple_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Add context filter
        context_filter = LoggingService._create_context_filter()
        
        # Setup handlers
        handlers = [
            LoggingService._create_file_handler(config.LOG_DIR / 'app.log', log_level, detailed_formatter),
            LoggingService._create_file_handler(config.LOG_DIR / 'errors.log', logging.ERROR, detailed_formatter),
            LoggingService._create_console_handler(log_level, simple_formatter)
        ]
        
        for handler in handlers:
            handler.addFilter(context_filter)
            root_logger.addHandler(handler)
        
        # Configure werkzeug logger
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.handlers.clear()
        werkzeug_logger.setLevel(log_level)
        werkzeug_logger.propagate = False
        
        request_handler = LoggingService._create_file_handler(
            config.LOG_DIR / 'requests.log', log_level, simple_formatter
        )
        request_handler.addFilter(LoggingService._create_request_filter())
        werkzeug_logger.addHandler(request_handler)
        
        # Setup request middleware
        LoggingService._setup_request_middleware(app)
        
        logging.info(f"Logging initialized. Level: {config.LOG_LEVEL}, Directory: {config.LOG_DIR}")
        return root_logger
    
    @staticmethod
    def _create_context_filter():
        """Create a context filter for adding request context to logs."""
        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.request_id = getattr(g, 'request_id', '-') if has_request_context() else '-'
                record.component = record.name.split('.')[0] if '.' in record.name else record.name
                return True
        return ContextFilter()
    
    @staticmethod
    def _create_request_filter():
        """Create a filter for excluding noisy requests."""
        class RequestFilter(logging.Filter):
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
                except:
                    pass
                return True
        return RequestFilter()
    
    @staticmethod
    def _create_file_handler(filename: Path, level: int, formatter: logging.Formatter) -> logging.Handler:
        """Create a rotating file handler."""
        handler = logging.handlers.RotatingFileHandler(
            filename=filename,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
    
    @staticmethod
    def _create_console_handler(level: int, formatter: logging.Formatter) -> logging.Handler:
        """Create a console handler."""
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(formatter)
        return handler
    
    @staticmethod
    def _setup_request_middleware(app: Flask):
        """Setup request logging middleware."""
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
            duration = time.time() - getattr(g, 'start_time', time.time())
            is_quiet = getattr(g, 'is_quiet', False)
            
            if response.status_code >= 400 or duration > 1.0 or not is_quiet:
                level = logging.WARNING if response.status_code >= 400 else logging.INFO
                logging.log(level, f"Response: {request.method} {request.path} - "
                                 f"Status: {response.status_code} - Duration: {duration:.3f}s")
            return response


def get_logger(component: str) -> logging.Logger:
    """Get a logger for a specific component."""
    return logging.getLogger(component)


# ===========================
# ENUMS
# ===========================

class BaseEnum(str, Enum):
    """Base enum class with string values."""
    def __str__(self):
        return self.value


class ScanStatus(BaseEnum):
    """Enumeration of possible scan statuses."""
    NOT_RUN = "Not Run"
    STARTING = "Starting"
    SPIDERING = "Spidering"
    SCANNING = "Scanning"
    COMPLETE = "Complete"
    FAILED = "Failed"
    STOPPED = "Stopped"
    ERROR = "Error"


class JobStatus(BaseEnum):
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


class TaskStatus(BaseEnum):
    """Status of a batch task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


class AnalysisType(BaseEnum):
    """Types of analysis that can be performed."""
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_SECURITY = "backend_security"
    PERFORMANCE = "performance"
    ZAP = "zap"
    GPT4ALL = "gpt4all"
    CODE_QUALITY = "code_quality"


class ContainerState(BaseEnum):
    """Container state enumeration."""
    CREATING = "creating"
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    REMOVING = "removing"
    DEAD = "dead"
    UNKNOWN = "unknown"


class OperationType(BaseEnum):
    """Container operation types."""
    CREATE = "create"
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    BUILD = "build"
    REMOVE = "remove"
    PAUSE = "pause"
    UNPAUSE = "unpause"


# ===========================
# BASE CLASSES
# ===========================

@dataclass
class BaseModel:
    """Base model with common functionality."""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), cls=CustomJSONEncoder)


@dataclass
class TimestampedModel(BaseModel):
    """Base model with timestamp fields."""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = field(default=None)
    
    def update(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()


class BaseService(ABC):
    """Base service class with common functionality."""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = get_logger(logger_name or self.__class__.__name__)
        self._lock = threading.RLock()
    
    @abstractmethod
    def cleanup(self):
        """Cleanup resources."""
        pass


class CacheableService(BaseService):
    """Base service with caching capabilities."""
    
    def __init__(self, logger_name: Optional[str] = None, cache_ttl: int = 300):
        super().__init__(logger_name)
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._cache_ttl = cache_ttl
    
    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self._cache_ttl:
                return value
            else:
                del self._cache[key]
        return None
    
    def _set_cached(self, key: str, value: Any):
        """Set value in cache."""
        self._cache[key] = (value, time.time())
    
    def clear_cache(self):
        """Clear all cached values."""
        self._cache.clear()
    
    def cleanup(self):
        """Cleanup resources."""
        self.clear_cache()


# ===========================
# UTILITIES
# ===========================

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle complex types."""
    def default(self, o: Any) -> Any:
        if hasattr(o, 'to_dict') and callable(o.to_dict):
            return o.to_dict()
        if hasattr(o, "__dataclass_fields__"):
            return asdict(o)
        if isinstance(o, (datetime, Path)):
            return str(o)
        if isinstance(o, Enum):
            return o.value
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)


class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(self, message: str, code: int = 500):
        super().__init__(message)
        self.message = message
        self.code = code


class InitializationError(AppError):
    """Exception raised during application initialization."""
    pass


def handle_errors(f):
    """Decorator for consistent error handling."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger = get_logger('error_handler')
            logger.exception(f"Error in {f.__name__}: {e}")
            if request.path.startswith('/api/'):
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'message': 'An error occurred'
                }), 500
            raise
    return wrapper


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


class DockerUtils:
    """Centralized Docker utility functions."""
    
    _docker_available: Optional[bool] = None
    _compose_available: Optional[bool] = None
    _operation_locks: Dict[str, threading.RLock] = {}
    _locks_lock = threading.RLock()
    
    @classmethod
    def is_docker_available(cls) -> bool:
        """Check if Docker is available and running."""
        if cls._docker_available is not None:
            return cls._docker_available
        
        try:
            result = subprocess.run(
                ["docker", "version", "--format", "{{.Client.Version}}"],
                capture_output=True,
                text=True,
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            cls._docker_available = result.returncode == 0
            return cls._docker_available
        except:
            cls._docker_available = False
            return False
    
    @classmethod
    def is_compose_available(cls) -> bool:
        """Check if Docker Compose is available."""
        if cls._compose_available is not None:
            return cls._compose_available
        
        try:
            for cmd in [["docker", "compose", "version"], ["docker-compose", "--version"]]:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                if result.returncode == 0:
                    cls._compose_available = True
                    return True
            cls._compose_available = False
            return False
        except:
            cls._compose_available = False
            return False
    
    @staticmethod
    def sanitize_project_name(name: str) -> str:
        """Sanitize a string to be a valid Docker project name."""
        if not name:
            return "default"
        
        sanitized = name.lower()
        sanitized = re.sub(r'[^a-z0-9_-]', '_', sanitized)
        sanitized = re.sub(r'[_-]+', '_', sanitized).strip('_-')
        
        if not sanitized:
            sanitized = "default"
        elif len(sanitized) > 63:
            sanitized = sanitized[:63].rstrip('_-')
        
        return sanitized
    
    @classmethod
    def get_project_name(cls, model: str, app_num: int) -> str:
        """Get a sanitized Docker project name."""
        if not model or app_num < 1:
            raise ValueError("Invalid model name or app number")
        return cls.sanitize_project_name(f"{model}_app{app_num}")
    
    @classmethod
    def get_operation_lock(cls, project_name: str) -> threading.RLock:
        """Get or create a lock for Docker operations on a specific project."""
        with cls._locks_lock:
            if project_name not in cls._operation_locks:
                cls._operation_locks[project_name] = threading.RLock()
            return cls._operation_locks[project_name]


class JsonResultsManager:
    """Centralized results manager for all analysis types."""
    
    def __init__(self, module_name: str, base_path: Optional[Path] = None):
        self.module_name = module_name
        self.reports_dir = (base_path or Path(__file__).parent.parent) / "reports"
        self.logger = get_logger('json_results')
    
    def save_results(self, model: str, app_num: int, results: Any, 
                    file_name: Optional[str] = None) -> Path:
        """Save analysis results to JSON file."""
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        results_dir = self.reports_dir / model / f"app{app_num}"
        results_dir.mkdir(parents=True, exist_ok=True)
        results_path = results_dir / file_name
        
        # Convert to dict if needed
        data_to_save = results
        if hasattr(results, 'to_dict'):
            data_to_save = results.to_dict()
        elif hasattr(results, '__dict__') and not isinstance(results, dict):
            data_to_save = results.__dict__
        
        # Add metadata
        if isinstance(data_to_save, dict):
            data_to_save["_metadata"] = {
                "module": self.module_name,
                "model": model,
                "app_num": app_num,
                "saved_at": datetime.now().isoformat(),
                "filename": file_name
            }
        
        with open(results_path, "w", encoding='utf-8') as f:
            json.dump(data_to_save, f, indent=2, cls=CustomJSONEncoder)
        
        self.logger.info(f"Saved {self.module_name} results to {results_path}")
        return results_path
    
    def load_results(self, model: str, app_num: int, 
                    file_name: Optional[str] = None) -> Optional[Any]:
        """Load analysis results from JSON file."""
        if file_name is None:
            file_name = f".{self.module_name}_results.json"
        
        results_path = self.reports_dir / model / f"app{app_num}" / file_name
        
        if not results_path.exists():
            return None
        
        with open(results_path, "r", encoding='utf-8') as f:
            return json.load(f)


# ===========================
# DATA MODELS
# ===========================

@dataclass
class DockerStatus(BaseModel):
    """Docker container status information."""
    exists: bool = False
    running: bool = False
    health: str = "unknown"
    status: str = "unknown"
    details: str = ""


@dataclass
class AIModel(BaseModel):
    """AI model with comprehensive information."""
    name: str
    color: str = "#666666"
    provider: str = "unknown"
    context_length: int = 0
    pricing: Dict[str, Any] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_reasoning: bool = False
    max_tokens: int = 0
    description: str = ""


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
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    
    def update(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), cls=CustomJSONEncoder)


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
    created_at: datetime = field(default_factory=datetime.now)
    auto_start: bool = True
    options: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    error_message: Optional[str] = None
    progress: Dict[str, int] = field(default_factory=lambda: {"total": 0, "completed": 0, "failed": 0})
    results: List[Dict] = field(default_factory=list)
    
    def update(self):
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        data = asdict(self)
        # Convert datetime objects to strings for JSON serialization
        if data.get('created_at'):
            data['created_at_formatted'] = data['created_at'].strftime('%Y-%m-%d %H:%M:%S')
        if data.get('started_at'):
            data['started_at_formatted'] = data['started_at'].strftime('%Y-%m-%d %H:%M:%S')
        if data.get('completed_at'):
            data['completed_at_formatted'] = data['completed_at'].strftime('%Y-%m-%d %H:%M:%S')
        if data.get('updated_at'):
            data['updated_at_formatted'] = data['updated_at'].strftime('%Y-%m-%d %H:%M:%S')
        return data
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), cls=CustomJSONEncoder)


@dataclass
class ContainerInfo(BaseModel):
    """Container information data class."""
    name: str
    model: str
    app_num: int
    container_type: str
    state: ContainerState = ContainerState.UNKNOWN
    ports: Dict[str, int] = field(default_factory=dict)
    image: str = ""
    health: str = "unknown"
    project_name: str = ""
    compose_path: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


# ===========================
# DOCKER MANAGER
# ===========================

class DockerManager(BaseService):
    """Docker container management service."""
    
    def __init__(self, client: Optional[docker.DockerClient] = None):
        super().__init__('docker')
        self.client = client or self._create_docker_client()
    
    def _create_docker_client(self) -> Optional[docker.DockerClient]:
        """Create a Docker client instance."""
        try:
            # Try multiple connection options
            docker_hosts = self._get_docker_hosts()
            
            for docker_host in docker_hosts:
                try:
                    self.logger.info(f"Attempting Docker connection to: {docker_host}")
                    client = docker.DockerClient(base_url=docker_host, timeout=10)
                    client.ping()
                    self.logger.info(f"Docker client created and verified (host: {docker_host})")
                    return client
                except Exception as e:
                    self.logger.debug(f"Failed to connect to {docker_host}: {e}")
                    continue
            
            self.logger.error("All Docker connection attempts failed")
            return None
            
        except Exception as e:
            self.logger.error(f"Docker client creation failed: {e}")
            return None
    
    def _get_docker_hosts(self) -> List[str]:
        """Get list of Docker hosts to try."""
        docker_hosts = []
        
        # User-specified host
        user_host = os.getenv("DOCKER_HOST")
        if user_host:
            docker_hosts.append(user_host)
        
        # Platform-specific hosts
        if os.name == 'nt':
            docker_hosts.extend([
                "npipe:////./pipe/dockerDesktopLinuxEngine",
                "npipe:////./pipe/docker_engine",
                "tcp://localhost:2375",
                "tcp://localhost:2376"
            ])
        else:
            docker_hosts.append("unix://var/run/docker.sock")
        
        return docker_hosts
    
    def get_container_status(self, container_name: str) -> DockerStatus:
        """Get container status."""
        if not container_name or not self.client:
            return DockerStatus(exists=False, status="invalid")
        
        try:
            with self._lock:
                container = self.client.containers.get(container_name)
            
            container_status = container.status
            is_running = container_status == "running"
            state = container.attrs.get("State", {})
            health_info = state.get("Health", {})
            
            return DockerStatus(
                exists=True,
                running=is_running,
                health=health_info.get("Status", "healthy" if is_running else container_status),
                status=container_status,
                details=state.get("Status", "unknown")
            )
        except docker.errors.NotFound:
            return DockerStatus(exists=False, status="not_found")
        except Exception as e:
            self.logger.error(f"Error fetching status for {container_name}: {e}")
            return DockerStatus(exists=False, status="error", details=str(e))
    
    def get_container_logs(self, model: str, app_num: int, container_type: str = 'backend', 
                          tail: int = 100) -> str:
        """Get container logs."""
        if not self.client:
            return "Docker client unavailable"
        
        try:
            project_name = DockerUtils.get_project_name(model, app_num)
            container_name = f"{project_name}_{container_type}"
            
            container = self.client.containers.get(container_name)
            return container.logs(tail=tail).decode("utf-8", errors="replace")
            
        except Exception as e:
            self.logger.error(f"Log retrieval failed: {e}")
            return f"Log retrieval error: {e}"
    
    def execute_compose_command(self, compose_path: str, command: List[str], 
                               model: str, app_num: int, timeout: int = 300) -> Dict[str, Any]:
        """Execute a docker-compose command."""
        try:
            compose_file = Path(compose_path)
            if not compose_file.exists():
                return {'success': False, 'error': f'Docker compose file not found: {compose_path}'}
            
            project_name = DockerUtils.get_project_name(model, app_num)
            compose_dir = compose_file.parent
            
            # Build full command
            cmd = ["docker-compose", "-p", project_name, "-f", str(compose_file)] + command
            
            self.logger.info(f"Executing: {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=str(compose_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            output = result.stdout + ("\n--- STDERR ---\n" + result.stderr if result.stderr else "")
            
            return {
                'success': result.returncode == 0,
                'output': output,
                'project_name': project_name,
                'message': 'Command executed successfully' if result.returncode == 0 else 'Command failed',
                'error': output if result.returncode != 0 else None
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': f"Command timed out after {timeout}s"}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def start_containers(self, compose_path: str, model: str, app_num: int) -> Dict[str, Any]:
        """Start containers using docker-compose."""
        # Stop any conflicting containers first
        project_name = DockerUtils.get_project_name(model, app_num)
        self._stop_conflicting_containers(project_name)
        
        return self.execute_compose_command(
            compose_path, ["up", "-d", "--remove-orphans"], 
            model, app_num, timeout=300
        )
    
    def stop_containers(self, compose_path: str, model: str, app_num: int) -> Dict[str, Any]:
        """Stop containers using docker-compose."""
        return self.execute_compose_command(
            compose_path, ["down", "--timeout", "30"], 
            model, app_num, timeout=180
        )
    
    def restart_containers(self, compose_path: str, model: str, app_num: int) -> Dict[str, Any]:
        """Restart containers."""
        stop_result = self.stop_containers(compose_path, model, app_num)
        if not stop_result['success']:
            return stop_result
        
        time.sleep(2)
        return self.start_containers(compose_path, model, app_num)
    
    def build_containers(self, compose_path: str, model: str, app_num: int, 
                        no_cache: bool = True) -> Dict[str, Any]:
        """Build containers using docker-compose."""
        command = ["build"]
        if no_cache:
            command.extend(["--no-cache", "--pull"])
        
        return self.execute_compose_command(
            compose_path, command, 
            model, app_num, timeout=900
        )
    
    def _stop_conflicting_containers(self, project_name: str) -> Tuple[bool, str]:
        """Stop conflicting containers for a project."""
        try:
            # Try docker-compose down first
            subprocess.run(
                ["docker-compose", "-p", project_name, "down", "--remove-orphans", "--timeout", "15"],
                capture_output=True,
                text=True,
                timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # Find and remove any remaining containers
            result = subprocess.run(
                ["docker", "ps", "-a", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode == 0 and result.stdout.strip():
                container_names = [name.strip() for name in result.stdout.strip().split('\n') 
                                 if name.strip() and project_name in name]
                
                for container_name in container_names:
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        text=True,
                        timeout=15,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                
                if container_names:
                    self.logger.info(f"Removed {len(container_names)} conflicting containers")
            
            return True, "Cleanup completed"
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
            return False, str(e)
    
    def cleanup(self):
        """Cleanup resources."""
        if self.client:
            try:
                self.client.close()
            except:
                pass


# ===========================
# PORT MANAGER
# ===========================

class PortManager(CacheableService):
    """Port configuration management service."""
    
    def __init__(self, port_config: List[Dict[str, Any]]):
        super().__init__('port_manager')
        self.port_config = port_config
        self._build_cache()
    
    def _build_cache(self):
        """Build cache of port configurations."""
        for config in self.port_config:
            model_name = config.get('model_name')
            app_number = config.get('app_number')
            if model_name and app_number:
                key = f"{model_name}-{app_number}"
                self._set_cached(key, config)
        self.logger.info(f"Built port cache with {len(self.port_config)} entries")
    
    def get_app_config(self, model_name: str, app_number: int) -> Optional[Dict[str, Any]]:
        """Get app configuration."""
        key = f"{model_name}-{app_number}"
        cached = self._get_cached(key)
        if cached:
            return cached
        
        # Fallback to linear search
        for config in self.port_config:
            if config.get('model_name') == model_name and config.get('app_number') == app_number:
                self._set_cached(key, config)
                return config
        return None
    
    def get_app_ports(self, model_name: str, app_number: int) -> Optional[Dict[str, int]]:
        """Get port configuration for an app."""
        config = self.get_app_config(model_name, app_number)
        if not config:
            return None
        return {
            "backend": config.get('backend_port'),
            "frontend": config.get('frontend_port')
        }
    
    def get_model_apps(self, model_name: str) -> List[Dict[str, Any]]:
        """Get all apps for a model."""
        return [config for config in self.port_config 
                if config.get('model_name') == model_name]
    
    def get_all_models(self) -> List[str]:
        """Get all unique model names."""
        return list(set(config.get('model_name') for config in self.port_config 
                       if config.get('model_name')))


# ===========================
# SCAN MANAGER
# ===========================

class ScanManager(BaseService):
    """Manages application security scans."""
    
    def __init__(self):
        super().__init__('scan_manager')
        self.scans: Dict[str, Dict[str, Any]] = {}
    
    def create_scan(self, model: str, app_num: int, options: dict) -> str:
        """Create a new scan."""
        scan_id = f"{model}-{app_num}-{int(time.time())}"
        with self._lock:
            self.scans[scan_id] = {
                "status": ScanStatus.STARTING,
                "progress": 0,
                "start_time": datetime.now().isoformat(),
                "end_time": None,
                "options": options,
                "model": model,
                "app_num": app_num,
                "results": None,
            }
        self.logger.info(f"Created scan '{scan_id}'")
        return scan_id
    
    def update_scan(self, scan_id: str, **kwargs) -> bool:
        """Update scan information."""
        with self._lock:
            if scan_id in self.scans:
                # Set end time for terminal states
                if 'status' in kwargs and kwargs['status'] in (
                    ScanStatus.COMPLETE, ScanStatus.FAILED,
                    ScanStatus.STOPPED, ScanStatus.ERROR
                ):
                    kwargs.setdefault('end_time', datetime.now().isoformat())
                
                self.scans[scan_id].update(kwargs)
                return True
            return False
    
    def get_scan(self, scan_id: str) -> Optional[Dict[str, Any]]:
        """Get scan details."""
        with self._lock:
            return self.scans.get(scan_id)
    
    def get_latest_scan(self, model: str, app_num: int) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Get the latest scan for a model/app."""
        with self._lock:
            matching_scans = [(sid, scan) for sid, scan in self.scans.items()
                            if scan['model'] == model and scan['app_num'] == app_num]
            
            if not matching_scans:
                return None
            
            # Sort by scan ID (which includes timestamp)
            return max(matching_scans, key=lambda x: x[0])
    
    def cleanup_old_scans(self, max_age_hours: int = 1) -> int:
        """Clean up old completed scans."""
        current_time = datetime.now()
        terminal_statuses = {ScanStatus.COMPLETE, ScanStatus.FAILED, 
                           ScanStatus.STOPPED, ScanStatus.ERROR}
        
        with self._lock:
            to_remove = []
            for scan_id, scan in self.scans.items():
                if scan.get("status") in terminal_statuses:
                    try:
                        end_time = datetime.fromisoformat(scan.get("end_time", scan["start_time"]))
                        if (current_time - end_time).total_seconds() > max_age_hours * 3600:
                            to_remove.append(scan_id)
                    except:
                        continue
            
            for scan_id in to_remove:
                del self.scans[scan_id]
            
            if to_remove:
                self.logger.info(f"Cleaned up {len(to_remove)} old scans")
            return len(to_remove)
    
    def cleanup(self):
        """Cleanup resources."""
        self.scans.clear()


# ===========================
# MODEL INTEGRATION SERVICE
# ===========================

class ModelIntegrationService(CacheableService):
    """Service for integrating model information from JSON files."""
    
    def __init__(self, base_path: Optional[Path] = None):
        super().__init__('model_integration')
        self.base_path = base_path or Path.cwd()
        self.models_data = {}
        self._raw_data = {
            'port_config': [],
            'model_capabilities': {},
            'models_summary': {}
        }
        self.load_all_data()
    
    def load_all_data(self) -> bool:
        """Load all model data from JSON files."""
        success = True
        
        # Load port configuration
        success &= self._load_json_file(
            'port_config.json', 
            lambda data: self._raw_data.update({'port_config': data})
        )
        
        # Load model capabilities
        success &= self._load_json_file(
            'model_capabilities.json',
            lambda data: self._raw_data.update({'model_capabilities': data.get('models', {})})
        )
        
        # Load models summary
        success &= self._load_json_file(
            'models_summary.json',
            lambda data: self._raw_data.update({'models_summary': data})
        )
        
        if success:
            self._integrate_model_data()
        
        return success
    
    def _load_json_file(self, filename: str, processor) -> bool:
        """Load a JSON file and process it."""
        try:
            path = self.base_path / filename
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                processor(data)
                self.logger.info(f"Loaded {filename}")
                return True
            else:
                self.logger.warning(f"File not found: {path}")
                return False
        except Exception as e:
            self.logger.error(f"Failed to load {filename}: {e}")
            return False
    
    def _integrate_model_data(self):
        """Integrate data from all sources into unified model objects."""
        self.models_data = {}
        
        # Group port configs by model
        port_configs_by_model = {}
        for config in self._raw_data['port_config']:
            model_name = config.get('model_name', '')
            if model_name:
                port_configs_by_model.setdefault(model_name, []).append(config)
        
        # Build integrated model data
        for model_name, port_configs in port_configs_by_model.items():
            model = AIModel(name=model_name)
            
            # Add summary data
            summary_models = {m['name']: m for m in self._raw_data['models_summary'].get('models', [])}
            if model_name in summary_models:
                summary = summary_models[model_name]
                model.color = summary.get('color', model.color)
                model.provider = summary.get('provider', model.provider)
            
            # Add capabilities data
            if model_name in self._raw_data['model_capabilities']:
                caps = self._raw_data['model_capabilities'][model_name]
                model.context_length = caps.get('context_length', 0)
                model.pricing = caps.get('pricing', {})
                model.capabilities = caps.get('capabilities', [])
                model.supports_vision = caps.get('supports_vision', False)
                model.supports_function_calling = caps.get('supports_function_calling', False)
                model.supports_reasoning = 'reasoning' in model.capabilities
                model.max_tokens = caps.get('max_tokens', 0)
                model.description = caps.get('description', '')
            
            self.models_data[model_name] = model
        
        self.logger.info(f"Integrated data for {len(self.models_data)} models")
    
    def get_all_models(self) -> List[AIModel]:
        """Get all integrated models."""
        return list(self.models_data.values())
    
    def get_model(self, model_name: str) -> Optional[AIModel]:
        """Get a specific model by name."""
        return self.models_data.get(model_name)
    
    def cleanup(self):
        """Cleanup resources."""
        super().cleanup()
        self.models_data.clear()


# ===========================
# BATCH ANALYSIS SERVICE
# ===========================

class BatchTaskWorker:
    """Worker for executing batch analysis tasks."""
    
    def __init__(self, app: Any):
        self.app = app
        self.logger = get_logger('batch_worker')
    
    def execute_task(self, task: BatchTask) -> BatchTask:
        """Execute a single analysis task."""
        start_time = time.time()
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        
        try:
            with self.app.app_context():
                # Get the appropriate analyzer
                analyzer = self._get_analyzer(task.analysis_type)
                if not analyzer:
                    raise ValueError(f"No analyzer available for {task.analysis_type}")
                
                # Run analysis
                result = self._run_analysis(analyzer, task)
                
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.issues_count = self._count_issues(result)
                
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
    
    def _get_analyzer(self, analysis_type: str):
        """Get the appropriate analyzer for the analysis type."""
        analyzer_map = {
            AnalysisType.FRONTEND_SECURITY: 'frontend_security_analyzer',
            AnalysisType.BACKEND_SECURITY: 'backend_security_analyzer',
            AnalysisType.PERFORMANCE: 'performance_analyzer',
            AnalysisType.ZAP: 'zap_scanner',
            AnalysisType.GPT4ALL: 'gpt4all_analyzer',
            AnalysisType.CODE_QUALITY: 'code_quality_analyzer'
        }
        
        analyzer_name = analyzer_map.get(analysis_type)
        if analyzer_name:
            return getattr(self.app, analyzer_name, None)
        return None
    
    def _run_analysis(self, analyzer, task: BatchTask) -> Dict[str, Any]:
        """Run the analysis using the analyzer."""
        # This is a simplified version - implement specific logic for each analyzer
        if hasattr(analyzer, 'analyze_app'):
            return analyzer.analyze_app(task.model, task.app_num)
        elif hasattr(analyzer, 'run_security_analysis'):
            issues, status, outputs = analyzer.run_security_analysis(
                task.model, task.app_num, use_all_tools=True
            )
            return {"issues": issues, "tool_status": status, "outputs": outputs}
        elif hasattr(analyzer, 'run_performance_test'):
            return analyzer.run_performance_test(task.model, task.app_num)
        elif hasattr(analyzer, 'scan_app'):
            return analyzer.scan_app(task.model, task.app_num)
        else:
            raise ValueError(f"Analyzer does not support required methods")
    
    def _count_issues(self, result: Dict[str, Any]) -> int:
        """Count issues in the result."""
        if 'issues' in result:
            return len(result.get('issues', []))
        elif 'issues_count' in result:
            return result['issues_count']
        return 0


class BatchAnalysisService(BaseService):
    """Service for managing batch analysis jobs."""
    
    def __init__(self, app: Optional[Any] = None):
        super().__init__('batch_service')
        self.jobs: Dict[str, BatchJob] = {}
        self.tasks: Dict[str, BatchTask] = {}
        self.app = app
        self.worker_pool: Optional[ThreadPoolExecutor] = None
        self.job_threads: Dict[str, threading.Thread] = {}
        self.shutdown_event = threading.Event()
    
    def init_app(self, app: Any):
        """Initialize with Flask app."""
        self.app = app
        app_config = app.config.get('APP_CONFIG')
        if app_config and hasattr(app_config, 'BATCH_MAX_WORKERS'):
            max_workers = app_config.BATCH_MAX_WORKERS
        else:
            max_workers = 4  # Default fallback
        self.worker_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.logger.info(f"Initialized with {max_workers} workers")
    
    def create_job(self, name: str, description: str, analysis_types: List[str],
                   models: List[str], app_range_str: str, 
                   options: Optional[Dict[str, Any]] = None,
                   auto_start: bool = True) -> BatchJob:
        """Create a new batch job."""
        # Parse app range
        app_range = self._parse_app_range(app_range_str)
        
        # Validate inputs
        if not analysis_types or not models or not app_range['apps']:
            raise ValueError("Invalid job parameters")
        
        # Convert analysis types to enums
        analysis_type_enums = []
        for at_str in analysis_types:
            try:
                analysis_type_enums.append(AnalysisType(at_str))
            except ValueError:
                self.logger.warning(f"Unknown analysis type: {at_str}")
        
        if not analysis_type_enums:
            raise ValueError("No valid analysis types specified")
        
        # Create job
        job_id = str(uuid.uuid4())
        job = BatchJob(
            id=job_id,
            name=name,
            description=description or "",
            status=JobStatus.PENDING,
            analysis_types=analysis_type_enums,
            models=models,
            app_range=app_range,
            options=options or {},
            auto_start=auto_start
        )
        
        # Create tasks
        for model in models:
            for app_num in app_range['apps']:
                for analysis_type in analysis_type_enums:
                    task = BatchTask(
                        id=str(uuid.uuid4()),
                        job_id=job_id,
                        model=model,
                        app_num=app_num,
                        analysis_type=analysis_type.value
                    )
                    self.tasks[task.id] = task
        
        job.progress['total'] = len(models) * len(app_range['apps']) * len(analysis_type_enums)
        
        with self._lock:
            self.jobs[job_id] = job
        
        self.logger.info(f"Created job {job_id} with {job.progress['total']} tasks")
        
        if auto_start:
            self.start_job(job_id)
        
        return job
    
    def _parse_app_range(self, app_range_str: str) -> Dict[str, Any]:
        """Parse app range string."""
        if app_range_str.strip().lower() == 'all':
            return {"raw": app_range_str, "apps": list(range(1, 31))}
        
        apps = []
        for part in app_range_str.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    apps.extend(range(start, end + 1))
                except ValueError:
                    self.logger.warning(f"Invalid range: {part}")
            else:
                try:
                    apps.append(int(part))
                except ValueError:
                    self.logger.warning(f"Invalid app number: {part}")
        
        return {"raw": app_range_str, "apps": sorted(set(apps))}
    
    def start_job(self, job_id: str) -> bool:
        """Start executing a job."""
        job = self.jobs.get(job_id)
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
        self.logger.info(f"Started job: {job_id}")
        return True
    
    def _execute_job(self, job_id: str):
        """Execute all tasks in a job."""
        job = self.jobs.get(job_id)
        if not job:
            return
        
        try:
            tasks = [task for task in self.tasks.values() if task.job_id == job_id]
            worker = BatchTaskWorker(self.app)
            
            # Submit all tasks
            futures = []
            for task in tasks:
                if self.shutdown_event.is_set():
                    break
                
                future = self.worker_pool.submit(worker.execute_task, task)
                futures.append((future, task))
            
            # Process results
            for future, task in futures:
                if self.shutdown_event.is_set():
                    future.cancel()
                    continue
                
                try:
                    completed_task = future.result(timeout=300)
                    self.tasks[task.id] = completed_task
                    
                    if completed_task.status == TaskStatus.COMPLETED:
                        job.progress["completed"] += 1
                    else:
                        job.progress["failed"] += 1
                        
                except Exception as e:
                    self.logger.error(f"Task execution failed: {e}")
                    job.progress["failed"] += 1
            
            # Update job status
            if job.progress["failed"] == 0:
                job.status = JobStatus.COMPLETED
            elif job.progress["completed"] == 0:
                job.status = JobStatus.FAILED
            else:
                job.status = JobStatus.COMPLETED
            
        except Exception as e:
            self.logger.error(f"Job execution failed: {e}", exc_info=True)
            job.status = JobStatus.FAILED
            job.error_message = str(e)
        
        finally:
            job.completed_at = datetime.now()
            
            with self._lock:
                if job_id in self.job_threads:
                    del self.job_threads[job_id]
    
    def get_job(self, job_id: str) -> Optional[BatchJob]:
        """Get a specific job."""
        return self.jobs.get(job_id)
    
    def get_all_jobs(self) -> List[BatchJob]:
        """Get all jobs."""
        return list(self.jobs.values())
    
    def get_job_stats(self) -> Dict[str, int]:
        """Get job statistics."""
        stats = {
            'total': len(self.jobs),
            'pending': 0,
            'running': 0,
            'completed': 0,
            'failed': 0,
            'cancelled': 0,
            'archived': 0
        }
        
        for job in self.jobs.values():
            status = job.status.lower()
            if status in stats:
                stats[status] += 1
        
        return stats
    
    def get_detailed_statistics(self) -> Dict[str, Any]:
        """Get detailed job and task statistics."""
        with self._lock:
            stats = {
                'total_jobs': len(self.jobs),
                'pending_jobs': 0,
                'running_jobs': 0,
                'completed_jobs': 0,
                'failed_jobs': 0,
                'cancelled_jobs': 0,
                'archived_jobs': 0,
                'total_tasks': len(self.tasks),
                'pending_tasks': 0,
                'running_tasks': 0,
                'completed_tasks': 0,
                'failed_tasks': 0,
                'success_rate': 0.0
            }
            
            # Count job statuses
            for job in self.jobs.values():
                status_key = f"{job.status.value}_jobs"
                if status_key in stats:
                    stats[status_key] += 1
            
            # Count task statuses
            for task in self.tasks.values():
                status_key = f"{task.status.value}_tasks"
                if status_key in stats:
                    stats[status_key] += 1
            
            # Calculate success rate
            total_completed = stats['completed_tasks'] + stats['failed_tasks']
            if total_completed > 0:
                stats['success_rate'] = round((stats['completed_tasks'] / total_completed) * 100, 1)
                
            return stats
    
    def get_job_tasks(self, job_id: str) -> List[BatchTask]:
        """Get all tasks for a specific job."""
        with self._lock:
            return [task for task in self.tasks.values() if task.job_id == job_id]
    
    def get_task(self, task_id: str) -> Optional[BatchTask]:
        """Get a specific task by ID."""
        with self._lock:
            return self.tasks.get(task_id)
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running or pending job."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        with self._lock:
            job.status = JobStatus.CANCELLED
            job.completed_at = datetime.now()
            
            # Cancel running thread if exists
            if job_id in self.job_threads:
                # Note: Python threads can't be forcefully stopped
                # We rely on shutdown_event being checked in the execution loop
                pass
        
        self.logger.info(f"Cancelled job: {job_id}")
        return True
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a running job."""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.RUNNING:
            return False
        
        with self._lock:
            job.status = JobStatus.PAUSED
        
        self.logger.info(f"Paused job: {job_id}")
        return True
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        job = self.jobs.get(job_id)
        if not job or job.status != JobStatus.PAUSED:
            return False
        
        with self._lock:
            job.status = JobStatus.RUNNING
        
        # Restart the job execution
        self.start_job(job_id)
        self.logger.info(f"Resumed job: {job_id}")
        return True
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job and all its tasks."""
        job = self.jobs.get(job_id)
        if not job:
            return False
        
        # Only allow deletion of completed, failed, or cancelled jobs
        if job.status in [JobStatus.RUNNING, JobStatus.PENDING]:
            return False
        
        with self._lock:
            # Remove job
            if job_id in self.jobs:
                del self.jobs[job_id]
            
            # Remove associated tasks
            tasks_to_remove = [task_id for task_id, task in self.tasks.items() 
                             if task.job_id == job_id]
            for task_id in tasks_to_remove:
                del self.tasks[task_id]
        
        self.logger.info(f"Deleted job: {job_id}")
        return True
    
    def cleanup(self):
        """Cleanup resources."""
        self.shutdown_event.set()
        if self.worker_pool:
            self.worker_pool.shutdown(wait=True)
        
        for thread in self.job_threads.values():
            thread.join(timeout=5)


# ===========================
# APPLICATION CONTEXT UTILITIES
# ===========================

class AppContext:
    """Centralized access to application context and services."""
    
    @staticmethod
    def get_docker_manager() -> DockerManager:
        """Get Docker manager from app context."""
        if not hasattr(current_app, 'docker_manager'):
            raise RuntimeError("Docker manager not available")
        return current_app.docker_manager
    
    @staticmethod
    def get_port_manager() -> PortManager:
        """Get Port manager from app context."""
        if not hasattr(current_app, 'port_manager'):
            raise RuntimeError("Port manager not available")
        return current_app.port_manager
    
    @staticmethod
    def get_scan_manager() -> ScanManager:
        """Get Scan manager from app context."""
        if not hasattr(current_app, 'scan_manager'):
            raise RuntimeError("Scan manager not available")
        return current_app.scan_manager
    
    @staticmethod
    def get_batch_service() -> BatchAnalysisService:
        """Get Batch service from app context."""
        if not hasattr(current_app, 'batch_service'):
            raise RuntimeError("Batch service not available")
        return current_app.batch_service
    
    @staticmethod
    def get_model_service() -> ModelIntegrationService:
        """Get Model service from app context."""
        return current_app.config.get('MODEL_SERVICE')
    
    @staticmethod
    def get_ai_models() -> List[AIModel]:
        """Get AI models from app context."""
        return current_app.config.get('AI_MODELS', [])
    
    @staticmethod
    def get_port_config() -> List[Dict[str, Any]]:
        """Get port configuration from app context."""
        return current_app.config.get('PORT_CONFIG', [])


class AppUtils:
    """Application utility functions."""
    
    @staticmethod
    def get_app_info(model: str, app_num: int) -> Optional[Dict[str, Any]]:
        """Get information about a specific app."""
        port_manager = AppContext.get_port_manager()
        config = port_manager.get_app_config(model, app_num)
        
        if not config:
            return None
        
        backend_port = config.get('backend_port')
        frontend_port = config.get('frontend_port')
        
        if backend_port is None or frontend_port is None:
            return None
        
        return {
            "model": model,
            "app_num": app_num,
            "backend_port": backend_port,
            "frontend_port": frontend_port,
            "backend_url": f"http://localhost:{backend_port}",
            "frontend_url": f"http://localhost:{frontend_port}"
        }
    
    @staticmethod
    def get_all_apps() -> List[Dict[str, Any]]:
        """Get all applications."""
        port_config = AppContext.get_port_config()
        apps = []
        
        for config in port_config:
            model = config.get('model_name')
            app_num = config.get('app_number')
            
            if model and app_num:
                app_info = AppUtils.get_app_info(model, app_num)
                if app_info:
                    apps.append(app_info)
        
        return apps
    
    @staticmethod
    def get_container_names(model: str, app_num: int) -> Tuple[str, str]:
        """Get standardized container names for an application."""
        port_manager = AppContext.get_port_manager()
        config = port_manager.get_app_config(model, app_num)
        
        if not config:
            raise ValueError(f"No configuration found for {model}/app{app_num}")
        
        backend_port = config.get('backend_port')
        frontend_port = config.get('frontend_port')
        
        if not backend_port or not frontend_port:
            raise ValueError(f"Missing port configuration for {model}/app{app_num}")
        
        project_name = DockerUtils.get_project_name(model, app_num)
        
        return (
            f"{project_name}_backend_{backend_port}",
            f"{project_name}_frontend_{frontend_port}"
        )
    
    @staticmethod
    def get_app_directory(model: str, app_num: int) -> Path:
        """Get the directory path for a specific application."""
        models_base_dir = Path(current_app.config['APP_CONFIG'].MODELS_BASE_DIR)
        app_path = models_base_dir / model / f"app{app_num}"
        
        if not app_path.is_dir():
            raise FileNotFoundError(f"Application directory not found: {app_path}")
        
        return app_path
    
    @staticmethod
    def handle_docker_action(action: str, model: str, app_num: int) -> Tuple[bool, str]:
        """Handle Docker actions for an application."""
        valid_actions = {"start", "stop", "restart", "build"}
        if action not in valid_actions:
            return False, f"Invalid action: {action}"
        
        try:
            docker_manager = AppContext.get_docker_manager()
            app_dir = AppUtils.get_app_directory(model, app_num)
            compose_path = app_dir / "docker-compose.yml"
            
            if not compose_path.exists():
                compose_path = app_dir / "docker-compose.yaml"
            
            if not compose_path.exists():
                return False, "No docker-compose file found"
            
            # Execute action
            action_methods = {
                "start": docker_manager.start_containers,
                "stop": docker_manager.stop_containers,
                "restart": docker_manager.restart_containers,
                "build": docker_manager.build_containers
            }
            
            result = action_methods[action](str(compose_path), model, app_num)
            
            return result['success'], result.get('message', result.get('error', 'Unknown result'))
            
        except Exception as e:
            return False, str(e)


# ===========================
# SERVICE MANAGER
# ===========================

class ServiceManager:
    """Manages application services lifecycle."""
    
    def __init__(self, app: Flask):
        self.app = app
        self.logger = get_logger('service_manager')
        self._services = {}
    
    def register(self, name: str, service: Any):
        """Register a service."""
        self._services[name] = service
        setattr(self.app, name, service)
        self.logger.info(f"Registered service: {name}")
    
    def register_service(self, name: str, service: Any):
        """Register a service (alias for register method)."""
        return self.register(name, service)
    
    def get_service(self, name: str):
        """Get a registered service."""
        return self._services.get(name)
    
    def cleanup(self):
        """Cleanup all services."""
        for name, service in self._services.items():
            try:
                if hasattr(service, 'cleanup'):
                    service.cleanup()
                self.logger.info(f"Cleaned up service: {name}")
            except Exception as e:
                self.logger.error(f"Error cleaning up {name}: {e}")


class ServiceInitializer:
    """Initializes application services in the correct order."""
    
    def __init__(self, app: Flask, service_manager: ServiceManager):
        self.app = app
        self.service_manager = service_manager
        self.logger = get_logger('service_initializer')
    
    def initialize_all(self):
        """Initialize all services in the correct order."""
        try:
            self.logger.info("Starting service initialization...")
            
            # Initialize port manager (lightweight, no dependencies)
            self.initialize_port_manager()
            
            # Initialize docker manager
            self.initialize_docker_service()
            
            # Initialize scan manager
            self.initialize_scan_service()
            
            # Initialize batch service
            self.initialize_batch_service()
            
            # Initialize performance service if configured
            self.initialize_performance_service()
            
            self.logger.info("All services initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Error during service initialization: {e}")
            raise
    
    def initialize_port_manager(self):
        """Initialize the port manager service."""
        try:
            # Get port configuration from app config
            port_config = self.app.config.get('PORT_CONFIG', [])
            port_manager = PortManager(port_config)
            self.service_manager.register('port_manager', port_manager)
            self.logger.info(f"Port manager initialized with {len(port_config)} configurations")
        except Exception as e:
            self.logger.error(f"Failed to initialize port manager: {e}")
            raise
    
    def initialize_docker_service(self):
        """Initialize the Docker manager service."""
        try:
            docker_manager = DockerManager()
            self.service_manager.register('docker_manager', docker_manager)
            self.logger.info("Docker manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Docker manager: {e}")
            # Don't raise - Docker might not be available in all environments
    
    def initialize_scan_service(self):
        """Initialize the scan manager service."""
        try:
            scan_manager = ScanManager()
            self.service_manager.register('scan_manager', scan_manager)
            self.logger.info("Scan manager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize scan manager: {e}")
            # Don't raise - scanning might not be available in all environments
    
    def initialize_batch_service(self):
        """Initialize the batch processing service."""
        try:
            batch_service = BatchAnalysisService()
            self.service_manager.register('batch_service', batch_service)
            self.logger.info("Batch service initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize batch service: {e}")
            # Don't raise - batch processing is optional
    
    def initialize_performance_service(self):
        """Initialize the performance service if configured."""
        try:
            # This is optional and may not be available in all configurations
            if hasattr(self.app.config, 'ENABLE_PERFORMANCE_MONITORING') and self.app.config.get('ENABLE_PERFORMANCE_MONITORING'):
                # Performance service initialization would go here
                self.logger.info("Performance monitoring not configured")
        except Exception as e:
            self.logger.error(f"Failed to initialize performance service: {e}")
            # Don't raise - performance monitoring is optional


# ===========================
# FLASK APPLICATION FACTORY
# ===========================

class FlaskApplicationFactory:
    """Factory for creating Flask applications."""
    
    def create_app(self) -> Flask:
        """Create and configure the Flask application."""
        try:
            # Create Flask instance
            app = Flask(__name__)
            
            # Load configuration
            config = AppConfig()
            app.config.from_object(config)
            app.config['APP_CONFIG'] = config
            
            # Setup logging
            LoggingService.setup(app)
            logger = get_logger('app')
            
            # Setup proxy fix
            app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
            
            # Initialize services
            service_manager = ServiceManager(app)
            self._initialize_services(app, service_manager)
            
            # Register blueprints
            self._register_blueprints(app)
            
            # Setup error handlers
            self._setup_error_handlers(app)
            
            # Setup context processors
            self._setup_context_processors(app)
            
            # Register cleanup
            atexit.register(lambda: service_manager.cleanup())
            
            logger.info("Application initialized successfully")
            return app
            
        except Exception as e:
            raise InitializationError(f"Failed to create application: {e}")
    
    def _initialize_services(self, app: Flask, service_manager: ServiceManager):
        """Initialize all application services."""
        # Load port configuration
        port_config = self._load_port_config(app.config['APP_CONFIG'].BASE_DIR.parent)
        app.config['PORT_CONFIG'] = port_config
        
        # Initialize model service
        model_service = ModelIntegrationService(app.config['APP_CONFIG'].BASE_DIR.parent)
        app.config['MODEL_SERVICE'] = model_service
        app.config['AI_MODELS'] = self._extract_ai_models(port_config, model_service)
        
        # Initialize core services
        service_manager.register('docker_manager', DockerManager())
        service_manager.register('port_manager', PortManager(port_config))
        service_manager.register('scan_manager', ScanManager())
        
        # Initialize batch service
        batch_service = BatchAnalysisService()
        batch_service.init_app(app)
        service_manager.register('batch_service', batch_service)
        
        # Initialize analyzers (simplified - would load actual analyzers)
        self._initialize_analyzers(app, service_manager)
    
    def _load_port_config(self, base_path: Path) -> List[Dict[str, Any]]:
        """Load port configuration."""
        config_path = base_path / "port_config.json"
        
        if not config_path.exists():
            return []
        
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            get_logger('config').error(f"Failed to load port config: {e}")
            return []
    
    def _extract_ai_models(self, port_config: List[Dict[str, Any]], 
                          model_service: ModelIntegrationService) -> List[AIModel]:
        """Extract AI models from configuration."""
        models = []
        seen_models = set()
        
        for config in port_config:
            model_name = config.get('model_name')
            if model_name and model_name not in seen_models:
                seen_models.add(model_name)
                
                # Get model from service if available
                model_data = model_service.get_model(model_name)
                if model_data:
                    models.append(model_data)
                else:
                    # Create basic model
                    models.append(AIModel(name=model_name))
        
        return models
    
    def _initialize_analyzers(self, app: Flask, service_manager: ServiceManager):
        """Initialize analyzer services (placeholder for actual analyzers)."""
        # This would load actual analyzers like:
        # - frontend_security_analyzer
        # - backend_security_analyzer
        # - performance_analyzer
        # - zap_scanner
        # - gpt4all_analyzer
        # - code_quality_analyzer
        pass
    
    def _register_blueprints(self, app: Flask):
        """Register application blueprints."""
        # Register main routes
        app.register_blueprint(create_main_blueprint())
        app.register_blueprint(create_api_blueprint())
        app.register_blueprint(create_docker_blueprint())
        app.register_blueprint(create_batch_blueprint())
    
    def _setup_error_handlers(self, app: Flask):
        """Setup error handlers."""
        @app.errorhandler(404)
        def not_found(e):
            if request.path.startswith('/api/'):
                return create_api_response(False, error="Not found", code=404)
            return render_template('404.html'), 404
        
        @app.errorhandler(500)
        def server_error(e):
            if request.path.startswith('/api/'):
                return create_api_response(False, error="Internal server error", code=500)
            return render_template('500.html'), 500
    
    def _setup_context_processors(self, app: Flask):
        """Setup template context processors."""
        @app.context_processor
        def inject_globals():
            return {
                'ai_models': AppContext.get_ai_models,
                'get_app_info': AppUtils.get_app_info
            }


# ===========================
# BLUEPRINTS
# ===========================

def create_main_blueprint() -> Blueprint:
    """Create main blueprint with dashboard routes."""
    bp = Blueprint('main', __name__)
    
    @bp.route('/')
    def index():
        """Main dashboard."""
        try:
            apps = AppUtils.get_all_apps()
            models = AppContext.get_ai_models()
            
            return render_template('index.html', apps=apps, models=models)
        except Exception as e:
            return render_template('error.html', error=str(e)), 500
    
    @bp.route('/app/<model>/<int:app_num>')
    def app_detail(model: str, app_num: int):
        """Application detail page."""
        try:
            app_info = AppUtils.get_app_info(model, app_num)
            if not app_info:
                return render_template('404.html'), 404
            
            # Get container status
            docker_manager = AppContext.get_docker_manager()
            backend_name, frontend_name = AppUtils.get_container_names(model, app_num)
            
            backend_status = docker_manager.get_container_status(backend_name)
            frontend_status = docker_manager.get_container_status(frontend_name)
            
            return render_template('app_detail.html',
                                 app=app_info,
                                 backend_status=backend_status,
                                 frontend_status=frontend_status)
        except Exception as e:
            return render_template('error.html', error=str(e)), 500
    
    return bp


def create_api_blueprint() -> Blueprint:
    """Create API blueprint."""
    bp = Blueprint('api', __name__, url_prefix='/api')
    
    @bp.route('/status')
    def status():
        """System status endpoint."""
        return create_api_response(True, data={
            'docker': DockerUtils.is_docker_available(),
            'compose': DockerUtils.is_compose_available()
        })
    
    @bp.route('/apps')
    @handle_errors
    def list_apps():
        """List all applications."""
        apps = AppUtils.get_all_apps()
        return create_api_response(True, data=apps)
    
    @bp.route('/apps/<model>/<int:app_num>')
    @handle_errors
    def get_app(model: str, app_num: int):
        """Get specific application info."""
        app_info = AppUtils.get_app_info(model, app_num)
        if not app_info:
            return create_api_response(False, error="App not found", code=404)
        return create_api_response(True, data=app_info)
    
    @bp.route('/apps/<model>/<int:app_num>/status')
    @handle_errors
    def get_app_status(model: str, app_num: int):
        """Get application container status."""
        docker_manager = AppContext.get_docker_manager()
        backend_name, frontend_name = AppUtils.get_container_names(model, app_num)
        
        return create_api_response(True, data={
            'backend': docker_manager.get_container_status(backend_name).to_dict(),
            'frontend': docker_manager.get_container_status(frontend_name).to_dict()
        })
    
    return bp


def create_docker_blueprint() -> Blueprint:
    """Create Docker management blueprint."""
    bp = Blueprint('docker', __name__, url_prefix='/docker')
    
    @bp.route('/action', methods=['POST'])
    @handle_errors
    def docker_action():
        """Handle Docker actions."""
        data = request.get_json()
        
        action = data.get('action')
        model = data.get('model')
        app_num = data.get('app_num')
        
        if not all([action, model, app_num]):
            return create_api_response(False, error="Missing required parameters", code=400)
        
        success, message = AppUtils.handle_docker_action(action, model, app_num)
        
        return create_api_response(success, message=message, code=200 if success else 500)
    
    @bp.route('/logs/<model>/<int:app_num>')
    @handle_errors
    def get_logs(model: str, app_num: int):
        """Get container logs."""
        container_type = request.args.get('container', 'backend')
        tail = int(request.args.get('tail', 100))
        
        docker_manager = AppContext.get_docker_manager()
        logs = docker_manager.get_container_logs(model, app_num, container_type, tail)
        
        return create_api_response(True, data={'logs': logs})
    
    return bp


def create_batch_blueprint() -> Blueprint:
    """Create batch analysis blueprint."""
    bp = Blueprint('batch', __name__, url_prefix='/batch')
    
    @bp.route('/jobs', methods=['GET'])
    @handle_errors
    def list_jobs():
        """List all batch jobs."""
        batch_service = AppContext.get_batch_service()
        jobs = [job.to_dict() for job in batch_service.get_all_jobs()]
        return create_api_response(True, data=jobs)
    
    @bp.route('/jobs', methods=['POST'])
    @handle_errors
    def create_job():
        """Create a new batch job."""
        data = request.get_json()
        
        batch_service = AppContext.get_batch_service()
        job = batch_service.create_job(
            name=data.get('name', 'Unnamed Job'),
            description=data.get('description', ''),
            analysis_types=data.get('analysis_types', []),
            models=data.get('models', []),
            app_range_str=data.get('app_range', '1-5'),
            auto_start=data.get('auto_start', True)
        )
        
        return create_api_response(True, data=job.to_dict())
    
    @bp.route('/jobs/<job_id>')
    @handle_errors
    def get_job(job_id: str):
        """Get specific job details."""
        batch_service = AppContext.get_batch_service()
        job = batch_service.get_job(job_id)
        
        if not job:
            return create_api_response(False, error="Job not found", code=404)
        
        return create_api_response(True, data=job.to_dict())
    
    return bp


# ===========================
# APPLICATION ENTRY POINT
# ===========================

def create_app() -> Flask:
    """Create and configure the Flask application."""
    factory = FlaskApplicationFactory()
    return factory.create_app()


# ===========================
# UTILITY FUNCTIONS
# ===========================

def get_docker_project_name(model: str, app_num: int) -> str:
    """Generate a sanitized Docker project name from model and app number.
    
    Args:
        model: The model name (e.g., 'anthropic/claude-3-sonnet')
        app_num: The application number (1-30)
    
    Returns:
        Sanitized project name (e.g., 'anthropic_claude_3_sonnet_app1')
    """
    # Replace special characters with underscores and make lowercase
    sanitized_model = re.sub(r'[^a-zA-Z0-9_]', '_', model.lower())
    # Remove multiple consecutive underscores
    sanitized_model = re.sub(r'_+', '_', sanitized_model)
    # Remove leading/trailing underscores
    sanitized_model = sanitized_model.strip('_')
    
    return f"{sanitized_model}_app{app_num}"


def get_port_config():
    """Get port configuration from Flask app config."""
    from flask import current_app
    return current_app.config.get('PORT_CONFIG', [])


def get_ai_models():
    """Get AI models from Flask app config.""" 
    from flask import current_app
    return current_app.config.get('MODEL_CAPABILITIES', [])


def get_app_config_by_model_and_number(model: str, app_num: int):
    """Get app configuration for specific model and app number."""
    port_config = get_port_config()
    for config in port_config:
        if config.get('model') == model and config.get('app_num') == app_num:
            return config
    return None


def get_container_names(model: str, app_num: int):
    """Get container names for a specific model and app."""
    project_name = get_docker_project_name(model, app_num)
    config = get_app_config_by_model_and_number(model, app_num)
    
    if not config:
        return None
        
    backend_port = config.get('backend_port')
    frontend_port = config.get('frontend_port')
    
    return {
        'backend': f"{project_name}_backend_{backend_port}",
        'frontend': f"{project_name}_frontend_{frontend_port}"
    }


def diagnose_docker_issues():
    """Diagnose common Docker issues."""
    issues = []
    
    try:
        import docker
        client = docker.from_env()
        client.ping()
    except Exception as e:
        issues.append(f"Docker connection failed: {e}")
        return issues
    
    # Check if Docker is running
    try:
        client.info()
    except Exception as e:
        issues.append(f"Docker daemon not accessible: {e}")
    
    return issues


def generation_lookup_service():
    """Mock generation lookup service for web routes compatibility."""
    class MockGenerationLookup:
        def get_generation_by_id(self, gen_id):
            return None
        
        def get_generations_by_model(self, model):
            return []
    
    return MockGenerationLookup()


def main():
    """Main entry point."""
    try:
        app = create_app()
        config = app.config['APP_CONFIG']
        
        logger = get_logger('main')
        logger.info(f"Starting Flask application on {config.HOST}:{config.PORT}")
        
        app.run(
            host=config.HOST,
            port=config.PORT,
            debug=config.DEBUG,
            threaded=True
        )
    except Exception as e:
        print(f"Failed to start application: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())