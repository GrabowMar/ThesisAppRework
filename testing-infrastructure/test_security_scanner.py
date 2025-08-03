#!/usr/bin/env python3
"""
Test script for containerized security scanner
"""
import requests
import json
import time

def test_security_scanner():
    base_url = "http://localhost:8001"
    
    # Test health endpoint
    print("🏥 Testing health endpoint...")
    health_response = requests.get(f"{base_url}/health")
    print(f"Health Status: {health_response.status_code}")
    print(f"Health Response: {health_response.json()}")
    
    # Submit security test
    print("\n🔒 Submitting security test for anthropic_claude-3.7-sonnet app1...")
    test_request = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_backend",
        "tools": ["bandit", "safety"],
        "target_url": "http://localhost:6051"
    }
    
    submit_response = requests.post(
        f"{base_url}/tests",
        json=test_request,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Submit Status: {submit_response.status_code}")
    if submit_response.status_code == 200:
        result = submit_response.json()
        print(f"Submit Response: {json.dumps(result, indent=2)}")
        
        # Get test ID
        if 'data' in result and 'test_id' in result['data']:
            test_id = result['data']['test_id']
            print(f"\n📝 Test ID: {test_id}")
            
            # Check status
            print("\n⏳ Checking test status...")
            for i in range(5):
                status_response = requests.get(f"{base_url}/tests/{test_id}/status")
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    print(f"Status Check {i+1}: {json.dumps(status_data, indent=2)}")
                    
                    if status_data.get('data', {}).get('status') == 'completed':
                        # Get results
                        print("\n📊 Getting test results...")
                        result_response = requests.get(f"{base_url}/tests/{test_id}/result")
                        if result_response.status_code == 200:
                            result_data = result_response.json()
                            print(f"Results: {json.dumps(result_data, indent=2)}")
                        break
                    
                    time.sleep(2)
                else:
                    print(f"Status check failed: {status_response.status_code}")
                    break
    else:
        print(f"Submit failed: {submit_response.text}")

if __name__ == "__main__":
    try:
        test_security_scanner()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to security scanner. Make sure it's running on port 8001")
    except Exception as e:
        print(f"❌ Error: {e}")
