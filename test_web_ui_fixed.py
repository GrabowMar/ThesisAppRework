"""
Test Web UI Analysis with Fixed Result Paths
=============================================

Creates a new analysis via web UI and verifies results are saved correctly.
"""

import requests
import time
import json
from pathlib import Path

BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'

print("=" * 70)
print("Testing Web UI Analysis with Fixed Result Paths")
print("=" * 70)
print()

# Create analysis via form endpoint
form_data = {
    'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
    'app_number': '1',
    'analysis_mode': 'custom',
    'selected_tools[]': ['bandit', 'safety', 'pylint'],
    'priority': 'high'
}

headers = {
    'Authorization': f'Bearer {BEARER_TOKEN}'
}

print("Creating analysis via web UI form...")
print(f"Model: {form_data['model_slug']}")
print(f"App: {form_data['app_number']}")
print(f"Tools: {form_data['selected_tools[]']}")
print()

response = requests.post(
    f'{BASE_URL}/analysis/create',
    data=form_data,
    headers=headers,
    allow_redirects=False
)

if response.status_code != 302:
    print(f"❌ Failed to create analysis: {response.status_code}")
    print(response.text[:500])
    exit(1)

print(f"✅ Analysis created! Redirected to: {response.headers.get('Location')}")
print()

# Wait for task execution
print("Waiting 45 seconds for analysis to complete...")
for i in range(9):
    time.sleep(5)
    print(f"  ... {(i+1)*5}s elapsed")

print()

# Check for results
model_slug = form_data['model_slug']
app_number = form_data['app_number']
results_dir = Path(__file__).parent / 'results' / model_slug / f'app{app_number}'

print(f"Checking results in: {results_dir}")
print()

if not results_dir.exists():
    print(f"❌ Results directory doesn't exist: {results_dir}")
    exit(1)

# List all task directories
task_dirs = sorted(results_dir.glob('task_*'), key=lambda p: p.stat().st_mtime, reverse=True)

if not task_dirs:
    print(f"❌ No task directories found in {results_dir}")
    exit(1)

print(f"Found {len(task_dirs)} task directories:")
for task_dir in task_dirs[:5]:  # Show latest 5
    print(f"  - {task_dir.name}")
    
    # Check for JSON files
    json_files = list(task_dir.glob('*.json'))
    if json_files:
        print(f"    Files: {len(json_files)} JSON files")
        
        # Read the main result file
        for json_file in json_files:
            if 'manifest' not in json_file.name:
                try:
                    with open(json_file, 'r') as f:
                        data = json.load(f)
                    
                    summary = data.get('results', {}).get('summary', {})
                    print(f"    ✅ Results: {summary.get('total_findings', 0)} findings, {summary.get('tools_executed', 0)} tools")
                    
                    # Check for double "task_" prefix bug
                    if 'task_task_' in task_dir.name:
                        print(f"    ⚠️  WARNING: Double 'task_' prefix detected!")
                    else:
                        print(f"    ✅ Correct path format (no double prefix)")
                    
                except Exception as e:
                    print(f"    ❌ Error reading {json_file.name}: {e}")
    else:
        print(f"    ❌ No JSON files found")
    
    print()

print("=" * 70)
print("Test Complete")
print("=" * 70)
print()

# Show latest result path
if task_dirs:
    latest = task_dirs[0]
    print(f"Latest result: {latest}")
    
    if 'task_task_' in latest.name:
        print("❌ BUG STILL PRESENT: Double 'task_' prefix")
    else:
        print("✅ BUG FIXED: Correct path format")
