"""
Core Models
===========

Core database models for AI models, applications, and ports.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class ModelCapability(db.Model):
    """AI model metadata and capabilities."""
    __tablename__ = 'model_capabilities'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    canonical_slug: Mapped[str] = mapped_column(db.String(200), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(db.String(300))
    provider: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    parameters_billions: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    context_length: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ModelCapability {self.canonical_slug}>"


class PortConfiguration(db.Model):
    """Docker port allocations for generated applications."""
    __tablename__ = 'port_configurations'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    model_slug: Mapped[str] = mapped_column(db.String(200), index=True)
    app_number: Mapped[int] = mapped_column(db.Integer)
    backend_port: Mapped[int] = mapped_column(db.Integer, unique=True)
    frontend_port: Mapped[int] = mapped_column(db.Integer, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        db.UniqueConstraint('model_slug', 'app_number', name='uq_model_app'),
    )
    
    def __repr__(self):
        return f"<PortConfiguration {self.model_slug}/{self.app_number}>"


class GeneratedApplication(db.Model):
    """AI-generated application instances."""
    __tablename__ = 'generated_applications'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    model_slug: Mapped[str] = mapped_column(db.String(200), index=True)
    app_number: Mapped[int] = mapped_column(db.Integer)
    status: Mapped[str] = mapped_column(db.String(50), default='created')
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_status_check: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    generation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('model_slug', 'app_number', name='uq_generated_app'),
    )
    
    def __repr__(self):
        return f"<GeneratedApplication {self.model_slug}/app{self.app_number}>"


class GeneratedCodeResult(db.Model):
    """Results from code generation processes."""
    __tablename__ = 'generated_code_results'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, db.ForeignKey('generated_applications.id'), index=True)
    result_type: Mapped[str] = mapped_column(db.String(50))
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<GeneratedCodeResult {self.id} type={self.result_type}>"
