"""
Check Web UI Created Tasks Status
==================================

Check status of tasks created via web UI to see if they're actually executing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from datetime import datetime, timedelta

app = create_app()

with app.app_context():
    print("=" * 70)
    print("Recently Created Tasks (last hour)")
    print("=" * 70)
    print()
    
    # Get tasks from last hour
    one_hour_ago = datetime.utcnow() - timedelta(hours=1)
    recent_tasks = AnalysisTask.query.filter(
        AnalysisTask.created_at >= one_hour_ago
    ).order_by(AnalysisTask.created_at.desc()).limit(20).all()
    
    if not recent_tasks:
        print("No tasks created in the last hour")
    else:
        print(f"Found {len(recent_tasks)} recent tasks:\n")
        
        for task in recent_tasks:
            print(f"Task ID: {task.task_id}")
            print(f"  Model: {task.target_model}")
            print(f"  App: {task.target_app_number}")
            print(f"  Status: {task.status}")
            print(f"  Type: {task.analysis_type or 'N/A'}")
            print(f"  Is Main: {task.is_main_task}")
            print(f"  Parent: {task.parent_task_id or 'None'}")
            print(f"  Created: {task.created_at}")
            print(f"  Started: {task.started_at or 'Not started'}")
            print(f"  Completed: {task.completed_at or 'Not completed'}")
            print(f"  Progress: {task.progress_percentage}%")
            
            # Check if results exist
            if task.target_model and task.target_app_number:
                results_dir = Path(__file__).parent / 'results' / task.target_model / f'app{task.target_app_number}'
                if results_dir.exists():
                    task_dirs = list(results_dir.glob(f'task_{task.task_id}*'))
                    if task_dirs:
                        print(f"  Results: ✅ {task_dirs[0].name}")
                    else:
                        print(f"  Results: ❌ Not found")
                else:
                    print(f"  Results: ❌ Directory doesn't exist")
            
            print()
    
    print("=" * 70)
    print("Task Status Summary")
    print("=" * 70)
    
    from sqlalchemy import func
    status_counts = app.extensions['sqlalchemy'].db.session.query(
        AnalysisTask.status, func.count(AnalysisTask.id)
    ).filter(
        AnalysisTask.created_at >= one_hour_ago
    ).group_by(AnalysisTask.status).all()
    
    for status, count in status_counts:
        print(f"{status}: {count}")
