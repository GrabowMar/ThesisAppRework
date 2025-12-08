#!/usr/bin/env python3
"""
Database migration script to add the pipeline_executions table.
This script safely adds the table if it doesn't exist.

Run this script once to set up the pipeline_executions table.

Usage:
    python scripts/add_pipeline_executions_table.py
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sqlalchemy import inspect, text
from app.factory import create_app
from app.extensions import db
from app.models.pipeline import PipelineExecution, PipelineExecutionStatus


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()


def add_pipeline_executions_table():
    """Add the pipeline_executions table if it doesn't exist."""
    
    print("=" * 60)
    print("Pipeline Executions Table Migration")
    print("=" * 60)
    
    app = create_app()
    
    with app.app_context():
        # Check if table already exists
        if table_exists('pipeline_executions'):
            print("\n✓ Table 'pipeline_executions' already exists.")
            
            # Verify structure
            inspector = inspect(db.engine)
            columns = [col['name'] for col in inspector.get_columns('pipeline_executions')]
            print(f"  Existing columns: {', '.join(columns)}")
            
            return True
        
        print("\n→ Creating 'pipeline_executions' table...")
        
        try:
            # Create the table using SQLAlchemy model
            PipelineExecution.__table__.create(db.engine)
            db.session.commit()
            
            print("✓ Table 'pipeline_executions' created successfully!")
            
            # Verify the table was created
            if table_exists('pipeline_executions'):
                inspector = inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('pipeline_executions')]
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
            count = PipelineExecution.query.count()
            print(f"✓ Model verified - {count} existing pipeline records found.")
            return True
        except Exception as e:
            print(f"✗ Model verification failed: {e}")
            return False


def main():
    """Run the migration."""
    success = add_pipeline_executions_table()
    
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
