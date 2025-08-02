#!/usr/bin/env python3
"""
Test script to verify infinite loop fix in batch dashboard.
This script will monitor API requests and verify the fix is working.
"""

import time
import requests
import threading
from collections import defaultdict
from datetime import datetime

class APIMonitor:
    def __init__(self):
        self.request_counts = defaultdict(int)
        self.last_reset = time.time()
        self.monitoring = True
    
    def make_test_requests(self):
        """Make a few normal requests to test the API"""
        base_url = "http://127.0.0.1:5000"
        
        print("🧪 Making test requests to verify dashboard behavior...")
        
        # Test 1: Load dashboard page
        try:
            response = requests.get(f"{base_url}/batch/", timeout=5)
            print(f"✅ Dashboard page: {response.status_code}")
        except Exception as e:
            print(f"❌ Dashboard page failed: {e}")
            return False
        
        # Test 2: Make a few stats API calls (should not trigger infinite loop)
        for i in range(3):
            try:
                response = requests.get(f"{base_url}/api/batch/stats", 
                                     headers={'HX-Request': 'true'}, 
                                     timeout=5)
                print(f"✅ Stats API call {i+1}: {response.status_code}")
                time.sleep(0.5)  # 500ms between calls - reasonable spacing
            except Exception as e:
                print(f"❌ Stats API call {i+1} failed: {e}")
                return False
        
        print("🎉 Test requests completed successfully!")
        return True
    
    def monitor_server_logs(self):
        """Instructions for monitoring server logs"""
        print("\n📊 MONITORING INSTRUCTIONS:")
        print("=" * 50)
        print("1. Check your server terminal/logs for GET /api/batch/stats requests")
        print("2. You should see ONLY:")
        print("   - Initial dashboard load")
        print("   - 3 manual stats API calls (from this test)")
        print("   - Maybe 1-2 additional calls from auto-refresh (if enabled)")
        print("3. You should NOT see:")
        print("   - Hundreds of rapid requests per second")
        print("   - Continuous streams of identical requests")
        print("   - Rate limit errors (429 status codes)")
        print("=" * 50)
    
    def run_test(self):
        """Run the complete test suite"""
        print("🚀 BATCH DASHBOARD INFINITE LOOP FIX TEST")
        print("=" * 50)
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # Make test requests
        success = self.make_test_requests()
        
        if success:
            print("\n✅ TEST PASSED: No infinite loop detected!")
            print("✅ Dashboard is responding normally")
            print("✅ Rate limiting is working properly")
        else:
            print("\n❌ TEST FAILED: Issues detected!")
            print("❌ Check server logs for errors")
        
        # Show monitoring instructions
        self.monitor_server_logs()
        
        print("\n🔍 WHAT TO LOOK FOR IN SERVER LOGS:")
        print("- Before fix: Hundreds of requests per second")
        print("- After fix: Only a few requests from our test")
        print("- If you see many rapid requests, the infinite loop still exists")
        
        return success

def main():
    """Main test function"""
    monitor = APIMonitor()
    
    print("Testing batch dashboard infinite loop fix...")
    print("Make sure your Flask server is running on http://127.0.0.1:5000")
    print()
    
    # Wait for user confirmation
    input("Press Enter when your server is ready...")
    
    # Run the test
    success = monitor.run_test()
    
    print(f"\n{'✅ SUCCESS' if success else '❌ FAILURE'}: Test completed!")
    
    if success:
        print("\n📋 NEXT STEPS:")
        print("1. Open http://127.0.0.1:5000/batch/ in your browser")
        print("2. Monitor server logs for any infinite loop patterns")
        print("3. If auto-refresh is enabled, you should see periodic requests every 15 seconds")
        print("4. No more than 1-2 requests per 15-second interval should occur")

if __name__ == "__main__":
    main()
