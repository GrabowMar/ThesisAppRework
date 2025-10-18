"""Test improved generation system with Claude 3.5 Haiku."""
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
    """Generate 3 test apps with Claude 3.5 Haiku."""
    print("=" * 80)
    print("TESTING CLAUDE 3.5 HAIKU - HI LIL BRO! 🤖💙")
    print("=" * 80)
    print("Testing if improved system works universally across different models...")
    print()
    
    # Test apps for Claude 3.5 Haiku (using same requirements as GPT-4o-mini test)
    test_cases = [
        ('anthropic/claude-3.5-haiku-20241022', 1, 'todo_api'),
        ('anthropic/claude-3.5-haiku-20241022', 2, 'base64_api'),
        ('anthropic/claude-3.5-haiku-20241022', 3, 'calculator_api'),
    ]
    
    results = []
    for model_slug, app_num, requirement_id in test_cases:
        success = await generate_app(model_slug, app_num, requirement_id)
        results.append((model_slug, app_num, requirement_id, success))
        
        # Small delay between generations
        if app_num < 3:
            print("\nWaiting 2 seconds before next generation...")
            await asyncio.sleep(2)
    
    # Summary
    print("\n" + "=" * 80)
    print("CLAUDE 3.5 HAIKU GENERATION SUMMARY")
    print("=" * 80)
    
    for model_slug, app_num, requirement_id, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {model_slug}/app{app_num} ({requirement_id})")
    
    successful = sum(1 for _, _, _, success in results if success)
    print(f"\n{successful}/{len(results)} apps generated successfully")
    
    if successful == len(results):
        print("\n🎉 ALL CLAUDE APPS GENERATED!")
        print("\nNext steps:")
        print("1. Check code quality and size")
        print("2. docker-compose build in each app directory")
        print("3. docker-compose up -d")
        print("4. Test APIs and frontends")
    else:
        print("\n⚠️  Some apps failed. Check errors above.")
    
    return successful == len(results)

if __name__ == '__main__':
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

