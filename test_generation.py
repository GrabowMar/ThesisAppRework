"""Quick test generation script for scaffolding validation."""
import asyncio
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.services.generation import GenerationService
from app.utils.slug_utils import normalize_model_slug

async def generate_test_apps():
    """Generate test apps with 3 different cheap models."""
    app = create_app()
    
    with app.app_context():
        gen_service = GenerationService()
        
        # Test models - different cheap/fast options (not previously tested)
        test_models = [
            "nvidia/llama-3.1-nemotron-70b-instruct",  # Nvidia Nemotron
            "cohere/command-r7b-12-2024",  # Cohere Command R7B
        ]
        
        # Use simple todo list requirement
        template_slug = "crud_todo_list"
        
        for model in test_models:
            model_slug = normalize_model_slug(model)
            print(f"\n{'='*60}")
            print(f"Generating with: {model} -> {model_slug}")
            print('='*60)
            
            try:
                # Get next available app number (look for max existing)
                from app.models.core import GeneratedApplication
                from sqlalchemy import func
                max_app = GeneratedApplication.query.filter_by(model_slug=model_slug).with_entities(func.max(GeneratedApplication.app_number)).scalar()
                app_num = (max_app or 0) + 1
                
                result = await gen_service.generate_full_app(
                    model_slug=model_slug,
                    app_num=app_num,
                    template_slug=template_slug,
                    generate_frontend=True,
                    generate_backend=True
                )
                
                if result.get('success'):
                    print(f"✓ Success: generated/{model_slug}/app{app_num}")
                else:
                    print(f"✗ Failed: {result.get('errors')}")
                    
            except Exception as e:
                print(f"✗ Error: {e}")
                import traceback
                traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(generate_test_apps())
