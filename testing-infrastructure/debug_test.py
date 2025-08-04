#!/usr/bin/env python3
"""
Debug the bandit parsing issue
"""
import requests
import json
import time

def debug_analysis():
    """Debug why bandit results aren't showing up."""
    base_url = "http://localhost:8001"
    
    print("🔬 DEBUGGING SECURITY ANALYSIS")
    print("=" * 40)
    
    # Test 1: Backend analysis
    print("\n🐍 BACKEND ANALYSIS (Python)")
    test_request_backend = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_backend",
        "tools": ["bandit"],
        "target_url": "http://localhost:6051"
    }
    
    run_analysis_test(base_url, test_request_backend, "Backend")
    
    # Test 2: Frontend analysis
    print("\n🌐 FRONTEND ANALYSIS (JavaScript)")
    test_request_frontend = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_frontend",
        "tools": ["retire"],
        "target_url": "http://localhost:9051"
    }
    
    run_analysis_test(base_url, test_request_frontend, "Frontend")

def run_analysis_test(base_url, test_request, test_name):
    """Run a single analysis test."""
    print(f"📋 Submitting {test_name} analysis...")
    response = requests.post(f"{base_url}/tests", json=test_request)
    
    if response.status_code == 200:
        test_id = response.json()['data']['test_id']
        print(f"✅ Test ID: {test_id}")
        
        # Wait for completion
        time.sleep(8)
        
        # Get results
        result_response = requests.get(f"{base_url}/tests/{test_id}/result")
        if result_response.status_code == 200:
            result_data = result_response.json()['data']
            
            print(f"📊 {test_name} Results:")
            print(f"   Status: {result_data.get('status')}")
            print(f"   Duration: {result_data.get('duration'):.3f} seconds")
            print(f"   Tools Used: {result_data.get('tools_used', [])}")
            
            issues = result_data.get('issues', [])
            print(f"   Issues Found: {len(issues)}")
            
            if issues:
                for i, issue in enumerate(issues[:2]):  # Show first 2 issues
                    print(f"\n   🔍 Issue {i+1}:")
                    print(f"      Tool: {issue.get('tool')}")
                    print(f"      Severity: {issue.get('severity')}")
                    print(f"      File: {issue.get('file_path')}")
                    print(f"      Line: {issue.get('line_number')}")
                    print(f"      Message: {issue.get('message')}")
                    print(f"      Description: {issue.get('description')}")
                    if issue.get('code_snippet'):
                        print(f"      Code: {issue.get('code_snippet')}")
            else:
                print("   ✅ No issues found")
        else:
            print(f"   ❌ Failed to get results: {result_response.status_code}")
    else:
        print(f"   ❌ Failed to submit: {response.status_code}")
        print(f"   Response: {response.text}")

if __name__ == "__main__":
    debug_analysis()
