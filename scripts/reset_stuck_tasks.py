#!/usr/bin/env python3
"""
Reset Stuck Analysis Tasks
==========================
Resets main analysis tasks stuck in RUNNING state with PENDING subtasks
so the web daemon can pick them up and dispatch subtasks properly.
"""

import sys
import os

# Run this inside the Docker container or ensure path is set
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from app.factory import create_app
    from app.extensions import db
    from app.models import AnalysisTask
    from app.constants import AnalysisStatus
except ImportError:
    print("Error: Run this script from within the Docker container or set PYTHONPATH")
    sys.exit(1)

app = create_app()

with app.app_context():
    # Find main tasks stuck in RUNNING with pending subtasks
    running_main = AnalysisTask.query.filter(
        AnalysisTask.status == AnalysisStatus.RUNNING,
        AnalysisTask.is_main_task == True
    ).all()
    
    reset_count = 0
    for task in running_main:
        subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
        pending_subtasks = [s for s in subtasks if s.status == AnalysisStatus.PENDING]
        
        # Reset if ALL subtasks are still pending (never dispatched)
        if len(pending_subtasks) == len(subtasks) and len(subtasks) > 0:
            task.status = AnalysisStatus.PENDING
            task.started_at = None
            reset_count += 1
            print(f"Reset: {task.task_id} ({len(subtasks)} subtasks)")
    
    if reset_count > 0:
        db.session.commit()
        print(f"\n✅ Reset {reset_count} main tasks to PENDING for retry")
    else:
        print("No stuck tasks found")
