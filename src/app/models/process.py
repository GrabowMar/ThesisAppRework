"""
Process Tracking Models
=======================

Models for tracking background processes.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class ProcessTracking(db.Model):
    """Background process tracking."""
    __tablename__ = 'process_tracking'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    process_id: Mapped[str] = mapped_column(db.String(100), unique=True, index=True)
    process_type: Mapped[str] = mapped_column(db.String(50))
    status: Mapped[str] = mapped_column(db.String(50), default='running')
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ProcessTracking {self.process_id}>"
