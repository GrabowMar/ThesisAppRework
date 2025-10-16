"""Test script for V2 generation system."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.generation_v2 import ScaffoldingManager

def test_scaffold_only():
    """Test scaffolding setup without AI generation."""
    print("=" * 80)
    print("Testing V2 Scaffolding (No AI Generation)")
    print("=" * 80)
    
    scaffolder = ScaffoldingManager()
    
    # Test parameters
    model_name = "x-ai_grok-code-fast-1"
    app_num = 1
    
    print(f"\nModel: {model_name}")
    print(f"App Number: {app_num}")
    
    # Get ports
    backend_port, frontend_port = scaffolder.get_ports(app_num)
    print(f"Backend Port: {backend_port}")
    print(f"Frontend Port: {frontend_port}")
    
    # Setup scaffolding
    print("\n" + "-" * 80)
    print("Setting up scaffolding...")
    print("-" * 80)
    
    success = scaffolder.scaffold(model_name, app_num)
    
    if not success:
        print("\n✗ Scaffolding failed!")
        return False
    
    # Get directories
    app_dir = scaffolder.get_app_dir(model_name, app_num)
    backend_dir = app_dir / 'backend'
    frontend_dir = app_dir / 'frontend'
    
    print(f"\nApp directory: {app_dir}")
    print(f"Backend directory: {backend_dir}")
    print(f"Frontend directory: {frontend_dir}")
    
    # Verify scaffolding files
    print("\n" + "-" * 80)
    print("Verifying scaffolding files...")
    print("-" * 80)
    
    expected_files = {
        'backend': [
            'Dockerfile',
            'requirements.txt',
            'app.py',
        ],
        'frontend': [
            'Dockerfile',
            'package.json',
            'vite.config.js',
            'nginx.conf',
            'src/App.jsx',
            'src/main.jsx',
            'index.html',
        ],
        'root': [
            'docker-compose.yml',
        ]
    }
    
    all_good = True
    
    # Check backend files
    print("\nBackend files:")
    for file in expected_files['backend']:
        path = backend_dir / file
        exists = path.exists()
        print(f"  {'✓' if exists else '✗'} {file}")
        if not exists:
            all_good = False
    
    # Check frontend files
    print("\nFrontend files:")
    for file in expected_files['frontend']:
        path = frontend_dir / file
        exists = path.exists()
        print(f"  {'✓' if exists else '✗'} {file}")
        if not exists:
            all_good = False
    
    # Check root files
    print("\nRoot files:")
    app_root = backend_dir.parent
    for file in expected_files['root']:
        path = app_root / file
        exists = path.exists()
        print(f"  {'✓' if exists else '✗'} {file}")
        if not exists:
            all_good = False
    
    # Verify port substitution
    print("\n" + "-" * 80)
    print("Verifying port substitution...")
    print("-" * 80)
    
    # Check docker-compose.yml
    compose_file = app_root / 'docker-compose.yml'
    if compose_file.exists():
        content = compose_file.read_text()
        # Check for environment var defaults and internal ports
        has_backend_port = f"BACKEND_PORT:-{backend_port}" in content and f":{backend_port}" in content
        has_frontend_port = f"FRONTEND_PORT:-{frontend_port}" in content
        has_placeholder = "{{backend_port" in content or "{{frontend_port" in content
        
        print("\ndocker-compose.yml:")
        print(f"  {'✓' if has_backend_port else '✗'} Backend port {backend_port} found")
        print(f"  {'✓' if has_frontend_port else '✗'} Frontend port {frontend_port} found")
        print(f"  {'✓' if not has_placeholder else '✗'} No unsubstituted placeholders")
        
        if not (has_backend_port and has_frontend_port and not has_placeholder):
            all_good = False
    
    # Check vite.config.js
    vite_config = frontend_dir / 'vite.config.js'
    if vite_config.exists():
        content = vite_config.read_text()
        # Check that port is in the proxy target (can be localhost or backend container)
        has_backend_port = f":{backend_port}" in content and "target:" in content
        has_placeholder = "{{backend_port" in content
        
        print("\nvite.config.js:")
        print(f"  {'✓' if has_backend_port else '✗'} Backend port {backend_port} in proxy")
        print(f"  {'✓' if not has_placeholder else '✗'} No unsubstituted placeholders")
        
        if not (has_backend_port and not has_placeholder):
            all_good = False
    
    # Summary
    print("\n" + "=" * 80)
    if all_good:
        print("✓ SUCCESS: All scaffolding files present with correct ports!")
    else:
        print("✗ FAILURE: Some scaffolding files missing or incorrect ports!")
    print("=" * 80)
    
    return all_good

def test_compare_with_broken_app():
    """Compare V2 generated app with the broken app1."""
    print("\n" + "=" * 80)
    print("Comparing V2 App with Broken App1")
    print("=" * 80)
    
    v2_app = Path("generated/apps/x-ai_grok-code-fast-1/app1")
    broken_app = Path("generated/apps/x-ai_grok-code-fast-1/app1_old")
    
    if not v2_app.exists():
        print("\n⚠ V2 app not generated yet. Run test_scaffold_only() first.")
        return
    
    print("\nV2 App Structure:")
    for file in sorted(v2_app.rglob('*')):
        if file.is_file():
            rel_path = file.relative_to(v2_app)
            print(f"  {rel_path}")
    
    if broken_app.exists():
        print("\nBroken App1 Structure:")
        for file in sorted(broken_app.rglob('*')):
            if file.is_file():
                rel_path = file.relative_to(broken_app)
                print(f"  {rel_path}")
    
    # Check for Docker files in V2
    docker_files = [
        'docker-compose.yml',
        'backend/Dockerfile',
        'frontend/Dockerfile',
    ]
    
    print("\nDocker Infrastructure Check:")
    for docker_file in docker_files:
        v2_has = (v2_app / docker_file).exists()
        print(f"  {'✓' if v2_has else '✗'} {docker_file}")

if __name__ == '__main__':
    success = test_scaffold_only()
    
    if success:
        print("\n" + "=" * 80)
        print("Next step: Test with AI generation")
        print("Run: python scripts/test_simple_generation.py")
        print("=" * 80)
    
    # Uncomment after scaffolding test passes:
    # test_compare_with_broken_app()
