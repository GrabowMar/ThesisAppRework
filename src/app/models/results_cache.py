"""
Results Cache Models
====================

Models for caching analysis results.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class AnalysisResultsCache(db.Model):
    """Cache for analysis results."""
    __tablename__ = 'analysis_results_cache'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(db.String(100), unique=True, index=True)
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    cached_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    
    def __repr__(self):
        return f"<AnalysisResultsCache {self.task_id}>"
