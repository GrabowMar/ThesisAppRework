"""Test V2 generation with AI."""
import sys
import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.services.generation_v2 import get_generation_service_v2

async def test_xsd_verifier():
    """Test generating an XSD verifier app."""
    print("=" * 80)
    print("Testing V2 Full Generation - XSD Verifier App")
    print("=" * 80)
    
    service = get_generation_service_v2()
    
    # Parameters
    # Use OpenRouter format: provider/model-name
    model_slug = "anthropic/claude-3.5-sonnet"  # Known working model
    app_num = 3  # Use app3 to avoid conflicts
    template_id = 1
    
    print(f"\nModel: {model_slug}")
    print(f"App Number: {app_num}")
    print(f"Backend: True")
    print(f"Frontend: True")
    
    # Generate
    print("\n" + "-" * 80)
    print("Generating application...")
    print("-" * 80)
    
    result = await service.generate_full_app(
        model_slug=model_slug,
        app_num=app_num,
        template_id=template_id,
        generate_frontend=True,
        generate_backend=True
    )
    
    if not result['success']:
        print("\n✗ Generation failed!")
        print(f"Errors: {', '.join(result['errors'])}")
        return False
    
    print("\n✓ Generation successful!")
    print(f"  Scaffolded: {result['scaffolded']}")
    print(f"  Backend generated: {result['backend_generated']}")
    print(f"  Frontend generated: {result['frontend_generated']}")
    print(f"  Backend port: {result['backend_port']}")
    print(f"  Frontend port: {result['frontend_port']}")
    
    # Check generated files
    app_dir = Path(result['app_dir'])
    
    if not app_dir.exists():
        print(f"\n✗ App directory not found: {app_dir}")
        return False
    
    print(f"\n✓ App directory created: {app_dir}")
    
    # List generated files
    print("\n" + "-" * 80)
    print("Generated Files:")
    print("-" * 80)
    
    for file in sorted(app_dir.rglob('*')):
        if file.is_file():
            rel_path = file.relative_to(app_dir)
            size = file.stat().st_size
            print(f"  {rel_path} ({size} bytes)")
    
    # Verify Docker files
    docker_files = [
        'docker-compose.yml',
        'backend/Dockerfile',
        'frontend/Dockerfile',
        'frontend/nginx.conf',
        'frontend/vite.config.js',
    ]
    
    print("\n" + "-" * 80)
    print("Docker Infrastructure Check:")
    print("-" * 80)
    
    all_good = True
    for docker_file in docker_files:
        exists = (app_dir / docker_file).exists()
        print(f"  {'✓' if exists else '✗'} {docker_file}")
        if not exists:
            all_good = False
    
    # Show summary
    print("\n" + "=" * 80)
    if all_good:
        print("✓ SUCCESS: XSD Verifier app generated with complete Docker infrastructure!")
    else:
        print("✗ PARTIAL: App generated but some Docker files missing!")
    print("=" * 80)
    
    return all_good

if __name__ == '__main__':
    success = asyncio.run(test_xsd_verifier())
    sys.exit(0 if success else 1)
