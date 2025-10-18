"""Lightweight system monitoring helpers for dashboard endpoints.

The modern code path does not rely on a dedicated monitoring daemon, but the
API still imports ``get_system_stats``. Provide a minimal implementation that
reports CPU, memory, and disk utilisation when ``psutil`` is available and
returns sensible defaults otherwise.
"""
from __future__ import annotations

from typing import Dict

import shutil


def _collect_cpu_percent() -> float:
    try:
        import psutil  # type: ignore

        return float(psutil.cpu_percent(interval=0.1))
    except Exception:  # pragma: no cover - psutil optional
        return 0.0


def _collect_memory_percent() -> float:
    try:
        import psutil  # type: ignore

        return float(psutil.virtual_memory().percent)
    except Exception:  # pragma: no cover - psutil optional
        return 0.0


def _collect_disk_usage() -> float:
    try:
        usage = shutil.disk_usage("/")
        if usage.total:
            return round((usage.used / usage.total) * 100, 2)
    except Exception:  # pragma: no cover - general fallback
        pass
    return 0.0


def get_system_stats() -> Dict[str, float]:
    """Return basic system utilisation metrics for dashboard display."""
    return {
        "cpu_percent": _collect_cpu_percent(),
        "memory_percent": _collect_memory_percent(),
        "disk_usage": _collect_disk_usage(),
    }
