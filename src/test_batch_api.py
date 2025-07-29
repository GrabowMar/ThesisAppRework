#!/usr/bin/env python3
"""Test batch job web API functionality."""

import requests
import json

def test_batch_job_web_api():
    base_url = "http://127.0.0.1:5000"
    
    print("Testing batch job web API...")
    
    # Test 1: Create a new batch job via POST request
    create_data = {
        'name': 'Web API Test Job',
        'description': 'Testing batch job creation via web API',
        'analysis_types': ['backend_security'],
        'models': ['anthropic_claude-3.7-sonnet'],
        'app_range': '1-2',
        'auto_start': False
    }
    
    try:
        print("1. Creating batch job via web API...")
        response = requests.post(f"{base_url}/batch/create", data=create_data)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                job_id = result['data']['job_id']
                print(f"✅ Successfully created job: {job_id}")
                
                # Test 2: Retrieve the job details
                print("2. Retrieving job details...")
                detail_response = requests.get(f"{base_url}/batch/job/{job_id}")
                
                if detail_response.status_code == 200:
                    print("✅ Successfully retrieved job details")
                else:
                    print(f"❌ Failed to retrieve job details: {detail_response.status_code}")
                    
            else:
                print(f"❌ Job creation failed: {result.get('error', 'Unknown error')}")
        else:
            print(f"❌ HTTP request failed: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing web API: {str(e)}")
    
    # Test 3: List all jobs
    try:
        print("3. Listing all batch jobs...")
        response = requests.get(f"{base_url}/batch")
        
        if response.status_code == 200:
            print("✅ Successfully retrieved batch overview")
        else:
            print(f"❌ Failed to retrieve batch overview: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error listing jobs: {str(e)}")

if __name__ == '__main__':
    test_batch_job_web_api()
