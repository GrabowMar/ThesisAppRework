"""Check security tasks for anthropic_claude-4.5-haiku-20251001 app 1"""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()

with app.app_context():
    # Get security tasks for app 1
    tasks = AnalysisTask.query.filter_by(
        target_model='anthropic_claude-4.5-haiku-20251001',
        target_app_number=1,
        analysis_type='security'
    ).order_by(AnalysisTask.created_at.desc()).limit(2).all()
    
    print(f"Found {len(tasks)} security tasks for app 1\n")
    
    for task in tasks:
        print(f"=== Task {task.task_id} ===")
        print(f"  Status: {task.status}")
        print(f"  Issues found: {task.issues_found}")
        print(f"  Created at: {task.created_at}")
        print(f"  Completed at: {task.completed_at}")
        print(f"  Target app number: {task.target_app_number}")
        print(f"  Analysis type: {task.analysis_type}")
        
        # Check task_metadata field
        if task.task_metadata:
            print(f"  Has task_metadata (length: {len(task.task_metadata)})")
        
        # Check result_summary field
        if task.result_summary:
            print(f"  Has result_summary (length: {len(task.result_summary)})")
            
            # Try to parse it
            try:
                import json
                summary_data = json.loads(task.result_summary)
                print(f"  Result summary keys: {list(summary_data.keys())}")
                if 'summary' in summary_data:
                    print(f"    - Summary: {summary_data['summary']}")
            except Exception as e:
                print(f"  Could not parse result_summary: {e}")
        
        # Check if get_result_summary method works
        result_summary = task.get_result_summary()
        print(f"  get_result_summary() returns data: {bool(result_summary)}")
        
        print()
