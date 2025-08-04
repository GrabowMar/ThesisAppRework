"""Quick API test to check what's wrong with the requests."""

import requests
import json

def test_api():
    base_url = "http://localhost:8001"
    
    # Test basic health check
    try:
        response = requests.get(f"{base_url}/health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Health check failed: {e}")
    
    # Test API docs
    try:
        response = requests.get(f"{base_url}/docs")
        print(f"Docs endpoint: {response.status_code}")
    except Exception as e:
        print(f"Docs check failed: {e}")
    
    # Test the request that's failing
    test_request = {
        "model_name": "anthropic_claude-3.7-sonnet",
        "app_number": 1,
        "analysis_type": "comprehensive"
    }
    
    try:
        print(f"Sending request: {json.dumps(test_request, indent=2)}")
        response = requests.post(f"{base_url}/tests", json=test_request, timeout=30)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_api()
