"""
Backfill Docker Files to Generated Applications
==============================================

This script adds missing Docker-related files to existing generated applications,
making them containerizable and ready for deployment.

Files added:
- backend/Dockerfile
- backend/.dockerignore
- frontend/Dockerfile
- frontend/.dockerignore
- frontend/nginx.conf
- docker-compose.yml
- .env.example
- README.md (if missing)

Usage:
    python scripts/backfill_docker_files.py [--dry-run] [--model MODEL] [--app-num NUM]
"""

import argparse
import shutil
import sys
from pathlib import Path
from typing import List, Tuple

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.paths import GENERATED_APPS_DIR


def find_generated_apps(model_filter: str | None = None, app_num_filter: int | None = None) -> List[Tuple[str, int, Path]]:
    """
    Find all generated apps or filter by model/app_num.
    
    Returns:
        List of (model_slug, app_num, app_path) tuples
    """
    apps = []
    
    if not GENERATED_APPS_DIR.exists():
        print(f"Warning: Generated apps directory not found: {GENERATED_APPS_DIR}")
        return apps
    
    for model_dir in GENERATED_APPS_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        
        model_slug = model_dir.name
        
        # Filter by model if specified
        if model_filter and model_slug != model_filter:
            continue
        
        for app_dir in model_dir.iterdir():
            if not app_dir.is_dir() or not app_dir.name.startswith('app'):
                continue
            
            try:
                app_num = int(app_dir.name.replace('app', ''))
            except ValueError:
                continue
            
            # Filter by app_num if specified
            if app_num_filter is not None and app_num != app_num_filter:
                continue
            
            apps.append((model_slug, app_num, app_dir))
    
    return apps


def get_scaffolding_path() -> Path:
    """Get the scaffolding template directory."""
    return Path(__file__).parent.parent / "misc" / "scaffolding" / "react-flask"


def file_needs_update(dest: Path, source: Path) -> bool:
    """Check if destination file needs to be updated."""
    if not dest.exists():
        return True
    
    # Don't overwrite existing files by default (preserve user changes)
    return False


def backfill_app(app_path: Path, scaffolding_path: Path, dry_run: bool = False) -> dict:
    """
    Backfill Docker files for a single app.
    
    Returns:
        Dict with 'added', 'skipped', and 'errors' counts
    """
    result = {'added': 0, 'skipped': 0, 'errors': []}
    
    # Define file mappings: (source_path, dest_path, required_parent_dir)
    file_mappings = [
        # Backend files
        ('backend/Dockerfile', 'backend/Dockerfile', 'backend'),
        ('backend/.dockerignore', 'backend/.dockerignore', 'backend'),
        
        # Frontend files
        ('frontend/Dockerfile', 'frontend/Dockerfile', 'frontend'),
        ('frontend/.dockerignore', 'frontend/.dockerignore', 'frontend'),
        ('frontend/nginx.conf', 'frontend/nginx.conf', 'frontend'),
        
        # Root files
        ('docker-compose.yml', 'docker-compose.yml', None),
        ('.env.example', '.env.example', None),
        ('README.md', 'README.md', None),
    ]
    
    for source_rel, dest_rel, required_dir in file_mappings:
        source = scaffolding_path / source_rel
        dest = app_path / dest_rel
        
        # Skip if source template doesn't exist
        if not source.exists():
            result['errors'].append(f"Template missing: {source}")
            continue
        
        # Skip if required parent directory doesn't exist (e.g., no frontend)
        if required_dir and not (app_path / required_dir).exists():
            result['skipped'] += 1
            continue
        
        # Check if file needs update
        if not file_needs_update(dest, source):
            result['skipped'] += 1
            continue
        
        # Copy file
        try:
            if not dry_run:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
                print(f"  ✅ Added: {dest.relative_to(app_path)}")
            else:
                print(f"  [DRY RUN] Would add: {dest.relative_to(app_path)}")
            
            result['added'] += 1
        except Exception as e:
            error_msg = f"Failed to copy {source_rel}: {e}"
            result['errors'].append(error_msg)
            print(f"  ❌ {error_msg}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Backfill Docker files to generated applications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Only process specific model (e.g., openai_gpt-4)'
    )
    parser.add_argument(
        '--app-num',
        type=int,
        help='Only process specific app number'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing files (use with caution!)'
    )
    
    args = parser.parse_args()
    
    # Find scaffolding templates
    scaffolding_path = get_scaffolding_path()
    if not scaffolding_path.exists():
        print(f"❌ Error: Scaffolding directory not found: {scaffolding_path}")
        sys.exit(1)
    
    print(f"📦 Scaffolding source: {scaffolding_path}")
    print(f"🎯 Generated apps: {GENERATED_APPS_DIR}")
    
    if args.dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    
    if args.force:
        print("⚠️  FORCE MODE - Existing files will be overwritten!")
        # Update file_needs_update logic if force is enabled
        def force_check(dest: Path, source: Path) -> bool:
            return True
        global file_needs_update
        file_needs_update = force_check
    
    print()
    
    # Find apps to process
    apps = find_generated_apps(args.model, args.app_num)
    
    if not apps:
        print("❌ No apps found matching criteria")
        sys.exit(1)
    
    print(f"Found {len(apps)} app(s) to process\n")
    
    # Process each app
    total_added = 0
    total_skipped = 0
    total_errors = []
    
    for model_slug, app_num, app_path in apps:
        print(f"📁 Processing {model_slug}/app{app_num}")
        
        result = backfill_app(app_path, scaffolding_path, args.dry_run)
        
        total_added += result['added']
        total_skipped += result['skipped']
        total_errors.extend(result['errors'])
        
        if result['added'] == 0 and result['skipped'] == 0 and not result['errors']:
            print("  ℹ️  No changes needed")
        
        print()
    
    # Summary
    print("=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Apps processed: {len(apps)}")
    print(f"Files added: {total_added}")
    print(f"Files skipped: {total_skipped}")
    print(f"Errors: {len(total_errors)}")
    
    if total_errors:
        print("\n❌ Errors encountered:")
        for error in total_errors:
            print(f"  - {error}")
    
    if args.dry_run and total_added > 0:
        print("\n💡 Run without --dry-run to apply changes")
    
    return 0 if not total_errors else 1


if __name__ == "__main__":
    sys.exit(main())
