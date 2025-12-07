"""
Add PipelineSettings table for automation pipeline configuration storage.

Run this script to create the pipeline_settings table:
    python scripts/add_pipeline_settings_table.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import PipelineSettings


def add_pipeline_settings_table():
    """Create the pipeline_settings table if it doesn't exist."""
    app = create_app()
    
    with app.app_context():
        # Check if table exists
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        if 'pipeline_settings' in existing_tables:
            print("✓ pipeline_settings table already exists")
            return True
        
        # Create the table
        print("Creating pipeline_settings table...")
        
        try:
            # Create only the PipelineSettings table
            PipelineSettings.__table__.create(db.engine)
            print("✓ pipeline_settings table created successfully")
            return True
        except Exception as e:
            print(f"✗ Error creating table: {e}")
            return False


if __name__ == '__main__':
    success = add_pipeline_settings_table()
    sys.exit(0 if success else 1)
