import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.paths import RESULTS_DIR

app = create_app()
with app.app_context():
    failed_tasks = AnalysisTask.query.filter_by(status=AnalysisStatus.FAILED).all()
    print(f'Total FAILED tasks: {len(failed_tasks)}')
    
    for task in failed_tasks[:5]:
        print(f'\nTask: {task.task_id}')
        print(f'  Model: {task.target_model}')
        print(f'  App: {task.target_app_number}')
        print(f'  Has result_summary: {task.result_summary is not None}')
        print(f'  Completed at: {task.completed_at}')
        print(f'  Error: {task.error_message[:80] if task.error_message else "None"}')
        
        # Check for files
        task_id_clean = task.task_id.replace('task_', '', 1) if task.task_id.startswith('task_') else task.task_id
        task_dir = RESULTS_DIR / task.target_model / f"app{task.target_app_number}" / f"task_{task_id_clean}"
        if task_dir.exists():
            json_files = list(task_dir.glob("*.json"))
            print(f'  Files on disk: {len(json_files)} JSON files')
        else:
            print(f'  Files on disk: No directory')
