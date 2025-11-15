"""
Database Model ID Validation and Fix Script
===========================================

Validates all model IDs in the database against OpenRouter's live catalog
and suggests/applies corrections for invalid IDs.

Usage:
    # Dry run (check only, no changes):
    python scripts/validate_and_fix_model_ids.py

    # Apply fixes automatically:
    python scripts/validate_and_fix_model_ids.py --fix

    # Interactive mode (confirm each fix):
    python scripts/validate_and_fix_model_ids.py --fix --interactive
"""

import sys
import os
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Load .env early before importing app modules
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from {env_path}")
except Exception as e:
    print(f"⚠️ Could not load .env: {e}")
    # Try manual .env loading
    try:
        env_path = Path(__file__).parent.parent / '.env'
        if env_path.exists():
            for line in env_path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and (k not in os.environ):
                        os.environ[k] = v
            print(f"✅ Manually loaded .env from {env_path}")
    except Exception as e2:
        print(f"⚠️ Failed manual .env loading: {e2}")

def main():
    parser = argparse.ArgumentParser(description="Validate and fix model IDs in database")
    parser.add_argument('--fix', action='store_true', help='Apply corrections to database')
    parser.add_argument('--interactive', action='store_true', help='Confirm each fix interactively')
    parser.add_argument('--provider', type=str, help='Filter by provider (e.g., anthropic)')
    args = parser.parse_args()
    
    from app.factory import create_app
    from app.models import db, ModelCapability
    from app.services.model_validator import get_validator
    
    app = create_app()
    validator = get_validator()
    
    print("=" * 80)
    print("Model ID Validation Report")
    print("=" * 80)
    print()
    
    # Refresh catalog
    print("Fetching OpenRouter model catalog...")
    if not validator.refresh_catalog(force=True):
        print("❌ Failed to fetch OpenRouter catalog. Cannot proceed.")
        sys.exit(1)
    
    print("✅ Catalog refreshed successfully")
    print()
    
    # Validate all models
    with app.app_context():
        print("Validating database models...")
        results = validator.validate_all_database_models(app_context=app.app_context())
        
        if 'error' in results:
            print(f"❌ Error: {results['error']}")
            sys.exit(1)
        
        summary = results['summary']
        print()
        print(f"Total models:    {summary['total']}")
        print(f"✅ Valid:        {summary['valid']}")
        print(f"❌ Invalid:      {summary['invalid']}")
        print(f"💡 Fixable:      {summary['fixable']}")
        print()
        
        if summary['invalid'] == 0:
            print("🎉 All model IDs are valid!")
            return
        
        # Show invalid models
        print("-" * 80)
        print("Invalid Models:")
        print("-" * 80)
        
        for inv in results['invalid']:
            print(f"  • {inv['canonical_slug']}")
            print(f"    Current ID: {inv['model_id']}")
            print(f"    Provider: {inv['provider']}")
            
            # Find matching suggestion
            suggestion = next((s for s in results['suggestions'] if s['canonical_slug'] == inv['canonical_slug']), None)
            if suggestion:
                print(f"    💡 Suggested: {suggestion['suggested_id']}")
                print(f"       Reason: {suggestion['reason']}")
            else:
                print(f"    ⚠️  No automatic fix available")
            print()
        
        if not args.fix:
            print("=" * 80)
            print("ℹ️  Dry run mode (no changes made)")
            print("   Run with --fix to apply corrections")
            print("=" * 80)
            return
        
        # Apply fixes
        print("=" * 80)
        print("Applying Fixes")
        print("=" * 80)
        print()
        
        fixed_count = 0
        skipped_count = 0
        
        for suggestion in results['suggestions']:
            canonical_slug = suggestion['canonical_slug']
            current_id = suggestion['model_id']
            suggested_id = suggestion['suggested_id']
            reason = suggestion['reason']
            
            # Interactive mode confirmation
            if args.interactive:
                print(f"Model: {canonical_slug}")
                print(f"  Current: {current_id}")
                print(f"  Suggested: {suggested_id}")
                print(f"  Reason: {reason}")
                response = input("Apply fix? [y/N]: ").strip().lower()
                if response not in ['y', 'yes']:
                    skipped_count += 1
                    print("  ⏭️  Skipped")
                    print()
                    continue
            
            # Apply fix
            model = ModelCapability.query.filter_by(canonical_slug=canonical_slug).first()
            if not model:
                print(f"⚠️  Model not found: {canonical_slug}")
                skipped_count += 1
                continue
            
            # Determine which field to update (priority: hugging_face_id > base_model_id > model_id)
            if model.hugging_face_id == current_id:
                model.hugging_face_id = suggested_id
                field_updated = 'hugging_face_id'
            elif model.base_model_id == current_id:
                model.base_model_id = suggested_id
                field_updated = 'base_model_id'
            else:
                model.model_id = suggested_id
                # Also update base_model_id if it's derived from model_id
                if not model.base_model_id or model.base_model_id == current_id:
                    base_id = suggested_id.split(':')[0] if ':' in suggested_id else suggested_id
                    model.base_model_id = base_id
                field_updated = 'model_id, base_model_id'
            
            try:
                db.session.flush()
                fixed_count += 1
                print(f"✅ Fixed: {canonical_slug}")
                print(f"   {current_id} → {suggested_id}")
                print(f"   Updated field(s): {field_updated}")
                print()
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to fix {canonical_slug}: {e}")
                skipped_count += 1
                print()
        
        # Commit changes
        if fixed_count > 0:
            try:
                db.session.commit()
                print("=" * 80)
                print(f"✅ Successfully fixed {fixed_count} model(s)")
                if skipped_count > 0:
                    print(f"⏭️  Skipped {skipped_count} model(s)")
                print("=" * 80)
            except Exception as e:
                db.session.rollback()
                print(f"❌ Failed to commit changes: {e}")
                sys.exit(1)
        else:
            print("=" * 80)
            print("ℹ️  No fixes applied")
            print("=" * 80)


if __name__ == '__main__':
    main()
