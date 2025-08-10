"""
Database Models for Thesis Research App

This module defines SQLAlchemy models for the thesis research application
that analyzes AI-generated applications across multiple models.

Models include:
- ModelCapability: AI model metadata and capabilities
- PortConfiguration: Docker port allocations
- GeneratedApplication: AI-generated app instances
- SecurityAnalysis: Security analysis results
- PerformanceTest: Performance testing results
- BatchAnalysis: Batch processing records
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, List

# Import centralized constants and enums
from ..constants import AnalysisStatus, JobStatus, ContainerState
from ..extensions import db

def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)

class ModelCapability(db.Model):
    """Model for storing AI model capabilities and metadata."""
    __tablename__ = 'model_capabilities'
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    canonical_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    provider = db.Column(db.String(100), nullable=False, index=True)
    model_name = db.Column(db.String(200), nullable=False)
    
    # Capabilities
    is_free = db.Column(db.Boolean, default=False)
    context_window = db.Column(db.Integer, default=0)
    max_output_tokens = db.Column(db.Integer, default=0)
    supports_function_calling = db.Column(db.Boolean, default=False)
    supports_vision = db.Column(db.Boolean, default=False)
    supports_streaming = db.Column(db.Boolean, default=False)
    supports_json_mode = db.Column(db.Boolean, default=False)
    
    # Pricing
    input_price_per_token = db.Column(db.Float, default=0.0)
    output_price_per_token = db.Column(db.Float, default=0.0)
    
    # Performance metrics
    cost_efficiency = db.Column(db.Float, default=0.0)
    safety_score = db.Column(db.Float, default=0.0)
    
    # JSON fields for detailed data
    capabilities_json = db.Column(db.Text)  # Detailed capabilities
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get capabilities as dictionary."""
        if self.capabilities_json:
            try:
                return json.loads(self.capabilities_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_capabilities(self, capabilities_dict: Dict[str, Any]) -> None:
        """Set capabilities from dictionary."""
        self.capabilities_json = json.dumps(capabilities_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'canonical_slug': self.canonical_slug,
            'provider': self.provider,
            'model_name': self.model_name,
            'is_free': self.is_free,
            'context_window': self.context_window,
            'max_output_tokens': self.max_output_tokens,
            'supports_function_calling': self.supports_function_calling,
            'supports_vision': self.supports_vision,
            'supports_streaming': self.supports_streaming,
            'supports_json_mode': self.supports_json_mode,
            'input_price_per_token': self.input_price_per_token,
            'output_price_per_token': self.output_price_per_token,
            'cost_efficiency': self.cost_efficiency,
            'safety_score': self.safety_score,
            'capabilities': self.get_capabilities(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ModelCapability {self.model_id}>'


class PortConfiguration(db.Model):
    """Model for storing Docker port configurations."""
    __tablename__ = 'port_configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(200), nullable=False, index=True)  # Model name/ID
    app_num = db.Column(db.Integer, nullable=False, index=True)    # App number
    frontend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    backend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    is_available = db.Column(db.Boolean, default=True, index=True)
    
    # JSON field for additional metadata
    metadata_json = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Unique constraint for model + app combination
    __table_args__ = (db.UniqueConstraint('model', 'app_num', name='unique_model_app_port'),)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model': self.model,
            'app_num': self.app_num,
            'frontend_port': self.frontend_port,
            'backend_port': self.backend_port,
            'is_available': self.is_available,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<PortConfiguration {self.model}/app{self.app_num}>'


class GeneratedApplication(db.Model):
    """Model for storing information about AI-generated applications."""
    __tablename__ = 'generated_applications'
    
    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), nullable=False, index=True)
    app_number = db.Column(db.Integer, nullable=False)
    app_type = db.Column(db.String(50), nullable=False)
    provider = db.Column(db.String(100), nullable=False, index=True)  # Added provider field
    generation_status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    has_backend = db.Column(db.Boolean, default=False)
    has_frontend = db.Column(db.Boolean, default=False)
    has_docker_compose = db.Column(db.Boolean, default=False)
    backend_framework = db.Column(db.String(50))
    frontend_framework = db.Column(db.String(50))
    container_status = db.Column(db.String(50), default='stopped')
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    updated_at = db.Column(db.DateTime, default=db.func.current_timestamp(), 
                          onupdate=db.func.current_timestamp())
    
    # Relationships
    security_analyses = db.relationship('SecurityAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    performance_tests = db.relationship('PerformanceTest', backref='application', lazy=True, cascade='all, delete-orphan')
    zap_analyses = db.relationship('ZAPAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    openrouter_analyses = db.relationship('OpenRouterAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    
    # Unique constraint
    __table_args__ = (db.UniqueConstraint('model_slug', 'app_number', name='unique_model_app'),)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def get_directory_path(self) -> str:
        """Get the directory path for this application."""
        return f"{self.model_slug}/app_{self.app_number}"
    
    def get_ports(self) -> Dict[str, Any]:
        """Get port configuration for this application."""
        return {}  # Implement based on port configuration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'app_type': self.app_type,
            'provider': self.provider,
            'generation_status': self.generation_status.value if self.generation_status else None,
            'has_backend': self.has_backend,
            'has_frontend': self.has_frontend,
            'has_docker_compose': self.has_docker_compose,
            'backend_framework': self.backend_framework,
            'frontend_framework': self.frontend_framework,
            'container_status': self.container_status,
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<GeneratedApplication {self.model_slug}/app{self.app_number}>'


class SecurityAnalysis(db.Model):
    """Model for storing security analysis results."""
    __tablename__ = 'security_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis status and configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    
    # Tool enablement
    bandit_enabled = db.Column(db.Boolean, default=True)
    safety_enabled = db.Column(db.Boolean, default=True)
    pylint_enabled = db.Column(db.Boolean, default=True)
    eslint_enabled = db.Column(db.Boolean, default=True)
    npm_audit_enabled = db.Column(db.Boolean, default=True)
    snyk_enabled = db.Column(db.Boolean, default=False)
    
    # Results summary
    total_issues = db.Column(db.Integer, default=0)
    critical_severity_count = db.Column(db.Integer, default=0)
    high_severity_count = db.Column(db.Integer, default=0)
    medium_severity_count = db.Column(db.Integer, default=0)
    low_severity_count = db.Column(db.Integer, default=0)
    
    # Performance metrics
    analysis_duration = db.Column(db.Float)  # Duration in seconds
    
    # JSON field for detailed results
    results_json = db.Column(db.Text)       # Detailed analysis results
    metadata_json = db.Column(db.Text)      # Analysis metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self) -> Dict[str, Any]:
        """Get results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict: Dict[str, Any]) -> None:
        """Set results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'bandit_enabled': self.bandit_enabled,
            'safety_enabled': self.safety_enabled,
            'pylint_enabled': self.pylint_enabled,
            'eslint_enabled': self.eslint_enabled,
            'npm_audit_enabled': self.npm_audit_enabled,
            'snyk_enabled': self.snyk_enabled,
            'total_issues': self.total_issues,
            'critical_severity_count': self.critical_severity_count,
            'high_severity_count': self.high_severity_count,
            'medium_severity_count': self.medium_severity_count,
            'low_severity_count': self.low_severity_count,
            'analysis_duration': self.analysis_duration,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<SecurityAnalysis {self.id}>'


class PerformanceTest(db.Model):
    """Model for storing performance test results."""
    __tablename__ = 'performance_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Test configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    test_type = db.Column(db.String(50), default='load')  # load, stress, spike
    users = db.Column(db.Integer, default=10)
    spawn_rate = db.Column(db.Float, default=1.0)
    test_duration = db.Column(db.Integer, default=60)  # seconds
    
    # Results
    requests_per_second = db.Column(db.Float)
    average_response_time = db.Column(db.Float)  # milliseconds
    p95_response_time = db.Column(db.Float)
    p99_response_time = db.Column(db.Float)
    error_rate = db.Column(db.Float)  # percentage
    total_requests = db.Column(db.Integer)
    failed_requests = db.Column(db.Integer)
    
    # JSON fields
    results_json = db.Column(db.Text)       # Detailed test results
    metadata_json = db.Column(db.Text)      # Test metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self) -> Dict[str, Any]:
        """Get results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict: Dict[str, Any]) -> None:
        """Set results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'test_type': self.test_type,
            'users': self.users,
            'spawn_rate': self.spawn_rate,
            'test_duration': self.test_duration,
            'requests_per_second': self.requests_per_second,
            'average_response_time': self.average_response_time,
            'p95_response_time': self.p95_response_time,
            'p99_response_time': self.p99_response_time,
            'error_rate': self.error_rate,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<PerformanceTest {self.id}>'


class ZAPAnalysis(db.Model):
    """Model for storing ZAP security analysis results."""
    __tablename__ = 'zap_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # ZAP specific configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    target_url = db.Column(db.String(500), nullable=False)
    scan_type = db.Column(db.String(50), default='active')  # active, passive, spider
    
    # Results summary
    high_risk_alerts = db.Column(db.Integer, default=0)
    medium_risk_alerts = db.Column(db.Integer, default=0)
    low_risk_alerts = db.Column(db.Integer, default=0)
    informational_alerts = db.Column(db.Integer, default=0)
    
    # JSON fields
    zap_report_json = db.Column(db.Text)    # Full ZAP report
    metadata_json = db.Column(db.Text)      # Scan metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_zap_report(self) -> Dict[str, Any]:
        """Get ZAP report as dictionary."""
        if self.zap_report_json:
            try:
                return json.loads(self.zap_report_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_zap_report(self, report_dict: Dict[str, Any]) -> None:
        """Set ZAP report from dictionary."""
        self.zap_report_json = json.dumps(report_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'target_url': self.target_url,
            'scan_type': self.scan_type,
            'high_risk_alerts': self.high_risk_alerts,
            'medium_risk_alerts': self.medium_risk_alerts,
            'low_risk_alerts': self.low_risk_alerts,
            'informational_alerts': self.informational_alerts,
            'zap_report': self.get_zap_report(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ZAPAnalysis {self.id}>'


class OpenRouterAnalysis(db.Model):
    """Model for storing OpenRouter AI analysis results."""
    __tablename__ = 'openrouter_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    analyzer_model = db.Column(db.String(200))  # Which AI model was used
    analysis_prompt = db.Column(db.Text)
    
    # Results
    overall_score = db.Column(db.Float)  # 0-100
    code_quality_score = db.Column(db.Float)
    security_score = db.Column(db.Float)
    maintainability_score = db.Column(db.Float)
    
    # Token usage and cost
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    cost_usd = db.Column(db.Float)
    
    # JSON fields
    findings_json = db.Column(db.Text)      # Structured findings
    recommendations_json = db.Column(db.Text)  # AI recommendations
    summary = db.Column(db.Text)            # Analysis summary
    metadata_json = db.Column(db.Text)      # Analysis metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_findings(self) -> Dict[str, Any]:
        """Get findings as dictionary."""
        if self.findings_json:
            try:
                return json.loads(self.findings_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_findings(self, findings_dict: Dict[str, Any]) -> None:
        """Set findings from dictionary."""
        self.findings_json = json.dumps(findings_dict)
    
    def get_recommendations(self) -> List[str]:
        """Get recommendations as list."""
        if self.recommendations_json:
            try:
                return json.loads(self.recommendations_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_recommendations(self, recommendations_list: List[str]) -> None:
        """Set recommendations from list."""
        self.recommendations_json = json.dumps(recommendations_list)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'analyzer_model': self.analyzer_model,
            'analysis_prompt': self.analysis_prompt,
            'overall_score': self.overall_score,
            'code_quality_score': self.code_quality_score,
            'security_score': self.security_score,
            'maintainability_score': self.maintainability_score,
            'input_tokens': self.input_tokens,
            'output_tokens': self.output_tokens,
            'cost_usd': self.cost_usd,
            'findings': self.get_findings(),
            'recommendations': self.get_recommendations(),
            'summary': self.summary,
            'metadata': self.get_metadata(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<OpenRouterAnalysis {self.id}>'


class ContainerizedTest(db.Model):
    """Model for tracking containerized test services."""
    __tablename__ = 'containerized_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    container_name = db.Column(db.String(200), unique=True, nullable=False, index=True)
    service_type = db.Column(db.String(100), nullable=False)  # security, performance, zap
    
    # Container information
    container_id = db.Column(db.String(100))
    image_name = db.Column(db.String(200))
    port = db.Column(db.Integer)
    status = db.Column(db.String(50), default=ContainerState.STOPPED.value)
    
    # Health monitoring
    last_health_check = db.Column(db.DateTime)
    health_status = db.Column(db.String(50))  # healthy, unhealthy, unknown
    
    # Usage statistics
    total_requests = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    # JSON fields
    config_json = db.Column(db.Text)        # Container configuration
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration from dictionary."""
        self.config_json = json.dumps(config_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'container_name': self.container_name,
            'service_type': self.service_type,
            'container_id': self.container_id,
            'image_name': self.image_name,
            'port': self.port,
            'status': self.status,
            'last_health_check': self.last_health_check,
            'health_status': self.health_status,
            'total_requests': self.total_requests,
            'last_used': self.last_used,
            'config': self.get_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ContainerizedTest {self.container_name}>'


class BatchAnalysis(db.Model):
    """Model for tracking batch analysis jobs."""
    __tablename__ = 'batch_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Job configuration
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING, index=True)
    analysis_types = db.Column(db.Text)     # JSON array of analysis types
    
    # Progress tracking
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    failed_tasks = db.Column(db.Integer, default=0)
    progress_percentage = db.Column(db.Float, default=0.0)
    
    # Configuration filters
    model_filter = db.Column(db.Text)       # JSON array of model patterns
    app_filter = db.Column(db.Text)         # JSON array of app number patterns
    
    # Results summary
    results_summary = db.Column(db.Text)    # JSON summary of results
    
    # Timing
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    estimated_completion = db.Column(db.DateTime)
    
    # JSON fields
    config_json = db.Column(db.Text)        # Full job configuration
    metadata_json = db.Column(db.Text)      # Job metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_analysis_types(self) -> List[str]:
        """Get analysis types as list."""
        if self.analysis_types:
            try:
                return json.loads(self.analysis_types)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_analysis_types(self, types_list: List[str]) -> None:
        """Set analysis types from list."""
        self.analysis_types = json.dumps(types_list)
    
    def get_model_filter(self) -> List[str]:
        """Get model filter as list."""
        if self.model_filter:
            try:
                return json.loads(self.model_filter)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_model_filter(self, filter_list: List[str]) -> None:
        """Set model filter from list."""
        self.model_filter = json.dumps(filter_list)
    
    def get_app_filter(self) -> List[int]:
        """Get app filter as list."""
        if self.app_filter:
            try:
                return json.loads(self.app_filter)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_app_filter(self, filter_list: List[int]) -> None:
        """Set app filter from list."""
        self.app_filter = json.dumps(filter_list)
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get results summary as dictionary."""
        if self.results_summary:
            try:
                return json.loads(self.results_summary)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results_summary(self, summary_dict: Dict[str, Any]) -> None:
        """Set results summary from dictionary."""
        self.results_summary = json.dumps(summary_dict)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration from dictionary."""
        self.config_json = json.dumps(config_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def update_progress(self) -> None:
        """Update progress percentage based on task counts."""
        if self.total_tasks > 0:
            self.progress_percentage = (self.completed_tasks / self.total_tasks) * 100.0
        else:
            self.progress_percentage = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'batch_id': self.batch_id,
            'status': self.status.value if self.status else None,
            'analysis_types': self.get_analysis_types(),
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'progress_percentage': self.progress_percentage,
            'model_filter': self.get_model_filter(),
            'app_filter': self.get_app_filter(),
            'results_summary': self.get_results_summary(),
            'started_at': self.started_at,
            'completed_at': self.completed_at,
            'estimated_completion': self.estimated_completion,
            'config': self.get_config(),
            'metadata': self.get_metadata(),
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<BatchAnalysis {self.batch_id}>'


# Initialize database function
def init_db():
    """Create all database tables."""
    db.create_all()

# Export all models for easy import
__all__ = [
    'db',
    'utc_now',
    'init_db',
    'ModelCapability',
    'PortConfiguration', 
    'GeneratedApplication',
    'SecurityAnalysis',
    'PerformanceTest',
    'ZAPAnalysis',
    'OpenRouterAnalysis',
    'ContainerizedTest',
    'BatchAnalysis'
]
