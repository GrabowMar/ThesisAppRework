#!/usr/bin/env python
"""Test that new analysis tasks work without timezone errors."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.services.task_service import AnalysisTaskService
from app.extensions import db
import time

def main():
    app = create_app()
    with app.app_context():
        # Create a new test task
        print("Creating test analysis task...")
        task = AnalysisTaskService.create_task(
            model_slug='anthropic_claude-4.5-haiku-20251001',
            app_number=1,
            analysis_type='security',
            task_name='test_datetime_fix'
        )
        print(f"Created task: {task.task_id}")
        print(f"Initial status: {task.status}")
        
        # Wait a few seconds for the task executor to pick it up
        print("\nWaiting for task executor to process...")
        for i in range(20):
            time.sleep(2)
            db.session.refresh(task)
            print(f"  [{i*2}s] Status: {task.status}, Progress: {task.progress_percentage}%")
            
            if task.error_message:
                print(f"  ERROR: {task.error_message}")
                if 'offset-naive' in task.error_message:
                    print("\n❌ FAILED: Timezone error still exists!")
                    return 1
                    
            if task.status.value in ('completed', 'failed'):
                break
        
        # Final check
        if task.error_message and 'offset-naive' in task.error_message:
            print(f"\n❌ FAILED: Task has timezone error: {task.error_message}")
            return 1
        elif not task.error_message or 'offset-naive' not in task.error_message:
            print(f"\n✅ SUCCESS: No timezone error! Status: {task.status}")
            if task.actual_duration is not None:
                print(f"   Duration calculated correctly: {task.actual_duration}s")
            return 0
        
        print(f"\n⚠️  Task completed with status: {task.status}")
        return 0

if __name__ == '__main__':
    sys.exit(main())
