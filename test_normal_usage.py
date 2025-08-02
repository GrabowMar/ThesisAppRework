#!/usr/bin/env python3
"""
Simple test to verify dashboard works for normal users
"""

import requests
import time

def test_normal_usage():
    """Test how a normal user would use the dashboard"""
    print("🌐 Testing Normal Dashboard Usage")
    print("=" * 40)
    
    # Test 1: Load dashboard page
    print("\n1. Loading dashboard page...")
    try:
        response = requests.get("http://127.0.0.1:5000/batch/", timeout=10)
        if response.status_code == 200:
            print("   ✅ Dashboard loads successfully")
        else:
            print(f"   ❌ Dashboard failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Dashboard error: {e}")
        return False
    
    # Test 2: Wait a moment then test API (like auto-refresh)
    print("\n2. Testing API after page load (simulating auto-refresh)...")
    time.sleep(2)  # Wait like a normal user would
    
    try:
        response = requests.get("http://127.0.0.1:5000/api/batch/stats", timeout=5)
        if response.status_code == 200:
            print("   ✅ API call successful")
        elif response.status_code == 429:
            print("   ⚠️  API rate limited - this would cause user-visible errors")
            return False
        else:
            print(f"   ❌ API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ API error: {e}")
        return False
    
    # Test 3: Another API call after a reasonable interval
    print("\n3. Testing API after normal interval (10 seconds)...")
    time.sleep(1)  # Shorter for testing, but represents normal usage
    
    try:
        response = requests.get("http://127.0.0.1:5000/api/batch/stats", timeout=5)
        if response.status_code == 200:
            print("   ✅ Second API call successful")
        elif response.status_code == 429:
            print("   ⚠️  Still rate limited - rate limiting too aggressive")
            return False
        else:
            print(f"   ❌ Second API failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Second API error: {e}")
        return False
    
    return True

def main():
    success = test_normal_usage()
    
    print(f"\n📋 Result")
    print("=" * 20)
    if success:
        print("✅ Dashboard works normally for regular users!")
        print("🎯 No user-visible rate limit errors")
    else:
        print("❌ Dashboard has user experience issues")
        print("⚠️  Users will see rate limit errors")
    
    print(f"\n💡 Next: Visit http://127.0.0.1:5000/batch/ and check browser console")

if __name__ == "__main__":
    main()
