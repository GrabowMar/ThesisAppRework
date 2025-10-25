"""Reorganize legacy analysis results into task-based folders.

This utility scans the ``results`` directory for legacy per-service JSON
files that still live directly under ``analysis/``. For each run it builds a
consolidated payload containing all available services and then delegates to
``AnalyzerManager.save_task_results`` to emit the new grouped artefacts under
``analysis/task_<task_id>/`` (legacy runs used ``task-<task_id>``). After a
successful write, the legacy files are
removed so the new structure is authoritative.

Usage (dry run by default)::

    python scripts/migrate_results_to_task_folders.py

Apply changes (irreversible)::

    python scripts/migrate_results_to_task_folders.py --apply

You can scope the migration to a single model or app using ``--model`` and
``--app``. The script intentionally deletes legacy files after grouping when
``--apply`` is provided, matching the "move, don't copy" requirement.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analyzer.analyzer_manager import AnalyzerManager  # noqa: E402


@dataclass(slots=True)
class LegacyResult:
    path: Path
    model_slug: str
    app_number: int
    service_name: str
    timestamp: str
    payload: Dict[str, object]


def _safe_slug(model_slug: str) -> str:
    return model_slug.replace('/', '_').replace('\\', '_')


def _extract_legacy_result(path: Path) -> Optional[LegacyResult]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None

    metadata = data.get('metadata') if isinstance(data, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}

    model_slug = metadata.get('model_slug')
    if not isinstance(model_slug, str) or not model_slug.strip():
        try:
            model_slug = path.parents[2].name
        except IndexError:
            return None

    app_number = metadata.get('app_number')
    if not isinstance(app_number, int):
        try:
            app_part = path.parents[1].name  # app<number>
            if app_part.lower().startswith('app'):
                app_number = int(app_part[3:])
            else:
                app_number = int(app_part)
        except (IndexError, ValueError):
            return None

    service_name, timestamp = _parse_filename(path, app_number)
    if not service_name or not timestamp:
        return None

    results_section = data.get('results') if isinstance(data.get('results'), dict) else data
    if not isinstance(results_section, dict):
        return None

    services_map = results_section.get('services') if isinstance(results_section.get('services'), dict) else None
    payload = services_map.get(service_name) if isinstance(services_map, dict) else None
    if payload is None and isinstance(results_section.get(service_name), dict):
        payload = results_section[service_name]
    if payload is None:
        payload = results_section

    if not isinstance(payload, dict):
        return None

    return LegacyResult(
        path=path,
        model_slug=model_slug,
        app_number=int(app_number),
        service_name=service_name,
        timestamp=timestamp,
        payload=payload,
    )


def _parse_filename(path: Path, app_number: int) -> Tuple[Optional[str], Optional[str]]:
    stem = path.stem
    marker = f"_app{app_number}_"
    idx = stem.find(marker)
    if idx == -1:
        return None, None
    remainder = stem[idx + len(marker):]
    if remainder.startswith('task-') or remainder.startswith('task_'):
        return None, None
    parts = remainder.split('_')
    if len(parts) < 3:
        return None, None
    service_name = parts[0]
    timestamp = '_'.join(parts[1:])
    return service_name or None, timestamp or None


def _iter_legacy_files(results_dir: Path, model_filter: Optional[str], app_filter: Optional[int]) -> Iterable[Path]:
    pattern = '*/*/analysis/*.json'
    for candidate in results_dir.glob(pattern):
        if candidate.parent.name.startswith('task-') or candidate.parent.name.startswith('task_'):
            continue
        if candidate.name.endswith('_suppressed.json'):
            continue
        try:
            safe_slug = candidate.parents[2].name
            app_name = candidate.parents[1].name
        except IndexError:
            continue
        if model_filter and safe_slug != _safe_slug(model_filter):
            continue
        if app_filter is not None:
            try:
                parsed = int(app_name[3:]) if app_name.lower().startswith('app') else int(app_name)
            except ValueError:
                continue
            if parsed != app_filter:
                continue
        yield candidate


def _merge_payloads(results: List[LegacyResult]) -> Dict[str, Dict[str, object]]:
    merged: Dict[str, Dict[str, object]] = {}
    for item in results:
        merged[item.service_name] = item.payload
    return merged


def _summarise_group(results: List[LegacyResult]) -> str:
    services = ', '.join(sorted(r.service_name for r in results))
    return f"services=[{services}] count={len(results)}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Group legacy analysis results into task folders")
    parser.add_argument('--results-dir', default=PROJECT_ROOT / 'results', type=Path, help='Root results directory')
    parser.add_argument('--model', help='Only migrate a specific model slug')
    parser.add_argument('--app', type=int, help='Only migrate a specific app number')
    parser.add_argument('--apply', action='store_true', help='Perform changes (default is dry-run)')
    parser.add_argument('--task-id', default='comprehensive', help='Task identifier to use for grouped output (default: comprehensive)')
    args = parser.parse_args(argv)

    results_dir = args.results_dir.resolve()
    if not results_dir.exists():
        print(f"Results directory not found: {results_dir}")
        return 1

    legacy_files = list(_iter_legacy_files(results_dir, args.model, args.app))
    if not legacy_files:
        print('No legacy analysis files detected. Nothing to migrate.')
        return 0

    grouped: Dict[Tuple[str, int, str], List[LegacyResult]] = defaultdict(list)
    for legacy_path in legacy_files:
        extracted = _extract_legacy_result(legacy_path)
        if not extracted:
            print(f"Skipping unreadable legacy file: {legacy_path}")
            continue
        key = (extracted.model_slug, extracted.app_number, extracted.timestamp)
        grouped[key].append(extracted)

    if not grouped:
        print('No convertible legacy files found.')
        return 0

    manager = AnalyzerManager()
    manager.results_dir = results_dir

    dry_run = not args.apply

    for (model_slug, app_number, timestamp), items in sorted(grouped.items()):
        summary = _summarise_group(items)
        print(f"\n[{model_slug} app{app_number} @ {timestamp}] {summary}")
        consolidated = _merge_payloads(items)
        if not consolidated:
            print('  -> Skipping; no payloads extracted.')
            continue
        if dry_run:
            print('  -> DRY RUN: would call save_task_results and delete legacy files:')
            for item in items:
                print(f"     - {item.path}")
            continue

        async def _store() -> Path:
            return await manager.save_task_results(model_slug, app_number, args.task_id, consolidated)

        try:
            new_path = asyncio.run(_store())
            print(f"  -> Created grouped task result: {new_path}")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"  !! Failed to write grouped result for {model_slug} app{app_number}: {exc}")
            continue

        for item in items:
            try:
                item.path.unlink()
                print(f"     deleted legacy file: {item.path}")
            except Exception as exc:  # pragma: no cover - best effort
                print(f"     !! Could not delete {item.path}: {exc}")

    if dry_run:
        print('\nDry run complete. Re-run with --apply to persist changes.')
    else:
        print('\nMigration complete. Legacy per-service files have been removed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
