#!/usr/bin/env python3
"""Migrate generated apps from template-based to flat directory structure.

This script converts:
  generated/apps/{model}/{template}/app{N}/  →  generated/apps/{model}/app{M}/

Where M is a new globally-unique app number per model.

The migration:
1. Scans for apps in the old template-based structure
2. Assigns new sequential app numbers (starting from 1)
3. Moves each app directory to the flat structure
4. Updates the database records accordingly

Run with --dry-run first to preview changes without moving files.
"""

import argparse
import shutil
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


def find_template_based_apps(apps_dir: Path) -> list:
    """Find all apps in the old template-based structure.
    
    Returns list of tuples: (model_slug, template_slug, old_app_num, app_dir)
    """
    apps = []
    
    if not apps_dir.exists():
        return apps
    
    for model_dir in apps_dir.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_slug = model_dir.name
        
        for subdir in model_dir.iterdir():
            if not subdir.is_dir():
                continue
            
            # Skip if this is already a flat app directory
            if subdir.name.startswith('app'):
                continue
            
            # This is a template directory - look for app subdirs
            template_slug = subdir.name
            
            for app_subdir in subdir.iterdir():
                if app_subdir.is_dir() and app_subdir.name.startswith('app'):
                    try:
                        old_app_num = int(app_subdir.name.replace('app', ''))
                        apps.append((model_slug, template_slug, old_app_num, app_subdir))
                    except ValueError:
                        continue
    
    return apps


def get_next_flat_app_number(apps_dir: Path, model_slug: str) -> int:
    """Get the next available app number for flat structure."""
    model_dir = apps_dir / model_slug
    
    if not model_dir.exists():
        return 1
    
    max_num = 0
    for subdir in model_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith('app'):
            try:
                num = int(subdir.name.replace('app', ''))
                max_num = max(max_num, num)
            except ValueError:
                continue
    
    return max_num + 1


def migrate_apps(apps_dir: Path, dry_run: bool = True):
    """Migrate apps from template-based to flat structure."""
    apps = find_template_based_apps(apps_dir)
    
    if not apps:
        print("No template-based apps found. Nothing to migrate.")
        return
    
    print(f"Found {len(apps)} app(s) in template-based structure:\n")
    
    # Group by model for sequential numbering
    by_model = {}
    for model_slug, template_slug, old_app_num, app_dir in apps:
        if model_slug not in by_model:
            by_model[model_slug] = []
        by_model[model_slug].append((template_slug, old_app_num, app_dir))
    
    migration_plan = []
    
    for model_slug, model_apps in by_model.items():
        # Sort by (template, old_app_num) for consistent ordering
        model_apps.sort(key=lambda x: (x[0], x[1]))
        
        next_num = get_next_flat_app_number(apps_dir, model_slug)
        
        for template_slug, old_app_num, old_path in model_apps:
            new_path = apps_dir / model_slug / f"app{next_num}"
            migration_plan.append({
                'model_slug': model_slug,
                'template_slug': template_slug,
                'old_app_num': old_app_num,
                'new_app_num': next_num,
                'old_path': old_path,
                'new_path': new_path,
            })
            next_num += 1
    
    # Print migration plan
    print("Migration plan:")
    print("-" * 80)
    for item in migration_plan:
        print(f"  {item['model_slug']}/{item['template_slug']}/app{item['old_app_num']}")
        print(f"    → {item['model_slug']}/app{item['new_app_num']}")
        print()
    
    if dry_run:
        print("\n[DRY RUN] No files were moved. Run with --execute to apply changes.")
        return
    
    # Execute migration
    print("\nExecuting migration...")
    
    for item in migration_plan:
        old_path = item['old_path']
        new_path = item['new_path']
        
        print(f"  Moving: {old_path.name} → {new_path.name}")
        
        # Create parent directory if needed
        new_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Move the directory
        shutil.move(str(old_path), str(new_path))
        
        # Try to remove empty template directory
        template_dir = old_path.parent
        if template_dir.exists() and not any(template_dir.iterdir()):
            template_dir.rmdir()
            print(f"    Removed empty template dir: {template_dir.name}")
    
    print(f"\nMigration complete! Moved {len(migration_plan)} app(s).")
    print("\nIMPORTANT: You may need to update database records manually.")
    print("Run: python scripts/sync_generated_apps.py")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate apps from template-based to flat directory structure"
    )
    parser.add_argument(
        '--execute',
        action='store_true',
        help="Actually move files (default is dry-run)"
    )
    parser.add_argument(
        '--apps-dir',
        type=Path,
        default=Path(__file__).parent.parent / 'generated' / 'apps',
        help="Path to generated/apps directory"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.execute
    
    if not dry_run:
        confirm = input("This will move files. Are you sure? (yes/no): ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return
    
    migrate_apps(args.apps_dir, dry_run=dry_run)


if __name__ == '__main__':
    main()
