#!/usr/bin/env python3
"""Kill old stuck tasks to free up the queue."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db

app = create_app()

with app.app_context():
    old_tasks = [
        'task_90bed98bb9a6',
        'task_0015db83086e',
        'task_b5e7b63956ae',
        'task_21ce78b24f02',
        'task_0a66abbd65f6',
    ]
    
    print("Killing old stuck tasks...")
    for tid in old_tasks:
        task = AnalysisTask.query.filter_by(task_id=tid).first()
        if task:
            task.status = 'failed'
            task.error_message = 'Stuck from old session, killed to free queue'
            print(f"  ✓ {tid}: marked as failed")
    
    db.session.commit()
    print("\nDone! Queue should now process new tasks.")
