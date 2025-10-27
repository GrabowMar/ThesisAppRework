"""Inspect the actual result_summary structure of completed tasks."""
import sys
import json
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask

app = create_app()

with app.app_context():
    # Get the first security task for app 1
    task = AnalysisTask.query.filter_by(
        target_model='anthropic_claude-4.5-haiku-20251001',
        target_app_number=1,
        analysis_type='security',
        status='completed'
    ).order_by(AnalysisTask.created_at.desc()).first()
    
    if not task:
        print("No completed security tasks found!")
        sys.exit(1)
    
    print(f"Task: {task.task_id}")
    print(f"Status: {task.status}")
    print(f"Issues found: {task.issues_found}")
    print()
    
    # Get result_summary
    result_summary = task.get_result_summary()
    
    if not result_summary:
        print("No result_summary found!")
        sys.exit(1)
    
    print("=== Result Summary Structure ===")
    print(json.dumps(result_summary, indent=2))
    print()
    
    # Check if payload contains the actual results
    if 'payload' in result_summary:
        print("=== Payload Structure ===")
        payload = result_summary['payload']
        print(f"Payload keys: {list(payload.keys()) if isinstance(payload, dict) else 'not a dict'}")
        
        if isinstance(payload, dict):
            # Check for common result fields
            for key in ['summary', 'results', 'findings', 'tools_executed', 'services_executed']:
                if key in payload:
                    print(f"  - Has {key}: {type(payload[key])}")
                    if key == 'summary' and isinstance(payload[key], dict):
                        print(f"      Summary keys: {list(payload[key].keys())}")
