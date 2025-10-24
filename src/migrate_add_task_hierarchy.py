#!/usr/bin/env python
"""
Database Migration: Add Task Hierarchy Fields
==============================================

Adds parent_task_id, is_main_task, and service_name columns to analysis_tasks table.
Clears old tasks since they don't use the new hierarchy system.
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent
sys.path.insert(0, str(src_dir))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from sqlalchemy import text


def main():
    """Add task hierarchy columns to analysis_tasks table and clear old tasks."""
    app = create_app()
    
    with app.app_context():
        print("=" * 60)
        print("Adding Task Hierarchy Fields Migration")
        print("=" * 60)
        
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        existing_columns = [col['name'] for col in inspector.get_columns('analysis_tasks')]
        
        columns_to_add = []
        if 'parent_task_id' not in existing_columns:
            columns_to_add.append('parent_task_id')
        if 'is_main_task' not in existing_columns:
            columns_to_add.append('is_main_task')
        if 'service_name' not in existing_columns:
            columns_to_add.append('service_name')
        
        if not columns_to_add:
            print("✅ All task hierarchy columns already exist!")
        else:
            print(f"Adding columns: {', '.join(columns_to_add)}")
        
        try:
            # Add parent_task_id column
            if 'parent_task_id' in columns_to_add:
                print("Adding parent_task_id column...")
                db.session.execute(text("""
                    ALTER TABLE analysis_tasks 
                    ADD COLUMN parent_task_id VARCHAR(100)
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_analysis_tasks_parent_task_id 
                    ON analysis_tasks(parent_task_id)
                """))
                print("✅ parent_task_id column added")
            
            # Add is_main_task column
            if 'is_main_task' in columns_to_add:
                print("Adding is_main_task column...")
                db.session.execute(text("""
                    ALTER TABLE analysis_tasks 
                    ADD COLUMN is_main_task BOOLEAN DEFAULT FALSE
                """))
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_analysis_tasks_is_main_task 
                    ON analysis_tasks(is_main_task)
                """))
                print("✅ is_main_task column added")
            
            # Add service_name column
            if 'service_name' in columns_to_add:
                print("Adding service_name column...")
                db.session.execute(text("""
                    ALTER TABLE analysis_tasks 
                    ADD COLUMN service_name VARCHAR(100)
                """))
                print("✅ service_name column added")
            
            # Add foreign key constraint for parent_task_id
            if 'parent_task_id' in columns_to_add:
                print("Adding foreign key constraint...")
                try:
                    db.session.execute(text("""
                        ALTER TABLE analysis_tasks 
                        ADD CONSTRAINT fk_parent_task 
                        FOREIGN KEY (parent_task_id) 
                        REFERENCES analysis_tasks(task_id)
                        ON DELETE CASCADE
                    """))
                    print("✅ Foreign key constraint added")
                except Exception as e:
                    # Foreign key might fail on SQLite, that's okay
                    print(f"⚠️  Foreign key constraint skipped: {e}")
            
            db.session.commit()
            
            # Clear old tasks since they don't use the new hierarchy
            print("\nClearing old tasks from database...")
            old_task_count = AnalysisTask.query.count()
            AnalysisTask.query.delete()
            db.session.commit()
            print(f"✅ Deleted {old_task_count} old tasks")
            
            print("=" * 60)
            print("✅ Migration completed successfully!")
            print("Database is ready for new task hierarchy system")
            print("New analyses will create main tasks with subtasks")
            print("=" * 60)
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Migration failed: {e}")
            print("=" * 60)
            raise


if __name__ == '__main__':
    main()
