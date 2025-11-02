#!/usr/bin/env python3
"""
Test script to verify stop all tasks functionality.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.services.task_service import AnalysisTaskService

app = create_app()

with app.app_context():
    print("=== Stop All Tasks Test ===\n")
    
    # Get current active tasks
    active_tasks_before = AnalysisTask.query.filter(
        AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
    ).all()
    
    print(f"Active tasks before: {len(active_tasks_before)}")
    for task in active_tasks_before:
        print(f"  - {task.task_id}: {task.status.value}, {task.analysis_type}")
    print()
    
    if len(active_tasks_before) == 0:
        print("✅ No active tasks to cancel - test cannot proceed")
        print("   Create some tasks through the web UI first")
        sys.exit(0)
    
    # Test cancelling all tasks
    print("Attempting to cancel all active tasks...")
    cancelled_count = 0
    failed_count = 0
    
    for task in active_tasks_before:
        try:
            result = AnalysisTaskService.cancel_task(task.task_id)
            if result:
                print(f"  ✅ Cancelled: {task.task_id}")
                cancelled_count += 1
            else:
                print(f"  ❌ Failed to cancel: {task.task_id}")
                failed_count += 1
        except Exception as e:
            print(f"  ❌ Error cancelling {task.task_id}: {e}")
            failed_count += 1
    
    print()
    print(f"Results:")
    print(f"  Cancelled: {cancelled_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total: {len(active_tasks_before)}")
    print()
    
    # Verify tasks are now cancelled
    active_tasks_after = AnalysisTask.query.filter(
        AnalysisTask.status.in_([AnalysisStatus.PENDING, AnalysisStatus.RUNNING])
    ).all()
    
    cancelled_tasks = AnalysisTask.query.filter(
        AnalysisTask.status == AnalysisStatus.CANCELLED
    ).limit(10).all()
    
    print(f"Active tasks after: {len(active_tasks_after)}")
    print(f"Recently cancelled tasks: {len(cancelled_tasks)}")
    for task in cancelled_tasks[:5]:
        print(f"  - {task.task_id}: {task.status.value}")
    
    print()
    if cancelled_count > 0:
        print("✅ Stop all tasks functionality works!")
    else:
        print("⚠️  No tasks were cancelled - check if tasks can be cancelled")
