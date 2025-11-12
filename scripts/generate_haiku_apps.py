"""Script to generate additional Claude Haiku applications for analysis."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.services.generation import get_generation_service

async def main():
    """Generate 3 additional Claude Haiku apps (apps 2, 3, 4)."""
    app = create_app()
    
    with app.app_context():
        service = get_generation_service()
        model_slug = "anthropic_claude-4.5-haiku-20251001"
        template_slug = "crud_todo_list"  # Use same template as app1
        
        print(f"Generating 3 apps for {model_slug}...")
        print("=" * 60)
        
        for app_num in [2, 3, 4]:
            print(f"\n[APP {app_num}] Starting generation...")
            
            try:
                result = await service.generate_full_app(
                    model_slug=model_slug,
                    app_num=app_num,
                    template_slug=template_slug,
                    generate_frontend=True,
                    generate_backend=True,
                    template_type='auto'
                )
                
                if result['success']:
                    print(f"[APP {app_num}] ✓ SUCCESS")
                    print(f"  - Scaffolded: {result['scaffolded']}")
                    print(f"  - Backend: {result['backend_generated']}")
                    print(f"  - Frontend: {result['frontend_generated']}")
                    print(f"  - Directory: {result.get('app_dir', 'N/A')}")
                else:
                    print(f"[APP {app_num}] ✗ FAILED")
                    for error in result.get('errors', []):
                        print(f"  - Error: {error}")
                        
            except Exception as e:
                print(f"[APP {app_num}] ✗ EXCEPTION: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 60)
        print("Generation complete!")

if __name__ == '__main__':
    asyncio.run(main())
