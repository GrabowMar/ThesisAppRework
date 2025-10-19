"""Legacy simple generation shim.

This module previously hosted the standalone ``SimpleGenerationService``. The
codebase now standardizes on :mod:`app.services.generation`. To avoid circular
imports or stale dependencies, the old entry point simply proxies to the new
service and emits a deprecation warning when accessed.
"""

from __future__ import annotations

import warnings
from typing import Any

from app.services.generation import get_generation_service


def get_simple_generation_service() -> Any:
    """Return the primary GenerationService singleton.

    The legacy simple generation service has been removed; callers should use
    ``get_generation_service`` directly. A deprecation warning is emitted to
    highlight the change while maintaining import compatibility.
    """

    warnings.warn(
        "SimpleGenerationService has been retired. Use get_generation_service() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_generation_service()


__all__ = [
    'get_simple_generation_service',
]
