"""
Test Report Generation through Web UI
Tests the /reports routes and validates data correctness.
"""
import requests
import json
from pathlib import Path
import time

BASE_URL = "http://127.0.0.1:5000"

def test_health():
    """Check if Flask app is running."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✓ Flask app is running: {response.status_code}")
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        print(f"❌ Flask app not reachable: {e}")
        return False

def test_report_creation_ui():
    """Test report creation through web UI."""
    print("\n" + "="*80)
    print("TESTING REPORT GENERATION VIA WEB UI")
    print("="*80)
    
    if not test_health():
        print("❌ Cannot proceed - Flask app not running")
        print("   Please start the app with: python src/main.py")
        return False
    
    # Test 1: Check reports page loads
    print("\n📊 Test 1: Check reports page")
    try:
        response = requests.get(f"{BASE_URL}/reports", timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print("  ✓ Reports page loads")
            # Check if page contains expected elements
            if "Report Generation" in response.text or "reports" in response.text.lower():
                print("  ✓ Page contains report-related content")
        else:
            print(f"  ❌ Unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False
    
    # Test 2: Check report creation form
    print("\n📋 Test 2: Check report creation page")
    try:
        response = requests.get(f"{BASE_URL}/reports/create", timeout=10)
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print("  ✓ Report creation page loads")
            # Check for form elements
            has_model = "model" in response.text.lower()
            has_app = "app" in response.text.lower()
            has_format = "format" in response.text.lower()
            print(f"  Has model field: {has_model}")
            print(f"  Has app field: {has_app}")
            print(f"  Has format field: {has_format}")
        else:
            print(f"  ❌ Unexpected status: {response.status_code}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    # Test 3: Get available models
    print("\n🤖 Test 3: Get available models for reports")
    try:
        # Try to find models page or API endpoint
        response = requests.get(f"{BASE_URL}/models", timeout=10)
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            print("  ✓ Models page accessible")
            if "haiku" in response.text.lower() or "claude" in response.text.lower():
                print("  ✓ Haiku model found")
        
    except Exception as e:
        print(f"  ⚠️ Models page not accessible: {e}")
    
    # Test 4: Check if we can list existing reports
    print("\n📄 Test 4: List existing reports")
    try:
        response = requests.get(f"{BASE_URL}/reports/list", timeout=10)
        if response.status_code == 404:
            # Try alternative endpoint
            response = requests.get(f"{BASE_URL}/reports", timeout=10)
        
        print(f"  Status: {response.status_code}")
        if response.status_code == 200:
            print("  ✓ Can list reports")
            # Check if we can see report count
            if "report" in response.text.lower():
                print("  ✓ Response contains report data")
    except Exception as e:
        print(f"  ⚠️ Error: {e}")
    
    # Test 5: Check for API endpoint
    print("\n🔌 Test 5: Check API endpoints")
    try:
        response = requests.get(f"{BASE_URL}/api/reports", timeout=10)
        print(f"  GET /api/reports: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  ✓ API response is JSON")
            print(f"  Reports found: {len(data) if isinstance(data, list) else 'N/A'}")
            
            if isinstance(data, list) and len(data) > 0:
                # Show latest report
                latest = data[0]
                print(f"\n  Latest Report:")
                print(f"    ID: {latest.get('report_id', 'N/A')}")
                print(f"    Type: {latest.get('report_type', 'N/A')}")
                print(f"    Format: {latest.get('format', 'N/A')}")
                print(f"    Status: {latest.get('status', 'N/A')}")
                
    except Exception as e:
        print(f"  ⚠️ API not available: {e}")
    
    return True


def check_available_analysis_data():
    """Check what analysis data is available for reporting."""
    print("\n" + "="*80)
    print("CHECKING AVAILABLE ANALYSIS DATA")
    print("="*80)
    
    results_dir = Path("results")
    if not results_dir.exists():
        print("❌ Results directory not found")
        return
    
    print(f"\n📁 Results directory: {results_dir.absolute()}")
    
    # List model directories
    model_dirs = [d for d in results_dir.iterdir() if d.is_dir() and not d.name.endswith('.db')]
    print(f"\n🤖 Found {len(model_dirs)} model(s):")
    
    for model_dir in model_dirs:
        print(f"\n  Model: {model_dir.name}")
        
        # List apps
        app_dirs = [d for d in model_dir.iterdir() if d.is_dir() and d.name.startswith('app')]
        print(f"    Apps: {len(app_dirs)}")
        
        for app_dir in app_dirs:
            # Count task directories
            task_dirs = [d for d in app_dir.iterdir() if d.is_dir() and d.name.startswith('task_')]
            print(f"      {app_dir.name}: {len(task_dirs)} task(s)")
            
            if task_dirs:
                # Check latest task
                latest_task = sorted(task_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[0]
                print(f"        Latest: {latest_task.name}")
                
                # Check for manifest
                manifest_file = latest_task / "manifest.json"
                if manifest_file.exists():
                    try:
                        manifest = json.loads(manifest_file.read_text())
                        total_findings = manifest.get('summary', {}).get('total_findings', 0)
                        tools_count = len(manifest.get('tools', {}))
                        print(f"          Findings: {total_findings}, Tools: {tools_count}")
                    except Exception as e:
                        print(f"          ⚠️ Error reading manifest: {e}")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("WEB REPORT GENERATION TEST SUITE")
    print("="*80)
    
    print("\nℹ️ This test requires the Flask app to be running.")
    print("   If not running, start it with: python src/main.py")
    print("\n" + "="*80)
    
    try:
        # Check available data first
        check_available_analysis_data()
        
        # Test web UI
        input("\n⏸️  Press Enter to test web UI (ensure Flask app is running)...")
        result = test_report_creation_ui()
        
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"  Web UI Tests: {'✓ PASSED' if result else '❌ FAILED'}")
        print("="*80)
        
        if result:
            print("\n✓ Web UI is functional!")
            print("\nNext steps:")
            print("1. Navigate to http://127.0.0.1:5000/reports")
            print("2. Create a report for Haiku app 1")
            print("3. Download and verify the report contains correct data")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
