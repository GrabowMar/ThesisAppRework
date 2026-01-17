"""Code Generator
================

Generates application code using LLM with a 2-prompt strategy:
1. Generate backend (models, routes, auth)
2. Scan backend to extract API info
3. Generate frontend with backend context
"""

import json
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.paths import TEMPLATES_V2_DIR, REQUIREMENTS_DIR, SCAFFOLDING_DIR
from app.models import ModelCapability

from .config import GenerationConfig, GenerationResult
from .api_client import get_api_client
from .backend_scanner import scan_backend_response, BackendScanResult

logger = logging.getLogger(__name__)

# Directory for saving prompts/responses
RAW_PAYLOADS_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'payloads'
RAW_RESPONSES_DIR = Path(__file__).parent.parent.parent.parent.parent / 'generated' / 'raw' / 'responses'


class CodeGenerator:
    """Generates application code via LLM queries.
    
    2-prompt strategy:
    1. Backend - Models, auth, user routes, admin routes
    2. Frontend - React components with backend API context
    """
    
    def __init__(self):
        self.client = get_api_client()
        self.templates_dir = TEMPLATES_V2_DIR
        self.requirements_dir = REQUIREMENTS_DIR
        self.scaffolding_dir = SCAFFOLDING_DIR
        self._run_id = str(uuid.uuid4())[:8]
        
        # Setup Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    
    def _save_payload(self, config: GenerationConfig, component: str, 
                      model: str, messages: list, temperature: float, max_tokens: int) -> None:
        """Save the request payload for debugging."""
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
                }
            }
            
            (payloads_dir / filename).write_text(
                json.dumps(payload_data, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception as e:
            logger.warning(f"Failed to save payload: {e}")
    
    def _save_response(self, config: GenerationConfig, component: str, response: Dict[str, Any]) -> None:
        """Save the API response for debugging."""
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
        except Exception as e:
            logger.warning(f"Failed to save response: {e}")
    
    async def generate(self, config: GenerationConfig) -> Dict[str, str]:
        """Generate all code for an app using 2-prompt strategy.
        
        Args:
            config: Generation configuration
            
        Returns:
            Dict with 'backend' and 'frontend' raw LLM responses
            
        Raises:
            RuntimeError: If generation fails
        """
        results = {}
        
        # Load template requirements
        requirements = self._load_requirements(config.template_slug)
        if not requirements:
            raise RuntimeError(f"Template not found: {config.template_slug}")
        
        # Get OpenRouter model ID
        openrouter_model = self._get_openrouter_model(config.model_slug)
        if not openrouter_model:
            raise RuntimeError(f"Model not found in database: {config.model_slug}")
        
        logger.info(f"Generating {config.model_slug}/app{config.app_num} (2-prompt)")
        logger.info(f"  Template: {config.template_slug}")
        logger.info(f"  Model ID: {openrouter_model}")
        
        # Step 1: Generate Backend
        logger.info("  → Query 1: Backend")
        backend_prompt = self._build_backend_prompt(requirements)
        backend_system = self._get_backend_system_prompt()
        
        messages = [
            {"role": "system", "content": backend_system},
            {"role": "user", "content": backend_prompt},
        ]
        
        if config.save_artifacts:
            self._save_payload(config, 'backend', openrouter_model, 
                               messages, config.temperature, config.max_tokens)
        
        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        )
        
        if config.save_artifacts and success:
            self._save_response(config, 'backend', response)
        
        if not success:
            error = response.get('error', 'Unknown error')
            if isinstance(error, dict):
                error = error.get('message', str(error))
            raise RuntimeError(f"Backend generation failed: {error}")
        
        backend_code = self._extract_content(response)
        results['backend'] = backend_code
        logger.info(f"    ✓ Backend: {len(backend_code)} chars")
        
        # Step 2: Scan backend for API context
        logger.info("  → Scanning backend for API context...")
        scan_result = scan_backend_response(backend_code)
        backend_api_context = scan_result.to_frontend_context()
        logger.info(f"    ✓ Found {len(scan_result.endpoints)} endpoints, {len(scan_result.models)} models")
        
        # Step 3: Generate Frontend with backend context
        logger.info("  → Query 2: Frontend")
        frontend_prompt = self._build_frontend_prompt(requirements, backend_api_context)
        frontend_system = self._get_frontend_system_prompt()
        
        messages = [
            {"role": "system", "content": frontend_system},
            {"role": "user", "content": frontend_prompt},
        ]
        
        if config.save_artifacts:
            self._save_payload(config, 'frontend', openrouter_model,
                               messages, config.temperature, config.max_tokens)
        
        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            timeout=config.timeout,
        )
        
        if config.save_artifacts and success:
            self._save_response(config, 'frontend', response)
        
        if not success:
            error = response.get('error', 'Unknown error')
            if isinstance(error, dict):
                error = error.get('message', str(error))
            raise RuntimeError(f"Frontend generation failed: {error}")
        
        frontend_code = self._extract_content(response)
        results['frontend'] = frontend_code
        logger.info(f"    ✓ Frontend: {len(frontend_code)} chars")
        
        return results
    
    def _load_requirements(self, template_slug: str) -> Optional[Dict[str, Any]]:
        """Load requirements JSON for a template."""
        json_path = self.requirements_dir / f"{template_slug}.json"
        if not json_path.exists():
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
        return model.hugging_face_id or model.base_model_id or model.model_id
    
    def _build_backend_prompt(self, requirements: Dict) -> str:
        """Build backend prompt from template."""
        template = self.jinja_env.get_template("two-query/backend.md.jinja2")
        
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'backend_requirements': requirements.get('backend_requirements', []),
            'admin_requirements': requirements.get('admin_requirements', []),
            'api_endpoints': self._format_endpoints(requirements.get('api_endpoints', [])),
            'admin_api_endpoints': self._format_endpoints(requirements.get('admin_api_endpoints', [])),
            'data_model': requirements.get('data_model', {}),
        }
        
        return template.render(**context)
    
    def _build_frontend_prompt(self, requirements: Dict, backend_api_context: str) -> str:
        """Build frontend prompt with backend context."""
        template = self.jinja_env.get_template("two-query/frontend.md.jinja2")
        
        context = {
            'name': requirements.get('name', 'Application'),
            'description': requirements.get('description', ''),
            'frontend_requirements': requirements.get('frontend_requirements', []),
            'admin_requirements': requirements.get('admin_requirements', []),
            'backend_api_context': backend_api_context,
        }
        
        return template.render(**context)
    
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
    
    def _get_backend_system_prompt(self) -> str:
        """Get system prompt for backend generation."""
        return """You are an expert Flask backend developer. Generate complete, production-ready code.

CRITICAL RULES:
- Generate ONLY ONE file: app.py with ALL code
- No placeholders, no TODOs, no "..."
- Every import must be valid
- Every function must be fully implemented
- All models need to_dict() methods
- Use proper error handling with try/except

OUTPUT FORMAT:
- Generate ONLY: ```python:app.py with complete application
- Include: models, auth decorators, all routes in ONE file
- Optionally include ```requirements for additional packages

AUTHENTICATION:
- Implement JWT auth with bcrypt passwords
- token_required and admin_required decorators
- /api/auth/register, /api/auth/login, /api/auth/me endpoints

ROUTE PATTERNS:
- User routes: /api/* (e.g., /api/items)
- Admin routes: /api/admin/* (e.g., /api/admin/stats)
- Auth routes: /api/auth/* (e.g., /api/auth/login)"""
    
    def _get_frontend_system_prompt(self) -> str:
        """Get system prompt for frontend generation."""
        return """You are an expert React frontend developer. Generate complete, production-ready code.

CRITICAL RULES:
- Generate ONLY ONE file: App.jsx with ALL code
- No placeholders, no TODOs
- Every component must be complete
- Handle loading and error states
- Use react-hot-toast for notifications

OUTPUT FORMAT:
- Generate ONLY: ```jsx:App.jsx with complete application
- Include: API client, auth context, all pages, navigation in ONE file
- The file must export App as default

AVAILABLE PACKAGES ONLY:
react, react-dom, react-router-dom, axios, react-hot-toast, @heroicons/react, date-fns, clsx, uuid
DO NOT import any other packages.

STRUCTURE INSIDE App.jsx:
1. API client with axios
2. Auth functions (login, register, logout)
3. AuthContext and useAuth hook
4. LoginPage component
5. UserPage component
6. AdminPage component
7. Navigation component
8. ProtectedRoute wrapper
9. Main App component with BrowserRouter"""
    
    def _extract_content(self, response: Dict) -> str:
        """Extract content from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        return choices[0].get('message', {}).get('content', '').strip()


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get shared code generator instance."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
