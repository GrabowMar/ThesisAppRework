#!/usr/bin/env python3
"""
Test Frontend Integration with CLI Analysis System
==================================================
Tests the API endpoints and frontend integration for the CLI analysis system.
"""

import requests
import json
from pathlib import Path
import sys
import time

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_api_endpoints():
    """Test the new API endpoints for CLI analysis."""
    base_url = "http://127.0.0.1:5000"
    
    print("🧪 Testing Frontend Integration with CLI Analysis System")
    print("=" * 60)
    
    # Test model: anthropic_claude-3.7-sonnet, app: 1
    model = "anthropic_claude-3.7-sonnet"
    app_num = 1
    
    print(f"📋 Test Target: {model}/app{app_num}")
    
    # Test 1: Check if main app analysis page loads
    print("\n🌐 Testing Main Analysis Page...")
    try:
        response = requests.get(f"{base_url}/app/{model}/{app_num}/analysis", timeout=10)
        if response.status_code == 200:
            print("✅ Analysis page loads successfully")
            # Check if our new form elements are present
            if 'use_all_tools' in response.text and 'include_quality' in response.text:
                print("✅ New tool selection form elements present")
            else:
                print("⚠️ New form elements missing")
        else:
            print(f"❌ Analysis page failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Analysis page request failed: {e}")
    
    # Test 2: Test getting existing analysis results
    print("\n📊 Testing Analysis Results API...")
    try:
        response = requests.get(f"{base_url}/api/analysis/{model}/{app_num}/results", timeout=10)
        if response.status_code == 200:
            print("✅ Results API responds successfully")
            if 'analysis-category' in response.text or 'No Analysis Results' in response.text:
                print("✅ Results format is correct")
            else:
                print("⚠️ Unexpected results format")
        else:
            print(f"❌ Results API failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Results API request failed: {e}")
    
    # Test 3: Test export functionality
    print("\n📁 Testing Export API...")
    try:
        response = requests.get(f"{base_url}/api/analysis/{model}/{app_num}/export", timeout=10)
        if response.status_code == 200:
            print("✅ Export API responds successfully")
            try:
                export_data = response.json()
                if 'model' in export_data and 'results' in export_data:
                    print("✅ Export data structure is correct")
                    print(f"📊 Export contains {export_data.get('total_issues', 0)} issues")
                else:
                    print("⚠️ Export data structure unexpected")
            except json.JSONDecodeError:
                print("⚠️ Export response is not valid JSON")
        elif response.status_code == 404:
            print("ℹ️ No analysis results to export (expected if no analysis run yet)")
        else:
            print(f"❌ Export API failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Export API request failed: {e}")
    
    # Test 4: Test CLI analysis endpoint (POST)
    print("\n🔧 Testing CLI Analysis API...")
    try:
        # Prepare form data for a quick analysis
        form_data = {
            'bandit': 'on',
            'safety': 'on',
            'eslint': 'on'
        }
        
        response = requests.post(
            f"{base_url}/api/analysis/{model}/{app_num}/security",
            data=form_data,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ CLI Analysis API responds successfully")
            if 'CLI Analysis Completed' in response.text or 'CLI Analysis Failed' in response.text:
                print("✅ Analysis response format is correct")
                if 'total issues' in response.text.lower():
                    print("✅ Analysis contains issue counts")
            else:
                print("⚠️ Unexpected analysis response format")
        else:
            print(f"❌ CLI Analysis API failed: {response.status_code}")
            if response.text:
                print(f"Response: {response.text[:200]}...")
    except requests.exceptions.RequestException as e:
        print(f"❌ CLI Analysis API request failed: {e}")
    
    # Test 5: Test tests page
    print("\n🧪 Testing Tests Page...")
    try:
        response = requests.get(f"{base_url}/app/{model}/{app_num}/tests", timeout=10)
        if response.status_code == 200:
            print("✅ Tests page loads successfully")
            if 'CLI Security Analysis' in response.text and 'Use All Tools' in response.text:
                print("✅ Updated test page content present")
            else:
                print("⚠️ Test page content not updated")
        else:
            print(f"❌ Tests page failed: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Tests page request failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Frontend Integration Test Complete!")
    print("\n💡 Next Steps:")
    print("1. Open http://127.0.0.1:5000 in your browser")
    print(f"2. Navigate to: /app/{model}/{app_num}/analysis")
    print("3. Test the CLI analysis form with tool selection")
    print("4. Check the results display and export functionality")


if __name__ == "__main__":
    # Wait a moment for the server to fully start
    print("⏳ Waiting for server to start...")
    time.sleep(2)
    
    test_api_endpoints()
