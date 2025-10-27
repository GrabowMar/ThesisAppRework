"""
Complete Parallel Execution Test Suite
Tests API, UI (BeautifulSoup), and CLI methods for creating analysis tasks
Verifies parallel execution and tool result consistency
"""
import sys
import os
import time
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Prevent Flask debug mode from auto-starting
os.environ['WERKZEUG_RUN_MAIN'] = 'true'
os.environ['FLASK_DEBUG'] = '0'

# Add src to path
project_root = Path(__file__).parent.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(src_dir))

import requests
from bs4 import BeautifulSoup

# Configuration
BASE_URL = "http://localhost:5000"
DB_PATH = project_root / 'src' / 'data' / 'thesis_app.db'
TEST_MODEL = "openai_codex-mini"
TEST_APP = 1

# Results tracking
test_results = {
    'api': None,
    'ui': None,
    'cli': None
}

def print_header(text):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {text}")
    print(f"{'='*80}\n")

def print_success(text):
    """Print success message"""
    print(f"✅ {text}")

def print_error(text):
    """Print error message"""
    print(f"❌ {text}")

def print_info(text):
    """Print info message"""
    print(f"ℹ️  {text}")

def get_auth_token():
    """Get API token from .env file"""
    env_path = project_root / '.env'
    if not env_path.exists():
        print_error("No .env file found")
        return None
    
    with open(env_path) as f:
        for line in f:
            if line.startswith('API_KEY_FOR_APP='):
                token = line.split('=', 1)[1].strip()
                print_success(f"Found API token: {token[:20]}...")
                return token
    
    print_error("API_KEY_FOR_APP not found in .env")
    return None

def check_celery_workers():
    """Check if Celery workers are running"""
    print_header("Checking Celery Workers")
    
    try:
        from app.tasks import celery
        inspect = celery.control.inspect()
        workers = inspect.active_queues() or {}
        
        if workers:
            print_success(f"Found {len(workers)} active Celery worker(s)")
            for worker_name in workers.keys():
                print(f"  - {worker_name}")
            return True
        else:
            print_error("No Celery workers found!")
            print("Start workers with: celery -A app.tasks worker --loglevel=info")
            return False
    except Exception as e:
        print_error(f"Failed to check Celery workers: {e}")
        return False

def check_analyzer_containers():
    """Check if analyzer containers are healthy"""
    print_header("Checking Analyzer Containers")
    
    services = ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer']
    ports = [2001, 2002, 2003, 2004]
    
    all_healthy = True
    for service, port in zip(services, ports):
        try:
            resp = requests.get(f"http://localhost:{port}/health", timeout=2)
            if resp.status_code == 200:
                print_success(f"{service:20s} - Healthy (port {port})")
            else:
                print_error(f"{service:20s} - Unhealthy (status {resp.status_code})")
                all_healthy = False
        except Exception as e:
            print_error(f"{service:20s} - Unreachable ({e})")
            all_healthy = False
    
    return all_healthy

def test_api_method():
    """Test task creation via API endpoint"""
    print_header("TEST 1: API Method (POST /api/analysis/run)")
    
    token = get_auth_token()
    if not token:
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
    
    print_info(f"Creating task via API: {TEST_MODEL} app{TEST_APP}")
    
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
            print_success(f"Task created: {task_id}")
            print(f"  Status: {data.get('status')}")
            print(f"  Response: {json.dumps(data, indent=2)}")
            return task_id
        else:
            print_error(f"API request failed: {resp.status_code}")
            print(f"  Response: {resp.text}")
            return None
            
    except Exception as e:
        print_error(f"API request exception: {e}")
        return None

def test_ui_method():
    """Test task creation via UI form submission"""
    print_header("TEST 2: UI Method (POST /analysis/create)")
    
    # First, get a session cookie by logging in
    session = requests.Session()
    
    # Check if we need to login
    resp = session.get(f"{BASE_URL}/analysis/create")
    if 'login' in resp.url.lower():
        print_info("Need to login first")
        
        # Get credentials from env
        env_path = project_root / '.env'
        username = None
        password = None
        
        with open(env_path) as f:
            for line in f:
                if line.startswith('ADMIN_USERNAME='):
                    username = line.split('=', 1)[1].strip()
                elif line.startswith('ADMIN_PASSWORD='):
                    password = line.split('=', 1)[1].strip()
        
        if not username or not password:
            print_error("ADMIN_USERNAME or ADMIN_PASSWORD not in .env")
            return None
        
        # Login
        login_data = {
            'username': username,
            'password': password
        }
        
        login_resp = session.post(f"{BASE_URL}/auth/login", data=login_data)
        if login_resp.status_code != 200 or 'login' in login_resp.url.lower():
            print_error("Login failed")
            return None
        
        print_success("Logged in successfully")
    
    # Now submit the analysis creation form
    print_info(f"Submitting form: {TEST_MODEL} app{TEST_APP}")
    
    form_data = {
        'model_slug': TEST_MODEL,
        'app_number': str(TEST_APP),
        'analysis_mode': 'profile',
        'analysis_profile': 'security'
    }
    
    try:
        resp = session.post(
            f"{BASE_URL}/analysis/create",
            data=form_data,
            allow_redirects=True
        )
        
        if resp.status_code == 200:
            # Parse response to find task ID
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Look for success message or redirect to task list
            if 'analysis/list' in resp.url or 'success' in resp.text.lower():
                # Get the most recent task from database
                conn = sqlite3.connect(str(DB_PATH))
                cur = conn.cursor()
                
                recent_task = cur.execute("""
                    SELECT task_id, created_at 
                    FROM analysis_tasks 
                    WHERE target_model=? AND target_app_number=?
                    AND is_main_task=1
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (TEST_MODEL, TEST_APP)).fetchone()
                
                conn.close()
                
                if recent_task:
                    task_id = recent_task[0]
                    print_success(f"Task created via UI: {task_id}")
                    return task_id
                else:
                    print_error("Task created but not found in database")
                    return None
            else:
                print_error("Form submission did not succeed")
                print(f"  URL: {resp.url}")
                return None
                
        else:
            print_error(f"Form submission failed: {resp.status_code}")
            return None
            
    except Exception as e:
        print_error(f"UI submission exception: {e}")
        return None

def test_cli_method():
    """Test task creation via CLI (direct service call)"""
    print_header("TEST 3: CLI Method (Direct Service)")
    
    print_info(f"Creating task via service layer: {TEST_MODEL} app{TEST_APP}")
    
    try:
        from app.factory import create_app
        from app.services.task_service import AnalysisTaskService
        from app.extensions import db
        
        app = create_app()
        app.config['TESTING'] = False
        
        with app.app_context():
            # Get all tools by service
            from app.engines.unified_registry import get_unified_tool_registry
            registry = get_unified_tool_registry()
            
            all_tools = registry.list_tools_detailed()
            
            # Group by service
            tools_by_service = {
                'static-analyzer': [],
                'dynamic-analyzer': [],
                'performance-tester': [],
                'ai-analyzer': []
            }
            
            for tool in all_tools:
                tool_id = tool.get('id')
                tool_service = tool.get('service_name')  # Try different key
                
                if not tool_service:
                    # Infer from tool name
                    tool_name = tool.get('name', '').lower()
                    if any(t in tool_name for t in ['bandit', 'safety', 'pylint', 'flake8', 'eslint']):
                        tool_service = 'static-analyzer'
                    elif any(t in tool_name for t in ['zap', 'nmap', 'connectivity']):
                        tool_service = 'dynamic-analyzer'
                    elif any(t in tool_name for t in ['ab', 'locust', 'aiohttp', 'benchmark']):
                        tool_service = 'performance-tester'
                    elif any(t in tool_name for t in ['requirements', 'code-review', 'ai']):
                        tool_service = 'ai-analyzer'
                
                if tool_service and tool_service in tools_by_service:
                    tools_by_service[tool_service].append(tool_id)
            
            print(f"  Tools grouped by service:")
            for svc, tool_ids in tools_by_service.items():
                print(f"    {svc}: {len(tool_ids)} tools")
            
            # Create main task with subtasks
            task = AnalysisTaskService.create_main_task_with_subtasks(
                model_slug=TEST_MODEL,
                app_number=TEST_APP,
                analysis_type='security',
                tools_by_service=tools_by_service,
                task_name=f'CLI Test: {TEST_MODEL} app{TEST_APP}'
            )
            
            db.session.commit()
            
            task_id = task.task_id
            print_success(f"Task created via CLI: {task_id}")
            return task_id
            
    except Exception as e:
        print_error(f"CLI creation exception: {e}")
        import traceback
        traceback.print_exc()
        return None

def monitor_task_execution(task_id, timeout=600):
    """Monitor task execution until completion"""
    print_header(f"Monitoring Task: {task_id}")
    
    start_time = time.time()
    last_status = None
    
    while time.time() - start_time < timeout:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        
        # Get main task status
        main_task = cur.execute("""
            SELECT status, completed_steps, total_steps, error_message
            FROM analysis_tasks
            WHERE task_id=?
        """, (task_id,)).fetchone()
        
        if not main_task:
            conn.close()
            print_error(f"Task {task_id} not found")
            return None
        
        status, completed, total, error = main_task
        
        # Get subtask statuses
        subtasks = cur.execute("""
            SELECT service_name, status, error_message
            FROM analysis_tasks
            WHERE parent_task_id=?
            ORDER BY service_name
        """, (task_id,)).fetchall()
        
        conn.close()
        
        # Print status if changed
        current_status = f"{status}:{completed}/{total}"
        if current_status != last_status:
            print(f"[{int(time.time() - start_time)}s] Main Task: {status} ({completed}/{total} steps)")
            
            for svc, st_status, st_error in subtasks:
                error_msg = f" - {st_error[:50]}" if st_error else ""
                print(f"  └─ {svc:20s}: {st_status}{error_msg}")
            
            last_status = current_status
        
        # Check if completed or failed
        if status in ('COMPLETED', 'FAILED'):
            print()
            if status == 'COMPLETED':
                print_success(f"Task completed in {int(time.time() - start_time)}s")
            else:
                print_error(f"Task failed: {error}")
            
            return {
                'status': status,
                'duration': int(time.time() - start_time),
                'subtasks': subtasks
            }
        
        time.sleep(2)
    
    print_error(f"Task monitoring timed out after {timeout}s")
    return None

def analyze_task_results(task_id):
    """Analyze task results and verify tool execution"""
    print_header(f"Analyzing Results: {task_id}")
    
    # Find result file
    results_dir = project_root / 'results' / TEST_MODEL.replace('/', '_') / f'app{TEST_APP}'
    
    if not results_dir.exists():
        print_error(f"Results directory not found: {results_dir}")
        return None
    
    # Find the task's result file
    task_files = list(results_dir.glob(f'**/task*{task_id}*/*.json'))
    
    if not task_files:
        print_error(f"No result files found for task {task_id}")
        return None
    
    # Read the main result file (not manifest)
    result_file = None
    for f in task_files:
        if 'manifest' not in f.name:
            result_file = f
            break
    
    if not result_file:
        print_error("Could not find main result file")
        return None
    
    print_info(f"Reading result file: {result_file.name}")
    
    with open(result_file) as f:
        results = json.load(f)
    
    # Analyze results
    summary = results.get('summary', {})
    tools = results.get('tools', {})
    services = results.get('services', {})
    findings = results.get('findings', [])
    
    print(f"\n📊 Summary:")
    print(f"  Total Findings: {summary.get('total_findings', 0)}")
    print(f"  Services Executed: {summary.get('services_executed', 0)}")
    print(f"  Tools Executed: {summary.get('tools_executed', 0)}")
    print(f"  Tools Failed: {len(summary.get('tools_failed', []))}")
    
    print(f"\n🔧 Tool Results ({len(tools)} tools):")
    tools_ok = 0
    tools_failed = 0
    
    for tool_name, tool_data in sorted(tools.items()):
        status = tool_data.get('status', 'unknown')
        executed = tool_data.get('executed', False)
        
        if status in ('success', 'completed') and executed:
            print(f"  ✅ {tool_name:25s} - {status}")
            tools_ok += 1
        else:
            error = tool_data.get('error', 'N/A')
            print(f"  ❌ {tool_name:25s} - {status} ({error[:40]})")
            tools_failed += 1
    
    print(f"\n📦 Service Results ({len(services)} services):")
    for service_name in sorted(services.keys()):
        service_data = services[service_name]
        service_tools = service_data.get('tool_results', {})
        print(f"  {service_name}: {len(service_tools)} tools executed")
    
    # Check for parallel execution indicators
    metadata = results.get('metadata', {})
    print(f"\n⚡ Execution Metadata:")
    print(f"  Unified Analysis: {metadata.get('unified_analysis', False)}")
    print(f"  Orchestrator Version: {metadata.get('orchestrator_version', 'unknown')}")
    print(f"  Schema Version: {metadata.get('schema_version', 'unknown')}")
    
    return {
        'total_findings': summary.get('total_findings', 0),
        'tools_executed': len(tools),
        'tools_ok': tools_ok,
        'tools_failed': tools_failed,
        'services': len(services),
        'result_file': str(result_file)
    }

def compare_results():
    """Compare results from all three methods"""
    print_header("Comparing Results Across Methods")
    
    if not any(test_results.values()):
        print_error("No test results to compare")
        return
    
    print("\n📊 Results Summary:")
    print(f"{'Method':<10} {'Task ID':<25} {'Tools OK':<10} {'Tools Failed':<12} {'Findings':<10}")
    print("-" * 80)
    
    for method, result in test_results.items():
        if result:
            task_id = result.get('task_id', 'N/A')
            analysis = result.get('analysis', {})
            print(f"{method.upper():<10} {task_id[:24]:<25} {analysis.get('tools_ok', 0):<10} "
                  f"{analysis.get('tools_failed', 0):<12} {analysis.get('total_findings', 0):<10}")
        else:
            print(f"{method.upper():<10} {'FAILED':<25} {'-':<10} {'-':<12} {'-':<10}")
    
    # Check consistency
    print("\n🔍 Consistency Check:")
    
    successful_results = [r for r in test_results.values() if r and r.get('analysis')]
    
    if len(successful_results) < 2:
        print_info("Not enough successful tests to compare")
        return
    
    # Compare tool counts
    tool_counts = [r['analysis']['tools_executed'] for r in successful_results]
    if len(set(tool_counts)) == 1:
        print_success(f"All methods executed same number of tools: {tool_counts[0]}")
    else:
        print_error(f"Tool count mismatch: {tool_counts}")
    
    # Compare success rates
    success_counts = [r['analysis']['tools_ok'] for r in successful_results]
    if len(set(success_counts)) == 1:
        print_success(f"All methods had same tool success count: {success_counts[0]}")
    else:
        print_error(f"Tool success mismatch: {success_counts}")

def main():
    """Main test execution"""
    print_header("🚀 Parallel Execution Complete Test Suite")
    print(f"Testing Model: {TEST_MODEL}")
    print(f"Testing App: {TEST_APP}")
    print(f"Base URL: {BASE_URL}")
    
    # Pre-flight checks
    if not check_celery_workers():
        print_error("\n⚠️  WARNING: Celery workers not running!")
        print("   Parallel execution requires Celery workers.")
        print("   Start with: celery -A app.tasks worker --loglevel=info")
        sys.exit(1)
    
    if not check_analyzer_containers():
        print_error("\n⚠️  WARNING: Some analyzer containers are unhealthy!")
        print("   Start containers with: python analyzer/analyzer_manager.py start")
        sys.exit(1)
    
    print_success("\n✅ All pre-flight checks passed!")
    
    # Run tests
    tests = [
        ('api', test_api_method),
        ('ui', test_ui_method),
        ('cli', test_cli_method)
    ]
    
    for method_name, test_func in tests:
        task_id = test_func()
        
        if task_id:
            # Monitor execution
            execution_result = monitor_task_execution(task_id)
            
            if execution_result and execution_result['status'] == 'COMPLETED':
                # Analyze results
                analysis_result = analyze_task_results(task_id)
                
                test_results[method_name] = {
                    'task_id': task_id,
                    'execution': execution_result,
                    'analysis': analysis_result
                }
            else:
                test_results[method_name] = {
                    'task_id': task_id,
                    'execution': execution_result,
                    'analysis': None
                }
        
        # Wait between tests
        if method_name != 'cli':
            print_info("\nWaiting 5s before next test...")
            time.sleep(5)
    
    # Compare results
    compare_results()
    
    # Final summary
    print_header("🎯 Test Suite Complete")
    
    successful_tests = sum(1 for r in test_results.values() if r and r.get('analysis'))
    print(f"Tests Passed: {successful_tests}/3")
    
    if successful_tests == 3:
        print_success("✅ ALL TESTS PASSED!")
        sys.exit(0)
    elif successful_tests > 0:
        print_info(f"⚠️  PARTIAL SUCCESS: {successful_tests}/3 tests passed")
        sys.exit(1)
    else:
        print_error("❌ ALL TESTS FAILED!")
        sys.exit(1)

if __name__ == '__main__':
    main()
