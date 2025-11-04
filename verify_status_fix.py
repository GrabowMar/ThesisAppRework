"""Quick test to verify status enum handling after migration."""
import sys
sys.path.insert(0, 'src')

from app.factory import create_app
from app.models.analysis_models import AnalysisTask
from app.constants import AnalysisStatus

app = create_app()
with app.app_context():
    print("Testing status enum handling after migration...\n")
    
    # Test querying all tasks (this was failing before)
    try:
        all_tasks = AnalysisTask.query.all()
        print(f"✅ Successfully queried {len(all_tasks)} tasks")
    except Exception as e:
        print(f"❌ Failed to query all tasks: {e}")
        sys.exit(1)
    
    # Test filtering by each status
    for status in AnalysisStatus:
        try:
            count = AnalysisTask.query.filter_by(status=status).count()
            print(f"✅ {status.value}: {count} tasks")
        except Exception as e:
            print(f"❌ Failed to filter by {status.value}: {e}")
            sys.exit(1)
    
    # Test ordering
    try:
        recent = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).limit(5).all()
        print(f"\n✅ Successfully queried {len(recent)} most recent tasks")
        for task in recent:
            print(f"   - {task.task_id}: {task.status.value}")
    except Exception as e:
        print(f"❌ Failed to query recent tasks: {e}")
        sys.exit(1)
    
    print("\n✅ All enum tests passed!")
