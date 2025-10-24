"""Helpers for grouping analyzer result files by main task.

This module provides a small utility for discovering consolidated task
results that now live in per-task folders (``analysis/task-<id>``).  It also
exposes helpers for rebuilding a unified payload from the per-service
snapshots when the primary consolidated file is missing.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _normalize_model_slug(model_slug: str) -> str:
    return model_slug.replace('/', '_').replace('\\', '_')


def _parse_app_number(app_folder: str) -> Optional[int]:
    folder = app_folder.lower()
    if folder.startswith('app'):
        candidate = folder[3:]
        if candidate.isdigit():
            return int(candidate)
    try:
        return int(folder)
    except ValueError:
        return None


def _extract_task_id(stem: str) -> Optional[str]:
    if "_task-" not in stem:
        return None
    prefix, suffix = stem.split("_task-", 1)
    parts = suffix.split("_", 1)
    if not parts:
        return None
    return parts[0] or None


@dataclass(frozen=True)
class TaskResultFile:
    """Represents a consolidated result JSON stored under a task folder."""

    path: Path
    model_folder: str
    app_number: int
    task_id: str


class AnalysisResultAggregator:
    """Utility to discover grouped task results and rebuild payloads."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    # ------------------------------------------------------------------
    # Discovery helpers
    # ------------------------------------------------------------------
    def iter_unified_files(
        self,
        *,
        model_slug: Optional[str] = None,
        app_number: Optional[int] = None,
    ) -> Iterable[TaskResultFile]:
        """Yield consolidated result files stored inside per-task folders."""
        safe_filter = _normalize_model_slug(model_slug) if model_slug else None

        pattern = "*/*/analysis/task-*/*.json"
        for candidate in self.base_dir.glob(pattern):
            if candidate.parent.name == 'services':
                continue
            stem = candidate.stem
            if '_task-' not in stem:
                continue
            if stem.endswith('_universal'):
                continue

            try:
                model_folder = candidate.parents[3].name
                app_folder = candidate.parents[2].name
            except IndexError:
                continue

            if safe_filter and model_folder != safe_filter:
                continue

            parsed_app = _parse_app_number(app_folder)
            if parsed_app is None:
                continue
            if app_number is not None and parsed_app != app_number:
                continue

            task_id = _extract_task_id(stem)
            if not task_id:
                continue

            yield TaskResultFile(
                path=candidate,
                model_folder=model_folder,
                app_number=parsed_app,
                task_id=task_id,
            )

    # ------------------------------------------------------------------
    # Payload reconstruction
    # ------------------------------------------------------------------
    def build_payload_from_services(self, task_dir: Path) -> Optional[Dict[str, Any]]:
        """Construct a unified payload when only service snapshots exist."""
        services_dir = task_dir / 'services'
        if not services_dir.exists():
            return None

        service_files = sorted(services_dir.glob('*.json'))
        if not service_files:
            return None

        service_payloads: Dict[str, Any] = {}
        summary_services: List[str] = []
        findings: List[Any] = []
        tools_used: List[str] = []
        severity_breakdown: Dict[str, int] = {'high': 0, 'medium': 0, 'low': 0}

        model_slug: Optional[str] = None
        app_number: Optional[int] = None
        task_id: Optional[str] = None

        for path in service_files:
            try:
                data = json.loads(path.read_text(encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(data, dict):
                continue

            metadata = data.get('metadata')
            results = data.get('results')
            if not isinstance(metadata, dict) or not isinstance(results, dict):
                continue

            service_name = metadata.get('service_name') or path.stem.split('_')[-1]
            if not isinstance(service_name, str):
                continue

            model_slug = model_slug or metadata.get('model_slug')
            app_number = app_number or metadata.get('app_number')
            task_id = task_id or metadata.get('task_id')

            service_payloads[service_name] = results
            summary_services.append(service_name)

            # Collect lightweight aggregates for summary
            analysis_candidate = results.get('analysis')
            analysis_block = analysis_candidate if isinstance(analysis_candidate, dict) else {}
            tools_section = analysis_block.get('tools_used') if isinstance(analysis_block, dict) else []
            if isinstance(tools_section, list):
                for tool_name in tools_section:
                    if isinstance(tool_name, str) and tool_name not in tools_used:
                        tools_used.append(tool_name)

            severity_map = analysis_block.get('severity_breakdown') if isinstance(analysis_block, dict) else {}
            if isinstance(severity_map, dict):
                for key in ('high', 'medium', 'low'):
                    value = severity_map.get(key)
                    if isinstance(value, int):
                        severity_breakdown[key] += value

            findings_block = analysis_block.get('findings') if isinstance(analysis_block, dict) else []
            if isinstance(findings_block, list):
                findings.extend(findings_block)

        if not service_payloads or model_slug is None or app_number is None or task_id is None:
            return None

        manifest_path = task_dir / 'manifest.json'
        manifest_timestamp: Optional[str] = None
        if manifest_path.exists():
            try:
                manifest_timestamp = datetime.fromtimestamp(manifest_path.stat().st_mtime).isoformat()
            except Exception:
                manifest_timestamp = None

        payload: Dict[str, Any] = {
            'metadata': {
                'model_slug': model_slug,
                'app_number': app_number,
                'analysis_type': task_id,
                'timestamp': manifest_timestamp,
            },
            'results': {
                'task': {
                    'task_id': task_id,
                    'analysis_type': task_id,
                    'model_slug': model_slug,
                    'app_number': app_number,
                },
                'summary': {
                    'services_executed': len(summary_services),
                    'tools_used': tools_used,
                    'severity_breakdown': severity_breakdown,
                    'total_findings': len(findings),
                },
                'services': service_payloads,
                'findings': findings,
            },
        }
        return payload