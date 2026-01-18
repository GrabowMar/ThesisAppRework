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
        return """You are an expert Flask backend developer generating production-ready applications.

ABSOLUTE REQUIREMENTS:
1. Generate EXACTLY ONE file: app.py containing ALL code (400-600 lines)
2. DO NOT split code into multiple files (no models.py, no routes/*.py)
3. NO placeholders, NO TODOs, NO "...", NO incomplete functions
4. NO "Would you like me to continue?" - generate EVERYTHING in one response
5. Every function must be FULLY implemented with real logic
6. All models must have complete to_dict() methods

FILE STRUCTURE (in this exact order):
1. Imports (os, logging, datetime, functools, flask, sqlalchemy, cors, bcrypt, jwt)
2. Flask app creation and configuration
3. SQLAlchemy db = SQLAlchemy() setup
4. ALL Model classes with to_dict() methods
5. Auth decorators (token_required, admin_required)
6. Auth routes (/api/auth/register, /api/auth/login, /api/auth/me)
7. User routes (/api/*)
8. Admin routes (/api/admin/*)
9. Health check route (/api/health)
10. Database initialization with create_all() and default admin user
11. Main entry point (if __name__ == '__main__')

AUTHENTICATION REQUIREMENTS:
- JWT tokens with 24-hour expiration
- bcrypt password hashing
- User model: id, username, email, password_hash, is_admin, is_active, created_at, updated_at
- Create default admin user on startup (username: admin, password: admin123)

CODE QUALITY:
- Input validation with descriptive error messages
- Try/except blocks for database operations
- Proper HTTP status codes (200, 201, 400, 401, 403, 404, 500)
- Pagination for list endpoints (page, per_page, total)
- Soft delete pattern (is_active=False instead of hard delete)

OUTPUT FORMAT:
```python:app.py
# Complete Flask application - 400-600 lines of production code
# ALL models, auth, and routes in this single file
```

Optional:
```requirements
package-name==1.0.0
```"""
    
    def _get_frontend_system_prompt(self) -> str:
        """Get system prompt for frontend generation."""
        return """You are an expert React frontend developer generating production-ready applications.

ABSOLUTE REQUIREMENTS:
1. Generate EXACTLY ONE file: App.jsx containing ALL code (600-900 lines)
2. DO NOT split code into multiple files (no separate components, services, or hooks files)
3. NO placeholders, NO TODOs, NO "...", NO "// LLM:" comments
4. NO "Would you like me to continue?" - generate EVERYTHING in one response
5. Every component must be FULLY implemented with real JSX and logic
6. All forms must have proper validation and error handling

FILE STRUCTURE (in this exact order):
1. All imports at the top
2. API client setup (axios instance with auth interceptor)
3. All API functions organized by domain (authAPI, itemsAPI, adminAPI)
4. AuthContext and AuthProvider with full implementation
5. useAuth hook
6. Utility components (LoadingSpinner, ProtectedRoute)
7. Navigation component with conditional links
8. All Page components (HomePage, LoginPage, RegisterPage, UserPage, AdminPage)
9. Main App component with Routes (NO BrowserRouter - main.jsx provides it)
10. export default App

CRITICAL: Do NOT wrap App in BrowserRouter. main.jsx already provides it.

AVAILABLE PACKAGES (use only these):
react, react-dom, react-router-dom, axios, react-hot-toast, @heroicons/react, date-fns, clsx, uuid

COMPONENT REQUIREMENTS:
- HomePage: Public page with guest view and logged-in summary
- LoginPage: Form with username/password, error handling, loading state
- RegisterPage: Form with username/email/password/confirm, validation
- UserPage: Full CRUD interface with list, create, edit, delete
- AdminPage: Dashboard stats, data table, bulk actions, search/filter

UI QUALITY:
- Tailwind CSS for all styling
- Loading states with spinners
- Error states with helpful messages
- Empty states with call-to-action
- Toast notifications for success/error
- Responsive design

OUTPUT FORMAT:
```jsx:App.jsx
// Complete React application - 600-900 lines of production code
// ALL components, auth, and pages in this single file
```"""
    
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
