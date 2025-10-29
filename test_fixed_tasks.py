#!/usr/bin/env python3
"""Test script to verify task execution fix."""
import sys
import time
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.extensions import db
from app.constants import AnalysisStatus

app = create_app()

with app.app_context():
    print("\n" + "="*80)
    print("TASK EXECUTION TEST")
    print("="*80)
    
    # Get all tasks (including new ones)
    all_tasks = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(15).all()
    
    print(f"\nFound {len(all_tasks)} recent tasks")
    
    # Group by main vs subtasks
    main_tasks = [t for t in all_tasks if t.is_main_task]
    subtasks = [t for t in all_tasks if not t.is_main_task]
    
    print(f"  Main tasks: {len(main_tasks)}")
    print(f"  Subtasks: {len(subtasks)}")
    
    # Check if any pending subtasks exist (should NOT happen after fix)
    pending_subtasks = [t for t in subtasks if t.status == AnalysisStatus.PENDING]
    if pending_subtasks:
        print(f"\n⚠️  WARNING: Found {len(pending_subtasks)} PENDING subtasks!")
        print("  These should be handled by parent task, not daemon loop")
        for st in pending_subtasks:
            print(f"    - {st.task_id} (service: {st.service_name})")
    else:
        print("\n✅ No pending subtasks (correct behavior)")
    
    # Show main tasks status
    print(f"\n--- Main Tasks ({len(main_tasks)}) ---")
    for task in main_tasks:
        status_str = task.status.value if hasattr(task.status, 'value') else task.status
        print(f"\nTask: {task.task_id}")
        print(f"  Status: {status_str}")
        print(f"  Model: {task.target_model}")
        print(f"  App: {task.target_app_number}")
        print(f"  Progress: {task.progress_percentage}%")
        
        if task.error_message:
            print(f"  Error: {task.error_message[:200]}")
        
        # Show subtasks
        if task.subtasks:
            print(f"  Subtasks: {len(task.subtasks)}")
            for st in task.subtasks:
                st_status = st.status.value if hasattr(st.status, 'value') else st.status
                print(f"    - {st.service_name}: {st_status} ({st.progress_percentage}%)")
                if st.error_message and len(st.error_message) < 100:
                    print(f"      Error: {st.error_message}")
    
    print("\n" + "="*80)
