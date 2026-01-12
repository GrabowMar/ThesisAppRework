#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("=== ALL ANALYSIS TASKS (Last 20) ===")
    tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(20).all()
    print(f'Total visible: {len(tasks)}\n')
    
    for task in tasks:
        print(f'Task ID: {task.task_id}')
        print(f'  Status: {task.status}')
        print(f'  Target: {task.target_model}/app{task.target_app_number}')
        print(f'  Error: {task.error_message or "None"}')
        if task.error_message:
            print(f'  Completed Steps: {task.completed_steps}/{task.total_steps}')
            print(f'  Progress: {task.progress_percentage}%')
        print()
