#!/usr/bin/env python3
"""
Migration script to mark existing failed apps retroactively.

This script scans all GeneratedApplication records in the database and marks
apps as failed based on:
1. Errors in their metadata JSON
2. generation_status = FAILED but is_generation_failed not set
3. Missing or incomplete filesystem directories with errors in metadata

Usage:
    python scripts/mark_existing_failed_apps.py [--dry-run] [--verbose]

Options:
    --dry-run   Show what would be changed without making changes
    --verbose   Show detailed information about each app checked
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import GeneratedApplication
from app.constants import AnalysisStatus
from app.utils.time import utc_now


def determine_failure_stage(errors: list, metadata: dict) -> str:
    """Determine the failure stage based on error messages."""
    if not errors:
        return 'unknown'
    
    error_text = ' '.join(str(e).lower() for e in errors)
    
    if 'scaffold' in error_text:
        return 'scaffold'
    elif 'backend' in error_text:
        if 'admin' in error_text:
            return 'backend'  # backend admin failed
        return 'backend'
    elif 'frontend' in error_text:
        if 'admin' in error_text:
            return 'frontend'  # frontend admin failed
        return 'frontend'
    elif not metadata.get('scaffolded'):
        return 'scaffold'
    elif not metadata.get('backend_generated'):
        return 'backend'
    elif not metadata.get('frontend_generated'):
        return 'frontend'
    else:
        return 'finalization'


def write_error_log_for_app(app_dir: Path, model_slug: str, app_num: int, 
                            failure_stage: str, error_message: str, errors: list) -> bool:
    """Write a generation_error.txt file for a failed app."""
    try:
        error_log_path = app_dir / 'generation_error.txt'
        
        # Don't overwrite existing error log
        if error_log_path.exists():
            return False
            
        timestamp = datetime.utcnow().isoformat()
        
        content_lines = [
            "=" * 60,
            "GENERATION FAILURE LOG (Retroactive)",
            "=" * 60,
            f"",
            f"Timestamp: {timestamp}",
            f"Model: {model_slug}",
            f"App Number: {app_num}",
            f"Failure Stage: {failure_stage}",
            f"",
            "=" * 60,
            "ERROR MESSAGE",
            "=" * 60,
            f"{error_message}",
            f"",
        ]
        
        if errors:
            content_lines.extend([
                "=" * 60,
                "DETAILED ERRORS",
                "=" * 60,
            ])
            for i, err in enumerate(errors, 1):
                content_lines.append(f"{i}. {err}")
            content_lines.append("")
        
        content_lines.extend([
            "=" * 60,
            "NOTES",
            "=" * 60,
            "This log was created retroactively by the migration script.",
            "This application failed during generation and is marked as 'dead'.",
            "It will be skipped by all analyzers.",
            "",
            "To retry generation, use the 'Retry Generation' feature in the UI.",
            "=" * 60,
        ])
        
        app_dir.mkdir(parents=True, exist_ok=True)
        error_log_path.write_text('\n'.join(content_lines), encoding='utf-8')
        return True
        
    except Exception as e:
        print(f"  Warning: Failed to write error log: {e}")
        return False


def mark_existing_failed_apps(dry_run: bool = False, verbose: bool = False):
    """Scan all apps and mark failed ones."""
    
    app = create_app()
    
    with app.app_context():
        # Get all apps
        all_apps = GeneratedApplication.query.all()
        
        print(f"Scanning {len(all_apps)} applications...")
        print()
        
        apps_to_mark = []
        already_marked = 0
        healthy_apps = 0
        
        for app_record in all_apps:
            model_slug = app_record.model_slug
            app_num = app_record.app_number
            
            # Check if already marked as failed - but might need error log
            if app_record.is_generation_failed:
                already_marked += 1
                
                # Check if error log exists
                app_dir = Path('generated/apps') / model_slug / f'app{app_num}'
                error_log_path = app_dir / 'generation_error.txt'
                
                if not error_log_path.exists() and app_dir.exists():
                    # Need to create error log for already-marked app
                    metadata = app_record.get_metadata() or {}
                    errors = metadata.get('errors', [])
                    apps_to_mark.append({
                        'record': app_record,
                        'model_slug': model_slug,
                        'app_num': app_num,
                        'failure_stage': app_record.failure_stage or 'unknown',
                        'error_message': app_record.error_message or 'Generation failed',
                        'errors': errors,
                        'needs_db_update': False,  # DB already updated, just need log
                        'needs_error_log': True
                    })
                    if verbose:
                        print(f"  [LOG]  {model_slug}/app{app_num} - Already marked, needs error log")
                else:
                    if verbose:
                        print(f"  [SKIP] {model_slug}/app{app_num} - Already marked as failed")
                continue
            
            # Get metadata
            metadata = app_record.get_metadata() or {}
            errors = metadata.get('errors', [])
            success = metadata.get('success', True)
            
            # Check conditions for failure
            should_mark_failed = False
            failure_stage = None
            error_message = None
            
            # Condition 1: generation_status is FAILED
            if app_record.generation_status == AnalysisStatus.FAILED:
                should_mark_failed = True
                failure_stage = determine_failure_stage(errors, metadata)
                error_message = '; '.join(str(e) for e in errors) if errors else 'Generation failed (status=FAILED)'
            
            # Condition 2: Has errors in metadata
            elif errors and not success:
                should_mark_failed = True
                failure_stage = determine_failure_stage(errors, metadata)
                error_message = '; '.join(str(e) for e in errors)
            
            # Condition 3: success=False in metadata
            elif success is False:
                should_mark_failed = True
                failure_stage = determine_failure_stage(errors, metadata)
                error_message = '; '.join(str(e) for e in errors) if errors else 'Generation failed (success=false in metadata)'
            
            if should_mark_failed:
                apps_to_mark.append({
                    'record': app_record,
                    'model_slug': model_slug,
                    'app_num': app_num,
                    'failure_stage': failure_stage,
                    'error_message': error_message,
                    'errors': errors,
                    'needs_db_update': True,
                    'needs_error_log': True
                })
                
                if verbose:
                    print(f"  [FAIL] {model_slug}/app{app_num}")
                    print(f"         Stage: {failure_stage}")
                    print(f"         Error: {error_message[:100]}..." if len(error_message or '') > 100 else f"         Error: {error_message}")
            else:
                healthy_apps += 1
                if verbose:
                    print(f"  [OK]   {model_slug}/app{app_num}")
        
        print()
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total apps scanned:     {len(all_apps)}")
        print(f"Already marked failed:  {already_marked}")
        print(f"Healthy apps:           {healthy_apps}")
        print(f"Apps to mark as failed: {len(apps_to_mark)}")
        print()
        
        if not apps_to_mark:
            print("No apps need to be marked as failed.")
            return
        
        if dry_run:
            print("DRY RUN - No changes will be made.")
            print()
            print("Apps that would be marked as failed:")
            for item in apps_to_mark:
                print(f"  - {item['model_slug']}/app{item['app_num']} (stage: {item['failure_stage']})")
            return
        
        # Apply changes
        print("Applying changes...")
        print()
        
        apps_dir = Path('generated/apps')
        
        for item in apps_to_mark:
            record = item['record']
            model_slug = item['model_slug']
            app_num = item['app_num']
            failure_stage = item['failure_stage']
            error_message = item['error_message']
            errors = item['errors']
            needs_db_update = item.get('needs_db_update', True)
            needs_error_log = item.get('needs_error_log', True)
            
            print(f"  Processing {model_slug}/app{app_num}...")
            
            # Update database record (if needed)
            if needs_db_update:
                record.is_generation_failed = True
                record.failure_stage = failure_stage
                record.error_message = error_message
                record.last_error_at = utc_now()
                if record.generation_status != AnalysisStatus.FAILED:
                    record.generation_status = AnalysisStatus.FAILED
                print(f"    Updated database record")
            
            # Write error log file (if needed)
            if needs_error_log:
                app_dir = apps_dir / model_slug / f'app{app_num}'
                if app_dir.exists():
                    if write_error_log_for_app(app_dir, model_slug, app_num, 
                                               failure_stage, error_message, errors):
                        print(f"    Written error log to {app_dir / 'generation_error.txt'}")
                    else:
                        print(f"    Error log already exists or could not be written")
                else:
                    print(f"    App directory does not exist: {app_dir}")
        
        # Commit all changes
        try:
            db.session.commit()
            print()
            print(f"Successfully marked {len(apps_to_mark)} apps as failed.")
        except Exception as e:
            db.session.rollback()
            print(f"Error committing changes: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description='Mark existing failed apps retroactively',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without making changes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed information about each app checked')
    
    args = parser.parse_args()
    
    mark_existing_failed_apps(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == '__main__':
    main()
