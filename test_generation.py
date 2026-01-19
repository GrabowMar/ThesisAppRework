#!/usr/bin/env python3
"""Test script for generation prompts - runs generation without Flask app."""
import asyncio
import json
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

# Set required environment
os.environ['DATABASE_URL'] = 'sqlite:////tmp/test.db'
os.environ['SECRET_KEY'] = 'test-key'


def test_prompt_generation():
    """Test that prompts are generated correctly."""
    from jinja2 import Environment, FileSystemLoader

    # Load a sample requirement
    req_path = Path('misc/requirements/crud_todo_list.json')
    with open(req_path) as f:
        requirements = json.load(f)

    print(f"Testing with: {requirements['name']}")
    print(f"Description: {requirements['description']}")

    # Load templates
    template_dir = Path('misc/templates/two-query')
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    # Format endpoints for template
    def format_endpoints(endpoints):
        lines = []
        for ep in endpoints:
            method = ep.get('method', 'GET')
            path = ep.get('path', '/')
            desc = ep.get('description', '')
            lines.append(f"- {method} {path}: {desc}")
        return '\n'.join(lines)

    # Render backend template
    backend_template = env.get_template('backend.md.jinja2')
    backend_prompt = backend_template.render(
        name=requirements['name'],
        description=requirements['description'],
        backend_requirements=requirements.get('backend_requirements', []),
        admin_requirements=requirements.get('admin_requirements', []),
        api_endpoints=format_endpoints(requirements.get('api_endpoints', [])),
        admin_api_endpoints=format_endpoints(requirements.get('admin_api_endpoints', [])),
        data_model=requirements.get('data_model', {}),
    )

    print("\n" + "="*60)
    print("BACKEND PROMPT:")
    print("="*60)
    print(backend_prompt[:2000] + "..." if len(backend_prompt) > 2000 else backend_prompt)

    # Render frontend template
    frontend_template = env.get_template('frontend.md.jinja2')
    frontend_prompt = frontend_template.render(
        name=requirements['name'],
        description=requirements['description'],
        frontend_requirements=requirements.get('frontend_requirements', []),
        admin_requirements=requirements.get('admin_requirements', []),
        backend_api_context="(Backend API endpoints from backend generation)",
    )

    print("\n" + "="*60)
    print("FRONTEND PROMPT:")
    print("="*60)
    print(frontend_prompt[:2000] + "..." if len(frontend_prompt) > 2000 else frontend_prompt)

    print("\n" + "="*60)
    print("PROMPT GENERATION SUCCESSFUL!")
    print("="*60)


def test_api_generation():
    """Test actual API generation if API key is available."""
    api_key = os.environ.get('OPENROUTER_API_KEY', '')
    if not api_key or api_key == 'your_openrouter_api_key_here':
        print("\nSkipping API test - OPENROUTER_API_KEY not set")
        return

    print("\n" + "="*60)
    print("TESTING API GENERATION...")
    print("="*60)

    from app.services.generation_v2.api_client import OpenRouterClient
    from app.services.generation_v2.code_generator import CodeGenerator

    # Test with a simple model
    async def run_test():
        generator = CodeGenerator()

        # Load requirements
        req_path = Path('misc/requirements/crud_todo_list.json')
        with open(req_path) as f:
            requirements = json.load(f)

        # Generate backend
        print("Generating backend...")
        backend_result = await generator.generate_backend(
            requirements=requirements,
            model='anthropic/claude-3-5-haiku',
        )

        if backend_result.get('success'):
            print("Backend generated successfully!")
            code = backend_result.get('code', '')
            print(f"Generated {len(code)} characters of code")
            print("\nFirst 500 chars:")
            print(code[:500])
        else:
            print(f"Backend generation failed: {backend_result.get('error')}")

    asyncio.run(run_test())


if __name__ == '__main__':
    test_prompt_generation()
    test_api_generation()
