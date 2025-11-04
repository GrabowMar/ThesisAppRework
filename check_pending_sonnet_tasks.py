import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.constants import AnalysisStatus

app = create_app()
with app.app_context():
    # Check for pending tasks for that specific model
    pending_tasks = AnalysisTask.query.filter(
        AnalysisTask.target_model == 'anthropic_claude-4.5-sonnet-20250929',
        AnalysisTask.target_app_number == 1,
        AnalysisTask.status == AnalysisStatus.PENDING
    ).all()
    
    print(f"\nFound {len(pending_tasks)} PENDING tasks for anthropic_claude-4.5-sonnet-20250929 app 1:\n")
    
    for task in pending_tasks:
        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
        print(f"Task ID: {task.task_id}")
        print(f"  Created: {task.created_at}")
        print(f"  Task Name: {task.task_name}")
        print(f"  Is Main: {task.is_main_task}")
        print(f"  Priority: {task.priority.value if task.priority else 'None'}")
        print(f"  Metadata source: {meta.get('custom_options', {}).get('source', 'unknown')}")
        print()
    
    # Check all tasks for this model/app
    all_tasks = AnalysisTask.query.filter(
        AnalysisTask.target_model == 'anthropic_claude-4.5-sonnet-20250929',
        AnalysisTask.target_app_number == 1
    ).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    
    print(f"\nLast 10 tasks for this model/app (any status):\n")
    for task in all_tasks:
        status_val = task.status.value if hasattr(task.status, 'value') else task.status
        print(f"{task.task_id}: {status_val} | {task.created_at} | {task.task_name}")
