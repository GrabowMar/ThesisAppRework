"""Automated App Verification and Deployment
============================================

After generation, automatically:
1. Build all Docker containers
2. Start all services
3. Wait for health checks
4. Test all APIs
5. Report status
"""

import subprocess
import time
import requests
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import GENERATED_APPS_DIR


def find_apps(model_slug: str):
    """Find all generated apps for a model."""
    model_dir = GENERATED_APPS_DIR / model_slug
    if not model_dir.exists():
        return []
    
    apps = []
    for app_dir in sorted(model_dir.iterdir()):
        if app_dir.is_dir() and app_dir.name.startswith('app'):
            apps.append(app_dir)
    return apps


def build_app(app_dir: Path):
    """Build Docker containers for an app."""
    print(f"\n[Building {app_dir.name}]")
    try:
        result = subprocess.run(
            ['docker-compose', 'build', '--no-cache'],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            print(f"✓ Build successful")
            return True
        else:
            print(f"❌ Build failed:")
            print(result.stderr[:500])
            return False
    except Exception as e:
        print(f"❌ Build error: {e}")
        return False


def start_app(app_dir: Path):
    """Start Docker containers for an app."""
    print(f"\n[Starting {app_dir.name}]")
    try:
        result = subprocess.run(
            ['docker-compose', 'up', '-d'],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            print(f"✓ Started successfully")
            return True
        else:
            print(f"❌ Start failed:")
            print(result.stderr[:500])
            return False
    except Exception as e:
        print(f"❌ Start error: {e}")
        return False


def get_ports(app_num: int):
    """Calculate ports for an app."""
    backend_port = 5001 + 2 * (app_num - 1)
    frontend_port = 8001 + 2 * (app_num - 1)
    return backend_port, frontend_port


def test_app(app_dir: Path):
    """Test if an app is working."""
    app_num = int(app_dir.name.replace('app', ''))
    backend_port, frontend_port = get_ports(app_num)
    
    print(f"\n[Testing {app_dir.name}]")
    print(f"  Backend: http://localhost:{backend_port}")
    print(f"  Frontend: http://localhost:{frontend_port}")
    
    # Wait for services to be ready
    print("  Waiting 10 seconds for services to start...")
    time.sleep(10)
    
    # Test backend
    try:
        response = requests.get(f"http://localhost:{backend_port}/health", timeout=5)
        if response.status_code == 200:
            print(f"  ✓ Backend health check OK")
            backend_ok = True
        else:
            print(f"  ❌ Backend returned {response.status_code}")
            backend_ok = False
    except Exception as e:
        print(f"  ❌ Backend not accessible: {e}")
        backend_ok = False
    
    # Test frontend
    try:
        response = requests.get(f"http://localhost:{frontend_port}", timeout=5)
        if response.status_code == 200:
            print(f"  ✓ Frontend accessible")
            frontend_ok = True
        else:
            print(f"  ❌ Frontend returned {response.status_code}")
            frontend_ok = False
    except Exception as e:
        print(f"  ❌ Frontend not accessible: {e}")
        frontend_ok = False
    
    return backend_ok and frontend_ok


def check_code_size(app_dir: Path):
    """Check generated code size."""
    backend_file = app_dir / 'backend' / 'app.py'
    frontend_file = app_dir / 'frontend' / 'src' / 'App.jsx'
    css_file = app_dir / 'frontend' / 'src' / 'App.css'
    
    print(f"\n[Code Size for {app_dir.name}]")
    
    if backend_file.exists():
        lines = len(backend_file.read_text(encoding='utf-8').split('\n'))
        print(f"  Backend: {lines} lines")
    else:
        print(f"  Backend: NOT FOUND")
        lines = 0
    
    if frontend_file.exists():
        jsx_lines = len(frontend_file.read_text(encoding='utf-8').split('\n'))
        print(f"  Frontend JSX: {jsx_lines} lines")
    else:
        print(f"  Frontend JSX: NOT FOUND")
        jsx_lines = 0
    
    if css_file.exists():
        css_lines = len(css_file.read_text(encoding='utf-8').split('\n'))
        print(f"  Frontend CSS: {css_lines} lines")
    else:
        print(f"  Frontend CSS: NOT FOUND")
        css_lines = 0
    
    total = lines + jsx_lines + css_lines
    print(f"  Total: {total} lines")
    return total


def main():
    """Main verification workflow."""
    print("🚀 AUTOMATED APP VERIFICATION")
    print("=" * 60)
    
    model_slug = "openai_gpt-4o-mini"
    apps = find_apps(model_slug)
    
    if not apps:
        print(f"❌ No apps found for {model_slug}")
        return False
    
    print(f"Found {len(apps)} apps to verify")
    
    results = []
    
    for app_dir in apps:
        print("\n" + "=" * 60)
        print(f"Processing {app_dir.name}")
        print("=" * 60)
        
        # Check code size
        total_lines = check_code_size(app_dir)
        
        # Build
        build_ok = build_app(app_dir)
        if not build_ok:
            results.append((app_dir.name, False, total_lines, "Build failed"))
            continue
        
        # Start
        start_ok = start_app(app_dir)
        if not start_ok:
            results.append((app_dir.name, False, total_lines, "Start failed"))
            continue
        
        # Test
        test_ok = test_app(app_dir)
        results.append((app_dir.name, test_ok, total_lines, "Working" if test_ok else "Tests failed"))
    
    # Summary
    print("\n" + "=" * 60)
    print("VERIFICATION SUMMARY")
    print("=" * 60)
    
    for app_name, success, lines, status in results:
        icon = "✓" if success else "❌"
        print(f"{icon} {app_name}: {lines} lines - {status}")
    
    successful = sum(1 for _, success, _, _ in results if success)
    print(f"\n{successful}/{len(results)} apps working correctly")
    
    if successful == len(results):
        print("\n✅ ALL APPS VERIFIED AND WORKING!")
    else:
        print("\n⚠️  Some apps have issues")
    
    return successful == len(results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
