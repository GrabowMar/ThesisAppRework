#!/usr/bin/env python
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("=== FAILED TASKS WITH NO ERROR MESSAGE ===\n")
    
    failed_no_error = AnalysisTask.query.filter(
        db.and_(
            AnalysisTask.status == 'failed',
            db.or_(AnalysisTask.error_message == None, AnalysisTask.error_message == '')
        )
    ).all()
    
    for task in failed_no_error:
        print(f'Task ID: {task.task_id}')
        print(f'  Target: {task.target_model}/app{task.target_app_number}')
        print(f'  Service: {task.service_name}')
        print(f'  Result Summary: {task.result_summary[:200] if task.result_summary else "None"}')
        print()
