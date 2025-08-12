"""
Analysis Configuration Models
=============================

Database models for storing analyzer configurations and settings.
"""

from datetime import datetime, timezone
from typing import Dict, Any
import json

from ..extensions import db


def utc_now() -> datetime:
    """Get current UTC time - replacement for deprecated datetime.utcnow()"""
    return datetime.now(timezone.utc)


class AnalysisConfig(db.Model):
    """Model for storing analysis tool configurations."""
    __tablename__ = 'analysis_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    config_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, ai
    
    # Configuration data as JSON
    config_data = db.Column(db.Text, nullable=False)
    
    # Metadata
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    tags = db.Column(db.Text)  # JSON array of tags
    
    # Version tracking
    version = db.Column(db.String(20), default='1.0.0')
    parent_config_id = db.Column(db.Integer, db.ForeignKey('analysis_configs.id'), nullable=True)
    
    # Usage tracking
    usage_count = db.Column(db.Integer, default=0)
    last_used = db.Column(db.DateTime)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    # Relationships
    child_configs = db.relationship('AnalysisConfig', 
                                  backref=db.backref('parent_config', remote_side=[id]),
                                  lazy=True)
    
    def get_config_data(self) -> Dict[str, Any]:
        """Get configuration data as dictionary."""
        if self.config_data:
            try:
                return json.loads(self.config_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_config_data(self, config_dict: Dict[str, Any]) -> None:
        """Set configuration data from dictionary."""
        self.config_data = json.dumps(config_dict, indent=2)
    
    def get_tags(self) -> list:
        """Get tags as list."""
        if self.tags:
            try:
                return json.loads(self.tags)
            except json.JSONDecodeError:
                return []
        return []
    
    def set_tags(self, tags_list: list) -> None:
        """Set tags from list."""
        self.tags = json.dumps(tags_list)
    
    def increment_usage(self) -> None:
        """Increment usage count and update last used timestamp."""
        self.usage_count += 1
        self.last_used = utc_now()
    
    def create_child_config(self, name: str, description: str = "") -> 'AnalysisConfig':
        """Create a child configuration based on this one."""
        child = AnalysisConfig(
            name=name,
            description=description,
            config_type=self.config_type,
            config_data=self.config_data,
            parent_config_id=self.id,
            version="1.0.0"
        )
        return child
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'config_type': self.config_type,
            'config_data': self.get_config_data(),
            'is_default': self.is_default,
            'is_active': self.is_active,
            'tags': self.get_tags(),
            'version': self.version,
            'parent_config_id': self.parent_config_id,
            'usage_count': self.usage_count,
            'last_used': self.last_used,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<AnalysisConfig {self.name} ({self.config_type})>'


class ConfigPreset(db.Model):
    """Model for storing predefined configuration presets."""
    __tablename__ = 'config_presets'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), nullable=False, index=True)  # quick_scan, comprehensive, etc.
    config_type = db.Column(db.String(50), nullable=False, index=True)  # security, performance, ai
    
    # Preset configuration
    preset_data = db.Column(db.Text, nullable=False)
    
    # Metadata
    is_system_preset = db.Column(db.Boolean, default=True)  # System vs user-created
    is_public = db.Column(db.Boolean, default=True)
    difficulty_level = db.Column(db.String(20), default='beginner')  # beginner, intermediate, advanced
    estimated_duration = db.Column(db.Integer)  # Estimated runtime in minutes
    
    # Usage tracking
    usage_count = db.Column(db.Integer, default=0)
    rating_sum = db.Column(db.Integer, default=0)
    rating_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=utc_now)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now)
    
    def get_preset_data(self) -> Dict[str, Any]:
        """Get preset data as dictionary."""
        if self.preset_data:
            try:
                return json.loads(self.preset_data)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_preset_data(self, preset_dict: Dict[str, Any]) -> None:
        """Set preset data from dictionary."""
        self.preset_data = json.dumps(preset_dict, indent=2)
    
    def get_average_rating(self) -> float:
        """Get average rating."""
        if self.rating_count > 0:
            return self.rating_sum / self.rating_count
        return 0.0
    
    def add_rating(self, rating: int) -> None:
        """Add a rating (1-5)."""
        if 1 <= rating <= 5:
            self.rating_sum += rating
            self.rating_count += 1
    
    def increment_usage(self) -> None:
        """Increment usage count."""
        self.usage_count += 1
    
    def to_config(self) -> AnalysisConfig:
        """Convert preset to an AnalysisConfig instance."""
        return AnalysisConfig(
            name=f"{self.name} (from preset)",
            description=self.description,
            config_type=self.config_type,
            config_data=self.preset_data
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'config_type': self.config_type,
            'preset_data': self.get_preset_data(),
            'is_system_preset': self.is_system_preset,
            'is_public': self.is_public,
            'difficulty_level': self.difficulty_level,
            'estimated_duration': self.estimated_duration,
            'usage_count': self.usage_count,
            'average_rating': self.get_average_rating(),
            'rating_count': self.rating_count,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    def __repr__(self) -> str:
        return f'<ConfigPreset {self.name} ({self.config_type})>'
