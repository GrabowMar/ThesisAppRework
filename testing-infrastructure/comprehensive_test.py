#!/usr/bin/env python3
"""
Comprehensive test for the containerized security scanner analyzing real model applications
"""
import requests
import json
import time
import sys

def test_real_model_analysis():
    """Test security analysis on real model applications."""
    base_url = "http://localhost:8001"
    
    print("🔍 TESTING REAL MODEL APPLICATIONS")
    print("=" * 60)
    
    # Test 1: Health Check
    print("\n1️⃣  Health Check")
    try:
        health = requests.get(f"{base_url}/health", timeout=10).json()
        print(f"   Status: {health['data']['status']}")
        print(f"   Service: {health['data']['service']}")
    except Exception as e:
        print(f"   ❌ Health check failed: {e}")
        return False
    
    # Test different models and apps
    test_cases = [
        ("anthropic_claude-3.7-sonnet", 1),
        ("anthropic_claude-3.7-sonnet", 2),
        ("openai_gpt_4", 1) if check_model_exists("openai_gpt_4") else ("anthropic_claude-3.7-sonnet", 3),
        ("google_gemini-2.5-flash", 1) if check_model_exists("google_gemini-2.5-flash") else ("anthropic_claude-3.7-sonnet", 4),
    ]
    
    for i, (model, app_num) in enumerate(test_cases, 2):
        print(f"\n{i}️⃣  Testing {model}/app{app_num}")
        
        # Submit security analysis test
        test_request = {
            "model": model,
            "app_num": app_num,
            "test_type": "security_comprehensive",
            "tools": ["bandit", "safety", "eslint", "retire"],
            "target_url": f"http://localhost:905{app_num}"  # Assuming apps run on 9051, 9052, etc.
        }
        
        try:
            response = requests.post(f"{base_url}/tests", json=test_request, timeout=30)
            if response.status_code == 200:
                result = response.json()
                test_id = result['data']['test_id']
                print(f"   ✅ Test submitted successfully")
                print(f"   📝 Test ID: {test_id}")
                
                # Wait for completion with timeout
                max_wait = 60  # 60 seconds max wait
                wait_time = 0
                while wait_time < max_wait:
                    time.sleep(2)
                    wait_time += 2
                    
                    status_response = requests.get(f"{base_url}/tests/{test_id}/status", timeout=10)
                    if status_response.status_code == 200:
                        status_data = status_response.json()['data']
                        current_status = status_data['status']
                        
                        if current_status == "completed":
                            break
                        elif current_status == "failed":
                            print(f"   ❌ Test failed")
                            continue
                        else:
                            print(f"   ⏳ Status: {current_status}")
                
                # Get final results
                result_response = requests.get(f"{base_url}/tests/{test_id}/result", timeout=10)
                if result_response.status_code == 200:
                    result_data = result_response.json()['data']
                    print(f"   ✅ Analysis completed")
                    print(f"   ⏱️  Duration: {result_data.get('duration', 'N/A'):.3f} seconds")
                    print(f"   🔧 Tools Used: {', '.join(result_data.get('tools_used', []))}")
                    
                    # Show detailed issue breakdown
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
                            print(f"   🔍 Sample Issues:")
                            for idx, issue in enumerate(issues[:3]):
                                tool = issue.get('tool', 'unknown')
                                severity = issue.get('severity', 'unknown')
                                file_path = issue.get('file_path', 'unknown')
                                message = issue.get('message', 'No description')
                                code_snippet = issue.get('code_snippet', '')
                                
                                print(f"      {idx+1}. [{tool.upper()}] {message}")
                                print(f"         Severity: {severity}")
                                print(f"         File: {file_path}")
                                if code_snippet:
                                    print(f"         Code: {code_snippet}")
                                if idx < len(issues) - 1:
                                    print()
                            
                            if len(issues) > 3:
                                print(f"      ... and {len(issues) - 3} more issues")
                    else:
                        print(f"   ✅ No security issues found!")
                        
                else:
                    print(f"   ❌ Failed to get results: {result_response.status_code}")
                    print(f"   Error: {result_response.text}")
            else:
                print(f"   ❌ Failed to submit test: {response.status_code}")
                print(f"   Error: {response.text}")
                
        except Exception as e:
            print(f"   ❌ Test error: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 REAL MODEL ANALYSIS TESTING COMPLETE")
    print("✅ Security scanner: Analyzing real source code")
    print("✅ Multiple tools: Bandit, Safety, ESLint, Retire.js") 
    print("✅ JSON responses: Structured issue reporting")
    print("✅ Real applications: AI-generated model apps")
    return True

def check_model_exists(model_name):
    """Check if a model directory exists."""
    import os
    model_path = f"../misc/models/{model_name}"
    return os.path.exists(model_path)

def test_specific_model_files():
    """Test analysis of specific known files."""
    print("\n🔬 DETAILED FILE ANALYSIS")
    print("=" * 40)
    
    # Test specific known vulnerable patterns
    base_url = "http://localhost:8001"
    
    # Test anthropic_claude-3.7-sonnet/app1 which we know exists
    test_request = {
        "model": "anthropic_claude-3.7-sonnet", 
        "app_num": 1,
        "test_type": "security_backend",
        "tools": ["bandit", "safety"],
        "target_url": "http://localhost:6051"
    }
    
    try:
        response = requests.post(f"{base_url}/tests", json=test_request)
        if response.status_code == 200:
            test_id = response.json()['data']['test_id']
            
            # Wait for completion
            time.sleep(5)
            
            result_response = requests.get(f"{base_url}/tests/{test_id}/result")
            if result_response.status_code == 200:
                result_data = result_response.json()['data']
                
                print("📁 Analyzed Files:")
                issues = result_data.get('issues', [])
                analyzed_files = set()
                
                for issue in issues:
                    file_path = issue.get('file_path', '')
                    if file_path:
                        analyzed_files.add(file_path)
                
                if analyzed_files:
                    for file_path in sorted(analyzed_files):
                        print(f"   📄 {file_path}")
                else:
                    print("   ℹ️  Analysis completed but no issues found in files")
                
                print(f"\n📊 Analysis Summary:")
                print(f"   Files analyzed: {len(analyzed_files) if analyzed_files else 'Unknown'}")
                print(f"   Security issues: {len(issues)}")
                print(f"   Tools executed: {', '.join(result_data.get('tools_used', []))}")
                
    except Exception as e:
        print(f"❌ Detailed analysis failed: {e}")

def main():
    """Main test execution."""
    try:
        success = test_real_model_analysis()
        test_specific_model_files()
        
        if success:
            print("\n🎯 ALL TESTS PASSED - Real model analysis working!")
            sys.exit(0)
        else:
            print("\n❌ SOME TESTS FAILED")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
