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
from datetime import datetime

try:
    from .extensions import db
except ImportError:
    from extensions import db

class AnalysisStatus(enum.Enum):
    """Status enum for analyses and tests."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
