"""Monitor comprehensive test task execution."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask

def main():
    app = create_app()
    with app.app_context():
        our_tasks = [
            'task_a0f9698aeee2', 'task_04dc0a4792d7', 'task_426bcba6fa08', 
            'task_420e917ab03d', 'task_050c2d2813d0', 'task_c6d2526628a3', 
            'task_cb4eae4fb1bf', 'task_9e31aff0a44a', 'task_0a66abbd65f6', 
            'task_e39fd2ed305e'
        ]
        
        tasks = [(tid, AnalysisTask.query.filter_by(task_id=tid).first()) 
                 for tid in our_tasks]
        
        print("\n" + "="*80)
        print("Comprehensive Test Tasks Status")
        print("="*80 + "\n")
        
        by_status = {}
        for tid, task in tasks:
            if task:
                by_status.setdefault(task.status, []).append((tid, task))
        
        for status in ['completed', 'running', 'pending', 'failed']:
            if status in by_status:
                print(f"\n{status.upper()} ({len(by_status[status])} tasks):")
                for tid, task in by_status[status]:
                    # Get tools from metadata
                    tools = []
                    try:
                        meta = task.get_metadata() or {}
                        custom = meta.get('custom_options', {})
                        tools = custom.get('selected_tool_names', [])
                        desc = custom.get('description', 'N/A')
                    except:
                        desc = 'N/A'
                    
                    print(f"  {tid}")
                    print(f"    Type: {desc}")
                    print(f"    Tools: {', '.join(tools) if tools else 'N/A'}")
        
        print(f"\n{'='*80}")
        completed = len(by_status.get('completed', []))
        print(f"Progress: {completed}/{len(our_tasks)} tasks completed")
        print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
