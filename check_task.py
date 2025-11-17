import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_907aff10a7cc').first()
    if task:
        print(f"Status: {task.status.value}")
        print(f"Started: {task.started_at}")
        print(f"Completed: {task.completed_at}")
        if task.error_message:
            print(f"Error: {task.error_message}")
        if task.result_summary:
            import json
            summary = json.loads(task.result_summary) if isinstance(task.result_summary, str) else task.result_summary
            print(f"Summary: {json.dumps(summary, indent=2)}")
    else:
        print("Task not found!")
