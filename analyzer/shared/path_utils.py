"""Shared path resolution utilities for analyzer services."""

from pathlib import Path
from typing import Optional
import logging


def resolve_app_source_path(model_slug: str, app_number: int, base_path: Path = Path('/app/sources')) -> Optional[Path]:
    """
    Resolve application source path supporting both flat and template-based directory structures.
    
    Resolution order (backward compatible):
      1. Flat structure: /app/sources/<model_slug>/app<N>
      2. Template-based structure: /app/sources/<model_slug>/<template>/app<N>
    
    Args:
        model_slug: Model identifier (e.g., 'anthropic_claude-4.5-haiku-20251001')
        app_number: Application number
        base_path: Base directory to search (default: /app/sources for containers)
    
    Returns:
        Path object if found, None if not found
    """
    log = logging.getLogger('path_utils')
    
    # Try flat structure first (backward compatible)
    model_dir = base_path / model_slug
    flat_path = model_dir / f'app{app_number}'
    
    if flat_path.exists():
        log.debug(f"Found app at flat path: {flat_path}")
        return flat_path
    
    # Search template subdirectories (new template-based structure)
    if model_dir.exists() and model_dir.is_dir():
        for template_dir in model_dir.iterdir():
            # Skip hidden directories and files
            if not template_dir.is_dir() or template_dir.name.startswith('.'):
                continue
            
            template_path = template_dir / f'app{app_number}'
            if template_path.exists() and template_path.is_dir():
                log.debug(f"Found app at template path: {template_path}")
                return template_path
    
    # Not found
    log.warning(f"App not found for {model_slug} app{app_number} (checked flat and template structures)")
    return None
