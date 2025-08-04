"""
Testing API Models for Security Scanner - Synchronized with Main App
===================================================================

These models are synchronized with the main application to ensure API compatibility.
This file should be kept in sync with the shared testing API models.

Key compatibility considerations:
- Status enums must match between web app and containers
- Data structures must be compatible for serialization
- All required fields must be present in both systems
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

# Export all the models that should be available for import
__all__ = [
    'TestingStatus', 'SeverityLevel', 'TestType',
    'TestRequest', 'SecurityTestRequest', 'TestIssue', 'TestResult', 'SecurityTestResult',
    'APIResponse', 'convert_testing_status_to_analysis_status', 'create_main_app_compatible_result'
]


class TestingStatus(str, Enum):
    """Status enumeration for testing operations - compatible with AnalysisStatus."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"  # Additional status for container timeouts


class SeverityLevel(str, Enum):
    """Severity levels for security and quality issues - matches main app."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestType(str, Enum):
    """Types of tests that can be performed - compatible with AnalysisType."""
    SECURITY_BACKEND = "security_backend"
    SECURITY_FRONTEND = "security_frontend"
    SECURITY_COMBINED = "security_combined"  # Added to match main app
    SECURITY_ZAP = "zap_security"  # Maps to main app's ZAP_SECURITY
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    AI_ANALYSIS = "ai_analysis"
    OPENROUTER = "openrouter"  # Added to match main app
    DEPENDENCY_CHECK = "dependency_check"  # Added to match main app
    DOCKER_SCAN = "docker_scan"  # Added to match main app


@dataclass
class TestRequest:
    """Base class for all test requests - compatible with main app contracts."""
    model: str
    app_num: int
    test_type: TestType
    options: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300  # 5 minutes default
    priority: int = 1  # 1=low, 2=normal, 3=high


@dataclass
class SecurityTestRequest(TestRequest):
    """Request for security analysis testing - matches main app expectations."""
    tools: List[str] = field(default_factory=list)  # bandit, safety, eslint, etc.
    scan_depth: str = "standard"  # minimal, standard, thorough
    include_dependencies: bool = True
    
    # Additional fields for compatibility with main app
    bandit_enabled: bool = True
    safety_enabled: bool = True
    pylint_enabled: bool = True
    eslint_enabled: bool = True
    npm_audit_enabled: bool = True
    snyk_enabled: bool = False


@dataclass
class TestIssue:
    """Represents a single issue found during testing - compatible with main app."""
    tool: str
    severity: SeverityLevel
    confidence: str
    file_path: str
    line_number: Optional[int] = None
    message: str = ""
    description: str = ""
    solution: str = ""
    reference: str = ""
    code_snippet: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with main app."""
        return {
            'tool': self.tool,
            'severity': self.severity.value,
            'confidence': self.confidence,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'message': self.message,
            'description': self.description,
            'solution': self.solution,
            'reference': self.reference,
            'code_snippet': self.code_snippet
        }


@dataclass
class TestResult:
    """Base class for all test results - compatible with main app storage."""
    test_id: str
    status: TestingStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    error_message: Optional[str] = None
    issues: List[TestIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization - main app compatible."""
        return {
            'test_id': self.test_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'error_message': self.error_message,
            'issues': [issue.to_dict() for issue in self.issues],
            'metadata': self.metadata,
            'total_issues': len(self.issues)
        }
    
    def get_severity_counts(self) -> Dict[str, int]:
        """Get severity counts compatible with main app SecurityAnalysis model."""
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in self.issues:
            severity = issue.severity.value.lower()
            if severity in counts:
                counts[severity] += 1
        return counts


@dataclass
class SecurityTestResult(TestResult):
    """Results from security analysis - compatible with main app SecurityAnalysis."""
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    tools_used: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Auto-calculate counts from issues for consistency."""
        if self.issues:
            self.total_issues = len(self.issues)
            severity_counts = self.get_severity_counts()
            self.critical_count = severity_counts["critical"]
            self.high_count = severity_counts["high"]
            self.medium_count = severity_counts["medium"]
            self.low_count = severity_counts["low"]
    
    def to_dict(self) -> Dict[str, Any]:
        """Enhanced dictionary with all fields expected by main app."""
        base_dict = super().to_dict()
        base_dict.update({
            'total_issues': self.total_issues,
            'critical_count': self.critical_count,
            'high_count': self.high_count,
            'medium_count': self.medium_count,
            'low_count': self.low_count,
            'tools_used': self.tools_used,
            # Map to main app field names
            'critical_severity_count': self.critical_count,
            'high_severity_count': self.high_count,
            'medium_severity_count': self.medium_count,
            'low_severity_count': self.low_count
        })
        return base_dict


@dataclass
class APIResponse:
    """Standard API response format - compatible with main app."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response - main app compatible."""
        result = {
            'success': self.success,
            'timestamp': self.timestamp.isoformat()
        }
        
        if self.data is not None:
            if hasattr(self.data, 'to_dict'):
                result['data'] = self.data.to_dict()
            elif isinstance(self.data, list) and self.data and hasattr(self.data[0], 'to_dict'):
                result['data'] = [item.to_dict() for item in self.data]
            else:
                result['data'] = self.data
                
        if self.error:
            result['error'] = self.error
            
        if self.message:
            result['message'] = self.message
            
        return result


# Utility functions for compatibility with main app
def convert_testing_status_to_analysis_status(status: TestingStatus) -> str:
    """Convert TestingStatus to AnalysisStatus for main app compatibility."""
    mapping = {
        TestingStatus.PENDING: "pending",
        TestingStatus.RUNNING: "running", 
        TestingStatus.COMPLETED: "completed",
        TestingStatus.FAILED: "failed",
        TestingStatus.CANCELLED: "cancelled",
        TestingStatus.TIMEOUT: "failed"  # Map timeout to failed for main app
    }
    return mapping.get(status, "failed")


def create_main_app_compatible_result(result: SecurityTestResult) -> Dict[str, Any]:
    """Create a result dictionary that's fully compatible with main app models."""
    return {
        # Core fields
        'status': convert_testing_status_to_analysis_status(result.status),
        'started_at': result.started_at,
        'completed_at': result.completed_at,
        'analysis_duration': result.duration,
        
        # Tool configuration (for SecurityAnalysis model)
        'bandit_enabled': 'bandit' in result.tools_used,
        'safety_enabled': 'safety' in result.tools_used,
        'pylint_enabled': 'pylint' in result.tools_used,
        'eslint_enabled': 'eslint' in result.tools_used,
        'npm_audit_enabled': 'npm-audit' in result.tools_used,
        'snyk_enabled': 'snyk' in result.tools_used,
        
        # Results summary
        'total_issues': result.total_issues,
        'critical_severity_count': result.critical_count,
        'high_severity_count': result.high_count,
        'medium_severity_count': result.medium_count,
        'low_severity_count': result.low_count,
        
        # Detailed results
        'results_json': result.to_dict(),
        'metadata_json': result.metadata
    }
