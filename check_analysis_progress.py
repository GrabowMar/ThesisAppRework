"""Check what the pipeline analysis stage recorded."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import PipelineExecution
import json

app = create_app()

with app.app_context():
    # Get latest pipeline
    pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
    
    if not pipeline:
        print("No pipeline found!")
        sys.exit(1)
    
    print(f"Pipeline: {pipeline.pipeline_id}")
    print(f"Status: {pipeline.status}")
    print(f"Current Stage: {pipeline.current_stage}")
    print(f"Current Job Index: {pipeline.current_job_index}")
    print()
    
    # Check analysis progress
    analysis_progress = pipeline.progress.get('analysis', {})
    
    print("Analysis Progress:")
    print(f"  Total: {analysis_progress.get('total', 0)}")
    print(f"  Completed: {analysis_progress.get('completed', 0)}")
    print(f"  Failed: {analysis_progress.get('failed', 0)}")
    print()
    
    # Check main task IDs
    main_task_ids = analysis_progress.get('main_task_ids', [])
    print(f"Main Task IDs ({len(main_task_ids)}):")
    for task_id in main_task_ids:
        print(f"  - {task_id}")
    print()
    
    # Check submitted apps
    submitted_apps = analysis_progress.get('submitted_apps', [])
    print(f"Submitted Apps ({len(submitted_apps)}):")
    for app_key in submitted_apps:
        print(f"  - {app_key}")
    print()
    
    # Check task_ids (legacy)
    task_ids = analysis_progress.get('task_ids', [])
    print(f"Task IDs (legacy) ({len(task_ids)}):")
    for task_id in task_ids:
        if not task_id.startswith('task_'):
            print(f"  - {task_id}")  # Only show error/skipped markers
    print()
    
    print(f"Job index at end of pipeline: {pipeline.current_job_index}")
    print(f"Generation results count: {len(pipeline.progress.get('generation', {}).get('results', []))}")
