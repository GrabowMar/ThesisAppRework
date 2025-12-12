import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask, AnalysisStatus
from app.extensions import db
app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_68a4102d7c93').first()
    if task:
        print(f"Task: {task.task_id}")
        print(f"  status: {task.status.value}")
        print(f"  is_main_task: {task.is_main_task}")
        print(f"  started_at: {task.started_at}")
        
    # Check if there are PENDING + is_main_task tasks
    pending = AnalysisTask.query.filter(
        AnalysisTask.status == AnalysisStatus.PENDING,
        (AnalysisTask.is_main_task == True) | (AnalysisTask.is_main_task == None)
    ).all()
    print(f"\nPENDING main tasks: {len(pending)}")
    for t in pending:
        print(f"  {t.task_id}: {t.task_name}")
