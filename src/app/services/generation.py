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

import json
import logging
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, List

import aiohttp

from app.paths import GENERATED_APPS_DIR, SCAFFOLDING_DIR, REQUIREMENTS_DIR

logger = logging.getLogger(__name__)


@dataclass
class GenerationConfig:
    """Configuration for code generation."""
    model_slug: str
    app_num: int
    template_id: int
    component: str  # 'frontend' or 'backend'
    temperature: float = 0.3
    max_tokens: int = 16000
    requirements: Optional[Dict] = None  # Requirements from JSON file


class ScaffoldingManager:
    """Manages scaffolding - the sacred Docker infrastructure."""
    
    def __init__(self):
        self.scaffolding_source = SCAFFOLDING_DIR / 'react-flask'
        self.base_backend_port = 5001
        self.base_frontend_port = 8001
    
    def get_ports(self, app_num: int) -> Tuple[int, int]:
        """Calculate ports for an app."""
        backend = self.base_backend_port + (app_num * 2)
        frontend = self.base_frontend_port + (app_num * 2)
        return backend, frontend
    
    def get_app_dir(self, model_slug: str, app_num: int) -> Path:
        """Get app directory path."""
        safe_model = re.sub(r'[^\w\-.]', '_', model_slug)
        return GENERATED_APPS_DIR / safe_model / f"app{app_num}"
    
    def scaffold(self, model_slug: str, app_num: int) -> bool:
        """Copy scaffolding to app directory.
        
        This creates the IMMUTABLE base structure that AI never touches.
        """
        app_dir = self.get_app_dir(model_slug, app_num)
        backend_port, frontend_port = self.get_ports(app_num)
        
        logger.info(f"Scaffolding {model_slug}/app{app_num} → {app_dir}")
        logger.info(f"Ports: backend={backend_port}, frontend={frontend_port}")
        
        if not self.scaffolding_source.exists():
            logger.error(f"Scaffolding source missing: {self.scaffolding_source}")
            return False
        
        # Create app directory
        app_dir.mkdir(parents=True, exist_ok=True)
        
        # Port substitutions
        subs = {
            'backend_port': str(backend_port),
            'frontend_port': str(frontend_port),
            'PROJECT_NAME': f"{model_slug.replace('/', '_')}_app{app_num}",
            'BACKEND_PORT': str(backend_port),
            'FRONTEND_PORT': str(frontend_port),
        }
        
        # Files to copy (EXACT list - no wildcards)
        files_to_copy = [
            'docker-compose.yml',
            '.env.example',
            'README.md',
            'backend/Dockerfile',
            'backend/.dockerignore',
            'backend/app.py',
            'backend/requirements.txt',
            'frontend/Dockerfile',
            'frontend/.dockerignore',
            'frontend/nginx.conf',
            'frontend/vite.config.js',
            'frontend/package.json',
            'frontend/index.html',
            'frontend/src/App.css',
            'frontend/src/App.jsx',
        ]
        
        copied = 0
        for rel_path in files_to_copy:
            src = self.scaffolding_source / rel_path
            dest = app_dir / rel_path
            
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
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.requirements_dir = REQUIREMENTS_DIR
        self.template_dir = SCAFFOLDING_DIR / 'templates'
        self.scaffolding_info_path = SCAFFOLDING_DIR / 'SCAFFOLDING_INFO.md'
    
    async def generate(self, config: GenerationConfig) -> Tuple[bool, str, str]:
        """Generate code for frontend or backend.
        
        Returns: (success, content, error_message)
        """
        # Build prompt
        prompt = self._build_prompt(config)
        
        # API request
        payload = {
            "model": config.model_slug,
            "messages": [
                {
                    "role": "system",
                    "content": self._get_system_prompt(config.component)
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": config.temperature,
            "max_tokens": config.max_tokens
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.api_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=300)
                ) as response:
                    if response.status != 200:
                        error = await response.text()
                        return False, "", f"API error {response.status}: {error}"
                    
                    data = await response.json()
                    content = data['choices'][0]['message']['content']
                    return True, content, ""
                    
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            return False, "", str(e)
    
    def _load_requirements(self, template_id: int) -> Optional[Dict]:
        """Load requirements from JSON file."""
        # Map template IDs to requirement files
        template_map = {
            1: 'todo_app.json',
            2: 'base64_converter.json',
            3: 'xsd_verifier.json'
        }
        
        filename = template_map.get(template_id)
        if not filename:
            logger.warning(f"No requirements file for template {template_id}")
            return None
        
        req_file = self.requirements_dir / filename
        if not req_file.exists():
            logger.warning(f"Requirements file not found: {req_file}")
            return None
        
        try:
            with open(req_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load requirements: {e}")
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
    
    def _load_prompt_template(self, component: str) -> str:
        """Load prompt template for component."""
        template_file = self.template_dir / f"{component}_prompt_template.md"
        
        if not template_file.exists():
            logger.warning(f"Template not found: {template_file}")
            return ""
        
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load template: {e}")
            return ""
    
    def _build_prompt(self, config: GenerationConfig) -> str:
        """Build generation prompt based on template + scaffolding + requirements."""
        # Load requirements if not already loaded
        if not config.requirements:
            config.requirements = self._load_requirements(config.template_id)
        
        reqs = config.requirements
        
        # Load scaffolding info and prompt template
        scaffolding_info = self._load_scaffolding_info()
        template = self._load_prompt_template(config.component)
        
        # If template exists, use it
        if template and reqs:
            app_name = reqs.get('name', 'Application')
            app_description = reqs.get('description', 'web application')
            
            if config.component == 'backend':
                req_list = '\n'.join([f"- {req}" for req in reqs.get('backend_requirements', [])])
            else:
                req_list = '\n'.join([f"- {req}" for req in reqs.get('frontend_requirements', [])])
            
            # Fill in template
            prompt = template.format(
                scaffolding_info=scaffolding_info,
                app_name=app_name,
                app_description=app_description,
                backend_requirements=req_list if config.component == 'backend' else '',
                frontend_requirements=req_list if config.component == 'frontend' else ''
            )
            
            logger.info(f"Built prompt using template: {len(prompt)} chars")
            return prompt
        
        # Fallback to old format if template/requirements not found
        logger.warning("Template or requirements not found, using fallback")
        
        if config.component == 'backend':
            if reqs and 'backend_requirements' in reqs:
                req_list = '\n'.join([f"- {req}" for req in reqs['backend_requirements']])
                app_desc = reqs.get('description', 'web application')
                app_name = reqs.get('name', 'Application')
                
                return f"""Generate Python Flask backend code for: {app_name}

Description: {app_desc}

BACKEND REQUIREMENTS:
{req_list}

IMPORTANT CONSTRAINTS:
- Generate ONLY the application code (routes, models, business logic)
- DO NOT generate Dockerfile, requirements.txt, or infrastructure files
- Use Flask best practices with proper error handling
- Use SQLAlchemy for database models where needed
- Include CORS configuration for frontend integration
- Add proper logging and validation
- Keep code clean, well-commented, and production-ready

Generate the complete Flask backend code:"""
            else:
                return """Generate Python code for a Flask backend API.

IMPORTANT: 
- Generate ONLY the application-specific code
- DO NOT generate Dockerfile, requirements.txt, or other infrastructure
- Focus on routes, models, business logic
- Keep it simple and working

Generate the Flask API code:"""
        
        else:  # frontend
            if reqs and 'frontend_requirements' in reqs:
                req_list = '\n'.join([f"- {req}" for req in reqs['frontend_requirements']])
                app_desc = reqs.get('description', 'web application')
                app_name = reqs.get('name', 'Application')
                
                return f"""Generate React frontend code for: {app_name}

Description: {app_desc}

FRONTEND REQUIREMENTS:
{req_list}

IMPORTANT CONSTRAINTS:
- Generate ONLY the App.jsx component code
- DO NOT generate index.html, package.json, vite.config.js, or infrastructure
- Use React hooks (useState, useEffect) for state management
- Use axios for API calls to backend
- Include proper error handling and loading states
- Add responsive design with clean, modern UI
- Keep code clean, well-commented, and production-ready

Generate the complete React App.jsx component:"""
            else:
                return """Generate React/JSX code for the frontend application.

IMPORTANT:
- Generate ONLY the App.jsx component code
- DO NOT generate index.html, package.json, vite.config, or other infrastructure
- Focus on the UI components and logic
- Keep it simple and working

Generate the React component code:"""
    
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
    """Merges AI-generated code with scaffolding."""
    
    def merge_backend(self, app_dir: Path, generated_content: str) -> bool:
        """Merge generated backend code with scaffolding app.py.
        
        Strategy:
        1. Keep scaffolding app.py structure
        2. Extract routes/models from generated code
        3. Add them to scaffolding
        """
        app_py = app_dir / 'backend' / 'app.py'
        
        if not app_py.exists():
            logger.error("Scaffolding app.py missing!")
            return False
        
        # Extract Python code blocks
        code_blocks = self._extract_code_blocks(generated_content, 'python')
        
        if not code_blocks:
            logger.warning("No Python code generated")
            return False
        
        # For now, just append the first code block
        # TODO: Smart merging
        base_content = app_py.read_text()
        generated_code = code_blocks[0]
        
        # Simple merge: add generated routes before if __name__
        if "if __name__" in base_content:
            parts = base_content.split("if __name__")
            merged = parts[0] + "\n\n# Generated Application Code\n" + generated_code + "\n\nif __name__" + parts[1]
        else:
            merged = base_content + "\n\n# Generated Application Code\n" + generated_code
        
        app_py.write_text(merged)
        logger.info("Merged backend code into app.py")
        return True
    
    def merge_frontend(self, app_dir: Path, generated_content: str) -> bool:
        """Merge generated frontend code with scaffolding App.jsx.
        
        Strategy:
        1. Keep scaffolding structure
        2. Replace App component with generated one
        """
        app_jsx = app_dir / 'frontend' / 'src' / 'App.jsx'
        
        if not app_jsx.exists():
            logger.error("Scaffolding App.jsx missing!")
            return False
        
        # Extract JSX code blocks
        code_blocks = self._extract_code_blocks(generated_content, 'jsx')
        
        if not code_blocks:
            logger.warning("No JSX code generated")
            return False
        
        # Replace App.jsx with generated code
        generated_code = code_blocks[0]
        
        # Ensure it has proper structure
        if 'import React' not in generated_code:
            generated_code = "import React from 'react';\n" + generated_code
        
        if 'export default' not in generated_code:
            generated_code += "\n\nexport default App;"
        
        app_jsx.write_text(generated_code)
        logger.info("Replaced App.jsx with generated code")
        return True
    
    def _extract_code_blocks(self, content: str, language: str) -> list[str]:
        """Extract code blocks of specific language."""
        pattern = re.compile(rf'```{language}\n(.*?)```', re.DOTALL)
        matches = pattern.findall(content)
        return [m.strip() for m in matches if m.strip()]


class GenerationService:
    """Main service orchestrating the generation process."""
    
    def __init__(self):
        self.scaffolding = ScaffoldingManager()
        self.generator = CodeGenerator()
        self.merger = CodeMerger()
    
    async def generate_full_app(
        self,
        model_slug: str,
        app_num: int,
        template_id: int,
        generate_frontend: bool = True,
        generate_backend: bool = True
    ) -> dict:
        """Generate complete application.
        
        Process:
        1. Scaffold (Docker infrastructure)
        2. Generate backend (if requested)
        3. Generate frontend (if requested)
        4. Merge generated code with scaffolding
        """
        result = {
            'success': False,
            'scaffolded': False,
            'backend_generated': False,
            'frontend_generated': False,
            'errors': []
        }
        
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
                template_id=template_id,
                component='backend'
            )
            
            success, content, error = await self.generator.generate(config)
            
            if success:
                if self.merger.merge_backend(app_dir, content):
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
                template_id=template_id,
                component='frontend'
            )
            
            success, content, error = await self.generator.generate(config)
            
            if success:
                if self.merger.merge_frontend(app_dir, content):
                    result['frontend_generated'] = True
                else:
                    result['errors'].append("Frontend merge failed")
            else:
                result['errors'].append(f"Frontend generation failed: {error}")
        
        # Overall success
        result['success'] = (
            result['scaffolded'] and
            (not generate_backend or result['backend_generated']) and
            (not generate_frontend or result['frontend_generated'])
        )
        
        result['app_dir'] = str(app_dir)
        backend_port, frontend_port = self.scaffolding.get_ports(app_num)
        result['backend_port'] = backend_port
        result['frontend_port'] = frontend_port
        
        logger.info(f"=== Generation complete: {result['success']} ===")
        return result


# Singleton
_service = None

def get_generation_service() -> GenerationService:
    """Get singleton instance."""
    global _service
    if _service is None:
        _service = GenerationService()
    return _service
