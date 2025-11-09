"""
Quick test to verify template fixes work.
Regenerates one app with fixed templates to confirm API_URL is correct.
"""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, 'src')

from app import create_app
from app.services.generation import GenerationService

async def test_template_fix():
    """Test that fixed templates generate correct API_URL."""
    app = create_app()
    
    with app.app_context():
        service = GenerationService()
        
        print("="*60)
        print("Testing Template Fix")
        print("="*60)
        print("\nGenerating test app with FIXED templates...")
        print("Model: openai_gpt-3.5-turbo")
        print("Template: crud_todo_list")
        print("Expected: API_URL = '' (empty string)")
        print("="*60 + "\n")
        
        result = await service.generate_full_app(
            model_slug='openai_gpt-3.5-turbo',
            app_num=99,  # Test app number
            template_slug='crud_todo_list',
            generate_frontend=True,
            generate_backend=False  # Only test frontend
        )
        
        if result.get('success'):
            print(f"✅ Generation succeeded")
            
            # Check generated App.jsx
            app_jsx = Path("generated/apps/openai_gpt-3.5-turbo/app99/frontend/src/App.jsx")
            if app_jsx.exists():
                content = app_jsx.read_text()
                
                print("\n" + "="*60)
                print("Checking Generated App.jsx")
                print("="*60)
                
                # Look for API_URL definition
                for line in content.split('\n')[:30]:  # Check first 30 lines
                    if 'API_URL' in line and '=' in line:
                        print(f"\nFound: {line.strip()}")
                        
                        if "API_URL = ''" in line or 'API_URL = ""' in line:
                            print("✅ CORRECT: Uses empty string (relative URLs)")
                            print("\n🎉 Template fix verified successfully!")
                            return True
                        elif 'backend:5000' in line or 'backend:' in line:
                            print("❌ INCORRECT: Still using backend:5000")
                            print("❌ Template fix did not work properly")
                            return False
                        else:
                            print(f"⚠️  Unexpected API_URL format")
                            return False
                
                print("\n⚠️  Could not find API_URL definition in first 30 lines")
                print("Full content preview:")
                print(content[:500])
                return False
            else:
                print(f"❌ App.jsx not found at {app_jsx}")
                return False
        else:
            print(f"❌ Generation failed: {result.get('error')}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_template_fix())
    sys.exit(0 if success else 1)
