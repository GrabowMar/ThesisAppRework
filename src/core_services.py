"""
Consolidated Flask Application for Thesis Research
==================================================

This module combines all services, utilities, and application components into a single file.
Provides security analysis, performance testing, ZAP scanning, batch processing, and more.
"""

# ===========================
# IMPORTS
# ===========================

import json
import logging
import logging.handlers
import os
import re
import subprocess
import threading
import time
import uuid
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docker
from docker.errors import NotFound as DockerNotFound
from dotenv import load_dotenv
from flask import (
    Blueprint, Flask, Response, current_app, g, has_request_context,
    jsonify, render_template, request
)

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
    
    @staticmethod
    def _safe_int_env(key: str, default: int) -> int:
        """Safely parse an integer from environment variables."""
        value = None  # Initialize value to avoid unbound variable
        try:
            value = os.getenv(key)
            if value:
                return int(value)
            return default
        except ValueError:
            logging.warning(f"Invalid integer value for {key}: '{value}', using default: {default}")
            return default

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
                        request_line = str(record.args[0]) if record.args else ""
                        parts = request_line.split()
                        if len(parts) >= 2:
                            path = parts[1]
                            if any(excluded in path for excluded in self.EXCLUDED_PATHS):
                                # Access status code more safely
                                if len(record.args) > 1:
                                    try:
                                        status_code = int(str(record.args[1]))
                                        return status_code >= 400
                                    except (ValueError, TypeError, IndexError):
                                        return True
                                return True
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
    updated_at: Optional[datetime] = field(default=None)
    
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
        datetime_fields = ['created_at', 'started_at', 'completed_at', 'updated_at']
        
        for field in datetime_fields:
            if data.get(field):
                try:
                    # Handle both datetime objects and string representations
                    if isinstance(data[field], datetime):
                        data[f'{field}_formatted'] = data[field].strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(data[field], str):
                        # Try to parse string as datetime and format it
                        try:
                            dt = datetime.fromisoformat(data[field].replace('Z', '+00:00'))
                            data[f'{field}_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            data[f'{field}_formatted'] = data[field]  # Use as-is if parsing fails
                    else:
                        data[f'{field}_formatted'] = str(data[field])
                except Exception as e:
                    # Fallback for any conversion issues
                    data[f'{field}_formatted'] = 'N/A'
        
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
        except DockerNotFound:
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
            
            # Build full command - try docker compose first, then docker-compose
            base_commands = [
                ["docker", "compose"],
                ["docker-compose"]
            ]
            
            for base_cmd in base_commands:
                cmd = base_cmd + ["-p", project_name, "-f", str(compose_file)] + command
                
                self.logger.info(f"Executing: {' '.join(cmd)}")
                
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=str(compose_dir),
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                    )
                    
                    # If command succeeded or it's a real error (not command not found)
                    if result.returncode == 0 or "command not found" not in result.stderr.lower():
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
                except FileNotFoundError:
                    # Try next command
                    continue
            
            # If we get here, no command worked
            return {'success': False, 'error': 'Docker Compose not found. Please install Docker Compose.'}
            
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
        
        backend_port = config.get('backend_port')
        frontend_port = config.get('frontend_port')
        
        # Ensure ports are integers
        if backend_port is None or frontend_port is None:
            return None
            
        return {
            "backend": int(backend_port),
            "frontend": int(frontend_port)
        }
    
    def get_all_models(self) -> List[str]:
        """Get all unique model names."""
        models = []
        for config in self.port_config:
            model_name = config.get('model_name')
            if model_name and isinstance(model_name, str):
                models.append(model_name)
        return list(set(models))


# ===========================
# TESTING SERVICE CLIENT
# ===========================

class TestingServiceClient(BaseService):
    """Client for communicating with containerized testing services."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        super().__init__('testing_client')
        self.base_url = base_url.rstrip('/')
        self.timeout = 300
        self._session = None
    
    def _get_session(self):
        """Get or create HTTP session."""
        if self._session is None:
            import requests
            self._session = requests.Session()
            self._session.timeout = self.timeout
        return self._session
    
    def submit_security_analysis(self, model: str, app_num: int, tools: List[str] = None) -> str:
        """Submit security analysis request."""
        try:
            session = self._get_session()
            data = {
                "model": model,
                "app_num": app_num,
                "test_type": "security_backend",
                "tools": tools or ["bandit", "safety", "pylint", "eslint"],
                "options": {}
            }
            
            response = session.post(f"{self.base_url}/api/security/tests", json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                return result["data"]["test_id"]
            else:
                raise Exception(f"Failed to submit test: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Failed to submit security analysis: {e}")
            raise
    
    def submit_performance_test(self, model: str, app_num: int, target_url: str, users: int = 10) -> str:
        """Submit performance test request."""
        try:
            session = self._get_session()
            data = {
                "model": model,
                "app_num": app_num,
                "test_type": "performance",
                "users": users,
                "target_url": target_url,
                "duration": 60,
                "options": {}
            }
            
            response = session.post(f"{self.base_url}/api/performance/tests", json=data)
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                return result["data"]["test_id"]
            else:
                raise Exception(f"Failed to submit test: {result.get('error')}")
                
        except Exception as e:
            self.logger.error(f"Failed to submit performance test: {e}")
            raise
    
    def get_test_status(self, test_id: str, service_type: str) -> str:
        """Get test status."""
        try:
            session = self._get_session()
            endpoint_map = {
                "security": "security",
                "performance": "performance", 
                "zap": "zap",
                "ai": "ai"
            }
            
            endpoint = endpoint_map.get(service_type, "security")
            response = session.get(f"{self.base_url}/api/{endpoint}/tests/{test_id}/status")
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                return result["data"]["status"]
            else:
                return "failed"
                
        except Exception as e:
            self.logger.error(f"Failed to get test status: {e}")
            return "failed"
    
    def get_test_result(self, test_id: str, service_type: str) -> Optional[Dict[str, Any]]:
        """Get test result."""
        try:
            session = self._get_session()
            endpoint_map = {
                "security": "security",
                "performance": "performance",
                "zap": "zap", 
                "ai": "ai"
            }
            
            endpoint = endpoint_map.get(service_type, "security")
            response = session.get(f"{self.base_url}/api/{endpoint}/tests/{test_id}/result")
            response.raise_for_status()
            
            result = response.json()
            if result.get("success"):
                return result["data"]
            else:
                return None
                
        except Exception as e:
            self.logger.error(f"Failed to get test result: {e}")
            return None
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all testing services."""
        try:
            session = self._get_session()
            response = session.get(f"{self.base_url}/api/health")
            response.raise_for_status()
            
            result = response.json()
            return result.get("data", {})
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return {}
    
    def cleanup(self):
        """Cleanup resources."""
        if self._session:
            self._session.close()
            self._session = None


# ===========================
# SCAN MANAGER
# ===========================

class ScanManager(BaseService):
    """Manages application security scans."""
    
    def __init__(self):
        super().__init__('scan_manager')
        self.scans: Dict[str, Dict[str, Any]] = {}
        self.testing_client = TestingServiceClient()
    
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
    
    def run_security_analysis(self, model: str, app_num: int, enabled_tools: dict) -> dict:
        """Run security analysis using containerized services with fallback to legacy."""
        try:
            self.logger.info(f"Starting security analysis for {model} app {app_num}")
            
            # Try containerized service first
            try:
                # Determine tools to use based on enabled_tools
                tools = []
                if any(tool in enabled_tools and enabled_tools[tool] for tool in ['bandit', 'safety', 'semgrep']):
                    tools.extend(['bandit', 'safety', 'pylint'])
                if any(tool in enabled_tools and enabled_tools[tool] for tool in ['eslint', 'npm_audit', 'retire']):
                    tools.extend(['eslint', 'retire', 'npm-audit'])
                
                if not tools:
                    tools = ['bandit', 'safety', 'eslint']
                
                # Submit to containerized service
                test_id = self.testing_client.submit_security_analysis(model, app_num, tools)
                
                return {
                    'success': True,
                    'test_id': test_id,
                    'message': 'Security analysis submitted to containerized service',
                    'data': {
                        'status': 'submitted',
                        'test_id': test_id,
                        'mode': 'containerized'
                    }
                }
                
            except Exception as containerized_error:
                self.logger.warning(f"Containerized service failed, falling back to legacy: {containerized_error}")
                
                # Fallback to legacy implementation
                return self._run_legacy_security_analysis(model, app_num, enabled_tools)
                
        except Exception as e:
            self.logger.error(f"Security analysis failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _run_legacy_security_analysis(self, model: str, app_num: int, enabled_tools: dict) -> dict:
        """Fallback security analysis when containerized services are unavailable."""
        self.logger.warning("Containerized security services unavailable, using mock analysis")
        return {
            'success': True,
            'data': {
                'issues': [],
                'total_issues': 0,
                'categories': [],
                'warning': 'Security analysis service not available - containerized services recommended',
                'mode': 'mock'
            }
        }

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
            if self.app:
                with self.app.app_context():
                    self._execute_task_with_context(task)
            else:
                self.logger.warning("No Flask app context available for task execution")
                self._execute_task_with_context(task)
                
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
    
    def _execute_task_with_context(self, task: BatchTask):
        """Execute task logic within proper context."""
        # Get the appropriate analyzer
        analyzer = self._get_analyzer(task.analysis_type)
        if not analyzer:
            raise ValueError(f"No analyzer available for {task.analysis_type}")
        
        # Run analysis
        result = self._run_analysis(analyzer, task)
        
        task.result = result
        task.status = TaskStatus.COMPLETED
        task.issues_count = self._count_issues(result)
    
    def _get_analyzer(self, analysis_type: str):
        """Get the appropriate analyzer for the analysis type."""
        analyzer_map = {
            AnalysisType.FRONTEND_SECURITY.value: 'frontend_security_analyzer',
            AnalysisType.BACKEND_SECURITY.value: 'backend_security_analyzer',
            AnalysisType.PERFORMANCE.value: 'performance_service',
            AnalysisType.ZAP.value: 'zap_service',
            AnalysisType.GPT4ALL.value: 'gpt4all_analyzer',
            AnalysisType.CODE_QUALITY.value: 'code_quality_analyzer'
        }
        
        analyzer_name = analyzer_map.get(analysis_type)
        if analyzer_name:
            # Try to get from service manager first
            if hasattr(self.app, 'config') and 'service_manager' in self.app.config:
                service_manager = self.app.config['service_manager']
                analyzer = service_manager.get_service(analyzer_name)
                if analyzer:
                    return analyzer
            
            # Fallback to direct app attribute
            return getattr(self.app, analyzer_name, None)
        return None
    
    def _run_analysis(self, analyzer, task: BatchTask) -> Dict[str, Any]:
        """Run the analysis using the analyzer."""
        # Handle mock services
        if hasattr(analyzer, '__class__') and 'Mock' in analyzer.__class__.__name__:
            return {"status": "unavailable", "message": f"{task.analysis_type} service not installed"}
        
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
            # Run within Flask application context if app is available
            if self.app:
                with self.app.app_context():
                    self._execute_job_tasks(job_id, job)
            else:
                self.logger.warning("No Flask app context available for job execution")
                self._execute_job_tasks(job_id, job)
                
        except Exception as e:
            self.logger.error(f"Job execution failed: {e}", exc_info=True)
            try:
                # Try to mark job as failed within app context if available
                if self.app:
                    with self.app.app_context():
                        job.status = JobStatus.FAILED
                        job.error_message = str(e)
                else:
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
            except Exception as mark_error:
                self.logger.error(f"Failed to mark job as failed: {mark_error}")
        
        finally:
            job.completed_at = datetime.now()
            
            with self._lock:
                if job_id in self.job_threads:
                    del self.job_threads[job_id]
                    
    def _execute_job_tasks(self, job_id: str, job: BatchJob):
        """Execute the actual job tasks."""
        tasks = [task for task in self.tasks.values() if task.job_id == job_id]
        worker = BatchTaskWorker(self.app)
        
        # Submit all tasks
        futures = []
        for task in tasks:
            if self.shutdown_event.is_set():
                break
            
            if self.worker_pool is not None:
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
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a running job (not implemented - jobs cannot be paused)."""
        # Note: JobStatus doesn't have PAUSED state
        return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job (not implemented - jobs cannot be paused)."""
        # Note: JobStatus doesn't have PAUSED state  
        return False

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
        # Check config first, then attributes
        docker_manager = current_app.config.get('docker_manager')
        if docker_manager:
            return docker_manager
        
        # Check if it's registered as an attribute via ServiceManager
        service_manager = current_app.config.get('service_manager')
        if service_manager:
            docker_manager = service_manager.get_service('docker_manager')
            if docker_manager:
                return docker_manager
            
        raise RuntimeError("Docker manager not available")
    
    @staticmethod
    def get_port_manager() -> PortManager:
        """Get Port manager from app context."""
        # Check config first, then attributes
        port_manager = current_app.config.get('port_manager')
        if port_manager:
            return port_manager
        
        # Check if it's registered via ServiceManager
        service_manager = current_app.config.get('service_manager')
        if service_manager:
            port_manager = service_manager.get_service('port_manager')
            if port_manager:
                return port_manager
            
        raise RuntimeError("Port manager not available")
    
    @staticmethod
    def get_scan_manager() -> ScanManager:
        """Get Scan manager from app context."""
        # Check config first, then attributes
        scan_manager = current_app.config.get('scan_manager')
        if scan_manager:
            return scan_manager
        
        # Check if it's registered via ServiceManager
        service_manager = current_app.config.get('service_manager')
        if service_manager:
            scan_manager = service_manager.get_service('scan_manager')
            if scan_manager:
                return scan_manager
            
        raise RuntimeError("Scan manager not available")
    
    @staticmethod
    def get_batch_service() -> BatchAnalysisService:
        """Get Batch service from app context."""
        # Check config first, then attributes
        batch_service = current_app.config.get('batch_service')
        if batch_service:
            return batch_service
        
        # Check if it's registered via ServiceManager
        service_manager = current_app.config.get('service_manager')
        if service_manager:
            batch_service = service_manager.get_service('batch_service')
            if batch_service:
                return batch_service
            
        raise RuntimeError("Batch service not available")
    
    @staticmethod
    def get_model_service() -> Optional[ModelIntegrationService]:
        """Get Model service from app context."""
        model_service = current_app.config.get('MODEL_SERVICE')
        if isinstance(model_service, ModelIntegrationService):
            return model_service
        return None
    
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
        app_config = current_app.config.get('APP_CONFIG')
        if app_config and hasattr(app_config, 'MODELS_BASE_DIR'):
            models_base_dir = Path(app_config.MODELS_BASE_DIR)
        else:
            # Fallback to default
            models_base_dir = Path(__file__).parent.parent / "models"
            
        app_path = models_base_dir / model / f"app{app_num}"
        
        if not app_path.is_dir():
            # Try misc/models path as fallback
            misc_models_dir = Path(__file__).parent.parent / "misc" / "models"
            app_path = misc_models_dir / model / f"app{app_num}"
            
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
        
        try:
            app_num = int(app_num)  # Ensure app_num is an integer
        except (ValueError, TypeError):
            return create_api_response(False, error="Invalid app_num", code=400)
        
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

# def create_app() -> Flask:
#     """Create and configure the Flask application."""
#     factory = FlaskApplicationFactory()
#     return factory.create_app()


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
    sanitized_model = re.sub(r'[^aA-Zz0-9_]', '_', model.lower())
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
        # Import from app.py instead of using local create_app
        from app import app
        
        logger = get_logger('main')
        logger.info("Starting Flask application from core_services main")
        
        # Add startup message
        print("""
╔══════════════════════════════════════════════════════════════╗
║           Thesis Research App - Core Services                ║
╚══════════════════════════════════════════════════════════════╝

🚀 Server starting...
📋 Core services module loaded
""")
        
        # Run app with basic config
        app.run(host='127.0.0.1', port=5000, debug=False)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
        return 0
    except Exception as e:
        print(f"Failed to start application: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())