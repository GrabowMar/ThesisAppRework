import sys
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask
app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id='task_68a4102d7c93').first()
    if task:
        print(f"Main: {task.status.value}, is_main_task={task.is_main_task}")
        meta = task.get_metadata() if hasattr(task, 'get_metadata') else {}
        custom = meta.get('custom_options', {})
        print(f"  unified_analysis: {custom.get('unified_analysis')}")
    subtasks = AnalysisTask.query.filter_by(parent_task_id='task_68a4102d7c93').all()
    for st in subtasks:
        meta = st.get_metadata() if hasattr(st, 'get_metadata') else {}
        custom = meta.get('custom_options', {})
        tools = custom.get('tool_names', [])
        print(f"  {st.service_name}: {st.status.value}, tools={tools}")
