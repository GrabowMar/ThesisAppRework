import sys
sys.path.insert(0, "src")
from app.factory import create_app
from app.models import AnalysisTask

app = create_app("development")
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id="task_ae1c96267419").first()
    if task:
        print(f"Task: {task.task_id}")
        print(f"Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
        print(f"Progress: {task.progress_percentage}%")
        print(f"Error: {task.error_message}")
        
        # Check metadata
        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
        custom_opts = meta.get('custom_options', {})
        print(f"\nMetadata:")
        print(f"  Tools: {custom_opts.get('tools') or custom_opts.get('selected_tool_names')}")
        print(f"  Unified: {custom_opts.get('unified_analysis')}")
    else:
        print("Task not found")
