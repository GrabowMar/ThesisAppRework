#!/usr/bin/env python
"""
Migration script to add unique constraint on analysis_task table.
Prevents duplicate tasks for the same (target_model, target_app_number, batch_id).

Run from project root:
    python scripts/migrate_analysis_task_constraint.py
"""

import os
import sys
import sqlite3
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def get_db_path():
    """Get the database path from config or default."""
    # Primary location based on actual project structure
    project_root = Path(__file__).parent.parent
    db_path = project_root / "src" / "data" / "thesis_app.db"
    
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Checking alternative locations...")
        
        # Try other common locations
        alt_paths = [
            project_root / "instance" / "app.db",
            project_root / "app.db",
            project_root / "src" / "instance" / "app.db",
        ]
        for alt in alt_paths:
            if alt.exists():
                db_path = alt
                break
    
    return db_path


def backup_database(db_path: Path):
    """Create a backup of the database before migration."""
    backup_path = db_path.with_suffix('.db.backup')
    
    if backup_path.exists():
        # Add timestamp to avoid overwriting
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.with_suffix(f'.db.backup_{timestamp}')
    
    import shutil
    shutil.copy2(db_path, backup_path)
    print(f"Created backup at: {backup_path}")
    return backup_path


def check_constraint_exists(conn: sqlite3.Connection) -> bool:
    """Check if the unique constraint already exists."""
    cursor = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='analysis_tasks'")
    row = cursor.fetchone()
    
    if row and row[0]:
        create_sql = row[0].upper()
        # Check for the unique constraint
        return 'UQ_ANALYSIS_TASK_MODEL_APP_PIPELINE' in create_sql or \
               ('UNIQUE' in create_sql and 'TARGET_MODEL' in create_sql and 'BATCH_ID' in create_sql)
    
    return False


def migrate_with_recreate(conn: sqlite3.Connection):
    """Migrate by recreating the table with the constraint."""
    
    print("Step 1: Creating new table with unique constraint...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analysis_tasks_new (
            id INTEGER NOT NULL,
            task_id VARCHAR(100) NOT NULL,
            parent_task_id VARCHAR(100),
            is_main_task BOOLEAN,
            service_name VARCHAR(100),
            analyzer_config_id INTEGER NOT NULL,
            status VARCHAR(15),
            priority VARCHAR(6),
            target_model VARCHAR(200) NOT NULL,
            target_app_number INTEGER NOT NULL,
            target_path VARCHAR(500),
            task_name VARCHAR(200),
            description TEXT,
            task_metadata TEXT,
            progress_percentage FLOAT,
            current_step VARCHAR(200),
            total_steps INTEGER,
            completed_steps INTEGER,
            batch_id VARCHAR(100),
            assigned_worker VARCHAR(100),
            execution_context TEXT,
            result_summary TEXT,
            issues_found INTEGER,
            severity_breakdown TEXT,
            estimated_duration INTEGER,
            actual_duration FLOAT,
            queue_time FLOAT,
            error_message TEXT,
            retry_count INTEGER,
            max_retries INTEGER,
            created_at DATETIME NOT NULL,
            updated_at DATETIME,
            started_at DATETIME,
            completed_at DATETIME,
            PRIMARY KEY (id),
            UNIQUE (target_model, target_app_number, batch_id)
        )
    """)
    
    print("Step 2: Copying data (ignoring duplicates)...")
    # Get column names from existing table
    cursor = conn.execute("PRAGMA table_info(analysis_tasks)")
    columns = [row[1] for row in cursor.fetchall()]
    columns_str = ', '.join(columns)
    
    # Copy data, ignoring duplicates
    conn.execute(f"""
        INSERT OR IGNORE INTO analysis_tasks_new ({columns_str})
        SELECT {columns_str} FROM analysis_tasks
    """)
    
    # Check how many rows were copied
    cursor = conn.execute("SELECT COUNT(*) FROM analysis_tasks")
    original_count = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM analysis_tasks_new")
    new_count = cursor.fetchone()[0]
    
    duplicates_removed = original_count - new_count
    if duplicates_removed > 0:
        print(f"  Removed {duplicates_removed} duplicate rows during migration")
    
    print("Step 3: Dropping old table...")
    conn.execute("DROP TABLE IF EXISTS analysis_tasks")
    
    print("Step 4: Renaming new table...")
    conn.execute("ALTER TABLE analysis_tasks_new RENAME TO analysis_tasks")
    
    print("Step 5: Recreating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_analysis_tasks_task_id ON analysis_tasks (task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_analysis_tasks_status ON analysis_tasks (status)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_analysis_tasks_batch_id ON analysis_tasks (batch_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_analysis_tasks_parent_task_id ON analysis_tasks (parent_task_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_analysis_tasks_target_model ON analysis_tasks (target_model)")
    
    conn.commit()
    print(f"Migration complete! {new_count} rows in analysis_tasks table.")


def main():
    db_path = get_db_path()
    
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Please ensure the application has been run at least once to create the database.")
        sys.exit(1)
    
    print(f"Database: {db_path}")
    
    # Create backup
    print("\nCreating backup...")
    backup_path = backup_database(db_path)
    
    # Connect and check current state
    conn = sqlite3.connect(db_path)
    
    try:
        # Check if constraint already exists
        if check_constraint_exists(conn):
            print("\n✓ Unique constraint already exists. No migration needed.")
            conn.close()
            return
        
        # Check if the table exists
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_tasks'")
        if not cursor.fetchone():
            print("\n⚠ analysis_tasks table does not exist yet.")
            print("The constraint will be applied when the table is created by SQLAlchemy.")
            conn.close()
            return
        
        print("\nApplying migration...")
        migrate_with_recreate(conn)
        
        # Verify the constraint was applied
        if check_constraint_exists(conn):
            print("\n✓ Migration successful! Unique constraint is now active.")
        else:
            print("\n⚠ Warning: Constraint may not have been applied correctly.")
        
    except Exception as e:
        print(f"\nERROR during migration: {e}")
        print(f"Restoring from backup: {backup_path}")
        conn.close()
        
        # Restore backup
        import shutil
        shutil.copy2(backup_path, db_path)
        print("Database restored from backup.")
        sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
