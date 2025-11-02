"""Check new tasks with streamlined tool selection."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from app.factory import create_app
from app.models import AnalysisTask

def main():
    app = create_app()
    with app.app_context():
        new_tasks = [
            'task_90bed98bb9a6',  # Dynamic: zap, nmap
            'task_0015db83086e',  # Dynamic: zap, nmap, nikto
            'task_b5e7b63956ae',  # Performance: ab, locust
            'task_21ce78b24f02',  # Performance: ab, locust, wrk
            'task_e734a4b3f5ae',  # AI: openrouter
            'task_48b418ce8040',  # Multi: bandit, pylint, eslint, zap, ab, openrouter
        ]
        
        print("\n" + "="*80)
        print("NEW TASKS - Streamlined Tool Selection Verification")
        print("="*80 + "\n")
        
        for tid in new_tasks:
            task = AnalysisTask.query.filter_by(task_id=tid).first()
            if not task:
                print(f"{tid}: NOT FOUND\n")
                continue
            
            print(f"{tid}:")
            print(f"  Status: {task.status}")
            
            # Get requested tools from metadata
            meta = task.get_metadata() or {}
            custom_opts = meta.get('custom_options', {})
            requested_tools = custom_opts.get('tools', [])
            print(f"  Requested Tools: {requested_tools}")
            
            # If completed, check what actually executed
            if task.status == 'completed':
                result_files = list(Path("results").rglob(f"*{tid}*.json"))
                if result_files:
                    with open(result_files[0]) as f:
                        result_data = json.load(f)
                    
                    executed_tools = list(result_data.get('results', {}).get('tools', {}).keys())
                    print(f"  Executed Tools: {executed_tools}")
                    
                    # Check if they match
                    if set(requested_tools) == set(executed_tools):
                        print(f"  ✅ MATCH - Tools executed correctly!")
                    else:
                        print(f"  ❌ MISMATCH - Expected {requested_tools}, got {executed_tools}")
                else:
                    print(f"  No result file yet")
            
            print()

if __name__ == "__main__":
    main()
