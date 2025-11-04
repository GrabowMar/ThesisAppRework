"""Quick test script for analysis API endpoint"""
import requests
import json
import time

# API configuration
BASE_URL = "http://localhost:5000"
API_TOKEN = "F9MPSYoWskudXyKpnGvxt-1Udfvi4vt0A-S4djFwy4tzN23e-Mzsy4XTB31eJeE5"
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def test_token_verify():
    """Test if API token is valid"""
    print("\n" + "="*60)
    print("Testing API Token Verification")
    print("="*60)
    
    try:
        response = requests.get(f"{BASE_URL}/api/tokens/verify", headers=HEADERS)
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_create_analysis():
    """Test creating analysis via API"""
    print("\n" + "="*60)
    print("Testing Analysis Creation")
    print("="*60)
    
    model_slug = "anthropic_claude-4.5-sonnet-20250929"
    app_number = 1
    
    payload = {
        "analysis_type": "comprehensive"
    }
    
    print(f"\nPOST /api/app/{model_slug}/{app_number}/analyze")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/app/{model_slug}/{app_number}/analyze",
            headers=HEADERS,
            json=payload
        )
        
        print(f"\nStatus: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 201]:
            task_id = response.json().get('data', {}).get('task_id') or response.json().get('task_id')
            return task_id
        else:
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def check_task_status(task_id):
    """Check task status"""
    print("\n" + "="*60)
    print(f"Checking Task Status: {task_id}")
    print("="*60)
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=HEADERS
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            task_data = response.json()
            print(f"Task Status: {task_data.get('status')}")
            print(f"Progress: {task_data.get('progress_percentage', 0)}%")
            print(f"Response: {json.dumps(task_data, indent=2)}")
            return task_data
        else:
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    """Main test flow"""
    print("\n" + "="*60)
    print("ANALYSIS API TEST SCRIPT")
    print("="*60)
    
    # Test 1: Verify token
    if not test_token_verify():
        print("\n❌ Token verification failed!")
        return
    
    print("\n✅ Token verified successfully!")
    
    # Test 2: Create analysis
    task_id = test_create_analysis()
    
    if not task_id:
        print("\n❌ Failed to create analysis task!")
        return
    
    print(f"\n✅ Analysis task created: {task_id}")
    
    # Test 3: Monitor task status
    print("\n\nMonitoring task progress...")
    
    for i in range(10):  # Check up to 10 times
        time.sleep(5)
        task_data = check_task_status(task_id)
        
        if task_data:
            status = task_data.get('status')
            if status in ['COMPLETED', 'FAILED', 'ERROR']:
                print(f"\n✅ Task finished with status: {status}")
                break
        
        print(f"Waiting... (attempt {i+1}/10)")
    
    print("\n" + "="*60)
    print("Test Complete!")
    print("="*60)

if __name__ == "__main__":
    main()
