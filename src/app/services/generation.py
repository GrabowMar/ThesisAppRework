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

import hashlib
import json
import logging
import os
import re
import shutil
import textwrap
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple, Dict, List, Set, Any

import aiohttp

from app.paths import GENERATED_APPS_DIR, SCAFFOLDING_DIR, REQUIREMENTS_DIR
from app.services.port_allocation_service import get_port_allocation_service

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
            logger.warning(
                "Falling back to deterministic port allocation for %s/app%s: %s",
                model_slug,
                app_num,
                exc,
            )
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
            'frontend/src/main.jsx',
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
        
        # Get the actual OpenRouter model ID from the database
        # canonical_slug is like: anthropic_claude-4.5-haiku-20251001
        # model_id is like: anthropic/claude-haiku-4.5 (what OpenRouter expects)
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug=config.model_slug).first()
        if not model:
            logger.error(f"Model not found in database: {config.model_slug}")
            return False, "", f"Model not found in database: {config.model_slug}"
        
        openrouter_model = model.model_id
        logger.info(f"Using OpenRouter model: {openrouter_model} (from slug: {config.model_slug})")
        
        # API request
        payload = {
            "model": openrouter_model,
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

    def __init__(self):
        self._backend_scaffold_sections: Optional[Tuple[str, str]] = None
    
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
        
        selected_code = self._select_code_block(
            generated_content,
            preferred_languages={'python', 'py', 'python3'}
        )

        if not selected_code:
            logger.warning("No Python code detected in generation response")
            return False

        selected_code = self._strip_existing_scaffold(selected_code)

        scaffold_head, scaffold_tail = self._get_backend_scaffold_sections()
        sanitized = self._sanitize_backend_code(selected_code)

        merged_parts = [scaffold_head.rstrip(), "# === AI Generated Backend Code ===", sanitized.rstrip()]
        if scaffold_tail:
            merged_parts.append(scaffold_tail.lstrip())

        merged_content = '\n\n'.join(part for part in merged_parts if part)

        if not merged_content.endswith('\n'):
            merged_content += '\n'

        app_py.write_text(merged_content, encoding='utf-8')
        logger.info("Merged backend app.py with scaffolding")
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
        
        selected_code = self._select_code_block(
            generated_content,
            preferred_languages={'jsx', 'javascript', 'js', 'tsx', 'typescript', 'ts'}
        )

        if not selected_code:
            logger.warning("No frontend code detected in generation response")
            return False

        # Basic guardrails to keep React structure usable
        if 'import React' not in selected_code:
            selected_code = "import React from 'react';\n" + selected_code
        if 'ReactDOM' in selected_code and 'import ReactDOM' not in selected_code:
            selected_code = "import ReactDOM from 'react-dom/client';\n" + selected_code
        if 'ReactDOM.createRoot' in selected_code and 'document.getElementById' not in selected_code:
            selected_code += (
                "\n\nconst root = ReactDOM.createRoot(document.getElementById('root'));"
                "\nroot.render(<App />);"
            )
        if 'export default' not in selected_code:
            selected_code += "\n\nexport default App;"

        if not selected_code.endswith('\n'):
            selected_code += '\n'

        app_jsx.write_text(selected_code, encoding='utf-8')
        logger.info("Replaced App.jsx with generated code")

        main_jsx = app_dir / 'frontend' / 'src' / 'main.jsx'
        if not main_jsx.exists():
            scaffold_main = SCAFFOLDING_DIR / 'react-flask' / 'frontend' / 'src' / 'main.jsx'
            try:
                if scaffold_main.exists():
                    main_jsx.write_text(scaffold_main.read_text(encoding='utf-8'), encoding='utf-8')
                    logger.info("Restored missing main.jsx from scaffolding")
                else:
                    fallback = (
                        "import React from 'react';\n"
                        "import ReactDOM from 'react-dom/client';\n"
                        "import App from './App.jsx';\n"
                        "import './App.css';\n\n"
                        "const root = ReactDOM.createRoot(document.getElementById('root'));\n"
                        "root.render(<App />);\n"
                    )
                    main_jsx.write_text(fallback, encoding='utf-8')
                    logger.info("Created fallback main.jsx entrypoint")
            except Exception as exc:
                logger.warning("Failed to backfill main.jsx: %s", exc)
        return True
    
    def _select_code_block(self, content: str, preferred_languages: Set[str]) -> Optional[str]:
        """Pick the first code block that matches preferred languages.

        Falls back to the first available block or the raw content if necessary.
        """
        blocks = []
        pattern = re.compile(r"```(?P<lang>[^\n\r`]+)?\s*[\r\n]+(.*?)```", re.DOTALL)

        for match in pattern.finditer(content or ""):
            lang = (match.group('lang') or 'text').strip().lower()
            lang = lang.replace('language-', '')
            code = (match.group(2) or '').strip()
            if code:
                blocks.append((lang, code))

        if not blocks and content and content.strip():
            blocks.append(('text', content.strip()))

        if not blocks:
            return None

        # Try preferred languages first
        for lang, code in blocks:
            if lang in preferred_languages:
                return code

        # Accept close variants (e.g. python fenced as ``````)
        for lang, code in blocks:
            if any(lang.startswith(pref) for pref in preferred_languages):
                return code

        # Fallback to first available block
        return blocks[0][1]

    def _get_backend_scaffold_sections(self) -> Tuple[str, str]:
        """Load and cache scaffold header/tail sections for backend app.py."""
        if self._backend_scaffold_sections is not None:
            return self._backend_scaffold_sections

        header = textwrap.dedent(
            '''
            # This file will be replaced by AI-generated code
            # DO NOT modify this file - it's just a placeholder for scaffolding

            import os
            import logging
            from flask import Flask, jsonify
            from flask_cors import CORS

            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            logger = logging.getLogger(__name__)

            app = Flask(__name__)
            CORS(app)

            app.config.setdefault('SQLALCHEMY_DATABASE_URI', os.environ.get('DATABASE_URL', 'sqlite:///app.db'))
            app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)

            def _scaffold_index():
                """Fallback index endpoint if AI code does not define one."""
                return jsonify({
                    'message': 'AI-Generated Application API',
                    'status': 'running',
                    'version': '1.0.0',
                    'endpoints': {
                        '/': 'API information',
                        '/health': 'Health check endpoint'
                    }
                })

            def _scaffold_health():
                """Fallback health endpoint used by Docker health checks."""
                return jsonify({'status': 'healthy', 'service': 'backend'}), 200

            def _register_scaffold_routes():
                """Register fallback routes only if they are missing."""
                try:
                    existing = {rule.rule for rule in app.url_map.iter_rules()}
                except Exception:
                    existing = set()

                added = []
                if '/' not in existing:
                    app.add_url_rule('/', 'scaffold_index', _scaffold_index)
                    added.append('/')
                if '/health' not in existing:
                    app.add_url_rule('/health', 'scaffold_health', _scaffold_health)
                    added.append('/health')

                if added:
                    logger.info('Registered scaffold fallback routes: %s', ', '.join(added))

            @app.errorhandler(404)
            def _scaffold_not_found(error):
                """Handle 404 errors with JSON response."""
                return jsonify({'error': 'Not found', 'message': 'The requested endpoint does not exist'}), 404

            @app.errorhandler(500)
            def _scaffold_internal_error(error):
                """Handle internal errors uniformly."""
                logger.error('Internal error: %s', error)
                return jsonify({'error': 'Internal server error', 'message': 'An unexpected error occurred'}), 500
            '''
        ).strip()

        tail = textwrap.dedent(
            '''
            if __name__ == '__main__':
                port = int(os.environ.get('FLASK_RUN_PORT', os.environ.get('PORT', 5000)))
                debug = os.environ.get('FLASK_ENV', 'production') == 'development'

                logger.info('Starting Flask application on port %s', port)
                logger.info('Debug mode: %s', debug)

                if 'setup_app' in globals():
                    try:
                        setup_app(app)
                        logger.info('Applied setup_app configuration')
                    except Exception as exc:
                        logger.error('Failed to configure Flask app: %s', exc)
                        raise
                else:
                    logger.debug('setup_app not defined; skipping setup integration')

                try:
                    _register_scaffold_routes()
                except Exception as exc:
                    logger.error('Failed to register scaffold fallback routes: %s', exc)
                    raise

                try:
                    app.run(host='0.0.0.0', port=port, debug=debug)
                except Exception as exc:
                    logger.error('Failed to start Flask application: %s', exc)
                    raise
            '''
        ).strip()

        self._backend_scaffold_sections = (header, tail)
        return self._backend_scaffold_sections

    def _sanitize_backend_code(self, code: str) -> str:
        """Strip duplicate bootstrap code from generated backend snippet."""
        lines = (code or "").splitlines()
        cleaned: List[str] = []
        skip_block = False
        block_indent = 0

        for line in lines:
            stripped = line.strip()

            if skip_block:
                if not stripped:
                    continue
                indent = len(line) - len(line.lstrip(' '))
                if indent <= block_indent:
                    skip_block = False
                else:
                    continue

            if stripped.startswith("if __name__ == '__main__':") or stripped.startswith('if __name__ == "__main__":'):
                skip_block = True
                block_indent = len(line) - len(line.lstrip(' '))
                continue

            if stripped.startswith('app = Flask(') or stripped.startswith('application = Flask('):
                continue

            if stripped.startswith('app = create_app('):
                continue

            if stripped.startswith('CORS(') and 'app' in stripped:
                continue

            cleaned.append(line)

        cleaned_code = '\n'.join(cleaned).strip()
        if cleaned_code:
            cleaned_code += '\n'
        return cleaned_code

    def _strip_existing_scaffold(self, code: str) -> str:
        """Remove scaffold markup if we're re-merging an existing file."""
        if not code:
            return code

        marker = '# === AI Generated Backend Code ==='
        if marker in code:
            code = code.split(marker)[-1]

        tail_markers = ["if __name__ == '__main__':", 'if __name__ == "__main__":']
        for tail_marker in tail_markers:
            idx = code.rfind(tail_marker)
            if idx != -1:
                code = code[:idx]

        return code.strip()


class GenerationService:
    """Main service orchestrating the generation process."""
    
    def __init__(self):
        self.scaffolding = ScaffoldingManager()
        self.generator = CodeGenerator()
        self.merger = CodeMerger()
        self.max_concurrent = int(os.getenv('GENERATION_MAX_CONCURRENT', os.getenv('SIMPLE_GENERATION_MAX_CONCURRENT', '4')))

    def get_template_catalog(self) -> List[Dict[str, Any]]:
        """Return available generation templates with metadata."""
        catalog: List[Dict[str, Any]] = []

        if not REQUIREMENTS_DIR.exists():
            logger.debug("Requirements directory missing: %s", REQUIREMENTS_DIR)
            return catalog

        for req_file in sorted(REQUIREMENTS_DIR.glob('*.json')):
            try:
                data = json.loads(req_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid requirements file %s: %s", req_file.name, exc)
                continue
            except OSError as exc:
                logger.warning("Failed to read requirements file %s: %s", req_file.name, exc)
                continue

            template_id = (
                data.get('app_id')
                or data.get('id')
                or data.get('template_id')
                or req_file.stem
            )
            name = data.get('name') or req_file.stem
            description = data.get('description', '')
            category = data.get('category') or data.get('domain') or 'general'
            complexity = data.get('complexity') or data.get('difficulty') or 'medium'

            features = data.get('features') or data.get('key_features') or []
            if isinstance(features, str):
                features = [features]

            tech_stack = data.get('tech_stack') or data.get('stack') or {}
            if not isinstance(tech_stack, dict):
                tech_stack = {'value': tech_stack}

            catalog.append({
                'id': template_id,
                'name': name,
                'description': description,
                'category': category,
                'complexity': complexity,
                'features': features,
                'tech_stack': tech_stack,
                'filename': req_file.name,
            })

        return catalog
    
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
        backend_port, frontend_port = self.scaffolding.get_ports(model_slug, app_num)
        result['backend_port'] = backend_port
        result['frontend_port'] = frontend_port
        
        logger.info(f"=== Generation complete: {result['success']} ===")
        return result

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
                status['in_flight_keys'] = [
                    f"{app.model_slug}/app{app.app_number}"
                    for app in recent
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
