"""Prompt Loader Service
=====================

Handles loading and rendering of prompt templates for code generation.
Centralizes all prompt logic to separate it from the execution logic.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.paths import MISC_DIR, SCAFFOLDING_DIR, PROMPTS_V2_DIR

logger = logging.getLogger(__name__)

class PromptLoader:
    """Loads and renders prompts for code generation."""
    
    def __init__(self):
        if not PROMPTS_V2_DIR.exists():
            logger.error(f"Prompts V2 directory not found at {PROMPTS_V2_DIR}")
        
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(PROMPTS_V2_DIR)),
            autoescape=select_autoescape(['html', 'xml', 'jinja2']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def _read_scaffolding_file(self, relative_path: str) -> str:
        """Read content from scaffolding file (legacy support)."""
        # Scaffolding is currently in misc/scaffolding/react-flask
        scaffold_base = SCAFFOLDING_DIR / 'react-flask'
        file_path = scaffold_base / relative_path
        
        if not file_path.exists():
            logger.error(f"Scaffolding file not found: {file_path}")
            return f"# Error: Scaffolding file not found at {relative_path}"
            
        return file_path.read_text(encoding='utf-8')

    def get_backend_prompts(self, requirements: Dict[str, Any]) -> Tuple[str, str]:
        """
        Get system and user prompts for Backend generation.
        
        Args:
            requirements: The loaded requirements dictionary
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        # Load scaffolding code to inject into prompt
        scaffolding_code = self._read_scaffolding_file('backend/app.py')
        
        # Prepare context
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'backend_requirements': requirements.get('backend_requirements', []),
            'admin_requirements': requirements.get('admin_requirements', []),
            'api_endpoints': self._format_endpoints(requirements.get('api_endpoints', [])),
            'admin_api_endpoints': self._format_endpoints(requirements.get('admin_api_endpoints', [])),
            'data_model': requirements.get('data_model', {}),
            'scaffolding_code': scaffolding_code
        }
        
        system_template = self.jinja_env.get_template("backend/system.md.jinja2")
        user_template = self.jinja_env.get_template("backend/user.md.jinja2")
        
        return system_template.render(), user_template.render(**context)

    def get_frontend_prompts(self, requirements: Dict[str, Any], backend_api_context: str) -> Tuple[str, str]:
        """
        Get system and user prompts for Frontend generation.
        
        Args:
            requirements: The loaded requirements dictionary
            backend_api_context: The extracted API context from the generated backend
            
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'frontend_requirements': requirements.get('frontend_requirements', []),
            'admin_requirements': requirements.get('admin_requirements', []),
            'backend_api_context': backend_api_context,
        }
        
        system_template = self.jinja_env.get_template("frontend/system.md.jinja2")
        user_template = self.jinja_env.get_template("frontend/user.md.jinja2")
        
        return system_template.render(), user_template.render(**context)

    def _format_endpoints(self, endpoints: list) -> str:
        """Format API endpoints for prompt."""
        if not endpoints:
            return ""
        
        lines = []
        for ep in endpoints:
            method = ep.get('method', 'GET')
            path = ep.get('path', '/')
            desc = ep.get('description', '')
            lines.append(f"- {method} {path}: {desc}")
        
        return '\n'.join(lines)
