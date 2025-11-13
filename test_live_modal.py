#!/usr/bin/env python3
"""
Live Integration Test: Report Modal Endpoint
=============================================

Makes a real HTTP request to the running Flask app to verify the modal works.
"""

import requests
import json
import re
from requests.exceptions import RequestException

def test_live_endpoint():
    """Test the live /reports/new endpoint."""
    base_url = "http://localhost:5000"
    endpoint = f"{base_url}/reports/new"
    
    print("=" * 60)
    print("LIVE ENDPOINT INTEGRATION TEST")
    print("=" * 60)
    
    try:
        # Create session and login
        session = requests.Session()
        
        print(f"\n🔐 Logging in as admin...")
        login_data = {
            'username': 'admin',
            'password': 'ia5aeQE2wR87J8w'
        }
        login_response = session.post(f"{base_url}/auth/login", data=login_data, timeout=10)
        
        if login_response.status_code != 200 and login_response.status_code != 302:
            print(f"   ❌ Login failed: {login_response.status_code}")
            return
        
        print(f"   ✅ Login successful")
        
        # Make request to the modal endpoint
        print(f"\n🌐 Requesting: {endpoint}")
        response = session.get(endpoint, timeout=10)
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Unexpected status code: {response.status_code}")
            if response.status_code == 302:
                print(f"   → Redirected to: {response.headers.get('Location')}")
                print("   ⚠️  You may need to log in first")
            return
        
        html = response.text
        print(f"   Response size: {len(html)} bytes")
        
        # Extract modelsCache
        models_match = re.search(r'const modelsCache = (\[.*?\]);', html, re.DOTALL)
        if models_match:
            try:
                models_data = json.loads(models_match.group(1))
                
                print(f"\n📊 Models in modal: {len(models_data)}")
                
                if len(models_data) == 0:
                    print("   ❌ FAILED: Modal shows 'No models available'")
                    print("   This means the database sync did not work correctly.")
                else:
                    print("   ✅ SUCCESS: Modal has model data!")
                    for i, model in enumerate(models_data, 1):
                        print(f"\n   {i}. {model.get('provider')} / {model.get('model_name')}")
                        print(f"      Slug: {model.get('canonical_slug')}")
            except json.JSONDecodeError as e:
                print(f"   ❌ Failed to parse models JSON: {e}")
        else:
            print("   ❌ Could not find modelsCache in response")
        
        # Extract appsCache
        apps_match = re.search(r'const appsCache = (\{.*?\});', html, re.DOTALL)
        if apps_match:
            try:
                apps_data = json.loads(apps_match.group(1))
                print(f"\n📋 Apps mapped for {len(apps_data)} models:")
                for slug, app_numbers in sorted(apps_data.items()):
                    print(f"   {slug}: {app_numbers}")
            except json.JSONDecodeError as e:
                print(f"   ❌ Failed to parse apps JSON: {e}")
        
        # Final verdict
        if models_match and apps_match:
            models_data = json.loads(models_match.group(1))
            apps_data = json.loads(apps_match.group(1))
            
            if len(models_data) > 0 and len(apps_data) > 0:
                print("\n" + "=" * 60)
                print("🎉 LIVE TEST PASSED!")
                print("The report modal will display models correctly in the UI.")
                print("=" * 60)
            else:
                print("\n" + "=" * 60)
                print("❌ LIVE TEST FAILED")
                print("Modal data is empty. Run: python scripts/sync_generated_apps.py")
                print("=" * 60)
        
    except RequestException as e:
        print(f"\n❌ Request failed: {e}")
        print("   Make sure Flask app is running: python src/main.py")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == '__main__':
    test_live_endpoint()
