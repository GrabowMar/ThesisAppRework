#!/usr/bin/env python3
"""
Test script to validate the batch generation fix.
Ensures exactly N apps are created (N = number of templates), not a pyramid pattern.
"""

import sys
import time
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import GeneratedApplication
from app.extensions import db


def count_apps_by_requirement(model_slug):
    """Count apps grouped by requirement slug."""
    app = create_app()
    
    with app.app_context():
        apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        
        # Group by requirement
        by_requirement = {}
        for app_record in apps:
            req = app_record.requirement_slug
            if req not in by_requirement:
                by_requirement[req] = []
            by_requirement[req].append(app_record.app_number)
        
        return by_requirement, len(apps)


def count_filesystem_apps(model_slug):
    """Count apps in filesystem grouped by requirement."""
    apps_dir = PROJECT_ROOT / 'generated' / 'apps' / model_slug
    
    if not apps_dir.exists():
        return {}, 0
    
    by_requirement = {}
    total = 0
    
    for req_dir in apps_dir.iterdir():
        if not req_dir.is_dir():
            continue
        
        req_name = req_dir.name
        app_dirs = [d for d in req_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
        
        if app_dirs:
            app_numbers = [int(d.name[3:]) for d in app_dirs]
            by_requirement[req_name] = sorted(app_numbers)
            total += len(app_numbers)
    
    return by_requirement, total


def main():
    """Run batch generation validation test."""
    
    print("\n" + "=" * 80)
    print("Batch Generation Fix - Validation Test")
    print("=" * 80)
    
    # Configuration
    model_slug = "anthropic_claude-4.5-haiku-20251001"
    expected_templates = 4  # User wanted to generate 4 apps
    
    print(f"\nTest Configuration:")
    print(f"  Model: {model_slug}")
    print(f"  Expected templates: {expected_templates}")
    print(f"  Expected total apps: {expected_templates}")
    print(f"  Expected apps per requirement: 1")
    
    print("\n" + "-" * 80)
    print("Database Records")
    print("-" * 80)
    
    db_apps, db_total = count_apps_by_requirement(model_slug)
    
    if db_total == 0:
        print("✓ No apps found in database (ready for fresh generation)")
    else:
        print(f"\n📊 Total apps in database: {db_total}")
        print(f"\nApps by requirement:")
        for req, app_nums in sorted(db_apps.items()):
            print(f"  {req}: {len(app_nums)} apps - {app_nums}")
            if len(app_nums) > 1:
                print(f"    ⚠️  WARNING: Multiple apps for same requirement (pyramid bug!)")
    
    print("\n" + "-" * 80)
    print("Filesystem Directories")
    print("-" * 80)
    
    fs_apps, fs_total = count_filesystem_apps(model_slug)
    
    if fs_total == 0:
        print("✓ No apps found in filesystem (ready for fresh generation)")
    else:
        print(f"\n📁 Total apps in filesystem: {fs_total}")
        print(f"\nApps by requirement:")
        for req, app_nums in sorted(fs_apps.items()):
            print(f"  {req}: {len(app_nums)} apps - {app_nums}")
            if len(app_nums) > 1:
                print(f"    ⚠️  WARNING: Multiple apps for same requirement (pyramid bug!)")
    
    print("\n" + "=" * 80)
    print("Validation Results")
    print("=" * 80)
    
    # Check results
    issues = []
    
    if db_total > 0:
        if db_total != expected_templates:
            issues.append(f"Database has {db_total} apps, expected {expected_templates}")
        
        for req, app_nums in db_apps.items():
            if len(app_nums) > 1:
                issues.append(f"Requirement '{req}' has {len(app_nums)} apps (pyramid bug detected)")
    
    if fs_total > 0:
        if fs_total != expected_templates:
            issues.append(f"Filesystem has {fs_total} apps, expected {expected_templates}")
        
        for req, app_nums in fs_apps.items():
            if len(app_nums) > 1:
                issues.append(f"Requirement '{req}' has {len(app_nums)} filesystem apps (pyramid bug detected)")
    
    if not issues:
        if db_total == 0 and fs_total == 0:
            print("\n✅ READY FOR TESTING")
            print("\nNext steps:")
            print("  1. Start Flask app: python src/main.py")
            print("  2. Navigate to batch generation wizard")
            print("  3. Select 4 templates and 1 model")
            print("  4. Run generation")
            print("  5. Re-run this script to validate")
        else:
            print("\n✅ TEST PASSED")
            print(f"\nGenerated exactly {db_total} apps (1 per requirement)")
            print("No pyramid pattern detected!")
    else:
        print("\n❌ TEST FAILED")
        print(f"\nIssues found ({len(issues)}):")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print("\nThe nested loop bug may still be present.")
        print("Check src/static/js/sample_generator_wizard.js")
    
    print("\n")
    
    return 0 if not issues else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
