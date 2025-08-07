"""
Constants and Enums for Thesis Research App
===========================================

Centralized constants, enums, and configuration values used throughout the application.
This module serves as a single source of truth for all shared constants.
"""

from enum import Enum
from pathlib import Path

# ===========================
# APPLICATION CONSTANTS
# ===========================

class AppDefaults:
    """Application default configuration values."""

    # Service timeouts
    CLEANUP_INTERVAL: int = 300  # 5 minutes
    IDLE_SCAN_TIMEOUT: int = 3600  # 1 hour
    MAX_ZAP_SCANS: int = 10

    # Network configuration
    HOST: str = "127.0.0.1"
    PORT: int = 5000

    # Threading and processing
    MAX_THREADS: int = 50
    BATCH_MAX_WORKERS: int = 4

    # Timeouts
    REQUEST_TIMEOUT: int = 30
    DOCKER_TIMEOUT: int = 10
    CONTAINER_HEALTH_TIMEOUT: int = 60
    BUILD_TIMEOUT: int = 300

    # Cache settings
    CACHE_TTL: int = 300  # 5 minutes
    DOCKER_CACHE_TTL: int = 10  # 10 seconds

    # Logging
    LOG_MAX_BYTES: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5


class ServiceNames:
    """Standardized service names for service locator pattern."""

    DOCKER_MANAGER = "docker_manager"
    SCAN_MANAGER = "scan_manager"
    MODEL_SERVICE = "model_service"
    PORT_MANAGER = "port_manager"
    BATCH_SERVICE = "batch_service"
    PERFORMANCE_SERVICE = "performance_service"
    ZAP_SERVICE = "zap_service"
    SECURITY_SERVICE = "security_service"


class ContainerNames:
    """Standard container naming patterns."""

    BACKEND = "backend"
    FRONTEND = "frontend"
    DATABASE = "database"

    @staticmethod
    def get_container_name(model: str, app_num: int, container_type: str) -> str:
        """Generate standardized container name."""
        project_name = f"{model.replace('/', '_').replace('-', '_')}_app{app_num}"
        return f"{project_name}_{container_type}"


# ===========================
# STATUS ENUMS
# ===========================

class BaseEnum(str, Enum):
    """Base enum class with string values for consistent behavior."""

    def __str__(self):
        return self.value


class AnalysisStatus(BaseEnum):
    """Status enum for analyses and tests."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobStatus(BaseEnum):
    """Status enum for batch jobs."""
    PENDING = "pending"
    QUEUED = "queued"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    CANCELLING = "cancelling"
    ARCHIVED = "archived"
    ERROR = "error"


class TaskStatus(BaseEnum):
    """Status enum for batch tasks."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"


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
# ANALYSIS AND TESTING ENUMS
# ===========================

class AnalysisType(BaseEnum):
    """Types of analysis that can be performed."""
    SECURITY_BACKEND = "security_backend"
    SECURITY_FRONTEND = "security_frontend"
    SECURITY_COMBINED = "security_combined"
    PERFORMANCE = "performance"
    ZAP_SECURITY = "zap_security"
    OPENROUTER = "openrouter"
    CODE_QUALITY = "code_quality"
    DEPENDENCY_CHECK = "dependency_check"
    DOCKER_SCAN = "docker_scan"
    # Legacy support
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_SECURITY = "backend_security"


class SeverityLevel(BaseEnum):
    """Severity levels for security issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class JobPriority(BaseEnum):
    """Priority levels for batch jobs."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ToolCategory(BaseEnum):
    """Tool categories for classification."""
    BACKEND_SECURITY = "backend_security"
    FRONTEND_SECURITY = "frontend_security"
    BACKEND_QUALITY = "backend_quality"
    FRONTEND_QUALITY = "frontend_quality"
    PERFORMANCE = "performance"
    VULNERABILITY = "vulnerability"


# ===========================
# TESTING INFRASTRUCTURE ENUMS
# ===========================

class TestType(BaseEnum):
    """Type of test to run."""
    SECURITY = "security"
    PERFORMANCE = "performance"
    ZAP = "zap"
    HEALTH = "health"


class TestingStatus(BaseEnum):
    """Status of test execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ===========================
# DIRECTORY PATHS
# ===========================

class Paths:
    """Centralized path definitions."""

    # Base paths
    SRC_DIR = Path(__file__).parent
    PROJECT_ROOT = SRC_DIR.parent

    # Data directories
    MISC_DIR = PROJECT_ROOT / "misc"
    MODELS_DIR = MISC_DIR / "models"
    LOGS_DIR = PROJECT_ROOT / "logs"
    DATA_DIR = SRC_DIR / "data"
    REPORTS_DIR = PROJECT_ROOT / "reports"

    # Configuration files
    PORT_CONFIG = MISC_DIR / "port_config.json"
    MODEL_CAPABILITIES = MISC_DIR / "model_capabilities.json"
    MODELS_SUMMARY = MISC_DIR / "models_summary.json"

    # Testing infrastructure
    TESTING_INFRASTRUCTURE = PROJECT_ROOT / "testing-infrastructure"

    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        for attr_name in dir(cls):
            if attr_name.endswith('_DIR'):
                path = getattr(cls, attr_name)
                if isinstance(path, Path):
                    path.mkdir(parents=True, exist_ok=True)


# ===========================
# NETWORK CONFIGURATION
# ===========================

class NetworkConfig:
    """Network configuration constants."""

    # Port ranges
    BACKEND_PORT_START = 5001
    FRONTEND_PORT_START = 8001
    TESTING_SERVICES_PORT_START = 8000

    # Service ports
    SECURITY_SCANNER_PORT = 8001
    PERFORMANCE_TESTER_PORT = 8002
    ZAP_SCANNER_PORT = 8003
    API_GATEWAY_PORT = 8000

    # URLs
    TESTING_SERVICES_BASE_URL = "http://localhost:8000"


# ===========================
# ERROR MESSAGES
# ===========================

class ErrorMessages:
    """Standardized error messages."""

    SERVICE_NOT_FOUND = "Service '{service_name}' not found"
    DOCKER_NOT_AVAILABLE = "Docker service is not available"
    CONTAINER_NOT_FOUND = "Container '{container_name}' not found"
    INVALID_MODEL_APP = "Invalid model '{model}' or app number '{app_num}'"
    OPERATION_TIMEOUT = "Operation timed out after {timeout} seconds"
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions for operation"
    SERVICE_INITIALIZATION_FAILED = "Failed to initialize service '{service_name}': {error}"


# ===========================
# HTTP STATUS CODES
# ===========================

class HTTPStatus:
    """HTTP status codes for API responses."""

    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503


# Initialize directories on import
Paths.ensure_directories()
