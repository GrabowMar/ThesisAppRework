#!/usr/bin/env python3
"""
Test script to verify that old PENDING tasks are cancelled on app startup.
This ensures tasks from previous sessions don't auto-execute after reboot.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db


def create_old_pending_task(model_slug="test_model", app_number=1, age_minutes=35):
    """Create a PENDING task with old timestamp to simulate leftover from previous session."""
    app = create_app()
    
    with app.app_context():
        task = AnalysisTask()
        task.task_id = f"task_old_pending_{datetime.now().timestamp()}"
        task.target_model = model_slug
        task.target_app_number = app_number
        task.status = AnalysisStatus.PENDING
        task.task_name = "Test Old Pending Task"
        task.description = "Simulates a leftover task from previous session"
        task.is_main_task = True
        
        # Set created_at to simulate old task
        old_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
        task.created_at = old_time
        
        # Assign a dummy analyzer config (required by model)
        from app.models import AnalyzerConfiguration
        config = AnalyzerConfiguration.query.first()
        if not config:
            config = AnalyzerConfiguration(name="Test Config", config_data="{}")
            db.session.add(config)
            db.session.flush()
        task.analyzer_config_id = config.id
        
        db.session.add(task)
        db.session.commit()
        
        print(f"✓ Created old PENDING task: {task.task_id}")
        print(f"  Age: {age_minutes} minutes")
        print(f"  Status: {task.status.value}")
        print(f"  Created at: {task.created_at}")
        
        return task.task_id


def check_task_status(task_id):
    """Check if task was cancelled by maintenance service on startup."""
    app = create_app()
    
    with app.app_context():
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        
        if not task:
            print(f"\n❌ Task {task_id} not found")
            return None
        
        print(f"\n📊 Task Status After Startup:")
        print(f"  Task ID: {task.task_id}")
        print(f"  Status: {task.status.value}")
        print(f"  Created at: {task.created_at}")
        print(f"  Completed at: {task.completed_at}")
        print(f"  Error message: {task.error_message or 'None'}")
        
        return task.status


def main():
    """Test startup task cleanup behavior."""
    
    print("\n" + "=" * 80)
    print("Startup Task Cleanup Test")
    print("=" * 80)
    
    print("\n[TEST SETUP]")
    print("This test verifies that old PENDING tasks are automatically")
    print("cancelled by MaintenanceService on app startup, preventing them")
    print("from being picked up by TaskExecutionService.")
    
    print("\n" + "-" * 80)
    print("Step 1: Create old PENDING task (simulates leftover from previous session)")
    print("-" * 80)
    
    task_id = create_old_pending_task(age_minutes=35)
    
    print("\n" + "-" * 80)
    print("Step 2: Simulate app restart (MaintenanceService runs startup cleanup)")
    print("-" * 80)
    
    print("\nWhen Flask app starts:")
    print("  1. MaintenanceService initializes FIRST")
    print("  2. Runs _cleanup_stuck_tasks() immediately")
    print("  3. Old PENDING tasks (>30min) → CANCELLED")
    print("  4. TaskExecutionService starts AFTER cleanup")
    print("  5. Only picks up NEW PENDING tasks, not old ones")
    
    input("\nPress ENTER to check task status after simulated startup...")
    
    print("\n" + "-" * 80)
    print("Step 3: Verify task was cancelled")
    print("-" * 80)
    
    status = check_task_status(task_id)
    
    print("\n" + "=" * 80)
    print("Test Results")
    print("=" * 80)
    
    if status == AnalysisStatus.CANCELLED:
        print("\n✅ TEST PASSED")
        print("\nOld PENDING task was successfully cancelled by MaintenanceService.")
        print("TaskExecutionService will NOT pick up this task on startup.")
        print("\nBehavior verified:")
        print("  ✓ MaintenanceService runs before TaskExecutionService")
        print("  ✓ Old PENDING tasks are cancelled (>30 minutes)")
        print("  ✓ Only fresh PENDING tasks will be executed")
    elif status == AnalysisStatus.PENDING:
        print("\n❌ TEST FAILED")
        print("\nTask is still in PENDING state!")
        print("This means MaintenanceService did not cancel it.")
        print("\nPossible issues:")
        print("  • MaintenanceService not running on startup")
        print("  • Task age threshold not met (<30 minutes)")
        print("  • Startup sequence incorrect (TaskExecutionService before Maintenance)")
    elif status == AnalysisStatus.RUNNING:
        print("\n❌ TEST FAILED (CRITICAL)")
        print("\nTask was picked up and started!")
        print("This means TaskExecutionService ran BEFORE MaintenanceService.")
        print("\nThe startup sequence is incorrect. Fix required in src/app/factory.py")
    else:
        print(f"\n⚠️  UNEXPECTED STATUS: {status.value if status else 'None'}")
        print("\nTask was modified but not in expected way.")
    
    # Cleanup
    print("\n" + "-" * 80)
    print("Cleanup")
    print("-" * 80)
    
    response = input("\nDelete test task? (Y/n): ")
    if response.lower() != 'n':
        app = create_app()
        with app.app_context():
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            if task:
                db.session.delete(task)
                db.session.commit()
                print(f"✓ Deleted task {task_id}")
    
    print("\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Test cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
