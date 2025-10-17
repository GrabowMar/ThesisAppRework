"""Manual App Validation Tool

Validates existing generated apps to identify issues.

Usage:
    python scripts/validate_app.py <model_slug> <app_num>
    
Example:
    python scripts/validate_app.py anthropic_claude-4.5-haiku-20251001 3
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.code_validator import validate_generated_code
from app.paths import GENERATED_APPS_DIR


def validate_app(model_slug: str, app_num: int):
    """Validate a specific generated app."""
    
    # Build path to app
    app_dir = GENERATED_APPS_DIR / model_slug / f"app{app_num}"
    
    if not app_dir.exists():
        print(f"❌ App not found: {app_dir}")
        return False
    
    print("=" * 80)
    print(f"Validating: {model_slug}/app{app_num}")
    print("=" * 80)
    print()
    
    # Read files
    backend_app = app_dir / "backend" / "app.py"
    backend_req = app_dir / "backend" / "requirements.txt"
    frontend_pkg = app_dir / "frontend" / "package.json"
    frontend_app = app_dir / "frontend" / "src" / "App.jsx"
    
    app_py = None
    requirements_txt = None
    package_json = None
    app_jsx = None
    
    if backend_app.exists():
        app_py = backend_app.read_text(encoding='utf-8')
        print(f"✓ Found backend/app.py ({len(app_py)} chars)")
    else:
        print("⚠ Missing backend/app.py")
    
    if backend_req.exists():
        requirements_txt = backend_req.read_text(encoding='utf-8')
        print(f"✓ Found backend/requirements.txt ({len(requirements_txt)} chars)")
    else:
        print("⚠ Missing backend/requirements.txt")
    
    if frontend_pkg.exists():
        package_json = frontend_pkg.read_text(encoding='utf-8')
        print(f"✓ Found frontend/package.json ({len(package_json)} chars)")
    else:
        print("⚠ Missing frontend/package.json")
    
    if frontend_app.exists():
        app_jsx = frontend_app.read_text(encoding='utf-8')
        print(f"✓ Found frontend/src/App.jsx ({len(app_jsx)} chars)")
    else:
        print("⚠ Missing frontend/src/App.jsx")
    
    print()
    
    # Validate
    if not any([app_py, requirements_txt, package_json, app_jsx]):
        print("❌ No files to validate")
        return False
    
    results = validate_generated_code(
        app_py=app_py,
        requirements_txt=requirements_txt,
        package_json=package_json,
        app_jsx=app_jsx
    )
    
    # Print results
    print("=" * 80)
    print("VALIDATION RESULTS")
    print("=" * 80)
    print()
    
    overall_status = "✓ PASS" if results['overall_valid'] else "✗ FAIL"
    print(f"Overall: {overall_status}")
    print()
    
    # Backend results
    if app_py and requirements_txt:
        backend = results['backend']
        status = "✓ PASS" if backend['valid'] else "✗ FAIL"
        print(f"Backend: {status}")
        
        if backend['errors']:
            print("\n  Errors:")
            for error in backend['errors']:
                print(f"    ❌ {error}")
        
        if backend['warnings']:
            print("\n  Warnings:")
            for warning in backend['warnings']:
                print(f"    ⚠ {warning}")
        
        print()
    
    # Frontend results
    if package_json and app_jsx:
        frontend = results['frontend']
        status = "✓ PASS" if frontend['valid'] else "✗ FAIL"
        print(f"Frontend: {status}")
        
        if frontend['errors']:
            print("\n  Errors:")
            for error in frontend['errors']:
                print(f"    ❌ {error}")
        
        if frontend['warnings']:
            print("\n  Warnings:")
            for warning in frontend['warnings']:
                print(f"    ⚠ {warning}")
        
        print()
    
    # Suggestions
    if not results['overall_valid']:
        print("=" * 80)
        print("SUGGESTED FIXES")
        print("=" * 80)
        print()
        
        backend = results['backend']
        if backend.get('errors'):
            for error in backend['errors']:
                if 'Missing dependencies' in error:
                    # Extract package names
                    import re
                    match = re.search(r'Missing dependencies.*?: (.+)', error)
                    if match:
                        packages = match.group(1).split(', ')
                        print("1. Add missing packages to backend/requirements.txt:")
                        for pkg in packages:
                            print(f"   {pkg}==<version>")
                        print()
                
                if 'Syntax error' in error:
                    print("2. Fix syntax error in backend/app.py")
                    print(f"   {error}")
                    print()
        
        frontend = results['frontend']
        if frontend.get('errors'):
            for error in frontend['errors']:
                if 'react' in error.lower():
                    print("3. Add React to frontend/package.json dependencies:")
                    print('   "react": "^18.2.0",')
                    print('   "react-dom": "^18.2.0"')
                    print()
    
    return results['overall_valid']


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        print("Usage: python scripts/validate_app.py <model_slug> <app_num>")
        print()
        print("Examples:")
        print("  python scripts/validate_app.py anthropic_claude-4.5-haiku-20251001 1")
        print("  python scripts/validate_app.py google_gemini-2.5-flash-preview-09-2025 2")
        sys.exit(1)
    
    model_slug = sys.argv[1]
    
    try:
        app_num = int(sys.argv[2])
    except ValueError:
        print(f"❌ Invalid app number: {sys.argv[2]}")
        sys.exit(1)
    
    success = validate_app(model_slug, app_num)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
