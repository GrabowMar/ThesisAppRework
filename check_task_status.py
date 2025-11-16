#!/usr/bin/env python
"""Quick script to check task status."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()

with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_f8c558a7a630').first()
    
    if not task:
        print("Task not found!")
        sys.exit(1)
    
    print(f"Task ID: {task.task_id}")
    print(f"Status: {task.status.value}")
    print(f"Progress: {task.progress_percentage or 0}%")
    print(f"Issues: {task.issues_found or 0}")
    print(f"Started: {task.started_at}")
    print(f"Completed: {task.completed_at}")
    
    if task.error_message:
        print(f"Error: {task.error_message}")
    
    # Check for results directory
    results_base = Path(__file__).parent / "results"
    model_slug = task.target_model.replace('/', '_').replace('\\', '_')
    task_dirs = [
        results_base / model_slug / f"app{task.target_app_number}" / task.task_id,
        results_base / model_slug / f"app{task.target_app_number}" / f"task_{task.task_id}"
    ]
    
    print(f"\nChecking for results...")
    for task_dir in task_dirs:
        if task_dir.exists():
            print(f"✓ Found: {task_dir}")
            json_files = list(task_dir.glob("*.json"))
            for jf in json_files:
                print(f"  - {jf.name} ({jf.stat().st_size / 1024:.1f} KB)")
        else:
            print(f"✗ Not found: {task_dir}")
