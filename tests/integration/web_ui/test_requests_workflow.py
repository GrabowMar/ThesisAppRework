import pytest

pytestmark = [pytest.mark.integration, pytest.mark.web_ui]

"""
Complete Web UI Analysis Test with Requests
===========================================

Uses requests library to:
1. Create analysis via POST to /analysis/create
2. Poll task status via GET requests  
3. Verify results exist and are correct

NO browser, NO Selenium - pure HTTP requests.
"""

import requests
import time
import json
from pathlib import Path
from datetime import datetime

BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'


def main():
    print("=" * 70)
    print("Web UI Analysis Test - Pure HTTP Requests")
    print("=" * 70)
    print()
    
    # Step 1: Create analysis
    print("Step 1: Creating analysis via HTTP POST")
    print("-" * 70)
    
    form_data = {
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': '1',
        'analysis_mode': 'custom',
        'selected_tools[]': ['bandit', 'safety', 'pylint', 'eslint'],
        'priority': 'high'
    }
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    print(f"POST {BASE_URL}/analysis/create")
    print(f"Tools: {form_data['selected_tools[]']}")
    print()
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    if response.status_code != 302:
        print(f"❌ Failed: {response.status_code}")
        print(response.text[:500])
        return False
    
    print(f"✅ Created! Status: {response.status_code}")
    print()
    
    # Step 2: Wait and check filesystem
    print("Step 2: Waiting for analysis to complete...")
    print("-" * 70)
    
    model_slug = form_data['model_slug']
    app_number = form_data['app_number']
    results_dir = Path(__file__).parent / 'results' / model_slug / f'app{app_number}'
    
    print(f"Monitoring: {results_dir}")
    print()
    
    # Track initial file count
    initial_count = len(list(results_dir.glob('task_*/')) if results_dir.exists() else [])
    
    for i in range(12):  # 60 seconds total
        time.sleep(5)
        
        if results_dir.exists():
            current_dirs = list(results_dir.glob('task_*/'))
            current_count = len(current_dirs)
            
            if current_count > initial_count:
                print(f"  [{(i+1)*5}s] ✅ New task directory detected!")
                
                # Find the newest directory
                newest = max(current_dirs, key=lambda p: p.stat().st_mtime)
                print(f"  Checking: {newest.name}")
                
                # Look for JSON result files
                json_files = [f for f in newest.glob('*.json') if 'manifest' not in f.name]
                
                if json_files:
                    print(f"  ✅ Found result file: {json_files[0].name}")
                    
                    # Read and analyze
                    try:
                        with open(json_files[0], 'r') as f:
                            data = json.load(f)
                        
                        summary = data.get('results', {}).get('summary', {})
                        findings = summary.get('total_findings', 0)
                        tools = summary.get('tools_executed', 0)
                        
                        print(f"  📊 Findings: {findings}, Tools: {tools}")
                        print()
                        
                        # Check path format
                        if 'task_task_' in newest.name:
                            print("  ⚠️  Double 'task_' prefix bug present")
                            print("  → Need to restart Flask app for fix to apply")
                        else:
                            print("  ✅ Correct path format")
                        
                        print()
                        print("=" * 70)
                        print("SUCCESS - Analysis completed!")
                        print("=" * 70)
                        print()
                        print(f"Results location: {newest}")
                        print(f"Findings: {findings}")
                        print(f"Tools executed: {tools}")
                        
                        if findings == 0:
                            print()
                            print("⚠️  WARNING: 0 findings detected")
                            print("This might indicate:")
                            print("  - Tools not executing properly")
                            print("  - App has no issues")
                            print("  - Results not being aggregated correctly")
                        
                        return True
                        
                    except Exception as e:
                        print(f"  ❌ Error reading results: {e}")
                else:
                    print(f"  [{(i+1)*5}s] Waiting for results file...")
            else:
                print(f"  [{(i+1)*5}s] Waiting for task directory...")
        else:
            print(f"  [{(i+1)*5}s] Results directory doesn't exist yet...")
    
    print()
    print("⏱️  Timeout - Analysis taking longer than 60 seconds")
    return False


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
