"""
FINAL FIX VERIFICATION
======================

1. Confirms fix is in code
2. Creates new analysis
3. Waits for completion
4. Verifies result path has NO double prefix
"""

import requests
import time
from pathlib import Path
import sys

BASE_URL = 'http://localhost:5000'
TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'

print("=" * 70)
print("FINAL FIX VERIFICATION - Web UI Double Prefix Bug")
print("=" * 70)
print()

# Step 1: Verify fix is in code
print("Step 1: Verify fix is in code")
print("-" * 70)
with open('src/app/services/task_execution_service.py', 'r') as f:
    content = f.read()
    if 'task_folder_name = sanitized_task if sanitized_task.startswith' in content:
        print("✅ Fix present in source code")
    else:
        print("❌ Fix NOT found in source code!")
        sys.exit(1)
print()

# Step 2: Check Flask is running
print("Step 2: Check Flask is running")
print("-" * 70)
try:
    resp = requests.get(f'{BASE_URL}/health', timeout=2)
    if resp.status_code == 200:
        print(f"✅ Flask running on {BASE_URL}")
    else:
        print(f"⚠️  Flask responded with: {resp.status_code}")
except Exception as e:
    print(f"❌ Flask not accessible: {e}")
    print("Please start Flask: python src/main.py")
    sys.exit(1)
print()

# Step 3: Get current task count
print("Step 3: Check existing results")
print("-" * 70)
results_dir = Path('results/anthropic_claude-4.5-sonnet-20250929/app1')
if results_dir.exists():
    existing_tasks = list(results_dir.glob('task_*'))
    print(f"Existing task directories: {len(existing_tasks)}")
    
    # Show status of existing
    double_prefix_count = sum(1 for t in existing_tasks if 'task_task_' in t.name)
    single_prefix_count = len(existing_tasks) - double_prefix_count
    
    print(f"  - Single prefix (correct): {single_prefix_count}")
    print(f"  - Double prefix (buggy): {double_prefix_count}")
else:
    existing_tasks = []
    print("No existing results directory")
print()

# Step 4: Create new analysis
print("Step 4: Create NEW analysis")
print("-" * 70)
resp = requests.post(
    f'{BASE_URL}/analysis/create',
    data={
        'model_slug': 'anthropic_claude-4.5-haiku-20251001',
        'app_number': '3',
        'analysis_mode': 'custom',
        'selected_tools[]': ['bandit', 'safety'],
        'priority': 'high'
    },
    headers={'Authorization': f'Bearer {TOKEN}'},
    allow_redirects=False
)

if resp.status_code != 302:
    print(f"❌ Failed to create: {resp.status_code}")
    sys.exit(1)

print(f"✅ Analysis created (status: {resp.status_code})")
print(f"Model: anthropic_claude-4.5-haiku-20251001, App: 3")
print()

# Step 5: Wait and check
print("Step 5: Wait for completion (60 seconds)")
print("-" * 70)
test_results_dir = Path('results/anthropic_claude-4.5-haiku-20251001/app3')

initial_count = len(list(test_results_dir.glob('task_*'))) if test_results_dir.exists() else 0

for i in range(12):
    time.sleep(5)
    
    if test_results_dir.exists():
        current_tasks = list(test_results_dir.glob('task_*'))
        current_count = len(current_tasks)
        
        if current_count > initial_count:
            newest = max(current_tasks, key=lambda p: p.stat().st_mtime)
            print(f"  [{(i+1)*5}s] ✅ NEW RESULT FOUND!")
            print()
            print("=" * 70)
            print("RESULT")
            print("=" * 70)
            print(f"Directory: {newest.name}")
            print()
            
            if 'task_task_' in newest.name:
                print("❌❌❌ FAIL: Double prefix STILL PRESENT!")
                print()
                print("This means:")
                print("  1. Flask app wasn't restarted properly, OR")
                print("  2. Old code is still in memory")
                print()
                print("Solution: Manually restart Flask:")
                print("  - Stop Flask (Ctrl+C)")
                print("  - Run: python src/main.py")
            else:
                print("✅✅✅ SUCCESS: Single prefix (FIX WORKING!)")
                print()
                print("The double 'task_' prefix bug is FIXED!")
            
            sys.exit(0)
    
    print(f"  [{(i+1)*5}s] Waiting...")

print()
print("⏱️  Timeout - analysis took longer than 60 seconds")
print("Check manually:")
print(f"  ls {test_results_dir}")
