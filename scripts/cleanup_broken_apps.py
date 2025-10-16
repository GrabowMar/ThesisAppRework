"""Clean up broken generated apps and re-scaffold them properly.

This script:
1. Finds all apps in generated/apps/
2. Checks for scaffolding issues (missing Docker files, numbered files, etc.)
3. Optionally re-scaffolds broken apps using the new simple generation system

Usage:
    python scripts/cleanup_broken_apps.py --dry-run      # See what would be fixed
    python scripts/cleanup_broken_apps.py --fix          # Actually fix them
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.paths import GENERATED_APPS_DIR
from app.services.simple_generation_service import get_simple_generation_service


def check_app_issues(app_dir: Path) -> list[str]:
    """Check an app directory for issues.
    
    Returns list of issues found.
    """
    issues = []
    
    # Check for Docker infrastructure
    docker_compose = app_dir / 'docker-compose.yml'
    backend_dockerfile = app_dir / 'backend' / 'Dockerfile'
    frontend_dockerfile = app_dir / 'frontend' / 'Dockerfile'
    
    if not docker_compose.exists():
        issues.append("Missing docker-compose.yml")
    
    if not backend_dockerfile.exists():
        issues.append("Missing backend/Dockerfile")
    
    if not frontend_dockerfile.exists():
        issues.append("Missing frontend/Dockerfile")
    
    # Check for numbered files (indicates broken generation)
    numbered_files = []
    for file_path in app_dir.rglob('*'):
        if file_path.is_file() and '_0' in file_path.name:
            # Files like index_02.html, package_01.json
            numbered_files.append(str(file_path.relative_to(app_dir)))
    
    if numbered_files:
        issues.append(f"Numbered files detected: {', '.join(numbered_files[:3])}")
    
    # Check for proper port substitution in docker-compose.yml
    if docker_compose.exists():
        content = docker_compose.read_text()
        if '{{backend_port' in content or '{{frontend_port' in content:
            issues.append("Un-substituted port placeholders in docker-compose.yml")
    
    # Check for vite.config.js
    vite_config = app_dir / 'frontend' / 'vite.config.js'
    if vite_config.exists():
        content = vite_config.read_text()
        if '{{' in content:
            issues.append("Un-substituted placeholders in vite.config.js")
    
    return issues


def parse_app_path(app_dir: Path) -> tuple[str, int] | None:
    """Parse model slug and app number from path.
    
    Returns (model_slug, app_num) or None if can't parse.
    """
    try:
        # Path format: generated/apps/{model_slug}/app{N}
        app_name = app_dir.name
        if not app_name.startswith('app'):
            return None
        
        app_num = int(app_name.replace('app', ''))
        model_slug = app_dir.parent.name
        
        # Convert filesystem slug back to API slug (x-ai_grok-1 -> x-ai/grok-1)
        if '_' in model_slug and '/' not in model_slug:
            parts = model_slug.split('_', 1)
            if len(parts) == 2:
                model_slug = f"{parts[0]}/{parts[1]}"
        
        return (model_slug, app_num)
    except (ValueError, IndexError):
        return None


def fix_app(app_dir: Path, dry_run: bool = True) -> bool:
    """Fix a broken app by re-scaffolding.
    
    Returns True if fixed successfully.
    """
    parsed = parse_app_path(app_dir)
    if not parsed:
        print(f"  ✗ Could not parse app path: {app_dir}")
        return False
    
    model_slug, app_num = parsed
    
    if dry_run:
        print(f"  Would re-scaffold {model_slug}/app{app_num}")
        return True
    
    print(f"  Re-scaffolding {model_slug}/app{app_num}...")
    
    try:
        service = get_simple_generation_service()
        success = service.scaffold_app(model_slug, app_num, force=True)
        
        if success:
            print(f"    ✓ Scaffolding successful")
            return True
        else:
            print(f"    ✗ Scaffolding failed")
            return False
            
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False


def main():
    """Scan and optionally fix broken apps."""
    parser = argparse.ArgumentParser(description="Clean up broken generated apps")
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Show what would be fixed without making changes"
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help="Actually fix broken apps"
    )
    
    args = parser.parse_args()
    
    if not args.dry_run and not args.fix:
        parser.print_help()
        print("\nError: Must specify either --dry-run or --fix")
        return 1
    
    print("=" * 80)
    print("BROKEN APP CLEANUP")
    print("=" * 80)
    print()
    
    if not GENERATED_APPS_DIR.exists():
        print(f"No generated apps directory found: {GENERATED_APPS_DIR}")
        return 0
    
    # Scan all apps
    all_apps = []
    broken_apps = []
    
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            all_apps.append(app_dir)
            
            # Check for issues
            issues = check_app_issues(app_dir)
            if issues:
                broken_apps.append((app_dir, issues))
    
    print(f"Scanned {len(all_apps)} apps")
    print(f"Found {len(broken_apps)} broken apps")
    print()
    
    if not broken_apps:
        print("✓ All apps are properly scaffolded!")
        return 0
    
    # Show issues
    print("Broken Apps:")
    print("-" * 80)
    
    for app_dir, issues in broken_apps:
        parsed = parse_app_path(app_dir)
        if parsed:
            model_slug, app_num = parsed
            label = f"{model_slug}/app{app_num}"
        else:
            label = str(app_dir)
        
        print(f"\n{label}:")
        for issue in issues:
            print(f"  • {issue}")
    
    print()
    print("=" * 80)
    
    # Fix if requested
    if args.fix:
        print(f"\nFixing {len(broken_apps)} apps...")
        print()
        
        fixed_count = 0
        failed_count = 0
        
        for app_dir, issues in broken_apps:
            if fix_app(app_dir, dry_run=False):
                fixed_count += 1
            else:
                failed_count += 1
        
        print()
        print("=" * 80)
        print(f"Fixed {fixed_count} apps")
        if failed_count:
            print(f"Failed to fix {failed_count} apps")
        print("=" * 80)
    
    elif args.dry_run:
        print(f"\nDry run complete. Run with --fix to actually fix these apps.")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
