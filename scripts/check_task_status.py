"""Quick script to check task status"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask

def check_task(task_id):
    app = create_app()
    with app.app_context():
        task = AnalysisTask.query.filter_by(task_id=task_id).first()
        if not task:
            print(f"Task {task_id} NOT FOUND")
            return
        
        print(f"Task ID: {task.task_id}")
        print(f"Status: {task.status.value if task.status else 'unknown'}")
        print(f"Progress: {task.progress_percentage}%")
        print(f"Started: {task.started_at}")
        print(f"Completed: {task.completed_at}")
        print(f"Error: {task.error_message or 'None'}")
        print(f"\nTarget: {task.target_model} app{task.target_app_number}")
        print(f"Type: {task.analysis_type.value if task.analysis_type else 'unknown'}")

if __name__ == '__main__':
    task_id = sys.argv[1] if len(sys.argv) > 1 else 'task_982d72cfa0f4'
    check_task(task_id)
