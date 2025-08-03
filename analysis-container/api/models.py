"""
Analysis Container Models
========================

Pydantic models for the analysis container API.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """Analysis status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolType(str, Enum):
    """Available analysis tool types."""
    # Security Tools
    BANDIT = "bandit"
    SAFETY = "safety"
    SEMGREP = "semgrep"
    ESLINT = "eslint"
    RETIRE_JS = "retire_js"
    SNYK = "snyk"
    TRUFFLEHOG = "trufflehog"
    
    # Performance Tools
    LOCUST = "locust"
    LIGHTHOUSE = "lighthouse"
    
    # Code Quality Tools
    FLAKE8 = "flake8"
    PYLINT = "pylint"
    MYPY = "mypy"
    SONARQUBE = "sonarqube"
    
    # Container Tools
    DOCKER_SCAN = "docker_scan"
    TRIVY = "trivy"
    
    # Web Security Tools
    ZAP = "zap"
    NIKTO = "nikto"


class AnalysisRequest(BaseModel):
    """Base analysis request model."""
    target_path: str
    tools: List[ToolType] = Field(default_factory=list)
    options: Dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    """Result from a single tool execution."""
    tool: ToolType
    status: AnalysisStatus
    duration: float
    output: Dict[str, Any]
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    """Complete analysis result."""
    analysis_id: str
    status: AnalysisStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration: Optional[float] = None
    tool_results: List[ToolResult] = Field(default_factory=list)
    summary: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class SecurityFinding(BaseModel):
    """Security analysis finding."""
    severity: str  # high, medium, low, info
    title: str
    description: str
    file_path: str
    line_number: Optional[int] = None
    cwe_id: Optional[str] = None
    rule_id: Optional[str] = None
    tool: str
    confidence: Optional[str] = None


class PerformanceMetric(BaseModel):
    """Performance analysis metric."""
    metric_name: str
    value: float
    unit: str
    timestamp: datetime
    context: Dict[str, Any] = Field(default_factory=dict)


class CodeQualityIssue(BaseModel):
    """Code quality issue."""
    severity: str  # error, warning, info
    message: str
    file_path: str
    line_number: Optional[int] = None
    column: Optional[int] = None
    rule: Optional[str] = None
    tool: str


class ContainerVulnerability(BaseModel):
    """Container vulnerability finding."""
    vulnerability_id: str
    severity: str
    title: str
    description: str
    package_name: str
    installed_version: str
    fixed_version: Optional[str] = None
    references: List[str] = Field(default_factory=list)
