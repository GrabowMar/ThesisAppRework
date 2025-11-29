"""
Results Cache Models
==================

Database models for caching transformed analysis results to improve
performance and provide better user experience.
"""

from __future__ import annotations
from typing import Dict, Any, Optional
import json
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, Float, Boolean, JSON

from ..extensions import db


class AnalysisResultsCache(db.Model):
    """Cache table for transformed analysis results."""
    
    __tablename__ = 'analysis_results_cache'
    
    id = Column(Integer, primary_key=True)
    task_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Basic metadata
    status = Column(String(50), nullable=False)
    analysis_type = Column(String(50), nullable=False)
    model_slug = Column(String(255), nullable=False)
    app_number = Column(Integer, nullable=False)
    
    # Timing information
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    analysis_timestamp = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Summary statistics
    total_findings = Column(Integer, default=0)
    tools_executed_count = Column(Integer, default=0)
    tools_failed_count = Column(Integer, default=0)
    
    # Transformed data (JSON fields)
    security_data = Column(JSON, nullable=True)
    performance_data = Column(JSON, nullable=True)
    quality_data = Column(JSON, nullable=True) 
    requirements_data = Column(JSON, nullable=True)
    
    # Raw API response (for debugging/fallback)
    raw_api_data = Column(Text, nullable=True)
    
    # Cache metadata
    cache_version = Column(String(20), default='1.0')
    is_stale = Column(Boolean, default=False)
    last_api_fetch = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f'<AnalysisResultsCache {self.task_id}>'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'analysis_type': self.analysis_type,
            'model_slug': self.model_slug,
            'app_number': self.app_number,
            'created_at': self.created_at.isoformat() if self.created_at is not None else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at is not None else None,
            'analysis_timestamp': self.analysis_timestamp.isoformat() if self.analysis_timestamp is not None else None,
            'duration_seconds': self.duration_seconds,
            'total_findings': self.total_findings,
            'tools_executed_count': self.tools_executed_count,
            'tools_failed_count': self.tools_failed_count,
            'security_data': self.security_data,
            'performance_data': self.performance_data,
            'quality_data': self.quality_data,
            'requirements_data': self.requirements_data,
            'cache_version': self.cache_version,
            'is_stale': self.is_stale,
            'last_api_fetch': self.last_api_fetch.isoformat() if self.last_api_fetch is not None else None
        }
    
    def get_raw_data(self) -> Optional[Dict[str, Any]]:
        """Get parsed raw API data."""
        try:
            if self.raw_api_data is not None:
                return json.loads(str(self.raw_api_data))
            return None
        except (json.JSONDecodeError, TypeError):
            return None
    
    def set_raw_data(self, data: Dict[str, Any]) -> None:
        """Set raw API data as JSON string."""
        if data:
            self.raw_api_data = json.dumps(data, default=str)
        else:
            self.raw_api_data = None
    
    @classmethod
    def from_analysis_results(cls, results) -> 'AnalysisResultsCache':
        """Create cache entry from AnalysisResults object."""
        cache_entry = cls()
        cache_entry.task_id = results.task_id
        cache_entry.status = results.status
        cache_entry.analysis_type = results.analysis_type
        cache_entry.model_slug = results.model_slug
        cache_entry.app_number = results.app_number
        cache_entry.analysis_timestamp = results.timestamp
        cache_entry.duration_seconds = results.duration
        cache_entry.total_findings = results.total_findings
        cache_entry.tools_executed_count = len(results.tools_executed)
        cache_entry.tools_failed_count = len(results.tools_failed)
        cache_entry.security_data = results.security
        cache_entry.performance_data = results.performance
        cache_entry.quality_data = results.quality
        cache_entry.requirements_data = results.requirements
        cache_entry.last_api_fetch = datetime.now(timezone.utc)
        cache_entry.set_raw_data(results.raw_data)
        return cache_entry


