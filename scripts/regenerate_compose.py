"""Regenerate docker-compose scaffolding for generated apps.

This CLI walks the generated/apps directory and re-runs the simplified
scaffolding pipeline so new placeholder substitutions take effect.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"

if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

logger = logging.getLogger(__name__)


def parse_app_number(name: str) -> Optional[int]:
    """Extract an app number from directory names like app1 or app_1."""
    match = re.search(r"app[_-]?(\d+)$", name)
    if not match:
        return None
    return int(match.group(1))


def discover_targets(root: Path, models: Iterable[str], apps: Iterable[int]) -> Iterator[Tuple[str, int, Path]]:
    """Yield (model_slug, app_num, app_dir) tuples for regeneration."""
    model_filters = set(models)
    app_filters = set(apps)

    for model_dir in sorted(root.iterdir()):
        if not model_dir.is_dir():
            continue
        model_slug = model_dir.name
        if model_filters and model_slug not in model_filters:
            continue

        for app_dir in sorted(model_dir.iterdir()):
            if not app_dir.is_dir():
                continue
            app_num = parse_app_number(app_dir.name)
            if app_num is None:
                continue
            if app_filters and app_num not in app_filters:
                continue
            yield model_slug, app_num, app_dir


def regenerate(model_slug: str, app_num: int, app_path: Path, generation_service, dry_run: bool = False) -> bool:
    """Re-scaffold a single app directory."""
    compose_path = app_path / "docker-compose.yml"
    logger.info("Processing %s/app%d -> %s", model_slug, app_num, compose_path)
    if dry_run:
        return compose_path.exists()
    return generation_service.scaffolding.scaffold(model_slug, app_num)


def run(models: List[str], apps: List[int], dry_run: bool = False) -> Tuple[int, int, List[str]]:
    """Execute regeneration across all matching apps."""
    regenerated = 0
    skipped = 0
    failures: List[str] = []

    from app.factory import create_app
    from app.paths import GENERATED_APPS_DIR
    from app.services.generation import get_generation_service

    app = create_app()
    with app.app_context():
        generation_service = get_generation_service()
        targets = list(discover_targets(GENERATED_APPS_DIR, models, apps))
        if not targets:
            logger.warning("No generated apps found matching the provided filters")
            return regenerated, skipped, failures

        for model_slug, app_num, app_path in targets:
            try:
                if regenerate(model_slug, app_num, app_path, generation_service, dry_run=dry_run):
                    regenerated += 1
                else:
                    skipped += 1
            except Exception as exc:  # pragma: no cover - CLI safety
                logger.error("Failed to regenerate %s/app%d: %s", model_slug, app_num, exc)
                failures.append(f"{model_slug}/app{app_num}: {exc}")

    return regenerated, skipped, failures


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate docker-compose scaffolding for generated apps")
    parser.add_argument("--model", dest="models", action="append", default=[], help="Limit to specific model slug")
    parser.add_argument("--app", dest="apps", type=int, action="append", default=[], help="Limit to specific app number")
    parser.add_argument("--dry-run", action="store_true", help="List apps without rewriting files")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    regenerated, skipped, failures = run(args.models, args.apps, dry_run=args.dry_run)

    logger.info("Regenerated: %d", regenerated)
    if skipped:
        logger.info("Skipped (already up to date): %d", skipped)
    if failures:
        logger.error("Failures: %d", len(failures))
        for item in failures:
            logger.error("  %s", item)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
