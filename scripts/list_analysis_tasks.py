"""
Script to list all analysis tasks in the database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models.analysis_models import AnalysisTask

def list_analysis_tasks():
    """List all analysis tasks."""
    app = create_app()
    
    with app.app_context():
        # Get tasks ordered by creation date
        tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(50).all()
        
        print(f"Found {len(tasks)} analysis task(s)\n")
        print("=" * 120)
        
        for task in tasks:
            print(f"Task ID: {task.task_id}")
            print(f"  Status: {task.status}")
            print(f"  Model: {task.target_model}")
            print(f"  App: {task.target_app_number}")
            print(f"  Main task: {task.is_main_task}")
            print(f"  Batch ID: {task.batch_id}")
            print(f"  Created: {task.created_at}")
            print("-" * 120)

if __name__ == '__main__':
    list_analysis_tasks()
