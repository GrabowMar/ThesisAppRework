"""
End-to-End Task Execution Test
===============================

Tests the complete task execution pipeline from creation to completion.
"""

import sys
import os
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_path))

import time
from app.factory import create_app
from app.extensions import db
from app.services.task_service import AnalysisTaskService
from app.constants import AnalysisStatus

def test_task_execution():
    """Test end-to-end task execution with ThreadPoolExecutor."""
    
    print("=" * 80)
    print("TASK EXECUTION END-TO-END TEST")
    print("=" * 80)
    
    # Create app context
    app = create_app('development')
    
    with app.app_context():
        print("\n1. Creating test task...")
        try:
            # Create a simple task with a few tools
            task = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug='openai_gpt-4.1-2025-04-14',
                app_number=4,
                tools=['bandit', 'safety', 'eslint', 'pylint'],  # Mix of tools across services
                priority='normal',
                task_name='test_task_execution',
                description='End-to-end test of ThreadPoolExecutor execution'
            )
            
            print(f"✓ Task created: {task.task_id}")
            print(f"  - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
            print(f"  - Is main task: {task.is_main_task}")
            print(f"  - Total steps: {task.total_steps}")
            print(f"  - Subtasks: {len(task.subtasks) if task.subtasks else 0}")
            
            if task.subtasks:
                print("\n  Subtasks created:")
                for subtask in task.subtasks:
                    print(f"    - {subtask.task_id} ({subtask.service_name}): {subtask.status.value if hasattr(subtask.status, 'value') else subtask.status}")
            else:
                print("\n  ⚠️  WARNING: No subtasks created!")
            
        except Exception as e:
            print(f"✗ Failed to create task: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n2. Waiting for task execution (max 30 seconds)...")
        max_wait = 30
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            # Refresh task from DB
            db.session.expire(task)
            task = AnalysisTaskService.get_task(task.task_id)
            
            status = task.status.value if hasattr(task.status, 'value') else task.status
            progress = task.progress_percentage
            
            print(f"  [{int(time.time() - start_time)}s] Status: {status}, Progress: {progress}%", end='\r')
            
            # Check if completed (success or failure)
            if status in ['completed', 'failed', 'cancelled']:
                print()  # New line after progress
                break
            
            time.sleep(1)
        
        # Final status
        print("\n3. Final task status:")
        task = AnalysisTaskService.get_task(task.task_id)
        print(f"  - Task ID: {task.task_id}")
        print(f"  - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        print(f"  - Progress: {task.progress_percentage}%")
        print(f"  - Error: {task.error_message or 'None'}")
        
        if task.subtasks:
            print("\n  Subtask statuses:")
            for subtask in task.subtasks:
                status = subtask.status.value if hasattr(subtask.status, 'value') else subtask.status
                print(f"    - {subtask.service_name}: {status} ({subtask.progress_percentage}%)")
                if subtask.error_message:
                    print(f"      Error: {subtask.error_message}")
        
        # Check for results
        print("\n4. Checking for results...")
        try:
            from app.services.results_api_service import ResultsAPIService
            results_service = ResultsAPIService()
            results = results_service.get_task_results(task.task_id)
            
            if results:
                print(f"✓ Found results for task {task.task_id}")
                print(f"  - Keys: {list(results.keys())}")
            else:
                print(f"⚠️  No results found for task {task.task_id}")
        except Exception as e:
            print(f"✗ Failed to check results: {e}")
        
        # Determine success
        final_status = task.status.value if hasattr(task.status, 'value') else task.status
        success = final_status == 'completed'
        
        print("\n" + "=" * 80)
        if success:
            print("✓ TEST PASSED: Task completed successfully")
        else:
            print(f"✗ TEST FAILED: Task ended with status '{final_status}'")
        print("=" * 80)
        
        return success

if __name__ == '__main__':
    try:
        success = test_task_execution()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
