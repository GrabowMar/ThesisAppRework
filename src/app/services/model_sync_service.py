"""Model Filesystem Sync Service
=================================

Purpose: Ensure that any models/applications generated outside of the
database initialization path (e.g. via legacy scripts or the sample
generator writing directly to the filesystem) are reflected in the
database so that the /models UI and related APIs return them.

Main entrypoints:
 - sync_models_from_filesystem(): full scan (idempotent)
 - upsert_model_and_application(): focused single model/app upsert used
   by the sample generation service right after a generation completes.

Heuristics:
 - Scans both ./models and ./generated roots (if present)
 - A "model directory" is any first‑level subdirectory containing
   subfolders named app1, app2, ... OR files like docker-compose.*
 - canonical_slug = directory name (lowercased). Slashes/spaces replaced
   with underscores. model_id uses same value for simplicity.
 - provider = first token before first '_' or '-' (fallback 'local')
 - model_name = original directory name (for display)
 - installed flag set True when found on disk
 - GeneratedApplication rows created for each appN folder with basic
   booleans derived from contents (backend/, frontend/, docker-compose*)

All operations are idempotent: existing rows are updated; new rows are
inserted only when missing. A single commit is used for the bulk sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Dict, Any, Optional

try:  # Prefer centralized path constants if available
    from app.paths import GENERATED_APPS_DIR
except Exception:  # pragma: no cover
    # Fallback to project-root based generated/apps for resilience
    GENERATED_APPS_DIR = Path('generated') / 'apps'

from app.extensions import db
from app.models import ModelCapability, GeneratedApplication
from app.constants import AnalysisStatus


# Directories occasionally mis-identified as models in legacy sync runs
LEGACY_METADATA_NAMES = {
    'capabilities', 'config', 'failures', 'indices', 'logs', 'markdown',
    'raw_api', 'stats', 'tmp', 'large_content', 'summaries', 'batches',
    'generation', 'payloads', 'responses'
}


@dataclass
class DiscoveredApp:
    model_slug: str
    app_number: int
    has_backend: bool
    has_frontend: bool
    has_compose: bool


def _normalize_slug(raw: str) -> str:
    return raw.strip().replace(' ', '_').replace('/', '_').lower()


def _infer_provider(slug: str) -> str:
    for sep in ('_', '-'):  # take earliest separation
        if sep in slug:
            return slug.split(sep, 1)[0] or 'local'
    return slug.split('/', 1)[0] if '/' in slug else slug


def _looks_like_model_dir(directory: Path) -> bool:
    """Return True when directory appears to contain generated app content."""
    try:
        for child in directory.iterdir():
            if not child.is_dir():
                continue
            name_low = child.name.lower()
            if name_low.startswith('app') and any(ch.isdigit() for ch in name_low):
                return True
        for fname in ('docker-compose.yml', 'docker-compose.yaml', 'docker-compose.generated.yml'):
            if (directory / fname).is_file():
                return True
    except Exception:  # pragma: no cover - defensive against permission issues
        return False
    return False


def _discover_model_dirs() -> Iterable[Path]:
    """Yield concrete model directories from known filesystem layouts."""
    roots = []
    # 1) Unified project-root generated/apps
    if GENERATED_APPS_DIR.exists():
        roots.append(GENERATED_APPS_DIR)

    # 2) Legacy project-root generated (mixed content)
    legacy_generated = Path('generated')
    if legacy_generated.exists() and legacy_generated != GENERATED_APPS_DIR.parent:
        roots.append(legacy_generated)

    # 3) Legacy standalone models directory
    legacy_models = Path('models')
    if legacy_models.exists():
        roots.append(legacy_models)

    seen: set[Path] = set()

    def _register(path: Path):
        try:
            if not path.is_dir() or path.name.startswith('_'):
                return None
            key = path.resolve()
            if key in seen:
                return None
            seen.add(key)
            return path
        except Exception:  # pragma: no cover - e.g. broken symlink
            return None

    for root in roots:
        try:
            if root == GENERATED_APPS_DIR:
                for child in root.iterdir():
                    registered = _register(child)
                    if registered:
                        yield registered
                continue

            for child in root.iterdir():
                if not child.is_dir() or child.name.startswith('_'):
                    continue

                # Legacy generated/apps subfolder (contains actual model dirs)
                if child.name.lower() == 'apps':
                    try:
                        for grandchild in child.iterdir():
                            registered = _register(grandchild)
                            if registered:
                                yield registered
                    except Exception:  # pragma: no cover
                        continue
                    continue

                # Ignore known metadata/support folders in legacy layouts
                if child.name.lower() in LEGACY_METADATA_NAMES:
                    continue

                if not _looks_like_model_dir(child):
                    continue

                registered = _register(child)
                if registered:
                    yield registered
        except Exception:  # pragma: no cover
            continue


def _discover_apps(model_dir: Path) -> Iterable[DiscoveredApp]:
    # match app directories named app1, app01, app_1, app1/, etc.
    for child in model_dir.iterdir():
        if not child.is_dir():
            continue
        name_low = child.name.lower()
        if name_low.startswith('app'):
            # Extract trailing digits
            digits = ''.join(c for c in name_low if c.isdigit())
            if not digits:
                continue
            try:
                num = int(digits)
            except ValueError:
                continue
            has_backend = (child / 'backend').is_dir()
            has_frontend = (child / 'frontend').is_dir()
            has_compose = any(
                (model_dir / fname).is_file() or (child / fname).is_file()
                for fname in (
                    'docker-compose.yml', 'docker-compose.yaml', 'docker-compose.generated.yml'
                )
            )
            yield DiscoveredApp(
                model_slug=model_dir.name,
                app_number=num,
                has_backend=has_backend,
                has_frontend=has_frontend,
                has_compose=has_compose,
            )


def upsert_model_and_application(model_slug: str, app_number: int, *, provider: Optional[str] = None,
                                 has_backend: bool = False, has_frontend: bool = False,
                                 has_compose: bool = False) -> Dict[str, Any]:
    """Upsert a single model + application pair.

    Returns dict with keys: model_created, app_created, model_slug, app_number.
    """
    canonical_slug = _normalize_slug(model_slug)
    provider = provider or _infer_provider(canonical_slug) or 'local'

    model = ModelCapability.query.filter_by(canonical_slug=canonical_slug).first()
    model_created = False
    if not model:
        model = ModelCapability()
        model.model_id = canonical_slug
        model.canonical_slug = canonical_slug
        model.provider = provider
        model.model_name = model_slug
        model.installed = True
        db.session.add(model)
        model_created = True
    else:
        # Ensure installed flag sticks if filesystem copy exists
        if not model.installed:
            model.installed = True

    app = GeneratedApplication.query.filter_by(model_slug=canonical_slug, app_number=app_number).first()
    app_created = False
    if not app:
        app = GeneratedApplication()
        app.model_slug = canonical_slug
        app.app_number = app_number
        app.app_type = 'web_app'
        app.provider = provider
        app.generation_status = AnalysisStatus.COMPLETED
        app.has_backend = has_backend
        app.has_frontend = has_frontend
        app.has_docker_compose = has_compose
        app.container_status = 'stopped'
        db.session.add(app)
        app_created = True
    else:
        # Update existing flags if new info appears
        if has_backend and not app.has_backend:
            app.has_backend = True
        if has_frontend and not app.has_frontend:
            app.has_frontend = True
        if has_compose and not app.has_docker_compose:
            app.has_docker_compose = True

    return {
        'model_created': model_created,
        'app_created': app_created,
        'model_slug': canonical_slug,
        'app_number': app_number,
    }


def sync_models_from_filesystem() -> Dict[str, Any]:
    """Scan filesystem and upsert DB rows. Returns summary counts."""
    model_dirs = list(_discover_model_dirs())
    created_models = 0
    created_apps = 0
    updated_apps = 0
    seen_models: set[str] = set()

    for mdir in model_dirs:
        slug = mdir.name
        canonical_slug = _normalize_slug(slug)
        provider = _infer_provider(canonical_slug)
        apps = list(_discover_apps(mdir))
        if not apps:
            # Skip directories without concrete app folders; they likely hold metadata
            continue
        seen_models.add(canonical_slug)
        for app in apps:
            res = upsert_model_and_application(
                app.model_slug,
                app.app_number,
                provider=provider,
                has_backend=app.has_backend,
                has_frontend=app.has_frontend,
                has_compose=app.has_compose,
            )
            if res['model_created']:
                created_models += 1
            if res['app_created']:
                created_apps += 1
            else:
                updated_apps += 1

    # Clean up placeholder records created from metadata directories in prior runs
    metadata_slugs = {_normalize_slug(name) for name in LEGACY_METADATA_NAMES}
    cleanup_slugs = metadata_slugs - seen_models
    removed_apps = removed_models = 0
    if cleanup_slugs:
        removed_apps = GeneratedApplication.query.filter(
            GeneratedApplication.model_slug.in_(cleanup_slugs)
        ).delete(synchronize_session=False)
        removed_models = ModelCapability.query.filter(
            ModelCapability.canonical_slug.in_(cleanup_slugs)
        ).delete(synchronize_session=False)

    # Single commit flush
    db.session.commit()
    return {
        'scanned_model_dirs': len(model_dirs),
        'created_models': created_models,
        'created_apps': created_apps,
        'updated_apps': updated_apps,
        'removed_placeholder_apps': removed_apps,
        'removed_placeholder_models': removed_models,
        'total_models_in_db': ModelCapability.query.count(),
        'total_apps_in_db': GeneratedApplication.query.count(),
    }

__all__ = [
    'sync_models_from_filesystem',
    'upsert_model_and_application'
]
