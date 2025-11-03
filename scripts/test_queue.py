"""Test queue service to see if it finds pending tasks."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.factory import create_app
from app.services.task_service import queue_service
from app.extensions import get_components

app = create_app()

with app.app_context():
    # Get pending tasks via queue service
    tasks = queue_service.get_next_tasks(limit=3)
    print(f"\nQueue service found {len(tasks)} task(s) to execute")
    
    if tasks:
        for task in tasks:
            print(f"\n  Task: {task.task_id}")
            print(f"    Status: {task.status.value if task.status else 'None'}")
            print(f"    Model: {task.target_model}")
            print(f"    App: {task.target_app_number}")
            print(f"    is_main_task: {task.is_main_task}")
    else:
        print("\nNo tasks selected by queue service")
        
        # Check database directly
        pending_count = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        print(f"  Total PENDING tasks in DB: {pending_count}")
        
        pending_main = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.PENDING,
            (AnalysisTask.is_main_task == True) | (AnalysisTask.is_main_task == None)
        ).count()
        print(f"  PENDING main tasks in DB: {pending_main}")
        
        # Check if there are running tasks blocking
        running_count = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).count()
        print(f"  RUNNING tasks: {running_count}")
    
    # Check components
    components = get_components()
    print(f"\nComponents available: {components is not None}")
