#!/usr/bin/env python
"""
Migration script to add report_data column to reports table.

Run from project root:
    python scripts/add_report_data_column.py
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db


def add_report_data_column():
    """Add report_data column to reports table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        # Check if column exists
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        columns = [col['name'] for col in inspector.get_columns('reports')]
        
        if 'report_data' in columns:
            print("✓ Column 'report_data' already exists in reports table")
            return True
        
        print("Adding 'report_data' column to reports table...")
        
        try:
            # Add the column
            with db.engine.connect() as conn:
                conn.execute(text("ALTER TABLE reports ADD COLUMN report_data TEXT"))
                conn.commit()
            
            print("✓ Successfully added 'report_data' column")
            return True
            
        except Exception as e:
            print(f"✗ Error adding column: {e}")
            return False


if __name__ == '__main__':
    success = add_report_data_column()
    sys.exit(0 if success else 1)
