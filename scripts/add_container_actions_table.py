#!/usr/bin/env python3
"""
Database migration script to add the container_actions table.
This script safely adds the table if it doesn't exist.

The container_actions table tracks Docker container operations (build, start, stop, restart)
with progress tracking, output capture, and action history.

Usage:
    python scripts/add_container_actions_table.py
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import inspect
from app.factory import create_app
from app.extensions import db
from app.models.container_action import ContainerAction, ContainerActionType, ContainerActionStatus


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()


def add_container_actions_table():
    """Add the container_actions table if it doesn't exist."""
    
    print("=" * 60)
    print("Container Actions Table Migration")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        # Check if table already exists
        if table_exists('container_actions'):
            print("\n✓ Table 'container_actions' already exists.")
            
            # Verify structure
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('container_actions')]
            print(f"  Existing columns: {', '.join(columns)}")
            
            return True
        
        print("\n→ Creating 'container_actions' table...")
        
        try:
            # Create the table using SQLAlchemy model
            ContainerAction.__table__.create(db.engine)
            db.session.commit()
            
            print("✓ Table 'container_actions' created successfully!")
            
            # Verify the table was created
            if table_exists('container_actions'):
                inspector = inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('container_actions')]
                print(f"  Created columns: {', '.join(columns)}")
                return True
            else:
                print("✗ Table creation failed - table not found after creation")
                return False
                
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            db.session.rollback()
            return False


def verify_model():
    """Verify the model can be used for queries."""
    print("\n→ Verifying model...")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Try a simple query
            count = ContainerAction.query.count()
            print(f"✓ Model verified - {count} existing action records found.")
            
            # Test enum values
            print(f"  Action types: {[t.value for t in ContainerActionType]}")
            print(f"  Status values: {[s.value for s in ContainerActionStatus]}")
            
            return True
        except Exception as e:
            print(f"✗ Model verification failed: {e}")
            return False


def main():
    """Run the migration."""
    success = add_container_actions_table()
    
    if success:
        verify_model()
        print("\n" + "=" * 60)
        print("Migration completed successfully!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("Migration failed!")
        print("=" * 60)
        sys.exit(1)


if __name__ == '__main__':
    main()
