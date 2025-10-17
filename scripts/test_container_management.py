"""
Test Container Management Frontend

Simple script to test the container management endpoints work correctly.
"""

import requests
import json
import time
import sys

BASE_URL = "http://127.0.0.1:5000"

def test_start_container(model_slug, app_number):
    """Test starting a container."""
    print(f"\n{'='*70}")
    print(f"Testing START: {model_slug}/app{app_number}")
    print('='*70)
    
    url = f"{BASE_URL}/api/app/{model_slug}/{app_number}/start"
    print(f"POST {url}")
    
    try:
        response = requests.post(url, headers={'Content-Type': 'application/json'}, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('message')}")
            if 'data' in data and 'status_summary' in data['data']:
                summary = data['data']['status_summary']
                print(f"   Containers: {summary.get('containers_found', 0)}")
                print(f"   States: {', '.join(summary.get('states', []))}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_stop_container(model_slug, app_number):
    """Test stopping a container."""
    print(f"\n{'='*70}")
    print(f"Testing STOP: {model_slug}/app{app_number}")
    print('='*70)
    
    url = f"{BASE_URL}/api/app/{model_slug}/{app_number}/stop"
    print(f"POST {url}")
    
    try:
        response = requests.post(url, headers={'Content-Type': 'application/json'}, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Success: {data.get('message')}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def test_status(model_slug, app_number):
    """Test getting container status."""
    print(f"\n{'='*70}")
    print(f"Testing STATUS: {model_slug}/app{app_number}")
    print('='*70)
    
    url = f"{BASE_URL}/api/app/{model_slug}/{app_number}/status"
    print(f"GET {url}")
    
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if 'data' in data:
                info = data['data']
                print(f"✅ Compose file exists: {info.get('compose_file_exists')}")
                print(f"   Containers: {info.get('containers', [])}")
                print(f"   Running: {info.get('running')}")
            return True
        else:
            print(f"❌ Failed: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Run the test suite."""
    print("\n" + "="*70)
    print("Container Management Frontend Test")
    print("="*70)
    
    # Test with app that exists and is fixed
    model = "anthropic_claude-4.5-haiku-20251001"
    app_num = 1
    
    results = []
    
    # Test 1: Start
    results.append(("Start Container", test_start_container(model, app_num)))
    
    # Wait for container to be healthy
    print("\nWaiting 5 seconds for container to become healthy...")
    time.sleep(5)
    
    # Test 2: Status
    results.append(("Get Status", test_status(model, app_num)))
    
    # Test 3: Stop
    results.append(("Stop Container", test_stop_container(model, app_num)))
    
    # Wait a moment
    time.sleep(2)
    
    # Test 4: Status again
    results.append(("Get Status (after stop)", test_status(model, app_num)))
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        all_passed = all_passed and passed
    
    print("="*70)
    
    if all_passed:
        print("\n🎉 All tests passed! Container management is working correctly.")
        print("\nYou can now:")
        print("1. Open http://127.0.0.1:5000/applications in your browser")
        print("2. Click start/stop buttons on any application")
        print("3. View real-time logs in the modal window")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please review the output above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
