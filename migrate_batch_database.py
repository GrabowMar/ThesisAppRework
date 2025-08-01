"""
Database Migration Script for Batch Dashboard Enhancement
========================================================

This script ensures the new batch processing tables are created properly.
Run this after implementing the new batch dashboard system.
"""

import os
import sys
import json
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

from app import create_app
from extensions import db
from models import BatchJob, BatchTask, BatchWorker

def migrate_database():
    """Create new batch processing tables"""
    app = create_app()
    
    with app.app_context():
        print("Creating new batch processing tables...")
        
        try:
            # Create all tables (will only create missing ones)
            db.create_all()
            
            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            required_tables = ['batch_jobs', 'batch_tasks', 'batch_workers']
            created_tables = []
            
            for table in required_tables:
                if table in tables:
                    created_tables.append(table)
                    print(f"✓ Table '{table}' exists")
                else:
                    print(f"✗ Table '{table}' missing")
            
            if len(created_tables) == len(required_tables):
                print("\n✅ All batch processing tables created successfully!")
            else:
                print(f"\n⚠️  Only {len(created_tables)}/{len(required_tables)} tables created")
            
            # Test basic operations
            print("\nTesting basic database operations...")
            
            # Test job creation
            import uuid
            from models import AnalysisType
            
            test_job = BatchJob()
            test_job.id = str(uuid.uuid4())
            test_job.name = "Migration Test Job"
            test_job.description = "Test job created during migration"
            test_job.created_by = "migration_script"
            
            # Set JSON fields directly since the setter methods aren't implemented yet
            test_job.analysis_types_json = json.dumps([AnalysisType.SECURITY_BACKEND.value])
            test_job.models_json = json.dumps(["test_model"])
            test_job.app_range_json = json.dumps("1")
            
            db.session.add(test_job)
            db.session.commit()
            
            job_count = BatchJob.query.count()
            print(f"✓ Job creation test passed (total jobs: {job_count})")
            
            # Clean up test data
            db.session.delete(test_job)
            db.session.commit()
            
            print("✓ Database operations test completed successfully")
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return True

if __name__ == '__main__':
    print("Batch Dashboard Database Migration")
    print("=" * 40)
    
    success = migrate_database()
    
    if success:
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Run the application: python src/app.py")
        print("2. Visit http://127.0.0.1:5000/batch/dashboard")
        print("3. Create your first batch job!")
    else:
        print("\n💥 Migration failed. Check the errors above.")
        sys.exit(1)
