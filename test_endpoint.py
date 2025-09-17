#!/usr/bin/env python3
"""Test task creation endpoint."""

import requests

def test_task_creation():
    """Test POST to /analysis/create endpoint."""
    data = {
        'model_slug': 'nousresearch_hermes-4-405b',
        'app_number': '1',
        'analysis_mode': 'profile',
        'analysis_profile': 'security',
        'priority': 'normal'
    }
    
    print('Testing POST to /analysis/create...')
    try:
        response = requests.post(
            'http://127.0.0.1:5000/analysis/create', 
            data=data, 
            allow_redirects=False,
            timeout=10
        )
        print(f'Status: {response.status_code}')
        print(f'Headers: {dict(response.headers)}')
        
        if response.status_code in [301, 302]:
            print(f'Redirect to: {response.headers.get("Location")}')
        elif response.text:
            print(f'Response body: {response.text[:500]}...')
            
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    test_task_creation()