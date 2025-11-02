"""Check if daemon-processed tasks have result files."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus

def main():
    app = create_app()
    with app.app_context():
        # Get recently completed tasks
        completed = AnalysisTask.query.filter_by(status=AnalysisStatus.COMPLETED).order_by(AnalysisTask.completed_at.desc()).limit(5).all()
        
        print(f"\nRecently completed tasks: {len(completed)}\n")
        
        for task in completed:
            print(f"Task: {task.task_id}")
            print(f"  Completed: {task.completed_at}")
            print(f"  Model: {task.target_model}, App: {task.target_app_number}")
            
            # Check metadata for result file path
            meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
            result_file = meta.get('result_file_path')
            
            if result_file:
                print(f"  ✅ Result file: {result_file}")
                if Path(result_file).exists():
                    print(f"     File exists: YES ({Path(result_file).stat().st_size} bytes)")
                else:
                    print(f"     File exists: NO")
            else:
                print(f"  ⚠️  No result file path in metadata")
                
                # Check if file exists in expected location
                results_dir = Path("results") / task.target_model / f"app{task.target_app_number}"
                if results_dir.exists():
                    task_dirs = list(results_dir.glob(f"task_{task.task_id}*"))
                    if task_dirs:
                        print(f"     But found directory: {task_dirs[0]}")
                        json_files = list(task_dirs[0].glob("*.json"))
                        print(f"     JSON files: {len(json_files)}")
            
            print()

if __name__ == "__main__":
    main()
