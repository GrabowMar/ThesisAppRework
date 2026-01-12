"""Code Generator
================

Generates application code using LLM.
Supports both guarded (4-query) and unguarded (single-query) modes.
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.paths import TEMPLATES_V2_DIR, REQUIREMENTS_DIR, SCAFFOLDING_DIR
from app.models import ModelCapability

from .config import GenerationConfig, GenerationMode, QueryType, GenerationResult
from .api_client import get_api_client, OpenRouterClient

logger = logging.getLogger(__name__)

# Directory for saving prompts/responses
RAW_PAYLOADS_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'payloads'
RAW_RESPONSES_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'responses'


class CodeGenerator:
    """Generates application code via LLM queries.
    
    Guarded mode (4 queries):
    1. backend_user - Models and user-facing routes
    2. backend_admin - Admin routes  
    3. frontend_user - User-facing React components
    4. frontend_admin - Admin dashboard components
    
    Unguarded mode (2 queries):
    1. backend - All backend code
    2. frontend - All frontend code
    """
    
    # Query order for guarded mode
    GUARDED_QUERIES = [
        QueryType.BACKEND_USER,
        QueryType.BACKEND_ADMIN,
        QueryType.FRONTEND_USER,
        QueryType.FRONTEND_ADMIN,
    ]
    
    def __init__(self):
        self.client = get_api_client()
        self.templates_dir = TEMPLATES_V2_DIR
        self.requirements_dir = REQUIREMENTS_DIR
        self.scaffolding_info = SCAFFOLDING_DIR / "SCAFFOLDING_INFO.md"
        self._run_id = str(uuid.uuid4())[:8]  # Unique ID for this generation run
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def _save_payload(self, config: GenerationConfig, component: str, 
                      model: str, messages: list, temperature: float, max_tokens: int) -> None:
        """Save the request payload for debugging and prompt viewing."""
        try:
            safe_model = re.sub(r'[^\w\-.]', '_', config.model_slug)
            payloads_dir = RAW_PAYLOADS_DIR / safe_model / f'app{config.app_num}'
            payloads_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f'{safe_model}_app{config.app_num}_{component}_{timestamp}_payload.json'
            
            payload_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'run_id': self._run_id,
                'payload': {
                    'model': model,
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': max_tokens,
                    'provider': {
                        'allow_fallbacks': True,
                        'data_collection': 'allow',
                    }
                }
            }
            
            (payloads_dir / filename).write_text(
                json.dumps(payload_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.debug(f"Saved payload: {filename}")
        except Exception as e:
            logger.warning(f"Failed to save payload: {e}")
    
    def _save_response(self, config: GenerationConfig, component: str, response: Dict[str, Any]) -> None:
        """Save the API response for debugging and prompt viewing."""
        try:
            safe_model = re.sub(r'[^\w\-.]', '_', config.model_slug)
            responses_dir = RAW_RESPONSES_DIR / safe_model / f'app{config.app_num}'
            responses_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f'{safe_model}_app{config.app_num}_{component}_{timestamp}_response.json'
            
            response_data = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'run_id': self._run_id,
                'response': response,
            }
            
            (responses_dir / filename).write_text(
                json.dumps(response_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
            logger.debug(f"Saved response: {filename}")
        except Exception as e:
            logger.warning(f"Failed to save response: {e}")
    
    async def generate(self, config: GenerationConfig) -> Dict[str, str]:
        """Generate all code for an app.
        
        Args:
            config: Generation configuration
            
        Returns:
            Dict mapping query type to generated code:
            - Guarded: {backend_user, backend_admin, frontend_user, frontend_admin}
            - Unguarded: {backend, frontend}
            
        Raises:
            RuntimeError: If any query fails
        """
        if config.is_guarded:
            return await self._generate_guarded(config)
        else:
            return await self._generate_unguarded(config)
    
    async def _generate_guarded(self, config: GenerationConfig) -> Dict[str, str]:
        """Generate code using 4-query guarded mode."""
        results = {}
        
        # Load template requirements
        requirements = self._load_requirements(config.template_slug)
        if not requirements:
            raise RuntimeError(f"Template not found: {config.template_slug}")
        
        # Get OpenRouter model ID
        openrouter_model = self._get_openrouter_model(config.model_slug)
        if not openrouter_model:
            raise RuntimeError(f"Model not found in database: {config.model_slug}")
        
        logger.info(f"Generating {config.model_slug}/app{config.app_num} (4-query guarded)")
        logger.info(f"  Template: {config.template_slug}")
        logger.info(f"  Model ID: {openrouter_model}")
        
        for query_type in self.GUARDED_QUERIES:
            logger.info(f"  → Query {query_type.value}")
            
            # Build prompt from template
            prompt = self._build_prompt(query_type.value, requirements, results)
            system_prompt = self._get_system_prompt(query_type.value)
            
            # Make API call
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            
            # Save payload before API call
            if config.save_artifacts:
                self._save_payload(config, query_type.value, openrouter_model, 
                                   messages, config.temperature, config.max_tokens)
            
            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
            )
            
            # Save response after API call
            if config.save_artifacts and success:
                self._save_response(config, query_type.value, response)
            
            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Query {query_type.value} failed: {error}")
            
            # Extract code from response
            code = self._extract_code(response, query_type)
            results[query_type.value] = code
            
            logger.info(f"    ✓ {len(code)} chars generated")
        
        return results
    
    async def _generate_unguarded(self, config: GenerationConfig) -> Dict[str, str]:
        """Generate code using 2-query unguarded mode."""
        results = {}
        
        # Load template requirements
        requirements = self._load_requirements(config.template_slug)
        if not requirements:
            raise RuntimeError(f"Template not found: {config.template_slug}")
        
        # Get OpenRouter model ID
        openrouter_model = self._get_openrouter_model(config.model_slug)
        if not openrouter_model:
            raise RuntimeError(f"Model not found in database: {config.model_slug}")
        
        logger.info(f"Generating {config.model_slug}/app{config.app_num} (2-query unguarded)")
        
        for component in ['backend', 'frontend']:
            logger.info(f"  → Query {component}")
            
            # Build prompt
            prompt = self._build_unguarded_prompt(component, requirements)
            system_prompt = self._get_system_prompt(component)
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            
            # Save payload before API call
            if config.save_artifacts:
                self._save_payload(config, component, openrouter_model,
                                   messages, config.temperature, config.max_tokens)
            
            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
            )
            
            # Save response after API call
            if config.save_artifacts and success:
                self._save_response(config, component, response)
            
            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Query {component} failed: {error}")
            
            code = self._extract_code(response, component)
            results[component] = code
            
            logger.info(f"    ✓ {len(code)} chars generated")
        
        return results
    
    def _load_requirements(self, template_slug: str) -> Optional[Dict[str, Any]]:
        """Load requirements JSON for a template."""
        # Try exact match first
        json_path = self.requirements_dir / f"{template_slug}.json"
        if not json_path.exists():
            # Try with underscores
            normalized = template_slug.lower().replace('-', '_')
            json_path = self.requirements_dir / f"{normalized}.json"
        
        if not json_path.exists():
            logger.error(f"Requirements file not found: {json_path}")
            return None
        
        try:
            return json.loads(json_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {json_path}: {e}")
            return None
    
    def _get_openrouter_model(self, model_slug: str) -> Optional[str]:
        """Get OpenRouter model ID from database."""
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            return None
        
        # Priority: hugging_face_id > base_model_id > model_id
        return model.hugging_face_id or model.base_model_id or model.model_id
    
    def _build_prompt(self, query_type: str, requirements: Dict, previous: Dict[str, str]) -> str:
        """Build prompt from Jinja2 template."""
        template_name = f"four-query/{query_type}.md.jinja2"
        
        try:
            template = self.jinja_env.get_template(template_name)
        except Exception as e:
            logger.error(f"Template not found: {template_name}")
            raise RuntimeError(f"Missing template: {template_name}")
        
        # Build context from requirements
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'backend_requirements': requirements.get('backend_requirements', []),
            'frontend_requirements': requirements.get('frontend_requirements', []),
            'admin_requirements': requirements.get('admin_requirements', []),
            'api_endpoints': self._format_endpoints(requirements.get('api_endpoints', [])),
            'admin_api_endpoints': self._format_endpoints(requirements.get('admin_api_endpoints', [])),
            'data_model': requirements.get('data_model', {}),
        }
        
        # Add previous query results for context
        if query_type == 'backend_admin' and 'backend_user' in previous:
            context['models_context'] = self._extract_models_summary(previous['backend_user'])
        
        if query_type.startswith('frontend_') and 'backend_user' in previous:
            context['api_context'] = self._extract_api_summary(previous['backend_user'])
        
        return template.render(**context)
    
    def _build_unguarded_prompt(self, component: str, requirements: Dict) -> str:
        """Build prompt for unguarded mode."""
        template_name = f"unguarded/{component}.md.jinja2"
        
        try:
            template = self.jinja_env.get_template(template_name)
        except Exception:
            # Fallback to combined prompt
            return self._build_fallback_prompt(component, requirements)
        
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'requirements': requirements.get(f'{component}_requirements', []),
            'api_endpoints': self._format_endpoints(requirements.get('api_endpoints', [])),
        }
        
        return template.render(**context)
    
    def _build_fallback_prompt(self, component: str, requirements: Dict) -> str:
        """Build simple fallback prompt if template missing."""
        name = requirements.get('name', 'Application')
        reqs = requirements.get(f'{component}_requirements', [])
        reqs_text = '\n'.join(f"- {r}" for r in reqs)
        
        if component == 'backend':
            return f"""Generate the complete Flask backend for: {name}

Requirements:
{reqs_text}

Generate complete, working Python code for models.py and routes."""
        else:
            return f"""Generate the complete React frontend for: {name}

Requirements:
{reqs_text}

Generate complete, working React components (App.jsx, App.css)."""
    
    def _format_endpoints(self, endpoints: List[Dict]) -> str:
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
    
    def _extract_models_summary(self, backend_code: str) -> str:
        """Extract model class names from backend code."""
        classes = re.findall(r'class\s+(\w+)\s*\([^)]*db\.Model', backend_code)
        if classes:
            return f"Available models: {', '.join(classes)}"
        return ""
    
    def _extract_api_summary(self, backend_code: str) -> str:
        """Extract route paths from backend code."""
        routes = re.findall(r"@\w+_bp\.route\s*\(\s*['\"]([^'\"]+)['\"]", backend_code)
        if routes:
            return f"Backend endpoints: {', '.join(routes[:10])}"
        return ""
    
    def _get_system_prompt(self, query_type: str) -> str:
        """Get system prompt for query type."""
        base = """You are an expert full-stack developer generating production-quality code.
Rules:
- Generate ONLY code, no explanations
- Use proper error handling
- Follow best practices for the framework
- Output complete, working code"""
        
        if 'backend' in query_type:
            return base + """

Backend specifics:
- Flask 3.x with Flask-SQLAlchemy 3.1+
- SQLite database at sqlite:////app/data/app.db
- Use blueprints (user_bp, admin_bp) with @bp.route() decorator
- Include proper to_dict() methods on models
- Use db.session.rollback() in exception handlers"""
        else:
            return base + """

Frontend specifics:
- React 18+ with Vite
- Use functional components with hooks
- Style with plain CSS (App.css)
- Use fetch() for API calls to /api/...
- Handle loading and error states"""
    
    def _extract_code(self, response: Dict, query_type) -> str:
        """Extract code from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        
        content = choices[0].get('message', {}).get('content', '')
        
        # Extract from code blocks if present
        # Matches: ```python, ```python:filename.py, ```javascript, ```jsx, etc.
        code_blocks = re.findall(r'```(?:[\w:./]+)?\n(.*?)```', content, re.DOTALL)
        if code_blocks:
            return '\n\n'.join(block.strip() for block in code_blocks)
        
        # Return raw content if no code blocks
        return content.strip()


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get shared code generator instance."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
