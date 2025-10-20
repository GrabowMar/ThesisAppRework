"""
Quick Browser Test Script

Opens the dashboard in the default browser with mock data
to validate the complete system integration.
"""

import webbrowser
import time
from pathlib import Path

def main():
    print("=" * 60)
    print("DASHBOARD BROWSER TEST")
    print("=" * 60)
    print()
    
    # Check if Flask is running
    print("📋 Prerequisites:")
    print("   1. Flask server must be running on port 5000")
    print("   2. Database initialized with test task")
    print("   3. Mock results.json generated")
    print()
    
    input("Press Enter when Flask server is ready (python src/main.py)...")
    
    # Mock data path
    mock_file = Path("results/test/mock_comprehensive_results.json")
    if not mock_file.exists():
        print(f"❌ Mock data not found: {mock_file}")
        print("   Run: python scripts/generate_mock_results.py results/test/mock_comprehensive_results.json")
        return 1
    
    print(f"✅ Mock data found: {mock_file}")
    print()
    
    # Dashboard URL
    url = "http://localhost:5000/analysis/dashboard/app/test_model/1"
    
    print("🌐 Opening dashboard in browser...")
    print(f"   URL: {url}")
    print()
    
    webbrowser.open(url)
    
    print("=" * 60)
    print("TESTING CHECKLIST")
    print("=" * 60)
    print()
    print("Visual Testing:")
    print("  [ ] All 7 tabs visible (Overview, Security, Performance, Quality, AI Requirements, Tools, Raw Data)")
    print("  [ ] Summary cards show correct values")
    print("  [ ] Tables populated with findings")
    print("  [ ] Badges have correct colors")
    print()
    print("Tab Testing:")
    print("  [ ] Click each tab - content switches correctly")
    print("  [ ] Overview: Shows severity breakdown, category distribution, top issues")
    print("  [ ] Security: Shows security findings with severity filter")
    print("  [ ] Performance: Shows performance findings")
    print("  [ ] Quality: Shows quality findings with tool filter")
    print("  [ ] AI Requirements: Shows placeholder or data")
    print("  [ ] Tools: Shows all 18 tools with status badges")
    print("  [ ] Raw Data: HTMX loads data or shows loading")
    print()
    print("Filtering Testing:")
    print("  [ ] Security severity filter works")
    print("  [ ] Quality tool filter works")
    print("  [ ] Raw Data filters work (category, severity, tool)")
    print("  [ ] Counts update when filters change")
    print()
    print("Interaction Testing:")
    print("  [ ] Click finding row - modal opens")
    print("  [ ] Modal shows complete finding details")
    print("  [ ] Modal close button works")
    print("  [ ] Click outside modal - modal closes")
    print()
    print("Data Accuracy:")
    print("  [ ] Total findings: 30")
    print("  [ ] High severity: 10 (1 critical + 9 high)")
    print("  [ ] Tools executed: 18/18")
    print("  [ ] Tools status: 0 failed, 0 skipped")
    print("  [ ] Security findings: 11")
    print("  [ ] Quality findings: 13")
    print("  [ ] Performance findings: 6")
    print()
    print("Console Testing:")
    print("  [ ] Open browser console (F12)")
    print("  [ ] No JavaScript errors")
    print("  [ ] No network errors (200 OK for all requests)")
    print("  [ ] Data loaded successfully message")
    print()
    print("=" * 60)
    print("Press Ctrl+C to exit test mode")
    print("=" * 60)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\\n\\n✅ Test session ended")
        return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
