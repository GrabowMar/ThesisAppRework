import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.constants import AnalysisStatus
from sqlalchemy import or_

app = create_app()
with app.app_context():
    print("Testing the exact query used by /analysis/api/tasks/list endpoint...\n")
    
    try:
        # Exact query from the endpoint
        all_tasks_query = AnalysisTask.query.filter(
            or_(
                AnalysisTask.is_main_task == True,
                AnalysisTask.parent_task_id == None
            )
        )
        
        all_tasks = all_tasks_query.order_by(AnalysisTask.created_at.desc()).all()
        
        print(f"✅ Query succeeded! Found {len(all_tasks)} tasks\n")
        
        # Show first 10
        print("First 10 tasks:")
        for task in all_tasks[:10]:
            status_val = task.status.value if hasattr(task.status, 'value') else task.status
            print(f"  {task.task_id}: {status_val} | {task.target_model} app{task.target_app_number} | {task.created_at}")
        
        # Check for the specific task
        haiku_task = next((t for t in all_tasks if t.task_id == 'task_aac9d905af66'), None)
        if haiku_task:
            print(f"\n✅ task_aac9d905af66 is in the results (position {all_tasks.index(haiku_task) + 1} of {len(all_tasks)})")
        else:
            print(f"\n❌ task_aac9d905af66 NOT in the results")
            
    except Exception as e:
        print(f"❌ Query failed with error:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
