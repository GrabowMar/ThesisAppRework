"""Quick test - create analysis and check path format"""
import requests
import time
from pathlib import Path

BASE_URL = 'http://localhost:5000'
TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'

# Create analysis
print("Creating analysis...")
resp = requests.post(
    f'{BASE_URL}/analysis/create',
    data={
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': '1',
        'analysis_mode': 'custom',
        'selected_tools[]': ['bandit', 'safety'],
        'priority': 'high'
    },
    headers={'Authorization': f'Bearer {TOKEN}'},
    allow_redirects=False
)

if resp.status_code == 302:
    print(f"✅ Created! Waiting 30 seconds...")
    time.sleep(30)
    
    # Check results
    results = Path('results/anthropic_claude-4.5-sonnet-20250929/app1')
    if results.exists():
        dirs = sorted(results.glob('task_*'), key=lambda p: p.stat().st_mtime, reverse=True)
        if dirs:
            latest = dirs[0]
            print(f"\nLatest result: {latest.name}")
            
            if 'task_task_' in latest.name:
                print("❌ BUG STILL PRESENT: Double prefix")
            else:
                print("✅ BUG FIXED: Single prefix")
        else:
            print("No task directories found")
    else:
        print("Results directory doesn't exist")
else:
    print(f"❌ Failed: {resp.status_code}")
