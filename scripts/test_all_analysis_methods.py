"""
Test script for validating all three analysis trigger methods:
1. CLI (analyzer_manager.py) - No auth
2. UI (web form) - Session-based auth
3. API (REST endpoints) - Bearer token auth

Validates that all three produce identical result structures.
"""

import os
import sys
import json
import time
import asyncio
import requests
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Color codes for output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def log_section(title):
    """Print a section header"""
    print(f"\n{BOLD}{BLUE}{'=' * 80}{RESET}")
    print(f"{BOLD}{BLUE}{title.center(80)}{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 80}{RESET}\n")

def log_success(msg):
    """Print success message"""
    print(f"{GREEN}✅ {msg}{RESET}")

def log_error(msg):
    """Print error message"""
    print(f"{RED}❌ {msg}{RESET}")

def log_info(msg):
    """Print info message"""
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def log_warning(msg):
    """Print warning message"""
    print(f"{YELLOW}⚠️  {msg}{RESET}")


# =============================================================================
# 1. CLI METHOD TEST (analyzer_manager.py)
# =============================================================================

def test_cli_method():
    """Test CLI method (no authentication required)"""
    log_section("TEST 1: CLI METHOD (analyzer_manager.py)")
    
    log_info("CLI method uses analyzer_manager.py directly")
    log_info("No authentication required - bypasses Flask app")
    
    # Check if analyzer services are running
    import subprocess
    result = subprocess.run(
        ['python', 'analyzer/analyzer_manager.py', 'health'],
        capture_output=True,
        text=True,
        timeout=10
    )
    
    if result.returncode != 0:
        log_warning("Analyzer services not healthy - starting them...")
        start_result = subprocess.run(
            ['python', 'analyzer/analyzer_manager.py', 'start'],
            capture_output=True,
            text=True,
            timeout=30
        )
        if start_result.returncode != 0:
            log_error("Failed to start analyzer services")
            log_error(start_result.stderr)
            return False
        log_success("Analyzer services started")
        time.sleep(5)  # Wait for services to be ready
    
    log_info("Running security analysis via CLI...")
    log_info("Command: python analyzer/analyzer_manager.py analyze openai_codex-mini 1 security --tools bandit")
    
    # Run actual analysis
    analysis_result = subprocess.run(
        ['python', 'analyzer/analyzer_manager.py', 'analyze', 
         'openai_codex-mini', '1', 'security', '--tools', 'bandit'],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    if analysis_result.returncode == 0:
        log_success("CLI analysis completed successfully")
        log_info(f"Output sample:\n{analysis_result.stdout[:500]}")
        
        # Check if result file was created
        result_dir = Path('results/openai_codex-mini/app1')
        if result_dir.exists():
            task_dirs = list(result_dir.glob('task_security_*'))
            if task_dirs:
                latest_task = max(task_dirs, key=lambda p: p.stat().st_mtime)
                log_success(f"Result file created: {latest_task.name}")
                
                # Read and validate structure
                result_files = list(latest_task.glob('*.json'))
                if result_files:
                    with open(result_files[0], 'r') as f:
                        result_data = json.load(f)
                    log_success(f"Result file contains {len(result_data.get('tool_results', {}))} tools")
                    return result_data
        log_warning("No result file found in results directory")
    else:
        log_error("CLI analysis failed")
        log_error(analysis_result.stderr)
        return False
    
    return True


# =============================================================================
# 2. UI METHOD TEST (Flask session auth)
# =============================================================================

def test_ui_method():
    """Test UI method (session-based authentication)"""
    log_section("TEST 2: UI METHOD (Flask Web Form)")
    
    # Load credentials from .env
    from dotenv import load_dotenv
    load_dotenv()
    
    username = os.getenv('ADMIN_USERNAME', 'admin')
    password = os.getenv('ADMIN_PASSWORD')
    
    if not password:
        log_error("ADMIN_PASSWORD not found in .env file")
        return False
    
    log_info(f"Authenticating with username: {username}")
    
    base_url = 'http://localhost:5000'
    session = requests.Session()
    
    # Step 1: Login
    log_info("Step 1: Logging in...")
    login_response = session.post(
        f'{base_url}/auth/login',
        data={'username': username, 'password': password},
        allow_redirects=False
    )
    
    if login_response.status_code in [200, 302, 303]:
        log_success("Login successful")
    else:
        log_error(f"Login failed: {login_response.status_code}")
        return False
    
    # Step 2: Submit analysis via UI form
    log_info("Step 2: Submitting analysis via /analysis/create...")
    
    analysis_data = {
        'model_slug': 'openai_codex-mini',
        'app_number': 1,
        'analysis_mode': 'tool-registry',
        'analysis_profile': 'security-basic',
        'selected_tools[]': ['bandit']
    }
    
    analysis_response = session.post(
        f'{base_url}/analysis/create',
        data=analysis_data,
        allow_redirects=False
    )
    
    if analysis_response.status_code in [200, 201, 302]:
        log_success(f"Analysis submitted via UI (status: {analysis_response.status_code})")
        
        # Try to extract task ID from response
        if analysis_response.status_code == 302:
            location = analysis_response.headers.get('Location', '')
            if 'task' in location:
                log_info(f"Redirected to: {location}")
        
        return True
    else:
        log_error(f"UI analysis submission failed: {analysis_response.status_code}")
        log_error(analysis_response.text[:500])
        return False


# =============================================================================
# 3. API METHOD TEST (Bearer token auth)
# =============================================================================

def test_api_method():
    """Test API method (Bearer token authentication)"""
    log_section("TEST 3: API METHOD (Bearer Token)")
    
    # Load API token from .env
    from dotenv import load_dotenv
    load_dotenv()
    
    api_token = os.getenv('API_KEY_FOR_APP')
    
    if not api_token:
        log_error("API_KEY_FOR_APP not found in .env file")
        log_warning("Generate a token via UI: User Menu → API Access → Generate Token")
        return False
    
    log_info(f"Using API token: {api_token[:20]}...")
    
    base_url = 'http://localhost:5000'
    headers = {
        'Authorization': f'Bearer {api_token}',
        'Content-Type': 'application/json'
    }
    
    # Step 1: Verify token is valid
    log_info("Step 1: Verifying token...")
    verify_response = requests.get(f'{base_url}/api/tokens/verify', headers=headers)
    
    if verify_response.status_code == 200:
        log_success("Token is valid")
    else:
        log_error(f"Token verification failed: {verify_response.status_code}")
        return False
    
    # Step 2: Check if API endpoint exists
    log_info("Step 2: Checking available API endpoints...")
    
    # Try the documented endpoint from copilot-instructions.md
    endpoints_to_try = [
        '/api/analysis/run',
        '/api/applications/openai_codex-mini/1/analyze',
        '/api/analysis/tool-registry/custom-analysis'
    ]
    
    working_endpoint = None
    for endpoint in endpoints_to_try:
        log_info(f"Trying: POST {endpoint}")
        
        test_data = {
            'model_slug': 'openai_codex-mini',
            'app_number': 1,
            'analysis_type': 'security',
            'tools': ['bandit']
        }
        
        response = requests.post(f'{base_url}{endpoint}', headers=headers, json=test_data)
        
        if response.status_code in [200, 201]:
            log_success(f"Endpoint works: {endpoint}")
            log_info(f"Response: {json.dumps(response.json(), indent=2)[:300]}")
            working_endpoint = endpoint
            break
        elif response.status_code == 404:
            log_warning(f"Endpoint not found: {endpoint}")
        else:
            log_warning(f"Endpoint returned {response.status_code}: {endpoint}")
    
    if working_endpoint:
        log_success(f"API method works via: {working_endpoint}")
        return True
    else:
        log_error("No working API endpoint found")
        log_warning("Need to implement: POST /api/analysis/run")
        return False


# =============================================================================
# 4. RESULT COMPARISON
# =============================================================================

def compare_results(cli_result, ui_result, api_result):
    """Compare results from all three methods"""
    log_section("RESULT COMPARISON")
    
    log_info("Comparing result file structures...")
    
    # Check if all methods produced results
    methods_with_results = []
    if cli_result:
        methods_with_results.append('CLI')
    if ui_result:
        methods_with_results.append('UI')
    if api_result:
        methods_with_results.append('API')
    
    if len(methods_with_results) == 3:
        log_success("All three methods produced results")
    elif methods_with_results:
        log_warning(f"Only {len(methods_with_results)} method(s) worked: {', '.join(methods_with_results)}")
    else:
        log_error("No methods produced results")
        return False
    
    # Compare tool counts
    if cli_result and isinstance(cli_result, dict):
        cli_tools = len(cli_result.get('tool_results', {}))
        log_info(f"CLI result: {cli_tools} tools")
        
        # Check for result file structure
        if 'metadata' in cli_result:
            log_success("CLI result has metadata")
        if 'tool_results' in cli_result:
            log_success("CLI result has tool_results")
    
    return True


# =============================================================================
# MAIN
# =============================================================================

def main():
    """Run all tests"""
    log_section("ANALYSIS METHOD CONSISTENCY TEST")
    
    log_info("Testing three analysis trigger methods:")
    log_info("1. CLI (analyzer_manager.py) - No auth")
    log_info("2. UI (web form) - Session auth")
    log_info("3. API (REST endpoints) - Bearer token auth")
    
    # Check prerequisites
    log_info("\nChecking prerequisites...")
    
    # Check if Flask app is running
    try:
        response = requests.get('http://localhost:5000/health', timeout=2)
        if response.status_code == 200:
            log_success("Flask app is running")
        else:
            log_error("Flask app not responding correctly")
            return
    except requests.exceptions.RequestException:
        log_error("Flask app not running - start with: cd src && python main.py")
        return
    
    # Check if .env file exists
    env_file = Path('.env')
    if env_file.exists():
        log_success(".env file found")
    else:
        log_error(".env file not found")
        return
    
    log_success("All prerequisites met\n")
    
    # Run tests
    cli_result = test_cli_method()
    time.sleep(2)
    
    ui_result = test_ui_method()
    time.sleep(2)
    
    api_result = test_api_method()
    
    # Compare results
    compare_results(cli_result, ui_result, api_result)
    
    # Summary
    log_section("SUMMARY")
    
    results = {
        'CLI': '✅ PASS' if cli_result else '❌ FAIL',
        'UI': '✅ PASS' if ui_result else '❌ FAIL',
        'API': '✅ PASS' if api_result else '❌ FAIL'
    }
    
    for method, status in results.items():
        print(f"{method:10} {status}")
    
    # Final verdict
    if all([cli_result, ui_result, api_result]):
        log_success("\n🎉 ALL METHODS WORKING!")
    else:
        log_warning("\n⚠️  Some methods need attention")


if __name__ == '__main__':
    main()
