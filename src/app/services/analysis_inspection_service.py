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
        # Derived durations
        if task.started_at and not task.completed_at:
            data['elapsed_seconds'] = (now - task.started_at).total_seconds()
        if task.started_at and task.completed_at:
            data['elapsed_seconds'] = (task.completed_at - task.started_at).total_seconds()
        if task.created_at:
            data['age_seconds'] = (now - task.created_at).total_seconds()
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
        summary = task.get_result_summary() if hasattr(task, 'get_result_summary') else {}
        severity = task.get_severity_breakdown() if hasattr(task, 'get_severity_breakdown') else {}
        findings: List[Dict[str, Any]] = []
        # Only include up to 50 findings inline to prevent huge HTML payloads
        for r in (task.results or [])[:50]:  # type: ignore[attr-defined]
            try:
                findings.append({
                    'id': r.id,
                    'result_id': r.result_id,
                    'tool': r.tool_name,
                    'severity': getattr(r.severity, 'value', r.severity),
                    'title': r.title,
                    'category': r.category,
                    'file_path': r.file_path,
                })
            except Exception:
                pass
        payload = {
            'task_id': task.task_id,
            'status': getattr(task.status, 'value', task.status),
            'analysis_type': getattr(task.analysis_type, 'value', task.analysis_type),
            'summary': summary,
            'severity_breakdown': severity,
            'findings_preview': findings,
            'findings_total': len(task.results or [])  # type: ignore[attr-defined]
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
