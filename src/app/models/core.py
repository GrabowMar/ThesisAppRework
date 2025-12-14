from __future__ import annotations
import json
from typing import Dict, Any
from sqlalchemy import Enum
from ..extensions import db
from ..constants import AnalysisStatus, GenerationMode
from ..utils.time import utc_now

class ModelCapability(db.Model):
    """Model for storing AI model capabilities and metadata."""
    __tablename__ = 'model_capabilities'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    canonical_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    base_model_id = db.Column(db.String(200), index=True)  # Model ID without variant suffix (e.g., without :free)
    hugging_face_id = db.Column(db.String(200), index=True)  # Exact case-sensitive ID from HuggingFace (if applicable)
    provider = db.Column(db.String(100), nullable=False, index=True)
    model_name = db.Column(db.String(200), nullable=False)
    
    # Capabilities
    is_free = db.Column(db.Boolean, default=False)
    installed = db.Column(db.Boolean, default=False, index=True)
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
    capabilities_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    def get_capabilities(self) -> Dict[str, Any]:
        if self.capabilities_json:
            try:
                return json.loads(self.capabilities_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_capabilities(self, capabilities_dict: Dict[str, Any]) -> None:
        self.capabilities_json = json.dumps(capabilities_dict)
    
    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(metadata_dict)

class PortConfiguration(db.Model):
    """Model for storing Docker port configurations."""
    __tablename__ = 'port_configurations'
    __table_args__ = (db.UniqueConstraint('model', 'app_num', name='unique_model_app'), {'extend_existing': True})
    
    id = db.Column(db.Integer, primary_key=True)
    model = db.Column(db.String(200), nullable=False, index=True)
    app_num = db.Column(db.Integer, nullable=False, index=True)
    frontend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    backend_port = db.Column(db.Integer, unique=True, nullable=False, index=True)
    is_available = db.Column(db.Boolean, default=True, index=True)
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(metadata_dict)

class GeneratedApplication(db.Model):
    """Model for storing information about AI-generated applications."""
    __tablename__ = 'generated_applications'
    __table_args__ = (
        db.UniqueConstraint('model_slug', 'app_number', 'version', name='unique_model_app_version'),
        db.Index('idx_model_template', 'model_slug', 'template_slug'),
        db.Index('idx_batch_id', 'batch_id'),
        {'extend_existing': True}
    )
    
    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), nullable=False, index=True)
    app_number = db.Column(db.Integer, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)  # Version number for regenerations (1, 2, 3...)
    parent_app_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=True)  # Links to parent app if this is a regeneration
    batch_id = db.Column(db.String(100), nullable=True, index=True)  # Groups apps created together in batch wizard
    app_type = db.Column(db.String(50), nullable=False)
    provider = db.Column(db.String(100), nullable=False, index=True)
    template_slug = db.Column(db.String(100), nullable=True, index=True)  # Tracks which requirement template was used
    generation_mode = db.Column(Enum(GenerationMode), default=GenerationMode.GUARDED, index=True)  # guarded vs unguarded generation
    generation_status = db.Column(Enum(AnalysisStatus), default=AnalysisStatus.PENDING)
    has_backend = db.Column(db.Boolean, default=False)
    has_frontend = db.Column(db.Boolean, default=False)
    has_docker_compose = db.Column(db.Boolean, default=False)
    backend_framework = db.Column(db.String(50))
    frontend_framework = db.Column(db.String(50))
    container_status = db.Column(db.String(50), default='stopped')
    last_status_check = db.Column(db.DateTime(timezone=True))
    missing_since = db.Column(db.DateTime(timezone=True), nullable=True)  # Track when filesystem directory went missing (for 7-day grace period)
    
    # Generation failure tracking
    is_generation_failed = db.Column(db.Boolean, default=False, index=True)  # True if generation failed at any stage
    failure_stage = db.Column(db.String(50), nullable=True)  # scaffold/backend/frontend/finalization
    error_message = db.Column(db.Text, nullable=True)  # Human-readable error message
    generation_attempts = db.Column(db.Integer, default=1)  # Number of generation attempts (for retry tracking)
    last_error_at = db.Column(db.DateTime(timezone=True), nullable=True)  # When the last error occurred
    
    # Fixes applied tracking
    retry_fixes = db.Column(db.Integer, default=0)  # Number of retry attempts during generation
    automatic_fixes = db.Column(db.Integer, default=0)  # Script-based automatic fixes during generation
    llm_fixes = db.Column(db.Integer, default=0)  # LLM-based fixes applied during generation
    manual_fixes = db.Column(db.Integer, default=0)  # Manual fixes applied post-generation
    
    metadata_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    
    security_analyses = db.relationship('SecurityAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    performance_tests = db.relationship('PerformanceTest', backref='application', lazy=True, cascade='all, delete-orphan')
    zap_analyses = db.relationship('ZAPAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    openrouter_analyses = db.relationship('OpenRouterAnalysis', backref='application', lazy=True, cascade='all, delete-orphan')
    
    def get_metadata(self) -> Dict[str, Any]:
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_metadata(self, metadata_dict: Dict[str, Any]) -> None:
        self.metadata_json = json.dumps(metadata_dict)

    def update_container_status(self, new_status: str) -> None:
        """Update container status and last check timestamp."""
        self.container_status = new_status
        self.last_status_check = utc_now()

    def is_status_fresh(self, max_age_minutes: int = 5) -> bool:
        """Check if the status was updated within the specified minutes."""
        if not self.last_status_check:
            return False
        from datetime import timedelta, timezone
        # Ensure both datetimes are timezone-aware for comparison
        now = utc_now()
        last_check = self.last_status_check
        if last_check.tzinfo is None:
            last_check = last_check.replace(tzinfo=timezone.utc)
        age = now - last_check
        return age < timedelta(minutes=max_age_minutes)

    def get_ports(self) -> Dict[str, Any]:
        """Get port configuration for this application."""
        from ..services.model_service import ModelService
        from flask import current_app
        
        try:
            # Create a model service instance if we have a current app
            if current_app:
                model_service = ModelService(current_app)
                return model_service.get_app_ports(self.model_slug, self.app_number) or {}
        except RuntimeError:
            # No Flask app context available
            pass
        except Exception:
            # Handle any other errors gracefully
            pass
        
        return {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'version': self.version,
            'parent_app_id': self.parent_app_id,
            'batch_id': self.batch_id,
            'app_type': self.app_type,
            'provider': self.provider,
            'template_slug': self.template_slug,
            'generation_mode': self.generation_mode.value if self.generation_mode else 'guarded',
            'generation_status': self.generation_status.value if self.generation_status else None,
            'has_backend': self.has_backend,
            'has_frontend': self.has_frontend,
            'has_docker_compose': self.has_docker_compose,
            'backend_framework': self.backend_framework,
            'frontend_framework': self.frontend_framework,
            'container_status': self.container_status,
            'last_status_check': self.last_status_check.isoformat() if self.last_status_check else None,
            # Failure tracking fields
            'is_generation_failed': self.is_generation_failed,
            'failure_stage': self.failure_stage,
            'error_message': self.error_message,
            'generation_attempts': self.generation_attempts,
            'last_error_at': self.last_error_at.isoformat() if self.last_error_at else None,
            # Fixes applied tracking
            'retry_fixes': self.retry_fixes or 0,
            'automatic_fixes': self.automatic_fixes or 0,
            'llm_fixes': self.llm_fixes or 0,
            'manual_fixes': self.manual_fixes or 0,
            'metadata': self.get_metadata(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class GeneratedCodeResult(db.Model):
    """Persistence model for AI code generation results."""
    __tablename__ = 'generated_code_results'
    __table_args__ = (db.UniqueConstraint('result_id', name='uq_generated_code_result_id'), {'extend_existing': True})

    id = db.Column(db.Integer, primary_key=True)
    result_id = db.Column(db.String(200), nullable=False, index=True)
    model = db.Column(db.String(200), nullable=False, index=True)
    app_num = db.Column(db.Integer, nullable=False, index=True)
    app_name = db.Column(db.String(200), nullable=False)
    success = db.Column(db.Boolean, default=False, index=True)
    error_message = db.Column(db.Text)
    duration = db.Column(db.Float)
    timestamp = db.Column(db.DateTime(timezone=True), default=utc_now, index=True)
    requirements_json = db.Column(db.Text)
    content = db.Column(db.Text)
    blocks_json = db.Column(db.Text)
