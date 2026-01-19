"""
Fix Stuck Task Statuses
=======================

This script resets stuck analysis tasks from RUNNING back to PENDING status.

The script identifies tasks that are stuck in RUNNING state (likely due to crashes
or timeouts) and resets them to allow re-processing. This includes:

- Resetting task status to PENDING
- Clearing started_at timestamp
- Resetting progress percentage to 0
- Clearing error messages
- Resetting any associated subtasks

Usage:
    python scripts/fix_task_statuses.py

This script is useful for recovering from system crashes or when tasks get
stuck due to infrastructure issues. It should be run periodically as part
of system maintenance.
"""

# Add src directory to path
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask, AnalysisStatus

def fix_stuck_tasks():
    app = create_app()
    with app.app_context():
        print("Checking for stuck tasks...")
        
        # Find all RUNNING tasks
        running_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
        
        if not running_tasks:
            print("No stuck tasks found.")
            return
            
        print(f"Found {len(running_tasks)} running tasks. Resetting to PENDING...")
        
        count = 0
        for task in running_tasks:
            print(f"Resetting task {task.task_id} (started: {task.started_at})")
            task.status = AnalysisStatus.PENDING
            task.started_at = None
            task.progress_percentage = 0.0
            task.error_message = None
            
            # Also reset subtasks if any
            if hasattr(task, 'subtasks'):
                for subtask in task.subtasks:
                    if subtask.status in [AnalysisStatus.RUNNING, AnalysisStatus.PENDING]:
                        print(f"  - Resetting subtask {subtask.task_id}")
                        subtask.status = AnalysisStatus.PENDING
                        subtask.started_at = None
                        subtask.progress_percentage = 0.0
                        subtask.error_message = None
            
            count += 1
            
        try:
            db.session.commit()
            print(f"Successfully reset {count} tasks.")
        except Exception as e:
            db.session.rollback()
            print(f"Error saving changes: {e}")

if __name__ == '__main__':
    fix_stuck_tasks()
