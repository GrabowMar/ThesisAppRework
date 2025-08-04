#!/usr/bin/env python3
"""
Test script to check if API endpoints are working
"""

import requests
import json

def test_endpoints():
    base_url = "http://127.0.0.1:5000"
    
    # Test health endpoint
    print("Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/testing/api/health")
        print(f"Health Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Health Response: {json.dumps(data, indent=2)}")
        else:
            print(f"Health Error: {response.text}")
    except Exception as e:
        print(f"Health Error: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # Test models endpoint  
    print("Testing models endpoint...")
    try:
        response = requests.get(f"{base_url}/testing/api/models")
        print(f"Models Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Models Count: {len(data.get('data', []))}")
            if data.get('data'):
                print("First few models:")
                for model in data['data'][:3]:
                    print(f"  - {model['display_name']}")
        else:
            print(f"Models Error: {response.text}")
    except Exception as e:
        print(f"Models Error: {e}")

if __name__ == '__main__':
    test_endpoints()
