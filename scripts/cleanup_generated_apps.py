#!/usr/bin/env python3
"""
⚠️  DEPRECATED - Use start.ps1 -Mode Maintenance instead
================================================

Legacy cleanup script to wipe generated apps from database and filesystem.
This script is now DEPRECATED in favor of the new maintenance system with:
  - 7-day grace period before deletion (safer)
  - Manual control via start.ps1 -Mode Maintenance
  - Automatic tracking of missing apps (missing_since timestamp)

If you need to perform immediate cleanup without the grace period,
this script can still be used, but be aware it bypasses safety mechanisms.

Use this ONLY for emergency cleanup after bugs create duplicate apps.
For normal maintenance, use: ./start.ps1 -Mode Maintenance
"""

import sys
import shutil
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import GeneratedApplication, PortConfiguration
from app.extensions import db


def main():
    """Wipe generated apps and port allocations for specified model."""
    
    app = create_app()
    
    with app.app_context():
        # Prompt for model slug
        print("\n" + "=" * 80)
        print("Generated Apps Cleanup Utility")
        print("=" * 80)
        print("\nThis will DELETE:")
        print("  1. All GeneratedApplication database records for the specified model")
        print("  2. All filesystem directories under generated/apps/{model}/")
        print("  3. All PortConfiguration records (reset port allocations)")
        print("\n⚠️  WARNING: This action cannot be undone!")
        print("=" * 80)
        
        # Get model slug
        model_slug = input("\nEnter model slug to wipe (e.g., 'anthropic_claude-4.5-haiku-20251001'): ").strip()
        
        if not model_slug:
            print("❌ No model slug provided. Exiting.")
            return
        
        # Check what exists
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        app_count = len(apps)
        
        if app_count == 0:
            print(f"\n✓ No database records found for model '{model_slug}'")
        else:
            print(f"\n📊 Found {app_count} GeneratedApplication records:")
            for app_record in apps[:10]:  # Show first 10
                print(f"   - {app_record.requirement_slug}/app{app_record.app_number}")
            if app_count > 10:
                print(f"   ... and {app_count - 10} more")
        
        # Check filesystem
        apps_dir = PROJECT_ROOT / 'generated' / 'apps' / model_slug
        fs_exists = apps_dir.exists()
        
        if fs_exists:
            subdirs = [d for d in apps_dir.iterdir() if d.is_dir()]
            print(f"\n📁 Found filesystem directory with {len(subdirs)} requirement folders")
            print(f"   Path: {apps_dir}")
        else:
            print(f"\n✓ No filesystem directory found at: {apps_dir}")
        
        # Check port allocations
        port_count = PortConfiguration.query.count()
        print(f"\n🔌 Found {port_count} PortConfiguration records")
        
        # Confirm deletion
        print("\n" + "=" * 80)
        print("⚠️  FINAL CONFIRMATION")
        print("=" * 80)
        
        actions = []
        if app_count > 0:
            actions.append(f"Delete {app_count} database records for {model_slug}")
        if fs_exists:
            actions.append(f"Delete filesystem directory: {apps_dir}")
        if port_count > 0:
            actions.append(f"Delete all {port_count} port allocation records")
        
        if not actions:
            print("\n✓ Nothing to delete. Exiting.")
            return
        
        print("\nActions to perform:")
        for i, action in enumerate(actions, 1):
            print(f"  {i}. {action}")
        
        print("\nType 'DELETE' to confirm (or anything else to cancel): ", end='')
        confirmation = input().strip()
        
        if confirmation != 'DELETE':
            print("\n❌ Cancelled. No changes made.")
            return
        
        print("\n" + "=" * 80)
        print("🗑️  Performing Cleanup...")
        print("=" * 80)
        
        # Delete database records
        if app_count > 0:
            print(f"\n[1/3] Deleting {app_count} GeneratedApplication records...")
            deleted = GeneratedApplication.query.filter_by(model_slug=model_slug).delete()
            db.session.commit()
            print(f"   ✓ Deleted {deleted} records")
        
        # Delete filesystem directory
        if fs_exists:
            print(f"\n[2/3] Deleting filesystem directory...")
            shutil.rmtree(apps_dir)
            print(f"   ✓ Deleted: {apps_dir}")
        
        # Delete port allocations
        if port_count > 0:
            print(f"\n[3/3] Deleting {port_count} PortConfiguration records...")
            deleted = PortConfiguration.query.delete()
            db.session.commit()
            print(f"   ✓ Deleted {deleted} records")
        
        print("\n" + "=" * 80)
        print("✅ Cleanup completed successfully!")
        print("=" * 80)
        print("\nYou can now:")
        print("  1. Re-run batch generation with the fixed code")
        print("  2. Verify exactly N apps are created (N = number of templates)")
        print("  3. Check that no duplicate apps appear under each requirement folder")
        print("\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
