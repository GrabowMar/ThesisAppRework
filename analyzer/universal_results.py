"""Universal Results Schema Writer
===================================

Provides a minimal, future-proof single-file schema for analysis runs.

Schema: universal-v1
--------------------
{
  "schema": {"name": "universal", "version": "v1"},
  "metadata": {
      "task_id": str,
      "model_slug": str,
      "app_number": int,
      "created_at": iso8601,
      "duration_seconds": float,
      "tools_requested": [str],
      "tools_successful": int,
      "tools_failed": int,
      "status": "completed|failed|partial",
      "languages_detected": [str]
  },
  "tools": {
      "<tool_name>": {
          "status": "success|error|skipped|not_available",
          "duration_seconds": float|null,
          "issue_count": int|null,
          "severity_breakdown": {"high":int,"medium":int,"low":int}?,
          "raw": {
              "stdout": str?,
              "stderr": str?,
              "summary": str?,
              "truncated": bool?
          }
      }, ...
  }
}

Design Goals:
 - Minimal mandatory surface: metadata + tools map.
 - Raw data captured only as flat strings (no nested opaque blobs) for portability.
 - Deterministic key ordering & stable naming for diff-friendliness.
 - No per-service hierarchy; all tools first-class.

Environment Flags:
 - UNIVERSAL_RESULTS=1 forces analyzer_manager to emit ONLY this schema.
 - UNIVERSAL_RAW_MAX (default 16000 chars) controls per-field truncation.
 - UNIVERSAL_INCLUDE_STDERR=1 to include stderr (default include if non-empty).
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pathlib import Path
import os
import json


@dataclass
class UniversalToolRecord:
    status: str
    duration_seconds: Optional[float] = None
    issue_count: Optional[int] = None
    severity_breakdown: Optional[Dict[str, int]] = None
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # Remove None values for compactness
        return {k: v for k, v in data.items() if v not in (None, [], {}, '')}


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...<truncated {len(value)-limit} chars>"


def _sanitize_task_id(task_id: str) -> str:
    cleaned = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in str(task_id))
    return cleaned or 'task'


def build_universal_payload(
    *,
    task_id: str,
    model_slug: str,
    app_number: int,
    tools_requested: List[str],
    tool_results: Dict[str, Dict[str, Any]],
    start_time: float,
    end_time: float,
    detected_languages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Construct the universal-v1 payload from normalized tool results.

    tool_results expected shape (normalized upstream):
      {
        tool_name: {
           'status': str,
           'duration': float?,
           'issues': list?|int?,
           'severity_breakdown': {...}?,
           'stdout': str?,
           'stderr': str?,
           'summary': str?,
        }
      }
    """
    max_len = int(os.getenv('UNIVERSAL_RAW_MAX', '16000'))
    include_stderr = os.getenv('UNIVERSAL_INCLUDE_STDERR', '1') not in ('0', 'false', 'False')

    tools_map: Dict[str, Any] = {}
    success = 0
    failed = 0

    for name, r in sorted(tool_results.items()):
        status = str(r.get('status', 'unknown'))
        if status.startswith('error') or status in ('error', 'failed', 'not_available'):
            failed += 1
        elif status not in ('skipped', 'not_available'):
            success += 1

        # Determine issue count
        issues_obj = r.get('issues')
        if isinstance(issues_obj, list):
            issue_count = len(issues_obj)
        elif isinstance(issues_obj, int):
            issue_count = issues_obj
        else:
            issue_count = r.get('total_issues') if isinstance(r.get('total_issues'), int) else None

        raw_block = {}
        stdout_val = r.get('stdout') or r.get('raw_output') or r.get('output')
        if isinstance(stdout_val, str) and stdout_val.strip():
            raw_block['stdout'] = _truncate(stdout_val, max_len)
        if include_stderr:
            stderr_val = r.get('stderr') or r.get('error_output')
            if isinstance(stderr_val, str) and stderr_val.strip():
                raw_block['stderr'] = _truncate(stderr_val, max_len)
        summary_val = r.get('summary') or r.get('message')
        if isinstance(summary_val, str) and summary_val.strip():
            raw_block['summary'] = _truncate(summary_val, 1024)
        if not raw_block:
            raw_block = None

        rec = UniversalToolRecord(
            status=status,
            duration_seconds=r.get('duration') or r.get('duration_seconds'),
            issue_count=issue_count,
            severity_breakdown=r.get('severity_breakdown') if isinstance(r.get('severity_breakdown'), dict) else None,
            raw=raw_block
        )
        tools_map[name] = rec.to_dict()

    total_duration = max(0.0, end_time - start_time)
    payload = {
        'schema': {'name': 'universal', 'version': 'v1'},
        'metadata': {
            'task_id': task_id,
            'model_slug': model_slug,
            'app_number': app_number,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': total_duration,
            'tools_requested': tools_requested,
            'tools_successful': success,
            'tools_failed': failed,
            'status': 'completed' if failed == 0 else ('partial' if success > 0 else 'failed'),
            'languages_detected': detected_languages or []
        },
        'tools': tools_map
    }
    return payload


def write_universal_file(base_dir, model_slug: str, app_number: int, task_id: str, payload: Dict[str, Any]) -> str:
    safe_slug = model_slug.replace('/', '_').replace('\\', '_')
    sanitized_task = _sanitize_task_id(task_id)
    app_dir = Path(base_dir) / safe_slug / f"app{app_number}"
    target_dir = app_dir / f"task_{sanitized_task}"

    target_dir.mkdir(parents=True, exist_ok=True)

    legacy_dirs = [
        app_dir / 'analysis' / f"task_{sanitized_task}",
        app_dir / 'analysis' / f"task-{sanitized_task}",
    ]
    for legacy_dir in legacy_dirs:
        if not legacy_dir.exists() or not legacy_dir.is_dir():
            continue
        for item in legacy_dir.iterdir():
            destination = target_dir / item.name
            if destination.exists():
                continue
            try:
                item.replace(destination)
            except Exception:
                try:
                    item.rename(destination)
                except Exception:
                    pass
        try:
            legacy_dir.rmdir()
        except OSError:
            pass

    legacy_analysis_file = app_dir / 'analysis' / f"{safe_slug}_app{app_number}_task_{sanitized_task}_universal.json"
    if legacy_analysis_file.exists() and not (target_dir / legacy_analysis_file.name).exists():
        try:
            legacy_analysis_file.replace(target_dir / legacy_analysis_file.name)
        except Exception:
            pass
    desired_name = f"{safe_slug}_app{app_number}_task_{sanitized_task}_universal.json"
    legacy_name = f"{safe_slug}_app{app_number}_task-{sanitized_task}_universal.json"

    existing = list(target_dir.glob(desired_name))
    if not existing:
        legacy_existing = list(target_dir.glob(legacy_name))
        if legacy_existing:
            try:
                legacy_existing[0].rename(target_dir / desired_name)
                existing = [target_dir / desired_name]
            except OSError:
                pass

    path = existing[0] if existing else target_dir / desired_name
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    return str(path)

__all__ = ['build_universal_payload', 'write_universal_file']