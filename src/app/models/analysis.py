"""
Analysis Models (Legacy)
========================

Legacy analysis models for security and performance tests.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class SecurityAnalysis(db.Model):
    """Security analysis results."""
    __tablename__ = 'security_analyses'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, index=True)
    analysis_type: Mapped[str] = mapped_column(db.String(50))
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<SecurityAnalysis {self.id}>"


class PerformanceTest(db.Model):
    """Performance test results."""
    __tablename__ = 'performance_tests'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, index=True)
    test_type: Mapped[str] = mapped_column(db.String(50))
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<PerformanceTest {self.id}>"


class ZAPAnalysis(db.Model):
    """OWASP ZAP analysis results."""
    __tablename__ = 'zap_analyses'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, index=True)
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ZAPAnalysis {self.id}>"


class OpenRouterAnalysis(db.Model):
    """OpenRouter AI analysis results."""
    __tablename__ = 'openrouter_analyses'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(db.Integer, index=True)
    result_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<OpenRouterAnalysis {self.id}>"
