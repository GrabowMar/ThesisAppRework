"""End-to-End Test: Generation → Dependency Fix → Container Build
======================================================================

Tests the complete workflow:
1. Generate app with multi-step process
2. Auto-fix dependencies
3. Build Docker containers
4. Verify containers start successfully
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

from app.services.multi_step_generation_service import (
    get_multi_step_service,
    MultiStepRequest
)


async def generate_app(requirement_id: str, model_slug: str, app_num: int):
    """Generate both backend and frontend."""
    
    print(f"\n{'='*70}")
    print(f"GENERATING: {requirement_id} with {model_slug}")
    print(f"{'='*70}\n")
    
    service = get_multi_step_service()
    
    # Generate backend
    print("Step 1: Generating backend...")
    backend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component="backend",
        temperature=0.3,
        max_tokens=16000
    )
    
    success, results, message = await service.generate_multi_step(backend_request)
    
    if not success:
        print(f"  ✗ Backend generation failed: {message}")
        return False
    
    print(f"  ✓ Backend generated ({sum(r.tokens_used for r in results)} tokens)")
    
    # Generate frontend
    print("Step 2: Generating frontend...")
    frontend_request = MultiStepRequest(
        requirement_id=requirement_id,
        model_slug=model_slug,
        app_num=app_num,
        component="frontend",
        temperature=0.3,
        max_tokens=16000
    )
    
    success, results, message = await service.generate_multi_step(frontend_request)
    
    if not success:
        print(f"  ✗ Frontend generation failed: {message}")
        return False
    
    print(f"  ✓ Frontend generated ({sum(r.tokens_used for r in results)} tokens)")
    
    return True


def check_dependencies(app_dir: Path):
    """Check that dependencies are complete."""
    
    print("\nStep 3: Checking dependencies...")
    
    backend_app = app_dir / 'backend' / 'app.py'
    requirements = app_dir / 'backend' / 'requirements.txt'
    
    if not backend_app.exists():
        print("  ✗ backend/app.py not found")
        return False
    
    if not requirements.exists():
        print("  ✗ requirements.txt not found")
        return False
    
    # Check if requirements has content
    content = requirements.read_text()
    lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
    
    if not lines:
        print("  ✗ requirements.txt is empty")
        return False
    
    print(f"  ✓ Found {len(lines)} packages in requirements.txt")
    
    # Run dependency fixer
    print("  Running dependency auto-fixer...")
    sys.path.insert(0, str(Path(__file__).parent))
    from fix_dependencies import fix_requirements_txt
    
    success, message = fix_requirements_txt(app_dir)
    print(f"  {message}")
    
    return True


def build_containers(app_dir: Path):
    """Build Docker containers."""
    
    print("\nStep 4: Building Docker containers...")
    
    docker_compose = app_dir / 'docker-compose.yml'
    
    if not docker_compose.exists():
        print("  ✗ docker-compose.yml not found")
        return False
    
    try:
        # Build backend
        print("  Building backend...")
        result = subprocess.run(
            ['docker-compose', 'build', 'backend'],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ✗ Backend build failed")
            print(result.stderr[-500:])  # Last 500 chars of error
            return False
        
        print("  ✓ Backend built successfully")
        
        # Build frontend
        print("  Building frontend...")
        result = subprocess.run(
            ['docker-compose', 'build', 'frontend'],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode != 0:
            print(f"  ✗ Frontend build failed")
            print(result.stderr[-500:])
            return False
        
        print("  ✓ Frontend built successfully")
        
        return True
    
    except subprocess.TimeoutExpired:
        print("  ✗ Build timed out (5 minutes)")
        return False
    except Exception as e:
        print(f"  ✗ Build error: {e}")
        return False


def test_containers(app_dir: Path):
    """Start containers and verify they work."""
    
    print("\nStep 5: Testing containers...")
    
    try:
        # Start containers
        print("  Starting containers...")
        result = subprocess.run(
            ['docker-compose', 'up', '-d'],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            print(f"  ✗ Failed to start containers")
            print(result.stderr[-500:])
            return False
        
        print("  ✓ Containers started")
        
        # Wait for startup
        print("  Waiting for services to be ready...")
        time.sleep(5)
        
        # Check if containers are running
        result = subprocess.run(
            ['docker-compose', 'ps'],
            cwd=str(app_dir),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if 'Up' in result.stdout or 'running' in result.stdout:
            print("  ✓ Containers are running")
            
            # Check logs for errors
            result = subprocess.run(
                ['docker-compose', 'logs', '--tail=50'],
                cwd=str(app_dir),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if 'ModuleNotFoundError' in result.stdout or 'ERROR' in result.stdout:
                print("  ⚠ Warning: Found errors in logs:")
                for line in result.stdout.split('\n'):
                    if 'ERROR' in line or 'ModuleNotFoundError' in line:
                        print(f"    {line}")
                return False
            
            print("  ✓ No errors in logs")
            return True
        else:
            print("  ✗ Containers not running")
            return False
    
    except Exception as e:
        print(f"  ✗ Test error: {e}")
        return False
    
    finally:
        # Stop containers
        try:
            subprocess.run(
                ['docker-compose', 'down'],
                cwd=str(app_dir),
                capture_output=True,
                timeout=30
            )
        except:
            pass


async def run_full_test(requirement_id: str, model_slug: str, app_num: int):
    """Run complete end-to-end test."""
    
    from app.services.simple_generation_service import SimpleGenerationService
    service = SimpleGenerationService()
    app_dir = service.get_app_dir(model_slug, app_num)
    
    # Step 1: Generate
    success = await generate_app(requirement_id, model_slug, app_num)
    if not success:
        return False
    
    # Step 2: Check dependencies
    success = check_dependencies(app_dir)
    if not success:
        return False
    
    # Step 3: Build
    success = build_containers(app_dir)
    if not success:
        return False
    
    # Step 4: Test
    success = test_containers(app_dir)
    
    return success


async def main():
    """Main test runner."""
    
    print("="*70)
    print("END-TO-END TEST: Generation → Dependencies → Containers")
    print("="*70)
    
    # Test configuration
    test_case = {
        'requirement_id': 'calculator_api',
        'model_slug': 'openai/gpt-4o-mini',
        'app_num': 50  # Use app50 for testing
    }
    
    try:
        success = await run_full_test(**test_case)
        
        print(f"\n{'='*70}")
        if success:
            print("✓ END-TO-END TEST PASSED")
            print("All steps completed successfully:")
            print("  ✓ Code generation")
            print("  ✓ Dependency detection")
            print("  ✓ Container build")
            print("  ✓ Container startup")
        else:
            print("✗ END-TO-END TEST FAILED")
            print("See errors above")
        print("="*70)
        
        return success
    
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        return False
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
