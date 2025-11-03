"""Debug SQLAlchemy enum query."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.models import AnalysisTask
from app.constants import AnalysisStatus
from app.factory import create_app
import logging

# Enable SQL logging
logging.basicConfig()
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

app = create_app()

with app.app_context():
    print("\n=== Test 1: Filter by enum value ===")
    query1 = AnalysisTask.query.filter_by(status=AnalysisStatus.PENDING)
    print(f"Query: {query1}")
    print(f"Enum value: {AnalysisStatus.PENDING}")
    print(f"Enum value type: {type(AnalysisStatus.PENDING)}")
    print(f"Enum str: {str(AnalysisStatus.PENDING)}")
    print(f"Enum .value: {AnalysisStatus.PENDING.value}")
    count1 = query1.count()
    print(f"Results: {count1}")
    
    print("\n=== Test 2: Filter by string value ===")
    query2 = AnalysisTask.query.filter(AnalysisTask.status == 'pending')
    print(f"Query: {query2}")
    count2 = query2.count()
    print(f"Results: {count2}")
    
    print("\n=== Test 3: Get one task and check its status ===")
    task = AnalysisTask.query.order_by(AnalysisTask.created_at.desc()).first()
    if task:
        print(f"Task: {task.task_id}")
        print(f"Status attribute: {task.status}")
        print(f"Status type: {type(task.status)}")
        print(f"Status == AnalysisStatus.PENDING: {task.status == AnalysisStatus.PENDING}")
        print(f"Status == 'pending': {task.status == 'pending'}")
