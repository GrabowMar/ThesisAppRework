#!/usr/bin/env python3
"""Check pipeline analysis tasks status."""
import json
from src.app.factory import create_app
from src.app.models import AnalysisTask, PipelineExecution, GeneratedApplication

app = create_app()

with app.app_context():
    # Get latest pipeline
    pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
    
    if not pipeline:
        print("No pipeline found!")
        exit(1)
    
    print(f"Pipeline: {pipeline.pipeline_id}")
    print(f"Status: {pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status}")
    print(f"\nConfig:")
    
    # Check selected apps
    selected_apps = pipeline.config.get('generation', {}).get('selected_apps', [])
    print(f"Selected Apps: {selected_apps}")
    
    # Check analysis progress
    analysis_prog = pipeline.progress.get('analysis', {})
    print(f"\nAnalysis Progress:")
    print(f"  Total: {analysis_prog.get('total', 0)}")
    print(f"  Completed: {analysis_prog.get('completed', 0)}")
    print(f"  Failed: {analysis_prog.get('failed', 0)}")
    print(f"  Main Task IDs: {len(analysis_prog.get('main_task_ids', []))}")
    print(f"  Submitted Apps: {analysis_prog.get('submitted_apps', [])}")
    
    # Query actual tasks
    model_slug = pipeline.config.get('generation', {}).get('model_slugs', [None])[0]
    if model_slug:
        print(f"\nQuerying tasks for model: {model_slug}")
        
        # Count all tasks for this model
        all_tasks = AnalysisTask.query.filter_by(
            target_model=model_slug,
            is_main_task=True
        ).all()
        
        print(f"Total main tasks in DB: {len(all_tasks)}")
        
        for task in all_tasks:
            print(f"  - App {task.target_app_number}: {task.status.value if hasattr(task.status, 'value') else task.status} (batch_id: {task.batch_id})")
        
        # Check which apps are generated
        generated_apps = GeneratedApplication.query.filter_by(model_slug=model_slug).all()
        print(f"\nGenerated apps: {len(generated_apps)}")
        app_numbers = sorted([app.app_number for app in generated_apps])
        print(f"App numbers: {app_numbers}")
        
        # Find missing tasks
        tasks_app_numbers = set(task.target_app_number for task in all_tasks)
        missing = set(app_numbers) - tasks_app_numbers
        if missing:
            print(f"\nMISSING TASKS FOR APPS: {sorted(missing)}")
