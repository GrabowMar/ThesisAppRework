"""
Simplified Tool Results Database Models
======================================

Simple database models for storing tool results efficiently.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime
from sqlalchemy.orm import relationship
import json
from typing import Dict, Any

from ..extensions import db
from ..utils.time import utc_now


class ToolResult(db.Model):
    """Simple tool execution results storage."""
    
    __tablename__ = 'tool_results'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(100), nullable=False, index=True)
    tool_name = Column(String(100), nullable=False)
    display_name = Column(String(150))
    description = Column(Text)
    category = Column(String(50))
    icon = Column(String(50))
    status = Column(String(20))
    executed = Column(Boolean, default=False)
    duration_seconds = Column(Float)
    exit_code = Column(Integer)
    total_issues = Column(Integer, default=0)
    error_message = Column(Text)
    has_output = Column(Boolean, default=False)
    in_summary_used = Column(Boolean, default=False)
    in_summary_failed = Column(Boolean, default=False)
    raw_data = Column(Text)  # JSON storage for all data
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    def get_raw_data(self) -> Dict[str, Any]:
        """Get raw data as dictionary."""
        if self.raw_data is not None:
            try:
                return json.loads(str(self.raw_data))
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_raw_data(self, data: Dict[str, Any]) -> None:
        """Set raw data from dictionary."""
        self.raw_data = json.dumps(data)


class ToolSummary(db.Model):
    """Summary of tool execution for a task."""
    
    __tablename__ = 'tool_summaries'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(100), nullable=False, unique=True, index=True)
    total_tools = Column(Integer, default=0)
    executed_tools = Column(Integer, default=0)
    successful_tools = Column(Integer, default=0)
    failed_tools = Column(Integer, default=0)
    not_available_tools = Column(Integer, default=0)
    total_issues_found = Column(Integer, default=0)
    tools_data = Column(Text)  # JSON for tool lists and categories
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    def get_tools_data(self) -> Dict[str, Any]:
        """Get tools data as dictionary."""
        if self.tools_data is not None:
            try:
                return json.loads(str(self.tools_data))
            except json.JSONDecodeError:
                return {}
        return {}
    
    def set_tools_data(self, data: Dict[str, Any]) -> None:
        """Set tools data from dictionary."""
        self.tools_data = json.dumps(data)