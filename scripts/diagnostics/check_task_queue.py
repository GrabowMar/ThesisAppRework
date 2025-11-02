#!/usr/bin/env python3
"""
Quick diagnostic to check task queue status and why tasks aren't being picked up.
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root / "src"))

from app.factory import create_app
from app.models import AnalysisTask, AnalysisStatus
from app.services.task_service import queue_service

app = create_app()

with app.app_context():
    print("=== Task Queue Diagnostic ===\n")
    
    # Get queue config
    config = queue_service.queue_config
    print(f"Queue Configuration:")
    print(f"  max_concurrent_tasks: {config['max_concurrent_tasks']}")
    if 'max_per_type' in config:
        print(f"  max_per_type: {config['max_per_type']}")
    print()
    
    # Get currently running tasks
    from app.services.task_service import AnalysisTaskService
    running_tasks = AnalysisTaskService.get_active_tasks()
    running_count = len([t for t in running_tasks if t.status == AnalysisStatus.RUNNING])
    
    print(f"Currently Running Tasks: {running_count}")
    for task in running_tasks:
        if task.status == AnalysisStatus.RUNNING:
            print(f"  - {task.task_id}: {task.analysis_type}")
    print()
    
    # Get pending main tasks
    pending_main = AnalysisTask.query.filter(
        AnalysisTask.status == AnalysisStatus.PENDING,
        (AnalysisTask.is_main_task == True) | (AnalysisTask.is_main_task == None)
    ).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    
    print(f"Pending Main Tasks: {len(pending_main)}")
    for task in pending_main:
        print(f"  - {task.task_id}:")
        print(f"      is_main_task: {task.is_main_task}")
        print(f"      analysis_type: {task.analysis_type}")
        print(f"      model: {task.target_model}, app: {task.target_app_number}")
        print(f"      created: {task.created_at}")
        if hasattr(task, 'subtasks') and task.subtasks:
            print(f"      subtasks: {len(task.subtasks)}")
    print()
    
    # Try to get next tasks
    print("Calling queue_service.get_next_tasks(limit=5)...")
    next_tasks = queue_service.get_next_tasks(limit=5)
    print(f"Returned {len(next_tasks)} tasks:")
    for task in next_tasks:
        print(f"  - {task.task_id}: {task.analysis_type}")
    print()
    
    # Calculate available slots
    available_slots = max(0, config['max_concurrent_tasks'] - running_count)
    print(f"Available Slots: {available_slots}")
    print()
    
    if len(pending_main) > 0 and len(next_tasks) == 0 and available_slots > 0:
        print("⚠️  WARNING: Pending tasks exist but queue returned nothing!")
        print("   This suggests a filtering or query issue.")
        
        # Check first pending task in detail
        task = pending_main[0]
        print(f"\n   Checking first pending task: {task.task_id}")
        print(f"   - Status: {task.status} (enum: {AnalysisStatus.PENDING})")
        print(f"   - is_main_task: {task.is_main_task} (type: {type(task.is_main_task)})")
        print(f"   - Analysis type: {task.analysis_type}")
        
        # Check if it would pass the filters
        is_pending = task.status == AnalysisStatus.PENDING
        is_main = (task.is_main_task == True) or (task.is_main_task == None)
        print(f"   - Passes status filter: {is_pending}")
        print(f"   - Passes is_main_task filter: {is_main}")
