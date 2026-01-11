#!/usr/bin/env python3
"""
Data Wipe Script
================

Completely wipes all generated applications, database records, and associated files.
This ensures a clean slate for testing prompt logging.

Usage:
    python scripts/wipe_all_data.py [--confirm]

Options:
    --confirm    Skip confirmation prompt and proceed with wipe
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / 'src'))

from app import create_app
from app.extensions import db
from app.models.core import GeneratedApplication, PortConfiguration
from app.models.pipeline import PipelineExecution
from app.utils.logging_config import get_logger

logger = get_logger('data_wipe')


def confirm_wipe(skip_confirm: bool = False) -> bool:
    """Ask user to confirm the wipe operation."""
    if skip_confirm:
        return True

    print("\n" + "=" * 70)
    print("WARNING: DATA WIPE OPERATION")
    print("=" * 70)
    print("\nThis will PERMANENTLY DELETE:")
    print("  - All generated applications from database")
    print("  - All pipeline executions and jobs")
    print("  - All port configurations")
    print("  - All files in generated/apps/")
    print("  - All files in generated/raw/payloads/")
    print("  - All files in generated/raw/responses/")
    print("  - All files in generated/metadata/indices/runs/")
    print("\nThis operation CANNOT be undone!")
    print("=" * 70)

    response = input("\nType 'WIPE ALL DATA' to confirm: ")
    return response.strip() == "WIPE ALL DATA"


def wipe_database_tables(app):
    """Delete all records from application-related tables."""
    logger.info("Wiping database tables...")

    with app.app_context():
        try:
            # Delete in order to respect foreign key constraints
            deleted_pipelines = PipelineExecution.query.delete()
            logger.info(f"  Deleted {deleted_pipelines} pipeline executions")

            deleted_apps = GeneratedApplication.query.delete()
            logger.info(f"  Deleted {deleted_apps} generated applications")

            deleted_ports = PortConfiguration.query.delete()
            logger.info(f"  Deleted {deleted_ports} port configurations")

            db.session.commit()
            logger.info("Database tables wiped successfully")

            return {
                'apps': deleted_apps,
                'pipelines': deleted_pipelines,
                'ports': deleted_ports
            }

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error wiping database: {e}")
            raise


def wipe_generated_files():
    """Delete all generated application files and metadata."""
    logger.info("Wiping generated files...")

    generated_dir = project_root / 'generated'

    # Directories to completely clear
    dirs_to_clear = [
        generated_dir / 'apps',
        generated_dir / 'raw' / 'payloads',
        generated_dir / 'raw' / 'responses',
        generated_dir / 'metadata' / 'indices' / 'runs'
    ]

    stats = {
        'dirs_cleared': 0,
        'files_deleted': 0,
        'errors': []
    }

    for dir_path in dirs_to_clear:
        if not dir_path.exists():
            logger.warning(f"  Directory does not exist: {dir_path}")
            continue

        try:
            # Count files before deletion
            file_count = sum(1 for _ in dir_path.rglob('*') if _.is_file())

            # Delete all contents but keep the directory
            for item in dir_path.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)

            logger.info(f"  Cleared {dir_path} ({file_count} files)")
            stats['dirs_cleared'] += 1
            stats['files_deleted'] += file_count

        except Exception as e:
            error_msg = f"Error clearing {dir_path}: {e}"
            logger.error(f"  {error_msg}")
            stats['errors'].append(error_msg)

    return stats


def verify_wipe():
    """Verify that the wipe was successful."""
    logger.info("Verifying wipe operation...")

    issues = []

    # Check database
    app = create_app()
    with app.app_context():
        app_count = GeneratedApplication.query.count()
        pipeline_count = PipelineExecution.query.count()

        if app_count > 0:
            issues.append(f"Database still has {app_count} applications")
        if pipeline_count > 0:
            issues.append(f"Database still has {pipeline_count} pipelines")

    # Check filesystem
    generated_dir = project_root / 'generated'
    apps_dir = generated_dir / 'apps'

    if apps_dir.exists():
        remaining_apps = [d for d in apps_dir.iterdir() if d.is_dir()]
        if remaining_apps:
            issues.append(f"generated/apps still has {len(remaining_apps)} directories")

    if issues:
        logger.warning("Verification found issues:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        return False
    else:
        logger.info("Verification passed - all data wiped successfully")
        return True


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Wipe all generated application data')
    parser.add_argument('--confirm', action='store_true',
                       help='Skip confirmation prompt')
    args = parser.parse_args()

    # Confirm operation
    if not confirm_wipe(args.confirm):
        print("\nOperation cancelled.")
        return 1

    print("\nStarting data wipe operation...")
    start_time = datetime.now()

    try:
        # Create app context
        app = create_app()

        # Wipe database
        print("\n[1/3] Wiping database tables...")
        db_stats = wipe_database_tables(app)
        print(f"  [OK] Deleted {db_stats['apps']} apps, {db_stats['pipelines']} pipelines, {db_stats['ports']} ports")

        # Wipe files
        print("\n[2/3] Wiping generated files...")
        file_stats = wipe_generated_files()
        print(f"  [OK] Cleared {file_stats['dirs_cleared']} directories, deleted {file_stats['files_deleted']} files")

        if file_stats['errors']:
            print(f"  [WARN] {len(file_stats['errors'])} errors occurred during file deletion")

        # Verify
        print("\n[3/3] Verifying wipe...")
        success = verify_wipe()

        elapsed = (datetime.now() - start_time).total_seconds()

        if success:
            print(f"\n[OK] Data wipe completed successfully in {elapsed:.2f}s")
            print("\nNext steps:")
            print("  1. Generate new applications")
            print("  2. Prompts will be automatically captured in generated/raw/")
            return 0
        else:
            print(f"\n[WARN] Data wipe completed with warnings in {elapsed:.2f}s")
            print("Please check the logs for details.")
            return 1

    except Exception as e:
        print(f"\n[ERROR] Data wipe failed: {e}")
        logger.error(f"Data wipe failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
