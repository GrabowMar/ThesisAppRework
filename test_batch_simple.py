#!/usr/bin/env python3
"""
Simple test script to verify batch API functionality
"""
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_get_batch_jobs():
    """Test getting all batch jobs"""
    try:
        response = requests.get(f"{BASE_URL}/api/batch/jobs")
        print(f"GET /api/batch/jobs - Status: {response.status_code}")
        if response.status_code == 200:
            jobs = response.json()
            print(f"Found {len(jobs)} jobs:")
            for job in jobs[:3]:  # Show first 3 jobs
                print(f"  - {job['id']}: {job.get('name', 'Unnamed')} ({job.get('status', 'Unknown')})")
        else:
            print(f"Error: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error testing GET jobs: {e}")
        return False

def test_create_batch_job():
    """Test creating a new batch job"""
    try:
        job_data = {
            "name": "Test Batch Job",
            "description": "Testing API functionality",
            "models": ["anthropic_claude-3.7-sonnet", "openai_gpt-4.1"],
            "apps": [1, 2, 3],
            "analysis_type": ["backend_security", "frontend_security"],
            "config": {
                "tools": {
                    "backend": {"bandit": True, "safety": True},
                    "frontend": {"eslint": True}
                }
            }
        }
        
        response = requests.post(
            f"{BASE_URL}/api/batch/jobs",
            json=job_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"POST /api/batch/jobs - Status: {response.status_code}")
        if response.status_code in [200, 201]:
            job = response.json()
            print(f"Created job: {job.get('id')} - {job.get('name')}")
            return job.get('id')
        else:
            print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"Error testing POST job: {e}")
        return None

def test_get_specific_job(job_id):
    """Test getting a specific job"""
    try:
        response = requests.get(f"{BASE_URL}/api/batch/jobs/{job_id}")
        print(f"GET /api/batch/jobs/{job_id} - Status: {response.status_code}")
        if response.status_code == 200:
            job = response.json()
            print(f"Job details: {job.get('name')} - Status: {job.get('status')}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Error testing GET specific job: {e}")
        return False

def test_dashboard_stats():
    """Test dashboard stats endpoint"""
    try:
        response = requests.get(f"{BASE_URL}/api/dashboard/stats")
        print(f"GET /api/dashboard/stats - Status: {response.status_code}")
        if response.status_code == 200:
            stats = response.json()
            print(f"Dashboard stats: {json.dumps(stats, indent=2)}")
            return True
        else:
            print(f"Error: {response.text}")
            return False
    except Exception as e:
        print(f"Error testing dashboard stats: {e}")
        return False

def main():
    print("=== Testing Batch API ===")
    print(f"Base URL: {BASE_URL}")
    print()
    
    # Test dashboard stats first
    print("1. Testing dashboard stats...")
    test_dashboard_stats()
    print()
    
    # Test getting existing jobs
    print("2. Testing get all jobs...")
    success = test_get_batch_jobs()
    print()
    
    if success:
        # Test creating a new job
        print("3. Testing create new job...")
        new_job_id = test_create_batch_job()
        print()
        
        if new_job_id:
            # Test getting the specific job
            print("4. Testing get specific job...")
            test_get_specific_job(new_job_id)
            print()
            
            # Test getting all jobs again to see the new one
            print("5. Testing get all jobs again...")
            test_get_batch_jobs()
    
    print("=== Test Complete ===")

if __name__ == "__main__":
    main()
