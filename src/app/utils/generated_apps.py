"""Utilities for accessing generated apps and related JSON metadata.

Safe, read-only helpers consolidating path logic so routes/services don't
hardcode locations. All functions fail gracefully and never raise on missing
files/directories (they return empty structures + error notes where helpful).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List, Tuple
import json
import logging

from config.settings import Config
from app.paths import GENERATED_APPS_DIR, MISC_DIR

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Tuple[Any, List[str]]:
    """Load JSON from path. Returns (data, errors)."""
    errors: List[str] = []
    if not path.exists():
        return None, [f"missing: {path.name}"]
    try:
        return json.loads(path.read_text(encoding='utf-8')), errors
    except Exception as e:  # noqa: BLE001
        errors.append(f"error reading {path.name}: {e}")
        return None, errors


def load_models_summary() -> Dict[str, Any]:
    path = Path(getattr(Config, 'MODELS_SUMMARY_FILE', MISC_DIR / 'models_summary.json'))
    data, errors = _load_json(path)
    return {"data": data, "errors": errors}


def load_port_config() -> Dict[str, Any]:
    data, errors = _load_json(Path(Config.PORT_CONFIG_FILE))
    # Normalize to list
    if data is not None and not isinstance(data, list):
        logger.warning("port_config.json not list; coercing to empty list")
        data = []
    return {"data": data, "errors": errors}


def list_generated_models() -> List[str]:
    if not GENERATED_APPS_DIR.exists():
        return []
    return [d.name for d in GENERATED_APPS_DIR.iterdir() if d.is_dir()]


def list_generated_apps(model_slug: str) -> List[int]:
    """Return list of app numbers for a model based on folder names (app1/app_1)."""
    model_dir = GENERATED_APPS_DIR / model_slug
    if not model_dir.exists():
        return []
    nums: List[int] = []
    for d in model_dir.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if name.startswith('app_'):
            part = name.split('_', 1)[1]
            if part.isdigit():
                nums.append(int(part))
        elif name.startswith('app') and name[3:].isdigit():
            nums.append(int(name[3:]))
    return sorted(nums)


def generated_apps_stats() -> Dict[str, Any]:
    models = list_generated_models()
    total_apps = 0
    per_model: Dict[str, int] = {}
    for m in models:
        apps = list_generated_apps(m)
        per_model[m] = len(apps)
        total_apps += len(apps)
    return {
        'models': models,
        'total_models': len(models),
        'total_apps': total_apps,
        'per_model': per_model,
        'root': str(GENERATED_APPS_DIR),
    }


__all__ = [
    'load_models_summary', 'load_port_config',
    'list_generated_models', 'list_generated_apps', 'generated_apps_stats'
]
