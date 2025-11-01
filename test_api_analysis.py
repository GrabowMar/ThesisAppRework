#!/usr/bin/env python3
"""
API Analysis Test
=================

Tests the web app API analysis endpoint to ensure parity with CLI analyzer.
"""

import asyncio
import json
import requests
import time
from pathlib import Path

API_BASE = "http://localhost:5000/api"
API_TOKEN = "rVeT8CcWIfqPLeGFJcO1FHKYx3vvXVJbjrnCHeoGbB0at6cJwWmMks4baFn9AT2w"

def test_api_analysis():
    """Test API analysis endpoint."""
    print("=" * 80)
    print("API ANALYSIS TEST")
    print("=" * 80)
    print()
    print("Testing model: anthropic_claude-4.5-haiku-20251001 app 1")
    print()
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # First test token verification
    print("[1/5] Verifying API token...")
    verify_response = requests.get(f"{API_BASE}/tokens/verify", headers=headers)
    if verify_response.status_code == 200:
        print("[OK] Token verified")
    else:
        print(f"[X] Token verification failed: {verify_response.status_code}")
        return None
    
    # Start analysis
    print("[2/5] Starting comprehensive analysis via API...")
    payload = {
        "model_slug": "anthropic_claude-4.5-haiku-20251001",
        "app_number": 1,
        "analysis_type": "comprehensive"
    }
    
    response = requests.post(f"{API_BASE}/analysis/run", headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"[X] Analysis request failed: {response.status_code}")
        print("Response:", response.text)
        try:
            error_data = response.json()
            print("Error details:", json.dumps(error_data, indent=2))
        except:
            pass
        return None
    
    result = response.json()
    task_id = result.get('task_id')
    print(f"[OK] Analysis started with task ID: {task_id}")
    
    # Poll for completion
    print("[3/5] Waiting for analysis completion...")
    max_wait = 600  # 10 minutes
    start_time = time.time()
    
    while time.time() - start_time < max_wait:
        status_response = requests.get(f"{API_BASE}/analysis/task/{task_id}/status", headers=headers)
        if status_response.status_code == 200:
            status_data = status_response.json()
            status = status_data.get('status')
            print(f"Status: {status}")
            
            if status in ['completed', 'failed']:
                break
        
        time.sleep(10)  # Poll every 10 seconds
    
    # Get final results
    print("[4/5] Retrieving results...")
    results_response = requests.get(f"{API_BASE}/analysis/task/{task_id}/results", headers=headers)
    
    if results_response.status_code != 200:
        print(f"[X] Failed to get results: {results_response.status_code}")
        return None
    
    api_results = results_response.json()
    
    # Analyze results
    print("[5/5] Analyzing API results...")
    
    # Extract key metrics
    services_executed = 0
    tools_successful = 0
    total_findings = 0
    
    # Check for services in results
    if 'services' in api_results:
        for service_name, service_data in api_results['services'].items():
            if service_data.get('status') == 'success':
                services_executed += 1
    
    # Check for tools
    if 'tools' in api_results:
        tools_successful = len([t for t in api_results['tools'].values() 
                               if t.get('status') in ['success', 'no_issues']])
    
    # Check for findings
    if 'findings' in api_results:
        total_findings = len(api_results['findings'])
    elif 'summary' in api_results:
        total_findings = api_results['summary'].get('total_findings', 0)
    
    print()
    print("=" * 80)
    print("API ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Task ID: {task_id}")
    print(f"Status: {api_results.get('status', 'unknown')}")
    print(f"Services: {services_executed} executed")
    print(f"Tools: {tools_successful} successful")
    print(f"Findings: {total_findings} total")
    print()
    
    return api_results

if __name__ == '__main__':
    try:
        result = test_api_analysis()
        exit_code = 0 if result and result.get('status') == 'completed' else 1
        exit(exit_code)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)