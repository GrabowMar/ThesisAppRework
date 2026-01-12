#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("=== FAILED TASKS ===\n")
    failed_tasks = AnalysisTask.query.filter_by(status='failed').all()
    for task in failed_tasks:
        print(f'Task ID: {task.task_id}')
        print(f'  Target: {task.target_model}/app{task.target_app_number}')
        print(f'  Error: {task.error_message}')
        print(f'  Retry Count: {task.retry_count}/{task.max_retries}')
        print(f'  Service: {task.service_name}')
        print()
    
    print("=== PARTIAL SUCCESS TASKS ===\n")
    partial_tasks = AnalysisTask.query.filter_by(status='partial_success').all()
    for task in partial_tasks:
        print(f'Task ID: {task.task_id}')
        print(f'  Target: {task.target_model}/app{task.target_app_number}')
        print(f'  Error: {task.error_message or "None"}')
        print(f'  Progress: {task.progress_percentage}%')
        print(f'  Issues Found: {task.issues_found}')
        print()
