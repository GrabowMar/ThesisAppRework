import json
import sys

task_id = sys.argv[1] if len(sys.argv) > 1 else 'task_33be9fd0826d'

# Read result file
result_file = f'results/anthropic_claude-4.5-sonnet-20250929/app7/{task_id}/anthropic_claude-4.5-sonnet-20250929_app7_{task_id}_20260121_212744.json'

with open(result_file) as f:
    data = json.load(f)

print(f"Task: {task_id}")
print(f"Metadata total_findings: {data.get('metadata', {}).get('total_findings', 0)}")
print()

services = data.get('services', {})
for service_name, service_data in services.items():
    print(f"\n{service_name}:")
    print(f"  findings count: {len(service_data.get('findings', []))}")
    print(f"  issue_count: {service_data.get('issue_count')}")
    print(f"  total_issues: {service_data.get('total_issues')}")
    
    if 'tools' in service_data:
        print(f"  Tools:")
        for tool_name, tool_data in service_data['tools'].items():
            print(f"    {tool_name}:")
            print(f"      issue_count: {tool_data.get('issue_count')}")
            print(f"      findings: {len(tool_data.get('findings', []))}")
            
            # Check SARIF files
            if 'sarif_file' in tool_data:
                print(f"      sarif_file: {tool_data['sarif_file']}")

# Check database
sys.path.insert(0, 'src')
from app.factory import create_app
from app.models import AnalysisTask

app = create_app()
with app.app_context():
    task = AnalysisTask.query.filter_by(task_id=task_id).first()
    if task:
        print(f"\n\nDatabase:")
        print(f"  task_id: {task.task_id}")
        print(f"  status: {task.status}")
        print(f"  issues_found: {task.issues_found}")
        print(f"  severity_breakdown: {task.severity_breakdown}")
