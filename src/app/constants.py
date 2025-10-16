"""
Constants and Enums for Thesis Research App
===========================================

Centralized enums and a minimal set of shared constants.

Notes:
- Prefer importing path constants from `app.paths`. The legacy `Paths` class
    remains for a few compatibility lookups (e.g., reports, legacy misc/*).
- Legacy/unused enums and constants have been pruned to reduce noise.
"""

from enum import Enum
from pathlib import Path


# (Pruned legacy constants: AppDefaults, ServiceNames, ContainerNames)


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


# (Pruned legacy enum: TaskStatus)


# (Pruned legacy enum: ScanStatus)


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


# (Pruned legacy enum: OperationType)


# ===========================
# ANALYSIS AND TESTING ENUMS
# ===========================

class AnalysisType(BaseEnum):
    """Types of analysis that can be performed."""
    SECURITY = "security"  # General security analysis (maps to backend by default)
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


# (Pruned legacy enum: ToolCategory)


# ===========================
# TESTING INFRASTRUCTURE ENUMS
# ===========================

# (Pruned legacy enum: TestType)


# (Pruned legacy enum: TestingStatus)


# ===========================
# DIRECTORY PATHS
# ===========================

class Paths:
    """Centralized path definitions."""
    
    # Base paths
    SRC_DIR = Path(__file__).parent
    PROJECT_ROOT = SRC_DIR.parent.parent
    
    # Data directories
    MISC_DIR = PROJECT_ROOT / "misc"
    MODELS_DIR = MISC_DIR / "models"
    LOGS_DIR = PROJECT_ROOT / "logs"
    DATA_DIR = SRC_DIR / "data"
    REPORTS_DIR = PROJECT_ROOT / "reports"
    
    # Configuration files
    PORT_CONFIG = MISC_DIR / "port_config.json"
    MODELS_SUMMARY = MISC_DIR / "models_summary.json"
    
    # Testing infrastructure
    TESTING_INFRASTRUCTURE = PROJECT_ROOT / "testing-infrastructure"
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        for attr_name in dir(cls):
            if not attr_name.endswith('_DIR'):
                continue
            # Do NOT auto-create legacy misc/models directory
            # This path is maintained for backward-compatible lookups only.
            # Creating it on import leads to an empty misc/models/ being spawned.
            if attr_name == 'MODELS_DIR':
                continue
            path = getattr(cls, attr_name)
            if isinstance(path, Path):
                path.mkdir(parents=True, exist_ok=True)


# ===========================
# NETWORK CONFIGURATION
# ===========================

# (Pruned legacy constants: NetworkConfig)


# ===========================
# ERROR MESSAGES
# ===========================

# (Pruned legacy constants: ErrorMessages)


# ===========================
# HTTP STATUS CODES
# ===========================

# (Pruned legacy constants: HTTPStatus)


# Initialize directories on import
Paths.ensure_directories()
