"""Generation V2 - Scaffolding-First Approach
============================================

PHILOSOPHY:
1. Scaffolding is SACRED - never overwrite it
2. AI generates ONLY application code files
3. Generated apps MUST look like scaffolding + app code

STRUCTURE:
generated/apps/{model}/app{N}/
├── [SCAFFOLDING - NEVER TOUCH]
│   ├── docker-compose.yml
│   ├── .env.example
│   ├── backend/Dockerfile
│   ├── backend/.dockerignore  
│   ├── backend/requirements.txt (base)
│   ├── frontend/Dockerfile
│   ├── frontend/.dockerignore
│   ├── frontend/nginx.conf
│   ├── frontend/vite.config.js
│   ├── frontend/package.json (base)
│   └── frontend/index.html (base)
│
└── [AI GENERATED - APPLICATION CODE]
    ├── backend/app_generated.py (merged into app.py)
    ├── backend/models.py (if needed)
    ├── backend/routes.py (if needed)
    ├── frontend/src/App.jsx (application)
    └── frontend/src/App.css (application)
"""

import ast
import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import textwrap
import time
import sys
import threading
from queue import Queue, Empty
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Set, Any, Union

import aiohttp
from sqlalchemy.exc import SQLAlchemyError

from app.paths import (
    GENERATED_APPS_DIR,
    SCAFFOLDING_DIR,
    REQUIREMENTS_DIR,
    GENERATED_RAW_API_PAYLOADS_DIR,
    GENERATED_RAW_API_RESPONSES_DIR,
    GENERATED_INDICES_DIR,
    GENERATED_MARKDOWN_DIR,
    TEMPLATES_V2_DIR,
    MISC_DIR,
)
from app.services.port_allocation_service import get_port_allocation_service
from app.services.openrouter_chat_service import get_openrouter_chat_service
from app.extensions import db
from app.models import GeneratedApplication, ModelCapability, AnalysisStatus
from app.utils.time import utc_now
from app.utils.slug_utils import auto_correct_model_id

logger = logging.getLogger(__name__)


def _ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is timezone-aware (UTC).
    
    Args:
        dt: Datetime object that might be naive or aware
        
    Returns:
        Timezone-aware datetime in UTC, or None if input was None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive datetime - assume UTC and make aware
        from datetime import timezone as tz
        return dt.replace(tzinfo=tz.utc)
    return dt


# Model-specific token limits for output generation
MODEL_TOKEN_LIMITS = {
    # Anthropic models (increased limits for longer code generation)
    'anthropic/claude-3.5-sonnet': 16384,
    'anthropic/claude-3-5-sonnet-20240620': 16384,
    'anthropic/claude-3-5-sonnet-20241022': 16384,
    'anthropic/claude-3-opus': 8192,
    'anthropic/claude-3-sonnet': 8192,
    'anthropic/claude-3-haiku': 8192,
    'anthropic/claude-4.5-haiku-20251001': 16384,
    'anthropic/claude-4.5-sonnet-20250929': 16384,
    # OpenAI models (increased limits for longer code generation)
    'openai/gpt-4o': 32768,
    'openai/gpt-4o-2024-11-20': 32768,
    'openai/gpt-4o-2024-08-06': 32768,
    'openai/gpt-4o-mini': 32768,
    'openai/gpt-4-turbo': 8192,
    'openai/gpt-4': 16384,
    'openai/gpt-3.5-turbo': 8192,
    'openai/gpt-5-codex': 8192,  # Added gpt-5-codex with increased limit
    # Google models (increased limits)
    'google/gemini-2.0-flash-exp': 16384,
    'google/gemini-pro': 4096,
    'google/gemini-1.5-pro': 16384,
    'google/gemini-1.5-flash': 16384,
    # Meta models (increased limits)
    'meta-llama/llama-3.1-405b-instruct': 8192,
    'meta-llama/llama-3.1-70b-instruct': 8192,
    'meta-llama/llama-3.2-90b-vision-instruct': 8192,
    # Mistral models (increased limits)
    'mistralai/mistral-large': 16384,
    'mistralai/mistral-medium': 16384,
    'mistralai/codestral': 16384,
    # Default for unknown models
    'default': 8192,
}


def get_model_token_limit(model_slug: str, default: int = 32000) -> int:
    """Get the maximum output tokens for a given model.
    
    Args:
        model_slug: The model identifier (e.g., 'anthropic/claude-3.5-sonnet')
        default: Default limit if model not found
        
    Returns:
        Maximum output tokens for the model
    """
    return MODEL_TOKEN_LIMITS.get(model_slug, MODEL_TOKEN_LIMITS.get('default', default))


@dataclass
class GenerationConfig:
    """Configuration for code generation."""
    model_slug: str
    app_num: int
    template_slug: str
    component: str  # 'frontend' or 'backend'
    query_type: str = 'user'  # 'user' or 'admin' - determines which requirements/routes to generate
    temperature: float = 0.3
    max_tokens: int = 64000  # Increased from 32000 for longer, more complete code generation
    requirements: Optional[Dict] = None  # Requirements from JSON file
    existing_models_summary: Optional[str] = None  # Summary of models from user query (for admin)


class ScaffoldingManager:
    """Manages scaffolding - the sacred Docker infrastructure."""
    
    def __init__(self):
        self.scaffolding_source = SCAFFOLDING_DIR / 'react-flask'
        self.base_backend_port = 5001
        self.base_frontend_port = 8001
        self._port_service = get_port_allocation_service()

    def _build_project_names(self, model_slug: str, app_num: int) -> Tuple[str, str]:
        """Create sanitized project identifiers for Docker Compose."""
        raw_slug = model_slug.lower()
        safe_slug = re.sub(r'[^a-z0-9]+', '-', raw_slug)
        safe_slug = re.sub(r'-+', '-', safe_slug).strip('-')
        if not safe_slug:
            safe_slug = hashlib.sha1(model_slug.encode('utf-8')).hexdigest()[:8]

        suffix = f"-app{app_num}"
        max_base_length = max(8, 42 - len(suffix))
        if len(safe_slug) > max_base_length:
            safe_slug = safe_slug[:max_base_length].rstrip('-')
            if not safe_slug:
                safe_slug = hashlib.sha1(model_slug.encode('utf-8')).hexdigest()[:8]

        project_name = f"{safe_slug}{suffix}"
        return project_name, project_name

    def get_ports(self, model_slug: str, app_num: int) -> Tuple[int, int]:
        """Fetch or allocate ports for a model/app pair."""
        try:
            port_pair = self._port_service.get_or_allocate_ports(model_slug, app_num)
            return port_pair.backend, port_pair.frontend
        except Exception as exc:  # noqa: BLE001
            logger = logging.getLogger(__name__)
            logger.error(
                "Port allocation service failed for %s/app%s: %s",
                model_slug,
                app_num,
                exc,
            )
            raise RuntimeError(
                f"Port allocation failed for {model_slug}/app{app_num}. "
                f"Ensure PortAllocationService is properly initialized. Error: {exc}"
            )
    
    def get_app_dir(self, model_slug: str, app_num: int, template_slug: Optional[str] = None) -> Path:
        """Get app directory path using flat structure.
        
        IMPORTANT: App numbering is global per model. The template_slug is stored
        in the database but does NOT affect the filesystem path. This ensures:
        1. Unique app numbers across all templates for a model
        2. No directory collisions when same app_num used with different templates
        3. Consistent Docker Compose project naming ({model}-app{N})
        
        Args:
            model_slug: Normalized model slug (e.g., 'openai_gpt-4')
            app_num: App number (1, 2, 3...)
            template_slug: Ignored for path generation (stored in DB only)
        
        Returns:
            Path to app directory: generated/apps/{model}/app{N}/
        """
        safe_model = re.sub(r'[^\w\-.]', '_', model_slug)
        base_path = GENERATED_APPS_DIR / safe_model
        
        # Always use flat path: {model}/app{N}
        # template_slug is stored in DB but doesn't affect filesystem structure
        # This prevents collisions when multiple templates generate apps for same model
        return base_path / f"app{app_num}"
    
    def scaffold(self, model_slug: str, app_num: int, template_slug: Optional[str] = None) -> bool:
        """Copy scaffolding to app directory.
        
        This creates the IMMUTABLE base structure that AI never touches.
        
        Args:
            model_slug: Normalized model slug
            app_num: App number
            template_slug: Optional template slug for path organization
        """
        app_dir = self.get_app_dir(model_slug, app_num, template_slug)
        backend_port, frontend_port = self.get_ports(model_slug, app_num)
        
        logger.info(f"Scaffolding {model_slug}/app{app_num} → {app_dir}")
        logger.info(f"Ports: backend={backend_port}, frontend={frontend_port}")
        
        if not self.scaffolding_source.exists():
            logger.error(f"Scaffolding source missing: {self.scaffolding_source}")
            return False
        
        # Create app directory
        app_dir.mkdir(parents=True, exist_ok=True)

        project_name, compose_project_name = self._build_project_names(model_slug, app_num)
        
        # Port substitutions
        subs = {
            'backend_port': str(backend_port),
            'frontend_port': str(frontend_port),
            'PROJECT_NAME': project_name,
            'project_name': project_name,
            'COMPOSE_PROJECT_NAME': compose_project_name,
            'compose_project_name': compose_project_name,
            'BACKEND_PORT': str(backend_port),
            'FRONTEND_PORT': str(frontend_port),
        }
        
        # Dynamically discover all files in the scaffolding directory
        files_to_copy = []
        for path in self.scaffolding_source.rglob('*'):
            if path.is_file():
                files_to_copy.append(str(path.relative_to(self.scaffolding_source)))
        
        logger.info(f"Found {len(files_to_copy)} files to copy from scaffolding source.")
        
        copied = 0
        for rel_path in files_to_copy:
            src = self.scaffolding_source / rel_path
            dest = app_dir / rel_path

            # Rename .env.example to .env
            if rel_path == '.env.example':
                dest = app_dir / '.env'
            
            if not src.exists():
                logger.warning(f"Scaffolding file missing: {rel_path}")
                continue
            
            # Create parent directory
            dest.parent.mkdir(parents=True, exist_ok=True)
            
            # Read and substitute
            try:
                content = src.read_text(encoding='utf-8')
                
                # Apply substitutions
                for key, value in subs.items():
                    # {{key|default}} pattern
                    content = re.sub(
                        r'\{\{' + re.escape(key) + r'\|[^\}]+\}\}',
                        value,
                        content
                    )
                    # {{key}} pattern
                    content = content.replace(f'{{{{{key}}}}}', value)

                    # Handle patterns that embed {{app_num}} inside larger tokens
                    if '{{app_num}}' in content:
                        content = content.replace('app{{app_num}}', f'app{app_num}')
                
                # Write
                dest.write_text(content, encoding='utf-8')
                copied += 1
                logger.debug(f"  ✓ {rel_path}")
                
            except UnicodeDecodeError:
                # Binary file
                shutil.copy2(src, dest)
                copied += 1
                logger.debug(f"  ✓ {rel_path} (binary)")
                
            except Exception as e:
                logger.error(f"  ✗ {rel_path}: {e}")
        
        logger.info(f"Scaffolded {copied}/{len(files_to_copy)} files")
        return copied >= 10  # Must have at least core files


class CodeGenerator:
    """Generates application code using AI."""
    
    def __init__(self):
        self.chat_service = get_openrouter_chat_service()
        self.requirements_dir = REQUIREMENTS_DIR
        self.template_dir = TEMPLATES_V2_DIR
        self.scaffolding_info_path = SCAFFOLDING_DIR / 'SCAFFOLDING_INFO.md'
    
    async def generate(self, config: GenerationConfig) -> Tuple[bool, str, str]:
        """Generate code for frontend or backend.
        
        Returns: (success, content, error_message)
        """
        # Build prompt
        prompt = self._build_prompt(config)
        
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug=config.model_slug).first()
        if not model:
            logger.error(f"Model not found in database: {config.model_slug}")
            return False, "", f"Model not found in database: {config.model_slug}"
        
        # Priority: 1) hugging_face_id (case-sensitive, most accurate)
        #          2) base_model_id (normalized, no variant suffix)
        #          3) model_id (fallback)
        openrouter_model = model.hugging_face_id or model.base_model_id or model.model_id
        
        # Optional runtime validation (fails open if catalog unavailable)
        # The OpenRouter API will be the final authority on model validity
        try:
            from app.services.model_validator import get_validator
            validator = get_validator()
            
            if not validator.is_valid_model_id(openrouter_model):
                # Try to find correction
                suggestion = validator.suggest_correction(openrouter_model)
                if suggestion:
                    corrected_id, reason = suggestion
                    logger.info(f"Auto-correcting model ID: {openrouter_model} → {corrected_id} ({reason})")
                    openrouter_model = corrected_id
                # If no suggestion, continue anyway - let OpenRouter API validate
        except Exception as e:
            # Validation is optional - continue with generation if it fails
            logger.debug(f"Model validation skipped: {e}")
        
        logger.info(f"Using OpenRouter model: {openrouter_model} (HF ID: {model.hugging_face_id}, base: {model.base_model_id}, model_id: {model.model_id}, slug: {config.model_slug})")
        
        # Get model-specific token limit, capping at config.max_tokens
        model_limit = get_model_token_limit(openrouter_model, default=config.max_tokens)
        effective_max_tokens = min(config.max_tokens, model_limit)
        
        if effective_max_tokens < config.max_tokens:
            logger.info(f"Capping max_tokens to {effective_max_tokens} (model limit) from {config.max_tokens} (config)")
        
        # Get system prompt with query_type for 4-query system
        query_type = config.query_type if hasattr(config, 'query_type') and config.query_type else 'user'
        system_prompt = self._get_system_prompt(config.component, query_type)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]

        # Prepare metadata tracking
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        safe_model = re.sub(r'[^\w\-.]', '_', config.model_slug)
        run_id = f"{safe_model}_app{config.app_num}_{config.component}_{timestamp}"
        
        try:
            success, response_data, status_code = await self.chat_service.generate_chat_completion(
                model=openrouter_model,
                messages=messages,
                temperature=config.temperature,
                max_tokens=effective_max_tokens
            )

            # Save request/response artifacts regardless of outcome
            self._save_payload(run_id, safe_model, config.app_num, self.chat_service._build_payload(openrouter_model, messages, config.temperature, effective_max_tokens), self.chat_service._get_headers())
            self._save_response(run_id, safe_model, config.app_num, response_data, {})

            if not success:
                error_obj = response_data.get("error", {})
                error_message = error_obj.get("message", "Unknown API error")
                error_code = error_obj.get("code", status_code)
                
                # Log detailed error for debugging
                logger.error(f"OpenRouter API error for {openrouter_model}: {error_code} - {error_message}")
                logger.error(f"Full error response: {response_data}")
                
                # Return user-friendly error with model ID info
                return False, "", f"API error {error_code}: {error_message} (tried model ID: {openrouter_model})"

            # Validate response structure before accessing
            if not isinstance(response_data, dict) or 'choices' not in response_data:
                error_msg = f"Invalid API response structure: {type(response_data).__name__}"
                if isinstance(response_data, dict) and 'error' in response_data:
                    error_obj = response_data.get('error', {})
                    if isinstance(error_obj, dict):
                        error_msg += f" - {error_obj.get('message', str(error_obj))}"
                    else:
                        error_msg += f" - {error_obj}"
                logger.error(error_msg)
                logger.error(f"Response data: {response_data}")
                return False, "", f"Backend generation failed: {error_msg}"
            
            # Validate choices array structure
            if not response_data.get('choices') or not isinstance(response_data['choices'], list):
                error_msg = "API response missing valid 'choices' array"
                logger.error(f"{error_msg}: {response_data}")
                return False, "", f"Backend generation failed: {error_msg}"
            
            if len(response_data['choices']) == 0:
                error_msg = "API response has empty 'choices' array"
                logger.error(f"{error_msg}: {response_data}")
                return False, "", f"Backend generation failed: {error_msg}"

            content = response_data['choices'][0]['message']['content']
            finish_reason = response_data['choices'][0].get('finish_reason', 'unknown')
            
            # Check for truncation
            if finish_reason == 'length':
                token_count = response_data.get('usage', {}).get('completion_tokens', 0)
                logger.warning(f"Generation truncated at {token_count} tokens (hit model limit). Code may be incomplete!")
                logger.warning(f"Consider: 1) Using a model with higher output limit, or 2) Simplifying requirements")
            
            # Save metadata on success
            await self._save_metadata(run_id, safe_model, config.app_num, config.component, 
                                    self.chat_service._build_payload(openrouter_model, messages, config.temperature, effective_max_tokens), 
                                    response_data, status_code, {})
            
            return True, content, ""
                    
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return False, "", str(e)
    
    def _load_requirements(self, template_slug: str) -> Optional[Dict]:
        """Load requirements from JSON file using slug naming convention.
        
        Templates must be named: {slug}.json (e.g., crud_todo_list.json, realtime_chat_app.json)
        """
        if not self.requirements_dir.exists():
            logger.error(f"Requirements directory not found: {self.requirements_dir}")
            return None

        # Normalize slug (allow underscores and hyphens)
        normalized_slug = template_slug.lower().replace('-', '_')
        
        # Try direct lookup with normalized slug
        req_file = self.requirements_dir / f"{normalized_slug}.json"
        
        if not req_file.exists():
            logger.warning(f"Requirements file not found: {req_file.name}")
            return None
        
        try:
            data = json.loads(req_file.read_text(encoding='utf-8'))
            
            # Validate slug matches filename
            file_slug = data.get('slug')
            if file_slug is None:
                logger.error(f"Template {req_file.name} missing 'slug' field")
                return None
            
            if file_slug.lower().replace('-', '_') != normalized_slug:
                logger.error(
                    f"Slug mismatch in {req_file.name}: file has slug={file_slug}, expected {template_slug}"
                )
                return None
            
            logger.info(f"Loaded requirements for template slug '{template_slug}'")
            return data
            
        except (json.JSONDecodeError, ValueError, OSError) as e:
            logger.error(f"Failed to load requirements file {req_file.name}: {e}")
            return None
    
    def _load_scaffolding_info(self) -> str:
        """Load scaffolding information."""
        if not self.scaffolding_info_path.exists():
            logger.warning("Scaffolding info file not found")
            return ""
        
        try:
            with open(self.scaffolding_info_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load scaffolding info: {e}")
            return ""
    
    def _load_prompt_template(self, component: str, query_type: str = 'user', model_slug: Optional[str] = None) -> str:
        """Load prompt template for component and query type.
        
        Args:
            component: 'frontend' or 'backend'
            query_type: 'user' or 'admin'
            model_slug: Optional model-specific override
            
        Returns:
            Template content or empty string if not found
        """
        # Build template filename based on query system (4-query vs 2-query)
        four_query_dir = self.template_dir / 'four-query'
        two_query_dir = self.template_dir / 'two-query'
        
        # Try 4-query templates first
        if four_query_dir.exists():
            template_name = f"{component}_{query_type}.md.jinja2"
            template_file = four_query_dir / template_name
            if template_file.exists():
                logger.info(f"Using 4-query template: {template_name}")
                try:
                    return template_file.read_text(encoding='utf-8')
                except Exception as e:
                    logger.error(f"Failed to load 4-query template: {e}")
        
        # Fall back to 2-query templates (for backward compatibility)
        if query_type == 'user':  # Only user query maps to 2-query
            template_file = two_query_dir / f"{component}.md.jinja2"
            if template_file.exists():
                logger.info(f"Falling back to 2-query template: {component}.md.jinja2")
                try:
                    return template_file.read_text(encoding='utf-8')
                except Exception as e:
                    logger.error(f"Failed to load 2-query template: {e}")
        
        logger.warning(f"No template found for {component}/{query_type}")
        return ""

    def _format_api_endpoints(self, requirements: Optional[Dict[str, Any]], admin: bool = False) -> str:
        """Format API endpoint definitions for inclusion in prompts.
        
        Args:
            requirements: Requirements dict containing api_endpoints or admin_api_endpoints
            admin: If True, format admin_api_endpoints instead
        """
        if not requirements:
            return "No explicit API endpoints provided."

        # Choose endpoint key based on admin flag
        endpoint_key = 'admin_api_endpoints' if admin else 'api_endpoints'
        endpoints = requirements.get(endpoint_key) or []
        if not endpoints:
            return "No explicit API endpoints provided."

        formatted: List[str] = []
        for endpoint in endpoints:
            method = endpoint.get('method', 'GET')
            path = endpoint.get('path', '/api/example')
            description = (endpoint.get('description') or '').strip()
            header = f"- {method} {path}: {description}".rstrip()
            block_parts = [header]

            request_spec = endpoint.get('request', None)
            if request_spec is not None:
                request_json = json.dumps(request_spec, ensure_ascii=True, indent=2)
                block_parts.append(textwrap.indent(f"Request:\n{request_json}", "  "))

            response_spec = endpoint.get('response', None)
            if response_spec is not None:
                response_json = json.dumps(response_spec, ensure_ascii=True, indent=2)
                block_parts.append(textwrap.indent(f"Response:\n{response_json}", "  "))

            notes = (endpoint.get('notes') or '').strip()
            if notes:
                block_parts.append(textwrap.indent(f"Notes: {notes}", "  "))

            formatted.append('\n'.join(block_parts))

        return '\n'.join(formatted)
    
    def _save_payload(self, run_id: str, model_slug: str, app_num: int, 
                     payload: Dict, headers: Dict) -> None:
        """Save request payload to raw directory."""
        try:
            payload_dir = GENERATED_RAW_API_PAYLOADS_DIR / model_slug / f"app{app_num}"
            payload_dir.mkdir(parents=True, exist_ok=True)
            
            payload_file = payload_dir / f"{run_id}_payload.json"
            payload_data = {
                'timestamp': datetime.now().isoformat(),
                'run_id': run_id,
                'headers': headers,
                'payload': payload
            }
            payload_file.write_text(json.dumps(payload_data, indent=2), encoding='utf-8')
            logger.debug(f"Saved payload: {payload_file}")
        except Exception as e:
            logger.warning(f"Failed to save payload: {e}")
    
    def _save_response(self, run_id: str, model_slug: str, app_num: int,
                      response: Dict, headers: Dict) -> None:
        """Save API response to raw directory."""
        try:
            response_dir = GENERATED_RAW_API_RESPONSES_DIR / model_slug / f"app{app_num}"
            response_dir.mkdir(parents=True, exist_ok=True)
            
            response_file = response_dir / f"{run_id}_response.json"
            response_data = {
                'timestamp': datetime.now().isoformat(),
                'run_id': run_id,
                'headers': dict(headers),
                'response': response
            }
            response_file.write_text(json.dumps(response_data, indent=2), encoding='utf-8')
            logger.debug(f"Saved response: {response_file}")
        except Exception as e:
            logger.warning(f"Failed to save response: {e}")
    
    async def _save_metadata(self, run_id: str, model_slug: str, app_num: int, component: str,
                            payload: Dict, response: Dict, status: int, headers: Dict) -> None:
        """Save comprehensive generation metadata with OpenRouter stats.
        
        Fetches extended metadata from OpenRouter /api/v1/generation endpoint
        including native tokens, cost, provider info, etc.
        """
        try:
            metadata_dir = GENERATED_INDICES_DIR / "runs" / model_slug / f"app{app_num}"
            metadata_dir.mkdir(parents=True, exist_ok=True)
            
            # Extract basic info from response
            usage = response.get('usage', {})
            generation_id = response.get('id')
            
            # Build comprehensive metadata
            metadata = {
                'run_id': run_id,
                'timestamp': datetime.now().isoformat(),
                'model_slug': model_slug,
                'app_num': app_num,
                'component': component,
                'model_used': response.get('model'),
                'status': status,
                # Normalized token counts (from main response)
                'prompt_tokens': usage.get('prompt_tokens'),
                'completion_tokens': usage.get('completion_tokens'),
                'total_tokens': usage.get('total_tokens'),
                # Response metadata
                'finish_reason': response.get('choices', [{}])[0].get('finish_reason'),
                'native_finish_reason': response.get('choices', [{}])[0].get('native_finish_reason'),
                'generation_id': generation_id,
                # Request parameters
                'temperature': payload.get('temperature'),
                'max_tokens': payload.get('max_tokens'),
            }
            
            # Fetch extended OpenRouter metadata from /api/v1/generation endpoint
            if generation_id:
                try:
                    # Wait 1 second for OpenRouter to process generation stats
                    await asyncio.sleep(1.0)
                    
                    async with aiohttp.ClientSession() as session:
                        generation_url = f"https://openrouter.ai/api/v1/generation?id={generation_id}"
                        headers_for_stats = {
                            "Authorization": f"Bearer {self.chat_service.api_key}",
                        }
                        
                        async with session.get(
                            generation_url,
                            headers=headers_for_stats,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as gen_response:
                            if gen_response.status == 200:
                                gen_data = await gen_response.json()
                                data = gen_data.get('data', {})
                                
                                # Add OpenRouter-specific metadata
                                metadata.update({
                                    'native_tokens_prompt': data.get('native_tokens_prompt'),
                                    'native_tokens_completion': data.get('native_tokens_completion'),
                                    'provider_name': data.get('provider_name'),
                                    'model_used_actual': data.get('model'),
                                    'total_cost': data.get('total_cost'),  # USD
                                    'generation_time_ms': data.get('generation_time'),
                                    'created_at': data.get('created_at'),
                                    'cancelled': data.get('cancelled', False),
                                    'upstream_id': data.get('upstream_id'),
                                })
                                logger.debug(f"Enhanced metadata with OpenRouter stats for {run_id}")
                            else:
                                error_text = await gen_response.text()
                                logger.warning(
                                    f"Failed to fetch OpenRouter generation stats (status {gen_response.status}): {error_text}"
                                )
                                metadata['generation_stats_error'] = f"Status {gen_response.status}"
                
                except asyncio.TimeoutError:
                    logger.warning(f"Timeout fetching OpenRouter generation stats for {run_id}")
                    metadata['generation_stats_error'] = "Timeout"
                except Exception as e:
                    logger.warning(f"Failed to fetch OpenRouter generation stats: {e}")
                    metadata['generation_stats_error'] = str(e)
            
            metadata_file = metadata_dir / f"{run_id}_metadata.json"
            metadata_file.write_text(json.dumps(metadata, indent=2), encoding='utf-8')
            logger.debug(f"Saved comprehensive metadata: {metadata_file}")
        except Exception as e:
            logger.warning(f"Failed to save metadata: {e}")
    
    def _build_prompt(self, config: GenerationConfig) -> str:
        """Build generation prompt based on 4-query template system.
        
        4-Query System:
        - Query 1: backend_user - Models + User routes + Services
        - Query 2: backend_admin - Admin routes (uses models from Query 1)
        - Query 3: frontend_user - UserPage + API service + Hooks
        - Query 4: frontend_admin - AdminPage + Admin API functions
        """
        from jinja2 import Environment, FileSystemLoader

        # Load requirements if not already loaded
        if not config.requirements:
            config.requirements = self._load_requirements(config.template_slug)
        
        reqs = config.requirements
        query_type = config.query_type  # 'user' or 'admin'
        
        # Determine template directory (prefer four-query)
        four_query_dir = self.template_dir / 'four-query'
        two_query_dir = self.template_dir / 'two-query'
        
        template = None
        template_name = None
        
        # Try 4-query templates first
        if four_query_dir.exists():
            template_name = f"{config.component}_{query_type}.md.jinja2"
            env = Environment(loader=FileSystemLoader(four_query_dir))
            try:
                template = env.get_template(template_name)
                logger.info(f"Using 4-query template: {template_name}")
            except Exception:
                template = None
        
        # Fall back to 2-query for user queries only
        if not template and query_type == 'user':
            template_name = f"{config.component}.md.jinja2"
            env = Environment(loader=FileSystemLoader(two_query_dir))
            try:
                template = env.get_template(template_name)
                logger.info(f"Falling back to 2-query template: {template_name}")
            except Exception as e:
                logger.error(f"Template not found: {e}")
                template = None

        # If template exists, use it
        if template and reqs:
            app_name = reqs.get('name', 'Application')
            app_description = reqs.get('description', 'web application')
            
            # Select requirements based on query type
            if query_type == 'admin':
                req_list = reqs.get('admin_requirements', [])
                endpoint_text = self._format_api_endpoints(reqs, admin=True)
            else:
                if config.component == 'backend':
                    req_list = reqs.get('backend_requirements', [])
                else:
                    req_list = reqs.get('frontend_requirements', [])
                endpoint_text = self._format_api_endpoints(reqs, admin=False)
            
            # Also provide user endpoints for admin context
            admin_endpoint_text = self._format_api_endpoints(reqs, admin=True) if query_type == 'admin' else ''
            
            # Load scaffolding content
            scaffolding_content = self._load_scaffolding_files(config.model_slug, config.app_num, config.template_slug)

            # Create context for Jinja2
            context = {
                'name': app_name,
                'description': app_description,
                'backend_requirements': reqs.get('backend_requirements', []) if config.component == 'backend' and query_type == 'user' else [],
                'frontend_requirements': reqs.get('frontend_requirements', []) if config.component == 'frontend' and query_type == 'user' else [],
                'admin_requirements': reqs.get('admin_requirements', []) if query_type == 'admin' else [],
                'api_endpoints': endpoint_text,
                'admin_api_endpoints': admin_endpoint_text,
                'existing_models_summary': config.existing_models_summary or 'No models defined yet.',
                **scaffolding_content
            }
            
            # Render the prompt
            prompt = template.render(context)
            
            logger.info(f"Built {query_type} prompt using Jinja2 template: {len(prompt)} chars")
            return prompt
        
        # Fallback to old format if template/requirements not found
        logger.warning("Jinja2 template or requirements not found, using fallback")
        return self._build_fallback_prompt(config, reqs)
    
    def _build_fallback_prompt(self, config: GenerationConfig, reqs: Optional[Dict]) -> str:
        """Build fallback prompt when templates are not available."""
        endpoint_text = self._format_api_endpoints(reqs)

        if config.component == 'backend':
            # Prefer new structured requirements format
            if reqs and ('functional_requirements' in reqs or 'backend_requirements' in reqs):
                # Use functional requirements if available, otherwise fall back to backend_requirements
                if 'functional_requirements' in reqs:
                    functional_reqs = '\n'.join([f"- {req}" for req in reqs['functional_requirements']])
                    requirements_section = f"""FUNCTIONAL REQUIREMENTS:
{functional_reqs}"""
                else:
                    backend_reqs = '\n'.join([f"- {req}" for req in reqs['backend_requirements']])
                    requirements_section = f"""BACKEND REQUIREMENTS:
{backend_reqs}"""
                
                # Add control endpoints if available
                control_endpoints_section = ""
                if 'control_endpoints' in reqs:
                    endpoint_lines = []
                    for ep in reqs['control_endpoints']:
                        endpoint_lines.append(f"- {ep['method']} {ep['path']} (returns {ep['expected_status']}): {ep.get('description', 'Control endpoint')}")
                    control_endpoints_section = f"""

REQUIRED CONTROL ENDPOINTS:
{chr(10).join(endpoint_lines)}"""
                
                app_desc = reqs.get('description', 'web application')
                app_name = reqs.get('name', 'Application')

                return (
                    f"""Generate Python Flask backend code for: {app_name}

Description: {app_desc}

{requirements_section}{control_endpoints_section}

API ENDPOINTS:
{endpoint_text}

IMPORTANT CONSTRAINTS:
- Generate ONLY the application code (routes, models, business logic)
- DO NOT generate Dockerfile, requirements.txt, or infrastructure files
- Use Flask best practices with proper error handling
- Use SQLAlchemy for database models where needed
- Include CORS configuration for frontend integration
- Add proper logging and validation
- Implement ALL control endpoints as specified
- Keep code clean, well-commented, and production-ready

Generate the complete Flask backend code:"""
                )
            else:
                return (
                    """Generate Python code for a Flask backend API.

IMPORTANT:
- Generate ONLY the application-specific code
- DO NOT generate Dockerfile, requirements.txt, or other infrastructure
- Focus on routes, models, business logic
- Keep it simple and working

Generate the Flask API code:"""
                )

        else:  # frontend
            # Prefer new structured requirements format
            if reqs and ('functional_requirements' in reqs or 'stylistic_requirements' in reqs or 'frontend_requirements' in reqs):
                requirements_lines = []
                
                # Add functional requirements if available
                if 'functional_requirements' in reqs:
                    requirements_lines.append("FUNCTIONAL REQUIREMENTS:")
                    requirements_lines.extend([f"- {req}" for req in reqs['functional_requirements']])
                
                # Add stylistic requirements if available
                if 'stylistic_requirements' in reqs:
                    if requirements_lines:
                        requirements_lines.append("")
                    requirements_lines.append("STYLISTIC REQUIREMENTS:")
                    requirements_lines.extend([f"- {req}" for req in reqs['stylistic_requirements']])
                
                # Fall back to frontend_requirements if new format not available
                if not requirements_lines and 'frontend_requirements' in reqs:
                    requirements_lines.append("FRONTEND REQUIREMENTS:")
                    requirements_lines.extend([f"- {req}" for req in reqs['frontend_requirements']])
                
                req_list = '\n'.join(requirements_lines)
                app_desc = reqs.get('description', 'web application')
                app_name = reqs.get('name', 'Application')

                return (
                    f"""Generate React frontend code for: {app_name}

Description: {app_desc}

{req_list}

API ENDPOINTS:
{endpoint_text}

IMPORTANT CONSTRAINTS:
- Generate ONLY the App.jsx component code
- DO NOT generate index.html, package.json, vite.config.js, or infrastructure
- Use React hooks (useState, useEffect) for state management
- Use axios for API calls to backend
- Include proper error handling and loading states
- Add responsive design with clean, modern UI
- Keep code clean, well-commented, and production-ready

Generate the complete React App.jsx component:"""
                )
            else:
                return (
                    """Generate React/JSX code for the frontend application.

IMPORTANT:
- Generate ONLY the App.jsx component code
- DO NOT generate index.html, package.json, vite.config, or other infrastructure
- Focus on the UI components and logic
- Keep it simple and working

Generate the React component code:"""
                )

    def _load_scaffolding_files(self, model_slug: str, app_num: int, template_slug: Optional[str] = None) -> Dict[str, str]:
        """Load content of key scaffolding files to inject into prompts."""
        scaffold_manager = ScaffoldingManager()
        app_dir = scaffold_manager.get_app_dir(model_slug, app_num, template_slug)
        
        files_to_load = {
            'scaffolding_app_py': app_dir / 'backend' / 'app.py',
            'scaffolding_app_jsx': app_dir / 'frontend' / 'src' / 'App.jsx',
            'scaffolding_package_json': app_dir / 'frontend' / 'package.json',
            'scaffolding_requirements_txt': app_dir / 'backend' / 'requirements.txt',
            'scaffolding_backend_context': app_dir / 'backend' / 'SCAFFOLDING_CONTEXT.md',
            'scaffolding_frontend_context': app_dir / 'frontend' / 'SCAFFOLDING_CONTEXT.md',
        }
        
        content = {}
        for key, path in files_to_load.items():
            try:
                if path.exists():
                    content[key] = path.read_text(encoding='utf-8')
                else:
                    # Only log warning for missing context files, as they are optional
                    if 'CONTEXT' not in key:
                        logger.warning(f"Scaffolding file missing: {path}")
                    content[key] = f"<!-- File not found: {path.name} -->"
            except Exception as e:
                logger.warning(f"Could not read scaffolding file {path}: {e}")
                content[key] = f"<!-- Error reading file: {path.name} -->"
        
        return content

    def _get_system_prompt(self, component: str, query_type: str = 'user') -> str:
        """Get system prompt from external file for 4-query system.
        
        Args:
            component: 'backend' or 'frontend'
            query_type: 'user' or 'admin'
            
        Returns:
            System prompt string
        """
        prompts_dir = MISC_DIR / 'prompts' / 'system'
        
        # Try 4-query specific prompt first (e.g., backend_user.md)
        four_query_file = prompts_dir / f'{component}_{query_type}.md'
        if four_query_file.exists():
            try:
                content = four_query_file.read_text(encoding='utf-8')
                logger.info(f"Loaded 4-query system prompt from {four_query_file}")
                return content
            except Exception as e:
                logger.warning(f"Failed to load prompt from {four_query_file}: {e}")
        
        # Fallback to component-only prompt (e.g., backend.md) for user queries
        if query_type == 'user':
            fallback_file = prompts_dir / f'{component}.md'
            if fallback_file.exists():
                try:
                    content = fallback_file.read_text(encoding='utf-8')
                    logger.info(f"Loaded fallback system prompt from {fallback_file}")
                    return content
                except Exception as e:
                    logger.warning(f"Failed to load prompt from {fallback_file}: {e}, using embedded")
        
        # Fallback to embedded prompts
        return self._get_fallback_system_prompt(component, query_type)
    
    def _get_fallback_system_prompt(self, component: str, query_type: str) -> str:
        """Get embedded fallback system prompts for 4-query system."""
        if component == 'frontend':
            if query_type == 'admin':
                return """You are an expert React developer creating the ADMIN interface.

Your task is to generate the AdminPage component and admin API functions.

## What You MUST Generate
- AdminPage.jsx: Admin dashboard with data management interface
- api.js additions: Admin-specific API functions (fetchAllItems, toggleStatus, bulkDelete, fetchStats)

## Technical Guidelines
- Use simple hardcoded admin check (no full auth system)
- Admin pages should display all data with management controls
- Include toggle status, bulk delete, and statistics features
- Use existing hooks/useData.js patterns

## Output Format
Return your code wrapped in markdown code blocks:
- AdminPage: ```jsx:src/pages/AdminPage.jsx
- API additions: ```jsx:src/services/api.js

Generate complete, working code - no placeholders or TODOs."""
            else:  # user
                return """You are an expert React developer specializing in production-ready web applications.

Your task is to generate the USER-facing React frontend code.

## What You MUST Generate
- UserPage.jsx: Main user interface component
- api.js: API service with user endpoints
- useData.js: Custom hooks for data management

## Technical Guidelines
- Use modern React patterns (functional components, hooks)
- Include proper error handling, loading states, and user feedback
- Use Tailwind CSS or custom CSS for styling
- Connect to backend API endpoints

## Output Format
Return your code wrapped in markdown code blocks:
- UserPage: ```jsx:src/pages/UserPage.jsx
- API service: ```jsx:src/services/api.js
- Hooks: ```jsx:src/hooks/useData.js

Generate complete, working code - no placeholders or TODOs."""
        
        else:  # backend
            if query_type == 'admin':
                return """You are an expert Flask developer creating ADMIN routes.

Your task is to generate admin-specific routes using the models from Query 1.

## What You MUST Generate
- routes/admin.py: Admin routes with the admin_bp Blueprint (/api/admin prefix)

## Admin Endpoints Pattern
- GET /api/admin/items - Fetch all items with filters
- POST /api/admin/items/<id>/toggle - Toggle item status
- POST /api/admin/items/bulk-delete - Bulk delete items
- GET /api/admin/stats - Get statistics

## Technical Guidelines
- Use simple hardcoded admin check (SECRET_ADMIN_KEY header)
- Import models from models.py (already generated)
- Import services from services.py (already generated)
- Use the db instance from app.py

## Output Format
Return your code wrapped in markdown code blocks:
- Admin routes: ```python:routes/admin.py

Generate complete, working code - no placeholders or TODOs."""
            else:  # user
                return """You are an expert Flask developer specializing in production-ready REST APIs.

Your task is to generate the USER-facing Flask backend code.

## What You MUST Generate
- models.py: SQLAlchemy models
- routes/user.py: User routes with the user_bp Blueprint (/api prefix)
- services.py: Business logic services

## Technical Guidelines
- Use Flask best practices and proper project structure
- Use SQLAlchemy for database models
- Database path: sqlite:////app/data/app.db
- Include CORS configuration for frontend integration
- Add proper error handling, validation, and logging

## Output Format
Return your code wrapped in markdown code blocks:
- Models: ```python:models.py
- User routes: ```python:routes/user.py
- Services: ```python:services.py

Generate complete, working code - no placeholders or TODOs."""


class CodeMerger:
    """Simplified code merger that overwrites files with LLM-generated code.
    
    Philosophy: LLM generates complete, working files. We just extract from fences,
    validate syntax, fix Docker networking, and write. No AST merging complexity.
    """

    def __init__(self):
        # Keep dependency inference for requirements.txt updates
        try:
            self._stdlib_modules = set(sys.stdlib_module_names)
        except AttributeError:
            self._stdlib_modules = {'os', 'sys', 'logging', 'json', 're', 'asyncio', 'datetime', 'pathlib', 'shutil', 'hashlib', 'textwrap', 'time', 'collections'}
        self._local_prefixes = {'app', 'models', 'routes', 'services', 'utils', 'config', 'db'}
        self._package_version_map = {
            'flask': 'Flask==3.0.0',
            'flask_sqlalchemy': 'Flask-SQLAlchemy==3.1.1',
            'sqlalchemy': 'SQLAlchemy==2.0.25',
            'flask_cors': 'Flask-CORS==4.0.0',
            'werkzeug': 'Werkzeug==3.0.1',
            'psycopg2': 'psycopg2-binary==2.9.9',
            'psycopg2_binary': 'psycopg2-binary==2.9.9',
            'python_dotenv': 'python-dotenv==1.0.1',
            'bcrypt': 'bcrypt==4.1.2',
            'pyjwt': 'PyJWT==2.8.0',
        }

    def validate_generated_code(self, code: str, component: str) -> Tuple[bool, List[str]]:
        """Validate generated code for syntax errors before merging.
        
        Args:
            code: The generated code to validate
            component: 'backend' or 'frontend'
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        if not code or not code.strip():
            errors.append("Generated code is empty")
            return False, errors
        
        if component == 'backend':
            # Validate Python syntax
            try:
                ast.parse(code)
                logger.info("Backend code validation passed: Python syntax is valid")
            except SyntaxError as e:
                # Check if error is due to fence markers in the code
                if '```' in code[:100]:  # Check first 100 chars for fence markers
                    logger.warning("Syntax error may be due to markdown fences, attempting cleanup")
                    cleaned_code = re.sub(r'^```[a-z]*\s*\n?', '', code, flags=re.MULTILINE)
                    cleaned_code = re.sub(r'\n?```\s*$', '', cleaned_code, flags=re.MULTILINE)
                    
                    try:
                        ast.parse(cleaned_code)
                        logger.info("✓ Code is valid after fence cleanup - fence markers were the issue")
                        # Note: We can't modify the original 'code' parameter here,
                        # but caller should handle this via _select_code_block cleanup
                        errors.append("Code contains markdown fence markers - extraction may have failed")
                        return False, errors
                    except SyntaxError:
                        # Fall through to original error handling
                        logger.warning("Code still invalid after fence cleanup - genuine syntax error")
                
                # Original error handling
                error_msg = f"Python syntax error at line {e.lineno}: {e.msg}"
                # Only include error text if it doesn't contain fence markers (avoids confusing output)
                if e.text and '```' not in e.text:
                    error_msg += f"\n  Code: {e.text.strip()}"
                elif e.text:
                    error_msg += f"\n  (Error text contains fence markers - code extraction likely failed)"
                errors.append(error_msg)
                logger.error(f"Backend code validation failed: {error_msg}")
            except Exception as e:
                errors.append(f"Unexpected error during Python parsing: {str(e)}")
                logger.error(f"Backend code validation failed with unexpected error: {e}")
        
        elif component == 'frontend':
            # Basic JSX/JavaScript validation (check for common issues)
            if 'import' not in code and 'function' not in code and 'const' not in code:
                errors.append("Frontend code appears incomplete (missing imports, functions, or components)")
                logger.warning("Frontend code validation: code appears incomplete")
            
            if 'export default' not in code:
                errors.append("Frontend code missing 'export default' statement")
                logger.warning("Frontend code validation: missing export default")
            
            # Check for common mistakes
            if 'localhost' in code.lower() and 'backend:5000' not in code:
                errors.append("Frontend code should use 'http://backend:5000' not localhost")
                logger.warning("Frontend code validation: found localhost instead of backend:5000")
            
            logger.info(f"Frontend code validation completed with {len(errors)} warnings")
        
        is_valid = len(errors) == 0
        return is_valid, errors

    # File whitelists for query_type filtering
    # 'user' queries can write to any file (they set up the base structure)
    # 'admin' queries should only write to admin-specific files
    BACKEND_ADMIN_WHITELIST = {
        'routes/admin.py',
        'admin.py',  # Legacy fallback
    }
    
    # Files that admin queries can APPEND to (not overwrite)
    BACKEND_ADMIN_APPEND_FILES = {
        'services.py',  # Admin may add service functions
    }
    
    FRONTEND_ADMIN_WHITELIST = {
        'pages/adminpage.jsx',
        'adminpage.jsx',  # Legacy fallback
        'pages/admin.jsx',
        'admin.jsx',
    }
    
    # Files that admin queries can APPEND to (not overwrite)
    FRONTEND_ADMIN_APPEND_FILES = {
        'services/api.js',
        'api.js',  # Legacy fallback
    }

    def merge_backend(self, app_dir: Path, generated_content: str, query_type: str = 'user') -> bool:
        """
        Replace backend files with LLM-generated code.
        
        Args:
            app_dir: Path to the app directory
            generated_content: LLM response with code blocks
            query_type: 'user' or 'admin' - controls which files can be written
                       'user' queries can write any file
                       'admin' queries are restricted to admin-specific files
        """
        logger.info(f"Starting backend merge (query_type={query_type})...")
        
        backend_dir = app_dir / 'backend'
        
        # Extract all code blocks from the response
        all_blocks = self._extract_all_code_blocks(generated_content)
        
        if query_type == 'user':
            # User query: standard behavior - write main app.py and all additional files
            return self._merge_backend_user(app_dir, all_blocks, generated_content)
        else:
            # Admin query: restricted to admin-specific files only
            return self._merge_backend_admin(app_dir, all_blocks)
    
    def _merge_backend_user(self, app_dir: Path, all_blocks: List[Dict], generated_content: str) -> bool:
        """Handle backend merge for 'user' query - writes to models.py, services.py, routes/user.py.
        
        NOTE: Does NOT overwrite app.py unless the LLM explicitly outputs app.py content with Flask app setup.
        The scaffolding's app.py already has proper Flask factory pattern.
        """
        backend_dir = app_dir / 'backend'
        models_path = backend_dir / 'models.py'
        services_path = backend_dir / 'services.py'
        user_routes_path = backend_dir / 'routes' / 'user.py'
        
        files_written = 0
        
        # Process each code block and route to appropriate file
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '').lower() if block.get('filename') else ''
            code = block.get('code', '')
            
            if not code or lang not in {'python', 'py'}:
                # Handle requirements separately
                if lang == 'requirements' or filename == 'requirements.txt':
                    self._append_requirements(app_dir, code)
                continue
            
            # Determine target file based on filename or content analysis
            target_path = None
            
            if filename:
                # Explicit filename given
                if filename == 'models.py':
                    target_path = models_path
                elif filename == 'services.py':
                    target_path = services_path
                elif 'routes/user' in filename or filename == 'user.py':
                    target_path = user_routes_path
                elif filename == 'app.py':
                    # Only write to app.py if it's actual Flask app code (has Flask import and app setup)
                    if 'from flask import' in code and ('Flask(' in code or 'create_app' in code):
                        target_path = backend_dir / 'app.py'
                        logger.info("Found explicit app.py with Flask setup")
                    else:
                        # This is probably models being output as app.py - redirect to models.py
                        logger.warning("Block named app.py appears to be models, redirecting to models.py")
                        target_path = models_path
                else:
                    # Other Python file
                    target_path = backend_dir / block.get('filename', filename)
            else:
                # No filename - analyze content to determine destination
                if 'db.Model' in code or 'class ' in code and 'db.Column' in code:
                    target_path = models_path
                    logger.info("Unnamed block appears to be models, writing to models.py")
                elif '@user_bp.route' in code or 'from routes import user_bp' in code:
                    target_path = user_routes_path
                    logger.info("Unnamed block appears to be user routes, writing to routes/user.py")
                elif 'def ' in code and ('validate' in code or 'get_' in code or 'create_' in code):
                    target_path = services_path
                    logger.info("Unnamed block appears to be services, writing to services.py")
                elif 'from flask import' in code and ('Flask(' in code or 'create_app' in code):
                    target_path = backend_dir / 'app.py'
                    logger.info("Unnamed block appears to be Flask app, writing to app.py")
                else:
                    # Default to models.py for class definitions
                    if 'class ' in code:
                        target_path = models_path
                        logger.info("Unnamed block with class, defaulting to models.py")
                    else:
                        logger.warning(f"Could not determine target for unnamed block, skipping")
                        continue
            
            if target_path:
                # Validate Python syntax
                is_valid, errors = self.validate_generated_code(code, 'backend')
                if not is_valid:
                    logger.warning(f"Backend code validation warnings for {target_path.name}:")
                    for err in errors[:3]:  # Limit error output
                        logger.warning(f"  - {err}")
                
                # Create parent directory if needed
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ Wrote {len(code)} chars to {target_path.name}")
                files_written += 1

        # Infer and update dependencies from written files
        for path in [models_path, services_path, user_routes_path]:
            if path.exists():
                code = path.read_text(encoding='utf-8')
                inferred_deps = self._infer_backend_dependencies(code)
                if inferred_deps:
                    self._update_backend_requirements(app_dir, inferred_deps)
        
        logger.info(f"Backend user merge complete: {files_written} files written")
        return files_written > 0
    
    def _merge_backend_admin(self, app_dir: Path, all_blocks: List[Dict]) -> bool:
        """Handle backend merge for 'admin' query - restricted to admin files only."""
        backend_dir = app_dir / 'backend'
        files_written = 0
        files_skipped = 0
        
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '')
            code = block.get('code', '')
            
            if not code:
                continue
            
            # Handle requirements additions (always allowed)
            if lang == 'requirements' or filename == 'requirements.txt':
                self._append_requirements(app_dir, code)
                continue
            
            # Only process Python files
            if lang not in {'python', 'py'}:
                continue
            
            filename_lower = filename.lower() if filename else ''
            
            # Check if file is in admin whitelist
            if self._is_backend_admin_allowed(filename_lower):
                target_path = backend_dir / filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Validate Python syntax
                is_valid, errors = self.validate_generated_code(code, 'backend')
                if not is_valid:
                    logger.warning(f"Admin backend code validation warnings for {filename}:")
                    for err in errors:
                        logger.warning(f"  - {err}")
                
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ [ADMIN] Wrote {len(code)} chars to {filename}")
                files_written += 1
            
            # Check if file can be appended to
            elif self._is_backend_append_allowed(filename_lower):
                target_path = backend_dir / filename
                if target_path.exists():
                    self._smart_append_python(target_path, code)
                    logger.info(f"✓ [ADMIN] Appended functions to {filename}")
                    files_written += 1
                else:
                    logger.warning(f"[ADMIN] Cannot append to non-existent file: {filename}")
                    files_skipped += 1
            
            else:
                # File not allowed for admin query - log warning but continue
                logger.warning(
                    f"[ADMIN] Skipping unauthorized file: {filename} "
                    f"(admin queries can only write to: {', '.join(self.BACKEND_ADMIN_WHITELIST)})"
                )
                files_skipped += 1
        
        if files_written == 0 and files_skipped > 0:
            logger.warning(
                f"[ADMIN] No admin files were written! "
                f"LLM generated {files_skipped} files outside admin whitelist. "
                f"This may indicate a prompt issue."
            )
        
        logger.info(f"[ADMIN] Backend merge complete: {files_written} files written, {files_skipped} skipped")
        return files_written > 0 or files_skipped == 0  # Success if we wrote something OR nothing was generated
    
    def _is_backend_admin_allowed(self, filename: str) -> bool:
        """Check if filename is allowed for admin backend query."""
        if not filename:
            return False
        filename = filename.lower().replace('\\', '/')
        return filename in self.BACKEND_ADMIN_WHITELIST or filename.endswith('/admin.py')
    
    def _is_backend_append_allowed(self, filename: str) -> bool:
        """Check if filename can be appended to during admin query."""
        if not filename:
            return False
        filename = filename.lower().replace('\\', '/')
        return filename in self.BACKEND_ADMIN_APPEND_FILES
    
    def _smart_append_python(self, file_path: Path, new_code: str) -> None:
        """Intelligently append new Python functions/classes to existing file.
        
        Extracts function and class definitions from new_code and appends
        only those that don't already exist in the target file.
        """
        try:
            existing_content = file_path.read_text(encoding='utf-8')
            
            # Parse existing file to find defined names
            existing_names = set()
            try:
                tree = ast.parse(existing_content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        existing_names.add(node.name)
                    elif isinstance(node, ast.ClassDef):
                        existing_names.add(node.name)
            except SyntaxError:
                logger.warning(f"Could not parse {file_path} for duplicate detection")
            
            # Parse new code to extract definitions
            new_definitions = []
            try:
                new_tree = ast.parse(new_code)
                for node in ast.iter_child_nodes(new_tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        if node.name not in existing_names:
                            # Extract the source lines for this definition
                            start_line = node.lineno - 1
                            end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1
                            lines = new_code.splitlines()[start_line:end_line]
                            new_definitions.append('\n'.join(lines))
                            logger.info(f"  Adding new definition: {node.name}")
                        else:
                            logger.info(f"  Skipping duplicate: {node.name}")
            except SyntaxError:
                logger.warning(f"Could not parse new code for {file_path}, appending raw")
                new_definitions = [new_code]
            
            if new_definitions:
                with file_path.open('a', encoding='utf-8') as f:
                    f.write('\n\n# === Admin additions ===\n')
                    f.write('\n\n'.join(new_definitions))
                    f.write('\n')
                logger.info(f"Appended {len(new_definitions)} definitions to {file_path}")
            else:
                logger.info(f"No new definitions to append to {file_path}")
                
        except Exception as e:
            logger.error(f"Failed to append to {file_path}: {e}")

    def merge_frontend(self, app_dir: Path, generated_content: str, query_type: str = 'user') -> bool:
        """
        Replace frontend files with LLM-generated code.
        
        Args:
            app_dir: Path to the app directory
            generated_content: LLM response with code blocks
            query_type: 'user' or 'admin' - controls which files can be written
                       'user' queries can write any file
                       'admin' queries are restricted to admin-specific files
        """
        logger.info(f"Starting frontend merge (query_type={query_type})...")
        
        # Extract all code blocks from the response
        all_blocks = self._extract_all_code_blocks(generated_content)
        
        if query_type == 'user':
            # User query: standard behavior - write main App.jsx and all additional files
            return self._merge_frontend_user(app_dir, all_blocks, generated_content)
        else:
            # Admin query: restricted to admin-specific files only
            return self._merge_frontend_admin(app_dir, all_blocks)
    
    def _merge_frontend_user(self, app_dir: Path, all_blocks: List[Dict], generated_content: str) -> bool:
        """Handle frontend merge for 'user' query - writes to pages/UserPage.jsx and services/api.js.
        
        NOTE: Does NOT overwrite App.jsx - the scaffolding's App.jsx already has routing.
        The LLM generates UserPage content which goes to pages/UserPage.jsx.
        """
        frontend_src_dir = app_dir / 'frontend' / 'src'
        user_page_path = frontend_src_dir / 'pages' / 'UserPage.jsx'
        
        if not user_page_path.exists():
            logger.warning(f"Target UserPage.jsx missing at {user_page_path}, creating...")
            user_page_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Find main JSX code (the user page content)
        # Priority: explicit pages/UserPage.jsx > UserPage.jsx > unnamed block
        main_code = None
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '').lower()
            if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                # Explicit UserPage reference
                if 'userpage' in filename:
                    main_code = block['code']
                    logger.info(f"Found explicit UserPage.jsx block")
                    break
        
        # If no explicit UserPage, look for unnamed block (assume it's UserPage content)
        if not main_code:
            for block in all_blocks:
                lang = block.get('language', '').lower()
                filename = block.get('filename', '').lower()
                if lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                    # Unnamed block - assume it's page content
                    if not filename:
                        main_code = block['code']
                        logger.info(f"Using unnamed JSX block as UserPage content")
                        break
                    # Also accept app.jsx if it looks like page content (has function UserPage or similar)
                    elif filename in {'app.jsx', 'src/app.jsx'}:
                        code = block['code']
                        # Check if this looks like page content (single component, not router)
                        if 'Routes' not in code and 'BrowserRouter' not in code:
                            main_code = code
                            logger.info(f"Block named app.jsx appears to be page content (no router)")
                            break
        
        if not main_code:
            # Fall back to old method
            main_code = self._select_code_block(generated_content, {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'})
        
        if not main_code:
            logger.error(f"Code extraction failed: No frontend code found in LLM response")
            logger.error(f"Response preview: {generated_content[:500]}...")
            return False

        logger.info(f"Extracted {len(main_code)} chars of JSX code from LLM response")

        # Fix Docker networking: replace localhost with relative path for Nginx proxy
        if 'localhost:5000' in main_code:
            logger.info("Fixing API_URL: replacing localhost:5000 with relative path")
            main_code = re.sub(
                r'http://localhost:5000',
                '',
                main_code,
                flags=re.IGNORECASE
            )

        # Ensure export default exists (should export UserPage, not App)
        if 'export default' not in main_code:
            # Detect the function name
            func_match = re.search(r'function\s+(\w+)', main_code)
            export_name = func_match.group(1) if func_match else 'UserPage'
            logger.info(f"Adding missing 'export default {export_name};'")
            main_code += f"\n\nexport default {export_name};"

        # Write to pages/UserPage.jsx (NOT App.jsx)
        user_page_path.write_text(main_code, encoding='utf-8')
        logger.info(f"✓ Wrote {len(main_code)} chars to {user_page_path}")
        
        # Handle additional frontend files (api.js, hooks, components)
        files_written = 1  # UserPage counts as 1
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '')
            code = block.get('code', '')
            
            if not filename or not code:
                continue
            
            # Normalize filename
            filename_lower = filename.lower()
            
            # Skip if this was the main UserPage content we already handled
            if 'userpage' in filename_lower:
                continue
            if filename_lower in {'app.jsx', 'src/app.jsx'}:
                # Check if this is routing code (should go to App.jsx)
                if 'Routes' in code or 'BrowserRouter' in code:
                    app_jsx_path = frontend_src_dir / 'App.jsx'
                    app_jsx_path.write_text(code, encoding='utf-8')
                    logger.info(f"✓ Wrote router code to App.jsx")
                    files_written += 1
                # Otherwise skip - we already used it as UserPage content or it's duplicate
                continue
            
            # Handle CSS files
            if lang == 'css' or filename.endswith('.css'):
                target_filename = filename if filename.endswith('.css') else 'App.css'
                target_path = frontend_src_dir / target_filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ Wrote CSS file: {target_filename}")
                files_written += 1
            
            # Handle additional JSX/JS files
            elif lang in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                target_path = frontend_src_dir / filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ Wrote additional component: {filename}")
                files_written += 1
        
        logger.info(f"Frontend user merge complete: {files_written} files written")
        return True
    
    def _merge_frontend_admin(self, app_dir: Path, all_blocks: List[Dict]) -> bool:
        
        return True
    
    def _merge_frontend_admin(self, app_dir: Path, all_blocks: List[Dict]) -> bool:
        """Handle frontend merge for 'admin' query - restricted to admin files only."""
        frontend_src_dir = app_dir / 'frontend' / 'src'
        files_written = 0
        files_skipped = 0
        
        for block in all_blocks:
            lang = block.get('language', '').lower()
            filename = block.get('filename', '')
            code = block.get('code', '')
            
            if not code:
                continue
            
            filename_lower = filename.lower() if filename else ''
            
            # Handle CSS files (always allowed for styling)
            if lang == 'css' or (filename and filename.endswith('.css')):
                target_filename = filename if filename.endswith('.css') else 'Admin.css'
                target_path = frontend_src_dir / target_filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ [ADMIN] Wrote CSS file: {target_filename}")
                files_written += 1
                continue
            
            # Only process JS/JSX files
            if lang not in {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}:
                continue
            
            # Check if file is in admin whitelist
            if self._is_frontend_admin_allowed(filename_lower):
                # Fix Docker networking
                if 'localhost:5000' in code:
                    code = re.sub(r'http://localhost:5000', '', code, flags=re.IGNORECASE)
                
                target_path = frontend_src_dir / filename
                target_path.parent.mkdir(parents=True, exist_ok=True)
                target_path.write_text(code, encoding='utf-8')
                logger.info(f"✓ [ADMIN] Wrote {len(code)} chars to {filename}")
                files_written += 1
            
            # Check if file can be appended to (api.js)
            elif self._is_frontend_append_allowed(filename_lower):
                target_path = frontend_src_dir / filename
                if target_path.exists():
                    self._smart_append_javascript(target_path, code)
                    logger.info(f"✓ [ADMIN] Appended exports to {filename}")
                    files_written += 1
                else:
                    logger.warning(f"[ADMIN] Cannot append to non-existent file: {filename}")
                    files_skipped += 1
            
            else:
                # File not allowed for admin query - log warning but continue
                logger.warning(
                    f"[ADMIN] Skipping unauthorized file: {filename} "
                    f"(admin queries can only write to: {', '.join(self.FRONTEND_ADMIN_WHITELIST)})"
                )
                files_skipped += 1
        
        if files_written == 0 and files_skipped > 0:
            logger.warning(
                f"[ADMIN] No admin files were written! "
                f"LLM generated {files_skipped} files outside admin whitelist. "
                f"This may indicate a prompt issue."
            )
        
        logger.info(f"[ADMIN] Frontend merge complete: {files_written} files written, {files_skipped} skipped")
        return files_written > 0 or files_skipped == 0
    
    def _is_frontend_admin_allowed(self, filename: str) -> bool:
        """Check if filename is allowed for admin frontend query."""
        if not filename:
            return False
        filename = filename.lower().replace('\\', '/')
        return filename in self.FRONTEND_ADMIN_WHITELIST or 'admin' in filename.lower()
    
    def _is_frontend_append_allowed(self, filename: str) -> bool:
        """Check if filename can be appended to during admin query."""
        if not filename:
            return False
        filename = filename.lower().replace('\\', '/')
        return filename in self.FRONTEND_ADMIN_APPEND_FILES
    
    def _smart_append_javascript(self, file_path: Path, new_code: str) -> None:
        """Intelligently append new JavaScript exports to existing file.
        
        Extracts export statements from new_code and appends only those
        that don't already exist in the target file.
        """
        try:
            existing_content = file_path.read_text(encoding='utf-8')
            
            # Find existing exported names (simplified regex approach)
            existing_exports = set(re.findall(
                r'export\s+(?:const|let|var|function|async\s+function)\s+(\w+)',
                existing_content
            ))
            
            # Find new exports to add
            new_exports = []
            # Match export statements
            export_pattern = re.compile(
                r'(export\s+(?:const|let|var|function|async\s+function)\s+(\w+)[^;]*(?:;|\{[^}]*\}))',
                re.MULTILINE | re.DOTALL
            )
            
            for match in export_pattern.finditer(new_code):
                full_export = match.group(1)
                export_name = match.group(2)
                
                if export_name not in existing_exports:
                    new_exports.append(full_export)
                    logger.info(f"  Adding new export: {export_name}")
                else:
                    logger.info(f"  Skipping duplicate export: {export_name}")
            
            if new_exports:
                with file_path.open('a', encoding='utf-8') as f:
                    f.write('\n\n// === Admin API additions ===\n')
                    f.write('\n\n'.join(new_exports))
                    f.write('\n')
                logger.info(f"Appended {len(new_exports)} exports to {file_path}")
            else:
                logger.info(f"No new exports to append to {file_path}")
                
        except Exception as e:
            logger.error(f"Failed to append to {file_path}: {e}")
    
    def _extract_all_code_blocks(self, content: str) -> List[Dict[str, str]]:
        """Extract all code blocks from content, including filename annotations.
        
        Supports formats:
        - ```python
        - ```python:filename.py
        - ```jsx:components/MyComponent.jsx
        - ```css:App.css
        - ```requirements
        
        Returns list of dicts with 'language', 'filename', and 'code' keys.
        """
        blocks = []
        # Pattern matches ```lang or ```lang:filename
        pattern = re.compile(
            r"```(?P<lang>[a-zA-Z0-9_+-]+)?(?::(?P<filename>[^\n\r`]+))?\s*[\r\n]+(.*?)```",
            re.DOTALL
        )
        
        for match in pattern.finditer(content or ""):
            lang = (match.group('lang') or '').strip().lower()
            filename = (match.group('filename') or '').strip()
            code = (match.group(3) or '').strip()
            
            if code:
                blocks.append({
                    'language': lang,
                    'filename': filename,
                    'code': code
                })
        
        return blocks
    
    def _append_requirements(self, app_dir: Path, requirements_content: str) -> None:
        """Append requirements content to backend requirements.txt."""
        requirements_path = app_dir / 'backend' / 'requirements.txt'
        if not requirements_path.exists():
            logger.warning(f"Backend requirements.txt missing at {requirements_path}")
            return
        
        try:
            existing = requirements_path.read_text(encoding='utf-8')
            existing_packages = {
                re.split(r'[<>=]', line, 1)[0].strip().lower() 
                for line in existing.splitlines() 
                if line.strip() and not line.strip().startswith('#')
            }
            
            new_lines = []
            for line in requirements_content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                pkg_name = re.split(r'[<>=]', line, 1)[0].strip().lower()
                if pkg_name and pkg_name not in existing_packages:
                    new_lines.append(line)
            
            if new_lines:
                with requirements_path.open('a', encoding='utf-8') as f:
                    if not existing.endswith('\n'):
                        f.write('\n')
                    f.write('\n'.join(new_lines) + '\n')
                logger.info(f"Added {len(new_lines)} requirements: {', '.join(new_lines)}")
        except Exception as e:
            logger.warning(f"Failed to append requirements: {e}")
    
    def _select_code_block(self, content: str, preferred_languages: Set[str]) -> Optional[str]:
        """Pick the first code block that matches preferred languages.
        
        Enhanced with fence cleanup for incomplete/malformed markdown fences.
        """
        pattern = re.compile(r"```(?P<lang>[^\n\r`]+)?\s*[\r\n]+(.*?)```", re.DOTALL)
        matches = list(pattern.finditer(content or ""))
        
        if matches:
            # Standard extraction: find matching language or use first fence
            for match in matches:
                lang = (match.group('lang') or '').strip().lower()
                if lang in preferred_languages:
                    return (match.group(2) or '').strip()
            return (matches[0].group(2) or '').strip()
        
        # No complete fences found - check for incomplete/malformed fences
        if '```' in (content or ''):
            logger.warning("Found incomplete code fences, attempting to strip fence markers")
            # Strip leading fence markers (e.g., ```python at start)
            cleaned = re.sub(r'^```[a-z]*\s*\n?', '', content, flags=re.MULTILINE)
            # Strip trailing fence markers (e.g., ``` at end)
            cleaned = re.sub(r'\n?```\s*$', '', cleaned, flags=re.MULTILINE)
            
            if cleaned.strip() and cleaned.strip() != content.strip():
                logger.info(f"Successfully stripped fence markers, extracted {len(cleaned.strip())} chars")
                return cleaned.strip()
            else:
                logger.warning("Fence cleanup did not change content")
        
        # Fallback: return raw content if no fences at all
        return content.strip() if content else None

    def _infer_backend_dependencies(self, code: str) -> Set[str]:
        """Infer third-party packages from generated backend code."""
        modules: Set[str] = set()
        try:
            tree = ast.parse(code or '')
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        modules.add((alias.name or '').split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        modules.add(node.module.split('.')[0])
        except SyntaxError:
            logger.debug("AST parsing failed for dependency inference; falling back to regex")
            for match in re.finditer(r"^\s*(?:from\s+([\w\.]+)\s+import|import\s+([\w\.]+))", code or '', re.MULTILINE):
                module = match.group(1) or match.group(2) or ''
                if module: modules.add(module.split('.')[0])

        packages: Set[str] = set()
        for module in {m for m in modules if m and m.lower() not in self._stdlib_modules and m.lower() not in self._local_prefixes}:
            packages.add(self._package_version_map.get(module, module.replace('_', '-')))
        return packages

    def _update_backend_requirements(self, app_dir: Path, packages: Set[str]) -> None:
        """Append inferred packages to backend requirements.txt if missing."""
        if not packages: return
        requirements_path = app_dir / 'backend' / 'requirements.txt'
        if not requirements_path.exists():
            logger.warning(f"Backend requirements.txt missing at {requirements_path}")
            return

        try:
            original_content = requirements_path.read_text(encoding='utf-8')
            existing_packages = {re.split(r'[<>=]', line, 1)[0].strip().lower() for line in original_content.splitlines() if line.strip() and not line.strip().startswith('#')}
            
            new_entries = [pkg for pkg in sorted(packages) if re.split(r'[<>=]', pkg, 1)[0].strip().lower() not in existing_packages]

            if new_entries:
                with requirements_path.open('a', encoding='utf-8') as f:
                    if not original_content.endswith('\n'): f.write('\n')
                    f.write('\n'.join(new_entries) + '\n')
                logger.info(f"Added {len(new_entries)} dependencies to backend requirements: {', '.join(new_entries)}")
        except OSError as exc:
            logger.warning(f"Failed to update backend requirements: {exc}")


class GenerationService:
    """Main service orchestrating the generation process."""
    
    def __init__(self):
        self.scaffolding = ScaffoldingManager()
        self.generator = CodeGenerator()
        # Remove shared merger - create per-request instances instead
        self.max_concurrent = int(os.getenv('GENERATION_MAX_CONCURRENT', os.getenv('SIMPLE_GENERATION_MAX_CONCURRENT', '4')))
        
        # Queue-based generation control
        self.use_queue = os.getenv('GENERATION_USE_QUEUE', 'true').lower() == 'true'
        self.generation_queue: Optional[Queue] = Queue() if self.use_queue else None
        self.active_generations: Dict[str, threading.Lock] = {}  # Track locks per app
        self.active_lock = threading.Lock()  # Protects active_generations dict
        
        # Start queue worker thread if enabled
        if self.use_queue:
            self.queue_worker_thread = threading.Thread(
                target=self._queue_worker,
                daemon=True,
                name="GenerationQueueWorker"
            )
            self.queue_worker_thread.start()
            logger.info(f"Generation queue enabled with max_concurrent={self.max_concurrent}")
        else:
            logger.info(f"Generation queue disabled - direct execution with max_concurrent={self.max_concurrent}")

    def _get_app_lock(self, model_slug: str, app_num: int) -> threading.Lock:
        """Get or create a file-lock for a specific app to prevent concurrent writes."""
        app_key = f"{model_slug}/app{app_num}"
        with self.active_lock:
            if app_key not in self.active_generations:
                self.active_generations[app_key] = threading.Lock()
            return self.active_generations[app_key]

    def _extract_models_summary(self, app_dir: Path) -> str:
        """Extract summary of models from generated models.py file.
        
        Used to pass model context from backend_user (Query 1) to backend_admin (Query 2).
        """
        models_file = app_dir / 'backend' / 'models.py'
        if not models_file.exists():
            return "No models.py file found."
        
        try:
            content = models_file.read_text(encoding='utf-8')
            
            # Extract class definitions and their fields
            classes = re.findall(r'class\s+(\w+)\([^)]*\):', content)
            
            if not classes:
                return "No model classes found in models.py."
            
            summary_parts = ["Available models from models.py:"]
            for cls in classes:
                if cls not in ('db', 'SQLAlchemy'):  # Skip non-model classes
                    summary_parts.append(f"- {cls}")
            
            # Also include column definitions if found
            columns = re.findall(r'(\w+)\s*=\s*db\.Column\([^)]+\)', content)
            if columns:
                summary_parts.append("\nDefined columns include: " + ", ".join(set(columns[:10])))
            
            return '\n'.join(summary_parts)
        except Exception as e:
            logger.warning(f"Failed to extract models summary: {e}")
            return f"Error reading models.py: {str(e)}"

    def _queue_worker(self):
        """Background worker that processes generation tasks from the queue."""
        if self.generation_queue is None:
            logger.error("Queue worker started but queue is None!")
            return
            
        logger.info("Generation queue worker started")
        while True:
            try:
                # Get task from queue with timeout
                task = self.generation_queue.get(timeout=1.0)
                if task is None:  # Poison pill to stop worker
                    break
                
                # Execute the task
                func, args, kwargs, result_callback = task
                try:
                    result = asyncio.run(func(*args, **kwargs))
                    if result_callback:
                        result_callback(result)
                except Exception as e:
                    logger.exception(f"Queue task failed: {e}")
                    if result_callback:
                        result_callback({'success': False, 'errors': [str(e)]})
                finally:
                    self.generation_queue.task_done()
            except Empty:
                continue
            except Exception as e:
                logger.exception(f"Queue worker error: {e}")

    def get_template_catalog(self) -> List[Dict[str, Any]]:
        """Return available generation templates with metadata.
        
        Validates templates follow slug naming convention and have required fields.
        """
        catalog: List[Dict[str, Any]] = []
        seen_slugs = set()

        if not REQUIREMENTS_DIR.exists():
            logger.debug("Requirements directory missing: %s", REQUIREMENTS_DIR)
            return catalog

        for req_file in sorted(REQUIREMENTS_DIR.glob('*.json')):
            try:
                data = json.loads(req_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON in %s: %s", req_file.name, exc)
                continue
            except OSError as exc:
                logger.warning("Failed to read %s: %s", req_file.name, exc)
                continue

            # Validate required fields
            template_slug = data.get('slug')
            if template_slug is None:
                logger.warning("Skipping %s: missing 'slug' field", req_file.name)
                continue
            
            name = data.get('name')
            if not name:
                logger.warning("Skipping %s: missing 'name' field", req_file.name)
                continue
            
            # Validate slug matches filename (normalized)
            normalized_slug = template_slug.lower().replace('-', '_')
            if req_file.stem.lower().replace('-', '_') != normalized_slug:
                logger.warning(
                    "Slug mismatch in %s: file has slug='%s', filename is %s",
                    req_file.name, template_slug, req_file.stem
                )
                continue
            
            # Check for duplicate slugs
            if template_slug in seen_slugs:
                logger.error("Duplicate template slug %s in %s", template_slug, req_file.name)
                continue
            seen_slugs.add(template_slug)
            
            # Validate structure
            if 'backend_requirements' not in data:
                logger.warning("Template %s missing 'backend_requirements'", req_file.name)
            if 'frontend_requirements' not in data:
                logger.warning("Template %s missing 'frontend_requirements'", req_file.name)
            if 'api_endpoints' not in data:
                logger.warning("Template %s missing 'api_endpoints'", req_file.name)

            description = data.get('description', '')
            category = data.get('category', 'general')
            complexity = data.get('complexity') or data.get('difficulty') or 'medium'

            features = data.get('features') or data.get('key_features') or []
            if isinstance(features, str):
                features = [features]

            tech_stack = data.get('tech_stack') or data.get('stack') or {}
            if not isinstance(tech_stack, dict):
                tech_stack = {'value': tech_stack}

            catalog.append({
                'slug': template_slug,
                'name': name,
                'description': description,
                'category': category,
                'complexity': complexity,
                'features': features,
                'tech_stack': tech_stack,
                'filename': req_file.name,
            })

        logger.info(f"Loaded {len(catalog)} valid templates from {REQUIREMENTS_DIR}")
        return catalog
    
    async def _reserve_app_number(
        self,
        model_slug: str,
        app_num: Optional[int],  # Now optional - None means auto-allocate
        template_slug: str,
        batch_id: Optional[str] = None,
        parent_app_id: Optional[int] = None,
        version: int = 1
    ) -> GeneratedApplication:
        """Atomically reserve an app number by creating DB record immediately.
        
        This prevents race conditions where multiple concurrent generations
        would get the same app number. The record is created in PENDING status
        and updated to COMPLETED/FAILED after generation finishes.
        
        Args:
            model_slug: Normalized model slug
            app_num: App number to reserve (None to auto-allocate next available)
            template_slug: Template being used
            batch_id: Optional batch ID for grouping
            parent_app_id: Optional parent app ID for regenerations
            version: Version number (default 1)
            
        Returns:
            GeneratedApplication record in PENDING status
            
        Raises:
            RuntimeError: If app number already reserved (race condition detected)
        """
        from ..models.core import GeneratedApplication, ModelCapability
        from ..constants import AnalysisStatus
        
        # Auto-allocate app number if not provided
        if app_num is None:
            # Get next available app number for this model
            max_app = db.session.query(
                db.func.max(GeneratedApplication.app_number)
            ).filter_by(model_slug=model_slug).scalar()
            
            app_num = (max_app or 0) + 1
            logger.info(f"Auto-allocated app number {app_num} for {model_slug}")
        
        # Get provider from model capability if available
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        provider = model.provider if model else 'unknown'
        
        # Check if this exact app already exists
        existing = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_num,
            version=version
        ).first()
        
        if existing:
            # App already reserved/exists - this is a race condition
            raise RuntimeError(
                f"App {model_slug}/app{app_num} v{version} already exists (ID={existing.id}). "
                f"This indicates a race condition in app number allocation."
            )
        
        # Create new record in PENDING status
        app_record = GeneratedApplication(
            model_slug=model_slug,
            app_number=app_num,
            version=version,
            parent_app_id=parent_app_id,
            batch_id=batch_id,
            app_type='web_application',
            provider=provider,
            template_slug=template_slug,
            generation_status=AnalysisStatus.PENDING,
            container_status='unknown',
            has_backend=False,
            has_frontend=False,
            has_docker_compose=False
        )
        
        db.session.add(app_record)
        
        try:
            db.session.commit()
            logger.info(
                f"Reserved app number: {model_slug}/app{app_num} v{version} "
                f"(ID={app_record.id}, template={template_slug}, batch={batch_id})"
            )
            return app_record
        except SQLAlchemyError as exc:
            db.session.rollback()
            # Likely a unique constraint violation (race condition)
            raise RuntimeError(
                f"Failed to reserve app {model_slug}/app{app_num} v{version}: {exc}. "
                f"This may indicate a race condition or database error."
            )
    
    async def generate_full_app(
        self,
        model_slug: str,
        app_num: Optional[int],  # None = auto-allocate next available
        template_slug: str,
        generate_frontend: bool = True,
        generate_backend: bool = True,
        batch_id: Optional[str] = None,  # For tracking batch operations
        parent_app_id: Optional[int] = None,  # For regenerations
        version: int = 1  # Version number (1 for new, incremented for regenerations)
    ) -> dict:
        """Generate complete application with atomic app number reservation.
        
        Process:
        0. Reserve app number in DB (atomic)
        1. Scaffold (Docker infrastructure)
        2. Generate backend (if requested)
        3. Generate frontend (if requested)
        4. Merge generated code with scaffolding
        5. Update DB record with final status
        
        Args:
            model_slug: Normalized model slug
            app_num: App number to generate
            template_slug: Template slug (e.g., 'url-shortener')
            generate_frontend: Whether to generate frontend code
            generate_backend: Whether to generate backend code
            batch_id: Optional batch ID for grouping related generations
            parent_app_id: Optional parent app ID if this is a regeneration
            version: Version number (1 for new, incremented for regenerations)
        """
        # Step 0: Atomic app reservation - create DB record immediately
        app_record = await self._reserve_app_number(
            model_slug=model_slug,
            app_num=app_num,
            template_slug=template_slug,
            batch_id=batch_id,
            parent_app_id=parent_app_id,
            version=version
        )
        
        # Use the allocated app_num from DB record (may differ if input was None)
        app_num = app_record.app_number
        
        # Acquire app-specific lock to prevent concurrent writes to same app
        app_lock = self._get_app_lock(model_slug, app_num)
        
        result = {
            'success': False,
            'scaffolded': False,
            'backend_generated': False,
            'frontend_generated': False,
            'errors': []
        }
        
        try:
            # Try to acquire lock with timeout to detect deadlocks
            if not app_lock.acquire(timeout=300):  # 5 minutes
                result['errors'].append(f"Timeout acquiring lock for {model_slug}/app{app_num}")
                return result
            
            try:
                # Create per-request CodeMerger instance
                merger = CodeMerger()
                
                # Step 1: Scaffold
                logger.info(f"=== Generating {model_slug}/app{app_num} (v{version}) ===")
                logger.info("Step 1: Scaffolding...")
                
                if not self.scaffolding.scaffold(model_slug, app_num, template_slug):
                    result['errors'].append("Scaffolding failed")
                    # Update DB record to FAILED status
                    app_record.generation_status = AnalysisStatus.FAILED
                    db.session.commit()
                    return result
                
                result['scaffolded'] = True
                app_dir = self.scaffolding.get_app_dir(model_slug, app_num, template_slug)
                
                # 4-Query System:
                # Query 1: backend_user - Models + User routes + Services
                # Query 2: backend_admin - Admin routes (uses models from Query 1)
                # Query 3: frontend_user - UserPage + API service + Hooks
                # Query 4: frontend_admin - AdminPage + Admin API additions
                
                models_summary = "No models defined yet."
                
                # Step 2: Generate Backend User (Query 1)
                if generate_backend:
                    logger.info("Step 2a: Generating backend user components...")
                    
                    config = GenerationConfig(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                        component='backend',
                        query_type='user'
                    )
                    
                    success, content, error = await self.generator.generate(config)
                    
                    if success:
                        if merger.merge_backend(app_dir, content, query_type='user'):
                            result['backend_user_generated'] = True
                            # Extract models summary for admin query
                            models_summary = self._extract_models_summary(app_dir)
                        else:
                            result['errors'].append("Backend user merge failed")
                    else:
                        result['errors'].append(f"Backend user generation failed: {error}")
                    
                    # Step 2b: Generate Backend Admin (Query 2) - only if user succeeded
                    if result.get('backend_user_generated'):
                        logger.info("Step 2b: Generating backend admin components...")
                        
                        config = GenerationConfig(
                            model_slug=model_slug,
                            app_num=app_num,
                            template_slug=template_slug,
                            component='backend',
                            query_type='admin',
                            existing_models_summary=models_summary
                        )
                        
                        success, content, error = await self.generator.generate(config)
                        
                        if success:
                            if merger.merge_backend(app_dir, content, query_type='admin'):
                                result['backend_admin_generated'] = True
                            else:
                                result['errors'].append("Backend admin merge failed")
                        else:
                            result['errors'].append(f"Backend admin generation failed: {error}")
                    
                    # Overall backend success
                    result['backend_generated'] = result.get('backend_user_generated', False) and result.get('backend_admin_generated', False)
                
                # Step 3: Generate Frontend User (Query 3)
                if generate_frontend:
                    logger.info("Step 3a: Generating frontend user components...")
                    
                    config = GenerationConfig(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                        component='frontend',
                        query_type='user'
                    )
                    
                    success, content, error = await self.generator.generate(config)
                    
                    if success:
                        if merger.merge_frontend(app_dir, content, query_type='user'):
                            result['frontend_user_generated'] = True
                        else:
                            result['errors'].append("Frontend user merge failed")
                    else:
                        result['errors'].append(f"Frontend user generation failed: {error}")
                    
                    # Step 3b: Generate Frontend Admin (Query 4) - only if user succeeded
                    if result.get('frontend_user_generated'):
                        logger.info("Step 3b: Generating frontend admin components...")
                        
                        config = GenerationConfig(
                            model_slug=model_slug,
                            app_num=app_num,
                            template_slug=template_slug,
                            component='frontend',
                            query_type='admin'
                        )
                        
                        success, content, error = await self.generator.generate(config)
                        
                        if success:
                            if merger.merge_frontend(app_dir, content, query_type='admin'):
                                result['frontend_admin_generated'] = True
                            else:
                                result['errors'].append("Frontend admin merge failed")
                        else:
                            result['errors'].append(f"Frontend admin generation failed: {error}")
                    
                    # Overall frontend success
                    result['frontend_generated'] = result.get('frontend_user_generated', False) and result.get('frontend_admin_generated', False)
            finally:
                # Always release the lock
                app_lock.release()
        except Exception as e:
            logger.exception(f"Unexpected error during generation: {e}")
            result['errors'].append(f"Unexpected error: {str(e)}")
            return result
        
        # Overall success
        result['success'] = (
            result['scaffolded'] and
            (not generate_backend or result['backend_generated']) and
            (not generate_frontend or result['frontend_generated'])
        )
        
        result['app_dir'] = str(app_dir)
        result['app_num'] = app_num
        result['app_number'] = app_num  # Alias for API compatibility
        result['model_slug'] = model_slug
        result['template_slug'] = template_slug
        backend_port, frontend_port = self.scaffolding.get_ports(model_slug, app_num)
        result['backend_port'] = backend_port
        result['frontend_port'] = frontend_port

        try:
            persist_summary = self._persist_generation_result(
                model_slug=model_slug,
                app_num=app_num,
                app_dir=app_dir,
                template_slug=template_slug,
                backend_port=backend_port,
                frontend_port=frontend_port,
                generate_backend=generate_backend,
                generate_frontend=generate_frontend,
                result_snapshot=result,
                app_record=app_record  # Pass existing record
            )
            result.update(persist_summary)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Failed to persist generation metadata for %s/app%s: %s",
                model_slug,
                app_num,
                exc,
            )
            result['database_updated'] = False
            result['database_error'] = str(exc)

        logger.info(f"=== Generation complete: {result['success']} ===")
        return result

    def _persist_generation_result(
        self,
        *,
        model_slug: str,
        app_num: int,
        app_dir: Path,
        template_slug: str,
        backend_port: int,
        frontend_port: int,
        generate_backend: bool,
        generate_frontend: bool,
        result_snapshot: Dict[str, Any],
        app_record: GeneratedApplication  # Pre-created record from _reserve_app_number
    ) -> Dict[str, Any]:
        """Update GeneratedApplication record after generation completes.
        
        The record was already created by _reserve_app_number in PENDING status.
        This method updates it with final status and metadata.
        """

        app_features = self._inspect_generated_app(app_dir)
        
        # Update existing record (no need to query, we have it from reservation)
        app_record.has_backend = app_features['has_backend']
        app_record.has_frontend = app_features['has_frontend']
        app_record.has_docker_compose = app_features['has_docker_compose']
        app_record.backend_framework = app_features['backend_framework']
        app_record.frontend_framework = app_features['frontend_framework']
        app_record.generation_status = (
            AnalysisStatus.COMPLETED if result_snapshot.get('success') else AnalysisStatus.FAILED
        )

        metadata = app_record.get_metadata() or {}
        metadata_updates = {
            'template_slug': template_slug,
            'generate_backend': generate_backend,
            'generate_frontend': generate_frontend,
            'backend_generated': result_snapshot.get('backend_generated'),
            'frontend_generated': result_snapshot.get('frontend_generated'),
            'scaffolded': result_snapshot.get('scaffolded'),
            'errors': result_snapshot.get('errors', []),
            'backend_port': backend_port,
            'frontend_port': frontend_port,
            'app_dir': str(app_dir),
            'success': result_snapshot.get('success'),
            'last_generated_at': utc_now().isoformat(),
        }
        metadata.update({key: value for key, value in metadata_updates.items() if value is not None})
        app_record.set_metadata(metadata)

        app_record.updated_at = utc_now()

        try:
            db.session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - best effort persistence
            db.session.rollback()
            raise RuntimeError(f"Database update failed: {exc}")

        return {
            'database_updated': True,
            'database_record_created': False,  # Record was created by _reserve_app_number
            'database_application_id': app_record.id,
        }

    def _inspect_generated_app(self, app_dir: Path) -> Dict[str, Any]:
        """Inspect generated app directory and infer feature flags."""

        features = {
            'has_backend': False,
            'has_frontend': False,
            'has_docker_compose': False,
            'backend_framework': None,
            'frontend_framework': None,
        }

        if not app_dir.exists():
            return features

        backend_dir = app_dir / 'backend'
        frontend_dir = app_dir / 'frontend'

        backend_app = backend_dir / 'app.py'
        backend_requirements = backend_dir / 'requirements.txt'
        backend_generated = backend_dir / 'app_generated.py'
        if backend_app.exists() or backend_requirements.exists() or backend_generated.exists():
            features['has_backend'] = True
            features['backend_framework'] = 'Flask'

        frontend_app = frontend_dir / 'src' / 'App.jsx'
        frontend_package = frontend_dir / 'package.json'
        if frontend_app.exists() or frontend_package.exists():
            features['has_frontend'] = True
            features['frontend_framework'] = 'React'

        compose_file = app_dir / 'docker-compose.yml'
        compose_alt = app_dir / 'docker-compose.yaml'
        if compose_file.exists() or compose_alt.exists():
            features['has_docker_compose'] = True

        return features

    def get_generation_status(self) -> Dict[str, Any]:
        """Expose lightweight status metrics for dashboards."""
        status: Dict[str, Any] = {
            'in_flight_count': 0,
            'available_slots': self.max_concurrent,
            'max_concurrent': self.max_concurrent,
            'in_flight_keys': [],
            'active_tasks': 0,
            'system_healthy': self.scaffolding.scaffolding_source.exists(),
        }

        try:
            from sqlalchemy import func
            from app.models import GeneratedApplication
            from app.constants import AnalysisStatus

            in_progress = (
                GeneratedApplication.query
                .filter(GeneratedApplication.generation_status == AnalysisStatus.RUNNING)
            )

            running = in_progress.count()
            status['in_flight_count'] = running
            status['active_tasks'] = running
            status['available_slots'] = max(self.max_concurrent - running, 0)

            if running:
                recent = (
                    in_progress.order_by(GeneratedApplication.updated_at.desc())
                    .limit(5)
                    .all()
                )
                # Ensure timezone-aware comparison to prevent errors
                status['in_flight_keys'] = [
                    f"{app.model_slug}/app{app.app_number}"
                    for app in recent
                    if _ensure_timezone_aware(app.updated_at) is not None
                ]

            total_apps = GeneratedApplication.query.count()
            status['total_results'] = total_apps

            latest_created = (
                GeneratedApplication.query
                .with_entities(func.max(GeneratedApplication.created_at))
                .scalar()
            )
            if latest_created:
                status['last_generated_at'] = latest_created.isoformat()

            status.setdefault('stubbed', False)
        except Exception:  # pragma: no cover - metrics are best-effort
            status.setdefault('total_results', 0)
            status['system_healthy'] = False
            status.setdefault('stubbed', True)

        return status

    def get_summary_metrics(self) -> Dict[str, Any]:
        """Return summary metrics used by the generator dashboards."""
        summary: Dict[str, Any] = {
            'total_results': 0,
            'total_templates': 0,
            'total_models': 0,
            'recent_results': 0,
        }

        try:
            from sqlalchemy import func
            from app.models import GeneratedApplication, ModelCapability
            from app.utils.time import utc_now

            summary['total_results'] = GeneratedApplication.query.count()
            summary['total_models'] = ModelCapability.query.count()

            day_ago = utc_now() - timedelta(days=1)
            summary['recent_results'] = (
                GeneratedApplication.query
                .filter(GeneratedApplication.created_at >= day_ago)
                .count()
            )

            latest_model = (
                ModelCapability.query
                .order_by(ModelCapability.created_at.desc())
                .with_entities(ModelCapability.canonical_slug)
                .first()
            )
            if latest_model:
                summary['latest_model'] = latest_model[0]

            summary['total_templates'] = sum(
                1 for path in self.scaffolding.scaffolding_source.rglob('*') if path.is_file()
            )
        except Exception:  # pragma: no cover - metrics are advisory
            pass

        return summary


# Singleton
_service = None

def get_generation_service() -> GenerationService:
    """Get singleton instance."""
    global _service
    if _service is None:
        _service = GenerationService()
    return _service
