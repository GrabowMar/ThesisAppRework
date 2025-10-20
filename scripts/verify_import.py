#!/usr/bin/env python3
"""Verify that analysis results were imported successfully."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models import AnalysisTask
from app.services.analysis_result_store import load_task_payload

app = create_app()

with app.app_context():
    tasks = AnalysisTask.query.all()
    print(f"\n✅ Total tasks in database: {len(tasks)}\n")
    
    # Group by model and app
    by_model = {}
    for task in tasks:
        key = f"{task.target_model} app{task.target_app_number}"
        if key not in by_model:
            by_model[key] = []
        by_model[key].append(task)
    
    # Display summary
    for key, task_list in sorted(by_model.items()):
        print(f"📦 {key}:")
        for task in task_list:
            analysis_type = task.analysis_type.value if task.analysis_type else "unknown"
            status = task.status.value if task.status else "unknown"
            
            # Check if payload exists
            payload = load_task_payload(task.task_id)
            has_payload = "✅" if payload else "❌"
            
            print(f"  {has_payload} {task.task_id}: {analysis_type} ({status})")
    
    print(f"\n📊 Summary:")
    print(f"  Total unique model/app combinations: {len(by_model)}")
    print(f"  Total analysis tasks: {len(tasks)}")
    
    # Check for missing payloads
    tasks_without_payload = 0
    for task in tasks:
        payload = load_task_payload(task.task_id)
        if not payload:
            tasks_without_payload += 1
    
    if tasks_without_payload > 0:
        print(f"  ⚠️  Tasks without payload: {tasks_without_payload}")
    else:
        print(f"  ✅ All tasks have payloads!")
