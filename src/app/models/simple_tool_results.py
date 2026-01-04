"""
Simplified Tool Results Database Models
======================================

Simple database models for storing tool results efficiently.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, Float, DateTime
from sqlalchemy.orm import relationship
import json
from datetime import datetime
from typing import Dict, Any, Optional

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
    
    def __init__(
        self,
        *,
        task_id: str = "",
        tool_name: str = "",
        display_name: Optional[str] = None,
        description: Optional[str] = None,
        category: Optional[str] = None,
        icon: Optional[str] = None,
        status: Optional[str] = None,
        executed: bool = False,
        duration_seconds: Optional[float] = None,
        exit_code: Optional[int] = None,
        total_issues: int = 0,
        error_message: Optional[str] = None,
        has_output: bool = False,
        in_summary_used: bool = False,
        in_summary_failed: bool = False,
        raw_data: Optional[str] = None,
        created_at: Optional[datetime] = None,
        **kwargs: Any
    ) -> None:
        """Initialize ToolResult with typed parameters."""
        init_kwargs = {
            'task_id': task_id,
            'tool_name': tool_name,
            'display_name': display_name,
            'description': description,
            'category': category,
            'icon': icon,
            'status': status,
            'executed': executed,
            'duration_seconds': duration_seconds,
            'exit_code': exit_code,
            'total_issues': total_issues,
            'error_message': error_message,
            'has_output': has_output,
            'in_summary_used': in_summary_used,
            'in_summary_failed': in_summary_failed,
            'raw_data': raw_data,
            'created_at': created_at,
            **kwargs
        }
        # Filter out None values for optional fields
        filtered_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
        super().__init__(**filtered_kwargs)
    
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
    
    def __init__(
        self,
        *,
        task_id: str = "",
        total_tools: int = 0,
        executed_tools: int = 0,
        successful_tools: int = 0,
        failed_tools: int = 0,
        not_available_tools: int = 0,
        total_issues_found: int = 0,
        tools_data: Optional[str] = None,
        created_at: Optional[datetime] = None,
        **kwargs: Any
    ) -> None:
        """Initialize ToolSummary with typed parameters."""
        init_kwargs = {
            'task_id': task_id,
            'total_tools': total_tools,
            'executed_tools': executed_tools,
            'successful_tools': successful_tools,
            'failed_tools': failed_tools,
            'not_available_tools': not_available_tools,
            'total_issues_found': total_issues_found,
            'tools_data': tools_data,
            'created_at': created_at,
            **kwargs
        }
        # Filter out None values for optional fields
        filtered_kwargs = {k: v for k, v in init_kwargs.items() if v is not None}
        super().__init__(**filtered_kwargs)
    
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