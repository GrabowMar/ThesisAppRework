"""Bulk Validation Script

Validates all generated apps and creates a summary report.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import GENERATED_APPS_DIR
from app.services.code_validator import validate_generated_code


def find_all_apps():
    """Find all generated apps."""
    apps = []
    
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_slug = model_dir.name
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            try:
                app_num = int(app_dir.name.replace('app', ''))
                apps.append((model_slug, app_num, app_dir))
            except ValueError:
                continue
    
    return sorted(apps)


def validate_all():
    """Validate all apps and generate report."""
    
    print("="*80)
    print("BULK VALIDATION REPORT")
    print("="*80)
    print()
    
    apps = find_all_apps()
    print(f"Found {len(apps)} apps to validate\n")
    
    results = []
    
    for model_slug, app_num, app_dir in apps:
        print(f"\nValidating: {model_slug}/app{app_num}")
        print("-" * 80)
        
        # Read files
        backend_app = app_dir / "backend" / "app.py"
        backend_req = app_dir / "backend" / "requirements.txt"
        frontend_pkg = app_dir / "frontend" / "package.json"
        frontend_app = app_dir / "frontend" / "src" / "App.jsx"
        
        app_py = backend_app.read_text(encoding='utf-8') if backend_app.exists() else None
        requirements_txt = backend_req.read_text(encoding='utf-8') if backend_req.exists() else None
        package_json = frontend_pkg.read_text(encoding='utf-8') if frontend_pkg.exists() else None
        app_jsx = frontend_app.read_text(encoding='utf-8') if frontend_app.exists() else None
        
        # Validate
        validation = validate_generated_code(
            app_py=app_py,
            requirements_txt=requirements_txt,
            package_json=package_json,
            app_jsx=app_jsx
        )
        
        backend_valid = validation['backend']['valid']
        frontend_valid = validation['frontend']['valid']
        overall_valid = validation['overall_valid']
        
        status = "[OK]" if overall_valid else "[FAIL]"
        print(f"  Overall: {status}")
        
        if not backend_valid:
            print(f"  Backend: [FAIL]")
            for err in validation['backend']['errors']:
                print(f"    - {err}")
        else:
            print(f"  Backend: [OK]")
        
        if not frontend_valid:
            print(f"  Frontend: [FAIL]")
            for err in validation['frontend']['errors']:
                print(f"    - {err}")
        else:
            print(f"  Frontend: [OK]")
        
        results.append({
            'model': model_slug,
            'app': app_num,
            'overall_valid': overall_valid,
            'backend_valid': backend_valid,
            'frontend_valid': frontend_valid,
            'backend_errors': validation['backend']['errors'],
            'frontend_errors': validation['frontend']['errors']
        })
    
    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for r in results if r['overall_valid'])
    backend_passed = sum(1 for r in results if r['backend_valid'])
    frontend_passed = sum(1 for r in results if r['frontend_valid'])
    
    print(f"\nTotal Apps: {total}")
    print(f"Overall Pass: {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"Backend Pass: {backend_passed}/{total} ({backend_passed/total*100:.1f}%)")
    print(f"Frontend Pass: {frontend_passed}/{total} ({frontend_passed/total*100:.1f}%)")
    
    # Failing apps
    failing = [r for r in results if not r['overall_valid']]
    if failing:
        print(f"\n\nFailing Apps ({len(failing)}):")
        for r in failing:
            print(f"\n  {r['model']}/app{r['app']}:")
            if r['backend_errors']:
                for err in r['backend_errors']:
                    print(f"    Backend: {err}")
            if r['frontend_errors']:
                for err in r['frontend_errors']:
                    print(f"    Frontend: {err}")
    
    # Common issues
    all_errors = []
    for r in results:
        all_errors.extend(r['backend_errors'])
        all_errors.extend(r['frontend_errors'])
    
    if all_errors:
        from collections import Counter
        print(f"\n\nMost Common Issues:")
        for error, count in Counter(all_errors).most_common(5):
            print(f"  {count}x: {error}")


if __name__ == '__main__':
    validate_all()
