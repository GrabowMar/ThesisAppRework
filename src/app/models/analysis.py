"""
Analysis Models
===============

Database models for storing various types of analysis results including security
analysis, performance testing, ZAP scanning, and AI-powered code analysis.

This module defines SQLAlchemy ORM models that track the execution and results of:
- SecurityAnalysis: Comprehensive security tool configurations and findings
- PerformanceTest: Load testing metrics and performance benchmarks
- ZAPAnalysis: OWASP ZAP security scan results
- OpenRouterAnalysis: AI-powered code quality assessments
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..extensions import db
from ..constants import AnalysisStatus
from ..utils.time import utc_now

class SecurityAnalysis(db.Model):
    """Model for storing security analysis results with comprehensive tool configurations."""
    __tablename__ = 'security_analyses'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    status = db.Column(db.Enum(AnalysisStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AnalysisStatus.PENDING, index=True)
    analysis_name = db.Column(db.String(200), default='Security Analysis')
    description = db.Column(db.Text)
    
    bandit_enabled = db.Column(db.Boolean, default=True)
    bandit_config_json = db.Column(db.Text)
    
    safety_enabled = db.Column(db.Boolean, default=True)
    safety_config_json = db.Column(db.Text)
    
    pylint_enabled = db.Column(db.Boolean, default=True)
    pylint_config_json = db.Column(db.Text)
    
    eslint_enabled = db.Column(db.Boolean, default=True)
    eslint_config_json = db.Column(db.Text)
    
    npm_audit_enabled = db.Column(db.Boolean, default=True)
    npm_audit_config_json = db.Column(db.Text)
    
    snyk_enabled = db.Column(db.Boolean, default=False)
    snyk_config_json = db.Column(db.Text)
    
    zap_enabled = db.Column(db.Boolean, default=False)
    zap_config_json = db.Column(db.Text)
    
    semgrep_enabled = db.Column(db.Boolean, default=False)
    semgrep_config_json = db.Column(db.Text)
    
    severity_threshold = db.Column(db.String(20), default='low')
    max_issues_per_tool = db.Column(db.Integer, default=1000)
    timeout_minutes = db.Column(db.Integer, default=30)
    exclude_patterns = db.Column(db.Text)
    include_patterns = db.Column(db.Text)
    
    total_issues = db.Column(db.Integer, default=0)
    critical_severity_count = db.Column(db.Integer, default=0)
    high_severity_count = db.Column(db.Integer, default=0)
    medium_severity_count = db.Column(db.Integer, default=0)
    low_severity_count = db.Column(db.Integer, default=0)
    tools_run_count = db.Column(db.Integer, default=0)
    tools_failed_count = db.Column(db.Integer, default=0)
    
    analysis_duration = db.Column(db.Float)
    
    results_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    global_config_json = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata JSON as dictionary."""
        if not self.metadata_json:
            return {}
        try:
            data = json.loads(self.metadata_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def set_metadata(self, metadata: Optional[Dict[str, Any]]) -> None:
        """Persist metadata dictionary as JSON."""
        self.metadata_json = json.dumps(metadata or {})

class PerformanceTest(db.Model):
    """Model for storing performance test results."""
    __tablename__ = 'performance_tests'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    status = db.Column(db.Enum(AnalysisStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AnalysisStatus.PENDING, index=True)
    test_type = db.Column(db.String(50), default='load')
    users = db.Column(db.Integer, default=10)
    spawn_rate = db.Column(db.Float, default=1.0)
    test_duration = db.Column(db.Integer, default=60)
    
    requests_per_second = db.Column(db.Float)
    average_response_time = db.Column(db.Float)
    p95_response_time = db.Column(db.Float)
    p99_response_time = db.Column(db.Float)
    error_rate = db.Column(db.Float)
    total_requests = db.Column(db.Integer)
    failed_requests = db.Column(db.Integer)
    
    results_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata JSON as dictionary."""
        if not self.metadata_json:
            return {}
        try:
            data = json.loads(self.metadata_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def set_metadata(self, metadata: Optional[Dict[str, Any]]) -> None:
        """Persist metadata dictionary as JSON."""
        self.metadata_json = json.dumps(metadata or {})

class ZAPAnalysis(db.Model):
    """Model for storing ZAP security analysis results."""
    __tablename__ = 'zap_analyses'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    status = db.Column(db.Enum(AnalysisStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AnalysisStatus.PENDING, index=True)
    target_url = db.Column(db.String(500), nullable=False)
    scan_type = db.Column(db.String(50), default='active')
    
    high_risk_alerts = db.Column(db.Integer, default=0)
    medium_risk_alerts = db.Column(db.Integer, default=0)
    low_risk_alerts = db.Column(db.Integer, default=0)
    informational_alerts = db.Column(db.Integer, default=0)
    
    zap_report_json = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata JSON as dictionary."""
        if not self.metadata_json:
            return {}
        try:
            data = json.loads(self.metadata_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def set_metadata(self, metadata: Optional[Dict[str, Any]]) -> None:
        """Persist metadata dictionary as JSON."""
        self.metadata_json = json.dumps(metadata or {})

    def get_zap_report(self) -> Dict[str, Any]:
        """Return stored ZAP report as dictionary."""
        if not self.zap_report_json:
            return {}
        try:
            data = json.loads(self.zap_report_json)
            return data if isinstance(data, dict) else {}
        except (TypeError, ValueError):
            return {}

    def set_zap_report(self, report: Optional[Dict[str, Any]]) -> None:
        """Persist ZAP report JSON."""
        self.zap_report_json = json.dumps(report or {})

class OpenRouterAnalysis(db.Model):
    """Model for storing OpenRouter AI analysis results."""
    __tablename__ = 'openrouter_analyses'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('generated_applications.id'), nullable=False, index=True)
    
    status = db.Column(db.Enum(AnalysisStatus, native_enum=False, values_callable=lambda obj: [e.value for e in obj]), default=AnalysisStatus.PENDING, index=True)
    analyzer_model = db.Column(db.String(200))
    analysis_prompt = db.Column(db.Text)
    
    overall_score = db.Column(db.Float)
    code_quality_score = db.Column(db.Float)
    security_score = db.Column(db.Float)
    maintainability_score = db.Column(db.Float)
    
    input_tokens = db.Column(db.Integer)
    output_tokens = db.Column(db.Integer)
    cost_usd = db.Column(db.Float)
    
    findings_json = db.Column(db.Text)
    recommendations_json = db.Column(db.Text)
    summary = db.Column(db.Text)
    metadata_json = db.Column(db.Text)
    
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=utc_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=utc_now, onupdate=utc_now)