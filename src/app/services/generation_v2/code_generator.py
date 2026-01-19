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
        frontend_finish = self._get_finish_reason(response)

        if frontend_finish == 'length':
            logger.warning("Frontend response truncated (finish_reason=length); requesting continuation")
            frontend_code = await self._continue_frontend(
                openrouter_model,
                messages,
                frontend_code,
                config,
            )

        if not self._has_frontend_code_block(frontend_code):
            logger.warning("Frontend response missing JSX code block; retrying with strict prompt")
            strict_system = (
                self._get_frontend_system_prompt()
                + "\n\nSTRICT MODE: Output ONLY a single JSX code block with filename App.jsx."
                + " No prose, no questions, no extra commentary."
            )
            strict_user = (
                frontend_prompt
                + "\n\nSTRICT OUTPUT: Return ONLY one code block in this exact format:"
                + "\n```jsx:App.jsx\n...full code...\n```"
            )

            messages = [
                {"role": "system", "content": strict_system},
                {"role": "user", "content": strict_user},
            ]

            strict_temperature = min(config.temperature, 0.2)

            if config.save_artifacts:
                self._save_payload(config, 'frontend_retry', openrouter_model,
                                   messages, strict_temperature, config.max_tokens)

            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=strict_temperature,
                max_tokens=config.max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts and success:
                self._save_response(config, 'frontend_retry', response)

            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Frontend generation failed on retry: {error}")

            frontend_code = self._extract_content(response)
            frontend_finish = self._get_finish_reason(response)

            if frontend_finish == 'length':
                logger.warning("Frontend retry truncated (finish_reason=length); requesting continuation")
                frontend_code = await self._continue_frontend(
                    openrouter_model,
                    messages,
                    frontend_code,
                    config,
                )

        if not self._has_frontend_code_block(frontend_code):
            coerced = self._coerce_frontend_output(frontend_code)
            if coerced:
                logger.warning("Coerced frontend output into JSX code block")
                frontend_code = coerced

        if not self._has_frontend_code_block(frontend_code):
            raise RuntimeError("Frontend generation produced no JSX code block")

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
        return """You are an expert Flask backend developer. Generate a COMPLETE, PRODUCTION-READY Flask application.

## OUTPUT: ONE FILE ONLY
Generate EXACTLY ONE file: `app.py` containing ALL code (400-600 lines).
DO NOT create models.py, routes.py, or any other files.

## EXACT FILE STRUCTURE (follow this order):

```python:app.py
import os
import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import bcrypt
import jwt

# 1. Flask app setup
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////app/data/app.db')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
db = SQLAlchemy(app)
CORS(app)

# 2. Models - User model + app-specific models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=False)  # bcrypt returns bytes
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'username': self.username, 'email': self.email,
                'is_admin': self.is_admin, 'is_active': self.is_active}

# 3. Auth decorators
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user = User.query.get(data['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'Invalid user'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except:
            return jsonify({'error': 'Invalid token'}), 401
        return f(user, *args, **kwargs)
    return decorated

def admin_required(f):
    # Similar to token_required but also checks user.is_admin
    ...

# 4. Auth routes: /api/auth/register, /api/auth/login, /api/auth/me, /api/auth/me (PUT)
# 5. User routes: /api/* endpoints for main functionality
# 6. Admin routes: /api/admin/* endpoints
# 7. Health check: /api/health

# 8. Database initialization - CRITICAL PATTERN (required for gunicorn)
def init_db():
    db.create_all()
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@example.com', is_admin=True)
        admin.password_hash = bcrypt.hashpw('admin123'.encode(), bcrypt.gensalt())
        db.session.add(admin)
        db.session.commit()

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('FLASK_RUN_PORT', 5000)))
```

## FORBIDDEN PATTERNS (will crash the app):
- ❌ @app.before_first_request - REMOVED in Flask 2.3+
- ❌ init_db() without with app.app_context() - crashes under gunicorn

## REQUIREMENTS:
- JWT tokens with 24-hour expiration using PyJWT
- bcrypt for password hashing (hashpw returns bytes, store as LargeBinary)
- All models must have to_dict() methods
- Input validation with descriptive errors
- Proper HTTP status codes (200, 201, 400, 401, 403, 404)
- Pagination for list endpoints (page, per_page query params)
- Default admin: username=admin, password=admin123, is_admin=True

## CRITICAL RULES:
1. NO placeholders, NO TODOs, NO "..." - generate COMPLETE code
2. NO "Would you like me to continue?" - generate EVERYTHING
3. Every route must be fully implemented
4. Do NOT ask questions or request clarification; make reasonable assumptions and proceed
5. Generate 400-600 lines of working code"""
    
    def _get_frontend_system_prompt(self) -> str:
        """Get system prompt for frontend generation."""
        return """You are an expert React frontend developer. Generate a COMPLETE, PRODUCTION-READY React application.

## OUTPUT: ONE FILE ONLY
Generate EXACTLY ONE file: `App.jsx` containing ALL code (600-900 lines).
DO NOT create separate component files, hooks files, or service files.

## EXACT FILE STRUCTURE (follow this order):

```jsx:App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, PencilIcon } from '@heroicons/react/24/outline';

// 1. API Client Setup
const baseURL = import.meta.env.VITE_BACKEND_URL
  ? `${import.meta.env.VITE_BACKEND_URL.replace(/\\/$/, '')}/api`
  : '/api';

const api = axios.create({ baseURL });
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// 2. API Functions
const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};
// Add app-specific API functions here

// 3. Auth Context
const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      authAPI.me().then(res => setUser(res.data)).catch(() => localStorage.removeItem('token')).finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => { /* ... */ };
  const register = async (data) => { /* ... */ };
  const logout = () => { localStorage.removeItem('token'); setUser(null); };

  return <AuthContext.Provider value={{ user, loading, login, register, logout, isAuthenticated: !!user, isAdmin: user?.is_admin }}>{children}</AuthContext.Provider>;
}

const useAuth = () => useContext(AuthContext);

// 4. Utility Components
function LoadingSpinner() { return <div className="flex justify-center"><div className="animate-spin ..."></div></div>; }
function ProtectedRoute({ children, adminOnly }) { /* redirect if not auth */ }

// 5. Navigation
function Navigation() { /* Links: Home, Admin (if admin), Login/Logout */ }

// 6. Page Components
function HomePage() { /* Main app page - public read-only + logged-in CRUD via conditional rendering */ }
function LoginPage() { /* Form with validation, error handling, loading state */ }
function RegisterPage() { /* Form with password confirmation */ }
function AdminPage() { /* Stats cards, data table, bulk actions, search */ }

// 7. Main App - NO BrowserRouter (main.jsx provides it)
function App() {
  return (
    <AuthProvider>
      <div className="min-h-screen bg-gray-50">
        <Navigation />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/admin" element={<ProtectedRoute adminOnly><AdminPage /></ProtectedRoute>} />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  );
}

export default App;
```

## CRITICAL: Do NOT wrap App in BrowserRouter - main.jsx already provides it!

## AVAILABLE PACKAGES (only use these):
react, react-dom, react-router-dom, axios, react-hot-toast, @heroicons/react, date-fns, clsx, uuid

## PAGE REQUIREMENTS:
- HomePage: Main app page with conditional rendering:
  * Fetches ALL data from public read endpoint (works without auth)
  * Public users: Read-only view + "Sign in to create/edit" CTAs
  * Logged-in users: Same content + create/edit/delete buttons + additional features
- LoginPage: Username/password form, loading state, error display, link to register, redirects to / on success
- RegisterPage: Username/email/password/confirm form, validation, link to login, redirects to / on success
- AdminPage: Stats cards, full data table, toggle status, bulk delete, search/filter

## UI REQUIREMENTS:
- Tailwind CSS for ALL styling
- Loading spinners during async operations
- Empty states with helpful messages
- Toast notifications (toast.success, toast.error)
- Responsive design

## CRITICAL RULES:
1. NO placeholders, NO TODOs, NO "..." - generate COMPLETE code
2. NO "Would you like me to continue?" - generate EVERYTHING
3. Do NOT ask questions or request clarification; make reasonable assumptions and proceed
4. Every component must be fully implemented with real JSX
5. Generate 600-900 lines of working code"""
    
    def _extract_content(self, response: Dict) -> str:
        """Extract content from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        return choices[0].get('message', {}).get('content', '').strip()

    def _get_finish_reason(self, response: Dict) -> str:
        """Extract finish reason from API response."""
        choices = response.get('choices', [])
        if not choices:
            return ""
        return (choices[0].get('finish_reason') or choices[0].get('native_finish_reason') or '').strip()

    async def _continue_frontend(
        self,
        model: str,
        base_messages: list,
        base_content: str,
        config: GenerationConfig,
        max_continuations: int = 2,
    ) -> str:
        """Request continuation for truncated frontend output and stitch code blocks."""
        stitched_code = self._extract_app_jsx_code(base_content)
        if stitched_code is None:
            stitched_code = ""

        continuation_prompt = (
            "Continue the App.jsx output from where you left off. "
            "Return ONLY the remaining code, wrapped in a single code block: "
            "```jsx:App.jsx\n...\n```. Do not repeat content already provided."
        )

        content = base_content
        for idx in range(max_continuations):
            messages = (
                list(base_messages)
                + [{"role": "assistant", "content": content},
                   {"role": "user", "content": continuation_prompt}]
            )

            success, response, status = await self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=min(config.temperature, 0.2),
                max_tokens=config.max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts:
                self._save_response(config, f'frontend_continue_{idx + 1}', response)

            if not success:
                error = response.get('error', 'Unknown error')
                if isinstance(error, dict):
                    error = error.get('message', str(error))
                raise RuntimeError(f"Frontend continuation failed: {error}")

            continuation_content = self._extract_content(response)
            continuation_code = self._extract_app_jsx_code(continuation_content) or ""

            stitched_code = self._merge_continuation(stitched_code, continuation_code)
            content = continuation_content

            finish = self._get_finish_reason(response)
            if finish != 'length':
                break

        if not stitched_code.strip():
            return base_content

        return f"```jsx:App.jsx\n{stitched_code.strip()}\n```"

    def _extract_app_jsx_code(self, content: str) -> Optional[str]:
        """Extract App.jsx code from a fenced JSX block; allow missing closing fence."""
        if not content:
            return None
        match = re.search(
            r"```\s*(jsx|javascript|js|tsx|typescript|ts)(?::([^\n\r`]+))?\s*[\r\n]+",
            content,
            re.IGNORECASE,
        )
        if not match:
            return None
        start = match.end()
        end_match = re.search(r"```", content[start:])
        if end_match:
            end = start + end_match.start()
            return content[start:end].strip()
        return content[start:].strip()

    def _merge_continuation(self, base_code: str, continuation: str) -> str:
        """Merge continuation code, trimming overlapping tail/head lines."""
        if not base_code.strip():
            return continuation
        if not continuation.strip():
            return base_code

        base_lines = base_code.splitlines()
        cont_lines = continuation.splitlines()

        max_overlap = min(50, len(base_lines), len(cont_lines))
        overlap = 0
        for i in range(1, max_overlap + 1):
            if base_lines[-i:] == cont_lines[:i]:
                overlap = i
        if overlap:
            cont_lines = cont_lines[overlap:]

        return "\n".join(base_lines + cont_lines)

    def _has_frontend_code_block(self, content: str) -> bool:
        """Return True if the content includes a JSX code block."""
        if not content:
            return False
        if re.search(r"```\s*(jsx|javascript|js|tsx|typescript|ts)(?::[^\n\r`]*)?\s*[\r\n]+", content, re.IGNORECASE):
            return True

        # Accept unlabeled fenced blocks if they look like JSX
        fence_match = re.search(r"```\s*[\r\n]+(.*?)```", content, re.DOTALL)
        if fence_match:
            return self._looks_like_jsx(fence_match.group(1))

        return False

    def _looks_like_jsx(self, code: str) -> bool:
        """Heuristic check for JSX/React code presence."""
        if not code:
            return False
        signals = (
            r"\bimport\s+React\b",
            r"from\s+['\"]react['\"]",
            r"\bfunction\s+App\b",
            r"\bconst\s+App\b",
            r"\bexport\s+default\s+App\b",
            r"<div[^>]*>",
            r"return\s*\("
        )
        return any(re.search(pattern, code) for pattern in signals)

    def _coerce_frontend_output(self, content: str) -> Optional[str]:
        """Coerce frontend output into a JSX code block if possible."""
        if not content:
            return None

        # Prefer fenced blocks if present (even without language)
        for match in re.finditer(r"```(?:[a-zA-Z0-9_+-]+)?(?::[^\n\r`]*)?\s*[\r\n]+(.*?)```", content, re.DOTALL):
            code = (match.group(1) or '').strip()
            if self._looks_like_jsx(code):
                return f"```jsx:App.jsx\n{code}\n```"

        # Fallback: treat entire content as code if it looks like JSX
        if self._looks_like_jsx(content):
            return f"```jsx:App.jsx\n{content.strip()}\n```"

        return None


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get shared code generator instance."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
