"""
Delete all tasks for anthropic_claude-4.5-sonnet-20250929 app 1
"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.extensions import db

app = create_app()
with app.app_context():
    print("Deleting all tasks for anthropic_claude-4.5-sonnet-20250929 app 1...\n")
    
    # Count tasks before deletion
    tasks_to_delete = AnalysisTask.query.filter(
        AnalysisTask.target_model == 'anthropic_claude-4.5-sonnet-20250929',
        AnalysisTask.target_app_number == 1
    ).all()
    
    total_tasks = len(tasks_to_delete)
    print(f"Found {total_tasks} tasks to delete")
    
    if total_tasks == 0:
        print("No tasks to delete.")
    else:
        print("\nTasks to be deleted:")
        for task in tasks_to_delete[:10]:  # Show first 10
            status_val = task.status.value if hasattr(task.status, 'value') else task.status
            print(f"  {task.task_id}: {status_val} | {task.created_at}")
        if total_tasks > 10:
            print(f"  ... and {total_tasks - 10} more")
        
        # Delete all tasks
        try:
            deleted_count = AnalysisTask.query.filter(
                AnalysisTask.target_model == 'anthropic_claude-4.5-sonnet-20250929',
                AnalysisTask.target_app_number == 1
            ).delete()
            db.session.commit()
            print(f"\n✅ Successfully deleted {deleted_count} tasks")
            
            # Verify deletion
            remaining = AnalysisTask.query.filter(
                AnalysisTask.target_model == 'anthropic_claude-4.5-sonnet-20250929',
                AnalysisTask.target_app_number == 1
            ).count()
            print(f"Remaining tasks for this model/app: {remaining}")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ Error deleting tasks: {e}")
            import traceback
            traceback.print_exc()
