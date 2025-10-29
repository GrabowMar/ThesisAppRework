"""
Cache Models
============

Models for caching external data.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class OpenRouterModelCache(db.Model):
    """Cache for OpenRouter model information."""
    __tablename__ = 'openrouter_model_cache'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[str] = mapped_column(db.String(200), unique=True, index=True)
    model_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    def __repr__(self):
        return f"<OpenRouterModelCache {self.model_id}>"


class ExternalModelInfoCache(db.Model):
    """Cache for external model information."""
    __tablename__ = 'external_model_info_cache'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    model_id: Mapped[str] = mapped_column(db.String(200), unique=True, index=True)
    source: Mapped[str] = mapped_column(db.String(100))
    info_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    def __repr__(self):
        return f"<ExternalModelInfoCache {self.model_id}>"
