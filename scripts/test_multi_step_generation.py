"""Test Multi-Step Generation System
===================================

Tests the new multi-step generation approach with simple requirements.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.services.multi_step_generation_service import (
    get_multi_step_service,
    MultiStepRequest
)


async def test_generation(requirement_id: str, model_slug: str, app_num: int):
    """Test generation with multi-step approach."""
    
    service = get_multi_step_service()
    
    print(f"\n{'='*60}")
    print(f"Testing: {requirement_id}")
    print(f"Model: {model_slug}")
    print(f"App: {app_num}")
    print(f"{'='*60}\n")
    
    # Test backend generation
    print("Generating backend...")
    backend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component="backend",
        temperature=0.3,
        max_tokens=16000
    )
    
    success, results, message = await service.generate_multi_step(backend_request)
    
    print(f"\nBackend Result: {message}")
    for result in results:
        print(f"  - {result.step_name}: {result.success} ({result.tokens_used} tokens)")
        if result.error:
            print(f"    Error: {result.error}")
    
    # Test frontend generation
    print("\nGenerating frontend...")
    frontend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component="frontend",
        temperature=0.3,
        max_tokens=16000
    )
    
    success, results, message = await service.generate_multi_step(frontend_request)
    
    print(f"\nFrontend Result: {message}")
    for result in results:
        print(f"  - {result.step_name}: {result.success} ({result.tokens_used} tokens)")
        if result.error:
            print(f"    Error: {result.error}")
    
    return success


async def analyze_generated_app(model_slug: str, app_num: int):
    """Analyze generated app for quality metrics."""
    
    from app.services.simple_generation_service import SimpleGenerationService
    
    service = SimpleGenerationService()
    app_dir = service.get_app_dir(model_slug, app_num)
    
    print(f"\n{'='*60}")
    print(f"Analyzing: {app_dir}")
    print(f"{'='*60}\n")
    
    # Check backend
    backend_app = app_dir / 'backend' / 'app.py'
    if backend_app.exists():
        with open(backend_app, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = len(content.split('\n'))
            print(f"Backend app.py: {lines} lines")
            
            # Check for key features
            has_flask = 'from flask import' in content
            has_sqlalchemy = 'SQLAlchemy' in content
            has_error_handling = 'try:' in content and 'except' in content
            has_logging = 'logging' in content or 'logger' in content
            
            print(f"  - Flask: {'✓' if has_flask else '✗'}")
            print(f"  - SQLAlchemy: {'✓' if has_sqlalchemy else '✗'}")
            print(f"  - Error handling: {'✓' if has_error_handling else '✗'}")
            print(f"  - Logging: {'✓' if has_logging else '✗'}")
    else:
        print("Backend app.py: NOT FOUND")
    
    # Check frontend
    frontend_app = app_dir / 'frontend' / 'src' / 'App.jsx'
    if frontend_app.exists():
        with open(frontend_app, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = len(content.split('\n'))
            print(f"\nFrontend App.jsx: {lines} lines")
            
            # Check for key features
            has_react = 'import React' in content or "from 'react'" in content
            has_axios = 'axios' in content
            has_state = 'useState' in content
            has_effect = 'useEffect' in content
            
            print(f"  - React: {'✓' if has_react else '✗'}")
            print(f"  - Axios: {'✓' if has_axios else '✗'}")
            print(f"  - useState: {'✓' if has_state else '✗'}")
            print(f"  - useEffect: {'✓' if has_effect else '✗'}")
    else:
        print("\nFrontend App.jsx: NOT FOUND")
    
    # Check if Docker files exist
    docker_compose = app_dir / 'docker-compose.yml'
    backend_dockerfile = app_dir / 'backend' / 'Dockerfile'
    frontend_dockerfile = app_dir / 'frontend' / 'Dockerfile'
    
    print(f"\nDocker Infrastructure:")
    print(f"  - docker-compose.yml: {'✓' if docker_compose.exists() else '✗'}")
    print(f"  - backend/Dockerfile: {'✓' if backend_dockerfile.exists() else '✗'}")
    print(f"  - frontend/Dockerfile: {'✓' if frontend_dockerfile.exists() else '✗'}")


async def test_build_containers(model_slug: str, app_num: int):
    """Test if containers build successfully."""
    
    from app.services.simple_generation_service import SimpleGenerationService
    import subprocess
    
    service = SimpleGenerationService()
    app_dir = service.get_app_dir(model_slug, app_num)
    
    print(f"\n{'='*60}")
    print(f"Testing Container Build: {app_dir}")
    print(f"{'='*60}\n")
    
    # Check if docker-compose exists
    docker_compose = app_dir / 'docker-compose.yml'
    if not docker_compose.exists():
        print("❌ docker-compose.yml not found")
        return False
    
    # Try to build
    print("Running: docker-compose build")
    try:
        result = subprocess.run(
            ['docker-compose', 'build'],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            print("✓ Build successful!")
            return True
        else:
            print("✗ Build failed!")
            print("\nSTDOUT:")
            print(result.stdout)
            print("\nSTDERR:")
            print(result.stderr)
            return False
    
    except subprocess.TimeoutExpired:
        print("✗ Build timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"✗ Build error: {e}")
        return False


async def main():
    """Main test runner."""
    
    # Test configurations (using app 20-22 for fresh test)
    tests = [
        ("todo_api", "openai/gpt-4o-mini", 20),
        ("base64_api", "openai/gpt-4o-mini", 21),
        ("calculator_api", "openai/gpt-4o-mini", 22),  # Use same model to avoid rate limits
    ]
    
    results = []
    
    for requirement_id, model_slug, app_num in tests:
        try:
            # Generate
            success = await test_generation(requirement_id, model_slug, app_num)
            
            # Analyze
            await analyze_generated_app(model_slug, app_num)
            
            # Try to build (commented out for now - can be slow)
            # build_success = await test_build_containers(model_slug, app_num)
            # results.append((requirement_id, model_slug, app_num, success, build_success))
            
            results.append((requirement_id, model_slug, app_num, success))
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            results.append((requirement_id, model_slug, app_num, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}\n")
    
    for result in results:
        requirement_id, model_slug, app_num, success = result
        status = "✓" if success else "✗"
        print(f"{status} {requirement_id} ({model_slug}, app{app_num})")


if __name__ == "__main__":
    asyncio.run(main())
