#!/usr/bin/env python3
"""
Migration script to add fixes_applied tracking columns to generated_applications table.

Tracks different types of fixes applied during the generation process:
- retry_fixes: Number of retry attempts during generation
- automatic_fixes: Script-based automatic fixes during generation
- llm_fixes: LLM-based fixes applied during generation
- manual_fixes: Manual fixes applied post-generation

Run with: python scripts/add_fixes_applied_columns.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from sqlalchemy import text
from app.factory import create_app
from app.extensions import db


def add_fixes_columns():
    """Add fixes tracking columns to generated_applications table."""
    app = create_app()
    
    with app.app_context():
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('generated_applications')]
        
        columns_to_add = [
            ('retry_fixes', 'INTEGER DEFAULT 0'),
            ('automatic_fixes', 'INTEGER DEFAULT 0'),
            ('llm_fixes', 'INTEGER DEFAULT 0'),
            ('manual_fixes', 'INTEGER DEFAULT 0'),
        ]
        
        added = []
        skipped = []
        
        for col_name, col_type in columns_to_add:
            if col_name in existing_columns:
                skipped.append(col_name)
                continue
            
            try:
                with db.engine.connect() as conn:
                    conn.execute(text(f'ALTER TABLE generated_applications ADD COLUMN {col_name} {col_type}'))
                    conn.commit()
                added.append(col_name)
                print(f"✓ Added column: {col_name}")
            except Exception as e:
                print(f"✗ Failed to add column {col_name}: {e}")
        
        if skipped:
            print(f"\nSkipped (already exist): {', '.join(skipped)}")
        
        if added:
            print(f"\nSuccessfully added {len(added)} column(s)")
        else:
            print("\nNo new columns added - all columns already exist")
        
        return len(added) > 0


if __name__ == '__main__':
    success = add_fixes_columns()
    sys.exit(0 if success else 1)
