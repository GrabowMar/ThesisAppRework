import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask, AnalysisStatus
from app.extensions import db
import uuid
app = create_app()
with app.app_context():
    # Create a new simple analysis task
    task_id = f"task_test_{uuid.uuid4().hex[:8]}"
    task = AnalysisTask(
        task_id=task_id,
        task_name=f"test:anthropic_claude-3-5-haiku:2",
        target_model="anthropic_claude-3-5-haiku",
        target_app_number=2,
        analysis_type="comprehensive",
        status=AnalysisStatus.PENDING,
        is_main_task=True
    )
    db.session.add(task)
    db.session.commit()
    print(f"Created test task: {task_id}")
    print("TaskExecutionService should pick it up within 5 seconds")
