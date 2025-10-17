"""Simple Code Generation Service
=================================

A clean, focused service for AI-powered code generation with proper scaffolding.

Philosophy:
- Do ONE thing well: generate code and save it properly
- Use scaffolding templates exactly as-is
- Simple, predictable port allocation
- No complex extraction logic - just save what AI gives us
- Clear separation of concerns

Directory Structure:
generated/apps/{model_slug}/app{N}/
  ├── docker-compose.yml          # From scaffolding
  ├── .env.example                # From scaffolding  
  ├── backend/
  │   ├── Dockerfile              # From scaffolding
  │   ├── app.py                  # AI generated
  │   └── requirements.txt        # AI generated or scaffolding
  └── frontend/
      ├── Dockerfile              # From scaffolding
      ├── nginx.conf              # From scaffolding
      ├── vite.config.js          # From scaffolding (with ports)
      ├── package.json            # AI generated or scaffolding
      ├── index.html              # AI generated or scaffolding
      └── src/
          ├── App.jsx             # AI generated
          ├── App.css             # AI generated or scaffolding
          └── main.jsx            # AI generated or scaffolding
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.paths import (
    GENERATED_APPS_DIR,
    APP_TEMPLATES_DIR,
    SCAFFOLDING_DIR,
)
from app.services.code_validator import validate_generated_code

logger = logging.getLogger(__name__)


@dataclass
class GenerationRequest:
    """Simple request for code generation."""
    template_id: int
    model_slug: str
    component: str  # "frontend" or "backend"
    temperature: float = 0.3
    max_tokens: int = 16000


@dataclass
class GenerationResult:
    """Simple result from code generation."""
    success: bool
    content: str
    error: Optional[str] = None
    tokens_used: int = 0
    duration: float = 0.0


class SimpleGenerationService:
    """Clean, simple code generation service."""
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.scaffolding_dir = SCAFFOLDING_DIR / 'react-flask'
        self.base_backend_port = 5001
        self.base_frontend_port = 8001
        
        # Ensure directories exist
        GENERATED_APPS_DIR.mkdir(parents=True, exist_ok=True)
        
    def get_ports(self, model_slug: str, app_num: int) -> Tuple[int, int]:
        """Get allocated ports for a model/app combination.
        
        Simple formula: backend = 5001 + (app_num * 2), frontend = backend + 1000
        """
        backend_port = self.base_backend_port + (app_num * 2)
        frontend_port = self.base_frontend_port + (app_num * 2)
        return backend_port, frontend_port
    
    def get_app_dir(self, model_slug: str, app_num: int) -> Path:
        """Get the directory for a specific app."""
        # Clean model slug for filesystem
        safe_model = re.sub(r'[^\w\-.]', '_', model_slug)
        app_dir = GENERATED_APPS_DIR / safe_model / f"app{app_num}"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir
    
    def scaffold_app(self, model_slug: str, app_num: int, force: bool = False) -> bool:
        """Copy scaffolding files to app directory with port substitution.
        
        This creates the complete Docker infrastructure:
        - docker-compose.yml
        - Dockerfiles (backend/frontend)
        - .dockerignore files
        - nginx.conf
        - vite.config.js
        - .env.example
        
        All placeholders {{backend_port|5000}} are replaced with actual ports.
        """
        app_dir = self.get_app_dir(model_slug, app_num)
        backend_port, frontend_port = self.get_ports(model_slug, app_num)
        
        # Check if already scaffolded (unless force=True)
        docker_compose = app_dir / 'docker-compose.yml'
        if docker_compose.exists() and not force:
            logger.info(f"App already scaffolded: {app_dir}")
            return True
        
        if not self.scaffolding_dir.exists():
            logger.error(f"Scaffolding directory not found: {self.scaffolding_dir}")
            return False
        
        logger.info(f"Scaffolding {model_slug}/app{app_num} with ports {backend_port}/{frontend_port}")
        
        # Substitution map
        substitutions = {
            'backend_port': str(backend_port),
            'frontend_port': str(frontend_port),
            'model_name': model_slug,
            'PROJECT_NAME': f"{model_slug}_app{app_num}",
            'BACKEND_PORT': str(backend_port),
            'FRONTEND_PORT': str(frontend_port),
            'FLASK_RUN_PORT': str(backend_port),
            'CORS_ORIGINS': f'http://localhost:{frontend_port}',
        }
        
        # Copy all files from scaffolding
        files_copied = 0
        for src_path in self.scaffolding_dir.rglob('*'):
            if not src_path.is_file():
                continue
            
            # Get relative path and target
            rel_path = src_path.relative_to(self.scaffolding_dir)
            dest_path = app_dir / rel_path
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                # Read content
                content = src_path.read_text(encoding='utf-8')
                
                # Apply ALL substitutions - both {{key|default}} and {{key}} patterns
                for key, value in substitutions.items():
                    # Replace {{key|anything}} with value
                    content = re.sub(
                        r'\{\{' + re.escape(key) + r'\|[^\}]+\}\}',
                        value,
                        content
                    )
                    # Replace {{key}} with value
                    content = content.replace(f'{{{{{key}}}}}', value)
                
                # Write file
                dest_path.write_text(content, encoding='utf-8')
                files_copied += 1
                logger.debug(f"Copied: {rel_path}")
                
            except UnicodeDecodeError:
                # Binary file, just copy
                shutil.copy2(src_path, dest_path)
                files_copied += 1
            except Exception as e:
                logger.warning(f"Failed to copy {src_path}: {e}")
        
        logger.info(f"Scaffolded {files_copied} files for {model_slug}/app{app_num}")
        return files_copied > 0
    
    async def generate_code(self, request: GenerationRequest) -> GenerationResult:
        """Generate code using AI model.
        
        Makes a single API call to OpenRouter for frontend OR backend generation.
        """
        start_time = time.time()
        
        # Load template
        template_content = await self._load_template(request.template_id, request.component)
        if not template_content:
            return GenerationResult(
                success=False,
                content="",
                error=f"Template {request.template_id} ({request.component}) not found"
            )
        
        # Build prompt
        prompt = self._build_prompt(template_content, request.component)
        
        # Get the actual OpenRouter model ID from the database
        # canonical_slug is like: anthropic_claude-4.5-haiku-20251001
        # model_id is like: anthropic/claude-haiku-4.5 (what OpenRouter expects)
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug=request.model_slug).first()
        if not model:
            raise ValueError(f"Model not found in database: {request.model_slug}")
        
        openrouter_model = model.model_id
        logger.info(f"Using OpenRouter model: {openrouter_model} (from slug: {request.model_slug})")
        
        # Prepare API request
        payload = {
            "model": openrouter_model,
            "messages": [
                {
                    "role": "system",
                    "content": self._get_system_prompt(request.component)
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Make API call
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return GenerationResult(
                            success=False,
                            content="",
                            error=f"API error {response.status}: {error_text}",
                            duration=time.time() - start_time
                        )
                    
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    tokens = data.get('usage', {}).get('total_tokens', 0)
                    
                    return GenerationResult(
                        success=True,
                        content=content,
                        tokens_used=tokens,
                        duration=time.time() - start_time
                    )
                    
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return GenerationResult(
                success=False,
                content="",
                error=str(e),
                duration=time.time() - start_time
            )
    
    def save_generated_code(
        self,
        model_slug: str,
        app_num: int,
        component: str,
        content: str
    ) -> Dict[str, Any]:
        """Extract code blocks from AI response and save to appropriate files.
        
        Simple extraction: look for ```language blocks and save based on patterns.
        Also validates the code before saving.
        """
        app_dir = self.get_app_dir(model_slug, app_num)
        
        # Extract code blocks
        code_blocks = self._extract_code_blocks(content)
        
        # Store extracted content for validation
        extracted_files = {}
        saved_files = []
        
        for language, code in code_blocks:
            # Determine target file
            target_path = self._determine_file_path(
                app_dir, language, code, component
            )
            
            if target_path:
                # Store for validation
                relative_path = str(target_path.relative_to(app_dir))
                extracted_files[relative_path] = code
                
                try:
                    # Ensure directory exists
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write file
                    target_path.write_text(code, encoding='utf-8')
                    saved_files.append(relative_path)
                    logger.info(f"Saved: {relative_path}")
                    
                except Exception as e:
                    logger.error(f"Failed to save {target_path}: {e}")
        
        # Validate generated code
        validation_results = self._validate_saved_code(extracted_files, component)
        
        result = {
            'saved_files': saved_files,
            'blocks_extracted': len(code_blocks),
            'app_dir': str(app_dir),
            'validation': validation_results
        }
        
        # Log validation warnings/errors
        if component == 'backend':
            backend_val = validation_results.get('backend', {})
            if backend_val.get('errors'):
                logger.error(f"Backend validation errors: {backend_val['errors']}")
            if backend_val.get('warnings'):
                logger.warning(f"Backend validation warnings: {backend_val['warnings']}")
        
        elif component == 'frontend':
            frontend_val = validation_results.get('frontend', {})
            if frontend_val.get('errors'):
                logger.error(f"Frontend validation errors: {frontend_val['errors']}")
            if frontend_val.get('warnings'):
                logger.warning(f"Frontend validation warnings: {frontend_val['warnings']}")
        
        return result
    
    def _validate_saved_code(self, extracted_files: Dict[str, str], component: str) -> Dict[str, Any]:
        """Validate extracted code files.
        
        Args:
            extracted_files: Dict of {relative_path: content}
            component: "backend" or "frontend"
            
        Returns:
            Validation results dict
        """
        # Prepare files for validation
        app_py = None
        requirements_txt = None
        package_json = None
        app_jsx = None
        
        for path, content in extracted_files.items():
            if 'app.py' in path:
                app_py = content
            elif 'requirements.txt' in path:
                requirements_txt = content
            elif 'package.json' in path:
                package_json = content
            elif 'App.jsx' in path:
                app_jsx = content
        
        # Run validation
        return validate_generated_code(
            app_py=app_py,
            requirements_txt=requirements_txt,
            package_json=package_json,
            app_jsx=app_jsx
        )
    
    def _extract_code_blocks(self, content: str) -> List[Tuple[str, str]]:
        """Extract code blocks from markdown-formatted content.
        
        Returns list of (language, code) tuples.
        """
        blocks = []
        pattern = re.compile(r'```(\w+)?\n(.*?)```', re.DOTALL)
        
        for match in pattern.finditer(content):
            language = match.group(1) or 'text'
            code = match.group(2).strip()
            
            if code and len(code) > 20:  # Minimum size
                blocks.append((language.lower(), code))
        
        return blocks
    
    def _determine_file_path(
        self,
        app_dir: Path,
        language: str,
        code: str,
        component: str
    ) -> Optional[Path]:
        """Determine where to save a code block.
        
        Simple, predictable logic:
        - Python -> backend/app.py or backend/main.py
        - JSX/JS -> frontend/src/App.jsx or frontend/src/main.jsx
        - HTML -> frontend/index.html
        - CSS -> frontend/src/App.css
        - JSON (package.json) -> frontend/package.json
        - Text (requirements) -> backend/requirements.txt
        """
        if component == 'backend':
            if language == 'python':
                if 'Flask' in code or 'app = Flask' in code:
                    return app_dir / 'backend' / 'app.py'
                else:
                    return app_dir / 'backend' / 'main.py'
            elif language == 'text' or 'requirements' in code.lower():
                return app_dir / 'backend' / 'requirements.txt'
                
        elif component == 'frontend':
            if language in ['jsx', 'javascript', 'js']:
                if 'export default' in code and ('App' in code or 'function' in code):
                    return app_dir / 'frontend' / 'src' / 'App.jsx'
                elif 'ReactDOM' in code or 'createRoot' in code:
                    return app_dir / 'frontend' / 'src' / 'main.jsx'
                else:
                    return app_dir / 'frontend' / 'src' / 'App.jsx'
            elif language == 'html':
                return app_dir / 'frontend' / 'index.html'
            elif language == 'css':
                return app_dir / 'frontend' / 'src' / 'App.css'
            elif language == 'json':
                if '"name"' in code and '"version"' in code:
                    return app_dir / 'frontend' / 'package.json'
        
        return None
    
    async def _load_template(self, template_id: int, component: str) -> Optional[str]:
        """Load template content from filesystem.
        
        Looks for: misc/app_templates/app_{N}_{component}_*.md
        """
        pattern = f"app_{template_id}_{component}_*.md"
        matches = list(APP_TEMPLATES_DIR.glob(pattern))
        
        if not matches:
            logger.warning(f"No template found for pattern: {pattern}")
            return None
        
        try:
            return matches[0].read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to load template {matches[0]}: {e}")
            return None
    
    def _build_prompt(self, template_content: str, component: str) -> str:
        """Build generation prompt from template."""
        return f"""Generate a complete {component} implementation based on this template:

{template_content}

Requirements:
- Generate COMPLETE, working code (no placeholders or TODOs)
- Wrap code in appropriate code blocks (```python, ```jsx, etc.)
- Include ALL necessary imports and dependencies
- Make it immediately runnable
- Follow modern best practices

Generate the {component} code now:"""
    
    def _get_system_prompt(self, component: str) -> str:
        """Get system prompt for AI generation."""
        if component == 'frontend':
            return """You are an expert frontend developer. Generate complete, production-ready React code.

Rules:
- Use React 18+ with functional components and hooks
- Include proper imports (React, ReactDOM)
- Generate COMPLETE files with NO placeholders
- Use modern JavaScript/JSX syntax
- Include proper error handling
- Write clean, readable code"""
        
        else:  # backend
            return """You are an expert backend developer. Generate complete, production-ready Flask code.

Rules:
- Use Flask with proper structure
- Include CORS configuration
- Generate COMPLETE files with NO placeholders
- Include all necessary imports
- Add proper error handling and logging
- Write clean, readable code
- Include requirements.txt with ALL dependencies"""


# Singleton instance
_service_instance = None

def get_simple_generation_service() -> SimpleGenerationService:
    """Get singleton instance of the simple generation service."""
    global _service_instance
    if _service_instance is None:
        _service_instance = SimpleGenerationService()
    return _service_instance
