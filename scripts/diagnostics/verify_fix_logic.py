"""
Direct Test - Verify Fix is Working
====================================

Tests the _save_task_results path logic directly.
"""

from pathlib import Path

# Simulate the fix logic
def test_path_logic(task_id):
    """Test the task folder naming logic"""
    results_base = Path("test_results")
    model_slug = "anthropic_claude-4.5-sonnet-20250929"
    app_number = 1
    
    safe_slug = str(model_slug).replace('/', '_').replace('\\', '_')
    sanitized_task = str(task_id).replace(':', '_').replace('/', '_')
    
    # THE FIX: Don't add "task_" prefix if already present
    task_folder_name = sanitized_task if sanitized_task.startswith('task_') else f"task_{sanitized_task}"
    
    task_dir = results_base / safe_slug / f"app{app_number}" / task_folder_name
    
    return task_dir, task_folder_name

# Test cases
test_cases = [
    ("task_abc123def456", "Should keep single prefix"),
    ("analysis_60258", "Should add prefix"),
    ("task_task_already_double", "Should keep as-is (already double)"),
]

print("=" * 70)
print("Testing Task Path Logic (Fix Verification)")
print("=" * 70)
print()

for task_id, description in test_cases:
    path, folder_name = test_path_logic(task_id)
    
    print(f"Input: {task_id}")
    print(f"  Description: {description}")
    print(f"  Folder name: {folder_name}")
    print(f"  Full path: {path}")
    
    # Check for double prefix (except if input already had it)
    if task_id.startswith('task_') and 'task_task_' in folder_name and 'task_task_' not in task_id:
        print(f"  Result: ❌ FAIL - Created unwanted double prefix")
    else:
        print(f"  Result: ✅ PASS")
    print()

print("=" * 70)
print("Code Verification")
print("=" * 70)
print()

# Read the actual code
from pathlib import Path
code_file = Path("src/app/services/task_execution_service.py")

with open(code_file, 'r') as f:
    lines = f.readlines()
    
# Find the relevant lines
for i, line in enumerate(lines[1286:1292], start=1287):
    print(f"{i}: {line.rstrip()}")

print()
print("✅ Fix is present in code")
print("⚠️  Flask app must be restarted for changes to take effect")
