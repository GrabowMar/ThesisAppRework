#!/usr/bin/env python
"""Simple test: create static-only analysis task and check it completes successfully."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.services.task_service import AnalysisTaskService

app = create_app()

with app.app_context():
    print("Creating static-only analysis task...")
    
    # Create task with explicit task_name to make analysis "comprehensive" run only static
    task = AnalysisTaskService.create_task(
        model_slug="anthropic_claude-4.5-haiku-20251001",
        app_number=2,
        tools=['bandit'],  # Single fast tool
        config_id=None,
        priority='normal',
        custom_options={
            'tools': ['bandit'],
            'source': 'fix_test'
        },
        batch_id=None,
        task_name='static'  # This will trigger static-only path
    )
    
    print(f"[OK] Created task: {task.task_id} (status: {task.status.value})")
    
    # Wait max 30s for completion
    print("Waiting for task execution...")
    for i in range(30):
        time.sleep(2)
        db.session.expire_all()
        task = AnalysisTask.query.get(task.id)
        status = task.status.value
        progress = task.progress_percentage or 0
        print(f"  [{i*2:>2}s] Status: {status:15} | Progress: {progress:3.0f}%")
        
        if status in ['completed', 'failed', 'partial_success']:
            break
    
    # Final check
    db.session.expire_all()
    task = AnalysisTask.query.get(task.id)
    
    print(f"\n{'='*60}")
    print(f"Final Status: {task.status.value}")
    print(f"Issues Found: {task.issues_found or 0}")
    if task.error_message:
        print(f"Error: {task.error_message}")
    
    # Check results directory
    results_base = Path(__file__).parent / "results"
    model_slug = task.target_model.replace('/', '_').replace('\\', '_')
    
    task_dirs = [
        results_base / model_slug / f"app{task.target_app_number}" / task.task_id,
        results_base / model_slug / f"app{task.target_app_number}" / f"task_{task.task_id.replace('task_', '')}"
    ]
    
    found_results = False
    for task_dir in task_dirs:
        if task_dir.exists():
            print(f"\n[OK] Results in: {task_dir.name}/")
            json_files = list(task_dir.glob("*.json"))
            for jf in json_files:
                size_kb = jf.stat().st_size / 1024
                print(f"  - {jf.name} ({size_kb:.1f} KB)")
                found_results = True
            break
    
    if not found_results:
        print(f"\n[X] No result files found")
    
    # VERDICT
    print(f"\n{'='*60}")
    success = task.status.value in ['completed', 'partial_success'] and found_results
    if success:
        print("[PASS] TEST PASSED - Fixes working correctly!")
    else:
        print(f"[FAIL] TEST FAILED - Status: {task.status.value}, Files: {found_results}")
        sys.exit(1)
