#!/usr/bin/env python3
"""Quick script to check recent task failures."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()

with app.app_context():
    tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(10).all()
    
    print("\n" + "="*80)
    print("RECENT TASKS")
    print("="*80)
    
    for task in tasks:
        print(f"\nTask ID: {task.task_id}")
        print(f"  Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        print(f"  Name: {task.task_name}")
        print(f"  Is Main: {task.is_main_task}")
        print(f"  Service: {task.service_name}")
        print(f"  Model: {task.target_model}")
        print(f"  App: {task.target_app_number}")
        print(f"  Progress: {task.progress_percentage}%")
        print(f"  Current Step: {task.current_step}")
        print(f"  Created: {task.created_at}")
        print(f"  Started: {task.started_at}")
        print(f"  Completed: {task.completed_at}")
        
        if task.error_message:
            print(f"  ERROR: {task.error_message[:500]}")
        
        # Check subtasks
        if hasattr(task, 'subtasks'):
            subtasks = task.subtasks
            if subtasks:
                print(f"  Subtasks ({len(subtasks)}):")
                for subtask in subtasks:
                    status_str = subtask.status.value if hasattr(subtask.status, 'value') else subtask.status
                    print(f"    - {subtask.task_id}: {status_str} ({subtask.progress_percentage}%)")
                    print(f"      Service: {subtask.service_name}")
                    if subtask.error_message:
                        print(f"      Error: {subtask.error_message[:200]}")
    
    print("\n" + "="*80)
