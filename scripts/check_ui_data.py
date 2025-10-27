"""Check if UI is showing openai_codex-mini tasks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models.analysis_models import AnalysisTask

app = create_app()

with app.app_context():
    print("=" * 70)
    print("Checking UI Data Availability")
    print("=" * 70)
    
    # 1. Database tasks
    print("\n1. Database Tasks (openai_codex-mini):")
    tasks = AnalysisTask.query.filter_by(target_model='openai_codex-mini').all()
    print(f"   Total: {len(tasks)}")
    
    for task in tasks[:3]:
        print(f"\n   Task: {task.task_id}")
        print(f"   - App: {task.target_app_number}")
        print(f"   - Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        print(f"   - Has result_summary: {bool(task.result_summary)}")
    
    # 2. Check results directory
    print("\n2. Results Directory Structure:")
    results_dir = Path('results/openai_codex-mini')
    if results_dir.exists():
        app_dirs = sorted(results_dir.iterdir())
        print(f"   Total app directories: {len(app_dirs)}")
        
        total_files = 0
        for app_dir in app_dirs:
            task_dirs = list(app_dir.iterdir())
            print(f"\n   {app_dir.name}:")
            for task_dir in task_dirs:
                json_files = list(task_dir.glob('*.json'))
                total_files += len(json_files)
                print(f"     - {task_dir.name}: {len(json_files)} JSON files")
    else:
        print("   ❌ Results directory doesn't exist")
        total_files = 0
    
    print("\n" + "=" * 70)
    print("Summary:")
    print(f"  - Database tasks: {len(tasks)}")
    print(f"  - Disk directories: {len(app_dirs) if 'app_dirs' in locals() else 0}")
    print(f"  - Total result files: {total_files}")
    
    if len(tasks) > 0 and total_files > 0:
        print("\n✅ UI should show openai_codex-mini results!")
        print("   Check at: http://localhost:5000/analysis/list")
    else:
        print("\n❌ Missing data for UI display")
    print("=" * 70)
