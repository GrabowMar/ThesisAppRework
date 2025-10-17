"""
Fix SQLAlchemy Configuration in Generated Apps

Adds missing SQLALCHEMY_DATABASE_URI configuration to generated Flask apps
that are failing to start due to missing database configuration.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / 'src'))


def fix_app_py(app_py_path: Path) -> bool:
    """Fix app.py by adding SQLAlchemy configuration if missing."""
    if not app_py_path.exists():
        return False
    
    content = app_py_path.read_text(encoding='utf-8')
    
    # Check if already has SQLALCHEMY_DATABASE_URI
    if 'SQLALCHEMY_DATABASE_URI' in content:
        print(f"  ✅ Already configured: {app_py_path.relative_to(project_root)}")
        return False
    
    # Check if uses SQLAlchemy
    if 'SQLAlchemy' not in content:
        print(f"  ⏭️  No SQLAlchemy: {app_py_path.relative_to(project_root)}")
        return False
    
    # Find the line with SECRET_KEY
    lines = content.splitlines(keepends=True)
    insert_index = None
    
    for i, line in enumerate(lines):
        if "app.config['SECRET_KEY']" in line or 'app.config["SECRET_KEY"]' in line:
            insert_index = i + 1
            break
    
    if insert_index is None:
        print(f"  ❌ Could not find insertion point: {app_py_path.relative_to(project_root)}")
        return False
    
    # Add SQLAlchemy configuration
    sqlalchemy_config = """app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
"""
    
    lines.insert(insert_index, sqlalchemy_config)
    
    # Write back
    app_py_path.write_text(''.join(lines), encoding='utf-8')
    print(f"  ✏️  Fixed: {app_py_path.relative_to(project_root)}")
    return True


def main():
    """Fix all generated apps."""
    print("=" * 70)
    print("Fixing SQLAlchemy Configuration in Generated Apps")
    print("=" * 70 + "\n")
    
    generated_dir = project_root / 'generated' / 'apps'
    
    if not generated_dir.exists():
        print(f"❌ Generated apps directory not found: {generated_dir}")
        return 1
    
    fixed_count = 0
    skipped_count = 0
    error_count = 0
    
    # Find all app.py files in backend directories
    for app_py in generated_dir.rglob('backend/app.py'):
        try:
            if fix_app_py(app_py):
                fixed_count += 1
            else:
                skipped_count += 1
        except Exception as e:
            print(f"  ❌ Error processing {app_py.relative_to(project_root)}: {e}")
            error_count += 1
    
    print("\n" + "=" * 70)
    print("Summary")
    print("=" * 70)
    print(f"✏️  Fixed: {fixed_count}")
    print(f"⏭️  Skipped: {skipped_count}")
    print(f"❌ Errors: {error_count}")
    print("=" * 70)
    
    if fixed_count > 0:
        print("\n✅ Configuration added successfully!")
        print("\nNext steps:")
        print("1. Rebuild the affected containers:")
        print("   docker compose -f <path-to-docker-compose.yml> -p <project-name> build --no-cache")
        print("2. Or use the UI to rebuild the containers")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
