#!/usr/bin/env python3
"""Clean up failed tasks from before the fix."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db
from app.constants import AnalysisStatus

app = create_app()

with app.app_context():
    # Get all RUNNING and FAILED tasks
    running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
    failed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).all()
    
    print(f"\nFound {len(running_tasks)} RUNNING tasks and {len(failed_tasks)} FAILED tasks")
    print("\nMarking all as FAILED and cleaning up...")
    
    # Mark all running tasks as failed (they're stuck from before the fix)
    for task in running_tasks:
        task.status = AnalysisStatus.FAILED
        task.error_message = "Task interrupted by system restart/fix deployment"
        task.progress_percentage = 0.0
    
    # Delete all failed tasks (clean slate)
    for task in failed_tasks:
        db.session.delete(task)
    for task in running_tasks:
        db.session.delete(task)
    
    db.session.commit()
    
    print(f"✅ Cleaned up {len(running_tasks) + len(failed_tasks)} tasks")
    print("\nReady for fresh test!")
