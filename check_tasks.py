import sys
import os
from sqlalchemy import func

# Add src to path
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from app.factory import create_app
from app.extensions import db
from app.models import AnalysisTask
from app.constants import AnalysisStatus

def check_tasks():
    app = create_app()
    with app.app_context():
        # Count by status
        counts = db.session.query(
            AnalysisTask.status, func.count(AnalysisTask.status)
        ).group_by(AnalysisTask.status).all()
        
        print("\n=== Task Counts ===")
        for status, count in counts:
            print(f"{status.value}: {count}")
            
        # List RUNNING tasks
        print("\n=== RUNNING Tasks ===")
        running = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
        for t in running:
            print(f"Task {t.task_id}: {t.task_name} (Created: {t.created_at})")
            
        # List PENDING tasks (first 5)
        print("\n=== PENDING Tasks (First 5) ===")
        pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).limit(5).all()
        for t in pending:
            print(f"Task {t.task_id}: {t.task_name} (Created: {t.created_at})")

if __name__ == "__main__":
    check_tasks()
