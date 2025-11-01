"""
Direct HTTP Analysis Request Test
==================================

Simulates web UI analysis creation using requests library.
This bypasses form submission and directly POSTs to the analysis endpoint.
"""

import requests
import json
import time
from datetime import datetime


BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'


def test_create_analysis_comprehensive():
    """Test creating comprehensive analysis via HTTP POST"""
    
    print("=" * 70)
    print("Direct HTTP Analysis Creation Test")
    print("=" * 70)
    print()
    
    # Test 1: Create comprehensive analysis via form endpoint
    print("Test 1: Create comprehensive analysis (all tools)")
    print("-" * 70)
    
    form_data = {
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': '1',
        'analysis_mode': 'profile',
        'analysis_profile': 'comprehensive',
        'priority': 'normal'
    }
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    print(f"POST {BASE_URL}/analysis/create")
    print(f"Data: {json.dumps(form_data, indent=2)}")
    print()
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    
    if response.status_code == 302:
        print(f"✅ Success! Redirected to: {response.headers.get('Location')}")
    else:
        print(f"❌ Failed!")
        print(f"Response: {response.text[:500]}")
    
    print()
    
    # Test 2: Check task was created via API
    print("Test 2: Verify task created via API")
    print("-" * 70)
    
    time.sleep(1)  # Give it a moment
    
    response = requests.get(
        f'{BASE_URL}/api/analysis/tasks',
        headers=headers
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        tasks = response.json()
        print(f"✅ Found {len(tasks)} task(s)")
        
        if tasks:
            latest = tasks[0]
            print(f"\nLatest task:")
            print(f"  ID: {latest.get('id')}")
            print(f"  Model: {latest.get('model_slug')}")
            print(f"  App: {latest.get('app_number')}")
            print(f"  Type: {latest.get('analysis_type')}")
            print(f"  Status: {latest.get('status')}")
            print(f"  Created: {latest.get('created_at')}")
    else:
        print(f"❌ Failed to get tasks")
        print(f"Response: {response.text[:200]}")
    
    print()
    
    # Test 3: Create custom tools analysis
    print("Test 3: Create custom tools analysis")
    print("-" * 70)
    
    form_data = {
        'model_slug': 'anthropic_claude-4.5-haiku-20251001',
        'app_number': '2',
        'analysis_mode': 'custom',
        'selected_tools[]': ['bandit', 'safety', 'eslint', 'zap'],
        'priority': 'high'
    }
    
    print(f"POST {BASE_URL}/analysis/create")
    print(f"Data: {json.dumps(form_data, indent=2)}")
    print()
    
    response = requests.post(
        f'{BASE_URL}/analysis/create',
        data=form_data,
        headers=headers,
        allow_redirects=False
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 302:
        print(f"✅ Success! Redirected to: {response.headers.get('Location')}")
    else:
        print(f"❌ Failed!")
        print(f"Response: {response.text[:500]}")
    
    print()
    
    # Test 4: Use API endpoint instead
    print("Test 4: Create via API endpoint (not form)")
    print("-" * 70)
    
    api_payload = {
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': 3,
        'analysis_profile': 'security',
        'priority': 'normal'
    }
    
    print(f"POST {BASE_URL}/api/analysis/run")
    print(f"Payload: {json.dumps(api_payload, indent=2)}")
    print()
    
    response = requests.post(
        f'{BASE_URL}/api/analysis/run',
        json=api_payload,
        headers={**headers, 'Content-Type': 'application/json'}
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code in [200, 201]:
        result = response.json()
        print(f"✅ Success!")
        print(f"Response: {json.dumps(result, indent=2)}")
    else:
        print(f"❌ Failed!")
        print(f"Response: {response.text[:500]}")
    
    print()
    
    # Summary
    print("=" * 70)
    print("Test Complete")
    print("=" * 70)
    print()
    print("Check results in:")
    print("  - Web UI: http://localhost:5000/analysis/list")
    print("  - File system: results/{model}/app{N}/task_*")
    print()


def test_api_direct():
    """Test API endpoint directly"""
    
    print("\n" + "=" * 70)
    print("Direct API Test (JSON payload)")
    print("=" * 70)
    print()
    
    payload = {
        'model_slug': 'anthropic_claude-4.5-sonnet-20250929',
        'app_number': 1,
        'tools': ['bandit', 'safety', 'pylint', 'eslint'],
        'priority': 'high'
    }
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}',
        'Content-Type': 'application/json'
    }
    
    print(f"POST {BASE_URL}/api/analysis/run")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    response = requests.post(
        f'{BASE_URL}/api/analysis/run',
        json=payload,
        headers=headers
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    print()


if __name__ == '__main__':
    test_create_analysis_comprehensive()
    test_api_direct()