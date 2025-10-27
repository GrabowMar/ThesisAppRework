#!/usr/bin/env python
"""Debug script to investigate analysis task failures."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

def main():
    app = create_app()
    with app.app_context():
        # Get recent failed tasks
        tasks = AnalysisTask.query.filter_by(
            target_model='anthropic_claude-4.5-haiku-20251001'
        ).order_by(AnalysisTask.created_at.desc()).limit(5).all()
        
        print(f"Found {len(tasks)} tasks for anthropic_claude-4.5-haiku-20251001\n")
        
        for task in tasks:
            print(f"Task ID: {task.task_id}")
            print(f"  Status: {task.status}")
            print(f"  Type: {task.analysis_type}")
            print(f"  App Number: {task.target_app_number}")
            print(f"  Is Main Task: {task.is_main_task}")
            print(f"  Has Subtasks: {len(task.subtasks) if task.subtasks else 0}")
            print(f"  Error Message: {task.error_message}")
            print(f"  Created: {task.created_at}")
            print(f"  Started: {task.started_at}")
            print(f"  Completed: {task.completed_at}")
            
            # Check subtasks
            if task.subtasks:
                print("  Subtasks:")
                for subtask in task.subtasks:
                    print(f"    - {subtask.service_name}: {subtask.status} (progress: {subtask.progress_percentage}%)")
                    if subtask.error_message:
                        print(f"      Error: {subtask.error_message}")
            
            # Check metadata
            try:
                metadata = task.get_metadata()
                if metadata:
                    print(f"  Metadata: {metadata}")
            except Exception as e:
                print(f"  Metadata error: {e}")
            
            print()

if __name__ == '__main__':
    main()
