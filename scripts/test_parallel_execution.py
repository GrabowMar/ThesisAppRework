"""Test parallel task execution"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.models import AnalysisTask
from app.services.task_service import AnalysisTaskService
from app.extensions import db
import time

app = create_app()
app.config['TESTING'] = False  # Real execution

with app.app_context():
    print("\n=== Creating Test Security Analysis Task ===\n")
    
    # Create a unified analysis task (security profile)
    from app.engines.unified_registry import get_unified_tool_registry
    registry = get_unified_tool_registry()
    
    # Get all tools grouped by service
    static_tools = [t['id'] for t in registry.list_tools_detailed() if t['service'] == 'static-analyzer']
    dynamic_tools = [t['id'] for t in registry.list_tools_detailed() if t['service'] == 'dynamic-analyzer']
    perf_tools = [t['id'] for t in registry.list_tools_detailed() if t['service'] == 'performance-tester']
    ai_tools = [t['id'] for t in registry.list_tools_detailed() if t['service'] == 'ai-analyzer']
    
    tools_by_service = {
        'static-analyzer': static_tools,
        'dynamic-analyzer': dynamic_tools,
        'performance-tester': perf_tools,
        'ai-analyzer': ai_tools
    }
    
    print(f"Tools by service:")
    for svc, tools in tools_by_service.items():
        print(f"  {svc}: {len(tools)} tools")
    
    # Create main task with subtasks
    task = AnalysisTaskService.create_main_task_with_subtasks(
        model_slug='openai_codex-mini',
        app_number=1,
        analysis_type='security',
        tools_by_service=tools_by_service,
        task_name='TEST: Parallel Execution Verification'
    )
    
    print(f"\nCreated task: {task.task_id}")
    print(f"  Main task: {task.is_main_task}")
    print(f"  Total steps: {task.total_steps}")
    print(f"  Status: {task.status.value if hasattr(task.status, 'value') else task.status}")
    
    # Check subtasks
    subtasks = AnalysisTask.query.filter_by(parent_task_id=task.task_id).all()
    print(f"\nSubtasks created: {len(subtasks)}")
    for st in subtasks:
        print(f"  - {st.service_name}: {st.status.value if hasattr(st.status, 'value') else st.status}")
    
    print("\n✅ Task created successfully!")
    print(f"   Task ID: {task.task_id}")
    print(f"\nMonitor execution:")
    print(f"  1. Check task status in UI: http://localhost:5000/analysis/list")
    print(f"  2. Watch logs: Look for 'Celery chord created' message")
    print(f"  3. Verify parallel execution: All 4 containers should show activity simultaneously")
    print(f"\nExpected behavior:")
    print(f"  - All 4 subtasks should transition to RUNNING at the same time")
    print(f"  - Container logs should show simultaneous execution")
    print(f"  - Total time should be ~5 min (not 14 min)")
