"""
Report database model for storing generated reports.

v2: Reports store JSON data directly in database - no file I/O.
Reports are rendered client-side using JavaScript.
"""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..extensions import db
from ..utils.time import utc_now


class Report(db.Model):
    """Generated analysis reports stored as JSON in database."""
    __tablename__ = 'reports'
    
    # Identifiers
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Report configuration  
    # Types: 'model_analysis', 'template_comparison', 'tool_analysis'
    report_type = db.Column(db.String(100), nullable=False, index=True)
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    
    # Configuration (JSON) - stores parameters for regeneration
    config = db.Column(db.Text, nullable=False, default='{}')
    
    # Report data (JSON) - the actual report content
    # Stored directly in DB for fast access - no file I/O needed
    report_data = db.Column(db.Text)
    
    # Legacy fields (kept for migration compatibility)
    format = db.Column(db.String(50), default='json')  # Always 'json' now
    file_path = db.Column(db.String(500))  # Deprecated - kept for migration
    file_size = db.Column(db.Integer)  # Deprecated - kept for migration
    
    # Status and processing
    status = db.Column(db.String(50), default='pending', nullable=False, index=True)
    error_message = db.Column(db.Text)
    progress_percent = db.Column(db.Integer, default=0)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    
    # Statistics and summary (denormalized for quick list display)
    summary = db.Column(db.Text)
    
    # Relationships
    analysis_task_id = db.Column(db.Integer, db.ForeignKey('analysis_tasks.id'), nullable=True)
    analysis_task = db.relationship('AnalysisTask', backref='reports', lazy='select')
    
    generated_app_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=True)
    generated_app = db.relationship('GeneratedApplication', backref='reports', lazy='select')
    
    user = db.relationship('User', backref='reports', lazy='select', foreign_keys=[created_by])
    
    # Indexes for common queries
    __table_args__ = (
        db.Index('idx_report_type_status', 'report_type', 'status'),
        db.Index('idx_report_created_at', 'created_at'),
    )
    
    def __init__(self, **kwargs: Any) -> None:
        """Initialize Report with keyword arguments for Pylance compatibility."""
        super().__init__(**kwargs)
    
    def get_config(self) -> Dict[str, Any]:
        """Get configuration as dictionary."""
        if self.config:
            try:
                return json.loads(self.config)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration from dictionary."""
        self.config = json.dumps(config_dict)
    
    def get_report_data(self) -> Optional[Dict[str, Any]]:
        """Get full report data as dictionary."""
        if self.report_data:
            try:
                return json.loads(self.report_data)
            except json.JSONDecodeError:
                return None
        return None
    
    def set_report_data(self, data: Dict[str, Any]) -> None:
        """Set report data from dictionary."""
        self.report_data = json.dumps(data, default=str)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary as dictionary."""
        if self.summary:
            try:
                return json.loads(self.summary)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_summary(self, summary_dict: Dict[str, Any]) -> None:
        """Set summary from dictionary."""
        self.summary = json.dumps(summary_dict)
    
    def mark_generating(self) -> None:
        """Mark report as generating."""
        self.status = 'generating'
        self.progress_percent = 0
        self.error_message = None
    
    def mark_completed(self) -> None:
        """Mark report as completed."""
        self.status = 'completed'
        self.completed_at = utc_now()
        self.progress_percent = 100
        self.error_message = None
    
    def mark_failed(self, error_message: str) -> None:
        """Mark report as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.completed_at = utc_now()
    
    def update_progress(self, percent: int) -> None:
        """Update generation progress."""
        self.progress_percent = max(0, min(100, percent))
    
    def is_expired(self) -> bool:
        """Check if report has expired."""
        if self.expires_at:
            now = utc_now()
            expires = self.expires_at
            
            # Handle timezone-aware/naive comparison
            if expires.tzinfo is None:
                from datetime import datetime
                now = datetime.utcnow()
            elif now.tzinfo is None:
                import pytz
                now = pytz.utc.localize(now)
            
            return now > expires
        return False
    
    def to_dict(self, include_data: bool = False) -> Dict[str, Any]:
        """
        Convert model to dictionary.
        
        Args:
            include_data: If True, include full report_data (can be large)
        """
        data = {
            'id': self.id,
            'report_id': self.report_id,
            'report_type': self.report_type,
            'title': self.title,
            'description': self.description,
            'config': self.get_config(),
            'format': self.format,
            'status': self.status,
            'error_message': self.error_message,
            'progress_percent': self.progress_percent,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'summary': self.get_summary(),
            'is_expired': self.is_expired()
        }
        
        if include_data:
            data['data'] = self.get_report_data()
        
        return data
    
    def __repr__(self) -> str:
        return f'<Report {self.report_id} ({self.report_type}, {self.status})>'
