import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.constants import AnalysisStatus

app = create_app()
with app.app_context():
    print("Checking recent tasks...\n")
    
    # Check for the specific task from the screenshot
    task = AnalysisTask.query.filter_by(task_id='task_aac9d905af66').first()
    if task:
        print(f"✅ Found task_aac9d905af66:")
        print(f"   Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        print(f"   Model: {task.target_model}")
        print(f"   App: {task.target_app_number}")
        print(f"   Is Main Task: {task.is_main_task}")
        print(f"   Created: {task.created_at}")
        print(f"   Completed: {task.completed_at}")
    else:
        print("❌ Task task_aac9d905af66 not found")
    
    # Check for any main tasks
    print("\n\nChecking all main tasks...")
    main_tasks = AnalysisTask.query.filter_by(is_main_task=True).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    print(f"Found {len(main_tasks)} main tasks (showing last 10):\n")
    for t in main_tasks:
        status_val = t.status.value if hasattr(t.status, 'value') else t.status
        print(f"  {t.task_id}: {status_val} | {t.target_model} app{t.target_app_number} | {t.created_at}")
    
    # Check for any tasks with parent_task_id = None
    print("\n\nChecking tasks with parent_task_id = None...")
    parent_none_tasks = AnalysisTask.query.filter(
        AnalysisTask.parent_task_id == None
    ).order_by(AnalysisTask.created_at.desc()).limit(10).all()
    print(f"Found {len(parent_none_tasks)} tasks (showing last 10):\n")
    for t in parent_none_tasks:
        status_val = t.status.value if hasattr(t.status, 'value') else t.status
        print(f"  {t.task_id}: {status_val} | is_main={t.is_main_task} | {t.target_model} app{t.target_app_number}")
