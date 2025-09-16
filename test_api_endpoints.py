#!/usr/bin/env python3
"""Quick test of tool registry API endpoints"""

import requests
import json
import sys
import os

# Add src to path to import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from app.factory import create_app
import threading
import time

# Start Flask app in background
app = create_app()

def start_server():
    app.run(host='127.0.0.1', port=5005, debug=False, use_reloader=False)

print("🚀 Starting Flask server...")
server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
time.sleep(3)  # Wait for server to start

base_url = "http://127.0.0.1:5005"

endpoints = [
    "/api/tool-registry/tools",
    "/api/tool-registry/categories", 
    "/api/tool-registry/profiles",
    "/api/tool-registry/tools/by-category"
]

print("🔧 Testing Tool Registry API Endpoints")
print("=" * 50)

for endpoint in endpoints:
    try:
        url = f"{base_url}{endpoint}"
        response = requests.get(url, timeout=5)
        
        print(f"✅ {endpoint}: {response.status_code}")
        if response.status_code == 200:
            try:
                data = response.json()
                if 'data' in data:
                    count = len(data['data'])
                    print(f"   Found {count} items")
                    if count > 0 and isinstance(data['data'], list):
                        # Show sample item
                        sample = data['data'][0]
                        if 'name' in sample:
                            print(f"   Sample: {sample['name']}")
                elif 'tools' in data:
                    print(f"   Found {len(data['tools'])} tools")
                elif 'categories' in data:
                    print(f"   Found {len(data['categories'])} categories")
                elif 'profiles' in data:
                    print(f"   Found {len(data['profiles'])} profiles")
            except:
                print(f"   Response: {response.text[:100]}")
        else:
            print(f"   Error: {response.text[:100]}")
            
    except Exception as e:
        print(f"❌ {endpoint}: {e}")

print("\n🎯 Tool Registry API Test Complete!")