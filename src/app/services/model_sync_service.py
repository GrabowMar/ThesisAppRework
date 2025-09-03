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
    GENERATED_APPS_DIR = Path('src/generated/apps')

from app.extensions import db
from app.models import ModelCapability, GeneratedApplication
from app.constants import AnalysisStatus


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


def _discover_model_dirs() -> Iterable[Path]:
    """Yield model directory roots from legacy and new layouts.

    Order:
      1. New unified generated/apps/*
      2. Legacy top-level models/*
      3. Legacy generated/* (older mixed layout)
    """
    roots = []
    # 1) Unified path
    if GENERATED_APPS_DIR.exists():
        roots.append(GENERATED_APPS_DIR)
    # 2) Legacy explicit
    legacy_models = Path('models')
    if legacy_models.exists():
        roots.append(legacy_models)
    # 3) Legacy generic generated (pre-refactor)
    legacy_generated = Path('generated')
    if legacy_generated.exists():
        roots.append(legacy_generated)

    seen = set()
    for root in roots:
        try:
            for child in root.iterdir():
                if not child.is_dir() or child.name.startswith('_'):
                    continue
                # In unified path, model dir is direct child of generated/apps
                if root == GENERATED_APPS_DIR:
                    key = child.resolve()
                    if key in seen:
                        continue
                    seen.add(key)
                    yield child
                else:
                    key = child.resolve()
                    if key in seen:
                        continue
                    seen.add(key)
                    yield child
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
    models_seen = set()
    created_models = 0
    created_apps = 0
    updated_apps = 0

    for mdir in model_dirs:
        slug = mdir.name
        canonical_slug = _normalize_slug(slug)
        provider = _infer_provider(canonical_slug)
        apps = list(_discover_apps(mdir))
        if not apps:
            # Still create model row if directory exists (placeholder)
            res = upsert_model_and_application(slug, 1, provider=provider)
            if res['model_created']:
                created_models += 1
            if res['app_created']:
                created_apps += 1
            else:
                updated_apps += 1
            continue
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
        models_seen.add(canonical_slug)

    # Single commit flush
    db.session.commit()
    return {
        'scanned_model_dirs': len(model_dirs),
        'created_models': created_models,
        'created_apps': created_apps,
        'updated_apps': updated_apps,
        'total_models_in_db': ModelCapability.query.count(),
        'total_apps_in_db': GeneratedApplication.query.count(),
    }

__all__ = [
    'sync_models_from_filesystem',
    'upsert_model_and_application'
]
