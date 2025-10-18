"""Test Generation with Synchronous Requests (Windows-compatible)."""
import requests
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.multi_step_generation_service import MultiStepGenerationService, MultiStepRequest

def generate_app_sync(model_slug: str, app_num: int, requirement_id: str):
    """Generate one complete app using sync version."""
    # Create a sync-compatible service
    service = MultiStepGenerationService()
    service._use_sync_http = True  # Flag to use requests instead of httpx
    
    print(f"\n{'='*60}")
    print(f"Generating {model_slug} / app{app_num} / {requirement_id}")
    print(f"{'='*60}")
    
    # Generate backend
    print("\n[Generating Backend]")
    backend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component='backend',
        temperature=0.3,
        max_tokens=16000
    )
    
    # Call sync version
    backend_success, backend_steps, backend_summary = service.generate_multi_step_sync(backend_request)
    
    if not backend_success:
        print(f"❌ Backend generation failed: {backend_summary}")
        return False
    
    print("✓ Backend generated successfully")
    for step in backend_steps:
        if step.success:
            print(f"  Step {step.step_name}: ✓ ({step.tokens_used} tokens)")
        else:
            print(f"  Step {step.step_name}: ❌ {step.error}")
    
    # Generate frontend
    print("\n[Generating Frontend]")
    frontend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component='frontend',
        temperature=0.3,
        max_tokens=16000
    )
    
    frontend_success, frontend_steps, frontend_summary = service.generate_multi_step_sync(frontend_request)
    
    if not frontend_success:
        print(f"❌ Frontend generation failed: {frontend_summary}")
        return False
    
    print("✓ Frontend generated successfully")
    for step in frontend_steps:
        if step.success:
            print(f"  Step {step.step_name}: ✓ ({step.tokens_used} tokens)")
        else:
            print(f"  Step {step.step_name}: ❌ {step.error}")
    
    return True

def main():
    """Generate 3 test apps with Grok 4 Fast using SYNC requests."""
    print("=" * 80)
    print("TESTING GROK 4 FAST - SYNCHRONOUS VERSION (Windows-compatible)")
    print("=" * 80)
    print("Using synchronous requests library to avoid async timeout issues...")
    print()
    
    # Test apps for Grok 4 Fast
    test_cases = [
        ('x-ai/grok-4-fast', 4, 'todo_api'),
        ('x-ai/grok-4-fast', 5, 'base64_api'),
        ('x-ai/grok-4-fast', 6, 'calculator_api'),
    ]
    
    results = []
    for model_slug, app_num, requirement_id in test_cases:
        success = generate_app_sync(model_slug, app_num, requirement_id)
        results.append((model_slug, app_num, requirement_id, success))
        
        # Small delay between generations
        if app_num < 6:
            print("\nWaiting 3 seconds before next generation...")
            import time
            time.sleep(3)
    
    # Summary
    print("\n" + "=" * 80)
    print("GROK 4 FAST GENERATION SUMMARY")
    print("=" * 80)
    
    for model_slug, app_num, requirement_id, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {model_slug}/app{app_num} ({requirement_id})")
    
    successful = sum(1 for _, _, _, success in results if success)
    print(f"\n{successful}/{len(results)} apps generated successfully")
    
    if successful == len(results):
        print("\n🎉 ALL GROK APPS GENERATED!")
        print("\nNext steps:")
        print("1. Analyze code quality and size")
        print("2. Compare with GPT-4o-mini output")
        print("3. Build with docker-compose build")
        print("4. Test APIs and frontends")
    else:
        print("\n⚠️  Some apps failed. Check errors above.")
    
    return successful == len(results)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
