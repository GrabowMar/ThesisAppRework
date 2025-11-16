#!/usr/bin/env python3
"""
Database migration script to add missing_since column to generated_applications table.

This adds support for the 7-day grace period before orphan app deletion.
Run this script once to update the schema.

Usage:
    python scripts/add_missing_since_column.py
"""

import sys
from pathlib import Path

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.extensions import db
from sqlalchemy import text


def main():
    """Add missing_since column to generated_applications table."""
    
    app = create_app()
    
    with app.app_context():
        print("\n" + "=" * 80)
        print("Database Migration: Add missing_since Column")
        print("=" * 80)
        print("\nThis will add the 'missing_since' column to the generated_applications table.")
        print("This column tracks when an app's filesystem directory first went missing.")
        print("\nChanges:")
        print("  - Column: missing_since (DATETIME, nullable)")
        print("  - Default: NULL (not missing)")
        print("  - Purpose: Enable 7-day grace period before orphan app deletion")
        print("\n" + "=" * 80)
        
        # Check if column already exists
        inspector = db.inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('generated_applications')]
        
        if 'missing_since' in columns:
            print("\n✓ Column 'missing_since' already exists - no migration needed")
            print("\n" + "=" * 80)
            return
        
        print("\nPress Enter to apply migration (or Ctrl+C to cancel)...")
        input()
        
        try:
            # Add column using SQLAlchemy text for cross-database compatibility
            print("\n[1/2] Adding missing_since column...")
            
            # SQLite-compatible ALTER TABLE
            with db.engine.connect() as conn:
                conn.execute(text(
                    "ALTER TABLE generated_applications "
                    "ADD COLUMN missing_since DATETIME"
                ))
                conn.commit()
            
            print("  ✓ Column added successfully")
            
            # Verify column was added
            print("\n[2/2] Verifying migration...")
            inspector = db.inspect(db.engine)
            columns_after = [col['name'] for col in inspector.get_columns('generated_applications')]
            
            if 'missing_since' in columns_after:
                print("  ✓ Migration verified")
            else:
                print("  ✗ Migration verification failed - column not found")
                sys.exit(1)
            
            print("\n" + "=" * 80)
            print("✅ Migration completed successfully!")
            print("=" * 80)
            print("\nThe maintenance service will now:")
            print("  1. Mark apps as missing when filesystem directory disappears")
            print("  2. Keep marked apps for 7 days before deletion")
            print("  3. Clear the flag if filesystem directory is restored")
            print("\nRun manual maintenance with: ./start.ps1 -Mode Maintenance")
            print()
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✗ Migration cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
