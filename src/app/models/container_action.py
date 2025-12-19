"""
Container Action Model
======================

Tracks container operations (build, start, stop, restart) with progress tracking,
real-time updates, and action history. Follows AnalysisTask pattern.
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, Optional

from ..extensions import db
from ..utils.time import utc_now


class ContainerActionType(str, Enum):
    """Types of container actions."""
    BUILD = "build"
    START = "start"
    STOP = "stop"
    RESTART = "restart"
    
    def __str__(self) -> str:
        return self.value


class ContainerActionStatus(str, Enum):
    """Status of container actions."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    
    def __str__(self) -> str:
        return self.value


class ContainerAction(db.Model):
    """Model for tracking container operations with progress and history."""
    __tablename__ = 'container_actions'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Action type and target
    action_type = db.Column(
        db.Enum(ContainerActionType, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
        index=True
    )
    target_model = db.Column(db.String(200), nullable=False, index=True)
    target_app_number = db.Column(db.Integer, nullable=False)
    
    # Status tracking
    status = db.Column(
        db.Enum(ContainerActionStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]),
        default=ContainerActionStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    current_step = db.Column(db.String(500))
    total_steps = db.Column(db.Integer)
    completed_steps = db.Column(db.Integer, default=0)
    
    # Output capture
    stdout = db.Column(db.Text)
    stderr = db.Column(db.Text)
    combined_output = db.Column(db.Text)  # Real-time output for streaming
    
    # Result info
    exit_code = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    
    # Build-specific metadata (layers, images built, etc.)
    build_metadata = db.Column(db.Text)  # JSON
    
    # Timing
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    
    # User who triggered (optional, for audit)
    triggered_by = db.Column(db.String(100))
    
    def __repr__(self) -> str:
        return f'<ContainerAction {self.action_id} ({self.action_type.value})>'
    
    # --- Progress methods ---
    
    def update_progress(self, percentage: float, current_step: Optional[str] = None) -> None:
        """Update action progress."""
        self.progress_percentage = min(100.0, max(0.0, percentage))
        if current_step:
            self.current_step = current_step
    
    def append_output(self, line: str) -> None:
        """Append a line to combined output."""
        if self.combined_output:
            self.combined_output += line
        else:
            self.combined_output = line
    
    # --- Lifecycle methods ---
    
    def start_execution(self) -> None:
        """Mark action as started."""
        self.status = ContainerActionStatus.RUNNING
        self.started_at = utc_now()
        self.progress_percentage = 0.0
    
    def complete_execution(self, success: bool = True, exit_code: int = 0,
                          error_message: Optional[str] = None) -> None:
        """Mark action as completed or failed."""
        self.completed_at = utc_now()
        self.exit_code = exit_code
        
        if success and exit_code == 0:
            self.status = ContainerActionStatus.COMPLETED
            self.progress_percentage = 100.0
        else:
            self.status = ContainerActionStatus.FAILED
            if error_message:
                self.error_message = error_message
    
    def cancel(self, reason: Optional[str] = None) -> None:
        """Cancel the action."""
        self.status = ContainerActionStatus.CANCELLED
        self.completed_at = utc_now()
        if reason:
            self.error_message = reason
    
    # --- Metadata helpers ---
    
    def get_build_metadata(self) -> Dict[str, Any]:
        """Get build metadata as dictionary."""
        if self.build_metadata:
            try:
                return json.loads(self.build_metadata)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_build_metadata(self, metadata: Dict[str, Any]) -> None:
        """Set build metadata from dictionary."""
        self.build_metadata = json.dumps(metadata)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if action is currently active (pending or running)."""
        return self.status in (ContainerActionStatus.PENDING, ContainerActionStatus.RUNNING)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for API responses."""
        return {
            'id': self.id,
            'action_id': self.action_id,
            'action_type': self.action_type.value if self.action_type else None,
            'target_model': self.target_model,
            'target_app_number': self.target_app_number,
            'status': self.status.value if self.status else None,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'total_steps': self.total_steps,
            'completed_steps': self.completed_steps,
            'exit_code': self.exit_code,
            'error_message': self.error_message,
            'duration_seconds': self.duration_seconds,
            'build_metadata': self.get_build_metadata(),
            'triggered_by': self.triggered_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Minimal dict for list views."""
        return {
            'action_id': self.action_id,
            'action_type': self.action_type.value if self.action_type else None,
            'status': self.status.value if self.status else None,
            'progress_percentage': self.progress_percentage,
            'current_step': self.current_step,
            'duration_seconds': self.duration_seconds,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
