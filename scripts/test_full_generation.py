"""Test full generation flow from wizard to OpenRouter"""
import sys
import asyncio
import json
sys.path.insert(0, 'src')

from app import create_app
from app.services.generation import get_generation_service

async def test_full_generation():
    """Simulate exact wizard flow"""
    app = create_app()
    with app.app_context():
        # These are the exact values the wizard sends
        model_slug = 'x-ai_grok-code-fast-1'  # canonical_slug with underscore
        app_num = 1
        template_id = 1
        
        print("\n=== Testing Full Generation Flow ===")
        print(f"Model Slug (from wizard): {model_slug}")
        print(f"App Number: {app_num}")
        print(f"Template ID: {template_id}")
        
        # Run generation (exactly as the API endpoint does)
        service = get_generation_service()
        result = await service.generate_full_app(
            model_slug=model_slug,
            app_num=app_num,
            template_id=template_id,
            generate_frontend=True,
            generate_backend=True
        )
        
        print("\n=== Generation Result ===")
        print(f"Success: {result['success']}")
        print(f"Scaffolded: {result.get('scaffolded', False)}")
        print(f"Backend Generated: {result.get('backend_generated', False)}")
        print(f"Frontend Generated: {result.get('frontend_generated', False)}")
        print(f"Errors: {result.get('errors', [])}")
        
        if result.get('app_dir'):
            print(f"App Directory: {result['app_dir']}")
            print(f"Backend Port: {result.get('backend_port')}")
            print(f"Frontend Port: {result.get('frontend_port')}")

if __name__ == '__main__':
    asyncio.run(test_full_generation())
