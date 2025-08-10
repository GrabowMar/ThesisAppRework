#!/usr/bin/env python3
"""
Test script to verify database configuration
"""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

def test_database_config():
    """Test that database configuration is correct."""
    try:
        from app.factory import create_app
        
        # Create app
        app = create_app()
        
        # Get database URI
        db_uri = app.config['SQLALCHEMY_DATABASE_URI']
        print(f"Database URI: {db_uri}")
        
        # Check if it points to data folder
        if 'src/app/data/thesis_app.db' in db_uri or 'src\\app\\data\\thesis_app.db' in db_uri:
            print("✓ Database configuration correctly points to data folder")
            
            # Check if database file exists
            data_dir = project_root / "src" / "app" / "data"
            db_file = data_dir / "thesis_app.db"
            
            if db_file.exists():
                print(f"✓ Database file exists at: {db_file}")
                print(f"  File size: {db_file.stat().st_size} bytes")
            else:
                print(f"⚠ Database file not found at: {db_file}")
                
            return True
        else:
            print(f"✗ Database configuration does not point to data folder")
            return False
            
    except Exception as e:
        print(f"✗ Error testing database config: {e}")
        return False

if __name__ == "__main__":
    print("=== Database Configuration Test ===")
    success = test_database_config()
    
    if success:
        print("\n🎉 Database configuration test passed!")
        sys.exit(0)
    else:
        print("\n❌ Database configuration test failed!")
        sys.exit(1)
