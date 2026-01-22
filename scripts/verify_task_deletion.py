"""Verify task deletion and check for any remaining references."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.models.pipeline import PipelineExecution

app = create_app()
with app.app_context():
    # Check for any tasks with app 1 or 2 for the claude model
    model = 'anthropic_claude-4.5-sonnet-20250929'
    
    print("Checking for tasks with apps 1 and 2...")
    for app_num in [1, 2]:
        tasks = AnalysisTask.query.filter_by(
            target_model=model,
            target_app_number=app_num
        ).all()
        
        print(f"\nApp {app_num}: {len(tasks)} tasks found")
        if tasks:
            for t in tasks:
                print(f"  - {t.task_id} (status: {t.status}, main: {t.is_main_task})")
        else:
            print(f"  ✓ No tasks remain for app {app_num}")
    
    # Check all main tasks for the model
    print(f"\n\nAll main tasks for {model}:")
    main_tasks = AnalysisTask.query.filter_by(
        target_model=model,
        is_main_task=True
    ).all()
    
    print(f"Found {len(main_tasks)} main tasks")
    for t in main_tasks:
        print(f"  - App {t.target_app_number}: {t.task_id} ({t.status})")
