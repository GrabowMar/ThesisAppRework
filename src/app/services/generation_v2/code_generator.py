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

# Patterns that indicate model is asking for confirmation instead of generating
CONFIRMATION_PATTERNS = [
    r"would you like me to",
    r"shall i (proceed|continue|generate)",
    r"do you want me to",
    r"should i (proceed|continue|generate)",
    r"let me know if you",
    r"i can (generate|create|build)",
    r"i'll (generate|create|build).*if you",
    r"ready to (generate|create|proceed)",
]

# Compiled regex for efficiency
CONFIRMATION_REGEX = re.compile(
    '|'.join(CONFIRMATION_PATTERNS),
    re.IGNORECASE
)

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

    def _is_confirmation_seeking(self, content: str) -> bool:
        """Check if response is asking for confirmation instead of generating code.

        Models sometimes ask "Would you like me to generate...?" instead of
        actually generating the code. This detects such responses.
        """
        if not content:
            return False

        # Short responses that match confirmation patterns are likely seeking confirmation
        # Long responses with code are not
        if len(content) > 2000:
            return False

        return bool(CONFIRMATION_REGEX.search(content))

    def _get_model_context_window(self, model_slug: str) -> int:
        """Get model's context window size from database.

        Returns a safe default if not found.
        """
        try:
            model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
            if model and model.context_window and model.context_window > 0:
                return model.context_window
        except Exception as e:
            logger.warning(f"Failed to get context window for {model_slug}: {e}")

        # Default to 128K which is common for modern models
        return 128000

    def _calculate_max_tokens(self, model_slug: str, prompt_tokens_estimate: int = 8000) -> int:
        """Calculate safe max_tokens based on model's context window.

        Ensures we don't request more tokens than the model can handle.
        """
        context_window = self._get_model_context_window(model_slug)

        # Reserve space for prompt and leave buffer
        # Typically: context_window = prompt_tokens + completion_tokens
        # We want: max_tokens = context_window - prompt_estimate - safety_buffer
        safety_buffer = 1000
        available = context_window - prompt_tokens_estimate - safety_buffer

        # Clamp to reasonable range
        # Minimum 8K for basic code generation, maximum 32K for large apps
        return max(8000, min(32000, available))

    def _get_confirmation_response(self) -> str:
        """Get a response to use when model asks for confirmation."""
        return (
            "Yes, generate the complete code now. Output ONLY the code block, "
            "no explanations or questions. Start immediately with ```"
        )

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
        
        # Load template requirements - defines app structure, endpoints, models
        requirements = self._load_requirements(config.template_slug)
        if not requirements:
            raise RuntimeError(f"Template not found: {config.template_slug}")
        
        # Get OpenRouter model ID from database - maps slug to actual API model identifier
        openrouter_model = self._get_openrouter_model(config.model_slug)
        if not openrouter_model:
            raise RuntimeError(f"Model not found in database: {config.model_slug}")
        
        logger.info(f"Generating {config.model_slug}/app{config.app_num} (2-prompt)")
        logger.info(f"  Template: {config.template_slug}")
        logger.info(f"  Model ID: {openrouter_model}")

        # Calculate safe max_tokens based on model's context window to avoid truncation
        max_tokens = self._calculate_max_tokens(config.model_slug)
        logger.info(f"  Max tokens: {max_tokens}")

        # Step 1: Generate Backend - produces Flask app with models, auth, routes
        logger.info("  → Query 1: Backend")
        backend_prompt = self._build_backend_prompt(requirements)
        backend_system = self._get_backend_system_prompt()

        messages = [
            {"role": "system", "content": backend_system},
            {"role": "user", "content": backend_prompt},
        ]

        if config.save_artifacts:
            self._save_payload(config, 'backend', openrouter_model,
                               messages, config.temperature, max_tokens)

        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=max_tokens,
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
        
        # Step 2: Scan backend for API context - extract endpoints, models for frontend generation
        logger.info("  → Scanning backend for API context...")
        scan_result = scan_backend_response(backend_code)
        backend_api_context = scan_result.to_frontend_context()
        logger.info(f"    ✓ Found {len(scan_result.endpoints)} endpoints, {len(scan_result.models)} models")
        
        # Step 3: Generate Frontend with backend context - React app that matches backend API
        logger.info("  → Query 2: Frontend")
        frontend_prompt = self._build_frontend_prompt(requirements, backend_api_context)
        frontend_system = self._get_frontend_system_prompt()

        messages = [
            {"role": "system", "content": frontend_system},
            {"role": "user", "content": frontend_prompt},
        ]

        if config.save_artifacts:
            self._save_payload(config, 'frontend', openrouter_model,
                               messages, config.temperature, max_tokens)

        success, response, status = await self.client.chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=max_tokens,
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

        # Handle truncated responses by requesting continuation from model
        if frontend_finish == 'length':
            logger.warning("Frontend response truncated (finish_reason=length); requesting continuation")
            frontend_code = await self._continue_frontend(
                openrouter_model,
                messages,
                frontend_code,
                config,
                max_tokens,
            )

        # Some models ask for confirmation instead of generating code - handle this edge case
        if self._is_confirmation_seeking(frontend_code):
            logger.warning("Model asking for confirmation; responding with 'Yes, proceed'")
            # Continue the conversation by responding "Yes"
            messages.append({"role": "assistant", "content": frontend_code})
            messages.append({"role": "user", "content": self._get_confirmation_response()})

            if config.save_artifacts:
                self._save_payload(config, 'frontend_confirm', openrouter_model,
                                   messages, config.temperature, max_tokens)

            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=max_tokens,
                timeout=config.timeout,
            )

            if config.save_artifacts and success:
                self._save_response(config, 'frontend_confirm', response)

            if success:
                frontend_code = self._extract_content(response)
                frontend_finish = self._get_finish_reason(response)

                # Handle continuation again if needed after confirmation response
                if frontend_finish == 'length':
                    logger.warning("Frontend confirm response truncated; requesting continuation")
                    frontend_code = await self._continue_frontend(
                        openrouter_model,
                        messages,
                        frontend_code,
                        config,
                        max_tokens,
                    )

        # If frontend still doesn't have proper JSX code block, try strict retry with lower temperature
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
                                   messages, strict_temperature, max_tokens)

            success, response, status = await self.client.chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=strict_temperature,
                max_tokens=max_tokens,
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

            # Handle confirmation seeking even in strict mode
            if self._is_confirmation_seeking(frontend_code):
                logger.warning("Model still asking for confirmation after strict prompt; responding with 'Yes'")
                messages.append({"role": "assistant", "content": frontend_code})
                messages.append({"role": "user", "content": self._get_confirmation_response()})

                if config.save_artifacts:
                    self._save_payload(config, 'frontend_retry_confirm', openrouter_model,
                                       messages, strict_temperature, max_tokens)

                success, response, status = await self.client.chat_completion(
                    model=openrouter_model,
                    messages=messages,
                    temperature=strict_temperature,
                    max_tokens=max_tokens,
                    timeout=config.timeout,
                )

                if config.save_artifacts and success:
                    self._save_response(config, 'frontend_retry_confirm', response)

                if success:
                    frontend_code = self._extract_content(response)
                    frontend_finish = self._get_finish_reason(response)

            # Handle continuation after strict retry if needed
            if frontend_finish == 'length':
                logger.warning("Frontend retry truncated (finish_reason=length); requesting continuation")
                frontend_code = await self._continue_frontend(
                    openrouter_model,
                    messages,
                    frontend_code,
                    config,
                    max_tokens,
                )

        # Final fallback: try to coerce malformed output into proper JSX format
        if not self._has_frontend_code_block(frontend_code):
            coerced = self._coerce_frontend_output(frontend_code)
            if coerced:
                logger.warning("Coerced frontend output into JSX code block")
                frontend_code = coerced

        # Final validation - ensure we have proper JSX code block
        if not self._has_frontend_code_block(frontend_code):
            raise RuntimeError("Frontend generation produced no JSX code block")

        # Clean up any trailing text after code fence that model might have added
        frontend_code = self._sanitize_frontend_output(frontend_code)

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
        return model.get_openrouter_model_id()
    
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

CRITICAL INSTRUCTION: Generate the code IMMEDIATELY. Do NOT ask for confirmation. Do NOT ask "Would you like me to...?" or "Shall I proceed?". Just output the complete code block directly. This is a non-interactive code generation task.

## OUTPUT FORMAT
Generate EXACTLY ONE code block with this format:
```python:app.py
[complete code here - 400-600 lines]
```

## COMPLETE WORKING EXAMPLE STRUCTURE

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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////app/data/app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
db = SQLAlchemy(app)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# ============================================================================
# MODELS
# ============================================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.LargeBinary, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# ADD YOUR APP-SPECIFIC MODELS HERE with to_dict() methods

# ============================================================================
# AUTH DECORATORS
# ============================================================================

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token required'}), 401
        token = auth_header[7:]
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user = db.session.get(User, data['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'Invalid or inactive user'}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(user, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Token required'}), 401
        token = auth_header[7:]
        if not token:
            return jsonify({'error': 'Token required'}), 401
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user = db.session.get(User, data['user_id'])
            if not user or not user.is_active:
                return jsonify({'error': 'Invalid or inactive user'}), 401
            if not user.is_admin:
                return jsonify({'error': 'Admin access required'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(user, *args, **kwargs)
    return decorated

# ============================================================================
# AUTH ROUTES
# ============================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        email = (data.get('email') or '').strip()
        password = data.get('password') or ''

        if not username or len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        if not email or '@' not in email:
            return jsonify({'error': 'Valid email required'}), 400
        if not password or len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400

        user = User(
            username=username,
            email=email,
            password_hash=bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        )
        db.session.add(user)
        db.session.commit()

        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.now(timezone.utc) + timedelta(hours=24)},
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return jsonify({'token': token, 'user': user.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        logger.error(f"Registration error: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        username = (data.get('username') or '').strip()
        password = data.get('password') or ''

        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400

        user = User.query.filter_by(username=username).first()
        if not user or not bcrypt.checkpw(password.encode('utf-8'), user.password_hash):
            return jsonify({'error': 'Invalid credentials'}), 401
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401

        token = jwt.encode(
            {'user_id': user.id, 'exp': datetime.now(timezone.utc) + timedelta(hours=24)},
            app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        return jsonify({'token': token, 'user': user.to_dict()}), 200
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify(current_user.to_dict()), 200

@app.route('/api/auth/me', methods=['PUT'])
@token_required
def update_me(current_user):
    try:
        data = request.get_json() or {}
        if 'email' in data:
            email = (data['email'] or '').strip()
            if email and '@' in email:
                existing = User.query.filter(User.email == email, User.id != current_user.id).first()
                if existing:
                    return jsonify({'error': 'Email already in use'}), 400
                current_user.email = email
        db.session.commit()
        return jsonify(current_user.to_dict()), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update profile error: {e}")
        return jsonify({'error': 'Update failed'}), 500

# ============================================================================
# USER ROUTES - Implement your app-specific endpoints here
# ============================================================================

# Public endpoints (no auth): GET list endpoints return ALL data
# Protected endpoints (token_required): POST, PUT, DELETE

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_list_users(current_user):
    users = User.query.all()
    return jsonify({
        'items': [u.to_dict() for u in users],
        'total': len(users)
    }), 200

# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'backend'}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'}), 200

# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_db():
    db.create_all()
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(
            username='admin',
            email='admin@example.com',
            password_hash=bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        logger.info("Created default admin user")

with app.app_context():
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
```

## CRITICAL REQUIREMENTS

1. **SINGLE FILE**: ALL code in ONE app.py file (400-600 lines)
2. **NO PLACEHOLDERS**: Every function fully implemented, no "...", no TODOs
3. **WORKING AUTH**: bcrypt for passwords (LargeBinary column), PyJWT for tokens
4. **PUBLIC READ**: GET list endpoints return ALL data without authentication
5. **PROTECTED WRITE**: POST/PUT/DELETE require @token_required decorator
6. **ADMIN ROUTES**: Use @admin_required decorator for admin-only endpoints
7. **to_dict() METHODS**: Every model must have a to_dict() method
8. **HEALTH CHECK**: Both /api/health and /health endpoints

## FORBIDDEN PATTERNS
- ❌ @app.before_first_request (removed in Flask 2.3+)
- ❌ Calling init_db() without app.app_context()
- ❌ Using db.Model.query.get() - use db.session.get() instead
- ❌ Placeholders like "# implement here" or "pass"
- ❌ Asking "Would you like me to continue?"

## RESPONSE FORMAT
Output ONLY the code block. No explanations before or after."""
    
    def _get_frontend_system_prompt(self) -> str:
        """Get system prompt for frontend generation."""
        return """You are an expert React frontend developer. Generate a COMPLETE, PRODUCTION-READY React application.

CRITICAL INSTRUCTION: Generate the code IMMEDIATELY. Do NOT ask for confirmation. Do NOT ask "Would you like me to...?" or "Shall I proceed?". Just output the complete code block directly. This is a non-interactive code generation task.

## OUTPUT FORMAT
Generate EXACTLY ONE code block with this format:
```jsx:App.jsx
[complete code here - 600-900 lines]
```

## COMPLETE WORKING EXAMPLE STRUCTURE

```jsx:App.jsx
import React, { useState, useEffect, createContext, useContext } from 'react';
import { Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom';
import axios from 'axios';
import toast from 'react-hot-toast';
import { PlusIcon, TrashIcon, PencilIcon, XMarkIcon, CheckIcon } from '@heroicons/react/24/outline';

// ============================================================================
// API CLIENT
// ============================================================================

const baseURL = import.meta.env.VITE_BACKEND_URL
  ? `${import.meta.env.VITE_BACKEND_URL.replace(/\\/$/, '')}/api`
  : '/api';

const api = axios.create({ baseURL });

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Auth API
const authAPI = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  register: (data) => api.post('/auth/register', data),
  me: () => api.get('/auth/me'),
};

// App-specific API functions here...

// ============================================================================
// AUTH CONTEXT
// ============================================================================

const AuthContext = createContext(null);

function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      authAPI.me()
        .then(res => setUser(res.data))
        .catch(() => {
          localStorage.removeItem('token');
          setUser(null);
        })
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (username, password) => {
    const res = await authAPI.login(username, password);
    localStorage.setItem('token', res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const register = async (data) => {
    const res = await authAPI.register(data);
    localStorage.setItem('token', res.data.token);
    setUser(res.data.user);
    return res.data;
  };

  const logout = () => {
    localStorage.removeItem('token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{
      user,
      loading,
      login,
      register,
      logout,
      isAuthenticated: !!user,
      isAdmin: user?.is_admin || false
    }}>
      {children}
    </AuthContext.Provider>
  );
}

const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};

// ============================================================================
// UTILITY COMPONENTS
// ============================================================================

function LoadingSpinner() {
  return (
    <div className="flex justify-center items-center p-8">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
    </div>
  );
}

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isAdmin, loading } = useAuth();

  if (loading) return <LoadingSpinner />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;

  return children;
}

// ============================================================================
// NAVIGATION
// ============================================================================

function Navigation() {
  const { isAuthenticated, isAdmin, user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
    toast.success('Logged out successfully');
  };

  return (
    <nav className="bg-white shadow-sm border-b">
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="text-xl font-bold text-blue-600">App</Link>
            <Link to="/" className="text-gray-600 hover:text-gray-900">Home</Link>
            {isAdmin && (
              <Link to="/admin" className="text-gray-600 hover:text-gray-900">Admin</Link>
            )}
          </div>
          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <>
                <span className="text-gray-600">Hi, {user?.username}</span>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 text-gray-600 hover:text-gray-900"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="px-4 py-2 text-gray-600 hover:text-gray-900">Login</Link>
                <Link to="/register" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                  Register
                </Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}

// ============================================================================
// LOGIN PAGE
// ============================================================================

function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate('/');
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(username, password);
      toast.success('Welcome back!');
      navigate('/');
    } catch (err) {
      const msg = err.response?.data?.error || 'Login failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-10">
      <div className="bg-white p-8 rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Login</h1>
        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>
        <p className="mt-4 text-center text-gray-600">
          Don't have an account? <Link to="/register" className="text-blue-600 hover:underline">Register</Link>
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// REGISTER PAGE
// ============================================================================

function RegisterPage() {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { register, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) navigate('/');
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      await register({ username, email, password });
      toast.success('Account created successfully!');
      navigate('/');
    } catch (err) {
      const msg = err.response?.data?.error || 'Registration failed';
      setError(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto mt-10">
      <div className="bg-white p-8 rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Register</h1>
        {error && <div className="bg-red-50 text-red-600 p-3 rounded mb-4">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              required
              minLength={3}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              required
              minLength={6}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Confirm Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Creating account...' : 'Register'}
          </button>
        </form>
        <p className="mt-4 text-center text-gray-600">
          Already have an account? <Link to="/login" className="text-blue-600 hover:underline">Login</Link>
        </p>
      </div>
    </div>
  );
}

// ============================================================================
// HOME PAGE - implement app-specific content here
// ============================================================================

function HomePage() {
  const { isAuthenticated, user } = useAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch data on mount - public endpoint, works without auth
  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      setLoading(true);
      // Replace with your actual API endpoint
      // const res = await api.get('/items');
      // setItems(res.data.items || res.data || []);
      setItems([]); // Placeholder
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to load data');
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-2xl font-bold">
          {isAuthenticated ? `Welcome, ${user?.username}!` : 'Welcome!'}
        </h1>
        {isAuthenticated ? (
          <button className="flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            <PlusIcon className="h-5 w-5 mr-2" />
            Add New
          </button>
        ) : (
          <Link to="/login" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
            Sign in to create
          </Link>
        )}
      </div>

      {!isAuthenticated && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
          <p className="text-blue-800">
            <Link to="/login" className="font-medium underline">Sign in</Link> to create, edit, and manage items.
          </p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-600 p-4 rounded-lg mb-6">{error}</div>
      )}

      {items.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <p className="text-gray-500">No items yet.</p>
          {isAuthenticated && (
            <button className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Create your first item
            </button>
          )}
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow">
          {/* Render items here */}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// ADMIN PAGE
// ============================================================================

function AdminPage() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState({ total: 0, active: 0, inactive: 0 });

  useEffect(() => {
    fetchAdminData();
  }, []);

  const fetchAdminData = async () => {
    try {
      setLoading(true);
      // Replace with your actual admin API endpoint
      // const res = await api.get('/admin/items');
      // setItems(res.data.items || []);
      // setStats({ total: res.data.total, active: res.data.active, inactive: res.data.inactive });
      setItems([]);
      setStats({ total: 0, active: 0, inactive: 0 });
    } catch (err) {
      toast.error('Failed to load admin data');
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="max-w-6xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Admin Dashboard</h1>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-gray-500 text-sm">Total</p>
          <p className="text-3xl font-bold">{stats.total}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-gray-500 text-sm">Active</p>
          <p className="text-3xl font-bold text-green-600">{stats.active}</p>
        </div>
        <div className="bg-white p-6 rounded-lg shadow">
          <p className="text-gray-500 text-sm">Inactive</p>
          <p className="text-3xl font-bold text-red-600">{stats.inactive}</p>
        </div>
      </div>

      {/* Data Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ID</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {items.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-4 text-center text-gray-500">No items found</td>
              </tr>
            ) : (
              items.map(item => (
                <tr key={item.id}>
                  <td className="px-6 py-4 whitespace-nowrap">{item.id}</td>
                  <td className="px-6 py-4 whitespace-nowrap">{item.name || item.title}</td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <span className={`px-2 py-1 text-xs rounded-full ${item.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {item.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button className="text-blue-600 hover:text-blue-800">Toggle</button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============================================================================
// MAIN APP - DO NOT wrap in BrowserRouter (main.jsx provides it)
// ============================================================================

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
            <Route path="/admin" element={
              <ProtectedRoute adminOnly>
                <AdminPage />
              </ProtectedRoute>
            } />
          </Routes>
        </main>
      </div>
    </AuthProvider>
  );
}

export default App;
```

## CRITICAL REQUIREMENTS

1. **SINGLE FILE**: ALL code in ONE App.jsx file (600-900 lines)
2. **NO PLACEHOLDERS**: Every component fully implemented, no "...", no TODOs
3. **NO BrowserRouter**: main.jsx already provides it - DO NOT wrap App in BrowserRouter
4. **WORKING AUTH**: localStorage token, AuthContext, login/register/logout functions
5. **PUBLIC READ**: HomePage fetches data without auth, shows read-only for guests
6. **CONDITIONAL UI**: Show edit/delete buttons only when isAuthenticated
7. **TOAST NOTIFICATIONS**: Use toast.success() and toast.error() for feedback

## AVAILABLE PACKAGES (ONLY these)
react, react-dom, react-router-dom, axios, react-hot-toast, @heroicons/react, date-fns, clsx, uuid

DO NOT import any other packages.

## FORBIDDEN PATTERNS
- ❌ Wrapping App in BrowserRouter (main.jsx provides it)
- ❌ Placeholders like "// implement here" or "/* ... */"
- ❌ Asking "Would you like me to continue?"
- ❌ Importing packages not in the list above

## RESPONSE FORMAT
Output ONLY the code block. No explanations before or after."""
    
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
        max_tokens: int,
        max_continuations: int = 2,
    ) -> str:
        """Request continuation for truncated frontend output and stitch code blocks.
        
        When the model response is truncated (finish_reason='length'), we need to
        request continuation to get the complete code. This method handles the
        complex logic of stitching multiple response fragments together.
        """
        # Extract any existing JSX code from the base response to start stitching
        stitched_code = self._extract_app_jsx_code(base_content)
        if stitched_code is None:
            stitched_code = ""

        # Prompt for continuation - ask model to pick up where it left off
        continuation_prompt = (
            "Continue the App.jsx output from where you left off. "
            "Return ONLY the remaining code, wrapped in a single code block: "
            "```jsx:App.jsx\n...\n```. Do not repeat content already provided."
        )

        content = base_content
        for idx in range(max_continuations):
            # Build conversation history: original messages + previous response + continuation request
            messages = (
                list(base_messages)
                + [{"role": "assistant", "content": content},
                   {"role": "user", "content": continuation_prompt}]
            )

            success, response, status = await self.client.chat_completion(
                model=model,
                messages=messages,
                temperature=min(config.temperature, 0.2),  # Lower temp for more consistent continuation
                max_tokens=max_tokens,
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

            # Merge the continuation with existing code, handling overlaps
            stitched_code = self._merge_continuation(stitched_code, continuation_code)
            content = continuation_content

            # Check if this continuation completed the response (not truncated)
            finish = self._get_finish_reason(response)
            if finish != 'length':
                break

        # If we couldn't extract any code, return the original response
        if not stitched_code.strip():
            return base_content

        # Wrap the stitched code in proper JSX code block format
        return f"```jsx:App.jsx\n{stitched_code.strip()}\n```"

    def _extract_app_jsx_code(self, content: str) -> Optional[str]:
        """Extract App.jsx code from a fenced JSX block; allow missing closing fence."""
        if not content:
            return None
        
        # Match opening fence with JSX language specifier and optional filename
        match = re.search(
            r"```\s*(jsx|javascript|js|tsx|typescript|ts)(?::([^\n\r`]+))?\s*[\r\n]+",
            content,
            re.IGNORECASE,
        )
        if not match:
            return None
        
        start = match.end()
        
        # Find corresponding closing fence, but allow for missing closing fence
        end_match = re.search(r"```", content[start:])
        if end_match:
            end = start + end_match.start()
            return content[start:end].strip()
        
        # If no closing fence found, return everything after opening fence
        return content[start:].strip()

    def _merge_continuation(self, base_code: str, continuation: str) -> str:
        """Merge continuation code, trimming overlapping tail/head lines.
        
        When stitching multiple response fragments, there may be overlapping lines
        where the previous response ended and the continuation begins. This method
        detects and removes such overlaps to avoid duplicate code.
        
        Args:
            base_code: The accumulated code from previous responses
            continuation: The new code fragment to append
            
        Returns:
            Merged code with overlaps removed
        """
        if not base_code.strip():
            return continuation
        if not continuation.strip():
            return base_code

        base_lines = base_code.splitlines()
        cont_lines = continuation.splitlines()

        # Find maximum possible overlap (don't check more than 50 lines or half the content)
        max_overlap = min(50, len(base_lines), len(cont_lines))
        overlap = 0
        
        # Check for overlap by comparing tail of base_code with head of continuation
        # Start with largest possible overlap and work down to find exact match
        for i in range(1, max_overlap + 1):
            if base_lines[-i:] == cont_lines[:i]:
                overlap = i
                break
                
        # Remove the overlapping lines from the beginning of continuation
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

    def _sanitize_frontend_output(self, content: str) -> str:
        """Strip trailing requirement text accidentally appended after code fence.
        
        Sometimes the model includes extra text after the closing ``` code fence.
        This method finds the proper code block boundaries and strips everything
        after the closing fence, ensuring we only return the actual code.
        
        Args:
            content: Raw model response that may contain extra text after code
            
        Returns:
            Cleaned content containing only the code block
        """
        # Find the opening fence with optional language specifier
        match = re.search(
            r"```(?:\s*(?:jsx|javascript|js|tsx|typescript|ts)(?::[^\n\r`]*)?)?\s*[\r\n]+",
            content,
            re.IGNORECASE,
        )
        if not match:
            return content

        start = match.start()
        
        # Find the corresponding closing fence after the opening fence
        end_match = re.search(r"```", content[match.end():])
        if not end_match:
            return content

        # Extract only the content between the fences (including the fences themselves)
        end = match.end() + end_match.start() + 3  # +3 for the ``` characters
        return content[start:end].strip()


# Singleton
_generator: Optional[CodeGenerator] = None


def get_code_generator() -> CodeGenerator:
    """Get shared code generator instance."""
    global _generator
    if _generator is None:
        _generator = CodeGenerator()
    return _generator
