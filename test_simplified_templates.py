"""Test generation with simplified templates"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

async def test_simplified():
    from app.factory import create_app
    from app.services.generation import get_generation_service
    
    print("Testing simplified templates with GPT-4o-mini...")
    print("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        service = get_generation_service()
        
        result = await service.generate_full_app(
            model_slug='openai_gpt-4o-mini',
            app_num=7,
            template_slug='crud_todo_list',
            generate_backend=True,
            generate_frontend=True
        )
        
        print(f"\nGeneration result: {result['success']}")
        print(f"Backend generated: {result.get('backend_generated', False)}")
        print(f"Frontend generated: {result.get('frontend_generated', False)}")
        
        if result.get('errors'):
            print(f"Errors: {result['errors']}")
        
        # Check file sizes
        app_dir = service.scaffolding.get_app_dir('openai_gpt-4o-mini', 7)
        backend_file = app_dir / 'backend' / 'app.py'
        frontend_file = app_dir / 'frontend' / 'src' / 'App.jsx'
        
        if backend_file.exists():
            content = backend_file.read_text()
            lines = len(content.splitlines())
            print(f"\nBackend: {len(content)} bytes, {lines} lines")
            
            # Check for critical components
            has_db = 'db = SQLAlchemy()' in content
            has_setup = 'def setup_app' in content
            routes = content.count('@app.route')
            print(f"  Has db instance: {has_db}")
            print(f"  Has setup_app: {has_setup}")
            print(f"  Routes: {routes}")
        
        if frontend_file.exists():
            content = frontend_file.read_text()
            lines = len(content.splitlines())
            print(f"\nFrontend: {len(content)} bytes, {lines} lines")
            
            # Check for critical components
            has_react = 'import React' in content
            has_axios = 'import axios' in content
            has_api_url = "API_URL = 'http://backend:5000'" in content
            print(f"  React import: {has_react}")
            print(f"  Axios import: {has_axios}")
            print(f"  Correct API_URL: {has_api_url}")

if __name__ == '__main__':
    asyncio.run(test_simplified())
