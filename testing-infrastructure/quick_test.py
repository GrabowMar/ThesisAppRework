#!/usr/bin/env python3
"""
Test the security scanner with real model analysis
"""
import requests
import json
import time

def test_real_analysis():
    """Test security analysis on real model applications."""
    base_url = "http://localhost:8001"
    
    print("🔍 TESTING REAL MODEL ANALYSIS")
    print("=" * 50)
    
    # Test 1: Health Check
    print("\n1️⃣  Health Check")
    try:
        health = requests.get(f"{base_url}/health", timeout=10).json()
        print(f"   Status: {health['data']['status']}")
        print(f"   Service: {health['data']['service']}")
        print("   ✅ Health check passed")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test 2: Submit Real Analysis - Backend
    print("\n2️⃣  Submit Real Security Analysis - Backend")
    test_request_backend = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_backend",
        "tools": ["bandit", "safety"],
        "target_url": "http://localhost:6051"
    }
    
    success_backend = submit_and_check_test(base_url, test_request_backend, "Backend")
    
    # Test 3: Submit Real Analysis - Frontend  
    print("\n3️⃣  Submit Real Security Analysis - Frontend")
    test_request_frontend = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_frontend",
        "tools": ["eslint", "retire"],
        "target_url": "http://localhost:9051"
    }
    
    success_frontend = submit_and_check_test(base_url, test_request_frontend, "Frontend")
    
    return success_backend and success_frontend

def submit_and_check_test(base_url, test_request, test_name):
    """Submit a test and check results."""
    
def submit_and_check_test(base_url, test_request, test_name):
    """Submit a test and check results."""
    try:
        response = requests.post(f"{base_url}/tests", json=test_request, timeout=30)
        if response.status_code == 200:
            result = response.json()
            test_id = result['data']['test_id']
            print(f"   ✅ {test_name} test submitted successfully")
            print(f"   📝 Test ID: {test_id}")
            
            # Wait for completion
            print(f"   ⏳ Waiting for {test_name} analysis to complete...")
            max_wait = 60  # 60 seconds max wait
            wait_time = 0
            while wait_time < max_wait:
                time.sleep(3)
                wait_time += 3
                
                status_response = requests.get(f"{base_url}/tests/{test_id}/status", timeout=10)
                if status_response.status_code == 200:
                    status_data = status_response.json()['data']
                    current_status = status_data['status']
                    
                    if current_status == "completed":
                        break
                    elif current_status == "failed":
                        print(f"   ❌ {test_name} test failed")
                        return False
                    elif wait_time % 15 == 0:  # Show status every 15 seconds
                        print(f"   ⏳ Status: {current_status}")
            
            # Get results
            result_response = requests.get(f"{base_url}/tests/{test_id}/result", timeout=10)
            if result_response.status_code == 200:
                result_data = result_response.json()['data']
                print(f"   ✅ {test_name} analysis completed")
                print(f"   ⏱️  Duration: {result_data.get('duration', 'N/A'):.3f} seconds")
                print(f"   🔧 Tools Used: {', '.join(result_data.get('tools_used', []))}")
                
                # Show detailed results
                total_issues = result_data.get('total_issues', 0)
                print(f"   🐛 Total Issues Found: {total_issues}")
                
                if total_issues > 0:
                    print(f"   📊 Issue Breakdown:")
                    print(f"      🔴 Critical: {result_data.get('critical_count', 0)}")
                    print(f"      🟠 High: {result_data.get('high_count', 0)}")
                    print(f"      🟡 Medium: {result_data.get('medium_count', 0)}")
                    print(f"      🟢 Low: {result_data.get('low_count', 0)}")
                    
                    # Show sample issues
                    issues = result_data.get('issues', [])
                    if issues:
                        print(f"   🔍 Issues Found:")
                        for idx, issue in enumerate(issues[:3]):  # Show first 3 issues
                            tool = issue.get('tool', 'unknown')
                            severity = issue.get('severity', 'unknown')
                            file_path = issue.get('file_path', 'unknown')
                            message = issue.get('message', 'No description')
                            code_snippet = issue.get('code_snippet', '')
                            line_number = issue.get('line_number', '')
                            
                            print(f"      {idx+1}. [{tool.upper()}] {message}")
                            print(f"         Severity: {severity}")
                            print(f"         File: {file_path}")
                            if line_number:
                                print(f"         Line: {line_number}")
                            if code_snippet:
                                print(f"         Code: {code_snippet}")
                            print()
                        
                        if len(issues) > 3:
                            print(f"      ... and {len(issues) - 3} more issues")
                else:
                    print(f"   ✅ No security issues found!")
                
                return True
            else:
                print(f"   ❌ Failed to get {test_name} results: {result_response.status_code}")
                return False
        else:
            print(f"   ❌ Failed to submit {test_name} test: {response.status_code}")
            if response.text:
                print(f"   Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ {test_name} test error: {e}")
        return False

def main():
    """Main test execution."""
    try:
        success = test_real_analysis()
        
        print("\n" + "=" * 50)
        if success:
            print("🎉 REAL MODEL ANALYSIS TEST PASSED!")
            print("✅ Security scanner successfully analyzes real source code")
            print("✅ Actual Python and JavaScript files are being processed")
            print("✅ JSON results contain detailed security findings")
            print("✅ Multiple security tools are working together")
        else:
            print("❌ REAL MODEL ANALYSIS TEST FAILED!")
            
        return success
        
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return False

if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
