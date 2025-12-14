#!/usr/bin/env python
"""Cleanup script for failed generation files.

Removes filesystem directories for apps that have is_generation_failed=True
in the database. This helps clean up partial/incomplete app files that were
left behind after generation failures.

Options:
    --dry-run       Show what would be deleted without actually deleting
    --force         Delete without confirmation prompt
    --model SLUG    Only cleanup apps for specific model slug

Usage:
    python scripts/cleanup_failed_generation_files.py --dry-run
    python scripts/cleanup_failed_generation_files.py --force
    python scripts/cleanup_failed_generation_files.py --model anthropic_claude-3-5-haiku
"""

import sys
import os
import shutil
import argparse
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

os.environ.setdefault('FLASK_ENV', 'development')


def cleanup_failed_apps(dry_run: bool = True, force: bool = False, model_filter: str = None):
    """Cleanup filesystem directories for failed generation apps."""
    from app.factory import create_app
    from app.extensions import db
    from app.models import GeneratedApplication
    from app.constants import AnalysisStatus
    from app.paths import GENERATED_APPS_DIR
    
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Cleanup: Failed Generation Files")
        print("=" * 60)
        print(f"Mode: {'DRY RUN' if dry_run else 'ACTUAL DELETION'}")
        if model_filter:
            print(f"Filter: model_slug = {model_filter}")
        print()
        
        # Query for failed apps
        query = GeneratedApplication.query.filter(
            (GeneratedApplication.is_generation_failed == True) |
            (GeneratedApplication.generation_status == AnalysisStatus.FAILED)
        )
        
        if model_filter:
            query = query.filter(GeneratedApplication.model_slug == model_filter)
        
        failed_apps = query.all()
        
        if not failed_apps:
            print("No failed generation apps found.")
            return
        
        print(f"Found {len(failed_apps)} failed generation app(s):\n")
        
        apps_with_files = []
        apps_no_files = []
        
        for app_record in failed_apps:
            app_dir = GENERATED_APPS_DIR / app_record.model_slug / f'app{app_record.app_number}'
            failure_stage = app_record.failure_stage or 'unknown'
            error_msg = app_record.error_message or 'No error message'
            
            # Truncate error message for display
            if len(error_msg) > 60:
                error_msg = error_msg[:57] + '...'
            
            has_files = app_dir.exists()
            status_icon = "📁" if has_files else "❌"
            
            print(f"  {status_icon} {app_record.model_slug}/app{app_record.app_number}")
            print(f"      Stage: {failure_stage}")
            print(f"      Error: {error_msg}")
            print(f"      Path: {app_dir}")
            print(f"      Files exist: {has_files}")
            print()
            
            if has_files:
                apps_with_files.append((app_record, app_dir))
            else:
                apps_no_files.append(app_record)
        
        print("-" * 60)
        print(f"Apps with files to delete: {len(apps_with_files)}")
        print(f"Apps with no files: {len(apps_no_files)}")
        print()
        
        if not apps_with_files:
            print("No files to cleanup.")
            return
        
        if dry_run:
            print("DRY RUN - No files were deleted.")
            print("Run without --dry-run to actually delete files.")
            return
        
        if not force:
            confirm = input(f"Delete {len(apps_with_files)} app directories? (yes/no): ")
            if confirm.lower() not in ('yes', 'y'):
                print("Aborted.")
                return
        
        # Actually delete files
        deleted_count = 0
        error_count = 0
        
        for app_record, app_dir in apps_with_files:
            try:
                print(f"Deleting {app_dir}...", end=" ")
                shutil.rmtree(app_dir)
                print("✓")
                deleted_count += 1
            except Exception as e:
                print(f"✗ Error: {e}")
                error_count += 1
        
        print()
        print("=" * 60)
        print("Cleanup Complete!")
        print("=" * 60)
        print(f"Deleted: {deleted_count} directories")
        print(f"Errors: {error_count}")


def main():
    parser = argparse.ArgumentParser(
        description="Cleanup filesystem directories for failed generation apps"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Delete without confirmation prompt'
    )
    parser.add_argument(
        '--model',
        type=str,
        help='Only cleanup apps for specific model slug'
    )
    
    args = parser.parse_args()
    
    # Default to dry-run if neither flag is specified
    if not args.dry_run and not args.force:
        args.dry_run = True
    
    cleanup_failed_apps(
        dry_run=args.dry_run,
        force=args.force,
        model_filter=args.model
    )


if __name__ == '__main__':
    main()
