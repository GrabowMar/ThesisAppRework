"""
Container Models
================

Models for containerized test results.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class ContainerizedTest(db.Model):
    """Containerized test results."""
    __tablename__ = 'containerized_tests'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, index=True)
    container_id: Mapped[Optional[str]] = mapped_column(db.String(200), nullable=True)
    test_type: Mapped[str] = mapped_column(db.String(50))
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ContainerizedTest {self.id}>"
