"""
Simplified Parallel Execution Test
Tests API and monitors execution without importing Flask
"""
import sys
import time
import json
import sqlite3
import requests
from pathlib import Path

# Configuration
project_root = Path(__file__).parent.parent
DB_PATH = project_root / 'src' / 'data' / 'thesis_app.db'
BASE_URL = "http://localhost:5000"
TEST_MODEL = "openai_codex-mini"
TEST_APP = 1

def get_token():
    """Get API token from .env"""
    env_path = project_root / '.env'
    with open(env_path) as f:
        for line in f:
            if line.startswith('API_KEY_FOR_APP='):
                return line.split('=', 1)[1].strip()
    return None

def create_task_via_api():
    """Create analysis task via API"""
    print("\n" + "="*80)
    print("  Creating Analysis Task via API")
    print("="*80 + "\n")
    
    token = get_token()
    if not token:
        print("❌ No API token found in .env")
        return None
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model_slug': TEST_MODEL,
        'app_number': TEST_APP,
        'analysis_type': 'security'
    }
    
    print(f"📝 Request: POST /api/analysis/run")
    print(f"   Model: {TEST_MODEL}")
    print(f"   App: {TEST_APP}")
    print(f"   Type: security\n")
    
    try:
        resp = requests.post(
            f"{BASE_URL}/api/analysis/run",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if resp.status_code == 200:
            data = resp.json()
            task_id = data.get('task_id')
            print(f"✅ Task created: {task_id}")
            print(f"   Status: {data.get('status')}")
            return task_id
        else:
            print(f"❌ API request failed: {resp.status_code}")
            print(f"   Response: {resp.text}")
            return None
    except Exception as e:
        print(f"❌ Exception: {e}")
        return None

def monitor_task(task_id, timeout=300):
    """Monitor task execution"""
    print("\n" + "="*80)
    print(f"  Monitoring Task: {task_id}")
    print("="*80 + "\n")
    
    start_time = time.time()
    last_status = None
    parallel_detected = False
    
    while time.time() - start_time < timeout:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        
        # Get main task
        main_task = cur.execute("""
            SELECT status, completed_steps, total_steps, error_message
            FROM analysis_tasks
            WHERE task_id=?
        """, (task_id,)).fetchone()
        
        if not main_task:
            conn.close()
            print(f"❌ Task {task_id} not found")
            return None
        
        status, completed, total, error = main_task
        
        # Get subtasks
        subtasks = cur.execute("""
            SELECT service_name, status, error_message
            FROM analysis_tasks
            WHERE parent_task_id=?
            ORDER BY service_name
        """, (task_id,)).fetchall()
        
        conn.close()
        
        # Check for parallel execution
        running_count = sum(1 for _, st, _ in subtasks if st == 'RUNNING')
        if running_count >= 2:
            parallel_detected = True
        
        # Print status if changed
        current_status = f"{status}:{completed}/{total}:{running_count}"
        if current_status != last_status:
            elapsed = int(time.time() - start_time)
            print(f"[{elapsed:3d}s] Main Task: {status:12s} ({completed}/{total} steps)")
            
            for svc, st_status, st_error in subtasks:
                error_msg = f" - {st_error[:40]}" if st_error else ""
                status_icon = "⚡" if st_status == "RUNNING" else ("✅" if st_status == "COMPLETED" else "❌")
                print(f"       {status_icon} {svc:20s}: {st_status:12s}{error_msg}")
            
            if running_count >= 2:
                print(f"       🚀 PARALLEL EXECUTION DETECTED! {running_count} services running simultaneously")
            
            print()
            last_status = current_status
        
        # Check if done
        if status in ('COMPLETED', 'FAILED'):
            elapsed = int(time.time() - start_time)
            
            if status == 'COMPLETED':
                print(f"✅ Task completed in {elapsed}s")
            else:
                print(f"❌ Task failed: {error}")
            
            if parallel_detected:
                print(f"🚀 Parallel execution was detected during task execution!")
            else:
                print(f"⚠️  WARNING: No parallel execution detected - tasks may have run sequentially")
            
            return {
                'status': status,
                'duration': elapsed,
                'parallel': parallel_detected,
                'subtasks': subtasks
            }
        
        time.sleep(2)
    
    print(f"❌ Monitoring timed out after {timeout}s")
    return None

def analyze_results(task_id):
    """Analyze task results"""
    print("\n" + "="*80)
    print(f"  Analyzing Results: {task_id}")
    print("="*80 + "\n")
    
    # Find result file
    results_dir = project_root / 'results' / TEST_MODEL.replace('/', '_') / f'app{TEST_APP}'
    
    task_dirs = list(results_dir.glob(f'**/task*{task_id[:12]}*'))
    
    if not task_dirs:
        print(f"❌ No results found for task {task_id}")
        return None
    
    task_dir = task_dirs[0]
    result_files = [f for f in task_dir.glob('*.json') if 'manifest' not in f.name]
    
    if not result_files:
        print(f"❌ No result JSON found in {task_dir}")
        return None
    
    result_file = result_files[0]
    print(f"📄 Reading: {result_file.name}\n")
    
    with open(result_file) as f:
        results = json.load(f)
    
    summary = results.get('summary', {})
    tools = results.get('tools', {})
    services = results.get('services', {})
    
    print(f"📊 Summary:")
    print(f"   Total Findings: {summary.get('total_findings', 0)}")
    print(f"   Services Executed: {summary.get('services_executed', 0)}")
    print(f"   Tools Executed: {summary.get('tools_executed', 0)}")
    print(f"   Tools Failed: {len(summary.get('tools_failed', []))}\n")
    
    print(f"🔧 Tool Results ({len(tools)} tools):")
    tools_ok = 0
    tools_failed = 0
    
    for tool_name, tool_data in sorted(tools.items()):
        status = tool_data.get('status', 'unknown')
        executed = tool_data.get('executed', False)
        
        if status in ('success', 'completed') and executed:
            print(f"   ✅ {tool_name:25s} - {status}")
            tools_ok += 1
        else:
            error = tool_data.get('error', 'N/A')[:30]
            print(f"   ❌ {tool_name:25s} - {status} ({error})")
            tools_failed += 1
    
    print(f"\n📦 Services:")
    for service_name, service_data in sorted(services.items()):
        service_tools = service_data.get('tool_results', {})
        print(f"   {service_name}: {len(service_tools)} tools")
    
    return {
        'tools_ok': tools_ok,
        'tools_failed': tools_failed,
        'total_findings': summary.get('total_findings', 0)
    }

def main():
    """Main test execution"""
    print("\n" + "="*80)
    print("  🚀 PARALLEL EXECUTION TEST")
    print("="*80)
    print(f"\n   Model: {TEST_MODEL}")
    print(f"   App: {TEST_APP}")
    print(f"   URL: {BASE_URL}\n")
    
    # Create task
    task_id = create_task_via_api()
    if not task_id:
        print("\n❌ FAILED: Could not create task")
        sys.exit(1)
    
    # Monitor execution
    execution = monitor_task(task_id)
    if not execution:
        print("\n❌ FAILED: Monitoring failed")
        sys.exit(1)
    
    if execution['status'] != 'COMPLETED':
        print(f"\n❌ FAILED: Task status is {execution['status']}")
        sys.exit(1)
    
    # Analyze results
    analysis = analyze_results(task_id)
    if not analysis:
        print("\n❌ FAILED: Could not analyze results")
        sys.exit(1)
    
    # Final verdict
    print("\n" + "="*80)
    print("  🎯 TEST RESULTS")
    print("="*80 + "\n")
    
    print(f"   Task ID: {task_id}")
    print(f"   Duration: {execution['duration']}s")
    print(f"   Parallel Execution: {'✅ YES' if execution['parallel'] else '❌ NO'}")
    print(f"   Tools Successful: {analysis['tools_ok']}")
    print(f"   Tools Failed: {analysis['tools_failed']}")
    print(f"   Total Findings: {analysis['total_findings']}")
    
    if execution['parallel'] and analysis['tools_ok'] > 0:
        print("\n✅ TEST PASSED! Parallel execution working correctly.")
        sys.exit(0)
    elif not execution['parallel']:
        print("\n⚠️  TEST WARNING: No parallel execution detected (may have used sequential fallback)")
        sys.exit(1)
    else:
        print("\n❌ TEST FAILED: Tools did not execute successfully")
        sys.exit(1)

if __name__ == '__main__':
    main()
