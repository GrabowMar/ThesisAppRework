import sys
sys.path.insert(0, "src")
from app.factory import create_app
from app.models import AnalysisTask
from app.constants import AnalysisStatus

app = create_app("development")
with app.app_context():
    pending = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING).all()
    running = AnalysisTask.query.filter_by(status=AnalysisStatus.RUNNING).all()
    
    print(f"\nPending tasks: {len(pending)}")
    for task in pending[:5]:
        print(f"  - {task.task_id}: {task.target_model} app{task.target_app_number}")
    
    print(f"\nRunning tasks: {len(running)}")
    for task in running[:5]:
        print(f"  - {task.task_id}: {task.target_model} app{task.target_app_number}")
        
    # Check if TaskExecutionService is registered
    try:
        from app.extensions import get_components
        components = get_components()
        if components:
            exec_service = components.get("task_execution_service")
            if exec_service:
                print(f"\n✅ TaskExecutionService is registered and running: {exec_service._running}")
            else:
                print("\n❌ TaskExecutionService not found in components")
        else:
            print("\n❌ No components available")
    except Exception as e:
        print(f"\n❌ Error checking TaskExecutionService: {e}")
