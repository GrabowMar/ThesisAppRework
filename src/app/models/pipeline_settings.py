"""
Pipeline Settings Model
========================

Stores saved automation pipeline configurations per user.
Allows users to save, load, and reuse pipeline settings.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from ..extensions import db


class PipelineSettings(db.Model):
    """
    Pipeline settings model for storing user-defined automation configurations.
    
    Stores the full pipeline configuration including generation, analysis,
    and report settings so users can quickly reuse common configurations.
    """
    
    __tablename__ = 'pipeline_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # Settings metadata
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, default=False, nullable=False)
    
    # Pipeline configuration (stored as JSON)
    config = db.Column(db.JSON, nullable=False, default=dict)
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship to User
    user = db.relationship('User', backref=db.backref('pipeline_settings', lazy='dynamic'))
    
    def __init__(self, user_id: int, name: str, config: Dict[str, Any], description: Optional[str] = None):
        """Initialize a new pipeline settings instance."""
        self.user_id = user_id
        self.name = name
        self.config = config
        self.description = description
    
    def __repr__(self) -> str:
        return f'<PipelineSettings {self.name} (user_id={self.user_id})>'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'description': self.description,
            'is_default': self.is_default,
            'config': self.config,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    @classmethod
    def get_user_settings(cls, user_id: int) -> List['PipelineSettings']:
        """Get all settings for a user."""
        return cls.query.filter_by(user_id=user_id).order_by(cls.name).all()
    
    @classmethod
    def get_by_id(cls, settings_id: int, user_id: int) -> Optional['PipelineSettings']:
        """Get settings by ID for a specific user."""
        return cls.query.filter_by(id=settings_id, user_id=user_id).first()
    
    @classmethod
    def get_default(cls, user_id: int) -> Optional['PipelineSettings']:
        """Get the default settings for a user."""
        return cls.query.filter_by(user_id=user_id, is_default=True).first()
    
    def set_as_default(self) -> None:
        """Set this settings as the default for the user."""
        # Clear other defaults first
        PipelineSettings.query.filter_by(
            user_id=self.user_id, 
            is_default=True
        ).update({'is_default': False})
        
        self.is_default = True
        db.session.commit()
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """Update the configuration."""
        self.config = config
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def delete(self) -> None:
        """Delete this settings instance."""
        db.session.delete(self)
        db.session.commit()
