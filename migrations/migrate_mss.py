"""
Database migration script for MSS (Model Selection Score) columns.

This script adds Chapter 4 MSS-specific columns to the model_benchmark_cache table.
Run this from the project root with: python -m migrations.migrate_mss

Requirements:
- Flask app context
- Database connection configured
- SQLAlchemy models loaded
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.app import create_app
from src.app.extensions import db
from sqlalchemy import text


def run_migration():
    """Run the MSS migration."""
    app = create_app()

    with app.app_context():
        print("Starting MSS migration...")
        print("=" * 60)

        # Check if we're using SQLite or PostgreSQL
        engine_name = db.engine.name
        print(f"Database engine: {engine_name}")

        # Read SQL migration file
        sql_file = project_root / "migrations" / "add_mss_columns.sql"
        if not sql_file.exists():
            print(f"ERROR: SQL file not found: {sql_file}")
            return False

        with open(sql_file, 'r') as f:
            sql_content = f.read()

        # For SQLite, we need to modify the syntax
        if engine_name == 'sqlite':
            print("Detected SQLite - modifying syntax...")
            # SQLite doesn't support IF NOT EXISTS in ALTER TABLE
            # We'll need to check and add columns individually
            migrate_sqlite()
        else:
            # PostgreSQL - run the SQL directly
            print("Running PostgreSQL migration...")
            try:
                # Split by semicolon and execute each statement
                statements = [s.strip() for s in sql_content.split(';') if s.strip()]
                for i, statement in enumerate(statements, 1):
                    if statement.startswith('COMMENT'):
                        # Skip comment statements for now (SQLite doesn't support them)
                        continue
                    print(f"Executing statement {i}/{len(statements)}...")
                    db.session.execute(text(statement))

                db.session.commit()
                print("✓ Migration completed successfully!")
                return True

            except Exception as e:
                db.session.rollback()
                print(f"✗ Migration failed: {e}")
                return False


def migrate_sqlite():
    """Run migration for SQLite (different syntax)."""
    # Get existing columns
    inspector = db.inspect(db.engine)
    existing_columns = {col['name'] for col in inspector.get_columns('model_benchmark_cache')}

    print(f"Found {len(existing_columns)} existing columns")

    # Define new columns to add
    new_columns = {
        # Chapter 4 MSS Benchmarks
        'bfcl_score': 'REAL',
        'webdev_elo': 'REAL',
        'arc_agi_score': 'REAL',
        'simplebench_score': 'REAL',
        'canaicode_score': 'REAL',
        'seal_coding_score': 'REAL',
        'gpqa_score': 'REAL',

        # MSS Component Scores
        'adoption_score': 'REAL',
        'benchmark_score': 'REAL',
        'cost_efficiency_score': 'REAL',
        'accessibility_score': 'REAL',
        'mss': 'REAL',

        # Adoption Metrics
        'openrouter_programming_rank': 'INTEGER',
        'openrouter_overall_rank': 'INTEGER',
        'openrouter_market_share': 'REAL',

        # Accessibility Metrics
        'license_type': 'VARCHAR(50)',
        'api_stability': 'VARCHAR(20)',
        'documentation_quality': 'VARCHAR(20)',

        # Data Freshness
        'adoption_data_updated_at': 'TIMESTAMP',
        'accessibility_data_updated_at': 'TIMESTAMP',
    }

    added_count = 0
    skipped_count = 0

    for column_name, column_type in new_columns.items():
        if column_name in existing_columns:
            print(f"  - Skipping {column_name} (already exists)")
            skipped_count += 1
        else:
            try:
                sql = f"ALTER TABLE model_benchmark_cache ADD COLUMN {column_name} {column_type}"
                db.session.execute(text(sql))
                print(f"  + Added {column_name} ({column_type})")
                added_count += 1
            except Exception as e:
                print(f"  ✗ Failed to add {column_name}: {e}")

    try:
        # Create indexes (SQLite version)
        print("\nCreating indexes...")
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_mss ON model_benchmark_cache(mss DESC)",
            "CREATE INDEX IF NOT EXISTS idx_adoption_score ON model_benchmark_cache(adoption_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_benchmark_score ON model_benchmark_cache(benchmark_score DESC)",
            "CREATE INDEX IF NOT EXISTS idx_openrouter_programming_rank ON model_benchmark_cache(openrouter_programming_rank ASC)",
        ]

        for idx_sql in indexes:
            db.session.execute(text(idx_sql))
            print(f"  + Created index")

        db.session.commit()

        print("\n" + "=" * 60)
        print(f"✓ Migration completed!")
        print(f"  - Columns added: {added_count}")
        print(f"  - Columns skipped: {skipped_count}")
        print(f"  - Indexes created: {len(indexes)}")

        return True

    except Exception as e:
        db.session.rollback()
        print(f"\n✗ Migration failed: {e}")
        return False


def verify_migration():
    """Verify that all columns were added successfully."""
    app = create_app()

    with app.app_context():
        inspector = db.inspect(db.engine)
        columns = {col['name'] for col in inspector.get_columns('model_benchmark_cache')}

        required_columns = {
            'bfcl_score', 'webdev_elo', 'arc_agi_score', 'simplebench_score',
            'canaicode_score', 'seal_coding_score', 'gpqa_score',
            'adoption_score', 'benchmark_score', 'cost_efficiency_score',
            'accessibility_score', 'mss',
            'openrouter_programming_rank', 'openrouter_overall_rank',
            'openrouter_market_share', 'license_type', 'api_stability',
            'documentation_quality', 'adoption_data_updated_at',
            'accessibility_data_updated_at'
        }

        missing = required_columns - columns
        if missing:
            print(f"✗ Verification failed! Missing columns: {missing}")
            return False
        else:
            print("✓ Verification passed! All MSS columns present.")
            return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migrate database for MSS support')
    parser.add_argument('--verify-only', action='store_true', help='Only verify migration')
    args = parser.parse_args()

    if args.verify_only:
        success = verify_migration()
    else:
        success = run_migration()
        if success:
            print("\nVerifying migration...")
            verify_migration()

    sys.exit(0 if success else 1)
