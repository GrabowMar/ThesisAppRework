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
from ..models import AnalysisTask


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
            query = query.filter(AnalysisTask.status == status)  # type: ignore[arg-type]
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
        # Prefer a derived status if analyzer indicated success but DB status lags
        try:
            payload = self.get_task_results_payload(task.task_id)
            if isinstance(payload, dict) and payload.get('derived_status'):
                data['derived_status'] = payload.get('derived_status')
        except Exception:
            # Non-fatal if results not yet present or any parsing error occurs
            pass
        return data

    # ------------- Results JSON -------------------------------------------
    def get_task_results_payload(self, task_id: str) -> Dict[str, Any]:
        """Return a consolidated payload for the given task using the SQL store."""

        from .analysis_result_store import load_task_payload, load_task_findings

        task = self.get_task(task_id)
        payload = load_task_payload(task_id, include_findings=True, preview_limit=100) or {}

        # If the DB payload came back empty, fall back to reserialising findings only.
        if not payload:
            payload = {
                'task_id': task.task_id,
                'model_slug': task.target_model,
                'app_number': task.target_app_number,
                'analysis_type': getattr(task.analysis_type, 'value', task.analysis_type),
            }

        # Ensure we always mutate a copy (load_task_payload returns shared dict from SQLAlchemy state).
        payload = dict(payload)

        metadata = payload.setdefault('metadata', {})
        metadata.setdefault('task_id', task.task_id)
        metadata.setdefault('model_slug', task.target_model)
        metadata.setdefault('app_number', task.target_app_number)
        metadata.setdefault('analysis_type', getattr(task.analysis_type, 'value', task.analysis_type))

        payload.setdefault('task_id', task.task_id)
        payload.setdefault('model_slug', task.target_model)
        payload.setdefault('app_number', task.target_app_number)
        payload.setdefault('analysis_type', metadata['analysis_type'])

        summary = payload.setdefault('summary', {})

        findings = payload.get('findings')
        if not isinstance(findings, list):
            findings = load_task_findings(task_id)
            payload['findings'] = findings

        preview = payload.get('findings_preview')
        if not isinstance(preview, list):
            payload['findings_preview'] = findings[:50]
        else:
            payload['findings_preview'] = preview[:50]

        findings_total = payload.get('findings_total')
        if not isinstance(findings_total, int):
            findings_total = len(findings)
            payload['findings_total'] = findings_total

        findings_by_tool = payload.get('findings_by_tool')
        if not isinstance(findings_by_tool, dict):
            findings_by_tool = self._group_findings_by_tool(findings)
            payload['findings_by_tool'] = findings_by_tool

        findings_by_severity = payload.get('findings_by_severity')
        if not isinstance(findings_by_severity, dict):
            findings_by_severity = self._group_findings_by_severity(findings)
            payload['findings_by_severity'] = findings_by_severity

        summary.setdefault('total_findings', findings_total)
        summary.setdefault('severity_breakdown', findings_by_severity)

        tools_used_value = payload.get('tools_used')
        if isinstance(tools_used_value, list):
            tools_used = [tool for tool in tools_used_value if isinstance(tool, str)]
        else:
            tools_used = self._derive_tools_used(payload, findings, task)
        payload['tools_used'] = tools_used

        payload['tools_skipped'] = payload.get('tools_skipped') or self._derive_tools_skipped(payload, tools_used)

        payload['tool_metrics'] = payload.get('tool_metrics') or self._derive_tool_metrics(payload)

        if not payload.get('raw_outputs'):
            payload['raw_outputs'] = self._extract_raw_outputs(payload)

        payload.setdefault('configuration_applied', bool(metadata.get('configuration_applied')))
        payload.setdefault('analysis_time', payload.get('analysis_duration') or metadata.get('analysis_time'))

        db_status = getattr(task.status, 'value', task.status)
        payload['db_status'] = db_status

        derived_status = payload.get('derived_status') or summary.get('analysis_status') or summary.get('status')
        if not derived_status:
            if db_status in {'running', 'pending'}:
                derived_status = db_status
            else:
                derived_status = 'completed' if payload.get('success', True) else 'failed'
        payload['derived_status'] = derived_status
        payload['status'] = derived_status or db_status

        metadata.setdefault('extraction_version', '4.0')
        metadata.setdefault('comprehensive_parsing', True)
        metadata.setdefault('raw_outputs_included', bool(payload.get('raw_outputs')))
        metadata.setdefault('analysis_duration', payload.get('analysis_time'))

        payload.setdefault('severity_breakdown', findings_by_severity)

        return payload

    # ------------- Consolidated file direct loading ---------------------
    def _map_eslint_severity(self, severity: int) -> str:
        """Map ESLint numeric severity to string."""
        return {1: 'warning', 2: 'error'}.get(severity, 'unknown')

    def _derive_tools_used(
        self,
        payload: Dict[str, Any],
        findings: List[Dict[str, Any]],
        task: AnalysisTask,
    ) -> List[str]:
        """Infer the set of tools that participated in an analysis run."""

        ordered: List[str] = []

        def _extend(values: Any) -> None:
            if isinstance(values, (list, tuple, set)):
                for value in values:
                    if not isinstance(value, str):
                        continue
                    name = value.strip()
                    if name and name not in ordered:
                        ordered.append(name)

        # Inspect payload level hints first.
        for key in ('tools_used', 'tools_successful', 'tools_requested'):
            _extend(payload.get(key))

        metadata = payload.get('metadata') or {}
        for key in ('selected_tool_names', 'tools_used', 'tools_requested'):
            _extend(metadata.get(key))

        task_metadata = {}
        try:
            task_metadata = task.get_metadata() or {}
        except Exception:
            task_metadata = {}
        for key in ('selected_tool_names', 'tools_used', 'tools_requested'):
            _extend(task_metadata.get(key))

        # Finally, derive from findings if we still have nothing.
        if not ordered:
            for finding in findings:
                tool = finding.get('tool') or finding.get('tool_name')
                if isinstance(tool, str):
                    tool_name = tool.strip()
                    if tool_name and tool_name not in ordered:
                        ordered.append(tool_name)

        return ordered

    def _derive_tools_skipped(
        self,
        payload: Dict[str, Any],
        tools_used: Optional[List[str]],
    ) -> List[str]:
        """Infer which requested tools did not produce results."""

        used_set = {tool for tool in (tools_used or []) if isinstance(tool, str)}
        requested: List[str] = []

        def _extend(values: Any) -> None:
            if isinstance(values, (list, tuple, set)):
                for value in values:
                    if isinstance(value, str):
                        name = value.strip()
                        if name and name not in requested:
                            requested.append(name)

        for source in (payload, payload.get('metadata') or {}):
            for key in ('tools_requested', 'selected_tool_names'):
                _extend(source.get(key))

        skipped: List[str] = [tool for tool in requested if tool not in used_set]

        tool_results = payload.get('tool_results')
        if isinstance(tool_results, dict):
            for tool_name, info in tool_results.items():
                if not isinstance(tool_name, str):
                    continue
                if tool_name in used_set:
                    continue
                status = ''
                executed = None
                if isinstance(info, dict):
                    status = str(info.get('status') or '').lower()
                    executed = info.get('executed')
                if executed is False or status in {'skipped', 'not_run', 'no_files', 'unavailable', 'error'}:
                    skipped.append(tool_name)

        # Deduplicate while preserving first occurrence order.
        seen: set[str] = set()
        ordered_skipped: List[str] = []
        for tool in skipped:
            if tool not in seen:
                seen.add(tool)
                ordered_skipped.append(tool)
        return ordered_skipped

    def _derive_tool_metrics(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Build a lightweight metrics map from tool result payloads."""

        existing = payload.get('tool_metrics')
        if isinstance(existing, dict) and existing:
            return existing

        tool_results = payload.get('tool_results')
        derived: Dict[str, Any] = {}
        if isinstance(tool_results, dict):
            for tool_name, info in tool_results.items():
                if not isinstance(tool_name, str) or not isinstance(info, dict):
                    continue
                findings = info.get('findings')
                total_issues = info.get('total_issues')
                if isinstance(findings, list):
                    total_issues = total_issues if isinstance(total_issues, int) else len(findings)
                derived[tool_name] = {
                    'status': info.get('status'),
                    'total_issues': total_issues or 0,
                    'duration_seconds': info.get('duration_seconds'),
                    'files_analyzed': info.get('files_analyzed'),
                    'config_used': info.get('config_used'),
                    'metrics': info.get('metrics'),
                    'error': info.get('error'),
                }
        return derived

    def _group_findings_by_tool(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group findings count by tool."""
        groups = {}
        for finding in findings:
            tool = finding.get('tool', 'unknown')
            groups[tool] = groups.get(tool, 0) + 1
        return groups

    def _group_findings_by_severity(self, findings: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group findings count by severity."""
        groups = {}
        for finding in findings:
            severity = finding.get('severity', 'unknown')
            groups[severity] = groups.get(severity, 0) + 1
        return groups

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

    def _extract_raw_outputs(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Extract raw tool outputs from the stored payload."""

        raw_outputs = {}
        candidates: List[Dict[str, Any]] = []

        for key in ('raw_outputs', 'tool_results', 'results', 'metadata'):
            value = payload.get(key)
            if isinstance(value, dict):
                candidates.append(value)

        if isinstance(payload.get('analysis'), dict):
            candidates.append(payload['analysis'])

        for candidate in list(candidates):
            for nested_key in ('results', 'tool_results', 'tools'):
                nested = candidate.get(nested_key)
                if isinstance(nested, dict):
                    candidates.append(nested)

        for candidate in candidates:
            for tool_name, info in candidate.items():
                if not isinstance(tool_name, str) or not isinstance(info, dict):
                    continue
                output_info = self._extract_output_fields(info)
                if output_info and tool_name not in raw_outputs:
                    raw_outputs[tool_name] = output_info

        return raw_outputs

    def _extract_output_fields(self, tool_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract output fields from tool data."""
        output_info = {}
        
        # Universal output field mapping
        output_fields = {
            'raw_output': ['raw_output', 'output', 'stdout', 'result', 'response', 'content'],
            'command_line': ['command_line', 'command', 'cmd', 'executed_command'],
            'exit_code': ['exit_code', 'returncode', 'return_code', 'status_code'],
            'stderr': ['stderr', 'error_output', 'errors'],
            'error': ['error', 'error_message', 'exception'],
            'duration': ['duration', 'duration_seconds', 'execution_time', 'elapsed'],
            'status': ['status', 'state', 'result_status']
        }
        
        for output_key, possible_names in output_fields.items():
            for field_name in possible_names:
                if field_name in tool_data and tool_data[field_name] is not None:
                    # Convert to string if it's not already
                    value = tool_data[field_name]
                    if isinstance(value, (dict, list)):
                        # For complex objects, convert to JSON string
                        import json
                        try:
                            output_info[output_key] = json.dumps(value, indent=2)
                        except Exception:
                            output_info[output_key] = str(value)
                    else:
                        output_info[output_key] = str(value) if value is not None else ""
                    break  # Use first match
        
        return output_info

__all__ = ["AnalysisInspectionService"]
