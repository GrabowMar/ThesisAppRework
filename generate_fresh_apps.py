"""
Generate fresh test apps to validate fuckup-proof requirements.
Tests with 2 weak models + 1 strong model.
"""
import sys
import shutil
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, 'src')

from app import create_app
from app.services.generation import GenerationService, GenerationConfig

def clean_old_apps():
    """Remove all existing generated apps."""
    apps_dir = Path("generated/apps")
    if apps_dir.exists():
        print(f"Cleaning {apps_dir}...")
        for item in apps_dir.iterdir():
            if item.is_dir():
                print(f"  Removing {item.name}...")
                shutil.rmtree(item, ignore_errors=True)
        print("Old apps removed\n")
    else:
        print(f"{apps_dir} doesn't exist, nothing to clean\n")

def generate_test_apps():
    """Generate 3 fresh apps with fuckup-proof requirements."""
    app = create_app()
    
    # Test models: 2 weak, 1 strong
    test_cases = [
        {
            "model": "openai_codex-mini",
            "label": "Codex Mini (weak)",
            "run_id": "fresh_codex"
        },
        {
            "model": "openai_gpt-3.5-turbo",
            "label": "GPT-3.5 Turbo (weak)",
            "run_id": "fresh_gpt35"
        },
        {
            "model": "anthropic_claude-4.5-sonnet-20250929",
            "label": "Claude 4.5 Sonnet (strong)",
            "run_id": "fresh_sonnet"
        }
    ]
    
    with app.app_context():
        gen_service = GenerationService()
        
        for i, test in enumerate(test_cases, 1):
            print(f"{'='*60}")
            print(f"Generating App {i}/3: {test['label']}")
            print(f"   Model: {test['model']}")
            print(f"   Template: crud_todo_list (fuckup-proof)")
            print(f"{'='*60}\n")
            
            try:
                # Use the correct service method (same as web UI)
                result = asyncio.run(gen_service.generate_full_app(
                    model_slug=test['model'],
                    app_num=i,  # Use sequential app numbers
                    template_slug='crud_todo_list',
                    generate_frontend=True,
                    generate_backend=True
                ))
                
                if result.get('success'):
                    app_path = result.get('app_path', 'unknown')
                    print(f"SUCCESS: {app_path}")
                    print(f"   Files generated: {result.get('files_generated', 0)}")
                    print(f"   Duration: {result.get('duration_seconds', 0):.1f}s\n")
                else:
                    print(f"FAILED: {result.get('error', 'Unknown error')}\n")
                    
            except Exception as e:
                print(f"EXCEPTION: {str(e)}\n")
    
    print(f"\n{'='*60}")
    print("Generation Complete!")
    print(f"{'='*60}")
    print("\nNext Steps:")
    print("1. Check generated apps in generated/apps/")
    print("2. Verify all apps use /api/todos (not /api/items)")
    print("3. Build and test with Docker")
    print("4. Expected: 3/3 working (100% vs previous 33%)")

if __name__ == "__main__":
    print("Fresh App Generation Script")
    print("="*60)
    print("Purpose: Validate fuckup-proof requirements")
    print("Template: crud_todo_list (complete schemas)")
    print("Models: Codex Mini + GPT-3.5 + Claude Sonnet 4.5")
    print("="*60 + "\n")
    
    clean_old_apps()
    generate_test_apps()
