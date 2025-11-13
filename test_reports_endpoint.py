"""
Test the /reports/new endpoint with authentication
"""
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Create session with retries
session = requests.Session()
retry = Retry(connect=3, backoff_factor=0.5)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)

BASE_URL = 'http://localhost:5000'

def test_reports_new():
    """Test /reports/new endpoint"""
    print("=" * 80)
    print("Testing /reports/new endpoint")
    print("=" * 80)
    
    # Try without auth first
    print("\n1. Testing without authentication...")
    response = session.get(f'{BASE_URL}/reports/new', allow_redirects=False)
    print(f"   Status: {response.status_code}")
    
    if response.status_code == 302:
        print(f"   ✓ Redirects to: {response.headers.get('Location', 'N/A')}")
        print("   (Authentication required)")
    
    # Login as admin (assuming default credentials)
    print("\n2. Attempting login...")
    login_data = {
        'username': 'admin',
        'password': 'admin'
    }
    
    login_response = session.post(f'{BASE_URL}/auth/login', data=login_data, allow_redirects=True)
    print(f"   Login status: {login_response.status_code}")
    
    if login_response.status_code == 200 and 'login' not in login_response.url.lower():
        print("   ✓ Login successful!")
    else:
        print("   ✗ Login failed - using default admin/admin credentials")
        print("   You may need to run: python scripts/create_admin.py")
        return
    
    # Now test the reports/new endpoint
    print("\n3. Testing /reports/new with authentication...")
    reports_response = session.get(f'{BASE_URL}/reports/new')
    print(f"   Status: {reports_response.status_code}")
    
    if reports_response.status_code == 200:
        content = reports_response.text
        
        # Check for key elements
        checks = [
            ('modelsCache', 'Models data injection'),
            ('appsCache', 'Apps data injection'),
            ('buildModelSelect', 'Model select function'),
            ('buildModelMultiSelect', 'Model multi-select function'),
            ('report-modal', 'Modal container'),
        ]
        
        print("\n   Content checks:")
        all_passed = True
        for pattern, description in checks:
            found = pattern in content
            status = "✓" if found else "✗"
            print(f"   {status} {description}")
            if not all_passed and not found:
                all_passed = False
        
        # Extract models data
        if 'modelsCache' in content:
            import re
            match = re.search(r'const modelsCache = (\[.*?\]);', content, re.DOTALL)
            if match:
                import json
                try:
                    models_data = json.loads(match.group(1))
                    print(f"\n   ✓ Found {len(models_data)} models in modelsCache:")
                    for model in models_data:
                        print(f"      - {model.get('canonical_slug', 'N/A')} ({model.get('model_name', 'N/A')})")
                except json.JSONDecodeError as e:
                    print(f"\n   ✗ Failed to parse modelsCache JSON: {e}")
        
        # Extract apps data
        if 'appsCache' in content:
            match = re.search(r'const appsCache = (\{.*?\});', content, re.DOTALL)
            if match:
                try:
                    apps_data = json.loads(match.group(1))
                    print(f"\n   ✓ Found apps data for {len(apps_data)} models:")
                    for slug, app_nums in apps_data.items():
                        print(f"      - {slug}: {app_nums}")
                except json.JSONDecodeError as e:
                    print(f"\n   ✗ Failed to parse appsCache JSON: {e}")
        
        print("\n" + "=" * 80)
        if all_passed and 'modelsCache' in content:
            print("✅ SUCCESS: Modal should work correctly!")
        else:
            print("⚠️  WARNING: Some checks failed")
        print("=" * 80)
        
    else:
        print(f"   ✗ Failed to fetch: {reports_response.status_code}")
        print(f"   Response: {reports_response.text[:500]}")

if __name__ == '__main__':
    try:
        test_reports_new()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to Flask app")
        print("   Make sure Flask is running: python src/main.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
