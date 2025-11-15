"""
Simple migration script to add versioning fields to GeneratedApplication
Run this from the project root: python scripts/migrate_add_versioning.py
"""
import sqlite3
import sys
from pathlib import Path

# Find the database file
db_path = Path(__file__).parent.parent / 'src' / 'data' / 'thesis_app.db'

if not db_path.exists():
    print(f"Database not found at {db_path}")
    print("Looking for alternative locations...")
    
    # Try other common locations
    alt_paths = [
        Path(__file__).parent.parent / 'src' / 'instance' / 'app.db',
        Path(__file__).parent.parent / 'instance' / 'app.db',
        Path(__file__).parent.parent / 'app.db',
    ]
    
    for alt in alt_paths:
        if alt.exists():
            db_path = alt
            break
    else:
        print("ERROR: Could not find database file")
        sys.exit(1)

print(f"Using database: {db_path}")

# Connect to database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    print("\n=== Starting Migration ===")
    
    # Check if we need migration
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='generated_applications'")
    table_result = cursor.fetchone()
    table_schema = table_result[0] if table_result else ""
    
    # Check if old constraint exists
    has_old_constraint = 'CONSTRAINT unique_model_app UNIQUE (model_slug, app_number)' in table_schema or \
                        'UNIQUE (model_slug, app_number)' in table_schema
    
    cursor.execute("PRAGMA table_info(generated_applications)")
    columns = {row[1]: row for row in cursor.fetchall()}
    has_version = 'version' in columns
    
    if has_version and not has_old_constraint:
        print("✓ Migration already applied correctly")
        sys.exit(0)
    
    if has_version and has_old_constraint:
        print("⚠ Version column exists but old constraint remains - fixing...")
    if has_version and has_old_constraint:
        print("⚠ Version column exists but old constraint remains - fixing...")
    
    if not has_version:
        print("Adding new columns...")
        
        # Add version column (default 1 for existing apps)
        cursor.execute("""
            ALTER TABLE generated_applications 
            ADD COLUMN version INTEGER NOT NULL DEFAULT 1
        """)
        print("  ✓ Added version column")
        
        # Add parent_app_id column (nullable)
        cursor.execute("""
            ALTER TABLE generated_applications 
            ADD COLUMN parent_app_id INTEGER
        """)
        print("  ✓ Added parent_app_id column")
        
        # Add batch_id column (nullable)
        cursor.execute("""
            ALTER TABLE generated_applications 
            ADD COLUMN batch_id VARCHAR(100)
        """)
        print("  ✓ Added batch_id column")
    
    # Now fix the constraint regardless of whether columns were just added
    print("\nRecreating table to fix unique constraint...")
    
    # Create new table with updated schema
    cursor.execute("""
        CREATE TABLE generated_applications_new (
            id INTEGER PRIMARY KEY,
            model_slug VARCHAR(200) NOT NULL,
            app_number INTEGER NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            parent_app_id INTEGER,
            batch_id VARCHAR(100),
            app_type VARCHAR(50) NOT NULL,
            provider VARCHAR(100) NOT NULL,
            template_slug VARCHAR(100),
            generation_status VARCHAR(50),
            has_backend BOOLEAN,
            has_frontend BOOLEAN,
            has_docker_compose BOOLEAN,
            backend_framework VARCHAR(50),
            frontend_framework VARCHAR(50),
            container_status VARCHAR(50),
            last_status_check DATETIME,
            metadata_json TEXT,
            created_at DATETIME,
            updated_at DATETIME,
            FOREIGN KEY (parent_app_id) REFERENCES generated_applications_new(id),
            UNIQUE (model_slug, app_number, version)
        )
    """)
    print("  ✓ Created new table schema")
    
    # Copy existing data
    cursor.execute("""
        INSERT INTO generated_applications_new 
        SELECT 
            id, model_slug, app_number, version, parent_app_id, batch_id,
            app_type, provider, template_slug, generation_status,
            has_backend, has_frontend, has_docker_compose,
            backend_framework, frontend_framework, container_status,
            last_status_check, metadata_json, created_at, updated_at
        FROM generated_applications
    """)
    rows_copied = cursor.rowcount
    print(f"  ✓ Copied {rows_copied} existing records")
    
    # Drop old table
    cursor.execute("DROP TABLE generated_applications")
    print("  ✓ Dropped old table")
    
    # Rename new table
    cursor.execute("ALTER TABLE generated_applications_new RENAME TO generated_applications")
    print("  ✓ Renamed new table")
    
    # Create indexes for better query performance
    print("\nCreating indexes...")
    
    cursor.execute("""
        CREATE INDEX idx_model_slug ON generated_applications(model_slug)
    """)
    print("  ✓ Created index on model_slug")
    
    cursor.execute("""
        CREATE INDEX idx_provider ON generated_applications(provider)
    """)
    print("  ✓ Created index on provider")
    
    cursor.execute("""
        CREATE INDEX idx_template_slug ON generated_applications(template_slug)
    """)
    print("  ✓ Created index on template_slug")
    
    cursor.execute("""
        CREATE INDEX idx_model_template ON generated_applications(model_slug, template_slug)
    """)
    print("  ✓ Created index on (model_slug, template_slug)")
    
    cursor.execute("""
        CREATE INDEX idx_batch_id ON generated_applications(batch_id)
    """)
    print("  ✓ Created index on batch_id")
    
    # Commit changes
    conn.commit()
    print("\n✅ Migration completed successfully!")
    print(f"   Migrated {rows_copied} records")
    print("   All apps now have version=1 by default")
    
except Exception as e:
    conn.rollback()
    print(f"\n❌ Migration failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    conn.close()
