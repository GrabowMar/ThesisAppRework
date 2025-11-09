"""Find where these tasks are coming from."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask
from sqlalchemy import desc

app = create_app()
with app.app_context():
    # Get the most recently created tasks
    recent_tasks = AnalysisTask.query.order_by(desc(AnalysisTask.created_at)).limit(20).all()
    
    print('\n📋 Most Recent 20 Tasks Created:\n')
    for t in recent_tasks:
        print(f'  {t.task_id}:')
        print(f'    Target: {t.target_model}/app{t.target_app_number}')
        print(f'    Name: {t.task_name}')
        print(f'    Status: {t.status}')
        print(f'    Created: {t.created_at}')
        print(f'    Is Main: {t.is_main_task}')
        print()
