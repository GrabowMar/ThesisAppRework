#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("=== FAILED TASK ===")
    failed_task = AnalysisTask.query.filter_by(task_id='pipeline:anthropic_claude-3-haiku:1').first()
    if failed_task:
        print(f'Task ID: {failed_task.task_id}')
        print(f'Status: {failed_task.status}')
        print(f'Error Message: {failed_task.error_message}')
        print(f'\nTraceback:\n{failed_task.error_traceback}')
    else:
        print('Failed task not found')
    
    print("\n=== PARTIAL TASK ===")
    partial_task = AnalysisTask.query.filter_by(task_id='pipeline:anthropic_claude-3-5-haiku:3').first()
    if partial_task:
        print(f'Task ID: {partial_task.task_id}')
        print(f'Status: {partial_task.status}')
        print(f'Error Message: {partial_task.error_message}')
        print(f'Completed Tools: {partial_task.completed_tools}')
    else:
        print('Partial task not found')
