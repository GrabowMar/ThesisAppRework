"""Quick check for task hierarchy in database."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask

app = create_app()

with app.app_context():
    # Check main tasks
    main_tasks = AnalysisTask.query.filter_by(is_main_task=True).limit(5).all()
    print(f'Found {len(main_tasks)} main tasks:')
    
    for task in main_tasks:
        print(f'\n  Task: {task.task_name}')
        print(f'    - ID: {task.task_id}')
        print(f'    - Status: {task.status.value if task.status else "N/A"}')
        print(f'    - Subtasks: {len(task.subtasks)}')
        
        for subtask in task.subtasks:
            print(f'      └─ {subtask.service_name}: {subtask.status.value if subtask.status else "N/A"}')
    
    if not main_tasks:
        print('\nNo main tasks found. Database might be empty or needs migration.')
        
        # Check if there are ANY tasks
        all_tasks = AnalysisTask.query.limit(5).all()
        print(f'\nTotal tasks in DB: {AnalysisTask.query.count()}')
        
        if all_tasks:
            print('\nSample tasks (not main tasks):')
            for task in all_tasks[:3]:
                print(f'  - {task.task_name} (is_main_task={task.is_main_task})')
