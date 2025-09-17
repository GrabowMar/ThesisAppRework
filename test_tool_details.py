#!/usr/bin/env python3
"""
Test script to verify the enhanced tool details functionality.
This script tests the new tool details endpoint and template.
"""

import json
import requests
import sys
from pathlib import Path

def test_tool_details_enhancement():
    """Test the enhanced tool details display functionality."""
    base_url = "http://127.0.0.1:5000"
    task_id = None  # Initialize task_id
    
    print("🔧 Testing Enhanced Tool Details Functionality")
    print("=" * 60)
    
    # Test 1: Check if new endpoint exists
    print("\n1. Testing new tool details endpoint...")
    try:
        # Get list of tasks first
        tasks_response = requests.get(f"{base_url}/analysis/api/tasks/inspect/list", timeout=10)
        if tasks_response.status_code == 200:
            # Parse HTML to find task IDs
            content = tasks_response.text
            if 'href="/analysis/tasks/' in content:
                # Extract first task ID from HTML
                import re
                task_match = re.search(r'href="/analysis/tasks/([^"]+)"', content)
                if task_match:
                    task_id = task_match.group(1)
                    print(f"   ✅ Found task for testing: {task_id}")
                    
                    # Test new tool details endpoint
                    tools_url = f"{base_url}/analysis/api/tasks/{task_id}/results/tools"
                    tools_response = requests.get(tools_url, timeout=10)
                    
                    if tools_response.status_code == 200:
                        print(f"   ✅ Tool details endpoint working (status: {tools_response.status_code})")
                        
                        # Check if response contains expected content
                        content = tools_response.text
                        if "Tool Execution Details" in content:
                            print("   ✅ Tool details template loaded successfully")
                            if "tools executed" in content:
                                print("   ✅ Tool execution count displayed")
                            if "Analysis Duration" in content:
                                print("   ✅ Analysis timing information included")
                        else:
                            print("   ⚠️  Tool details template content may be incomplete")
                    else:
                        print(f"   ❌ Tool details endpoint failed (status: {tools_response.status_code})")
                        print(f"       Response: {tools_response.text[:200]}...")
                    
                    # Test original results endpoint for comparison
                    results_url = f"{base_url}/analysis/api/tasks/{task_id}/results/summary"
                    results_response = requests.get(results_url, timeout=10)
                    
                    if results_response.status_code == 200:
                        print("   ✅ Original results endpoint still working")
                    else:
                        print(f"   ⚠️  Original results endpoint issue (status: {results_response.status_code})")
                else:
                    print("   ❌ No task IDs found in HTML response")
            else:
                print("   ❌ No task links found in response")
        else:
            print(f"   ❌ Cannot access tasks list (status: {tasks_response.status_code})")
            print(f"       Response: {tasks_response.text[:200]}...")
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")
        return False
    
    # Test 2: Check if task detail page includes new section
    print("\n2. Testing task detail page integration...")
    try:
        if 'task_id' in locals():
            detail_url = f"{base_url}/analysis/tasks/{task_id}"
            detail_response = requests.get(detail_url, timeout=10)
            
            if detail_response.status_code == 200:
                content = detail_response.text
                if 'hx-get="/analysis/api/tasks/' in content and '/results/tools"' in content:
                    print("   ✅ Task detail page includes new tool details section")
                else:
                    print("   ⚠️  Task detail page may not include tool details section")
            else:
                print(f"   ❌ Cannot access task detail page (status: {detail_response.status_code})")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Task detail page error: {e}")
    
    # Test 3: Verify enhanced analysis inspection service
    print("\n3. Testing enhanced analysis inspection service...")
    try:
        if 'task_id' in locals():
            # Test the JSON payload endpoint
            json_url = f"{base_url}/analysis/api/tasks/{task_id}/results.json"
            json_response = requests.get(json_url, timeout=10)
            
            if json_response.status_code == 200:
                try:
                    payload = json_response.json()
                    
                    # Check for enhanced metadata
                    if 'tool_metrics' in payload:
                        tool_metrics = payload['tool_metrics']
                        print(f"   ✅ Tool metrics available for {len(tool_metrics)} tools")
                        
                        # Check for specific tool details
                        for tool_name, metrics in tool_metrics.items():
                            if 'status' in metrics and 'total_issues' in metrics:
                                print(f"       📊 {tool_name}: {metrics.get('status')} - {metrics.get('total_issues')} issues")
                    else:
                        print("   ⚠️  Tool metrics not found in payload")
                    
                    # Check for analysis duration
                    metadata = payload.get('metadata', {})
                    if 'analysis_duration' in metadata:
                        duration = metadata['analysis_duration']
                        print(f"   ✅ Analysis duration included: {duration}s")
                    else:
                        print("   ⚠️  Analysis duration not found in metadata")
                        
                except json.JSONDecodeError:
                    print("   ❌ Invalid JSON response")
            else:
                print(f"   ❌ Cannot access JSON payload (status: {json_response.status_code})")
                
    except requests.exceptions.RequestException as e:
        print(f"   ❌ JSON payload error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Enhanced tool details functionality test completed!")
    print("\nIf you see mostly ✅ symbols above, the enhancement is working.")
    print("If you see ⚠️ or ❌ symbols, there may be issues to investigate.")
    
    return True

if __name__ == "__main__":
    test_tool_details_enhancement()