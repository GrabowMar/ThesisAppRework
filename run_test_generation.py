"""
Test generation using the same logic as the web app
Simulates a generation request through the service layer
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def run_generation_test():
    """Run generation test using web app logic"""
    # Set environment to avoid starting Flask server
    os.environ['FLASK_SKIP_SERVER'] = '1'
    
    from app.factory import create_app
    from app.services.generation import GenerationService
    
    # Create app context (same as web app)
    app = create_app()
    
    with app.app_context():
        print("\n" + "="*80)
        print("GENERATION TEST - Using Web App Logic")
        print("="*80)
        
        # Test configuration
        models_to_test = [
            'anthropic_claude-4.5-haiku-20251001',
            # 'openai_gpt-4o-mini',  # Uncomment to test multiple models
        ]
        
        template = 'crud_todo_list'
        
        service = GenerationService()
        
        for model_slug in models_to_test:
            print(f"\n{'─'*80}")
            print(f"Model: {model_slug}")
            print(f"Template: {template}")
            print(f"App Number: 1")
            print(f"{'─'*80}\n")
            
            try:
                # This is exactly what the web app does
                print("⏳ Starting generation (this may take 30-60 seconds)...")
                result = await service.generate_full_app(
                    model_slug=model_slug,
                    app_num=1,
                    template_slug=template
                )
                
                if result:
                    print("\n✅ GENERATION SUCCESSFUL!")
                    print(f"\nGenerated app location:")
                    print(f"  generated/apps/{model_slug}/app1/")
                    
                    # Check what was generated
                    from pathlib import Path
                    app_dir = Path('generated/apps') / model_slug / 'app1'
                    
                    if app_dir.exists():
                        backend_app = app_dir / 'backend' / 'app.py'
                        frontend_app = app_dir / 'frontend' / 'src' / 'App.jsx'
                        
                        if backend_app.exists():
                            size = len(backend_app.read_text())
                            print(f"\n📄 Backend (app.py): {size} bytes")
                            
                            # Quick validation
                            content = backend_app.read_text()
                            has_db = 'db = SQLAlchemy()' in content
                            has_setup = 'def setup_app' in content
                            routes = content.count('@app.route')
                            
                            print(f"   ✓ Has db instance: {has_db}")
                            print(f"   ✓ Has setup_app: {has_setup}")
                            print(f"   ✓ Number of routes: {routes}")
                        
                        if frontend_app.exists():
                            size = len(frontend_app.read_text())
                            print(f"\n📄 Frontend (App.jsx): {size} bytes")
                            
                            # Quick validation
                            content = frontend_app.read_text()
                            has_react = 'import React' in content
                            has_axios = 'axios' in content
                            has_api_url = 'backend:5000' in content
                            has_export = 'export default' in content
                            
                            print(f"   ✓ Has React import: {has_react}")
                            print(f"   ✓ Uses axios: {has_axios}")
                            print(f"   ✓ Correct API URL: {has_api_url}")
                            print(f"   ✓ Has export: {has_export}")
                        
                        # Check docker-compose
                        docker_compose = app_dir / 'docker-compose.yml'
                        if docker_compose.exists():
                            print(f"\n🐳 Docker Compose: ✓ Present")
                        
                        print(f"\n💡 To start the app:")
                        print(f"   cd generated/apps/{model_slug}/app1")
                        print(f"   docker-compose up")
                    
                else:
                    print("\n❌ GENERATION FAILED")
                    print("Check logs above for details")
                    
            except Exception as e:
                print(f"\n❌ EXCEPTION DURING GENERATION:")
                print(f"   {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\n{'─'*80}\n")

if __name__ == '__main__':
    asyncio.run(run_generation_test())
