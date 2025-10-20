"""Test generation with agentica-org model to reproduce the error"""
import sys
import asyncio
sys.path.insert(0, 'src')

from app import create_app
from app.services.generation import get_generation_service

async def test_agentica_generation():
    """Test with the exact model that's failing in the UI"""
    app = create_app()
    with app.app_context():
        # Exact parameters from the screenshot
        model_slug = 'agentica-org_deepcoder-14b-preview'
        app_num = 1
        template_id = 1
        
        print(f"\n=== Testing Agentica Model Generation ===")
        print(f"Model Slug: {model_slug}")
        print(f"App Number: {app_num}")
        print(f"Template ID: {template_id}")
        
        # Verify model exists
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug=model_slug).first()
        if not model:
            print(f"❌ ERROR: Model '{model_slug}' not found in database!")
            return
        
        print("\n=== Model Info ===")
        print("Found in DB: YES")
        print(f"  canonical_slug: {model.canonical_slug}")
        print(f"  model_id: {model.model_id}")
        print(f"  provider: {model.provider}")
        
        # Run generation
        print(f"\n=== Running Generation ===")
        service = get_generation_service()
        result = await service.generate_full_app(
            model_slug=model_slug,
            app_num=app_num,
            template_id=template_id,
            generate_frontend=True,
            generate_backend=True
        )
        
        print(f"\n=== Generation Result ===")
        print(f"Success: {result['success']}")
        print(f"Scaffolded: {result.get('scaffolded', False)}")
        print(f"Backend Generated: {result.get('backend_generated', False)}")
        print(f"Frontend Generated: {result.get('frontend_generated', False)}")
        
        if result.get('errors'):
            print(f"\n❌ Errors:")
            for error in result['errors']:
                print(f"  - {error}")
        
        if result.get('success'):
            print(f"\n✅ App Directory: {result.get('app_dir')}")
            print(f"Backend Port: {result.get('backend_port')}")
            print(f"Frontend Port: {result.get('frontend_port')}")

if __name__ == '__main__':
    asyncio.run(test_agentica_generation())
