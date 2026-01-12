"""Check task errors."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    # Get failed tasks from recent pipeline
    tasks = AnalysisTask.query.filter(
        AnalysisTask.status.in_(['failed', 'FAILED'])
    ).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    
    for t in tasks:
        print(f"\nTask: {t.task_id}")
        print(f"  Model: {t.target_model}")
        print(f"  App: {t.target_app_number}")
        print(f"  Status: {t.status}")
        print(f"  Parent: {t.parent_task_id}")
        print(f"  Error: {t.error_message}")
        print(f"  Created: {t.created_at}")
