#!/usr/bin/env python
"""
Clear All Analysis Tasks
=========================

This script removes all analysis tasks from the database.

Usage:
    python scripts/clear_all_tasks.py
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.extensions import db
from app.models.analysis_task import AnalysisTask

def main():
    app = create_app()
    with app.app_context():
        # Count existing tasks
        total_tasks = AnalysisTask.query.count()
        
        if total_tasks == 0:
            print('No tasks found in database.')
            return
        
        print(f'Found {total_tasks} tasks in database.')
        print('Deleting all tasks...')
        
        # Delete all tasks
        deleted = AnalysisTask.query.delete()
        db.session.commit()
        
        print(f'✓ Successfully deleted {deleted} tasks')
        
        # Verify deletion
        remaining = AnalysisTask.query.count()
        print(f'Remaining tasks: {remaining}')

if __name__ == '__main__':
    main()
