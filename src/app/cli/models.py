#!/usr/bin/env python3
"""
Model Management CLI
===================

Convenience commands for model validation and migration.
Uses permanent service layer instead of one-time scripts.

Usage:
    python -m app.cli.models validate          # Check all models
    python -m app.cli.models fix               # Auto-fix invalid models
    python -m app.cli.models fix --dry-run     # Preview fixes
    python -m app.cli.models normalize         # Fix provider namespaces only
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app import create_app
from app.services.model_migration import get_migration_service
from app.services.model_validator import get_validator


def print_summary(result: dict):
    """Pretty print validation/fix summary."""
    summary = result.get('summary', {})
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"Total models:    {summary.get('total', 0)}")
    print(f"✅ Valid:        {summary.get('valid', 0)}")
    print(f"❌ Invalid:      {summary.get('invalid', 0)}")
    
    if 'fixed' in summary:
        print(f"🔧 Fixed:        {summary['fixed']}")
    if 'unfixable' in summary:
        print(f"⚠️  Unfixable:   {summary['unfixable']}")
    
    if summary.get('dry_run'):
        print("\n⚠️  DRY RUN MODE - No changes applied")
    
    print("=" * 80)


def cmd_validate(args):
    """Validate all models against OpenRouter catalog."""
    print("=" * 80)
    print("Model Validation")
    print("=" * 80)
    print("\nFetching OpenRouter catalog...")
    
    app = create_app()
    with app.app_context():
        migration = get_migration_service()
        result = migration.validate_and_fix_all_models(dry_run=True, auto_fix=False)
        
        print_summary(result)
        
        # Show invalid models
        invalid = result.get('invalid', [])
        if invalid:
            print("\n❌ Invalid Models:")
            for entry in invalid:
                print(f"  • {entry['slug']}")
                print(f"    Model ID: {entry['model_id']}")
        
        # Show suggestions
        unfixable = result.get('unfixable', [])
        if unfixable:
            print("\n⚠️  Unfixable Models:")
            for entry in unfixable:
                print(f"  • {entry['slug']}")
                print(f"    Model ID: {entry.get('model_id', 'N/A')}")
                print(f"    Reason: {entry.get('reason', 'Unknown')}")
        
        return 0 if not invalid else 1


def cmd_fix(args):
    """Auto-fix invalid models."""
    dry_run = '--dry-run' in args
    
    print("=" * 80)
    print(f"Model Auto-Fix {'(DRY RUN)' if dry_run else ''}")
    print("=" * 80)
    print("\nFetching OpenRouter catalog...")
    
    app = create_app()
    with app.app_context():
        migration = get_migration_service()
        result = migration.validate_and_fix_all_models(dry_run=dry_run, auto_fix=True)
        
        # Show what was fixed
        fixed = result.get('fixed', [])
        if fixed:
            print("\n🔧 Fixed Models:")
            for entry in fixed:
                print(f"  • {entry['slug']}")
                print(f"    {entry['old_id']} → {entry['new_id']}")
                print(f"    Reason: {entry['reason']}")
        
        print_summary(result)
        
        if not dry_run and fixed:
            print(f"\n✅ Successfully applied {len(fixed)} fixes to database")
        
        return 0


def cmd_normalize(args):
    """Normalize provider namespaces only."""
    dry_run = '--dry-run' in args
    
    print("=" * 80)
    print(f"Provider Namespace Normalization {'(DRY RUN)' if dry_run else ''}")
    print("=" * 80)
    print("\nFetching OpenRouter catalog...")
    
    app = create_app()
    with app.app_context():
        migration = get_migration_service()
        result = migration.normalize_provider_namespaces(dry_run=dry_run)
        
        # Show what was fixed
        fixed = result.get('fixed', [])
        if fixed:
            print("\n🔧 Normalized Models:")
            for entry in fixed:
                print(f"  • {entry['slug']}")
                print(f"    {entry['old_id']} → {entry['new_id']}")
        
        print_summary(result)
        
        if not dry_run and fixed:
            print(f"\n✅ Successfully normalized {len(fixed)} model IDs")
        
        return 0


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    
    command = sys.argv[1]
    args = sys.argv[2:]
    
    commands = {
        'validate': cmd_validate,
        'fix': cmd_fix,
        'normalize': cmd_normalize,
    }
    
    if command not in commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1
    
    try:
        return commands[command](args)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
