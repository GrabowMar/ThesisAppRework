"""Check task metadata for tool storage."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask

def main():
    app = create_app()
    with app.app_context():
        task_ids = ['task_a0f9698aeee2', 'task_050c2d2813d0', 'task_0a66abbd65f6']
        
        for tid in task_ids:
            task = AnalysisTask.query.filter_by(task_id=tid).first()
            if not task:
                continue
            
            print(f"\nTask: {tid}")
            print(f"  Status: {task.status}")
            
            try:
                meta = task.get_metadata() or {}
                print(f"  Metadata keys: {list(meta.keys())}")
                
                custom = meta.get('custom_options', {})
                print(f"  custom_options keys: {list(custom.keys())}")
                print(f"  custom_options.tools: {custom.get('tools')}")
                print(f"  custom_options.selected_tool_names: {custom.get('selected_tool_names')}")
            except Exception as e:
                print(f"  Error reading metadata: {e}")

if __name__ == "__main__":
    main()
