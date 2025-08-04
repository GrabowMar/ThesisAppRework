"""
Local Testing Models
===================

Simplified models for manage.py to avoid import issues.
These are lightweight models focused on the testing infrastructure needs.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from datetime import datetime


class TestType(Enum):
    """Type of test to run."""
    SECURITY_BACKEND = "security_backend"
    SECURITY_FRONTEND = "security_frontend" 
    SECURITY_ZAP = "security_zap"
    PERFORMANCE = "performance"
    AI_ANALYSIS = "ai_analysis"


class TestingStatus(Enum):
    """Status of test execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ServiceHealth:
    """Health status of a testing service."""
    service_name: str
    status: str
    port: int
    endpoint: str
    last_check: datetime
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['last_check'] = self.last_check.isoformat()
        return data


@dataclass
class TestRequest:
    """Basic test request structure."""
    test_type: TestType
    app_path: str
    model_name: str
    app_number: int
    test_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['test_type'] = self.test_type.value
        return data


@dataclass
class TestResult:
    """Basic test result structure."""
    test_id: str
    test_type: TestType
    status: TestingStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['test_type'] = self.test_type.value
        data['status'] = self.status.value
        data['started_at'] = self.started_at.isoformat()
        if self.completed_at:
            data['completed_at'] = self.completed_at.isoformat()
        return data


class LocalTestingAPIClient:
    """Simplified testing API client for infrastructure management."""
    
    def __init__(self, base_url: str = "http://localhost", timeout: int = 300):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        
        # Service endpoints
        self.endpoints = {
            TestType.SECURITY_BACKEND: f"{base_url}:8001",
            TestType.SECURITY_FRONTEND: f"{base_url}:8001", 
            TestType.SECURITY_ZAP: f"{base_url}:8003",
            TestType.PERFORMANCE: f"{base_url}:8002",
            TestType.AI_ANALYSIS: f"{base_url}:8004",
        }
    
    def get_service_endpoint(self, test_type: TestType) -> str:
        """Get the endpoint for a specific test type."""
        return self.endpoints.get(test_type, f"{self.base_url}:8000")
    
    def get_health_endpoint(self, test_type: TestType) -> str:
        """Get the health check endpoint for a service."""
        base_endpoint = self.get_service_endpoint(test_type)
        return f"{base_endpoint}/health"
    
    def create_test_request(self, test_type: TestType, app_path: str, 
                          model_name: str, app_number: int) -> TestRequest:
        """Create a test request object."""
        return TestRequest(
            test_type=test_type,
            app_path=app_path,
            model_name=model_name,
            app_number=app_number
        )
    
    def health_check(self) -> Dict[str, bool]:
        """Check health of all testing services."""
        health_status = {}
        for test_type in TestType:
            try:
                import requests
                endpoint = self.get_health_endpoint(test_type)
                response = requests.get(endpoint, timeout=5)
                health_status[test_type.value] = response.status_code == 200
            except Exception:
                health_status[test_type.value] = False
        return health_status
    
    def run_security_analysis(self, model_name: str, app_number: int, tools: List[str]) -> Dict[str, Any]:
        """Run security analysis (placeholder for infrastructure management)."""
        return {
            "test_id": f"security_{model_name}_app{app_number}_{int(datetime.now().timestamp())}",
            "status": "initiated",
            "model_name": model_name,
            "app_number": app_number,
            "tools": tools,
            "message": "Security analysis initiated via infrastructure manager"
        }
    
    def run_performance_test(self, model_name: str, app_number: int, target_url: str, duration: int) -> Dict[str, Any]:
        """Run performance test (placeholder for infrastructure management)."""
        return {
            "test_id": f"performance_{model_name}_app{app_number}_{int(datetime.now().timestamp())}",
            "status": "initiated",
            "model_name": model_name,
            "app_number": app_number,
            "target_url": target_url,
            "duration": duration,
            "message": "Performance test initiated via infrastructure manager"
        }
    
    def run_zap_scan(self, model_name: str, app_number: int, target_url: str, scan_type: str) -> Dict[str, Any]:
        """Run ZAP security scan (placeholder for infrastructure management)."""
        return {
            "test_id": f"zap_{model_name}_app{app_number}_{int(datetime.now().timestamp())}",
            "status": "initiated",
            "model_name": model_name,
            "app_number": app_number,
            "target_url": target_url,
            "scan_type": scan_type,
            "message": "ZAP scan initiated via infrastructure manager"
        }
