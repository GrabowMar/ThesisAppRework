"""Manually trigger task execution to test the system."""
from src.app.factory import create_app
from src.app.services.task_service import queue_service
from src.app.extensions import get_components

app = create_app()

with app.app_context():
    # Get pending tasks
    tasks = queue_service.get_next_tasks(limit=1)
    print(f"Found {len(tasks)} pending task(s)")
    
    if tasks:
        task = tasks[0]
        print(f"Task: {task.task_id}")
        print(f"Status: {task.status}")
        print(f"Model: {task.target_model}")
        print(f"App: {task.target_app_number}")
        print(f"is_main_task: {task.is_main_task}")
        
        # Check components
        components = get_components()
        print(f"Components available: {components is not None}")
    else:
        print("No tasks selected by queue service")
        
        # Check database directly
        from src.app.models import AnalysisTask
        from src.app.constants import AnalysisStatus
        
        pending_count = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).count()
        print(f"Total PENDING tasks in DB: {pending_count}")
        
        pending_main = AnalysisTask.query.filter(
            AnalysisTask.status == AnalysisStatus.PENDING,
            (AnalysisTask.is_main_task == True) | (AnalysisTask.is_main_task == None)
        ).count()
        print(f"PENDING main tasks in DB: {pending_main}")
