#!/usr/bin/env python3
"""
Simple debug test to find why analysis is stuck in pending
"""
import requests
import json
import time

def debug_stuck_analysis():
    """Debug why analysis gets stuck in pending status."""
    base_url = "http://localhost:8001"
    
    print("🔬 DEBUGGING STUCK ANALYSIS")
    print("=" * 40)
    
    # Submit a simple test
    test_request = {
        "model": "anthropic_claude-3.7-sonnet",
        "app_num": 1,
        "test_type": "security_backend",
        "tools": ["bandit"],
        "target_url": "http://localhost:6051"
    }
    
    print("📋 Submitting simple bandit test...")
    response = requests.post(f"{base_url}/tests", json=test_request)
    
    if response.status_code == 200:
        test_id = response.json()['data']['test_id']
        print(f"✅ Test ID: {test_id}")
        
        # Monitor for a shorter time with more frequent checks
        print("⏳ Monitoring status...")
        for i in range(20):  # Check for 20 iterations (60 seconds)
            time.sleep(3)
            
            status_response = requests.get(f"{base_url}/tests/{test_id}/status")
            if status_response.status_code == 200:
                status_data = status_response.json()['data']
                current_status = status_data['status']
                print(f"   {i+1:2d}. Status: {current_status}")
                
                if current_status == "completed":
                    # Get results immediately
                    result_response = requests.get(f"{base_url}/tests/{test_id}/result")
                    if result_response.status_code == 200:
                        result_data = result_response.json()['data']
                        print(f"\n✅ SUCCESS!")
                        print(f"Duration: {result_data.get('duration')}")
                        print(f"Issues: {len(result_data.get('issues', []))}")
                        
                        for issue in result_data.get('issues', []):
                            print(f"  - {issue.get('tool')}: {issue.get('message')}")
                        return True
                    break
                elif current_status == "failed":
                    print(f"\n❌ FAILED!")
                    # Try to get error details
                    result_response = requests.get(f"{base_url}/tests/{test_id}/result")
                    if result_response.status_code == 200:
                        result_data = result_response.json()['data']
                        error_msg = result_data.get('error_message', 'No error message')
                        print(f"Error: {error_msg}")
                    return False
        
        print(f"\n⏰ Still pending after 60 seconds - this indicates a problem")
        return False
    else:
        print(f"❌ Failed to submit: {response.status_code}")
        print(f"Response: {response.text}")
        return False

if __name__ == "__main__":
    debug_stuck_analysis()
