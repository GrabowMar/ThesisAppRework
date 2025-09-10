"""Analysis Inspection Service
================================

Provides read-only inspection utilities for `AnalysisTask` entities including
listing with filters, detailed task metadata aggregation, and retrieval of
result summary JSON blobs for lazy-loaded UI panels.

Design Goals:
 - No side effects (pure read operations)
 - Uses standardized exceptions from `service_base`
 - Returns ORM objects for list views (templates already expect attribute access)
 - Derives helpful computed fields (durations, elapsed)
 - Safely handles malformed JSON stored in text columns
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import json

from .service_base import NotFoundError, ValidationError
from ..models import AnalysisTask, AnalysisResult


def _ensure_timezone_aware(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware by adding UTC if naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class AnalysisInspectionService:
    """Read-only inspection utilities for analysis tasks."""

    # ------------- Listing -------------------------------------------------
    def list_tasks(
        self,
        *,
        status: Optional[str] = None,
        analysis_type: Optional[str] = None,
        model: Optional[str] = None,
        priority: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AnalysisTask]:
        """List tasks with lightweight filtering.

        Parameters accept raw enum values (e.g., 'pending', 'security').
        A small textual search is supported against task_id and task_name.
        """
        query = AnalysisTask.query
        if status:
            query = query.filter(AnalysisTask.status == status)
        if analysis_type:
            query = query.filter(AnalysisTask.analysis_type == analysis_type)
        if model:
            query = query.filter(AnalysisTask.target_model == model)
        if priority:
            query = query.filter(AnalysisTask.priority == priority)
        if search:
            like = f"%{search}%"
            query = query.filter(
                (AnalysisTask.task_id.ilike(like)) | (AnalysisTask.task_name.ilike(like))
            )
        return query.order_by(AnalysisTask.created_at.desc()).offset(offset).limit(limit).all()

    # ------------- Single Task --------------------------------------------
    def get_task(self, task_id: str) -> AnalysisTask:
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            raise NotFoundError(f"AnalysisTask not found: {task_id}")
        return task

    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        """Return enriched dictionary representation of a task."""
        task = self.get_task(task_id)
        data = task.to_dict()
        now = datetime.now(timezone.utc)
        
        # Derived durations - ensure all datetimes are timezone-aware
        if task.started_at and not task.completed_at:
            started_aware = _ensure_timezone_aware(task.started_at)
            data['elapsed_seconds'] = (now - started_aware).total_seconds()
        if task.started_at and task.completed_at:
            started_aware = _ensure_timezone_aware(task.started_at)
            completed_aware = _ensure_timezone_aware(task.completed_at)
            data['elapsed_seconds'] = (completed_aware - started_aware).total_seconds()
        if task.created_at:
            created_aware = _ensure_timezone_aware(task.created_at)
            data['age_seconds'] = (now - created_aware).total_seconds()
        # Provide simplified status flags
        status_val = data.get('status') or ''
        data['is_active'] = status_val in ('running', 'pending')
        data['is_finished'] = status_val in ('completed', 'failed', 'cancelled')
        data['has_error'] = bool(task.error_message)
        # Count attached results (if any)
        data['results_count'] = len(getattr(task, 'results', []) or [])
        return data

    # ------------- Results JSON -------------------------------------------
    def get_task_results_payload(self, task_id: str) -> Dict[str, Any]:
        """Return structured JSON payload combining summary + findings.

        For large result sets we only include counts (caller can page future route).
        """
        task = self.get_task(task_id)
        
        # Extract analysis results from task metadata
        metadata = task.get_metadata()
        analysis_data = metadata.get('analysis', {})
        
        # Build summary from metadata
        summary = analysis_data.get('summary', {})
        
        # Extract severity breakdown
        severity = summary.get('severity_breakdown', {})
        
        # Extract findings from the nested analysis results structure
        findings: List[Dict[str, Any]] = []
        total_issues = 0
        
        if 'results' in analysis_data:
            results = analysis_data['results']
            
            # Process Python tool results (bandit, pylint, etc.)
            if 'python' in results:
                python_results = results['python']
                
                # Process Bandit issues
                if 'bandit' in python_results and 'issues' in python_results['bandit']:
                    for issue in python_results['bandit']['issues'][:25]:  # Limit to first 25
                        findings.append({
                            'tool': 'bandit',
                            'severity': issue.get('issue_severity', 'unknown').lower(),
                            'title': issue.get('issue_text', 'Security issue'),
                            'category': issue.get('test_name', 'security'),
                            'file_path': issue.get('filename', '').replace('/app/sources/', ''),
                            'line_number': issue.get('line_number'),
                            'message': issue.get('issue_text', ''),
                            'test_id': issue.get('test_id'),
                            'confidence': issue.get('issue_confidence', 'unknown').lower()
                        })
                
                # Process PyLint issues  
                if 'pylint' in python_results and 'issues' in python_results['pylint']:
                    for issue in python_results['pylint']['issues'][:25]:  # Limit to first 25
                        findings.append({
                            'tool': 'pylint',
                            'severity': issue.get('type', 'unknown').lower(),
                            'title': issue.get('message', 'Code quality issue'),
                            'category': issue.get('symbol', 'code-quality'),
                            'file_path': issue.get('path', ''),
                            'line_number': issue.get('line'),
                            'message': issue.get('message', ''),
                            'symbol': issue.get('symbol'),
                            'message_id': issue.get('message-id')
                        })
            
            # Process JavaScript tool results
            if 'javascript' in results:
                js_results = results['javascript']
                if 'eslint' in js_results and 'issues' in js_results['eslint']:
                    for issue in js_results['eslint']['issues'][:25]:
                        findings.append({
                            'tool': 'eslint',
                            'severity': issue.get('severity', 'unknown').lower(),
                            'title': issue.get('message', 'JavaScript issue'),
                            'category': issue.get('ruleId', 'javascript'),
                            'file_path': issue.get('filePath', ''),
                            'line_number': issue.get('line'),
                            'message': issue.get('message', ''),
                            'rule_id': issue.get('ruleId')
                        })
        
        # Calculate total issues from summary or count findings
        total_issues = summary.get('total_issues_found', len(findings))
        
        payload = {
            'task_id': task.task_id,
            'status': getattr(task.status, 'value', task.status),
            'analysis_type': getattr(task.analysis_type, 'value', task.analysis_type),
            'summary': summary,
            'severity_breakdown': severity,
            'findings_preview': findings,
            'findings_total': total_issues
        }
        return payload

    def get_task_results_json(self, task_id: str) -> str:
        """Return pretty JSON string for UI rendering."""
        try:
            payload = self.get_task_results_payload(task_id)
        except NotFoundError:
            raise
        try:
            return json.dumps(payload, indent=2, sort_keys=True)
        except Exception as e:  # pragma: no cover - defensive
            raise ValidationError(f"Failed to serialize results: {e}")

__all__ = ["AnalysisInspectionService"]
