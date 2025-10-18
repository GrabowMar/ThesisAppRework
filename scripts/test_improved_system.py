"""Comprehensive System Test
==========================

Generate 3 apps with improved templates and verify they work.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.multi_step_generation_service import MultiStepGenerationService, MultiStepRequest
from app.paths import GENERATED_APPS_DIR

async def generate_app(model_slug: str, app_num: int, requirement_id: str):
    """Generate one complete app."""
    service = MultiStepGenerationService()
    
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
    
    backend_success, backend_steps, backend_summary = await service.generate_multi_step(backend_request)
    
    if not backend_success:
        print(f"❌ Backend generation failed: {backend_summary}")
        return False
    
    print(f"✓ Backend generated successfully")
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
    
    frontend_success, frontend_steps, frontend_summary = await service.generate_multi_step(frontend_request)
    
    if not frontend_success:
        print(f"❌ Frontend generation failed: {frontend_summary}")
        return False
    
    print(f"✓ Frontend generated successfully")
    for step in frontend_steps:
        if step.success:
            print(f"  Step {step.step_name}: ✓ ({step.tokens_used} tokens)")
        else:
            print(f"  Step {step.step_name}: ❌ {step.error}")
    
    return True


async def main():
    """Run comprehensive test."""
    print("🚀 COMPREHENSIVE SYSTEM TEST")
    print("=" * 60)
    print("Improvements Applied:")
    print("✓ Flask 3.0 compatibility (NO @app.before_first_request)")
    print("✓ Few-shot examples in templates")
    print("✓ Chain-of-thought prompting")
    print("✓ Increased max_tokens (16000)")
    print("✓ Lower temperature (0.3)")
    print("✓ Expanded dependency mapping")
    print("=" * 60)
    
    # Clean up old apps
    import shutil
    # Clean both old format and new format
    for model_slug in ['openai_gpt-4o-mini', 'openai_gpt-4o-mini']:
        model_dir = GENERATED_APPS_DIR / model_slug
        if model_dir.exists():
            print(f"\nCleaning up {model_dir}...")
            shutil.rmtree(model_dir)
    
    # Generate 3 apps (use OpenRouter format: openai/gpt-4o-mini)
    test_cases = [
        ('openai/gpt-4o-mini', 30, 'todo_api'),
        ('openai/gpt-4o-mini', 31, 'base64_api'),
        ('openai/gpt-4o-mini', 32, 'calculator_api'),
    ]
    
    results = []
    for model_slug, app_num, requirement_id in test_cases:
        success = await generate_app(model_slug, app_num, requirement_id)
        results.append((model_slug, app_num, requirement_id, success))
    
    # Summary
    print("\n" + "=" * 60)
    print("GENERATION SUMMARY")
    print("=" * 60)
    
    for model_slug, app_num, requirement_id, success in results:
        status = "✓" if success else "❌"
        print(f"{status} {model_slug}/app{app_num} ({requirement_id})")
    
    successful = sum(1 for _, _, _, success in results if success)
    print(f"\n{successful}/{len(results)} apps generated successfully")
    
    if successful == len(results):
        print("\n✅ ALL APPS GENERATED!")
        print("\nNext steps:")
        print("1. docker-compose up -d --build in each app directory")
        print("2. Test backends with curl")
        print("3. Test frontends in browser")
        print("4. Check logs for errors")
    else:
        print("\n⚠️  Some apps failed. Check errors above.")
    
    return successful == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
