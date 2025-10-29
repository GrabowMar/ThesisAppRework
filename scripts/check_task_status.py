"""Quick script to check task status and result availability."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.models import AnalysisTask, AnalysisStatus
from app.factory import create_app

app = create_app()

with app.app_context():
    tasks = AnalysisTask.query.filter_by(is_main_task=True).order_by(AnalysisTask.created_at.desc()).limit(5).all()
    
    print(f"\n{'='*80}")
    print("TASK STATUS CHECK")
    print(f"{'='*80}\n")
    
    for task in tasks:
        print(f"Task ID: {task.task_id}")
        print(f"  Status: {task.status.value if task.status else 'None'}")
        print(f"  Has result_summary: {bool(task.result_summary)}")
        print(f"  Completed at: {task.completed_at}")
        print(f"  Error: {task.error_message if task.error_message else 'None'}")
        
        if task.result_summary:
            try:
                summary = task.get_result_summary()
                total = summary.get('summary', {}).get('total_findings', 0)
                print(f"  Total findings: {total}")
            except Exception as e:
                print(f"  Error parsing summary: {e}")
        print()
