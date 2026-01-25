"""
WebSocket Message Protocol and Data Models for Analyzer
======================================================

Modern WebSocket-based communication protocol for real-time testing infrastructure.
Built with asyncio and type hints for robust, scalable analysis services.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid


class MessageType(str, Enum):
    """WebSocket message types for analyzer communication."""
    # Client requests
    ANALYSIS_REQUEST = "analysis_request"
    BATCH_REQUEST = "batch_request"
    STATUS_REQUEST = "status_request"
    CANCEL_REQUEST = "cancel_request"
    
    # Service responses
    ANALYSIS_RESULT = "analysis_result"
    BATCH_RESULT = "batch_result"
    PROGRESS_UPDATE = "progress_update"
    STATUS_UPDATE = "status_update"
    
    # System messages
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    SERVICE_REGISTER = "service_register"
    SERVICE_UNREGISTER = "service_unregister"
    CONNECTION_ACK = "connection_ack"


class ServiceType(str, Enum):
    """Available analyzer services."""
    SECURITY_ANALYZER = "security_analyzer"
    PERFORMANCE_TESTER = "performance_tester"
    DEPENDENCY_SCANNER = "dependency_scanner"
    CODE_QUALITY = "code_quality"
    AI_ANALYZER = "ai_analyzer"
    DYNAMIC_ANALYZER = "dynamic_analyzer"
    GATEWAY = "gateway"


class AnalysisType(str, Enum):
    """Types of analysis that can be performed."""
    SECURITY_PYTHON = "security_python"
    SECURITY_JAVASCRIPT = "security_javascript"
    DEPENDENCY_PYTHON = "dependency_python"
    DEPENDENCY_NODE = "dependency_node"
    PERFORMANCE_LOAD = "performance_load"
    PERFORMANCE_STRESS = "performance_stress"
    CODE_QUALITY_PYTHON = "code_quality_python"
    CODE_QUALITY_JAVASCRIPT = "code_quality_javascript"
    AI_REQUIREMENTS_CHECK = "ai_requirements_check"
    AI_CODE_REVIEW = "ai_code_review"
    DYNAMIC_SECURITY = "dynamic_security"
    DYNAMIC_VULNERABILITY = "dynamic_vulnerability"


class SeverityLevel(str, Enum):
    """Issue severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INFO = "info"


class AnalysisStatus(str, Enum):
    """Analysis execution status."""
    QUEUED = "queued"
    STARTING = "starting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class WebSocketMessage:
    """Base WebSocket message structure."""
    type: MessageType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service: Optional[ServiceType] = None
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    client_id: Optional[str] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'type': self.type.value,
            'id': self.id,
            'timestamp': self.timestamp.isoformat()
        }
        
        if self.service:
            result['service'] = self.service.value
        if self.data is not None:
            result['data'] = self.data
        if self.client_id:
            result['client_id'] = self.client_id
        if self.correlation_id:
            result['correlation_id'] = self.correlation_id
            
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WebSocketMessage':
        """Create from dictionary."""
        return cls(
            type=MessageType(data['type']),
            id=data.get('id', str(uuid.uuid4())),
            service=ServiceType(data['service']) if data.get('service') else None,
            data=data.get('data'),
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.now(timezone.utc),
            client_id=data.get('client_id'),
            correlation_id=data.get('correlation_id')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class AnalysisRequest:
    """Request for code analysis."""
    model: str
    app_number: int
    analysis_type: AnalysisType
    source_path: str
    options: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 900  # 15 minutes default
    priority: int = 1  # 1=low, 2=normal, 3=high
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'model': self.model,
            'app_number': self.app_number,
            'analysis_type': self.analysis_type.value,
            'source_path': self.source_path,
            'options': self.options,
            'timeout': self.timeout,
            'priority': self.priority
        }


@dataclass
class SecurityAnalysisRequest(AnalysisRequest):
    """Security analysis specific request."""
    tools: List[str] = field(default_factory=lambda: ['bandit', 'safety'])
    scan_depth: str = "standard"  # minimal, standard, thorough
    include_tests: bool = False
    exclude_patterns: List[str] = field(default_factory=list)


@dataclass
class PerformanceTestRequest(AnalysisRequest):
    """Performance testing request."""
    target_url: str = ""
    users: int = 10
    spawn_rate: int = 2
    duration: int = 60  # seconds
    test_scenario: str = "basic_load"


@dataclass
class DependencyAnalysisRequest(AnalysisRequest):
    """Dependency analysis request."""
    package_manager: str = "pip"  # pip, npm, yarn
    check_outdated: bool = True
    security_only: bool = False


@dataclass
class CodeQualityRequest(AnalysisRequest):
    """Code quality analysis request."""
    tools: List[str] = field(default_factory=lambda: ['flake8', 'pylint'])
    fix_issues: bool = False
    style_guide: str = "pep8"


@dataclass
class AIAnalysisRequest(AnalysisRequest):
    """AI-powered analysis request."""
    model_name: str = "mistralai/mistral-small-3.2-24b-instruct"
    analysis_focus: str = "requirements_check"
    requirements: List[str] = field(default_factory=list)
    max_tokens: int = 4000


@dataclass
class AnalysisIssue:
    """Represents a single issue found during analysis."""
    tool: str
    severity: SeverityLevel
    confidence: str
    file_path: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    message: str = ""
    description: str = ""
    rule_id: str = ""
    fix_suggestion: str = ""
    code_snippet: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'tool': self.tool,
            'severity': self.severity.value,
            'confidence': self.confidence,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'column': self.column,
            'message': self.message,
            'description': self.description,
            'rule_id': self.rule_id,
            'fix_suggestion': self.fix_suggestion,
            'code_snippet': self.code_snippet
        }


@dataclass
class ProgressUpdate:
    """Real-time progress update for long-running operations."""
    analysis_id: str
    stage: str  # e.g., "initializing", "scanning", "analyzing", "reporting"
    progress: float  # 0.0 to 1.0
    message: str = ""
    current_file: str = ""
    files_processed: int = 0
    total_files: int = 0
    issues_found: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'analysis_id': self.analysis_id,
            'stage': self.stage,
            'progress': self.progress,
            'message': self.message,
            'current_file': self.current_file,
            'files_processed': self.files_processed,
            'total_files': self.total_files,
            'issues_found': self.issues_found
        }


@dataclass
class AnalysisResult:
    """Results from code analysis."""
    analysis_id: str
    status: AnalysisStatus
    analysis_type: AnalysisType
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None  # seconds
    issues: List[AnalysisIssue] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'analysis_id': self.analysis_id,
            'status': self.status.value,
            'analysis_type': self.analysis_type.value,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.duration,
            'issues': [issue.to_dict() for issue in self.issues],
            'summary': self.summary,
            'metadata': self.metadata,
            'error_message': self.error_message
        }


@dataclass
class SecurityAnalysisResult(AnalysisResult):
    """Security analysis specific results."""
    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    tools_used: List[str] = field(default_factory=list)
    vulnerability_types: Dict[str, int] = field(default_factory=dict)


@dataclass
class PerformanceTestResult(AnalysisResult):
    """Performance testing results."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    min_response_time: float = 0.0
    max_response_time: float = 0.0
    p95_response_time: float = 0.0
    p99_response_time: float = 0.0
    requests_per_second: float = 0.0
    error_rate: float = 0.0
    response_time_distribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class DependencyAnalysisResult(AnalysisResult):
    """Dependency analysis results."""
    total_packages: int = 0
    vulnerable_packages: int = 0
    outdated_packages: int = 0
    package_details: List[Dict[str, Any]] = field(default_factory=list)
    security_advisories: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ServiceRegistration:
    """Service registration information."""
    service_type: ServiceType
    service_id: str
    version: str = "1.0.0"
    capabilities: List[str] = field(default_factory=list)
    health_endpoint: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'service_type': self.service_type.value,
            'service_id': self.service_id,
            'version': self.version,
            'capabilities': self.capabilities,
            'health_endpoint': self.health_endpoint,
            'metrics': self.metrics
        }


@dataclass
class ErrorMessage:
    """Error message structure."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    suggestion: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            'code': self.code,
            'message': self.message
        }
        if self.details:
            result['details'] = self.details
        if self.correlation_id:
            result['correlation_id'] = self.correlation_id
        if self.suggestion:
            result['suggestion'] = self.suggestion
        return result


@dataclass
class HeartbeatMessage:
    """Heartbeat message for connection health."""
    service_id: str
    status: str = "healthy"
    uptime: float = 0.0
    active_analyses: int = 0
    queue_size: int = 0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'service_id': self.service_id,
            'status': self.status,
            'uptime': self.uptime,
            'active_analyses': self.active_analyses,
            'queue_size': self.queue_size,
            'memory_usage': self.memory_usage,
            'cpu_usage': self.cpu_usage
        }


# Message factory functions
def create_analysis_request_message(
    request: AnalysisRequest,
    client_id: str,
    service: ServiceType
) -> WebSocketMessage:
    """Create an analysis request message."""
    return WebSocketMessage(
        type=MessageType.ANALYSIS_REQUEST,
        service=service,
        data=request.to_dict(),
        client_id=client_id
    )


def create_progress_update_message(
    analysis_id: str,
    stage: str,
    progress: float,
    message: str = "",
    client_id: Optional[str] = None,
    **kwargs
) -> WebSocketMessage:
    """Create a progress update message."""
    progress_update = ProgressUpdate(
        analysis_id=analysis_id,
        stage=stage,
        progress=progress,
        message=message,
        **kwargs
    )
    
    return WebSocketMessage(
        type=MessageType.PROGRESS_UPDATE,
        data=progress_update.to_dict(),
        client_id=client_id,
        correlation_id=analysis_id
    )


def create_result_message(
    result: AnalysisResult,
    client_id: Optional[str] = None
) -> WebSocketMessage:
    """Create an analysis result message."""
    return WebSocketMessage(
        type=MessageType.ANALYSIS_RESULT,
        data=result.to_dict(),
        client_id=client_id,
        correlation_id=result.analysis_id
    )


def create_error_message(
    code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    client_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    suggestion: Optional[str] = None
) -> WebSocketMessage:
    """Create an error message."""
    error = ErrorMessage(
        code=code,
        message=message,
        details=details,
        correlation_id=correlation_id,
        suggestion=suggestion
    )
    
    return WebSocketMessage(
        type=MessageType.ERROR,
        data=error.to_dict(),
        client_id=client_id,
        correlation_id=correlation_id
    )


def create_heartbeat_message(
    service_id: str,
    status: str = "healthy",
    **metrics
) -> WebSocketMessage:
    """Create a heartbeat message."""
    heartbeat = HeartbeatMessage(
        service_id=service_id,
        status=status,
        **metrics
    )
    
    return WebSocketMessage(
        type=MessageType.HEARTBEAT,
        data=heartbeat.to_dict()
    )


# Utility functions
def route_message_to_service(message: WebSocketMessage) -> ServiceType:
    """Determine which service should handle a message."""
    if message.service:
        return message.service
    
    # Auto-route based on message content
    if message.type == MessageType.ANALYSIS_REQUEST and message.data:
        analysis_type = message.data.get('analysis_type', '')
        
        if analysis_type.startswith('security_'):
            return ServiceType.SECURITY_ANALYZER
        elif analysis_type.startswith('performance_'):
            return ServiceType.PERFORMANCE_TESTER
        elif analysis_type.startswith('dependency_'):
            return ServiceType.DEPENDENCY_SCANNER
        elif analysis_type.startswith('code_quality_'):
            return ServiceType.CODE_QUALITY
        elif analysis_type.startswith('ai_'):
            return ServiceType.AI_ANALYZER
        elif analysis_type.startswith('dynamic_'):
            return ServiceType.DYNAMIC_ANALYZER
    
    # Default to gateway for routing
    return ServiceType.GATEWAY


def validate_message(message_dict: Dict[str, Any]) -> bool:
    """Validate WebSocket message structure."""
    required_fields = ['type', 'id', 'timestamp']
    
    for required_field in required_fields:
        if required_field not in message_dict:
            return False
    
    try:
        MessageType(message_dict['type'])
    except ValueError:
        return False
    
    return True


def create_request_from_dict(data: Dict[str, Any]) -> AnalysisRequest:
    """Create appropriate request object from dictionary."""
    analysis_type = AnalysisType(data['analysis_type'])
    
    if analysis_type.name.startswith('SECURITY_'):
        return SecurityAnalysisRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1),
            tools=data.get('tools', ['bandit', 'safety']),
            scan_depth=data.get('scan_depth', 'standard'),
            include_tests=data.get('include_tests', False),
            exclude_patterns=data.get('exclude_patterns', [])
        )
    elif analysis_type.name.startswith('PERFORMANCE_'):
        return PerformanceTestRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1),
            target_url=data.get('target_url', ''),
            users=data.get('users', 10),
            spawn_rate=data.get('spawn_rate', 2),
            duration=data.get('duration', 60),
            test_scenario=data.get('test_scenario', 'basic_load')
        )
    elif analysis_type.name.startswith('DEPENDENCY_'):
        return DependencyAnalysisRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1),
            package_manager=data.get('package_manager', 'pip'),
            check_outdated=data.get('check_outdated', True),
            security_only=data.get('security_only', False)
        )
    elif analysis_type.name.startswith('CODE_QUALITY_'):
        return CodeQualityRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1),
            tools=data.get('tools', ['flake8', 'pylint']),
            fix_issues=data.get('fix_issues', False),
            style_guide=data.get('style_guide', 'pep8')
        )
    elif analysis_type.name.startswith('AI_'):
        return AIAnalysisRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1),
            model_name=data.get('model_name', 'mistralai/mistral-small-3.2-24b-instruct'),
            analysis_focus=data.get('analysis_focus', 'requirements_check'),
            requirements=data.get('requirements', []),
            max_tokens=data.get('max_tokens', 4000)
        )
    else:
        # Base request type
        return AnalysisRequest(
            model=data['model'],
            app_number=data['app_number'],
            analysis_type=analysis_type,
            source_path=data['source_path'],
            options=data.get('options', {}),
            timeout=data.get('timeout', 300),
            priority=data.get('priority', 1)
        )
