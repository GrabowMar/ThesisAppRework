#!/usr/bin/env python3
"""Check what tasks are currently running and blocking the queue."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app

app = create_app()

with app.app_context():
    from app.extensions import db
    
    # Import the model
    from app.models import AnalysisTask
    
    # Query running tasks
    running = AnalysisTask.query.filter_by(status='running').all()
    print(f"\nRunning tasks ({len(running)}):")
    print("=" * 80)
    for task in running:
        meta = task.get_metadata() or {}
        model = meta.get('model_slug', 'unknown')
        app_num = meta.get('app_number', '?')
        print(f"  {task.task_id}: {model} app{app_num} (created: {task.created_at})")
    
    # Query new test tasks
    test_task_ids = [
        'task_90bed98bb9a6',
        'task_0015db83086e',
        'task_b5e7b63956ae',
        'task_21ce78b24f02',
        'task_e734a4b3f5ae',
        'task_48b418ce8040',
    ]
    
    print(f"\nNew test tasks:")
    print("=" * 80)
    for tid in test_task_ids:
        task = AnalysisTask.query.filter_by(task_id=tid).first()
        if task:
            meta = task.get_metadata() or {}
            tools = meta.get('custom_options', {}).get('tools', [])
            print(f"  {task.task_id}: {task.status} - tools: {tools}")
