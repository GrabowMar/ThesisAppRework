"""Check what's in all 15 openai_codex-mini tasks."""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app import create_app
from app.models.analysis_models import AnalysisTask

app = create_app()

with app.app_context():
    tasks = AnalysisTask.query.filter_by(target_model='openai_codex-mini').order_by(AnalysisTask.target_app_number, AnalysisTask.created_at).all()
    
    print(f"Total openai_codex-mini tasks: {len(tasks)}\n")
    print("=" * 80)
    
    for task in tasks:
        print(f"\nTask ID: {task.task_id}")
        print(f"  App: app{task.target_app_number}")
        print(f"  Analysis Type: {task.analysis_type.value if hasattr(task.analysis_type, 'value') else task.analysis_type}")
        print(f"  Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        
        if task.result_summary:
            try:
                summary = json.loads(task.result_summary)
                results = summary.get('results', {})
                
                # Check what tools were actually run
                tools_requested = results.get('tools_requested', [])
                tool_results = results.get('tool_results', {})
                
                print(f"  Tools Requested: {tools_requested}")
                print(f"  Tools in Results: {list(tool_results.keys())}")
                
                # Check which service executed
                raw_outputs = results.get('raw_outputs', {})
                service = raw_outputs.get('service', 'unknown')
                print(f"  Service: {service}")
                
            except Exception as e:
                print(f"  ⚠️  Error parsing result_summary: {e}")
        else:
            print("  No result_summary")
    
    print("\n" + "=" * 80)
    print("Summary by Analysis Type:")
    
    from collections import Counter
    types = Counter()
    for task in tasks:
        atype = task.analysis_type.value if hasattr(task.analysis_type, 'value') else task.analysis_type
        types[atype] += 1
    
    for atype, count in types.items():
        print(f"  {atype}: {count} tasks")
