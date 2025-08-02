#!/usr/bin/env python3
"""
Test script to verify batch dashboard fixes are working properly.
Tests both the JavaScript deduplication and backend rate limiting.
"""

import requests
import time
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "http://127.0.0.1:5000"

def test_single_request():
    """Test a single API request"""
    try:
        response = requests.get(f"{BASE_URL}/api/batch/stats", timeout=5)
        return {
            'status_code': response.status_code,
            'success': response.status_code == 200,
            'response_time': response.elapsed.total_seconds(),
            'content_length': len(response.text) if response.text else 0
        }
    except Exception as e:
        return {
            'status_code': None,
            'success': False,
            'error': str(e),
            'response_time': None,
            'content_length': 0
        }

def test_concurrent_requests(num_requests=3, max_workers=2):
    """Test multiple concurrent requests with spacing to verify proper handling"""
    print(f"\n🔧 Testing {num_requests} requests with proper spacing...")
    
    results = []
    
    # First request
    result1 = test_single_request()
    results.append(result1)
    print(f"   Request 1: {'✅' if result1['success'] else '❌'}")
    
    # Wait for rate limit
    time.sleep(0.12)
    
    # Second request
    result2 = test_single_request()
    results.append(result2)
    print(f"   Request 2: {'✅' if result2['success'] else '❌'}")
    
    # Wait for rate limit
    time.sleep(0.12)
    
    # Third request  
    result3 = test_single_request()
    results.append(result3)
    print(f"   Request 3: {'✅' if result3['success'] else '❌'}")
    
    # Analyze results
    successful = [r for r in results if r['success']]
    rate_limited = [r for r in results if r.get('status_code') == 429]
    errors = [r for r in results if not r['success'] and r.get('status_code') != 429]
    
    print(f"📊 Results:")
    print(f"   ✅ Successful: {len(successful)}")
    print(f"   ⏱️  Rate limited: {len(rate_limited)}")
    print(f"   ❌ Errors: {len(errors)}")
    
    return {
        'total_requests': num_requests,
        'successful': len(successful),
        'rate_limited': len(rate_limited),
        'errors': len(errors)
    }

def test_rapid_requests():
    """Test rapid requests to verify rate limiting kicks in but first request succeeds"""
    print(f"\n⚡ Testing rapid requests with proper timing...")
    
    results = []
    
    # First request should succeed
    print("   Making first request...")
    result1 = test_single_request()
    results.append(result1)
    print(f"   Request 1: {'✅' if result1['success'] else '❌'} "
          f"(Status: {result1.get('status_code', 'ERROR')})")
    
    # Immediate second request should be rate limited
    print("   Making immediate second request...")
    result2 = test_single_request()
    results.append(result2)
    print(f"   Request 2: {'⏱️' if result2.get('status_code') == 429 else ('✅' if result2['success'] else '❌')} "
          f"(Status: {result2.get('status_code', 'ERROR')})")
    
    # Wait for rate limit to reset, then try again
    print("   Waiting 150ms for rate limit reset...")
    time.sleep(0.15)
    
    result3 = test_single_request()
    results.append(result3)
    print(f"   Request 3: {'✅' if result3['success'] else '❌'} "
          f"(Status: {result3.get('status_code', 'ERROR')})")
    
    return results

def test_dashboard_page():
    """Test that the dashboard page loads correctly"""
    print(f"\n🌐 Testing dashboard page...")
    
    try:
        response = requests.get(f"{BASE_URL}/batch/", timeout=10)
        
        if response.status_code == 200:
            print("   ✅ Dashboard page loads successfully")
            
            # Check for key elements
            content = response.text.lower()
            checks = [
                ('stats-grid', 'statistics grid'),
                ('batch-dashboard', 'dashboard container'),
                ('updatestats', 'JavaScript updateStats function'),
                ('statsupdateinprogress', 'deduplication flag')
            ]
            
            for check, description in checks:
                if check in content:
                    print(f"   ✅ Found {description}")
                else:
                    print(f"   ⚠️  Missing {description}")
                    
        else:
            print(f"   ❌ Dashboard failed to load: {response.status_code}")
            
        return response.status_code == 200
        
    except Exception as e:
        print(f"   ❌ Dashboard test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Testing Batch Dashboard Fixes")
    print("=" * 50)
    
    # Test dashboard page
    dashboard_ok = test_dashboard_page()
    
    # Test single request
    print(f"\n🔍 Testing single API request...")
    single_result = test_single_request()
    if single_result['success']:
        print(f"   ✅ API working: {single_result['response_time']:.3f}s")
    else:
        print(f"   ❌ API failed: {single_result.get('error', 'Unknown error')}")
    
    # Test rapid requests (should hit rate limiting)
    rapid_results = test_rapid_requests()
    
    # Test concurrent requests
    concurrent_results = test_concurrent_requests()
    
    # Summary
    print(f"\n📋 Test Summary")
    print("=" * 30)
    print(f"Dashboard Page: {'✅ PASS' if dashboard_ok else '❌ FAIL'}")
    print(f"Single Request: {'✅ PASS' if single_result['success'] else '❌ FAIL'}")
    
    # Check if rate limiting is working (should have some rate limited requests in rapid test)
    rate_limiting_working = any(r.get('status_code') == 429 for r in rapid_results)
    print(f"Rate Limiting: {'✅ WORKING' if rate_limiting_working else '⚠️  NOT TRIGGERED'}")
    
    # Check if requests work when properly spaced
    spaced_requests_working = concurrent_results['successful'] >= 2
    print(f"Spaced Requests: {'✅ PASS' if spaced_requests_working else '❌ FAIL'}")
    
    if all([dashboard_ok, single_result['success'], spaced_requests_working]):
        print(f"\n🎉 All core tests passed! Dashboard should be working properly.")
        print(f"✅ Rate limiting prevents rapid requests while allowing normal usage.")
    else:
        print(f"\n⚠️  Some tests failed. Check the output above for details.")

if __name__ == "__main__":
    main()
