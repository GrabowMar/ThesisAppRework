"""Update created tasks to pending status so they get picked up by task executor."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.extensions import db

app = create_app()

with app.app_context():
    # Find all tasks in CREATED status
    created_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.CREATED).all()
    
    print(f"Found {len(created_tasks)} tasks in CREATED status")
    
    if not created_tasks:
        print("No tasks to update!")
        sys.exit(0)
    
    print("\nTasks to update:")
    for task in created_tasks:
        task_type = "Main" if task.is_main_task else f"Sub ({task.service_name})"
        print(f"  {task_type}: {task.target_model}/app{task.target_app_number}")
    
    # Update all to PENDING
    for task in created_tasks:
        task.status = AnalysisStatus.PENDING
    
    db.session.commit()
    
    print(f"\nSuccessfully updated {len(created_tasks)} tasks from CREATED to PENDING")
    print("These tasks will now be picked up by the task execution service.")
