"""
Simple test for Docker build functionality
"""
import requests

def test_single_build():
    """Test a single build to verify it works."""
    base_url = "http://127.0.0.1:5000"
    model = "anthropic_claude-3.7-sonnet"
    app_num = "2"
    
    print(f"Testing build for {model}/app{app_num}")
    
    try:
        build_url = f"{base_url}/docker/build/{model}/{app_num}"
        response = requests.post(build_url, timeout=30)
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print(f"✅ Build successful! Duration: {data.get('data', {}).get('duration', 'unknown')}s")
                print(f"Message: {data.get('message', '')}")
            else:
                print(f"❌ Build failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")

if __name__ == "__main__":
    test_single_build()
