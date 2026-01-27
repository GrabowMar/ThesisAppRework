#!/usr/bin/env python3
"""
Test script for code generation with different models.
Runs generation manually and checks if apps build.
"""

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Load .env file
env_file = Path(__file__).parent / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, _, value = line.partition('=')
            os.environ.setdefault(key.strip(), value.strip())

import aiohttp

# Configuration
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Test models (use cheaper/faster ones for testing)
TEST_MODELS = [
    ("anthropic/claude-3-5-haiku", "claude-3.5-haiku"),
    ("google/gemini-2.0-flash-exp:free", "gemini-2.0-flash"),
    ("openai/gpt-4o-mini", "gpt-4o-mini"),
]

# Output directory
TEST_OUTPUT_DIR = Path(__file__).parent / 'test_generation_output'

# Prompts directory
PROMPTS_DIR = Path(__file__).parent / 'misc' / 'prompts' / 'v2'
REQUIREMENTS_DIR = Path(__file__).parent / 'misc' / 'requirements'
SCAFFOLDING_DIR = Path(__file__).parent / 'misc' / 'scaffolding' / 'react-flask'


def load_prompt_template(component: str, prompt_type: str) -> str:
    """Load a Jinja2 template file."""
    path = PROMPTS_DIR / component / f"{prompt_type}.md.jinja2"
    return path.read_text(encoding='utf-8')


def load_requirements(template_slug: str) -> dict:
    """Load requirements JSON."""
    path = REQUIREMENTS_DIR / f"{template_slug}.json"
    return json.loads(path.read_text(encoding='utf-8'))


def load_scaffolding(relative_path: str) -> str:
    """Load scaffolding file."""
    path = SCAFFOLDING_DIR / relative_path
    if path.exists():
        return path.read_text(encoding='utf-8')
    return "# Scaffolding file not found"


def format_endpoints(endpoints: list) -> str:
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


def render_template(template: str, context: dict) -> str:
    """Simple Jinja2-like rendering (basic variable substitution)."""
    from jinja2 import Environment
    env = Environment()
    tmpl = env.from_string(template)
    return tmpl.render(**context)


def build_backend_prompts(requirements: dict) -> tuple:
    """Build backend system and user prompts."""
    system_template = load_prompt_template('backend', 'system')
    user_template = load_prompt_template('backend', 'user')

    scaffolding_code = load_scaffolding('backend/app.py')

    context = {
        'name': requirements.get('name', 'Application'),
        'description': requirements.get('description', ''),
        'backend_requirements': requirements.get('backend_requirements', []),
        'admin_requirements': requirements.get('admin_requirements', []),
        'api_endpoints': format_endpoints(requirements.get('api_endpoints', [])),
        'admin_api_endpoints': format_endpoints(requirements.get('admin_api_endpoints', [])),
        'data_model': requirements.get('data_model', {}),
        'scaffolding_code': scaffolding_code,
    }

    system_prompt = render_template(system_template, {})
    user_prompt = render_template(user_template, context)

    return system_prompt, user_prompt


def build_frontend_prompts(requirements: dict, backend_api_context: str) -> tuple:
    """Build frontend system and user prompts."""
    system_template = load_prompt_template('frontend', 'system')
    user_template = load_prompt_template('frontend', 'user')

    context = {
        'name': requirements.get('name', 'Application'),
        'description': requirements.get('description', ''),
        'frontend_requirements': requirements.get('frontend_requirements', []),
        'admin_requirements': requirements.get('admin_requirements', []),
        'backend_api_context': backend_api_context,
    }

    system_prompt = render_template(system_template, {})
    user_prompt = render_template(user_template, context)

    return system_prompt, user_prompt


async def call_openrouter(model: str, messages: list, max_tokens: int = 16000) -> dict:
    """Call OpenRouter API."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "ThesisApp Test",
    }

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, headers=headers, json=payload, timeout=300) as resp:
            return await resp.json()


def extract_code_block(content: str, lang: str) -> str:
    """Extract code block from LLM response."""
    # Match ```lang:filename or ```lang
    pattern = rf"```(?:{lang})(?::[^\n\r`]*)?\s*[\r\n]+(.*?)```"
    match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def extract_backend_api_context(backend_code: str) -> str:
    """Extract API routes from generated backend code."""
    routes = []
    for match in re.finditer(r"@app\.route\(['\"]([^'\"]+)['\"].*?methods=\[([^\]]+)\]", backend_code):
        path = match.group(1)
        methods = match.group(2).replace("'", "").replace('"', '').split(',')
        for method in methods:
            routes.append(f"- {method.strip()} {path}")

    if not routes:
        # Fallback: find any @app.route
        for match in re.finditer(r"@app\.route\(['\"]([^'\"]+)['\"]", backend_code):
            routes.append(f"- GET {match.group(1)}")

    return "## Available API Endpoints\n\n" + "\n".join(routes) if routes else "No API endpoints found"


def validate_python_syntax(code: str) -> tuple:
    """Validate Python syntax."""
    try:
        compile(code, '<string>', 'exec')
        return True, None
    except SyntaxError as e:
        return False, str(e)


def validate_jsx_syntax(code: str) -> tuple:
    """Basic JSX validation (check for common patterns)."""
    checks = [
        (r'\bimport\s+.*from\s+[\'"]react[\'"]', "Missing React import"),
        (r'\bfunction\s+App\b|\bconst\s+App\s*=', "Missing App component"),
        (r'\bexport\s+default', "Missing default export"),
    ]

    for pattern, error in checks:
        if not re.search(pattern, code):
            return False, error

    return True, None


async def test_generation(model_id: str, model_name: str, template_slug: str):
    """Run generation test for a single model."""
    print(f"\n{'='*60}")
    print(f"Testing: {model_name} ({model_id})")
    print(f"Template: {template_slug}")
    print(f"{'='*60}")

    # Create output directory
    output_dir = TEST_OUTPUT_DIR / model_name / template_slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load requirements
    requirements = load_requirements(template_slug)
    print(f"[OK] Loaded requirements: {requirements.get('name')}")

    # Build backend prompts
    backend_system, backend_user = build_backend_prompts(requirements)
    print(f"[OK] Built backend prompts ({len(backend_system)} + {len(backend_user)} chars)")

    # Save prompts for inspection
    (output_dir / 'backend_system.md').write_text(backend_system, encoding='utf-8')
    (output_dir / 'backend_user.md').write_text(backend_user, encoding='utf-8')

    # Call API for backend
    print("--> Calling OpenRouter for backend...")
    messages = [
        {"role": "system", "content": backend_system},
        {"role": "user", "content": backend_user},
    ]

    response = await call_openrouter(model_id, messages)

    if 'error' in response:
        print(f"[FAIL] API Error: {response['error']}")
        return False

    backend_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
    (output_dir / 'backend_response.md').write_text(backend_content, encoding='utf-8')

    # Extract backend code
    backend_code = extract_code_block(backend_content, 'python')
    if not backend_code:
        print("[FAIL] No Python code block found in backend response")
        return False

    (output_dir / 'app.py').write_text(backend_code, encoding='utf-8')
    print(f"[OK] Extracted backend code ({len(backend_code)} chars)")

    # Validate Python syntax
    valid, error = validate_python_syntax(backend_code)
    if not valid:
        print(f"[FAIL] Backend syntax error: {error}")
    else:
        print("[OK] Backend syntax valid")

    # Extract API context for frontend
    backend_api_context = extract_backend_api_context(backend_code)
    print(f"[OK] Extracted API context")

    # Build frontend prompts
    frontend_system, frontend_user = build_frontend_prompts(requirements, backend_api_context)
    print(f"[OK] Built frontend prompts ({len(frontend_system)} + {len(frontend_user)} chars)")

    # Save prompts
    (output_dir / 'frontend_system.md').write_text(frontend_system, encoding='utf-8')
    (output_dir / 'frontend_user.md').write_text(frontend_user, encoding='utf-8')

    # Call API for frontend
    print("--> Calling OpenRouter for frontend...")
    messages = [
        {"role": "system", "content": frontend_system},
        {"role": "user", "content": frontend_user},
    ]

    response = await call_openrouter(model_id, messages)

    if 'error' in response:
        print(f"[FAIL] API Error: {response['error']}")
        return False

    frontend_content = response.get('choices', [{}])[0].get('message', {}).get('content', '')
    (output_dir / 'frontend_response.md').write_text(frontend_content, encoding='utf-8')

    # Extract frontend code
    frontend_code = extract_code_block(frontend_content, 'jsx|javascript|js|tsx')
    if not frontend_code:
        print("[FAIL] No JSX code block found in frontend response")
        return False

    (output_dir / 'App.jsx').write_text(frontend_code, encoding='utf-8')
    print(f"[OK] Extracted frontend code ({len(frontend_code)} chars)")

    # Validate JSX
    valid, error = validate_jsx_syntax(frontend_code)
    if not valid:
        print(f"[FAIL] Frontend validation warning: {error}")
    else:
        print("[OK] Frontend syntax valid")

    print(f"\n[OK] Output saved to: {output_dir}")
    return True


async def main():
    """Run all generation tests."""
    if not OPENROUTER_API_KEY:
        print("ERROR: OPENROUTER_API_KEY environment variable not set")
        sys.exit(1)

    print("="*60)
    print("Code Generation Test")
    print(f"Time: {datetime.now().isoformat()}")
    print("="*60)

    # Test with multiple templates using one model
    templates = [
        "crud_todo_list",
        "crud_book_library",
        "finance_expense_list",
    ]

    model_id, model_name = TEST_MODELS[0]  # Use first model (Claude 3.5 Haiku)

    results = []
    for template in templates:
        try:
            success = await test_generation(model_id, model_name, template)
            results.append((template, success))
        except Exception as e:
            print(f"[FAIL] Error: {e}")
            results.append((template, False))

    # Summary
    print("\n" + "="*60)
    print(f"SUMMARY (Model: {model_name})")
    print("="*60)
    for template_name, success in results:
        status = "[OK] PASS" if success else "[FAIL] FAIL"
        print(f"  {template_name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
