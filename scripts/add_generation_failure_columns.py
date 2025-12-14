#!/usr/bin/env python
"""Migration script to add generation failure tracking columns.

Adds the following columns to generated_applications table:
- is_generation_failed: Boolean flag for failed generations
- failure_stage: Where generation failed (scaffold/backend/frontend/finalization)
- error_message: Human-readable error message
- generation_attempts: Number of retry attempts
- last_error_at: Timestamp of last error

Also migrates existing data:
- Sets is_generation_failed=True for apps with generation_status=FAILED
- Extracts errors from metadata_json into error_message field

Usage:
    python scripts/add_generation_failure_columns.py
"""

import sys
import os
import json
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

os.environ.setdefault('FLASK_ENV', 'development')


def run_migration():
    """Run the migration to add failure tracking columns."""
    from app.factory import create_app
    from app.extensions import db
    from sqlalchemy import text, inspect
    from app.models import GeneratedApplication
    from app.constants import AnalysisStatus
    
    app = create_app()
    
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('generated_applications')]
        
        print("=" * 60)
        print("Migration: Add Generation Failure Tracking Columns")
        print("=" * 60)
        
        # Track what we need to add
        new_columns = []
        
        # Check and add each column
        if 'is_generation_failed' not in columns:
            new_columns.append('is_generation_failed')
            db.session.execute(text(
                "ALTER TABLE generated_applications ADD COLUMN is_generation_failed BOOLEAN DEFAULT FALSE"
            ))
            print("✓ Added column: is_generation_failed")
        else:
            print("• Column already exists: is_generation_failed")
        
        if 'failure_stage' not in columns:
            new_columns.append('failure_stage')
            db.session.execute(text(
                "ALTER TABLE generated_applications ADD COLUMN failure_stage VARCHAR(50)"
            ))
            print("✓ Added column: failure_stage")
        else:
            print("• Column already exists: failure_stage")
        
        if 'error_message' not in columns:
            new_columns.append('error_message')
            db.session.execute(text(
                "ALTER TABLE generated_applications ADD COLUMN error_message TEXT"
            ))
            print("✓ Added column: error_message")
        else:
            print("• Column already exists: error_message")
        
        if 'generation_attempts' not in columns:
            new_columns.append('generation_attempts')
            db.session.execute(text(
                "ALTER TABLE generated_applications ADD COLUMN generation_attempts INTEGER DEFAULT 1"
            ))
            print("✓ Added column: generation_attempts")
        else:
            print("• Column already exists: generation_attempts")
        
        if 'last_error_at' not in columns:
            new_columns.append('last_error_at')
            db.session.execute(text(
                "ALTER TABLE generated_applications ADD COLUMN last_error_at DATETIME"
            ))
            print("✓ Added column: last_error_at")
        else:
            print("• Column already exists: last_error_at")
        
        db.session.commit()
        
        # Create index on is_generation_failed if we just added it
        if 'is_generation_failed' in new_columns:
            try:
                db.session.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_is_generation_failed "
                    "ON generated_applications (is_generation_failed)"
                ))
                db.session.commit()
                print("✓ Created index: idx_is_generation_failed")
            except Exception as e:
                print(f"• Index creation skipped (may already exist): {e}")
        
        print("\n" + "-" * 60)
        print("Migrating existing data...")
        print("-" * 60)
        
        # Migrate existing failed apps
        failed_apps = GeneratedApplication.query.filter(
            GeneratedApplication.generation_status == AnalysisStatus.FAILED
        ).all()
        
        migrated_count = 0
        for app in failed_apps:
            changed = False
            
            # Set is_generation_failed if not already set
            if not app.is_generation_failed:
                app.is_generation_failed = True
                changed = True
            
            # Extract errors from metadata_json if error_message not set
            if not app.error_message:
                metadata = app.get_metadata() or {}
                errors = metadata.get('errors', [])
                if errors:
                    # Combine all errors into a single message
                    if isinstance(errors, list):
                        app.error_message = '; '.join(str(e) for e in errors)
                    else:
                        app.error_message = str(errors)
                    changed = True
                    
                    # Try to infer failure stage from error message
                    if not app.failure_stage:
                        error_lower = app.error_message.lower()
                        if 'scaffold' in error_lower:
                            app.failure_stage = 'scaffold'
                        elif 'backend' in error_lower:
                            app.failure_stage = 'backend'
                        elif 'frontend' in error_lower:
                            app.failure_stage = 'frontend'
                        else:
                            app.failure_stage = 'unknown'
            
            if changed:
                migrated_count += 1
        
        db.session.commit()
        
        print(f"✓ Migrated {migrated_count} failed app records")
        
        # Summary
        total_apps = GeneratedApplication.query.count()
        failed_count = GeneratedApplication.query.filter(
            GeneratedApplication.is_generation_failed == True
        ).count()
        
        print("\n" + "=" * 60)
        print("Migration Complete!")
        print("=" * 60)
        print(f"Total apps in database: {total_apps}")
        print(f"Apps marked as failed: {failed_count}")
        print(f"New columns added: {len(new_columns)}")
        if new_columns:
            for col in new_columns:
                print(f"  - {col}")


if __name__ == '__main__':
    run_migration()
