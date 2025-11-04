import sys
sys.path.insert(0, "src")
from app.factory import create_app
from app.models import AnalysisTask

app = create_app("development")
with app.app_context():
    recent = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(5).all()
    
    print("\n5 Most Recent Tasks:")
    for task in recent:
        status_val = task.status.value if hasattr(task.status, 'value') else str(task.status)
        print(f"\n  Task: {task.task_id}")
        print(f"    Status: {status_val}")
        print(f"    Model: {task.target_model}")
        print(f"    App: {task.target_app_number}")
        print(f"    Progress: {task.progress_percentage}%")
        if task.error_message:
            print(f"    Error: {task.error_message[:100]}")
