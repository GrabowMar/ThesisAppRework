"""
Cache-related database models.
"""
import json
from datetime import timedelta
from typing import Dict, Any
from ..extensions import db

from ..utils.time import utc_now

class OpenRouterModelCache(db.Model):
    """Model for caching OpenRouter API model data to reduce API calls."""
    __tablename__ = 'openrouter_model_cache'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    model_id = db.Column(db.String(200), unique=True, nullable=False, index=True)
    
    # Cached data from OpenRouter API
    model_data_json = db.Column(db.Text, nullable=False)  # Full OpenRouter model data
    
    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fetch_duration = db.Column(db.Float)  # Time taken to fetch from API
    api_response_status = db.Column(db.Integer)  # HTTP status code
    
    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    last_accessed = db.Column(db.DateTime(timezone=True), default=utc_now)  # Track usage
    
    def get_model_data(self) -> Dict[str, Any]:
        """Get cached model data as dictionary."""
        if self.model_data_json:
            try:
                return json.loads(self.model_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_model_data(self, model_dict: Dict[str, Any]) -> None:
        """Set model data from dictionary."""
        self.model_data_json = json.dumps(model_dict)
    
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return utc_now() > self.cache_expires_at
    
    def mark_accessed(self) -> None:
        """Update last accessed timestamp."""
        self.last_accessed = utc_now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'model_id': self.model_id,
            'model_data': self.get_model_data(),
            'cache_expires_at': self.cache_expires_at,
            'fetch_duration': self.fetch_duration,
            'api_response_status': self.api_response_status,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_accessed': self.last_accessed,
            'is_expired': self.is_expired()
        }
    
    def __repr__(self) -> str:
        return f'<OpenRouterModelCache {self.model_id}>'


class ExternalModelInfoCache(db.Model):
    """Cache for external model info (primarily OpenRouter).

    Keyed by canonical model slug, stores JSON payload and expiry.
    """
    __tablename__ = 'external_model_info_cache'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    model_slug = db.Column(db.String(200), unique=True, nullable=False, index=True)

    # Cached merged JSON payload
    merged_json = db.Column(db.Text, nullable=False)

    # Cache metadata
    cache_expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    last_refreshed = db.Column(db.DateTime(timezone=True), default=utc_now)
    source_notes = db.Column(db.String(200))  # e.g., "openrouter+hf"

    # Timestamps
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_data(self) -> Dict[str, Any]:
        try:
            return json.loads(self.merged_json) if self.merged_json else {}
        except json.JSONDecodeError:
            return {}

    def set_data(self, data: Dict[str, Any]) -> None:
        self.merged_json = json.dumps(data)

    def is_expired(self) -> bool:
        return utc_now() > self.cache_expires_at

    def mark_refreshed(self, ttl_hours: int) -> None:
        self.last_refreshed = utc_now()
        self.cache_expires_at = utc_now().replace(microsecond=0) + timedelta(hours=ttl_hours)

    def __repr__(self) -> str:
        return f'<ExternalModelInfoCache {self.model_slug}>'
