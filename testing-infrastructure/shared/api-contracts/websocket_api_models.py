"""
WebSocket Message Protocol and Data Models
==========================================

Extended API models for WebSocket-based communication.
Maintains compatibility with existing TestRequest/TestResult models
while adding real-time messaging capabilities.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import json
import uuid

# Import existing models for compatibility
from .testing_api_models import (
    TestRequest, TestResult,
    SecurityTestRequest, PerformanceTestRequest, ZapTestRequest, AIAnalysisRequest
)


class MessageType(str, Enum):
    """WebSocket message types."""
    # Request types
    TEST_REQUEST = "test_request"
    BATCH_REQUEST = "batch_request"
    STATUS_REQUEST = "status_request"
    CANCEL_REQUEST = "cancel_request"
    
    # Response types
    TEST_RESULT = "test_result"
    BATCH_RESULT = "batch_result"
    STATUS_UPDATE = "status_update"
    PROGRESS_UPDATE = "progress_update"
    
    # System messages
    ERROR = "error"
    HEARTBEAT = "heartbeat"
    CONNECTION_ACK = "connection_ack"
    SERVICE_REGISTER = "service_register"
    SERVICE_UNREGISTER = "service_unregister"


class ServiceType(str, Enum):
    """Available testing services."""
    SECURITY_SCANNER = "security_scanner"
    PERFORMANCE_TESTER = "performance_tester"
    ZAP_SCANNER = "zap_scanner"
    AI_ANALYZER = "ai_analyzer"
    TEST_COORDINATOR = "test_coordinator"


@dataclass
class WebSocketMessage:
    """Base WebSocket message structure."""
    type: MessageType
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service: Optional[ServiceType] = None
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    client_id: Optional[str] = None
    correlation_id: Optional[str] = None  # For request/response correlation
    
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
            if hasattr(self.data, 'to_dict'):
                result['data'] = self.data.to_dict()
            else:
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
            timestamp=datetime.fromisoformat(data['timestamp']) if 'timestamp' in data else datetime.utcnow(),
            client_id=data.get('client_id'),
            correlation_id=data.get('correlation_id')
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'WebSocketMessage':
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


@dataclass
class ProgressUpdate:
    """Progress update for long-running operations."""
    test_id: str
    stage: str  # e.g., "initialization", "scanning", "analysis", "reporting"
    progress: float  # 0.0 to 1.0
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_id': self.test_id,
            'stage': self.stage,
            'progress': self.progress,
            'message': self.message,
            'details': self.details
        }


@dataclass
class ServiceRegistration:
    """Service registration information."""
    service_type: ServiceType
    service_id: str
    capabilities: List[str] = field(default_factory=list)
    health_endpoint: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'service_type': self.service_type.value,
            'service_id': self.service_id,
            'capabilities': self.capabilities,
            'health_endpoint': self.health_endpoint,
            'metadata': self.metadata
        }


@dataclass
class ErrorMessage:
    """Error message structure."""
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'code': self.code,
            'message': self.message
        }
        if self.details:
            result['details'] = self.details
        if self.correlation_id:
            result['correlation_id'] = self.correlation_id
        return result


@dataclass
class HeartbeatMessage:
    """Heartbeat message for connection health."""
    service_id: str
    status: str = "healthy"
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'service_id': self.service_id,
            'status': self.status,
            'metrics': self.metrics
        }


# WebSocket-specific request wrappers
@dataclass
class WebSocketTestRequest:
    """WebSocket wrapper for test requests."""
    request: TestRequest
    callback_client_id: str
    priority: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            'callback_client_id': self.callback_client_id,
            'priority': self.priority
        }
        
        if hasattr(self.request, 'to_dict'):
            result['request'] = self.request.to_dict()
        else:
            # Handle dataclass serialization
            result['request'] = {
                'model': self.request.model,
                'app_num': self.request.app_num,
                'test_type': self.request.test_type.value,
                'options': self.request.options,
                'timeout': self.request.timeout,
                'priority': self.request.priority
            }
            
            # Add specific fields based on request type
            if isinstance(self.request, SecurityTestRequest):
                result['request'].update({
                    'tools': self.request.tools,
                    'scan_depth': self.request.scan_depth,
                    'include_dependencies': self.request.include_dependencies
                })
            elif isinstance(self.request, PerformanceTestRequest):
                result['request'].update({
                    'users': self.request.users,
                    'spawn_rate': self.request.spawn_rate,
                    'duration': self.request.duration,
                    'target_url': self.request.target_url
                })
            elif isinstance(self.request, ZapTestRequest):
                result['request'].update({
                    'scan_type': self.request.scan_type,
                    'target_url': self.request.target_url,
                    'authentication': self.request.authentication
                })
            elif isinstance(self.request, AIAnalysisRequest):
                result['request'].update({
                    'model_name': self.request.model_name,
                    'analysis_type': self.request.analysis_type,
                    'requirements': self.request.requirements
                })
        
        return result


# Message factory functions
def create_test_request_message(
    test_request: TestRequest,
    client_id: str,
    service: ServiceType
) -> WebSocketMessage:
    """Create a test request message."""
    ws_request = WebSocketTestRequest(
        request=test_request,
        callback_client_id=client_id
    )
    
    return WebSocketMessage(
        type=MessageType.TEST_REQUEST,
        service=service,
        data=ws_request.to_dict(),
        client_id=client_id
    )


def create_progress_update_message(
    test_id: str,
    stage: str,
    progress: float,
    message: str = "",
    client_id: str = None
) -> WebSocketMessage:
    """Create a progress update message."""
    progress_update = ProgressUpdate(
        test_id=test_id,
        stage=stage,
        progress=progress,
        message=message
    )
    
    return WebSocketMessage(
        type=MessageType.PROGRESS_UPDATE,
        data=progress_update.to_dict(),
        client_id=client_id,
        correlation_id=test_id
    )


def create_result_message(
    test_result: TestResult,
    client_id: str = None
) -> WebSocketMessage:
    """Create a test result message."""
    return WebSocketMessage(
        type=MessageType.TEST_RESULT,
        data=test_result.to_dict(),
        client_id=client_id,
        correlation_id=test_result.test_id
    )


def create_error_message(
    code: str,
    message: str,
    details: Dict[str, Any] = None,
    client_id: str = None,
    correlation_id: str = None
) -> WebSocketMessage:
    """Create an error message."""
    error = ErrorMessage(
        code=code,
        message=message,
        details=details,
        correlation_id=correlation_id
    )
    
    return WebSocketMessage(
        type=MessageType.ERROR,
        data=error.to_dict(),
        client_id=client_id,
        correlation_id=correlation_id
    )


def create_heartbeat_message(service_id: str, metrics: Dict[str, Any] = None) -> WebSocketMessage:
    """Create a heartbeat message."""
    heartbeat = HeartbeatMessage(
        service_id=service_id,
        metrics=metrics or {}
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
    if message.type == MessageType.TEST_REQUEST and message.data:
        request_data = message.data.get('request', {})
        test_type = request_data.get('test_type', '')
        
        if test_type in ['security_backend', 'security_frontend']:
            return ServiceType.SECURITY_SCANNER
        elif test_type == 'security_zap':
            return ServiceType.ZAP_SCANNER
        elif test_type == 'performance':
            return ServiceType.PERFORMANCE_TESTER
        elif test_type == 'ai_analysis':
            return ServiceType.AI_ANALYZER
        elif test_type == 'code_quality':
            return ServiceType.SECURITY_SCANNER  # Can handle code quality
    
    # Default to coordinator for complex routing
    return ServiceType.TEST_COORDINATOR


def validate_websocket_message(message_dict: Dict[str, Any]) -> bool:
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
