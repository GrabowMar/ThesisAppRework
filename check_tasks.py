
from app.extensions import db
from app.models import AnalysisTask
from app import create_app
import json

app = create_app()
with app.app_context():
    task = AnalysisTask.query.first()
    if task:
        print(f"Task ID: {task.task_id}")
        print(f"Status: {task.status}")
        summary = task.get_result_summary()
        print(f"Summary Keys: {list(summary.keys())}")
        if 'services' in summary:
            for s, res in summary['services'].items():
                print(f"Service: {s}, Status: {res.get('status')}, Tools: {list(res.get('tools', {}).keys())}")
        else:
             # Basic format
             for s, res in summary.items():
                 if isinstance(res, dict) and 'status' in res:
                     print(f"Service/Tool: {s}, Status: {res.get('status')}")
    else:
        print("No tasks found")
