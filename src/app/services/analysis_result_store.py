"""Utilities for persisting analysis payloads into relational storage.

This module replaces the legacy JsonResultsManager by writing orchestrator
outputs directly into the SQLAlchemy models. It provides helpers that accept an
`AnalysisTask` instance (or task id) and merge the payload into the task record
while synchronising `AnalysisResult` rows for individual findings.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.constants import SeverityLevel
from app.extensions import db
from app.models import AnalysisResult, AnalysisTask


def _json_default(obj: Any) -> str:
    """Fallback JSON encoder that stringifies unknown objects."""
    return str(obj)


def _sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a JSON-serialisable copy of the payload."""
    if not isinstance(payload, dict):
        return {}
    try:
        return json.loads(json.dumps(payload, default=_json_default))
    except (TypeError, ValueError):
        return {}


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    value_str = str(value).strip()
    return value_str or None


def _coerce_severity(value: Any) -> SeverityLevel:
    candidate = str(value or "").lower()
    try:
        return SeverityLevel(candidate)
    except ValueError:
        return SeverityLevel.LOW


def _determine_tool_name(finding: Dict[str, Any]) -> str:
    for key in ("tool", "tool_name", "analyzer", "source"):
        val = finding.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return "unknown"


def _determine_title(finding: Dict[str, Any]) -> str:
    for key in ("title", "message", "description", "rule_id"):
        val = finding.get(key)
        if isinstance(val, str) and val.strip():
            return val
    return "Finding"


def _extract_code_snippet(finding: Dict[str, Any]) -> Optional[str]:
    for key in ("code_snippet", "code", "snippet"):
        value = finding.get(key)
        if isinstance(value, str) and value.strip():
            return value
    raw = finding.get("raw_data")
    if isinstance(raw, dict):
        for key in ("code_snippet", "code", "snippet"):
            nested = raw.get(key)
            if isinstance(nested, str) and nested.strip():
                return nested
    return None


def _extract_raw_output(finding: Dict[str, Any]) -> Optional[str]:
    raw_output = finding.get("raw_output")
    if isinstance(raw_output, str) and raw_output.strip():
        return raw_output
    raw = finding.get("raw_data")
    if isinstance(raw, dict):
        payload = raw.get("raw_output")
        if isinstance(payload, str) and payload.strip():
            return payload
    return None


def _collect_recommendations(finding: Dict[str, Any]) -> List[str]:
    recommendations: List[str] = []
    for key in ("recommendations", "references", "fixes", "next_steps"):
        value = finding.get(key)
        if isinstance(value, list):
            recommendations.extend(str(item) for item in value if item is not None)
        elif isinstance(value, str) and value.strip():
            recommendations.append(value)
    fix = finding.get("fix_suggestion") or finding.get("fix")
    if isinstance(fix, str) and fix.strip():
        recommendations.append(fix)
    return [rec for rec in recommendations if rec]


def _normalise_severity_breakdown(breakdown: Dict[str, Any]) -> Dict[str, int]:
    normalised: Dict[str, int] = {}
    for key, value in breakdown.items():
        coerced = _coerce_int(value)
        if coerced is not None:
            normalised[str(key)] = coerced
    return normalised


def _replace_task_findings(task: AnalysisTask, findings: Any) -> None:
    # Clear existing findings to avoid duplication.
    existing_findings = list(getattr(task, "results", []) or [])
    for existing in existing_findings:
        db.session.delete(existing)

    if not isinstance(findings, list):
        return

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        severity = _coerce_severity(finding.get("severity"))
        line_number = _coerce_int(finding.get("line_number") or finding.get("line"))
        column_number = _coerce_int(finding.get("column"))
        impact_score = _coerce_float(finding.get("impact_score") or finding.get("score"))

        result = AnalysisResult()
        result.result_id = str(uuid.uuid4())
        result.task_id = task.task_id
        result.tool_name = _determine_tool_name(finding)
        result.result_type = str(finding.get("result_type") or "finding")
        result.title = _determine_title(finding)
        result.description = finding.get("description")
        result.severity = severity
        result.confidence = _coerce_str(finding.get("confidence"))
        result.file_path = _coerce_str(finding.get("file_path") or finding.get("filename"))
        result.line_number = line_number
        result.column_number = column_number
        result.code_snippet = _extract_code_snippet(finding)
        result.category = _coerce_str(finding.get("category"))
        result.rule_id = _coerce_str(finding.get("rule_id"))
        result.raw_output = _extract_raw_output(finding)
        result.impact_score = impact_score
        result.business_impact = _coerce_str(finding.get("business_impact"))
        result.remediation_effort = _coerce_str(finding.get("remediation_effort"))

        tags = finding.get("tags")
        if isinstance(tags, list) and tags:
            result.set_tags([str(tag) for tag in tags if tag is not None])

        recommendations = _collect_recommendations(finding)
        if recommendations:
            result.set_recommendations(recommendations)

        structured = finding.get("raw_data")
        if isinstance(structured, dict) and structured:
            result.set_structured_data(structured)
        else:
            result.set_structured_data({k: v for k, v in finding.items() if k != "raw_data"})

        db.session.add(result)


def _apply_summary(task: AnalysisTask, payload: Dict[str, Any], findings: List[Dict[str, Any]]) -> None:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}

    issues = summary.get("total_findings") or summary.get("total_issues")
    if issues is None and findings:
        issues = len(findings)
    if isinstance(issues, int):
        task.issues_found = issues

    breakdown = summary.get("severity_breakdown")
    if isinstance(breakdown, dict):
        normalised = _normalise_severity_breakdown(breakdown)
        if normalised:
            task.set_severity_breakdown(normalised)


def store_analysis_payload(task: AnalysisTask, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Merge orchestrator payload into an existing task.

    Returns the sanitised payload that was stored.
    """
    sanitized = _sanitize_payload(payload)
    task.set_result_summary(sanitized)

    metadata = task.get_metadata() or {}
    metadata["analysis"] = sanitized
    task.set_metadata(metadata)

    raw_findings = sanitized.get("findings")
    findings_list: List[Dict[str, Any]] = []
    if isinstance(raw_findings, list):
        findings_list = [f for f in raw_findings if isinstance(f, dict)]

    _apply_summary(task, sanitized, findings_list)
    _replace_task_findings(task, findings_list)

    task.updated_at = datetime.now(timezone.utc)
    return sanitized


def persist_analysis_payload_by_task_id(task_id: str, payload: Dict[str, Any]) -> bool:
    """Persist payload for the given task id if it exists.

    Returns True when the task was found and updated.
    """
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        return False

    store_analysis_payload(task, payload)
    
    # Also write result files to disk for UI compatibility
    try:
        from .result_file_writer import write_task_result_files
        write_task_result_files(task, payload)
    except Exception as exc:
        # Log but don't fail - database persistence is primary
        from app.utils.logging_config import get_logger
        logger = get_logger(__name__)
        logger.warning(f"Failed to write disk files for task {task_id}: {exc}")
    
    return True


def _get_task_payload_from_task(task: AnalysisTask) -> Dict[str, Any]:
    summary = task.get_result_summary() or {}
    if not summary:
        metadata = task.get_metadata() or {}
        analysis_blob = metadata.get("analysis") if isinstance(metadata, dict) else None
        if isinstance(analysis_blob, dict):
            summary = analysis_blob

    payload = {}
    if isinstance(summary, dict):
        payload = _sanitize_payload(summary)

    payload.setdefault("model_slug", task.target_model)
    payload.setdefault("app_number", task.target_app_number)
    payload.setdefault("task_id", task.task_id)

    analysis_type = getattr(task.analysis_type, "value", None) or str(task.analysis_type)
    payload.setdefault("analysis_type", analysis_type)

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        payload["metadata"] = metadata
    metadata.setdefault("model_slug", task.target_model)
    metadata.setdefault("app_number", task.target_app_number)
    metadata.setdefault("task_id", task.task_id)
    metadata.setdefault("analysis_type", analysis_type)

    return payload


def _serialise_findings(results: Iterable[AnalysisResult]) -> List[Dict[str, Any]]:
    serialised: List[Dict[str, Any]] = []
    for result in results:
        try:
            serialised.append(_sanitize_payload(result.to_dict()))
        except Exception:
            # Best-effort: skip findings that fail to serialise cleanly
            continue
    return serialised


def load_task_payload(
    task_id: str,
    *,
    include_findings: bool = True,
    findings_limit: Optional[int] = None,
    preview_limit: int = 50,
) -> Optional[Dict[str, Any]]:
    """Load the persisted payload for a task with optional findings attachment.

    Returns None when the task does not exist or no payload has been stored yet.
    """

    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if not task:
        return None

    payload = _get_task_payload_from_task(task)
    if not payload:
        return {}

    summary = payload.get("summary")
    if not isinstance(summary, dict):
        summary = {}
        payload["summary"] = summary

    if include_findings:
        query = AnalysisResult.query.filter_by(task_id=task_id).order_by(AnalysisResult.created_at.asc())
        if findings_limit is not None:
            query = query.limit(findings_limit)
        findings = _serialise_findings(query.all())
        payload["findings"] = findings
        if preview_limit > 0:
            payload["findings_preview"] = findings[:preview_limit]
        summary.setdefault("total_findings", len(findings))
        if findings:
            counts: Dict[str, int] = {}
            for finding in findings:
                severity = finding.get("severity") or "unknown"
                counts[severity] = counts.get(severity, 0) + 1
            summary.setdefault("severity_breakdown", counts)

    if "success" not in payload:
        payload["success"] = bool(summary.get("total_findings") is not None and summary.get("status", "completed") == "completed")
    payload.setdefault("derived_status", "completed" if payload.get("success") else "failed")

    return payload


def load_task_findings(task_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return serialised findings for a task."""

    query = AnalysisResult.query.filter_by(task_id=task_id).order_by(AnalysisResult.created_at.asc())
    if limit is not None:
        query = query.limit(limit)
    return _serialise_findings(query.all())


class AnalysisResultStore:
    """File-based compatibility wrapper for legacy tests and tooling.

    Historically, analysis results were persisted as JSON files beneath the
    ``results/`` directory. Modern services store data in the database, but a
    few tests (and possibly external scripts) still rely on the old API. This
    lightweight adapter preserves the interface by serialising dictionaries to
    disk while reusing the new storage layout.
    """

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        project_root = Path(__file__).resolve().parents[3]
        default_dir = project_root / 'results'
        self.base_dir = base_dir or default_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_model_dir(model_slug: str) -> str:
        return model_slug.replace('/', '_').replace('\\', '_')

    def _result_path(self, model_slug: str, app_number: int) -> Path:
        safe_slug = self._safe_model_dir(model_slug)
        return self.base_dir / safe_slug / f'app{app_number}' / 'results.json'

    def save_results(self, model_slug: str, app_number: int, results: Dict[str, Any]) -> bool:
        """Persist results to a JSON file mirroring the legacy structure."""
        path = self._result_path(model_slug, app_number)
        path.parent.mkdir(parents=True, exist_ok=True)
        serialised = json.dumps(results or {}, indent=2, default=_json_default)
        path.write_text(serialised, encoding='utf-8')
        return True

    def load_results(self, model_slug: str, app_number: int) -> Optional[Dict[str, Any]]:
        """Load previously saved results if the JSON file exists."""
        path = self._result_path(model_slug, app_number)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else None
        except (OSError, ValueError, TypeError):
            return None
