#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("=== ALL ANALYSIS TASKS ===")
    tasks = AnalysisTask.query.all()
    print(f'Total tasks: {len(tasks)}')
    
    for task in tasks[-20:]:  # Last 20 tasks
        print(f'\nTask ID: {task.task_id}')
        print(f'  Status: {task.status}')
        print(f'  Error: {task.error_message}')
        if task.error_traceback:
            lines = task.error_traceback.split('\n')
            print(f'  Traceback (last 10 lines):\n{chr(10).join(lines[-10:])}')
