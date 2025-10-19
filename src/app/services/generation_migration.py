"""Migration helpers for consolidating generated artifacts.

Moves legacy directories into the unified structure introduced by the
new generation refactor. The migration is conservative (copies then
optionally deletes) and idempotent (writes a marker file to avoid
repeat work).
"""
from __future__ import annotations

from pathlib import Path
import json
import shutil
import time
from typing import Dict, Any

from app.paths import (
    PROJECT_ROOT,
    GENERATED_ROOT,
    GENERATED_INDICES_DIR,
    GENERATED_STATS_DIR,
    GENERATED_RAW_API_DIR,
    GENERATED_FAILURES_DIR,
    GENERATED_METADATA_DIR,
    GENERATED_MARKDOWN_DIR,
    GENERATED_CAPABILITIES_DIR,
    GENERATED_SUMMARIES_DIR,
    GENERATED_CONFIG_DIR,
    GENERATED_LARGE_CONTENT_DIR,
    GENERATED_INDICES_DIR,
    GENERATED_LOGS_DIR,
    GENERATED_TMP_DIR,
)

MIGRATION_MARKER = GENERATED_ROOT / '.migration_done'


def _copy_tree(src: Path, dst: Path) -> int:
    count = 0
    if not src.exists():
        return 0
    for item in src.rglob('*'):
        if item.is_file():
            rel = item.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(item, target)
                count += 1
            except Exception:  # pragma: no cover - best effort
                pass
    return count
def run_generated_migration(delete_source: bool = False) -> Dict[str, Any]:
    """Migrate legacy folders into ``generated`` (project root).



    Legacy patterns handled:
      - project_root/generated/* (old root) -> generated/apps/<model>
      - project_root/api_data/* -> generated/{raw/responses|metadata/stats|metadata/failures}
      - project_root/generated/<legacy_metadata> -> generated/metadata/<category>
    """

    GENERATED_ROOT.mkdir(parents=True, exist_ok=True)
    report: Dict[str, Any] = {
        'started': time.time(),
        'moved_files': 0,
        'sources': {},
        'deleted_sources': [],
        'skipped': False,
    }

    if MIGRATION_MARKER.exists():
        report['skipped'] = True
        return report

    legacy_root_generated = PROJECT_ROOT / 'generated'
    if legacy_root_generated.exists() and legacy_root_generated != GENERATED_ROOT:
        for model_dir in [p for p in legacy_root_generated.iterdir() if p.is_dir()]:
            target = GENERATED_ROOT / 'apps' / model_dir.name
            copied = _copy_tree(model_dir, target)
            report['moved_files'] += copied
        report['sources']['legacy_generated'] = str(legacy_root_generated)
        if delete_source:
            shutil.rmtree(legacy_root_generated, ignore_errors=True)
            report['deleted_sources'].append(str(legacy_root_generated))

    legacy_api_data = PROJECT_ROOT / 'api_data'
    if legacy_api_data.exists():
        mapping = {
            'raw_outputs': GENERATED_RAW_API_DIR / 'responses',
            'generation_stats': GENERATED_STATS_DIR / 'generation',
            'failed_attempts': GENERATED_FAILURES_DIR,
        }
        for name, target in mapping.items():
            src_sub = legacy_api_data / name
            if not src_sub.exists():
                continue
            copied = _copy_tree(src_sub, target)
            report['moved_files'] += copied
            report['sources'][f'legacy_api_data_{name}'] = str(src_sub)
            if delete_source:
                shutil.rmtree(src_sub, ignore_errors=True)
        if delete_source:
            shutil.rmtree(legacy_api_data, ignore_errors=True)
            report['deleted_sources'].append(str(legacy_api_data))
        else:
            report['sources']['legacy_api_data'] = str(legacy_api_data)

    legacy_metadata_map = {
        'raw_api': GENERATED_RAW_API_DIR,
        'metadata': GENERATED_METADATA_DIR,
        'markdown': GENERATED_MARKDOWN_DIR,
        'stats': GENERATED_STATS_DIR,
        'failures': GENERATED_FAILURES_DIR,
        'capabilities': GENERATED_CAPABILITIES_DIR,
        'summaries': GENERATED_SUMMARIES_DIR,
        'config': GENERATED_CONFIG_DIR,
        'large_content': GENERATED_LARGE_CONTENT_DIR,
        'indices': GENERATED_INDICES_DIR,
        'logs': GENERATED_LOGS_DIR,
        'tmp': GENERATED_TMP_DIR,
    }

    for legacy_name, target in legacy_metadata_map.items():
        legacy_path = GENERATED_ROOT / legacy_name
        if not legacy_path.exists():
            continue
        try:
            if legacy_path.resolve() == target.resolve():
                continue
        except Exception:
            if str(legacy_path) == str(target):
                continue
        copied = _copy_tree(legacy_path, target)
        report['moved_files'] += copied
        report['sources'][f'legacy_{legacy_name}'] = str(legacy_path)
        if delete_source:
            shutil.rmtree(legacy_path, ignore_errors=True)
            report['deleted_sources'].append(str(legacy_path))

    try:
        MIGRATION_MARKER.write_text(str(int(time.time())))
    except Exception:
        pass

    GENERATED_INDICES_DIR.mkdir(parents=True, exist_ok=True)
    try:
        (GENERATED_INDICES_DIR / 'migration_report.json').write_text(
            json.dumps(report, indent=2)
        )
    except Exception:
        pass

    report['completed'] = time.time()
    return report

__all__ = ['run_generated_migration']
