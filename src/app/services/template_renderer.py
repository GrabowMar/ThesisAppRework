"""
Template Renderer Service
Handles Jinja2 template rendering for application generation prompts.
Combines requirements JSON, scaffolding files, and templates into final prompts.
"""

import json
import logging
from typing import Dict, Any, List, Tuple
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from app.paths import MISC_DIR

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """Service for rendering generation templates with requirements and scaffolding"""
    
    def __init__(self):
        """Initialize the template renderer with Jinja2 environment"""
        self.templates_dir = MISC_DIR / "templates"
        self.scaffolding_dir = MISC_DIR / "scaffolding"
        self.requirements_dir = MISC_DIR / "requirements"
        
        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False,  # Don't escape markdown content
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        logger.info(f"Template renderer initialized with templates dir: {self.templates_dir}")
    
    def list_requirements(self) -> List[Dict[str, Any]]:
        """
        List all available requirements JSON files
        
        Returns:
            List of dicts with requirement metadata
        """
        requirements = []
        
        if not self.requirements_dir.exists():
            logger.warning(f"Requirements directory not found: {self.requirements_dir}")
            return requirements
        
        for req_file in self.requirements_dir.glob("*.json"):
            try:
                with open(req_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    requirements.append({
                        'id': data.get('app_id', req_file.stem),
                        'name': data.get('name', req_file.stem),
                        'description': data.get('description', ''),
                        'filename': req_file.name
                    })
            except Exception as e:
                logger.error(f"Failed to load requirement {req_file}: {e}")
        
        return requirements
    
    def list_scaffolding_types(self) -> List[str]:
        """
        List all available scaffolding types
        
        Returns:
            List of scaffolding type names
        """
        if not self.scaffolding_dir.exists():
            logger.warning(f"Scaffolding directory not found: {self.scaffolding_dir}")
            return []
        
        return [d.name for d in self.scaffolding_dir.iterdir() if d.is_dir()]
    
    def list_template_types(self) -> List[str]:
        """
        List all available template types
        
        Returns:
            List of template type names
        """
        if not self.templates_dir.exists():
            logger.warning(f"Templates directory not found: {self.templates_dir}")
            return []
        
        return [d.name for d in self.templates_dir.iterdir() if d.is_dir()]
    
    def load_requirements(self, requirement_id: str) -> Dict[str, Any]:
        """
        Load requirements from JSON file
        
        Args:
            requirement_id: ID or filename of requirement (e.g., 'xsd_verifier' or 'xsd_verifier.json')
        
        Returns:
            Requirements dictionary
        
        Raises:
            FileNotFoundError: If requirement file doesn't exist
            json.JSONDecodeError: If JSON is invalid
        """
        # Handle both with and without .json extension
        if not requirement_id.endswith('.json'):
            requirement_id += '.json'
        
        req_path = self.requirements_dir / requirement_id
        
        if not req_path.exists():
            raise FileNotFoundError(f"Requirement file not found: {req_path}")
        
        with open(req_path, 'r', encoding='utf-8') as f:
            requirements = json.load(f)
        
        logger.info(f"Loaded requirements from {req_path}")
        return requirements
    
    def load_scaffolding(self, scaffolding_type: str) -> Dict[str, Dict[str, str]]:
        """
        Load all scaffolding files for a given type
        
        Args:
            scaffolding_type: Type of scaffolding (e.g., 'react-flask')
        
        Returns:
            Dict with structure:
            {
                'backend': {'app_py': '...', 'requirements_txt': '...'},
                'frontend': {'package_json': '...', 'index_html': '...', 'app_jsx': '...', 'app_css': '...'}
            }
        
        Raises:
            FileNotFoundError: If scaffolding type doesn't exist
        """
        scaffolding_path = self.scaffolding_dir / scaffolding_type
        
        if not scaffolding_path.exists():
            raise FileNotFoundError(f"Scaffolding type not found: {scaffolding_path}")
        
        scaffolding = {
            'backend': {},
            'frontend': {}
        }
        
        # Load backend files
        backend_path = scaffolding_path / 'backend'
        if backend_path.exists():
            for file_path in backend_path.iterdir():
                if file_path.is_file():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        # Convert filename to variable name (e.g., app.py -> app_py)
                        var_name = file_path.name.replace('.', '_').replace('-', '_')
                        scaffolding['backend'][var_name] = f.read()
        
        # Load frontend files
        frontend_path = scaffolding_path / 'frontend'
        if frontend_path.exists():
            # Load root files
            for file_path in frontend_path.iterdir():
                if file_path.is_file():
                    with open(file_path, 'r', encoding='utf-8') as f:
                        var_name = file_path.name.replace('.', '_').replace('-', '_')
                        scaffolding['frontend'][var_name] = f.read()
            
            # Load src files
            src_path = frontend_path / 'src'
            if src_path.exists():
                for file_path in src_path.iterdir():
                    if file_path.is_file():
                        with open(file_path, 'r', encoding='utf-8') as f:
                            var_name = file_path.name.replace('.', '_').replace('-', '_')
                            scaffolding['frontend'][var_name] = f.read()
        
        logger.info(f"Loaded scaffolding for type: {scaffolding_type}")
        return scaffolding
    
    def render_template(
        self,
        template_type: str,
        component: str,
        requirements: Dict[str, Any],
        scaffolding: Dict[str, Dict[str, str]]
    ) -> str:
        """
        Render a template with requirements and scaffolding
        
        Args:
            template_type: Type of template (e.g., 'two-query')
            component: Component to render ('backend' or 'frontend')
            requirements: Requirements dictionary
            scaffolding: Scaffolding dictionary
        
        Returns:
            Rendered markdown prompt
        
        Raises:
            TemplateNotFound: If template doesn't exist
        """
        # Construct template path
        template_path = f"{template_type}/{component}.md.jinja2"
        
        try:
            template = self.jinja_env.get_template(template_path)
        except TemplateNotFound:
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        # Build context for rendering
        context = {
            # Requirements data
            'app_id': requirements.get('app_id', ''),
            'name': requirements.get('name', ''),
            'description': requirements.get('description', ''),
            'backend_requirements': requirements.get('backend_requirements', []),
            'frontend_requirements': requirements.get('frontend_requirements', []),
        }
        
        # Add scaffolding variables for the specific component
        for k, v in scaffolding.get(component, {}).items():
            context[f'scaffolding_{k}'] = v
        
        # Render template
        rendered = template.render(**context)
        
        logger.info(f"Rendered template: {template_path} for {requirements.get('name', 'unknown')}")
        return rendered
    
    def render_both(
        self,
        template_type: str,
        requirement_id: str,
        scaffolding_type: str
    ) -> Tuple[str, str]:
        """
        Render both backend and frontend templates
        
        Args:
            template_type: Type of template (e.g., 'two-query')
            requirement_id: ID of requirements JSON
            scaffolding_type: Type of scaffolding (e.g., 'react-flask')
        
        Returns:
            Tuple of (backend_prompt, frontend_prompt)
        """
        # Load requirements and scaffolding
        requirements = self.load_requirements(requirement_id)
        scaffolding = self.load_scaffolding(scaffolding_type)
        
        # Render both components
        backend_prompt = self.render_template(
            template_type, 'backend', requirements, scaffolding
        )
        frontend_prompt = self.render_template(
            template_type, 'frontend', requirements, scaffolding
        )
        
        return backend_prompt, frontend_prompt
    
    def preview(
        self,
        template_type: str,
        requirement_id: str,
        scaffolding_type: str
    ) -> Dict[str, str]:
        """
        Preview rendered templates without generating
        
        Args:
            template_type: Type of template
            requirement_id: ID of requirements JSON
            scaffolding_type: Type of scaffolding
        
        Returns:
            Dict with 'backend' and 'frontend' keys containing rendered prompts
        """
        backend_prompt, frontend_prompt = self.render_both(
            template_type, requirement_id, scaffolding_type
        )
        
        return {
            'backend': backend_prompt,
            'frontend': frontend_prompt
        }


# Singleton instance
_renderer = None


def get_template_renderer() -> TemplateRenderer:
    """Get or create the template renderer singleton"""
    global _renderer
    if _renderer is None:
        _renderer = TemplateRenderer()
    return _renderer
