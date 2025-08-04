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
import enum
from datetime import datetime, timezone, timedelta

try:
    from .extensions import db
except ImportError:
    from extensions import db

def utc_now():
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)

class AnalysisStatus(enum.Enum):
    """Status enum for analyses and tests."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobStatus(enum.Enum):
    """Status enum for batch jobs."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"

class TaskStatus(enum.Enum):
    """Status enum for batch tasks."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

class JobPriority(enum.Enum):
    """Priority levels for batch jobs."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class AnalysisType(enum.Enum):
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

class SeverityLevel(enum.Enum):
    """Severity levels for security issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

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
    
    def get_capabilities(self):
        """Get capabilities as dictionary."""
        if self.capabilities_json:
            try:
                return json.loads(self.capabilities_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_capabilities(self, capabilities_dict):
        """Set capabilities from dictionary."""
        self.capabilities_json = json.dumps(capabilities_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
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
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
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
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'frontend_port': self.frontend_port,
            'backend_port': self.backend_port,
            'is_available': self.is_available,
            'metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<PortConfiguration frontend:{self.frontend_port} backend:{self.backend_port}>'

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
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def get_directory_path(self):
        """Get the directory path for this application."""
        metadata = self.get_metadata()
        return metadata.get('directory_path', f"misc/models/{self.model_slug}/app{self.app_number}")
    
    def get_ports(self):
        """Get port configuration for this application."""
        metadata = self.get_metadata()
        return metadata.get('ports', {})
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'app_type': self.app_type,
            'provider': self.provider,
            'generation_status': self.generation_status,
            'has_backend': self.has_backend,
            'has_frontend': self.has_frontend,
            'has_docker_compose': self.has_docker_compose,
            'backend_framework': self.backend_framework,
            'frontend_framework': self.frontend_framework,
            'container_status': self.container_status,
            'metadata': self.get_metadata(),
            'directory_path': self.get_directory_path(),
            'ports': self.get_ports(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
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
    
    def get_enabled_tools(self):
        """Get dictionary of enabled analysis tools."""
        return {
            'bandit': self.bandit_enabled,
            'safety': self.safety_enabled,
            'pylint': self.pylint_enabled,
            'eslint': self.eslint_enabled,
            'npm_audit': self.npm_audit_enabled,
            'snyk': self.snyk_enabled
        }
    
    def set_enabled_tools(self, tools_dict):
        """Set enabled tools from dictionary."""
        self.bandit_enabled = tools_dict.get('bandit', False)
        self.safety_enabled = tools_dict.get('safety', False)
        self.pylint_enabled = tools_dict.get('pylint', False)
        self.eslint_enabled = tools_dict.get('eslint', False)
        self.npm_audit_enabled = tools_dict.get('npm_audit', False)
        self.snyk_enabled = tools_dict.get('snyk', False)
    
    def get_results(self):
        """Get analysis results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set analysis results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'enabled_tools': self.get_enabled_tools(),
            'total_issues': self.total_issues,
            'severity_breakdown': {
                'critical': self.critical_severity_count,
                'high': self.high_severity_count,
                'medium': self.medium_severity_count,
                'low': self.low_severity_count
            },
            'analysis_duration': self.analysis_duration,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<SecurityAnalysis {self.id} for App {self.application_id}>'

class PerformanceTest(db.Model):
    """Model for storing performance test results."""
    __tablename__ = 'performance_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Test configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    test_type = db.Column(db.String(50), default='load_test')  # load_test, stress_test, spike_test
    target_users = db.Column(db.Integer, default=1)
    duration_seconds = db.Column(db.Integer, default=60)
    
    # Test results
    requests_per_second = db.Column(db.Float)
    average_response_time = db.Column(db.Float)  # milliseconds
    error_rate_percent = db.Column(db.Float)
    
    # Resource usage
    cpu_usage_percent = db.Column(db.Float)
    memory_usage_mb = db.Column(db.Float)
    
    # JSON field for detailed results
    results_json = db.Column(db.Text)       # Detailed test results
    metadata_json = db.Column(db.Text)      # Test metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self):
        """Get test results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set test results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'test_type': self.test_type,
            'target_users': self.target_users,
            'duration_seconds': self.duration_seconds,
            'requests_per_second': self.requests_per_second,
            'average_response_time': self.average_response_time,
            'error_rate_percent': self.error_rate_percent,
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<PerformanceTest {self.id} for App {self.application_id}>'

class ZAPAnalysis(db.Model):
    """Model for storing ZAP (OWASP ZAP) security analysis results."""
    __tablename__ = 'zap_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis status and configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    
    # Results summary
    total_alerts = db.Column(db.Integer, default=0)
    high_risk_count = db.Column(db.Integer, default=0)
    medium_risk_count = db.Column(db.Integer, default=0)
    low_risk_count = db.Column(db.Integer, default=0)
    informational_count = db.Column(db.Integer, default=0)
    
    # Performance metrics
    analysis_duration = db.Column(db.Float)  # Duration in seconds
    
    # JSON field for detailed results
    results_json = db.Column(db.Text)       # Detailed ZAP analysis results
    metadata_json = db.Column(db.Text)      # Analysis metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_results(self):
        """Get analysis results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set analysis results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'total_alerts': self.total_alerts,
            'risk_breakdown': {
                'high': self.high_risk_count,
                'medium': self.medium_risk_count,
                'low': self.low_risk_count,
                'informational': self.informational_count
            },
            'analysis_duration': self.analysis_duration,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<ZAPAnalysis {self.id} for App {self.application_id}>'

class OpenRouterAnalysis(db.Model):
    """Model for storing OpenRouter analysis results."""
    __tablename__ = 'openrouter_analyses'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Analysis status and configuration
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    
    # Results summary
    total_requirements = db.Column(db.Integer, default=0)
    met_requirements = db.Column(db.Integer, default=0)
    unmet_requirements = db.Column(db.Integer, default=0)
    high_confidence_count = db.Column(db.Integer, default=0)
    medium_confidence_count = db.Column(db.Integer, default=0)
    low_confidence_count = db.Column(db.Integer, default=0)
    
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
    
    def get_results(self):
        """Get analysis results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set analysis results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'application_id': self.application_id,
            'status': self.status.value if self.status else None,
            'total_requirements': self.total_requirements,
            'met_requirements': self.met_requirements,
            'unmet_requirements': self.unmet_requirements,
            'confidence_breakdown': {
                'high': self.high_confidence_count,
                'medium': self.medium_confidence_count,
                'low': self.low_confidence_count
            },
            'analysis_duration': self.analysis_duration,
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<OpenRouterAnalysis {self.id} for App {self.application_id}>'

class ContainerizedTest(db.Model):
    """Model for tracking tests submitted to containerized services."""
    __tablename__ = 'containerized_tests'
    
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    # Test configuration
    test_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, zap, ai
    service_endpoint = db.Column(db.String(200))  # Which container service
    tools_used = db.Column(db.Text)  # JSON list of tools
    
    # Test lifecycle
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    submitted_at = db.Column(db.DateTime, default=utc_now, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Results
    result_data = db.Column(db.Text)  # JSON results from containerized service
    error_message = db.Column(db.Text)
    
    # Performance metrics
    execution_duration = db.Column(db.Float)  # Duration in seconds
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationship
    application = db.relationship('GeneratedApplication', backref=db.backref('containerized_tests', lazy=True))
    
    def get_tools_used(self):
        """Get list of tools used in test."""
        if self.tools_used:
            try:
                return json.loads(self.tools_used)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tools_used(self, tools_list):
        """Set list of tools used in test."""
        self.tools_used = json.dumps(tools_list) if tools_list else None
    
    def get_result_data(self):
        """Get parsed result data."""
        if self.result_data:
            try:
                return json.loads(self.result_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_result_data(self, data_dict):
        """Set result data as JSON."""
        self.result_data = json.dumps(data_dict) if data_dict else None
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'test_id': self.test_id,
            'application_id': self.application_id,
            'test_type': self.test_type,
            'service_endpoint': self.service_endpoint,
            'tools_used': self.get_tools_used(),
            'status': self.status.value if self.status else None,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_duration': self.execution_duration,
            'result_data': self.get_result_data(),
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<ContainerizedTest {self.test_id}: {self.test_type} - {self.status}>'


class BatchAnalysis(db.Model):
    """Model for storing batch analysis records."""
    __tablename__ = 'batch_analyses'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID string
    name = db.Column(db.String(200), nullable=False)
    analysis_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, zap
    status = db.Column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    
    # Progress tracking
    total_applications = db.Column(db.Integer, default=0)
    completed_applications = db.Column(db.Integer, default=0)
    failed_applications = db.Column(db.Integer, default=0)
    
    # Performance metrics
    batch_duration = db.Column(db.Float)  # Duration in seconds
    
    # JSON field for configuration and results
    config_json = db.Column(db.Text)        # Batch configuration
    results_json = db.Column(db.Text)       # Batch results summary
    metadata_json = db.Column(db.Text)      # Additional metadata
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_config(self):
        """Get batch configuration as dictionary."""
        if self.config_json:
            try:
                return json.loads(self.config_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict):
        """Set batch configuration from dictionary."""
        self.config_json = json.dumps(config_dict)
    
    def get_results(self):
        """Get batch results as dictionary."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set batch results from dictionary."""
        self.results_json = json.dumps(results_dict)
    
    def get_metadata(self):
        """Get metadata as dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict):
        """Set metadata from dictionary."""
        self.metadata_json = json.dumps(metadata_dict)
    
    def get_progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_applications == 0:
            return 0
        return round((self.completed_applications + self.failed_applications) / self.total_applications * 100, 1)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'analysis_type': self.analysis_type,
            'status': self.status.value if self.status else None,
            'total_applications': self.total_applications,
            'completed_applications': self.completed_applications,
            'failed_applications': self.failed_applications,
            'progress_percentage': self.get_progress_percentage(),
            'batch_duration': self.batch_duration,
            'config': self.get_config(),
            'results': self.get_results(),
            'metadata': self.get_metadata(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<BatchAnalysis {self.name}>'


class BatchJob(db.Model):
    """Enhanced model for batch analysis jobs with full database persistence."""
    __tablename__ = 'batch_jobs'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID string
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    
    # Job configuration
    status = db.Column(db.Enum(JobStatus), default=JobStatus.PENDING, index=True)
    priority = db.Column(db.Enum(JobPriority), default=JobPriority.NORMAL, index=True)
    auto_start = db.Column(db.Boolean, default=True)
    auto_retry = db.Column(db.Boolean, default=False)
    max_retries = db.Column(db.Integer, default=3)
    
    # Analysis configuration (JSON fields)
    analysis_types_json = db.Column(db.Text)  # List of AnalysisType values
    models_json = db.Column(db.Text)          # List of model slugs  
    app_range_json = db.Column(db.Text)       # App range configuration
    options_json = db.Column(db.Text)         # Additional options
    
    # Progress tracking
    total_tasks = db.Column(db.Integer, default=0)
    completed_tasks = db.Column(db.Integer, default=0)
    failed_tasks = db.Column(db.Integer, default=0)
    cancelled_tasks = db.Column(db.Integer, default=0)
    
    # Performance metrics
    estimated_duration_minutes = db.Column(db.Integer)
    actual_duration_seconds = db.Column(db.Float)
    
    # Error handling
    error_message = db.Column(db.Text)
    error_details_json = db.Column(db.Text)
    
    # Results summary
    results_summary_json = db.Column(db.Text)
    artifacts_json = db.Column(db.Text)  # Generated artifacts/reports
    
    # Timestamps
    scheduled_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_heartbeat = db.Column(db.DateTime)  # For monitoring
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Foreign key to user (if user management is added later)
    created_by = db.Column(db.String(100))  # For future user management
    
    # Relationships
    tasks = db.relationship('BatchTask', backref='job', lazy=True, cascade='all, delete-orphan')
    
    def get_analysis_types(self):
        """Get analysis types as list."""
        if self.analysis_types_json:
            try:
                return json.loads(self.analysis_types_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_analysis_types(self, types_list):
        """Set analysis types from list."""
        self.analysis_types_json = json.dumps(types_list)
    
    def get_models(self):
        """Get models as list."""
        if self.models_json:
            try:
                return json.loads(self.models_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_models(self, models_list):
        """Set models from list."""
        self.models_json = json.dumps(models_list)
    
    def get_app_range(self):
        """Get app range configuration."""
        if self.app_range_json:
            try:
                return json.loads(self.app_range_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_app_range(self, app_range_dict):
        """Set app range configuration."""
        self.app_range_json = json.dumps(app_range_dict)
    
    def get_options(self):
        """Get additional options."""
        if self.options_json:
            try:
                return json.loads(self.options_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_options(self, options_dict):
        """Set additional options."""
        self.options_json = json.dumps(options_dict)
    
    def get_error_details(self):
        """Get error details."""
        if self.error_details_json:
            try:
                return json.loads(self.error_details_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_error_details(self, error_dict):
        """Set error details."""
        self.error_details_json = json.dumps(error_dict)
    
    def get_results_summary(self):
        """Get results summary."""
        if self.results_summary_json:
            try:
                return json.loads(self.results_summary_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results_summary(self, summary_dict):
        """Set results summary."""
        self.results_summary_json = json.dumps(summary_dict)
    
    def get_artifacts(self):
        """Get generated artifacts."""
        if self.artifacts_json:
            try:
                return json.loads(self.artifacts_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_artifacts(self, artifacts_list):
        """Set generated artifacts."""
        self.artifacts_json = json.dumps(artifacts_list)
    
    def get_progress_percentage(self):
        """Calculate progress percentage."""
        if self.total_tasks == 0:
            return 0
        processed = self.completed_tasks + self.failed_tasks + self.cancelled_tasks
        return round(processed / self.total_tasks * 100, 1)
    
    def get_success_rate(self):
        """Calculate success rate percentage."""
        processed = self.completed_tasks + self.failed_tasks
        if processed == 0:
            return 0
        return round(self.completed_tasks / processed * 100, 1)
    
    def is_active(self):
        """Check if job is currently active."""
        return self.status in [JobStatus.QUEUED, JobStatus.RUNNING]
    
    def can_be_cancelled(self):
        """Check if job can be cancelled."""
        return self.status in [JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED]
    
    def can_be_restarted(self):
        """Check if job can be restarted."""
        return self.status in [JobStatus.FAILED, JobStatus.CANCELLED, JobStatus.COMPLETED]
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'auto_start': self.auto_start,
            'auto_retry': self.auto_retry,
            'max_retries': self.max_retries,
            'analysis_types': self.get_analysis_types(),
            'models': self.get_models(),
            'app_range': self.get_app_range(),
            'options': self.get_options(),
            'total_tasks': self.total_tasks,
            'completed_tasks': self.completed_tasks,
            'failed_tasks': self.failed_tasks,
            'cancelled_tasks': self.cancelled_tasks,
            'progress_percentage': self.get_progress_percentage(),
            'success_rate': self.get_success_rate(),
            'estimated_duration_minutes': self.estimated_duration_minutes,
            'actual_duration_seconds': self.actual_duration_seconds,
            'error_message': self.error_message,
            'error_details': self.get_error_details(),
            'results_summary': self.get_results_summary(),
            'artifacts': self.get_artifacts(),
            'is_active': self.is_active(),
            'can_be_cancelled': self.can_be_cancelled(),
            'can_be_restarted': self.can_be_restarted(),
            'created_by': self.created_by,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<BatchJob {self.name} ({self.status.value if self.status else "unknown"})>'


class BatchTask(db.Model):
    """Enhanced model for individual batch tasks with full database persistence."""
    __tablename__ = 'batch_tasks'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID string
    job_id = db.Column(db.String(36), db.ForeignKey('batch_jobs.id'), nullable=False, index=True)
    
    # Task identification
    model_slug = db.Column(db.String(200), nullable=False, index=True)
    app_number = db.Column(db.Integer, nullable=False, index=True)
    analysis_type = db.Column(db.Enum(AnalysisType), nullable=False, index=True)
    
    # Task configuration
    status = db.Column(db.Enum(TaskStatus), default=TaskStatus.PENDING, index=True)
    priority = db.Column(db.Enum(JobPriority), default=JobPriority.NORMAL)
    retry_count = db.Column(db.Integer, default=0)
    max_retries = db.Column(db.Integer, default=3)
    
    # Execution details
    assigned_worker = db.Column(db.String(100))  # Worker ID/name
    execution_host = db.Column(db.String(100))   # Host where task executed
    process_id = db.Column(db.Integer)           # Process ID during execution
    
    # Performance metrics
    estimated_duration_seconds = db.Column(db.Integer)
    actual_duration_seconds = db.Column(db.Float)
    memory_usage_mb = db.Column(db.Float)
    cpu_usage_percent = db.Column(db.Float)
    
    # Results and errors
    exit_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    error_details_json = db.Column(db.Text)
    
    # Analysis results
    results_json = db.Column(db.Text)
    artifacts_json = db.Column(db.Text)  # Generated files/reports
    
    # Analysis-specific metrics
    issues_found = db.Column(db.Integer, default=0)
    critical_issues = db.Column(db.Integer, default=0)
    high_issues = db.Column(db.Integer, default=0)
    medium_issues = db.Column(db.Integer, default=0)
    low_issues = db.Column(db.Integer, default=0)
    
    # Task dependencies (for future use)
    depends_on_json = db.Column(db.Text)  # List of task IDs this depends on
    
    # Timestamps
    queued_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    last_heartbeat = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_error_details(self):
        """Get error details."""
        if self.error_details_json:
            try:
                return json.loads(self.error_details_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_error_details(self, error_dict):
        """Set error details."""
        self.error_details_json = json.dumps(error_dict)
    
    def get_results(self):
        """Get task results."""
        if self.results_json:
            try:
                return json.loads(self.results_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_results(self, results_dict):
        """Set task results."""
        self.results_json = json.dumps(results_dict)
    
    def get_artifacts(self):
        """Get generated artifacts."""
        if self.artifacts_json:
            try:
                return json.loads(self.artifacts_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_artifacts(self, artifacts_list):
        """Set generated artifacts."""
        self.artifacts_json = json.dumps(artifacts_list)
    
    def get_depends_on(self):
        """Get task dependencies."""
        if self.depends_on_json:
            try:
                return json.loads(self.depends_on_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_depends_on(self, depends_list):
        """Set task dependencies."""
        self.depends_on_json = json.dumps(depends_list)
    
    def get_total_issues(self):
        """Get total issues count."""
        return self.critical_issues + self.high_issues + self.medium_issues + self.low_issues
    
    def can_be_retried(self):
        """Check if task can be retried."""
        return (
            self.status in [TaskStatus.FAILED, TaskStatus.CANCELLED] and
            self.retry_count < self.max_retries
        )
    
    def can_be_cancelled(self):
        """Check if task can be cancelled."""
        return self.status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.RUNNING]
    
    def get_execution_summary(self):
        """Get execution summary."""
        duration = self.actual_duration_seconds
        if duration and self.estimated_duration_seconds:
            efficiency = round((self.estimated_duration_seconds / duration) * 100, 1)
        else:
            efficiency = None
            
        return {
            'duration_seconds': duration,
            'estimated_duration_seconds': self.estimated_duration_seconds,
            'efficiency_percentage': efficiency,
            'memory_usage_mb': self.memory_usage_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'exit_code': self.exit_code,
            'retry_count': self.retry_count,
            'assigned_worker': self.assigned_worker,
            'execution_host': self.execution_host
        }
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'job_id': self.job_id,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'analysis_type': self.analysis_type.value if self.analysis_type else None,
            'status': self.status.value if self.status else None,
            'priority': self.priority.value if self.priority else None,
            'retry_count': self.retry_count,
            'max_retries': self.max_retries,
            'issues_found': self.issues_found,
            'critical_issues': self.critical_issues,
            'high_issues': self.high_issues,
            'medium_issues': self.medium_issues,
            'low_issues': self.low_issues,
            'total_issues': self.get_total_issues(),
            'execution_summary': self.get_execution_summary(),
            'error_message': self.error_message,
            'error_details': self.get_error_details(),
            'results': self.get_results(),
            'artifacts': self.get_artifacts(),
            'depends_on': self.get_depends_on(),
            'can_be_retried': self.can_be_retried(),
            'can_be_cancelled': self.can_be_cancelled(),
            'queued_at': self.queued_at.isoformat() if self.queued_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<BatchTask {self.model_slug}/app{self.app_number} {self.analysis_type.value if self.analysis_type else "unknown"} ({self.status.value if self.status else "unknown"})>'


class BatchWorker(db.Model):
    """Model for tracking batch workers/processes."""
    __tablename__ = 'batch_workers'
    
    id = db.Column(db.String(36), primary_key=True)  # UUID string
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(100), nullable=False)
    process_id = db.Column(db.Integer)
    
    # Worker status
    status = db.Column(db.String(20), default='idle')  # idle, busy, offline, error
    current_task_id = db.Column(db.String(36), db.ForeignKey('batch_tasks.id'), nullable=True)
    
    # Capabilities
    supported_analysis_types_json = db.Column(db.Text)
    max_concurrent_tasks = db.Column(db.Integer, default=1)
    current_task_count = db.Column(db.Integer, default=0)
    
    # Performance metrics
    total_tasks_completed = db.Column(db.Integer, default=0)
    total_tasks_failed = db.Column(db.Integer, default=0)
    average_task_duration = db.Column(db.Float)
    
    # Resource usage
    cpu_usage_percent = db.Column(db.Float)
    memory_usage_mb = db.Column(db.Float)
    disk_usage_mb = db.Column(db.Float)
    
    # Health monitoring
    last_heartbeat = db.Column(db.DateTime)
    last_error = db.Column(db.Text)
    error_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    started_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_supported_analysis_types(self):
        """Get supported analysis types."""
        if self.supported_analysis_types_json:
            try:
                return json.loads(self.supported_analysis_types_json)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_supported_analysis_types(self, types_list):
        """Set supported analysis types."""
        self.supported_analysis_types_json = json.dumps(types_list)
    
    def is_available(self):
        """Check if worker is available for tasks."""
        return (
            self.status == 'idle' and
            self.current_task_count < self.max_concurrent_tasks
        )
    
    def is_healthy(self):
        """Check if worker is healthy."""
        if not self.last_heartbeat:
            return False
        
        cutoff = utc_now() - timedelta(minutes=5)
        return self.last_heartbeat > cutoff and self.status != 'error'
    
    def get_efficiency_rating(self):
        """Calculate worker efficiency rating."""
        total = self.total_tasks_completed + self.total_tasks_failed
        if total == 0:
            return 0
        return round((self.total_tasks_completed / total) * 100, 1)
    
    def to_dict(self):
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'process_id': self.process_id,
            'status': self.status,
            'current_task_id': self.current_task_id,
            'supported_analysis_types': self.get_supported_analysis_types(),
            'max_concurrent_tasks': self.max_concurrent_tasks,
            'current_task_count': self.current_task_count,
            'total_tasks_completed': self.total_tasks_completed,
            'total_tasks_failed': self.total_tasks_failed,
            'average_task_duration': self.average_task_duration,
            'efficiency_rating': self.get_efficiency_rating(),
            'cpu_usage_percent': self.cpu_usage_percent,
            'memory_usage_mb': self.memory_usage_mb,
            'disk_usage_mb': self.disk_usage_mb,
            'is_available': self.is_available(),
            'is_healthy': self.is_healthy(),
            'last_error': self.last_error,
            'error_count': self.error_count,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def __repr__(self):
        return f'<BatchWorker {self.name} ({self.status})>'
