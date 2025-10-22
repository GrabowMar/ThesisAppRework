"""Utilities for reading stored analysis result files from the results directory."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app

from app.paths import PROJECT_ROOT


@dataclass
class ResultFileDescriptor:
    """Metadata describing a stored analysis result JSON file."""

    identifier: str
    model_slug: str
    app_number: int
    analysis_type: str
    timestamp: datetime
    status: str
    total_findings: Optional[int]
    severity_breakdown: Dict[str, int] = field(default_factory=dict)
    tools_executed: Optional[int] = None
    tools_failed: Optional[int] = None
    tools_used: List[str] = field(default_factory=list)
    path: Path = field(default_factory=Path)

    def display_timestamp(self) -> str:
        return self.timestamp.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if self.timestamp else "-"


class ResultFileService:
    """Helper for discovering and loading analysis result files."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self.base_dir = base_dir or self._resolve_base_dir()

    def _resolve_base_dir(self) -> Path:
        configured = current_app.config.get('RESULTS_DIR', 'results') if current_app else 'results'
        base_path = Path(configured)
        if not base_path.is_absolute():
            base_path = PROJECT_ROOT / base_path
        return base_path

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def list_results(self, model_slug: Optional[str] = None, app_number: Optional[int] = None) -> List[ResultFileDescriptor]:
        """Return descriptors for all result files, optionally filtered."""
        descriptors: List[ResultFileDescriptor] = []
        for path in self.base_dir.glob('*/*/analysis/*.json'):
            descriptor = self._build_descriptor(path)
            if model_slug and descriptor.model_slug != model_slug:
                continue
            if app_number is not None and descriptor.app_number != app_number:
                continue
            descriptors.append(descriptor)
        descriptors.sort(key=lambda item: item.timestamp, reverse=True)
        return descriptors

    def find_path_by_identifier(self, identifier: str) -> Optional[Path]:
        """Return the path to the result file matching the given identifier."""
        if not identifier:
            return None
        pattern = f"**/{identifier}.json"
        for path in self.base_dir.glob(pattern):
            return path
        return None

    def load_result_by_identifier(self, identifier: str) -> tuple[ResultFileDescriptor, Dict[str, Any]]:
        path = self.find_path_by_identifier(identifier)
        if not path or not path.exists():
            raise FileNotFoundError(identifier)
        payload = self._load_json(path)
        descriptor = self._build_descriptor(path, payload)
        return descriptor, payload

    def load_descriptor(self, identifier: str) -> ResultFileDescriptor:
        path = self.find_path_by_identifier(identifier)
        if not path or not path.exists():
            raise FileNotFoundError(identifier)
        return self._build_descriptor(path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_descriptor(self, path: Path, payload: Optional[Dict[str, Any]] = None) -> ResultFileDescriptor:
        data = payload or self._load_json(path)

        metadata: Dict[str, Any] = {}
        results: Dict[str, Any] = {}
        summary: Dict[str, Any] = {}
        task_info: Dict[str, Any] = {}

        if isinstance(data, dict):
            raw_metadata = data.get('metadata')
            if isinstance(raw_metadata, dict):
                metadata = raw_metadata
            raw_results = data.get('results')
            if isinstance(raw_results, dict):
                results = raw_results
                raw_summary = results.get('summary')
                if isinstance(raw_summary, dict):
                    summary = raw_summary
                raw_task = results.get('task')
                if isinstance(raw_task, dict):
                    task_info = raw_task

        model_slug = metadata.get('model_slug') or path.parent.parent.parent.name
        app_dir = path.parent.parent.name  # app<number>
        app_number = _extract_app_number(app_dir)
        analysis_type = metadata.get('analysis_type') or task_info.get('analysis_type') or _infer_analysis_type(path)

        timestamp = _parse_timestamp(
            metadata.get('timestamp')
            or task_info.get('completed_at')
            or task_info.get('started_at')
            or None,
            fallback=path.stat().st_mtime,
        )

        total_findings = summary.get('total_findings') if isinstance(summary, dict) else None
        if total_findings is None and isinstance(summary, dict):
            total_findings = summary.get('total_issues')

        severity_breakdown: Dict[str, int] = {}
        if isinstance(summary, dict):
            severity = summary.get('severity_breakdown')
            if isinstance(severity, dict):
                severity_breakdown = {str(k): int(v) for k, v in severity.items() if _is_int_like(v)}

        tools_executed = summary.get('tools_executed') if isinstance(summary, dict) else None
        tools_failed = summary.get('tools_failed') if isinstance(summary, dict) else None
        tools_used = summary.get('tools_used') if isinstance(summary, dict) else []
        if not isinstance(tools_used, list):
            tools_used = []

        status = summary.get('status') if isinstance(summary, dict) else None
        if not isinstance(status, str) or not status:
            status = task_info.get('status') if isinstance(task_info, dict) else None
        if not isinstance(status, str) or not status:
            status = 'unknown'

        identifier = path.stem

        return ResultFileDescriptor(
            identifier=identifier,
            model_slug=model_slug,
            app_number=app_number,
            analysis_type=analysis_type,
            timestamp=timestamp,
            status=status,
            total_findings=total_findings,
            severity_breakdown=severity_breakdown,
            tools_executed=_coerce_optional_int(tools_executed),
            tools_failed=_coerce_optional_int(tools_failed),
            tools_used=[str(tool) for tool in tools_used],
            path=path,
        )

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        data = json.loads(path.read_text(encoding='utf-8'))
        return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------


def _extract_app_number(app_folder_name: str) -> int:
    if app_folder_name.lower().startswith('app'):
        remainder = app_folder_name[3:]
        if remainder.isdigit():
            return int(remainder)
    try:
        return int(app_folder_name)
    except (TypeError, ValueError):
        return 0


def _infer_analysis_type(path: Path) -> str:
    parts = path.stem.split('_')
    if len(parts) >= 3:
        # filename: <model_slug>_app<number>_<analysis_type>_<timestamp>
        return parts[-2]
    return 'analysis'


def _parse_timestamp(value: Optional[str], fallback: float) -> datetime:
    if isinstance(value, str) and value:
        candidate = value.strip()
        if candidate.endswith('Z'):
            candidate = candidate.replace('Z', '+00:00')
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
    return datetime.fromtimestamp(fallback, tz=timezone.utc)


def _coerce_optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Payload analysis helpers exposed for templates/routes
# ---------------------------------------------------------------------------


def collect_findings_from_payload(payload: Dict[str, Any], limit: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return a flattened list of findings extracted from the payload."""

    findings: List[Dict[str, Any]] = []

    def _record(item: Dict[str, Any], context: Dict[str, Optional[str]]) -> None:
        if limit is not None and len(findings) >= limit:
            return

        message_candidates = [
            item.get('message'),
            item.get('issue_text'),
            item.get('title'),
            item.get('description'),
            item.get('check_id'),
            item.get('rule_id'),
        ]
        message = next((str(val) for val in message_candidates if isinstance(val, str) and val.strip()), 'Issue')

        severity_candidates = [
            item.get('severity'),
            item.get('issue_severity'),
            item.get('level'),
        ]
        severity = next((str(val) for val in severity_candidates if isinstance(val, str) and val.strip()), None)
        if not severity:
            extra = item.get('extra')
            if isinstance(extra, dict):
                severity = extra.get('severity') or extra.get('impact') or extra.get('likelihood')
            if isinstance(severity, str):
                severity = severity.strip()
        severity = severity or 'info'

        path = None
        for key in ('path', 'file_path', 'filename', 'file'):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                path = candidate
                break
            if isinstance(candidate, dict):
                nested_path = candidate.get('path') or candidate.get('name')
                if isinstance(nested_path, str) and nested_path.strip():
                    path = nested_path
                    break
        if not path:
            extra = item.get('extra')
            if isinstance(extra, dict):
                candidate = extra.get('path')
                if isinstance(candidate, str) and candidate.strip():
                    path = candidate

        line = None
        for key in ('line', 'line_number'):
            value = item.get(key)
            if isinstance(value, int):
                line = value
                break
        if line is None:
            start_block = item.get('start') or item.get('begin')
            if isinstance(start_block, dict):
                maybe_line = start_block.get('line') or start_block.get('line_number')
                if isinstance(maybe_line, int):
                    line = maybe_line
            if line is None and isinstance(item.get('line_range'), list):
                try:
                    line = int(item['line_range'][0])
                except (ValueError, TypeError, IndexError):
                    line = None

        rule = None
        for key in ('rule_id', 'check_id', 'symbol', 'code'):
            candidate = item.get(key)
            if isinstance(candidate, str) and candidate.strip():
                rule = candidate
                break
        if not rule:
            extra = item.get('extra')
            if isinstance(extra, dict):
                candidate = extra.get('rule_id') or extra.get('id')
                if isinstance(candidate, str) and candidate.strip():
                    rule = candidate

        findings.append(
            {
                'service': context.get('service'),
                'tool': context.get('tool') or context.get('service') or 'unknown',
                'severity': severity,
                'message': message,
                'path': path,
                'line': line,
                'rule': rule,
                'raw': item,
            }
        )

    def _walk(node: Any, context: Dict[str, Optional[str]]) -> None:
        if limit is not None and len(findings) >= limit:
            return
        if isinstance(node, dict):
            next_context = dict(context)
            tool_candidate = node.get('tool') or node.get('name')
            if isinstance(tool_candidate, str) and tool_candidate.strip():
                next_context['tool'] = tool_candidate
            service_candidate = node.get('service') or node.get('service_name') or node.get('container')
            if isinstance(service_candidate, str) and service_candidate.strip():
                next_context['service'] = service_candidate

            for key in ('issues', 'findings', 'results', 'alerts', 'violations'):
                collection = node.get(key)
                if isinstance(collection, list):
                    for item in collection:
                        if isinstance(item, dict):
                            _record(item, next_context)
                            _walk(item, next_context)

            for value in node.values():
                if isinstance(value, (dict, list)):
                    _walk(value, next_context)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    _walk(item, context)

    _walk(payload, {'service': None, 'tool': None})
    return findings[:limit] if limit is not None else findings


def summarise_services_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build a lightweight summary of services and their tools."""
    results = payload.get('results') if isinstance(payload, dict) else {}
    services = results.get('services') if isinstance(results, dict) else {}
    if not isinstance(services, dict):
        return []

    summaries: List[Dict[str, Any]] = []
    for service_name, service_payload in services.items():
        if not isinstance(service_payload, dict):
            continue
        summary: Dict[str, Any] = {
            'name': service_name,
            'type': service_payload.get('type') or service_payload.get('service'),
            'status': service_payload.get('status') or service_payload.get('service_status'),
            'tools': [],
            'summary': {},
        }

        service_summary = service_payload.get('summary')
        if isinstance(service_summary, dict):
            summary['summary'] = service_summary

        analysis_block = service_payload.get('analysis')
        if isinstance(analysis_block, dict):
            tools_section = analysis_block.get('results')
            _append_tools_from_section(summary['tools'], tools_section)
            tools_used = analysis_block.get('tools_used')
            if isinstance(tools_used, list):
                for tool_name in tools_used:
                    if not any(t['name'] == tool_name for t in summary['tools'] if isinstance(t, dict)):
                        summary['tools'].append({'name': tool_name, 'status': None, 'total_issues': None})

        # Some payloads store metrics in service -> tools -> {tool_name: {...}}
        tools_section = service_payload.get('tools')
        _append_tools_from_section(summary['tools'], tools_section)

        summaries.append(summary)

    return summaries


def _append_tools_from_section(container: List[Dict[str, Any]], tools_section: Any) -> None:
    if isinstance(tools_section, dict):
        for name, data in tools_section.items():
            if isinstance(data, dict):
                container.append(
                    {
                        'name': data.get('tool') or name,
                        'status': data.get('status'),
                        'executed': data.get('executed'),
                        'total_issues': data.get('total_issues') or data.get('issue_count'),
                    }
                )
    elif isinstance(tools_section, list):
        for item in tools_section:
            if isinstance(item, dict):
                container.append(
                    {
                        'name': item.get('tool') or item.get('name'),
                        'status': item.get('status'),
                        'executed': item.get('executed'),
                        'total_issues': item.get('total_issues') or item.get('issue_count'),
                    }
                )