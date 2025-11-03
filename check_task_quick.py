from src.app.factory import create_app
from src.app.data.database import get_db_session
from src.app.data.models import AnalysisTask

app = create_app()
with app.app_context():
    session = get_db_session()
    task = session.query(AnalysisTask).filter_by(id='task_e72e455f2245').first()
    if task:
        print(f'Task: {task.id}')
        print(f'Status: {task.status}')
        print(f'Created: {task.created_at}')
        print(f'Updated: {task.updated_at}')
        print(f'Tools: {task.requested_tools}')
        print(f'Priority: {task.priority}')
        print(f'Result Path: {task.result_path if hasattr(task, "result_path") else "N/A"}')
    else:
        print('Task not found')
