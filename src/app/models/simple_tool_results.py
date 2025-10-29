"""
Simple Tool Results Models
==========================

Models for storing tool execution results.
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any

from sqlalchemy import Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class ToolResult(db.Model):
    """Individual tool execution results."""
    __tablename__ = 'tool_results'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[str] = mapped_column(db.String(100), index=True)
    tool_name: Mapped[str] = mapped_column(db.String(100), index=True)
    status: Mapped[str] = mapped_column(db.String(50))
    issues_found: Mapped[int] = mapped_column(db.Integer, default=0)
    execution_time: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    raw_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ToolResult {self.tool_name} status={self.status}>"


class ToolSummary(db.Model):
    """Summary of tool execution across tasks."""
    __tablename__ = 'tool_summaries'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    tool_name: Mapped[str] = mapped_column(db.String(100), index=True)
    total_executions: Mapped[int] = mapped_column(db.Integer, default=0)
    successful_executions: Mapped[int] = mapped_column(db.Integer, default=0)
    failed_executions: Mapped[int] = mapped_column(db.Integer, default=0)
    avg_execution_time: Mapped[Optional[float]] = mapped_column(db.Float, nullable=True)
    last_execution_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f"<ToolSummary {self.tool_name}>"
