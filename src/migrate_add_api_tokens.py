#!/usr/bin/env python
"""Add API token columns to User model."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.extensions import db

app = create_app()

with app.app_context():
    # Add new columns to users table
    try:
        with db.engine.connect() as conn:
            # Check if columns exist
            result = conn.execute(db.text("PRAGMA table_info(users)"))
            columns = [row[1] for row in result]
            
            if 'api_token' not in columns:
                print("Adding api_token column...")
                conn.execute(db.text("ALTER TABLE users ADD COLUMN api_token VARCHAR(64)"))
                conn.commit()
                print("✅ api_token column added")
            else:
                print("ℹ️  api_token column already exists")
            
            if 'api_token_created_at' not in columns:
                print("Adding api_token_created_at column...")
                conn.execute(db.text("ALTER TABLE users ADD COLUMN api_token_created_at DATETIME"))
                conn.commit()
                print("✅ api_token_created_at column added")
            else:
                print("ℹ️  api_token_created_at column already exists")
        
        # Create index on api_token for fast lookups
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_api_token ON users (api_token)"))
                conn.commit()
                print("✅ Index on api_token created")
        except Exception as e:
            print(f"⚠️  Index creation warning (may already exist): {e}")
        
        print("\n✅ Database migration complete!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)
