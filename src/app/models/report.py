"""
Report database model for storing generated reports.
"""
import json
from typing import Dict, Any, List, Optional
from pathlib import Path
from ..extensions import db
from ..utils.time import utc_now


class Report(db.Model):
    """Generated analysis reports in various formats."""
    __tablename__ = 'reports'
    
    # Identifiers
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    
    # Report configuration
    report_type = db.Column(db.String(100), nullable=False, index=True)  # 'model_analysis', 'app_analysis', 'tool_analysis'
    title = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text)
    
    # Configuration (JSON) - stores parameters for regeneration
    # model_analysis: {'model_slug': str, 'date_range': {start, end}}
    # app_analysis (template comparison): {'template_slug': str, 'filter_models': [str], 'date_range': {start, end}}
    # tool_analysis: {'tool_name': str (optional), 'filter_model': str (optional), 'filter_app': int (optional), 'date_range': {start, end}}
    config = db.Column(db.Text, nullable=False)  # JSON: Configuration specific to report type
    
    # Output configuration
    format = db.Column(db.String(50), nullable=False)  # 'html', 'json' (pdf/excel removed)
    file_path = db.Column(db.String(500))  # Relative path from reports directory
    file_size = db.Column(db.Integer)  # File size in bytes
    
    # Status and processing
    status = db.Column(db.String(50), default='pending', nullable=False, index=True)  # 'pending', 'generating', 'completed', 'failed'
    error_message = db.Column(db.Text)
    progress_percent = db.Column(db.Integer, default=0)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    completed_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))  # Optional expiration for cleanup
    
    # Statistics and summary (denormalized for quick display)
    summary = db.Column(db.Text)  # JSON: Quick stats about the report content
    
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
    
    def get_absolute_path(self, reports_dir: Path) -> Optional[Path]:
        """Get absolute file path."""
        if self.file_path:
            return reports_dir / self.file_path
        return None
    
    def mark_generating(self) -> None:
        """Mark report as generating."""
        self.status = 'generating'
        self.progress_percent = 0
        self.error_message = None
    
    def mark_completed(self, file_path: str, file_size: int) -> None:
        """Mark report as completed."""
        self.status = 'completed'
        self.file_path = file_path
        self.file_size = file_size
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
                # expires_at is naive, compare with naive now
                from datetime import datetime
                now = datetime.utcnow()
            elif now.tzinfo is None:
                # now is naive but expires is aware - shouldn't happen with utc_now()
                # but handle it anyway by making now aware
                import pytz
                now = pytz.utc.localize(now)
            
            return now > expires
        return False
    
    def validate_config_for_type(self) -> bool:
        """
        Validate that config matches the requirements for report_type.
        
        Returns:
            True if valid, False otherwise
        """
        config = self.get_config()
        
        if self.report_type == 'model_analysis':
            return 'model_slug' in config
        elif self.report_type == 'app_analysis':
            return 'app_number' in config
        elif self.report_type == 'tool_analysis':
            # Tool analysis is flexible - all fields are optional
            return True
        
        return False
    
    def to_dict(self, include_file_path: bool = False) -> Dict[str, Any]:
        """Convert model to dictionary."""
        data = {
            'id': self.id,
            'report_id': self.report_id,
            'report_type': self.report_type,
            'title': self.title,
            'description': self.description,
            'config': self.get_config(),
            'format': self.format,
            'file_size': self.file_size,
            'status': self.status,
            'error_message': self.error_message,
            'progress_percent': self.progress_percent,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'summary': self.get_summary(),
            'analysis_task_id': self.analysis_task_id,
            'generated_app_id': self.generated_app_id,
            'is_expired': self.is_expired()
        }
        
        if include_file_path:
            data['file_path'] = self.file_path
        
        return data
    
    def __repr__(self) -> str:
        return f'<Report {self.report_id} ({self.report_type}, {self.status})>'
