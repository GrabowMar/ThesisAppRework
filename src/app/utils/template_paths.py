"""Template path compatibility helpers.

This module provides a compatibility layer after the large-scale template
restructure. Route code (and possibly background tasks) may still reference
legacy template paths like:

  - views/.../*.html
  - partials/common/error.html -> pages/errors/errors_main.html
  - partials/analysis/...

Rather than eagerly touching every call site, we maintain a mapping derived
from the JSON produced by the restructuring script (RESTRUCTURE_MAPPING.json)
and transparently rewrite legacy names to their new locations.

Usage:
    from .template_paths import render_template_compat as render_template

Then call exactly as before:
    return render_template('views/applications/index.html', **ctx)

The wrapper will replace the template name (and the common context key
"main_partial") with the new path if a mapping exists.

If the mapping file is missing (e.g. in a production build where it was not
packaged) the helper becomes a no-op.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from flask import render_template as _flask_render_template
from jinja2.loaders import BaseLoader
from jinja2.exceptions import TemplateNotFound
from typing import Tuple, Callable

logger = logging.getLogger(__name__)


def _templates_root() -> Path:
    # src/app/utils -> parents: 0=utils,1=app,2=src
    return Path(__file__).resolve().parents[2] / 'templates'


@lru_cache(maxsize=1)
def _load_mapping() -> Dict[str, str]:
    """Load old->new template mapping from RESTRUCTURE_MAPPING.json.

    Returns an empty dict if the file is absent or malformed.
    """
    mapping_file = _templates_root() / 'RESTRUCTURE_MAPPING.json'
    if not mapping_file.exists():
        return {}
    try:
        data = json.loads(mapping_file.read_text(encoding='utf-8'))
        changed = data.get('changed_files') or {}
        # Normalize keys (defensive) – ensure forward slashes
        normalized = {k.replace('\\', '/'): v.replace('\\', '/') for k, v in changed.items()}
        return normalized
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Failed to load template mapping: {e}")
        return {}


def remap_template(name: str) -> str:
    """Return the new template path if the legacy name was moved.

    Applies lightweight heuristics if the explicit mapping entry is missing
    (e.g., simple 'views/' -> 'pages/' renames) to reduce maintenance friction.
    """
    mapping = _load_mapping()
    # Fast path
    if name in mapping:
        return mapping[name]

    # Heuristic 1: views/* -> pages/*
    if name.startswith('views/'):
        candidate = name.replace('views/', 'pages/', 1)
        if (_templates_root() / candidate).exists():
            return candidate

    # Heuristic 2: common error partial relocated to pages/errors/main.html
    if name == 'partials/common/error.html' and (_templates_root() / 'pages/errors/main.html').exists():
        return 'pages/errors/main.html'

    # Heuristic 3: dashboard/system health inner partial moved under pages/system/partials
    if name.startswith('partials/dashboard/_system_health_inner'):
        candidate = 'pages/system/partials/_system_health_inner.html'
        if (_templates_root() / candidate).exists():
            return candidate

    # Heuristic 4 removed: dashboard analyzer services/stat cards templates deleted.

    # Heuristic 5: comparison matrix moved under pages/models/partials
    if name.startswith('partials/models/comparison_matrix'):
        candidate = 'pages/models/partials/comparison_matrix.html'
        if (_templates_root() / candidate).exists():
            return candidate

    # Heuristic 6 removed: active_tasks partial deprecated and removed.

    # Heuristic 7: reports index may still reside under app/templates/pages/reports
    if name == 'pages/reports/index.html':
        # Primary location (new structure) would be under global templates root.
        primary = _templates_root() / name
        if primary.exists():
            return name
        # Fallback: look under src/app/templates/pages/reports (legacy leftover)
        legacy_alt = Path(__file__).resolve().parents[1] / 'templates' / 'pages' / 'reports' / 'index.html'
        if legacy_alt.exists():
            # Jinja search path may not include this legacy path; copy or remap to a shim under global templates.
            # For safety (avoid filesystem writes at runtime), return original name so caller logs TemplateNotFound
            # only if neither path exists. If fallback exists but not in search path, we expose a synthetic alias.
            # We'll return a synthetic alias under 'pages/_legacy_reports_index.html' if needed.
            synthetic = 'pages/_legacy_reports_index.html'
            synth_path = _templates_root() / synthetic
            try:
                if not synth_path.exists():  # create once
                    synth_path.write_text(legacy_alt.read_text(encoding='utf-8'), encoding='utf-8')
                return synthetic
            except Exception:
                return name
        return name

    # Heuristic 8: error partial moved to pages/errors/main.html
    if name == 'partials/common/error.html':
        candidate = 'pages/errors/main.html'
        if (_templates_root() / candidate).exists():
            return candidate

    # Heuristic 9 removed: single_page.html deprecated.

    return name


def _remap_context(context: Dict[str, Any]) -> Dict[str, Any]:
    # Common keys that contain template partial names we want to auto-remap.
    for key in ('main_partial', 'partial', 'body_partial'):
        if key in context and isinstance(context[key], str):
            context[key] = remap_template(context[key])
    return context


def render_template_compat(template_name: str, /, **context):  # noqa: D401
    """Wrapper for flask.render_template with legacy path compatibility.

    Rewrites the top-level template name and selected context partial keys.
    """
    new_name = remap_template(template_name)
    context = _remap_context(context)
    return _flask_render_template(new_name, **context)


__all__ = [
    'render_template_compat',
    'remap_template',
    'attach_legacy_mapping_loader',
]


class _LegacyMappingLoader(BaseLoader):  # pragma: no cover - integration exercised in higher-level tests
    """Loader that delegates to an underlying loader then falls back to mapping heuristics.

    This allows Jinja {% include %} statements (which bypass our render_template wrapper)
    to still resolve legacy paths after the restructure.
    """

    def __init__(self, wrapped: BaseLoader):
        self._wrapped = wrapped

    def get_source(self, environment, template: str) -> Tuple[str, str, Callable[[], bool]]:  # type: ignore[override]
        # First attempt with the wrapped loader
        try:
            return self._wrapped.get_source(environment, template)  # type: ignore[arg-type]
        except TemplateNotFound:
            # Try remap
            new_name = remap_template(template)
            if new_name != template:
                try:
                    return self._wrapped.get_source(environment, new_name)  # type: ignore[arg-type]
                except TemplateNotFound:
                    pass
            raise


def attach_legacy_mapping_loader(app):  # pragma: no cover - simple wiring
    """Wrap the app's Jinja loader with legacy mapping fallback if not already wrapped."""
    try:
        from jinja2.loaders import ChoiceLoader
        if isinstance(app.jinja_loader, _LegacyMappingLoader):  # already wrapped
            return
        # Some setups use ChoiceLoader; wrap each underlying loader
        jl = app.jinja_loader
        if isinstance(jl, ChoiceLoader):
            jl.loaders = [_LegacyMappingLoader(loader) for loader in jl.loaders]
        else:
            app.jinja_loader = _LegacyMappingLoader(jl)
        logger.info("Legacy mapping Jinja loader attached")
    except Exception as e:  # pragma: no cover
        logger.warning(f"Could not attach legacy mapping loader: {e}")
