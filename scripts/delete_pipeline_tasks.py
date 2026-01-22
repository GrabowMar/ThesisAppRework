"""
Script to delete specific analysis tasks from the database.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.extensions import db
from app.models.analysis_models import AnalysisTask, AnalysisResult

def delete_analysis_tasks(task_ids: list[str]):
    """Delete analysis tasks by their task IDs."""
    app = create_app()
    
    with app.app_context():
        deleted_count = 0
        not_found = []
        
        for task_id in task_ids:
            # Query for the analysis task
            task = AnalysisTask.query.filter_by(task_id=task_id).first()
            
            if task:
                print(f"Found analysis task: {task.task_id}")
                print(f"  Status: {task.status}")
                print(f"  Model: {task.target_model}")
                print(f"  App: {task.target_app_number}")
                print(f"  Created: {task.created_at}")
                print(f"  Is main task: {task.is_main_task}")
                
                # Count results that will be deleted (cascade)
                result_count = len(task.results)
                if result_count > 0:
                    print(f"  Has {result_count} associated result(s)")
                
                # Count subtasks that will be deleted (cascade)
                if task.is_main_task:
                    subtask_count = len(task.subtasks)
                    if subtask_count > 0:
                        print(f"  Has {subtask_count} subtask(s)")
                
                # Delete the task (results and subtasks will be cascade deleted)
                db.session.delete(task)
                deleted_count += 1
                print(f"  ✓ Deleted\n")
            else:
                not_found.append(task_id)
                print(f"Analysis task not found: {task_id}\n")
        
        # Commit all deletions
        if deleted_count > 0:
            db.session.commit()
            print(f"\nSuccessfully deleted {deleted_count} analysis task(s)")
        
        if not_found:
            print(f"\nNot found: {', '.join(not_found)}")

def delete_by_model_and_app(model_slug: str, app_numbers: list[int], batch_id: str = None):
    """Delete analysis tasks by model slug and app numbers."""
    app = create_app()
    
    with app.app_context():
        deleted_count = 0
        deleted_ids = []
        
        for app_number in app_numbers:
            # Query for all tasks matching model and app number
            query = AnalysisTask.query.filter_by(
                target_model=model_slug,
                target_app_number=app_number
            )
            
            if batch_id:
                query = query.filter_by(batch_id=batch_id)
            
            tasks = query.all()
            
            print(f"\nSearching for {model_slug} app {app_number}:")
            print(f"  Found {len(tasks)} task(s)")
            
            for task in tasks:
                print(f"  - Task ID: {task.task_id}")
                print(f"    Status: {task.status}")
                print(f"    Batch: {task.batch_id}")
                print(f"    Main task: {task.is_main_task}")
                
                deleted_ids.append(task.task_id)
                # Delete the task
                db.session.delete(task)
                deleted_count += 1
                print(f"    ✓ Marked for deletion")
        
        # Commit with explicit flush
        if deleted_count > 0:
            print(f"\nCommitting deletion of {deleted_count} task(s)...")
            try:
                db.session.flush()
                db.session.commit()
                print(f"✓ Successfully deleted {deleted_count} analysis task(s)")
                
                # Verify deletion
                print("\nVerifying deletion...")
                for task_id in deleted_ids[:3]:  # Check first 3
                    check = AnalysisTask.query.filter_by(task_id=task_id).first()
                    if check:
                        print(f"  ⚠ Task {task_id} still exists!")
                    else:
                        print(f"  ✓ Task {task_id} confirmed deleted")
                        
            except Exception as e:
                db.session.rollback()
                print(f"✗ Error during commit: {e}")
                raise
        else:
            print("\nNo tasks found to delete")

if __name__ == '__main__':
    # The two tasks from the screenshot: apps 1 and 2 for this model
    model_slug = 'anthropic_claude-4.5-sonnet-20250929'
    app_numbers = [1, 2]
    
    print("Deleting analysis tasks...")
    print("=" * 60)
    
    delete_by_model_and_app(model_slug, app_numbers)
