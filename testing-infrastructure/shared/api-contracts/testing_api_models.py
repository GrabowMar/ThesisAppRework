"""
Testing API Models and Contracts
================================

Shared data models for communication between main app and testing containers.
These models ensure consistent API contracts across all testing services.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
import json


class TestingStatus(str, Enum):
    """Status enumeration for testing operations."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class SeverityLevel(str, Enum):
    """Severity levels for security and quality issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TestType(str, Enum):
    """Types of tests that can be performed."""
    SECURITY_BACKEND = "security_backend"
    SECURITY_FRONTEND = "security_frontend"
    SECURITY_ZAP = "security_zap"
    PERFORMANCE = "performance"
    CODE_QUALITY = "code_quality"
    AI_ANALYSIS = "ai_analysis"


@dataclass
class TestRequest:
    """Base class for all test requests."""
    model: str
    app_num: int
    test_type: TestType
    options: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300  # 5 minutes default
    priority: int = 1  # 1=low, 2=normal, 3=high


@dataclass
class SecurityTestRequest(TestRequest):
    """Request for security analysis testing."""
    tools: List[str] = field(default_factory=list)  # bandit, safety, eslint, etc.
    scan_depth: str = "standard"  # minimal, standard, thorough
    include_dependencies: bool = True


@dataclass
class PerformanceTestRequest(TestRequest):
    """Request for performance testing."""
    users: int = 10
    spawn_rate: int = 2
    duration: int = 60  # seconds
    target_url: str = ""


@dataclass
class ZapTestRequest(TestRequest):
    """Request for ZAP security scanning."""
    scan_type: str = "spider"  # spider, active, passive
    target_url: str = ""
    authentication: Optional[Dict[str, str]] = None


@dataclass
class AIAnalysisRequest(TestRequest):
    """Request for AI-powered code analysis."""
    model_name: str = "mistralai/mistral-small-3.2-24b-instruct"
    analysis_type: str = "requirements_check"
    requirements: List[str] = field(default_factory=list)


@dataclass
class TestIssue:
    """Represents a single issue found during testing."""
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


@dataclass
class TestResult:
    """Base class for all test results."""
    test_id: str
    status: TestingStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    error_message: Optional[str] = None
    issues: List[TestIssue] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'test_id': self.test_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'error_message': self.error_message,
            'issues': [
                {
                    'tool': issue.tool,
                    'severity': issue.severity.value,
                    'confidence': issue.confidence,
                    'file_path': issue.file_path,
                    'line_number': issue.line_number,
                    'message': issue.message,
                    'description': issue.description,
                    'solution': issue.solution,
                    'reference': issue.reference,
                    'code_snippet': issue.code_snippet
                }
                for issue in self.issues
            ],
            'metadata': self.metadata
        }


@dataclass
class SecurityTestResult(TestResult):
    """Results from security analysis."""
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    tools_used: List[str] = field(default_factory=list)


@dataclass
class PerformanceTestResult(TestResult):
    """Results from performance testing."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0
    requests_per_second: float = 0.0
    error_rate: float = 0.0


@dataclass
class ZapTestResult(TestResult):
    """Results from ZAP security scanning."""
    alerts_count: int = 0
    high_risk_count: int = 0
    medium_risk_count: int = 0
    low_risk_count: int = 0
    info_count: int = 0
    scan_type: str = ""
    target_url: str = ""


@dataclass
class AIAnalysisResult(TestResult):
    """Results from AI-powered analysis."""
    requirements_met: int = 0
    requirements_total: int = 0
    compliance_score: float = 0.0
    model_used: str = ""
    tokens_used: int = 0


@dataclass
class BatchTestRequest:
    """Request for batch testing across multiple apps/models."""
    batch_id: str
    name: str
    description: str
    tests: List[TestRequest]
    created_at: datetime = field(default_factory=datetime.utcnow)
    priority: int = 1


@dataclass
class BatchTestResult:
    """Results from batch testing."""
    batch_id: str
    status: TestingStatus
    total_tests: int
    completed_tests: int
    failed_tests: int
    results: List[TestResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# API Response Models
@dataclass
class APIResponse:
    """Standard API response format."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        result = {
            'success': self.success,
            'timestamp': self.timestamp.isoformat()
        }
        
        if self.data is not None:
            if hasattr(self.data, 'to_dict'):
                result['data'] = self.data.to_dict()
            else:
                result['data'] = self.data
                
        if self.error:
            result['error'] = self.error
            
        if self.message:
            result['message'] = self.message
            
        return result


# Utility functions for API contract validation
def validate_test_request(request_data: Dict[str, Any], test_type: TestType) -> bool:
    """Validate test request data against contract."""
    required_fields = ['model', 'app_num', 'test_type']
    
    for field in required_fields:
        if field not in request_data:
            return False
    
    if request_data['test_type'] != test_type.value:
        return False
    
    return True


def create_test_result_from_dict(data: Dict[str, Any]) -> TestResult:
    """Create TestResult from dictionary data."""
    issues = []
    for issue_data in data.get('issues', []):
        issues.append(TestIssue(
            tool=issue_data['tool'],
            severity=SeverityLevel(issue_data['severity']),
            confidence=issue_data['confidence'],
            file_path=issue_data['file_path'],
            line_number=issue_data.get('line_number'),
            message=issue_data.get('message', ''),
            description=issue_data.get('description', ''),
            solution=issue_data.get('solution', ''),
            reference=issue_data.get('reference', ''),
            code_snippet=issue_data.get('code_snippet', '')
        ))
    
    return TestResult(
        test_id=data['test_id'],
        status=TestingStatus(data['status']),
        started_at=datetime.fromisoformat(data['started_at']),
        completed_at=datetime.fromisoformat(data['completed_at']) if data.get('completed_at') else None,
        duration=data.get('duration'),
        error_message=data.get('error_message'),
        issues=issues,
        metadata=data.get('metadata', {})
    )
