"""
Test script to verify Docker build routes work correctly
"""
import requests
import time

def test_build_routes():
    """Test the Docker build functionality through web routes."""
    base_url = "http://127.0.0.1:5000"
    
    # Test build endpoint
    model = "anthropic_claude-3.7-sonnet"
    app_num = "1"
    
    print(f"Testing build route for {model}/app{app_num}")
    
    try:
        # Test the dedicated build route
        build_url = f"{base_url}/docker/build/{model}/{app_num}"
        print(f"POST {build_url}")
        
        response = requests.post(build_url, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            print("✅ Build route responded successfully")
        else:
            print("❌ Build route failed")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    
    # Test bulk build endpoint
    print("\nTesting bulk build route")
    
    try:
        bulk_build_url = f"{base_url}/docker/bulk-build"
        data = {
            'models': [model],
            'apps': ['1', '2'],
            'workers': 2
        }
        
        print(f"POST {bulk_build_url}")
        response = requests.post(bulk_build_url, json=data, timeout=60)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.text[:500]}...")
        
        if response.status_code == 200:
            print("✅ Bulk build route responded successfully")
        else:
            print("❌ Bulk build route failed")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Bulk build request failed: {e}")

if __name__ == "__main__":
    print("Testing Docker build routes...")
    print("=" * 50)
    test_build_routes()
