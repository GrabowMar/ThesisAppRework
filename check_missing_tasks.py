"""Check which apps are missing analysis tasks."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models import AnalysisTask, PipelineExecution, GeneratedApplication
from app.extensions import db

app = create_app()
with app.app_context():
    # Get latest pipeline
    pipeline = PipelineExecution.query.order_by(PipelineExecution.created_at.desc()).first()
    
    if not pipeline:
        print("No pipeline found!")
        sys.exit(1)
    
    print(f"=== Pipeline: {pipeline.pipeline_id} ===")
    print(f"Status: {pipeline.status.value if hasattr(pipeline.status, 'value') else pipeline.status}")
    print()
    
    # Get model slug
    model_slug = 'qwen_qwen3-coder-30b-a3b-instruct'
    
    # Get all generated apps
    apps = GeneratedApplication.query.filter_by(model_slug=model_slug).order_by(GeneratedApplication.app_number).all()
    print(f"Generated Apps: {len(apps)}")
    app_numbers = [app.app_number for app in apps]
    print(f"App numbers: {app_numbers}")
    print()
    
    # Get all analysis tasks
    tasks = AnalysisTask.query.filter_by(
        target_model=model_slug,
        is_main_task=True
    ).order_by(AnalysisTask.target_app_number).all()
    
    print(f"Analysis Tasks (main): {len(tasks)}")
    task_app_numbers = [task.target_app_number for task in tasks]
    print(f"Task app numbers: {task_app_numbers}")
    print()
    
    # Find missing
    missing = set(app_numbers) - set(task_app_numbers)
    if missing:
        print(f"MISSING TASKS FOR APPS: {sorted(missing)}")
        print()
        print("These apps need analysis tasks created.")
    else:
        print("All apps have analysis tasks!")
    
    # Show task details
    print()
    print("Existing Tasks:")
    for task in tasks:
        status = task.status.value if hasattr(task.status, 'value') else task.status
        print(f"  App {task.target_app_number}: {status} (batch: {task.batch_id})")
