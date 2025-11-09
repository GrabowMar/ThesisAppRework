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
)
from app.services.port_allocation_service import get_port_allocation_service
from app.services.openrouter_chat_service import get_openrouter_chat_service
from app.extensions import db
from app.models import GeneratedApplication, ModelCapability, AnalysisStatus
from app.utils.time import utc_now

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
    temperature: float = 0.3
    max_tokens: int = 64000  # Increased from 32000 for longer, more complete code generation
    requirements: Optional[Dict] = None  # Requirements from JSON file
    template_type: str = 'auto'  # 'auto', 'full', or 'compact'


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
    
    def get_app_dir(self, model_slug: str, app_num: int) -> Path:
        """Get app directory path."""
        safe_model = re.sub(r'[^\w\-.]', '_', model_slug)
        return GENERATED_APPS_DIR / safe_model / f"app{app_num}"
    
    def scaffold(self, model_slug: str, app_num: int) -> bool:
        """Copy scaffolding to app directory.
        
        This creates the IMMUTABLE base structure that AI never touches.
        """
        app_dir = self.get_app_dir(model_slug, app_num)
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
        
        # Use hugging_face_id if available (for case-sensitive providers), otherwise fall back to model_id
        openrouter_model = model.hugging_face_id or model.model_id
        logger.info(f"Using OpenRouter model: {openrouter_model} (HF ID: {model.hugging_face_id}, model_id: {model.model_id}, slug: {config.model_slug})")
        
        # Get model-specific token limit, capping at config.max_tokens
        model_limit = get_model_token_limit(openrouter_model, default=config.max_tokens)
        effective_max_tokens = min(config.max_tokens, model_limit)
        
        if effective_max_tokens < config.max_tokens:
            logger.info(f"Capping max_tokens to {effective_max_tokens} (model limit) from {config.max_tokens} (config)")
        
        messages = [
            {"role": "system", "content": self._get_system_prompt(config.component)},
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
                error_message = response_data.get("error", {}).get("message", "Unknown API error")
                return False, "", f"API error {status_code}: {error_message}"

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
    
    def _load_prompt_template(self, component: str, model_slug: Optional[str] = None) -> str:
        """Load prompt template for component.
        
        Automatically uses compact template for models with <8K output limit.
        """
        # Determine if we should use compact template
        use_compact = False
        if model_slug:
            token_limit = get_model_token_limit(model_slug)
            # Use compact for models with <=8192 output limit (raised from 4096 due to higher token limits)
            use_compact = token_limit <= 8192
        
        # Try compact template first if needed
        if use_compact:
            compact_file = self.template_dir / 'two-query' / f"{component}_compact.md.jinja2"
            if compact_file.exists():
                try:
                    with open(compact_file, 'r', encoding='utf-8') as f:
                        logger.info(f"Using compact template for {component} (model output limit: {token_limit})")
                        return f.read()
                except Exception as e:
                    logger.warning(f"Failed to load compact template, falling back to standard: {e}")
        
        # Use standard template
        template_file = self.template_dir / 'two-query' / f"{component}.md.jinja2"
        
        if not template_file.exists():
            logger.warning(f"Template not found: {template_file}")
            return ""
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            return ""

    def _format_api_endpoints(self, requirements: Optional[Dict[str, Any]]) -> str:
        """Format API endpoint definitions for inclusion in prompts."""
        if not requirements:
            return "No explicit API endpoints provided."

        endpoints = requirements.get('api_endpoints') or []
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
        """Build generation prompt based on template + scaffolding + requirements."""
        from jinja2 import Environment, FileSystemLoader

        # Load requirements if not already loaded
        if not config.requirements:
            config.requirements = self._load_requirements(config.template_slug)
        
        reqs = config.requirements
        
        # Set up Jinja2 environment
        env = Environment(loader=FileSystemLoader(self.template_dir / 'two-query'))
        
        # Determine which template to use based on preference or model output limit
        template_type = getattr(config, 'template_type', 'auto')
        
        if template_type == 'full':
            use_compact = False
            logger.info(f"Using FULL template for {config.component} (forced by user preference)")
        elif template_type == 'compact':
            use_compact = True
            logger.info(f"Using COMPACT template for {config.component} (forced by user preference)")
        else:  # 'auto'
            token_limit = get_model_token_limit(config.model_slug) if hasattr(config, 'model_slug') else 64000
            # Use compact for models with <=8192 output limit (raised from 4096 due to higher token limits)
            use_compact = token_limit <= 8192
            if use_compact:
                logger.info(f"Using compact template for {config.component} (auto: model limit {token_limit} tokens)")
            else:
                logger.info(f"Using full template for {config.component} (auto: model limit {token_limit} tokens)")
        
        template_name = f"{config.component}_compact.md.jinja2" if use_compact else f"{config.component}.md.jinja2"
        
        try:
            template = env.get_template(template_name)
        except Exception as e:
            # Fall back to standard template if compact not found
            if use_compact:
                logger.warning(f"Compact template not found, using standard: {e}")
                try:
                    template = env.get_template(f"{config.component}.md.jinja2")
                except Exception:
                    template = None
            else:
                template = None

        # If template exists, use it
        if template and reqs:
            app_name = reqs.get('name', 'Application')
            app_description = reqs.get('description', 'web application')
            
            if config.component == 'backend':
                req_list = reqs.get('backend_requirements', [])
            else:
                req_list = reqs.get('frontend_requirements', [])

            endpoint_text = self._format_api_endpoints(reqs)
            
            # Load scaffolding content
            scaffolding_content = self._load_scaffolding_files(config.model_slug, config.app_num)

            # Create context for Jinja2
            context = {
                'name': app_name,
                'description': app_description,
                'backend_requirements': req_list if config.component == 'backend' else [],
                'frontend_requirements': req_list if config.component == 'frontend' else [],
                'api_endpoints': endpoint_text,
                **scaffolding_content
            }
            
            # Render the prompt
            prompt = template.render(context)
            
            logger.info(f"Built prompt using Jinja2 template: {len(prompt)} chars")
            return prompt
        
        # Fallback to old format if template/requirements not found
        logger.warning("Jinja2 template or requirements not found, using fallback")

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

    def _load_scaffolding_files(self, model_slug: str, app_num: int) -> Dict[str, str]:
        """Load content of key scaffolding files to inject into prompts."""
        scaffold_manager = ScaffoldingManager()
        app_dir = scaffold_manager.get_app_dir(model_slug, app_num)
        
        files_to_load = {
            'scaffolding_app_py': app_dir / 'backend' / 'app.py',
            'scaffolding_app_jsx': app_dir / 'frontend' / 'src' / 'App.jsx',
            'scaffolding_package_json': app_dir / 'frontend' / 'package.json',
            'scaffolding_requirements_txt': app_dir / 'backend' / 'requirements.txt',
        }
        
        content = {}
        for key, path in files_to_load.items():
            try:
                if path.exists():
                    content[key] = path.read_text(encoding='utf-8')
                else:
                    content[key] = f"<!-- File not found: {path.name} -->"
            except Exception as e:
                logger.warning(f"Could not read scaffolding file {path}: {e}")
                content[key] = f"<!-- Error reading file: {path.name} -->"
        
        return content

    def _get_system_prompt(self, component: str) -> str:
        """Get system prompt."""
        if component == 'frontend':
            return """You are an expert React developer specializing in production-ready web applications.

Your task is to generate ONLY the App.jsx component code based on the given requirements.

RULES:
- Generate ONLY application code (App.jsx component)
- DO NOT generate infrastructure files (package.json, vite.config.js, index.html, Dockerfile, etc)
- Use modern React patterns (functional components, hooks)
- Include all necessary imports (React, axios, useState, useEffect, etc)
- Implement ALL specified frontend requirements completely
- Add proper error handling, loading states, and user feedback
- Use clean, semantic JSX structure
- Include inline styles or use className for CSS (App.css will exist)
- Generate complete, working code - no placeholders or TODOs

Return ONLY the JSX/JavaScript code wrapped in ```jsx code blocks."""
        
        else:
            return """You are an expert Flask developer specializing in production-ready REST APIs.

Your task is to generate ONLY the Flask application code based on the given requirements.

RULES:
- Generate ONLY application code (routes, models, business logic)
- DO NOT generate infrastructure files (Dockerfile, requirements.txt, docker-compose.yml, etc)
- Use Flask best practices and proper project structure
- Use SQLAlchemy for database models when needed
- Include CORS configuration for frontend integration
- Implement ALL specified backend requirements completely
- Add proper error handling, validation, and logging
- Use appropriate HTTP status codes and response formats
- Generate complete, working code - no placeholders or TODOs

Return ONLY the Python code wrapped in ```python code blocks."""


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

    def merge_backend(self, app_dir: Path, generated_content: str) -> bool:
        """
        Replace backend app.py with LLM-generated code after extracting from fences.
        """
        logger.info("Starting simplified backend merge (direct overwrite)...")
        app_py_path = app_dir / 'backend' / 'app.py'
        if not app_py_path.exists():
            logger.error(f"Target app.py missing at {app_py_path}!")
            return False

        # Extract code from markdown fences
        generated_code = self._select_code_block(generated_content, {'python', 'py'})
        if not generated_code:
            logger.error(f"Code extraction failed: No Python code found in LLM response")
            if '```' in generated_content[:200]:
                logger.error(f"  → Found fence markers but extraction failed (incomplete/malformed fences?)")
            else:
                logger.error(f"  → No markdown code fences detected (LLM may not have generated code)")
            logger.error(f"Response preview: {generated_content[:500]}...")
            return False

        logger.info(f"Extracted {len(generated_code)} chars of Python code from LLM response")

        # Validate Python syntax
        is_valid, errors = self.validate_generated_code(generated_code, 'backend')
        if not is_valid:
            logger.error(f"Backend code validation failed with {len(errors)} error(s):")
            for i, error in enumerate(errors, 1):
                logger.error(f"  {i}. {error}")
            logger.error("Writing code anyway - Docker build will catch critical errors")

        # Write complete generated code directly
        app_py_path.write_text(generated_code, encoding='utf-8')
        logger.info(f"✓ Wrote {len(generated_code)} chars to {app_py_path}")

        # Infer and update dependencies
        inferred_deps = self._infer_backend_dependencies(generated_code)
        if inferred_deps:
            logger.info(f"Inferred {len(inferred_deps)} backend dependencies: {sorted(inferred_deps)}")
            self._update_backend_requirements(app_dir, inferred_deps)
            
        return True

    def merge_frontend(self, app_dir: Path, generated_content: str) -> bool:
        """
        Replace frontend App.jsx with LLM-generated code after extracting from fences.
        """
        logger.info("Starting simplified frontend merge (direct overwrite)...")
        app_jsx = app_dir / 'frontend' / 'src' / 'App.jsx'
        if not app_jsx.exists():
            logger.error(f"Target App.jsx missing at {app_jsx}!")
            return False
        
        # Extract code from markdown fences
        selected_code = self._select_code_block(generated_content, {'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'})
        if not selected_code:
            logger.error(f"Code extraction failed: No frontend code found in LLM response")
            if '```' in generated_content[:200]:
                logger.error(f"  → Found fence markers but extraction failed (incomplete/malformed fences?)")
            elif '```python' in generated_content[:200]:
                logger.error(f"  → LLM used 'python' tag instead of 'jsx/javascript' (wrong language tag)")
            else:
                logger.error(f"  → No markdown code fences detected (LLM may not have generated code)")
            logger.error(f"Response preview: {generated_content[:500]}...")
            return False

        logger.info(f"Extracted {len(selected_code)} chars of JSX code from LLM response")

        # Fix Docker networking: replace localhost with backend:5000
        if 'localhost' in selected_code and 'backend:5000' not in selected_code:
            logger.info("Fixing API_URL: replacing localhost references with backend:5000")
            selected_code = re.sub(
                r'http://localhost:5000',
                'http://backend:5000',
                selected_code,
                flags=re.IGNORECASE
            )
            selected_code = re.sub(
                r'localhost:5000',
                'backend:5000',
                selected_code,
                flags=re.IGNORECASE
            )

        # Validate frontend code (warnings only)
        is_valid, errors = self.validate_generated_code(selected_code, 'frontend')
        if errors:
            logger.warning(f"Frontend validation warnings ({len(errors)}):")
            for i, error in enumerate(errors, 1):
                logger.warning(f"  {i}. {error}")

        # Ensure export default exists
        if 'export default' not in selected_code:
            logger.info("Adding missing 'export default App;'")
            selected_code += "\n\nexport default App;"

        # Write complete generated code directly
        app_jsx.write_text(selected_code, encoding='utf-8')
        logger.info(f"✓ Wrote {len(selected_code)} chars to {app_jsx}")
        return True
    
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
    
    async def generate_full_app(
        self,
        model_slug: str,
        app_num: int,
        template_slug: str,
        generate_frontend: bool = True,
        generate_backend: bool = True,
        template_type: str = 'auto'  # 'auto', 'full', or 'compact'
    ) -> dict:
        """Generate complete application.
        
        Process:
        1. Scaffold (Docker infrastructure)
        2. Generate backend (if requested)
        3. Generate frontend (if requested)
        4. Merge generated code with scaffolding
        
        Args:
            template_type: 'auto' (default, based on model limit), 'full', or 'compact'
        """
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
                logger.info(f"=== Generating {model_slug}/app{app_num} ===")
                logger.info("Step 1: Scaffolding...")
                
                if not self.scaffolding.scaffold(model_slug, app_num):
                    result['errors'].append("Scaffolding failed")
                    return result
                
                result['scaffolded'] = True
                app_dir = self.scaffolding.get_app_dir(model_slug, app_num)
                
                # Step 2: Generate Backend
                if generate_backend:
                    logger.info("Step 2: Generating backend...")
                    
                    config = GenerationConfig(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                        component='backend',
                        template_type=template_type
                    )
                    
                    success, content, error = await self.generator.generate(config)
                    
                    if success:
                        if merger.merge_backend(app_dir, content):
                            result['backend_generated'] = True
                        else:
                            result['errors'].append("Backend merge failed")
                    else:
                        result['errors'].append(f"Backend generation failed: {error}")
                
                # Step 3: Generate Frontend
                if generate_frontend:
                    logger.info("Step 3: Generating frontend...")
                    
                    config = GenerationConfig(
                        model_slug=model_slug,
                        app_num=app_num,
                        template_slug=template_slug,
                        component='frontend',
                        template_type=template_type
                    )
                    
                    success, content, error = await self.generator.generate(config)
                    
                    if success:
                        if merger.merge_frontend(app_dir, content):
                            result['frontend_generated'] = True
                        else:
                            result['errors'].append("Frontend merge failed")
                    else:
                        result['errors'].append(f"Frontend generation failed: {error}")
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
                result_snapshot=result
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
        result_snapshot: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create or update GeneratedApplication rows after generation."""

        app_features = self._inspect_generated_app(app_dir)
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        provider = 'unknown'
        if model and model.provider:
            provider = model.provider

        app_record = GeneratedApplication.query.filter_by(
            model_slug=model_slug,
            app_number=app_num
        ).first()

        created = False
        if not app_record:
            app_record = GeneratedApplication()
            app_record.model_slug = model_slug
            app_record.app_number = app_num
            app_record.app_type = 'web_application'
            app_record.provider = provider
            app_record.container_status = 'unknown'
            created = True
            db.session.add(app_record)
        else:
            if provider != 'unknown' and app_record.provider != provider:
                app_record.provider = provider
            if not app_record.app_type:
                app_record.app_type = 'web_application'
            if not app_record.provider:
                app_record.provider = 'unknown'

        app_record.has_backend = app_features['has_backend']
        app_record.has_frontend = app_features['has_frontend']
        app_record.has_docker_compose = app_features['has_docker_compose']
        app_record.backend_framework = app_features['backend_framework']
        app_record.frontend_framework = app_features['frontend_framework']
        app_record.template_slug = template_slug
        app_record.generation_status = (
            AnalysisStatus.COMPLETED if result_snapshot.get('success') else AnalysisStatus.FAILED
        )
        if not app_record.container_status:
            app_record.container_status = 'unknown'

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

        now = utc_now()
        if created and not app_record.created_at:
            app_record.created_at = now
        app_record.updated_at = now

        try:
            db.session.commit()
        except SQLAlchemyError as exc:  # pragma: no cover - best effort persistence
            db.session.rollback()
            raise RuntimeError(f"Database update failed: {exc}")

        return {
            'database_updated': True,
            'database_record_created': created,
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
