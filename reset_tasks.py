import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus

def reset_stuck_tasks():
    app = create_app()
    with app.app_context():
        # Find all RUNNING tasks
        running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
        print(f"Found {len(running_tasks)} stuck tasks in RUNNING state.")
        
        for task in running_tasks:
            print(f"  Resetting task {task.task_id} ({task.target_model}/app{task.target_app_number})")
            task.status = AnalysisStatus.FAILED
            task.error_message = "Reset by administrator due to stale state."
            
        db.session.commit()
        print("Done. All stuck tasks have been marked as FAILED.")

if __name__ == "__main__":
    reset_stuck_tasks()
