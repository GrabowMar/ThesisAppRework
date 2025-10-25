"""Utilities for reading stored analysis result files from the results directory."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app

from app.paths import PROJECT_ROOT
from app.services.analysis_result_loader import AnalysisResultAggregator


TASK_DIR_PREFIXES = ("task-", "task_")


def _is_task_dir(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in TASK_DIR_PREFIXES)


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
        self._aggregator = AnalysisResultAggregator(self.base_dir)

    def _resolve_base_dir(self) -> Path:
        configured = current_app.config.get('RESULTS_DIR', 'results') if current_app else 'results'
        base_path = Path(configured)
        if not base_path.is_absolute():
            base_path = PROJECT_ROOT / base_path
        return base_path

    @staticmethod
    def _to_safe_slug(value: str) -> str:
        return value.replace('/', '_').replace('\\', '_')

    def _merge_related_services(self, path: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich legacy single-service payloads with sibling service results."""
        results_block = payload.get('results') if isinstance(payload.get('results'), dict) else None
        if results_block is None:
            return payload

        services_map = results_block.get('services') if isinstance(results_block.get('services'), dict) else {}
        if services_map is None:
            services_map = {}
        if not isinstance(services_map, dict):
            services_map = {}
        results_block['services'] = services_map

        existing_services = {str(key) for key in services_map.keys()}
        target_services = {'static', 'dynamic', 'performance', 'ai'}
        missing = target_services.difference(existing_services)
        if not missing:
            return payload

        metadata_raw = payload.get('metadata')
        metadata = metadata_raw if isinstance(metadata_raw, dict) else {}
        model_slug = metadata.get('model_slug') or path.parents[2].name
        app_number = metadata.get('app_number')
        if not isinstance(app_number, int):
            app_number = _extract_app_number(path.parent.name) if path.parent and path.parent.name else None
        if app_number is None:
            return payload

        related_files = self._find_related_service_files(model_slug, app_number)
        current_path = path.resolve()

        for service_name, service_path in related_files.items():
            if service_name not in missing:
                continue
            if service_path.resolve() == current_path:
                continue
            other_payload = self._load_json(service_path)
            service_payload = self._extract_service_payload(service_name, other_payload)
            if not service_payload:
                continue
            services_map[service_name] = service_payload
            self._merge_summary_blocks(results_block, other_payload)
            self._merge_findings(results_block, other_payload)
            self._merge_tools(results_block, other_payload)
            self._merge_raw_outputs(results_block, other_payload)

        summary = results_block.get('summary') if isinstance(results_block.get('summary'), dict) else {}
        if not isinstance(summary, dict):
            summary = {}
        results_block['summary'] = summary
        if services_map:
            summary['services_executed'] = len([k for k, v in services_map.items() if isinstance(v, dict)])
        status_values = []
        for service_payload in services_map.values():
            if isinstance(service_payload, dict):
                status = service_payload.get('status')
                if isinstance(status, str):
                    status_values.append(status.lower())
        if status_values:
            if all(s in {'success', 'completed', 'ok'} for s in status_values):
                summary['status'] = 'completed'
            elif any(s in {'error', 'failed'} for s in status_values):
                summary['status'] = 'partial'
            elif 'timeout' in status_values:
                summary['status'] = 'partial'
            else:
                summary['status'] = status_values[0]
        return payload

    def _find_related_service_files(self, model_slug: str, app_number: int) -> Dict[str, Path]:
        safe_slug = self._to_safe_slug(model_slug)
        app_base = self.base_dir / safe_slug / f'app{app_number}'
        if not app_base.exists():
            return {}
        legacy_base = app_base / 'analysis'
        latest: Dict[str, Path] = {}
        timestamps: Dict[str, float] = {}
        search_roots = [app_base]
        if legacy_base.exists():
            search_roots.append(legacy_base)

        def _register(candidate: Path) -> None:
            service_name = self._determine_service_from_filename(candidate, app_number)
            if not service_name:
                return
            try:
                mtime = candidate.stat().st_mtime
            except OSError:
                return
            if service_name not in latest or mtime > timestamps.get(service_name, 0):
                latest[service_name] = candidate
                timestamps[service_name] = mtime

        for root in search_roots:
            if not root.exists():
                continue
            for candidate in root.glob('*.json'):
                if candidate.parent.name == 'services':
                    continue
                _register(candidate)
            for task_dir in self._iter_task_dirs(root):
                services_dir = task_dir / 'services'
                if not services_dir.exists():
                    continue
                for candidate in services_dir.glob(f'{safe_slug}_app{app_number}_*.json'):
                    _register(candidate)
        return latest

    def _determine_service_from_filename(self, path: Path, app_number: int) -> Optional[str]:
        stem = path.stem
        marker = f"_app{app_number}_"
        idx = stem.find(marker)
        if idx == -1:
            return None
        remainder = stem[idx + len(marker):]
        if remainder.startswith('task-') or remainder.startswith('task_'):
            return None
        service = remainder.split('_')[0]
        return service or None

    def _iter_task_dirs(self, base: Path) -> Iterable[Path]:
        for task_dir in base.iterdir():
            if task_dir.is_dir() and _is_task_dir(task_dir.name):
                yield task_dir

    @staticmethod
    def _extract_service_payload(service_name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        results = payload.get('results') if isinstance(payload.get('results'), dict) else None
        if not results:
            return None
        services = results.get('services') if isinstance(results.get('services'), dict) else None
        if isinstance(services, dict):
            service_payload = services.get(service_name)
            if isinstance(service_payload, dict):
                return service_payload
        if service_name in {'static', 'dynamic', 'performance', 'ai'} and isinstance(results, dict):
            # Some payloads store the service data directly under results
            candidate = results.get(service_name)
            if isinstance(candidate, dict):
                return candidate
        return None

    @staticmethod
    def _merge_summary_blocks(primary_results: Dict[str, Any], other_payload: Dict[str, Any]) -> None:
        primary_summary = primary_results.get('summary')
        if not isinstance(primary_summary, dict):
            primary_summary = {}
            primary_results['summary'] = primary_summary

        other_results = other_payload.get('results') if isinstance(other_payload.get('results'), dict) else None
        if not other_results:
            return
        other_summary = other_results.get('summary') if isinstance(other_results.get('summary'), dict) else None
        if not other_summary:
            return

        total_primary = _coerce_optional_int(primary_summary.get('total_findings') or primary_summary.get('total_issues')) or 0
        total_other = _coerce_optional_int(other_summary.get('total_findings') or other_summary.get('total_issues')) or 0
        primary_summary['total_findings'] = total_primary + total_other

        tools_executed_primary = _coerce_optional_int(primary_summary.get('tools_executed')) or 0
        tools_executed_other = _coerce_optional_int(other_summary.get('tools_executed')) or 0
        if tools_executed_primary or tools_executed_other:
            primary_summary['tools_executed'] = tools_executed_primary + tools_executed_other

        for list_key in ('tools_used', 'tools_failed', 'tools_skipped'):
            merged = set()
            current_list = primary_summary.get(list_key)
            if isinstance(current_list, list):
                merged.update(str(item) for item in current_list)
            other_list = other_summary.get(list_key)
            if isinstance(other_list, list):
                merged.update(str(item) for item in other_list)
            if merged:
                primary_summary[list_key] = sorted(merged)

        severity_primary_raw = primary_summary.get('severity_breakdown')
        severity_primary = severity_primary_raw if isinstance(severity_primary_raw, dict) else {}
        severity_other_raw = other_summary.get('severity_breakdown')
        severity_other = severity_other_raw if isinstance(severity_other_raw, dict) else {}
        if severity_primary or severity_other:
            combined: Dict[str, int] = {}
            for key in set(severity_primary.keys()).union(severity_other.keys()):
                value = 0
                if key in severity_primary and _is_int_like(severity_primary.get(key)):
                    value += int(severity_primary[key])  # type: ignore[arg-type]
                if key in severity_other and _is_int_like(severity_other.get(key)):
                    value += int(severity_other[key])  # type: ignore[arg-type]
                combined[key] = value
            primary_summary['severity_breakdown'] = combined

    @staticmethod
    def _merge_findings(primary_results: Dict[str, Any], other_payload: Dict[str, Any]) -> None:
        findings = primary_results.get('findings')
        if not isinstance(findings, list):
            findings = []
            primary_results['findings'] = findings
        other_results = other_payload.get('results') if isinstance(other_payload.get('results'), dict) else None
        if not other_results:
            return
        other_findings = other_results.get('findings')
        if isinstance(other_findings, list):
            findings.extend(other_findings)

    @staticmethod
    def _merge_tools(primary_results: Dict[str, Any], other_payload: Dict[str, Any]) -> None:
        tools_map = primary_results.get('tools')
        if not isinstance(tools_map, dict):
            tools_map = {}
            primary_results['tools'] = tools_map
        other_results = other_payload.get('results') if isinstance(other_payload.get('results'), dict) else None
        if not other_results:
            return
        other_tools = other_results.get('tools')
        if isinstance(other_tools, dict):
            for name, data in other_tools.items():
                if name not in tools_map:
                    tools_map[name] = data

    @staticmethod
    def _merge_raw_outputs(primary_results: Dict[str, Any], other_payload: Dict[str, Any]) -> None:
        raw_outputs = primary_results.get('raw_outputs')
        if not isinstance(raw_outputs, dict):
            raw_outputs = {}
            primary_results['raw_outputs'] = raw_outputs
        other_results = other_payload.get('results') if isinstance(other_payload.get('results'), dict) else None
        if not other_results:
            return
        other_raw = other_results.get('raw_outputs')
        if isinstance(other_raw, dict):
            for name, data in other_raw.items():
                if name not in raw_outputs:
                    raw_outputs[name] = data

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------

    def list_results(self, model_slug: Optional[str] = None, app_number: Optional[int] = None) -> List[ResultFileDescriptor]:
        """Return descriptors for all result files, optionally filtered."""
        descriptors: List[ResultFileDescriptor] = []
        seen_paths: set[Path] = set()

        for grouped in self._aggregator.iter_unified_files(model_slug=model_slug, app_number=app_number):
            try:
                descriptor = self._build_descriptor(grouped.path)
            except Exception:
                continue
            descriptors.append(descriptor)
            seen_paths.add(grouped.path.resolve())

        for legacy_path in self._iter_legacy_files(model_slug, app_number):
            resolved = legacy_path.resolve()
            if resolved in seen_paths:
                continue
            try:
                descriptor = self._build_descriptor(legacy_path)
            except Exception:
                continue
            descriptors.append(descriptor)
        descriptors.sort(key=lambda item: item.timestamp, reverse=True)
        return descriptors

    def _iter_legacy_files(
        self,
        model_slug: Optional[str],
        app_number: Optional[int],
    ) -> Iterable[Path]:
        """Yield legacy result files stored directly under analysis/ folders."""
        safe_filter = self._to_safe_slug(model_slug) if model_slug else None
        pattern = '*/*/analysis/*.json'
        for path in self.base_dir.glob(pattern):
            if _is_task_dir(path.parent.name):
                continue
            try:
                safe_slug = path.parents[2].name
                app_folder = path.parents[1].name
            except IndexError:
                continue
            if safe_filter and safe_slug != safe_filter:
                continue
            if app_number is not None:
                parsed_app = _extract_app_number(app_folder)
                if parsed_app != app_number:
                    continue
            yield path

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
        if _is_task_dir(path.parent.name):
            if not payload.get('results'):
                rebuilt = self._aggregator.build_payload_from_services(path.parent)
                if rebuilt:
                    payload = rebuilt
        else:
            payload = self._merge_related_services(path, payload)
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