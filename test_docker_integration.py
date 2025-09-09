#!/usr/bin/env python3
"""
Quick test script for Docker integration and diagnostics endpoints.
"""

import requests
import json

def test_docker_endpoints():
    """Test the new Docker-related API endpoints."""
    
    base_url = "http://localhost:5000"
    model_slug = "anthropic_claude-3.7-sonnet"
    app_number = 1
    
    endpoints = [
        f"/api/app/{model_slug}/{app_number}/diagnose",
        f"/api/app/{model_slug}/{app_number}/status",
    ]
    
    print("Testing Docker integration endpoints...")
    
    for endpoint in endpoints:
        url = f"{base_url}{endpoint}"
        print(f"\nTesting: {endpoint}")
        
        try:
            response = requests.get(url)
            print(f"Status: {response.status_code}")
            
            if response.headers.get('content-type', '').startswith('application/json'):
                # JSON response
                data = response.json()
                print("Response (JSON):")
                print(json.dumps(data, indent=2))
            else:
                # HTML response
                print("Response (HTML):")
                print(response.text[:500])
                if len(response.text) > 500:
                    print("... (truncated)")
                    
        except requests.exceptions.ConnectionError:
            print("ERROR: Could not connect to Flask app. Is it running on localhost:5000?")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_docker_endpoints()
