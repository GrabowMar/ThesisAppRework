"""
Analysis Models
===============

SQLAlchemy models for analysis tasks and results.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import uuid
import json

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..constants import AnalysisStatus, SeverityLevel, JobPriority


class AnalyzerConfiguration(db.Model):
    """Configuration for analyzer runtime settings."""
    __tablename__ = 'analyzer_configurations'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    config_id: Mapped[str] = mapped_column(db.String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(db.String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class AnalysisTask(db.Model):
    """Individual analysis task with lifecycle tracking."""
    __tablename__ = 'analysis_tasks'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(db.String(100), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    
    # Target information
    target_model: Mapped[str] = mapped_column(db.String(200), index=True)
    target_app_number: Mapped[int] = mapped_column(index=True)
    application_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True, index=True)
    
    # Task hierarchy
    is_main_task: Mapped[Optional[bool]] = mapped_column(db.Boolean, nullable=True, default=False)
    parent_task_id: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True, index=True)
    
    # Status and lifecycle
    status: Mapped[AnalysisStatus] = mapped_column(db.Enum(AnalysisStatus), default=AnalysisStatus.PENDING, index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True, index=True)
    
    # Results and metadata
    result_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issues_found: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    
    # Configuration
    config_id: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    batch_id: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True, index=True)
    priority: Mapped[Optional[JobPriority]] = mapped_column(db.Enum(JobPriority), nullable=True, default=JobPriority.NORMAL)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    
    # Service information
    service_name: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    task_name: Mapped[Optional[str]] = mapped_column(db.String(200), nullable=True)
    analysis_type: Mapped[Optional[str]] = mapped_column(db.String(50), nullable=True)
    progress_percentage: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True, default=0)
    
    # Relationships (lazy loaded)
    @property
    def subtasks(self):
        """Get subtasks if this is a main task."""
        if self.is_main_task:
            return AnalysisTask.query.filter_by(parent_task_id=self.task_id).all()
        return []
    
    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as dictionary."""
        return self.metadata_json or {}
    
    def set_metadata(self, metadata: Dict[str, Any]):
        """Set metadata from dictionary."""
        self.metadata_json = metadata
    
    def __repr__(self):
        return f"<AnalysisTask {self.task_id} status={self.status.value if isinstance(self.status, AnalysisStatus) else self.status}>"


class AnalysisResult(db.Model):
    """Stored findings from analyzer runs."""
    __tablename__ = 'analysis_results'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(db.String(100), index=True)
    
    # Tool information
    service_name: Mapped[str] = mapped_column(db.String(100), index=True)
    tool_name: Mapped[str] = mapped_column(db.String(100), index=True)
    
    # Finding details
    severity: Mapped[Optional[SeverityLevel]] = mapped_column(db.Enum(SeverityLevel), nullable=True, index=True)
    message: Mapped[str] = mapped_column(Text)
    
    # Location information
    file_path: Mapped[Optional[str]] = mapped_column(db.String(500), nullable=True)
    line_number: Mapped[Optional[int]] = mapped_column(db.Integer, nullable=True)
    
    # Additional metadata
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True, index=True)
    
    # SARIF 2.1.0 compliance fields
    sarif_level: Mapped[Optional[str]] = mapped_column(db.String(20), nullable=True)
    sarif_rule_id: Mapped[Optional[str]] = mapped_column(db.String(100), nullable=True)
    sarif_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), index=True)
    
    def __repr__(self):
        return f"<AnalysisResult {self.id} tool={self.tool_name} severity={self.severity.value if self.severity else None}>"
