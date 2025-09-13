#!/usr/bin/env python3
"""Quick test of tool registry API endpoints"""

import requests
import json

base_url = "http://127.0.0.1:5000"

endpoints = [
    "/api/tool-registry/tools",
    "/api/tool-registry/categories", 
    "/api/tool-registry/profiles",
    "/api/tool-registry/custom-analysis",
    "/api/tool-registry/execution-plan"
]

print("🔧 Testing Tool Registry API Endpoints")
print("=" * 50)

for endpoint in endpoints:
    try:
        url = f"{base_url}{endpoint}"
        if endpoint == "/api/tool-registry/custom-analysis":
            # POST endpoint needs data
            data = {
                "name": "Test Analysis",
                "description": "Test description", 
                "tool_ids": [1, 2],
                "configuration": {}
            }
            response = requests.post(url, json=data, timeout=5)
        elif endpoint == "/api/tool-registry/execution-plan":
            # POST endpoint needs data
            data = {
                "profile_id": 1,
                "application_id": 1
            }
            response = requests.post(url, json=data, timeout=5)
        else:
            # GET endpoints
            response = requests.get(url, timeout=5)
        
        print(f"✅ {endpoint}: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                if 'tools' in data:
                    print(f"   Found {len(data['tools'])} tools")
                elif 'categories' in data:
                    print(f"   Found {len(data['categories'])} categories")
                elif 'profiles' in data:
                    print(f"   Found {len(data['profiles'])} profiles")
            except:
                pass
        else:
            print(f"   Error: {response.text[:100]}")
            
    except Exception as e:
        print(f"❌ {endpoint}: {e}")

print("\n🎯 Tool Registry API Test Complete!")