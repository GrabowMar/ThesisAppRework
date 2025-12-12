import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask, AnalysisStatus
from app.extensions import db
app = create_app()
with app.app_context():
    # Reset main task
    task = AnalysisTask.query.filter_by(task_id='task_68a4102d7c93').first()
    if task:
        print(f"Found task: {task.task_id} status={task.status}")
        task.status = AnalysisStatus.PENDING
        task.started_at = None
        task.completed_at = None
        task.error_message = None
        print(f"Set to PENDING")
    # Reset subtasks
    subtasks = AnalysisTask.query.filter_by(parent_task_id='task_68a4102d7c93').all()
    for st in subtasks:
        print(f"Resetting subtask: {st.task_id}")
        st.status = AnalysisStatus.PENDING
        st.started_at = None
        st.completed_at = None
        st.error_message = None
    try:
        db.session.commit()
        print(f"Committed - Reset {len(subtasks)} subtasks")
    except Exception as e:
        print(f"Commit failed: {e}")
        db.session.rollback()
    
    # Verify
    task2 = AnalysisTask.query.filter_by(task_id='task_68a4102d7c93').first()
    print(f"After commit: {task2.task_id} status={task2.status}")
