#!/usr/bin/env python3
"""
Test Enhanced Results System

This script validates the enhanced results API and JavaScript functionality.
"""

import requests
import json
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_enhanced_results_api():
    """Test the enhanced results API endpoints."""
    
    print("🔍 Testing Enhanced Results API...")
    
    base_url = "http://localhost:5000/api"
    
    tests = [
        {
            'name': 'Enhanced Results Endpoint',
            'url': f'{base_url}/testing/results/enhanced',
            'expected_keys': ['success', 'results', 'pagination']
        },
        {
            'name': 'Statistics Endpoint', 
            'url': f'{base_url}/testing/results/statistics',
            'expected_keys': ['success', 'statistics']
        }
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            print(f"  Testing {test['name']}...")
            response = requests.get(test['url'], timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if all expected keys are present
                missing_keys = [key for key in test['expected_keys'] if key not in data]
                
                if not missing_keys:
                    print(f"    ✅ {test['name']} - PASSED")
                    passed += 1
                else:
                    print(f"    ❌ {test['name']} - FAILED (missing keys: {missing_keys})")
            else:
                print(f"    ❌ {test['name']} - FAILED (status: {response.status_code})")
                print(f"       Response: {response.text[:200]}")
                
        except requests.exceptions.RequestException as e:
            print(f"    ❌ {test['name']} - FAILED (connection error: {e})")
        except json.JSONDecodeError as e:
            print(f"    ❌ {test['name']} - FAILED (invalid JSON: {e})")
        except Exception as e:
            print(f"    ❌ {test['name']} - FAILED (error: {e})")
    
    print(f"\n📊 API Tests: {passed}/{total} passed")
    return passed == total

def test_javascript_syntax():
    """Test JavaScript syntax and basic structure."""
    
    print("\n🔍 Testing JavaScript Syntax...")
    
    js_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'static', 'js', 'enhanced-results.js')
    
    if not os.path.exists(js_file):
        print(f"    ❌ JavaScript file not found: {js_file}")
        return False
    
    try:
        with open(js_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Basic syntax checks
        checks = [
            ('EnhancedResultsManager class', 'class EnhancedResultsManager' in content),
            ('loadComparisonData method', 'loadComparisonData()' in content),
            ('renderComparisonView method', 'renderComparisonView(' in content),
            ('Chart.js integration', 'new Chart(' in content),
            ('Export functions', 'exportComparisonReport' in content),
            ('Proper function declarations', 'function ' in content)
        ]
        
        passed = 0
        for check_name, condition in checks:
            if condition:
                print(f"    ✅ {check_name} - PASSED")
                passed += 1
            else:
                print(f"    ❌ {check_name} - FAILED")
        
        print(f"\n📊 JavaScript Tests: {passed}/{len(checks)} passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"    ❌ Error reading JavaScript file: {e}")
        return False

def test_html_template():
    """Test HTML template structure."""
    
    print("\n🔍 Testing HTML Template...")
    
    template_file = os.path.join(os.path.dirname(__file__), '..', 'src', 'templates', 'partials', 'testing', 'enhanced_results.html')
    
    if not os.path.exists(template_file):
        print(f"    ❌ Template file not found: {template_file}")
        return False
    
    try:
        with open(template_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Template structure checks
        checks = [
            ('Results table', 'resultsTable' in content),
            ('Chart containers', 'Chart' in content),
            ('Filter controls', 'Filter' in content),
            ('Modal dialogs', 'modal' in content),
            ('Comparison features', 'comparison' in content),
            ('Bootstrap classes', 'card' in content and 'btn' in content)
        ]
        
        passed = 0
        for check_name, condition in checks:
            if condition:
                print(f"    ✅ {check_name} - PASSED")
                passed += 1
            else:
                print(f"    ❌ {check_name} - FAILED")
        
        print(f"\n📊 Template Tests: {passed}/{len(checks)} passed")
        return passed == len(checks)
        
    except Exception as e:
        print(f"    ❌ Error reading template file: {e}")
        return False

def main():
    """Run all enhanced results tests."""
    
    print("🚀 Enhanced Results System Validation")
    print("=" * 50)
    
    results = []
    
    # Test API functionality
    api_result = test_enhanced_results_api()
    results.append(('Enhanced Results API', api_result))
    
    # Test JavaScript
    js_result = test_javascript_syntax()
    results.append(('JavaScript Implementation', js_result))
    
    # Test HTML template
    html_result = test_html_template()
    results.append(('HTML Template', html_result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 VALIDATION SUMMARY")
    print("=" * 50)
    
    total_passed = 0
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name:30} {status}")
        if passed:
            total_passed += 1
    
    print("-" * 50)
    print(f"Overall: {total_passed}/{len(results)} components validated")
    
    if total_passed == len(results):
        print("\n🎉 All enhanced results components validated successfully!")
        return 0
    else:
        print(f"\n⚠️  {len(results) - total_passed} components need attention")
        return 1

if __name__ == '__main__':
    sys.exit(main())
