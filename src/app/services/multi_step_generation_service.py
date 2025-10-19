"""Multi-Step Code Generation Service
=====================================

Generates code using a multi-prompt approach similar to Copilot:
1. Structure - Basic implementation
2. Enhancement - Add features and validation
3. Polish - Final touches and optimization

This approach produces more comprehensive code (200+ LOC) while working
better across different model capabilities.
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx  # Better async HTTP client for Windows (aiohttp has timeout issues)
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

from app.paths import MISC_DIR
from app.services.generation import get_generation_service

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class MultiStepRequest:
    """Request for multi-step code generation."""
    requirement_id: str  # e.g., "todo_api"
    model_slug: str
    app_num: int
    component: str  # "frontend" or "backend"
    temperature: float = 0.3
    max_tokens: int = 16000


@dataclass
class StepResult:
    """Result from a single generation step."""
    step_name: str
    success: bool
    content: str
    tokens_used: int = 0
    error: Optional[str] = None


class MultiStepGenerationService:
    """Multi-step code generation service."""
    
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY', '')
        self.api_url = "https://openrouter.ai/api/v1/chat/completions"
        self.requirements_dir = MISC_DIR / 'requirements' / 'simple'
        self.templates_dir = MISC_DIR / 'templates' / 'minimal'
        
        # Setup Jinja2
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=False
        )
        
    def load_requirement(self, requirement_id: str) -> Dict[str, Any]:
        """Load requirement specification."""
        req_file = self.requirements_dir / f"{requirement_id}.json"
        if not req_file.exists():
            raise FileNotFoundError(f"Requirement not found: {requirement_id}")
        
        with open(req_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def render_prompt(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a prompt template."""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)
    
    async def call_api(
        self,
        prompt: str,
        model_slug: str,
        temperature: float,
        max_tokens: int,
        previous_code: Optional[str] = None
    ) -> Tuple[bool, str, int, Optional[str]]:
        """Call OpenRouter API."""
        
        messages = []
        
        # Add system message
        messages.append({
            "role": "system",
            "content": "You are an expert full-stack developer. Generate clean, working code."
        })
        
        # Add previous code as context if enhancing
        if previous_code:
            messages.append({
                "role": "user",
                "content": "Here is the current code:\n\n```python\n" + previous_code + "\n```"
            })
        
        # Add the prompt
        messages.append({
            "role": "user",
            "content": prompt
        })
        
        payload = {
            "model": model_slug,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        try:
            # Use httpx instead of aiohttp - works better on Windows
            # Set 5-minute timeout for slower models (Grok, Claude, etc.)
            timeout = httpx.Timeout(300.0, read=120.0)
            
            logger.info(f"Calling {model_slug} API with timeout: total=300s, read=120s")
            
            async with httpx.AsyncClient(timeout=timeout) as client:
                logger.info(f"Client created, sending POST to {self.api_url}")
                response = await client.post(
                    self.api_url,
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"Got response status: {response.status_code}")
                if response.status_code != 200:
                    error_text = response.text
                    return False, "", 0, f"API error {response.status_code}: {error_text}"
                
                logger.info("Reading response JSON...")
                data = response.json()
                logger.info(f"Response received, {data.get('usage', {}).get('total_tokens', 0)} tokens")
                content = data['choices'][0]['message']['content']
                tokens = data.get('usage', {}).get('total_tokens', 0)
                
                return True, content, tokens, None
        
        except Exception as e:
            logger.error(f"API call failed: {e}")
            return False, "", 0, str(e)
    
    def extract_code_blocks(self, content: str) -> Dict[str, str]:
        """Extract code blocks from AI response.
        
        Takes the LONGEST code block for each file type to get the most complete version.
        """
        import re
        
        # Temporary storage for all blocks by type
        candidates = {
            'app.py': [],
            'requirements.txt': [],
            'src/main.jsx': [],
            'src/App.jsx': [],
            'src/App.css': [],
            'index.html': [],
            'package.json': []
        }
        
        # Find all code blocks with language
        pattern = r'```(\w+)\n(.*?)```'
        matches = re.finditer(pattern, content, re.DOTALL)
        
        for match in matches:
            lang = match.group(1)
            code = match.group(2).strip()
            
            # Skip empty or tiny blocks
            if len(code) < 50:
                continue
            
            # Categorize by language and content
            if lang == 'python':
                candidates['app.py'].append(code)
            elif lang in ['text', 'txt']:
                if 'flask' in code.lower() or 'sqlalchemy' in code.lower():
                    candidates['requirements.txt'].append(code)
            elif lang in ['javascript', 'jsx', 'js']:
                if 'ReactDOM' in code or 'createRoot' in code:
                    candidates['src/main.jsx'].append(code)
                elif 'export default' in code or 'function App' in code or 'const App' in code:
                    candidates['src/App.jsx'].append(code)
            elif lang == 'css':
                candidates['src/App.css'].append(code)
            elif lang == 'html':
                candidates['index.html'].append(code)
            elif lang == 'json':
                if '"dependencies"' in code or '"scripts"' in code:
                    candidates['package.json'].append(code)
        
        # Select the LONGEST block for each file type
        files = {}
        for filename, blocks in candidates.items():
            if blocks:
                # Sort by length and take the longest
                longest = max(blocks, key=len)
                files[filename] = longest
                logger.info(f"Selected {filename}: {len(longest)} chars ({len(longest.split(chr(10)))} lines)")
        
        return files
    
    def save_files(
        self,
        files: Dict[str, str],
        model_slug: str,
        app_num: int,
        component: str
    ) -> Tuple[bool, str]:
        """Save generated files to disk."""

        service = get_generation_service()
        app_dir = service.scaffolding.get_app_dir(model_slug, app_num)

        # Determine base directory (frontend or backend)
        base_dir = app_dir / component
        base_dir.mkdir(parents=True, exist_ok=True)
        
        saved_files = []
        
        try:
            for filename, content in files.items():
                file_path = base_dir / filename
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                saved_files.append(str(file_path))
                logger.info(f"Saved {file_path}")
            
            return True, f"Saved {len(saved_files)} files"
        
        except Exception as e:
            logger.error(f"Failed to save files: {e}")
            return False, str(e)
    
    async def generate_step(
        self,
        step_name: str,
        template_name: str,
        context: Dict[str, Any],
        request: MultiStepRequest,
        previous_code: Optional[str] = None
    ) -> StepResult:
        """Generate code for one step."""
        
        logger.info(f"Generating step: {step_name}")
        
        # Render prompt
        prompt = self.render_prompt(template_name, context)
        
        # Call API
        success, content, tokens, error = await self.call_api(
            prompt,
            request.model_slug,
            request.temperature,
            request.max_tokens,
            previous_code
        )
        
        if not success:
            return StepResult(
                step_name=step_name,
                success=False,
                content="",
                error=error
            )
        
        return StepResult(
            step_name=step_name,
            success=True,
            content=content,
            tokens_used=tokens
        )
    
    async def generate_multi_step(
        self,
        request: MultiStepRequest
    ) -> Tuple[bool, List[StepResult], str]:
        """Generate code using multi-step approach."""
        
        # Prepare scaffolding using the consolidated generation service
        service = get_generation_service()
        scaffolding = service.scaffolding

        app_dir = scaffolding.get_app_dir(request.model_slug, request.app_num)
        docker_compose_file = app_dir / 'docker-compose.yml'

        if not docker_compose_file.exists():
            scaffolding.scaffold(request.model_slug, request.app_num)
        
        # Load requirement
        try:
            requirement = self.load_requirement(request.requirement_id)
        except Exception as e:
            return False, [], str(e)
        
        # Context for templates
        context = requirement.copy()
        
        # Define steps
        steps = [
            ("structure", f"{request.component}_step1_structure.md.jinja2"),
            ("enhance", f"{request.component}_step2_enhance.md.jinja2"),
            ("polish", f"{request.component}_step3_polish.md.jinja2"),
        ]
        
        results = []
        previous_code = None
        
        # Execute each step
        for step_name, template_name in steps:
            result = await self.generate_step(
                step_name,
                template_name,
                context,
                request,
                previous_code
            )
            
            results.append(result)
            
            if not result.success:
                return False, results, f"Step {step_name} failed: {result.error}"
            
            # Extract main code file for context in next step
            files = self.extract_code_blocks(result.content)
            if request.component == 'backend' and 'app.py' in files:
                previous_code = files['app.py']
            elif request.component == 'frontend' and 'src/App.jsx' in files:
                previous_code = files['src/App.jsx']
        
        # Save final result
        final_files = self.extract_code_blocks(results[-1].content)
        success, msg = self.save_files(
            final_files,
            request.model_slug,
            request.app_num,
            request.component
        )
        
        if not success:
            return False, results, f"Failed to save files: {msg}"
        
        # Auto-fix dependencies for backend
        if request.component == 'backend':
            try:
                app_dir = scaffolding.get_app_dir(request.model_slug, request.app_num)
                self._fix_backend_dependencies(app_dir)
            except Exception as e:
                logger.warning(f"Failed to auto-fix dependencies: {e}")
        
        return True, results, "Generation completed successfully"
    
    def _fix_backend_dependencies(self, app_dir) -> None:
        """Auto-detect and fix missing dependencies in requirements.txt."""
        
        import importlib.util

        scripts_dir = Path(__file__).resolve().parents[3] / 'scripts'
        module_path = scripts_dir / 'fix_dependencies.py'

        if not module_path.exists():
            logger.debug("fix_dependencies.py not found; skipping dependency check")
            return

        try:
            spec = importlib.util.spec_from_file_location('fix_dependencies', module_path)
            if not spec or not spec.loader:  # pragma: no cover - defensive
                logger.debug("Unable to load fix_dependencies module spec")
                return
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
            fixer = getattr(module, 'fix_requirements_txt', None)
            if callable(fixer):
                result = fixer(app_dir)
                if not (isinstance(result, tuple) and len(result) == 2):
                    logger.debug("Dependency fixer returned unexpected result; skipping logging")
                    return
                success, message = result
                if success:
                    logger.info(f"Dependency check: {message}")
                else:
                    logger.warning(f"Dependency check failed: {message}")
        except Exception as e:
            logger.warning(f"Could not auto-fix dependencies: {e}")


def get_multi_step_service() -> MultiStepGenerationService:
    """Get multi-step generation service singleton."""
    if not hasattr(get_multi_step_service, '_instance'):
        get_multi_step_service._instance = MultiStepGenerationService()
    return get_multi_step_service._instance
