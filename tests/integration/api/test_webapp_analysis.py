#!/usr/bin/env python3
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.api]

"""Test analysis via web app API."""
import requests
import time
import json
from pathlib import Path

# Flask app base URL
BASE_URL = "http://localhost:5000"

def test_web_app_analysis():
    """Trigger analysis via web app and monitor results."""
    
    # Test 1: Check Flask is running
    print("=" * 60)
    print("TEST 1: Health Check")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        print(f"✅ Flask is running: {response.status_code}")
        if response.status_code == 200:
            print(f"   Response: {response.json()}")
        else:
            print(f"   Text: {response.text[:200]}")
    except Exception as e:
        print(f"❌ Flask not reachable: {e}")
        return
    
    # Test 2: Check analyzer services status via API
    print("\n" + "=" * 60)
    print("TEST 2: Analyzer Services Status")
    print("=" * 60)
    try:
        response = requests.get(f"{BASE_URL}/api/analyzer/status", timeout=10)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            status = response.json()
            print(f"✅ Services running: {status.get('running', 'unknown')}")
            print(f"   Details: {json.dumps(status.get('services', {}), indent=2)}")
    except Exception as e:
        print(f"⚠️ Could not get analyzer status: {e}")
    
    # Test 3: Trigger analysis via POST /api/app/{model}/{app}/analyze
    print("\n" + "=" * 60)
    print("TEST 3: Trigger Analysis via API")
    print("=" * 60)
    
    model_slug = "openai_gpt-4.1-2025-04-14"
    app_number = 3
    
    payload = {
        "analysis_types": ["static", "security"],  # Shorter test
        "wait_for_completion": False  # Don't block
    }
    
    print(f"Triggering analysis for {model_slug} app {app_number}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/app/{model_slug}/{app_number}/analyze",
            json=payload,
            timeout=30
        )
        print(f"Response status: {response.status_code}")
        result = response.json()
        print(f"Response body: {json.dumps(result, indent=2)}")
        
        if response.status_code in [200, 201, 202]:
            task_id = result.get('task_id')
            print(f"\n✅ Analysis task created: {task_id}")
            
            # Test 4: Monitor task status
            print("\n" + "=" * 60)
            print("TEST 4: Monitor Task Status")
            print("=" * 60)
            
            if task_id:
                for i in range(20):  # Poll for up to ~100 seconds
                    time.sleep(5)
                    try:
                        status_response = requests.get(
                            f"{BASE_URL}/api/tasks/{task_id}/status",
                            timeout=5
                        )
                        if status_response.status_code == 200:
                            status_data = status_response.json()
                            current_status = status_data.get('status', 'unknown')
                            progress = status_data.get('progress_percentage', 0)
                            print(f"[{i*5}s] Status: {current_status} | Progress: {progress}%")
                            
                            if current_status in ['completed', 'failed', 'error']:
                                print(f"\n✅ Task finished with status: {current_status}")
                                break
                    except Exception as e:
                        print(f"⚠️ Status check failed: {e}")
                        break
                else:
                    print("\n⏱️ Timeout waiting for task completion")
                
                # Test 5: Check filesystem results
                print("\n" + "=" * 60)
                print("TEST 5: Verify Filesystem Results")
                print("=" * 60)
                
                results_base = Path(f"results/{model_slug}/app{app_number}")
                if results_base.exists():
                    # Find most recent task directory
                    task_dirs = [d for d in results_base.iterdir() if d.is_dir() and d.name.startswith('task_')]
                    if task_dirs:
                        latest_task = max(task_dirs, key=lambda d: d.stat().st_mtime)
                        print(f"✅ Found task directory: {latest_task}")
                        
                        # Check for consolidated JSON
                        json_files = list(latest_task.glob("*.json"))
                        if json_files:
                            latest_json = max(json_files, key=lambda f: f.stat().st_mtime)
                            print(f"✅ Found results JSON: {latest_json.name}")
                            
                            # Load and check structure
                            with open(latest_json) as f:
                                results_data = json.load(f)
                            
                            tools = results_data.get('results', {}).get('tools', {})
                            findings = results_data.get('results', {}).get('findings', [])
                            services = results_data.get('results', {}).get('services', {})
                            
                            print(f"\n📊 Results Summary:")
                            print(f"   Total tools: {len(tools)}")
                            print(f"   Total findings: {len(findings)}")
                            print(f"   Services: {list(services.keys())}")
                            
                            # Check SARIF tools
                            sarif_tools = ['bandit', 'pylint', 'semgrep', 'mypy', 'eslint', 'ruff']
                            present_sarif_tools = [t for t in sarif_tools if t in tools]
                            print(f"\n🔍 SARIF Tools Present: {present_sarif_tools}")
                            
                            for tool_name in present_sarif_tools:
                                tool_data = tools[tool_name]
                                status = tool_data.get('status', 'unknown')
                                issues = tool_data.get('total_issues', 0)
                                executed = tool_data.get('executed', False)
                                print(f"   ✅ {tool_name}: {status} (executed: {executed}, issues: {issues})")
                            
                            print("\n🎉 WEB APP ANALYSIS TEST COMPLETED SUCCESSFULLY!")
                        else:
                            print("❌ No JSON files found in task directory")
                    else:
                        print("❌ No task directories found")
                else:
                    print(f"❌ Results directory not found: {results_base}")
        else:
            print(f"❌ Failed to create analysis task: {result}")
            
    except Exception as e:
        print(f"❌ Analysis request failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_web_app_analysis()
