#!/usr/bin/env python3
"""Remove legacy per-service analysis JSON files.

The current analysis pipeline writes grouped results into
``results/<model>/appN/analysis/task_<task_id>/`` (legacy runs used
``task-<task_id>``).  Older runs produced
standalone JSON files directly inside ``analysis/`` as well as
per-service directories (``static-analyzer/`` etc.).  This utility
removes those legacy artefacts so the UI only shows grouped task
results.

Usage (from repo root)::

    python scripts/purge_legacy_analysis_results.py
    python scripts/purge_legacy_analysis_results.py --results-dir ./custom

By default the script performs a dry-run and prints the files that would
be removed.  Pass ``--apply`` to actually delete the files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

LEGACY_SERVICE_DIRS = {
    "static-analyzer",
    "dynamic-analyzer",
    "performance-tester",
    "ai-analyzer",
    "security-analyzer",
}

TASK_DIR_PREFIXES = ("task-", "task_")


def _is_task_dir(name: str) -> bool:
    return any(name.startswith(prefix) for prefix in TASK_DIR_PREFIXES)


def iter_legacy_files(root: Path) -> Iterable[Path]:
    """Yield legacy JSON files and directories slated for deletion."""
    if not root.exists():
        return []

    for model_dir in root.iterdir():
        if not model_dir.is_dir():
            continue
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.lower().startswith("app"):
                continue
            analysis_dir = app_dir / "analysis"
            if analysis_dir.exists():
                for candidate in analysis_dir.glob("*.json"):
                    if _is_task_dir(candidate.parent.name):
                        continue
                    yield candidate
            for legacy_name in LEGACY_SERVICE_DIRS:
                legacy_dir = app_dir / legacy_name
                if legacy_dir.exists():
                    yield legacy_dir


def purge(root: Path, apply: bool) -> None:
    targets = list(iter_legacy_files(root))
    if not targets:
        print("[purge] No legacy analysis artefacts found.")
        return

    action = "Deleting" if apply else "Would delete"
    for target in targets:
        print(f"{action}: {target}")
        if apply:
            if target.is_dir():
                for item in sorted(target.rglob("*"), reverse=True):
                    if item.is_file():
                        try:
                            item.unlink()
                        except Exception as exc:
                            print(f"  [warn] Failed to remove {item}: {exc}")
                    elif item.is_dir():
                        try:
                            item.rmdir()
                        except Exception as exc:
                            print(f"  [warn] Failed to remove dir {item}: {exc}")
                try:
                    target.rmdir()
                except Exception as exc:
                    print(f"  [warn] Failed to remove dir {target}: {exc}")
            else:
                try:
                    target.unlink()
                except Exception as exc:
                    print(f"  [warn] Failed to remove file {target}: {exc}")
    if not apply:
        print("\nRun again with --apply to delete the files above.")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        default="results",
        help="Path to the results directory (default: %(default)s)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete the files instead of performing a dry-run.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = Path(args.results_dir).resolve()
    purge(root, apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
