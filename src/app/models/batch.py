"""
Batch Analysis Models
=====================

Models for batch analysis operations.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class BatchAnalysis(db.Model):
    """Batch analysis records."""
    __tablename__ = 'batch_analyses'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_name: Mapped[str] = mapped_column(db.String(200))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(db.String(50), default='pending')
    total_tasks: Mapped[int] = mapped_column(db.Integer, default=0)
    completed_tasks: Mapped[int] = mapped_column(db.Integer, default=0)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    def __repr__(self):
        return f"<BatchAnalysis {self.id} {self.batch_name}>"
