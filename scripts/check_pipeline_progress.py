"""Check pipeline progress for pipeline_c6b261e64ec8"""
import sys
import json

sys.path.insert(0, 'src')
from app.factory import create_app
from app.models.pipeline import PipelineExecution

app = create_app()
with app.app_context():
    p = PipelineExecution.query.filter_by(pipeline_id='pipeline_c6b261e64ec8').first()
    if not p:
        print("Pipeline not found!")
        sys.exit(1)
    
    progress = json.loads(p.progress_json) if p.progress_json else {}
    gen = progress.get('generation', {})
    
    print('=== GENERATION RESULTS ===')
    for app_info in gen.get('apps', []):
        print(f"App: {app_info.get('model_slug')}/app{app_info.get('app_number')} - Status: {app_info.get('status')}")
    print(f"Total: {gen.get('completed', 0)} completed, {gen.get('failed', 0)} failed")
    
    # Also check analysis stage
    an = progress.get('analysis', {})
    print('\n=== ANALYSIS STAGE ===')
    print(f"Status: {an.get('status')}")
    print(f"Total: {an.get('total', 0)}")
    print(f"Completed: {an.get('completed', 0)}")
    print(f"Failed: {an.get('failed', 0)}")
    
    # Check if there are any analysis task IDs
    print('\n=== ANALYSIS TASKS ===')
    tasks = an.get('tasks', [])
    for task in tasks:
        print(f"Task: {task}")
    
    # Print raw progress JSON for debugging
    print('\n=== RAW PROGRESS JSON ===')
    print(json.dumps(progress, indent=2, default=str))
