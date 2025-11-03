import json
from pathlib import Path

result_file = Path("results/anthropic_claude-4.5-sonnet-20250929/app1/task_sarif_extraction_test_v2/anthropic_claude-4.5-sonnet-20250929_app1_task_sarif_extraction_test_v2_20251103_181056.json")

with open(result_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

semgrep = data['results']['services']['static']['analysis']['results']['python']['semgrep']

print("Semgrep keys:")
for key, value in semgrep.items():
    if isinstance(value, (list, dict)):
        size = len(json.dumps(value))
        print(f"  {key}: {type(value).__name__} ({size:,} bytes = {size/1024:.2f} KB)")
    else:
        print(f"  {key}: {value}")
        
# Check issues structure
if 'issues' in semgrep and isinstance(semgrep['issues'], list):
    issues = semgrep['issues']
    print(f"\nIssues: {len(issues)} items")
    if len(issues) > 0:
        first_issue = issues[0]
        print("First issue keys:")
        for key, value in first_issue.items():
            if isinstance(value, (list, dict)):
                size = len(json.dumps(value))
                print(f"  {key}: {type(value).__name__} ({size:,} bytes = {size/1024:.2f} KB)")
            else:
                print(f"  {key}: {str(value)[:100]}...")
