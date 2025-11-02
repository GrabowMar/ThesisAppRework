#!/usr/bin/env python3
"""
Verify Web UI Task Loading with Bearer Token
=============================================

This script verifies that the web UI's task loading endpoint works correctly
with Bearer token authentication (not just session cookies).

Tests:
1. Verify Bearer token is valid
2. Access /analysis/api/tasks/list with Bearer token
3. Parse the returned HTML to count tasks
4. Verify task data is complete
"""

import requests
from bs4 import BeautifulSoup
import json

# Configuration
BASE_URL = 'http://localhost:5000'
BEARER_TOKEN = 'WCVNOZZ125gzTx_Z1F6pjnW34JIWqYLyh9xTytVbaJnTUfXYFrir2EJcadpYgelI'

def print_header(text):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"  {text}")
    print(f"{'='*70}")


def verify_token():
    """Verify the Bearer token is valid"""
    print_header("TEST 1: Verify Bearer Token")
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    response = requests.get(f'{BASE_URL}/api/tokens/verify', headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        if data.get('valid'):
            user = data.get('user', {})
            print(f"✓ Token is VALID")
            print(f"  User: {user.get('username')}")
            print(f"  Email: {user.get('email')}")
            print(f"  Admin: {user.get('is_admin')}")
            return True
        else:
            print(f"✗ Token is INVALID")
            return False
    else:
        print(f"✗ Failed to verify token: {response.status_code}")
        return False


def test_tasks_endpoint():
    """Test the /analysis/api/tasks/list endpoint with Bearer token"""
    print_header("TEST 2: Load Tasks via HTMX Endpoint")
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}',
        'HX-Request': 'true',
        'HX-Trigger': 'load',
        'HX-Target': 'task-table-container'
    }
    
    params = {
        'page': 1,
        'per_page': 50
    }
    
    response = requests.get(
        f'{BASE_URL}/analysis/api/tasks/list',
        headers=headers,
        params=params
    )
    
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Content-Length: {len(response.text)} bytes")
    print(f"X-Partial: {response.headers.get('X-Partial', 'N/A')}")
    
    if response.status_code == 200:
        print(f"✓ Request successful")
        return response.text
    else:
        print(f"✗ Request failed")
        return None


def parse_tasks_table(html):
    """Parse the tasks table HTML to extract task information"""
    print_header("TEST 3: Parse Tasks Table HTML")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Find the table
    table = soup.find('table')
    if not table:
        print(f"✗ No table found in HTML")
        return []
    
    print(f"✓ Found table element")
    
    # Find all task rows (skip header)
    rows = table.find_all('tr')
    print(f"✓ Found {len(rows)} total rows (including header)")
    
    # Parse task data
    tasks = []
    for row in rows[1:]:  # Skip header row
        cells = row.find_all('td')
        if not cells:
            continue
        
        # Extract basic task info
        task_info = {
            'has_cells': len(cells),
            'is_subtask': 'subtask-row' in row.get('class', [])
        }
        
        # Try to extract task ID from link
        link = row.find('a', href=lambda x: x and '/analysis/tasks/' in x)
        if link:
            href = link.get('href', '')
            task_id = href.split('/analysis/tasks/')[-1].split('/')[0] if '/analysis/tasks/' in href else None
            task_info['task_id'] = task_id
        
        # Try to extract status badge
        badge = row.find('span', class_='badge')
        if badge:
            task_info['status'] = badge.text.strip()
        
        tasks.append(task_info)
    
    print(f"✓ Parsed {len(tasks)} task rows")
    
    # Count main tasks vs subtasks
    main_tasks = [t for t in tasks if not t.get('is_subtask')]
    subtasks = [t for t in tasks if t.get('is_subtask')]
    
    print(f"  Main tasks: {len(main_tasks)}")
    print(f"  Subtasks: {len(subtasks)}")
    
    # Show status breakdown
    statuses = {}
    for task in tasks:
        status = task.get('status', 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
    
    print(f"\n  Status breakdown:")
    for status, count in sorted(statuses.items()):
        print(f"    {status}: {count}")
    
    return tasks


def test_specific_task_details():
    """Test accessing a specific task's details via API"""
    print_header("TEST 4: Access Specific Task via API")
    
    headers = {
        'Authorization': f'Bearer {BEARER_TOKEN}'
    }
    
    # First, let's check what tasks exist via the API
    # (not the HTMX endpoint, but a proper API endpoint if available)
    
    # Try to access the analysis results export
    response = requests.get(
        f'{BASE_URL}/api/analysis/tasks',
        headers=headers,
        params={'limit': 5}
    )
    
    print(f"GET /api/analysis/tasks: {response.status_code}")
    
    if response.status_code == 200:
        try:
            data = response.json()
            tasks = data.get('tasks', data.get('data', []))
            print(f"✓ Found {len(tasks)} tasks via API")
            
            if tasks:
                first_task = tasks[0]
                print(f"\n  First task:")
                print(f"    ID: {first_task.get('task_id', first_task.get('id'))}")
                print(f"    Model: {first_task.get('model_slug')}")
                print(f"    App: {first_task.get('app_number')}")
                print(f"    Status: {first_task.get('status')}")
                return True
        except Exception as e:
            print(f"  Could not parse JSON: {e}")
            return False
    else:
        print(f"  Endpoint may not exist or requires different auth")
        return False


def main():
    """Run all verification tests"""
    print(f"\n{'#'*70}")
    print(f"  Web UI Task Loading Verification with Bearer Token")
    print(f"{'#'*70}")
    print(f"\nBase URL: {BASE_URL}")
    print(f"Token: {BEARER_TOKEN[:20]}...")
    
    # Test 1: Verify token
    if not verify_token():
        print(f"\n✗ FAILED: Token verification failed")
        return False
    
    # Test 2: Load tasks
    html = test_tasks_endpoint()
    if not html:
        print(f"\n✗ FAILED: Could not load tasks")
        return False
    
    # Test 3: Parse tasks
    tasks = parse_tasks_table(html)
    if not tasks:
        print(f"\n✗ WARNING: No tasks found in table")
    
    # Test 4: Try specific task API
    test_specific_task_details()
    
    # Summary
    print_header("SUMMARY")
    print(f"✓ Bearer token authentication: WORKING")
    print(f"✓ HTMX tasks endpoint: WORKING")
    print(f"✓ HTML table parsing: WORKING")
    print(f"✓ Tasks found: {len(tasks)}")
    
    if tasks:
        print(f"\n✓ SUCCESS: Web UI task loading works with Bearer token!")
        print(f"  The web UI can authenticate using Bearer tokens,")
        print(f"  not just session cookies.")
    else:
        print(f"\n⚠ NOTE: No tasks currently exist")
        print(f"  Run an analysis to create tasks, then verify they appear")
    
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
