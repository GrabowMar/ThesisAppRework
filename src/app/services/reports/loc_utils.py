"""LOC counting helpers for reports.

Multiple report generators need to derive LOC directly from generated app files
when generation metadata is unavailable.

This module provides a shared implementation to avoid drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Union


def count_loc_from_generated_files(
    model_slug: str,
    app_numbers: Union[int, List[int]],
) -> Dict[str, Any]:
    """Count lines of code directly from generated app files.

    Counts non-empty, non-comment lines in backend Python files and frontend
    JavaScript/JSX files, excluding scaffolding files.

    Returns a dict compatible with existing report expectations:
    total_loc, backend_loc, frontend_loc, per_app breakdown, counted.
    """

    import os

    # Normalize app_numbers to a list
    if isinstance(app_numbers, int):
        app_numbers = [app_numbers]

    # Known scaffolding files to exclude (only count AI-generated code)
    scaffolding_files = {
        # Backend scaffolding (not AI-generated)
        'app.py',
        # Frontend scaffolding
        'vite.config.js',
        'tailwind.config.js',
        'postcss.config.js',
    }

    scaffolding_dirs = {
        'node_modules',
        '__pycache__',
        '.git',
        'dist',
        'build',
    }

    base_path = Path(__file__).resolve().parent.parent.parent.parent.parent / 'generated' / 'apps'
    safe_slug = model_slug.replace('/', '_').replace('\\', '_')
    model_path = base_path / safe_slug

    result: Dict[str, Any] = {
        'total_loc': 0,
        'backend_loc': 0,
        'frontend_loc': 0,
        'per_app': {},
        'counted': False,
    }

    if not model_path.exists():
        return result

    for app_num in app_numbers:
        app_path = model_path / f"app{app_num}"
        if not app_path.exists():
            continue

        app_backend_loc = 0
        app_frontend_loc = 0

        # Count backend Python files
        backend_path = app_path / 'backend'
        if backend_path.exists():
            for root, dirs, files in os.walk(backend_path):
                dirs[:] = [d for d in dirs if d not in scaffolding_dirs]

                for filename in files:
                    if filename.endswith('.py') and filename not in scaffolding_files:
                        filepath = Path(root) / filename
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = [
                                    line
                                    for line in f.readlines()
                                    if line.strip() and not line.strip().startswith('#')
                                ]
                                app_backend_loc += len(lines)
                        except Exception:
                            pass

        # Count frontend JS/JSX files
        frontend_path = app_path / 'frontend' / 'src'
        if frontend_path.exists():
            for root, dirs, files in os.walk(frontend_path):
                dirs[:] = [d for d in dirs if d not in scaffolding_dirs]

                for filename in files:
                    if filename.endswith(('.js', '.jsx')) and filename not in scaffolding_files:
                        filepath = Path(root) / filename
                        try:
                            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                lines = [
                                    line
                                    for line in f.readlines()
                                    if line.strip() and not line.strip().startswith('//')
                                ]
                                app_frontend_loc += len(lines)
                        except Exception:
                            pass

        app_total = app_backend_loc + app_frontend_loc

        result['per_app'][app_num] = {
            'app_number': app_num,
            'total_loc': app_total,
            'backend_loc': app_backend_loc,
            'frontend_loc': app_frontend_loc,
        }

        result['backend_loc'] += app_backend_loc
        result['frontend_loc'] += app_frontend_loc
        result['total_loc'] += app_total

    result['counted'] = result['total_loc'] > 0
    return result
