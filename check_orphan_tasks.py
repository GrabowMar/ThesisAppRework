"""Check for orphan analysis tasks."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    tasks = AnalysisTask.query.filter_by(target_model='openai_codex-mini', target_app_number=4658).all()
    print(f'\nFound {len(tasks)} tasks for openai_codex-mini/app4658')
    
    for t in tasks[:10]:
        print(f'\n  Task {t.task_id}:')
        print(f'    Name: {t.task_name}')
        print(f'    Created: {t.created_at}')
        print(f'    Status: {t.status}')
        print(f'    Metadata: {t.metadata}')
