"""Auto-Fix Missing Dependencies

Automatically fixes common missing dependency issues in generated apps.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import GENERATED_APPS_DIR


COMMON_PACKAGES = {
    'lxml': 'lxml==5.1.0',
    'sqlalchemy': 'SQLAlchemy==2.0.25',
    'flask_sqlalchemy': 'Flask-SQLAlchemy==3.1.1',
    'werkzeug': 'Werkzeug==3.0.1',
    'bcrypt': 'bcrypt==4.1.2',
    'jwt': 'PyJWT==2.8.0',
    'requests': 'requests==2.31.0',
    'pillow': 'Pillow==10.2.0',
    'PIL': 'Pillow==10.2.0',
    'pandas': 'pandas==2.2.0',
    'dotenv': 'python-dotenv==1.0.0',
    'cryptography': 'cryptography==42.0.0',
}


def fix_app(model_slug: str, app_num: int, dry_run=True):
    """Fix missing dependencies for a specific app."""
    
    app_dir = GENERATED_APPS_DIR / model_slug / f"app{app_num}"
    backend_app = app_dir / "backend" / "app.py"
    backend_req = app_dir / "backend" / "requirements.txt"
    
    if not backend_app.exists() or not backend_req.exists():
        print(f"[SKIP] {model_slug}/app{app_num} - missing files")
        return False
    
    # Read files
    app_py = backend_app.read_text(encoding='utf-8')
    requirements_txt = backend_req.read_text(encoding='utf-8')
    
    # Find missing packages
    missing = []
    for pkg, version_spec in COMMON_PACKAGES.items():
        # Check if package is imported
        imports = [
            f"import {pkg}",
            f"from {pkg}",
            f"import {pkg.lower()}",
            f"from {pkg.lower()}",
        ]
        
        if any(imp in app_py for imp in imports):
            # Check if it's in requirements
            pkg_name = version_spec.split('==')[0]
            if pkg_name.lower() not in requirements_txt.lower():
                missing.append(version_spec)
    
    # Special case: if flask_sqlalchemy is used, ensure SQLAlchemy is present
    if ('flask_sqlalchemy' in app_py or 'Flask-SQLAlchemy' in requirements_txt):
        # Check for standalone SQLAlchemy (not Flask-SQLAlchemy)
        if not any(line.strip().lower().startswith('sqlalchemy==') for line in requirements_txt.split('\n')):
            missing.append('SQLAlchemy==2.0.25')
    
    if not missing:
        print(f"[OK] {model_slug}/app{app_num} - no missing dependencies")
        return False
    
    print(f"\n[FIX] {model_slug}/app{app_num}")
    print(f"  Adding {len(missing)} missing packages:")
    for pkg in missing:
        print(f"    + {pkg}")
    
    if dry_run:
        print("  (DRY RUN - no changes made)")
        return True
    
    # Add missing packages
    new_requirements = requirements_txt.rstrip() + '\n' + '\n'.join(missing) + '\n'
    backend_req.write_text(new_requirements, encoding='utf-8')
    print("  [SAVED] requirements.txt updated")
    
    return True


def fix_all_apps(dry_run=True):
    """Fix all apps with missing dependencies."""
    
    print("="*80)
    print("AUTO-FIX MISSING DEPENDENCIES")
    print("="*80)
    
    if dry_run:
        print("\n[DRY RUN MODE] - No files will be modified")
    else:
        print("\n[LIVE MODE] - Files will be updated!")
    
    print()
    
    # Known failing apps from validation
    failing_apps = [
        ('anthropic_claude-4.5-haiku-20251001', 3),
        ('openai_gpt-5-mini-2025-08-07', 1),
        ('openai_gpt-5-mini-2025-08-07', 2),
        ('openai_gpt-5-mini-2025-08-07', 3),
    ]
    
    fixed = 0
    for model, app_num in failing_apps:
        if fix_app(model, app_num, dry_run=dry_run):
            fixed += 1
    
    print(f"\n{'='*80}")
    print(f"Fixed {fixed} apps")
    
    if dry_run:
        print("\nTo apply these fixes, run with --apply:")
        print("  python scripts/auto_fix_deps.py --apply")
    else:
        print("\nRecommendation: Rebuild containers for fixed apps:")
        for model, app_num in failing_apps:
            app_dir = f"generated/apps/{model}/app{app_num}"
            print(f"  cd {app_dir} && docker-compose up --build -d backend")
    
    print("="*80)


if __name__ == '__main__':
    dry_run = '--apply' not in sys.argv
    fix_all_apps(dry_run=dry_run)
