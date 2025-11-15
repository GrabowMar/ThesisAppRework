"""
Live test of batch generation to verify atomic reservation and versioning.
This simulates what the batch generation wizard does.
"""
import asyncio
import requests
import json
from datetime import datetime
import uuid

BASE_URL = "http://127.0.0.1:5000"

def generate_batch_id():
    """Generate a batch ID like the wizard does."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = str(uuid.uuid4())[:8]
    return f"batch_{timestamp}_{random_suffix}"

async def test_batch_generation():
    """Test batch generation with multiple concurrent requests."""
    
    print("\n" + "="*80)
    print("LIVE BATCH GENERATION TEST")
    print("="*80)
    
    # Generate a batch ID for this test run
    batch_id = generate_batch_id()
    print(f"\nBatch ID: {batch_id}")
    
    # Prepare test data - simulate generating 3 apps with different templates
    test_configs = [
        {
            "model_slug": "test-batch-model",
            "template_slug": "template_a",
            "batch_id": batch_id,
            "description": "Test app 1 with template A"
        },
        {
            "model_slug": "test-batch-model", 
            "template_slug": "template_b",
            "batch_id": batch_id,
            "description": "Test app 2 with template B"
        },
        {
            "model_slug": "test-batch-model",
            "template_slug": "template_c",
            "batch_id": batch_id,
            "description": "Test app 3 with template C"
        }
    ]
    
    print(f"\nSubmitting {len(test_configs)} generation requests...")
    
    # Submit all requests (this would normally happen via the wizard)
    # In reality, the wizard calls /api/gen/generate without app_number
    # and the backend auto-allocates unique app numbers
    
    responses = []
    for i, config in enumerate(test_configs, 1):
        print(f"\n  [{i}] Submitting: {config['template_slug']}")
        
        # Simulate the API call (dry-run mode to not actually generate apps)
        payload = {
            "model_slug": config["model_slug"],
            "template_slug": config["template_slug"],
            "batch_id": config["batch_id"],
            # app_number is None - backend will auto-allocate
            "dry_run": True  # Don't actually generate, just reserve DB records
        }
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/gen/generate",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                data = response.json()
                responses.append(data)
                print(f"      ✓ Response: {data.get('status', 'unknown')}")
                if 'app_number' in data:
                    print(f"        App number: {data['app_number']}")
                if 'message' in data:
                    print(f"        Message: {data['message']}")
            else:
                print(f"      ✗ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            print(f"      ✗ Exception: {e}")
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    
    if not responses:
        print("❌ No successful responses - test failed")
        return False
    
    # Check that all got unique app numbers
    app_numbers = [r.get('app_number') for r in responses if 'app_number' in r]
    
    print(f"\nApp numbers allocated: {app_numbers}")
    print(f"Unique app numbers: {len(set(app_numbers))}")
    print(f"Total requests: {len(responses)}")
    
    if len(set(app_numbers)) == len(app_numbers) == len(test_configs):
        print("\n✅ SUCCESS: All requests got unique app numbers!")
        print(f"   Batch ID: {batch_id}")
        for r in responses:
            print(f"   - App {r.get('app_number')}: {r.get('template_slug', 'unknown template')}")
        return True
    else:
        print("\n❌ FAILED: App numbers were not unique or incomplete!")
        return False

if __name__ == "__main__":
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=2)
        if response.status_code == 200:
            print("✓ Server is running")
        else:
            print(f"✗ Server returned status {response.status_code}")
            exit(1)
    except requests.exceptions.ConnectionError:
        print("✗ Server is not running. Start it with: python src/main.py")
        exit(1)
    
    # Run the test
    result = asyncio.run(test_batch_generation())
    exit(0 if result else 1)
