"""Check test task status."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask, db

app = create_app()
with app.app_context():
    task = db.session.query(AnalysisTask).filter_by(task_id="test_1761719152").first()
    if task:
        print(f"Task found:")
        print(f"  Task ID: {task.task_id}")
        print(f"  Status: {task.status}")
        print(f"  Target Model: {task.target_model}")
        print(f"  Target App: {task.target_app_number}")
        print(f"  Created: {task.created_at}")
        print(f"  Started: {task.started_at}")
        print(f"  Completed: {task.completed_at}")
        print(f"  Error: {task.error_message}")
        print(f"  Issues Found: {task.issues_found}")
    else:
        print("Task not found!")
