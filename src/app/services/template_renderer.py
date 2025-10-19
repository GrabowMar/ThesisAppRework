"""Template renderer shim to maintain compatibility with legacy imports."""

from __future__ import annotations

import warnings
from typing import Any, Dict, List, Optional

from app.services.generation import get_generation_service


class TemplateRenderer:
    """Minimal shim that surfaces template metadata from GenerationService."""

    def __init__(self) -> None:
        warnings.warn(
            "TemplateRenderer is deprecated. Use get_generation_service().get_template_catalog().",
            DeprecationWarning,
            stacklevel=2,
        )

    def list_requirements(self) -> List[Dict[str, Any]]:
        """Return template metadata in the legacy shape."""
        catalog = get_generation_service().get_template_catalog()
        return [
            {
                'id': item['id'],
                'name': item['name'],
                'description': item.get('description', ''),
                'filename': item.get('filename', f"{item['id']}.json"),
            }
            for item in catalog
        ]

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - defensive guard
        raise RuntimeError(
            f"TemplateRenderer.{name} is no longer available. "
            "Use GenerationService for template metadata or scaffolding operations."
        )


_renderer: Optional[TemplateRenderer] = None


def get_template_renderer() -> TemplateRenderer:
    """Return the shim singleton, mirroring the old access pattern."""
    global _renderer
    if _renderer is None:
        _renderer = TemplateRenderer()
    return _renderer


__all__ = ['get_template_renderer', 'TemplateRenderer']
