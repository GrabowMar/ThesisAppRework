"""Scaffolding Manager
=====================

Copies and configures scaffolding templates for app generation.
Simple, focused on one job: create the project structure.
"""

import logging
import re
import shutil
from pathlib import Path
from typing import Dict, Tuple, Optional

from app.paths import SCAFFOLDING_DIR, GENERATED_APPS_DIR
from app.services.port_allocation_service import get_port_allocation_service

from .config import GenerationConfig

logger = logging.getLogger(__name__)


class ScaffoldingManager:
    """Creates app scaffolding from templates.
    
    Handles:
    - Copying scaffolding files to app directory
    - Port allocation for backend/frontend
    - Template variable substitution
    """
    
    # Single scaffolding template
    SCAFFOLDING_DIR_NAME = "react-flask"
    
    def __init__(self):
        self.port_service = get_port_allocation_service()
    
    def get_scaffolding_dir(self) -> Path:
        """Get scaffolding source directory."""
        return SCAFFOLDING_DIR / self.SCAFFOLDING_DIR_NAME
    
    def allocate_ports(self, model_slug: str, app_num: int) -> Tuple[int, int]:
        """Allocate backend and frontend ports.
        
        Returns:
            Tuple of (backend_port, frontend_port)
        """
        try:
            port_pair = self.port_service.get_or_allocate_ports(model_slug, app_num)
            return (port_pair.backend, port_pair.frontend)
        except Exception as e:
            logger.error(f"Port allocation failed: {e}")
            raise RuntimeError(f"Failed to allocate ports for {model_slug}/app{app_num}") from e
    
    def create_scaffolding(self, config: GenerationConfig) -> Path:
        """Create app scaffolding from template.
        
        Args:
            config: Generation configuration
            
        Returns:
            Path to created app directory
            
        Raises:
            RuntimeError: If scaffolding fails
        """
        # Determine paths
        app_dir = config.get_app_dir(GENERATED_APPS_DIR)
        scaffolding_dir = self.get_scaffolding_dir()
        
        logger.info(f"Creating scaffolding: {config.model_slug}/app{config.app_num}")
        logger.info(f"  Source: {scaffolding_dir}")
        logger.info(f"  Target: {app_dir}")
        
        if not scaffolding_dir.exists():
            raise RuntimeError(f"Scaffolding source not found: {scaffolding_dir}")
        
        # Allocate ports (or use overrides)
        if config.backend_port and config.frontend_port:
            backend_port = config.backend_port
            frontend_port = config.frontend_port
        else:
            backend_port, frontend_port = self.allocate_ports(config.model_slug, config.app_num)
        
        logger.info(f"  Ports: backend={backend_port}, frontend={frontend_port}")
        
        # Create app directory
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Build substitution map
        sanitized_slug = re.sub(r'[^a-z0-9_-]+', '-', config.safe_model_slug.lower()).strip('-_')
        project_name = f"{sanitized_slug}_app{config.app_num}"
        compose_name = f"{sanitized_slug}-app{config.app_num}"
        
        substitutions = {
            'backend_port': str(backend_port),
            'frontend_port': str(frontend_port),
            'PROJECT_NAME': project_name,
            'project_name': project_name,
            'COMPOSE_PROJECT_NAME': compose_name,
            'compose_project_name': compose_name,
            'BACKEND_PORT': str(backend_port),
            'FRONTEND_PORT': str(frontend_port),
            # App number for container name fallbacks
            'app_num': str(config.app_num),
        }
        
        # Copy all files with substitutions
        copied = 0
        for src_path in scaffolding_dir.rglob('*'):
            if src_path.is_dir():
                continue
            
            rel_path = src_path.relative_to(scaffolding_dir)
            dest_path = app_dir / rel_path
            
            # Rename .env.example → .env
            if rel_path.name == '.env.example':
                dest_path = dest_path.parent / '.env'
            
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # Try text file with substitutions
                content = src_path.read_text(encoding='utf-8')
                content = self._apply_substitutions(content, substitutions)
                dest_path.write_text(content, encoding='utf-8')
                copied += 1
            except UnicodeDecodeError:
                # Binary file - copy as-is
                shutil.copy2(src_path, dest_path)
                copied += 1
            except Exception as e:
                logger.warning(f"Failed to copy {rel_path}: {e}")
        
        logger.info(f"Scaffolding complete: {copied} files copied")
        
        if copied < 5:
            raise RuntimeError(f"Scaffolding incomplete: only {copied} files copied")
        
        return app_dir
    
    def _apply_substitutions(self, content: str, subs: Dict[str, str]) -> str:
        """Apply template substitutions to content.
        
        Handles patterns:
        - {{key}} → value
        - {{key|default}} → value
        """
        for key, value in subs.items():
            # {{key|default}} pattern
            content = re.sub(
                r'\{\{' + re.escape(key) + r'\|[^\}]+\}\}',
                value,
                content
            )
            # {{key}} pattern
            content = content.replace(f'{{{{{key}}}}}', value)
        
        return content


# Singleton
_manager: Optional[ScaffoldingManager] = None


def get_scaffolding_manager() -> ScaffoldingManager:
    """Get shared scaffolding manager instance."""
    global _manager
    if _manager is None:
        _manager = ScaffoldingManager()
    return _manager
