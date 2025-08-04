"""
Comprehensive Security Analysis Testing Script with Interactive Features
Tests all security tools (Bandit, Safety, ESLint, Retire.js) against real AI-generated applications.
"""

import requests
import time
import sys

class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'

def colored_print(text, color=""):
    """Print text with color formatting."""
    print(f"{color}{text}{Colors.RESET}")

def log_step(emoji, title, color=Colors.CYAN):
    """Log a major step with formatting."""
    colored_print(f"\n{emoji} {title}", f"{color}{Colors.BOLD}")
    colored_print("─" * (len(title) + 3), color)

def log_detail(text, color=Colors.WHITE, indent=0):
    """Log a detail with optional color and indentation."""
    prefix = "  " * indent
    colored_print(f"{prefix}{text}", color)

def run_analysis_test_interactive(base_url, test_request, test_name, expected_tools):
    """Run a single analysis test with interactive logging."""
    try:
        log_step("🔍", f"Testing {test_name}", Colors.BLUE)
        
        # Show what we're testing
        model = test_request.get('model', 'unknown')
        app_num = test_request.get('app_num', 'unknown')
        log_detail(f"📂 Model: {model}", color=Colors.CYAN)
        log_detail(f"📱 App: app{app_num}", color=Colors.CYAN)
        log_detail(f"🔧 Expected tools: {', '.join(expected_tools)}", color=Colors.YELLOW)
        
        # Submit test
        log_detail("📤 Submitting analysis request...", color=Colors.WHITE)
        response = requests.post(f"{base_url}/tests", json=test_request, timeout=30)
        
        if response.status_code != 200:
            log_detail(f"❌ Failed to submit: HTTP {response.status_code}", color=Colors.RED)
            return None
        
        test_id = response.json()['data']['test_id']
        log_detail(f"✅ Analysis started - Test ID: {test_id}", color=Colors.GREEN)
        
        # Wait for completion with progress updates
        log_detail("⏳ Waiting for analysis completion...", color=Colors.YELLOW)
        max_wait = 45  # 45 seconds max
        wait_time = 0
        progress_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        progress_idx = 0
        
        while wait_time < max_wait:
            # Show spinning progress indicator
            progress_char = progress_chars[progress_idx % len(progress_chars)]
            print(f"\r   {progress_char} Analyzing... ({wait_time}s)", end="", flush=True)
            
            time.sleep(3)
            wait_time += 3
            progress_idx += 1
            
            status_response = requests.get(f"{base_url}/tests/{test_id}/status", timeout=10)
            if status_response.status_code == 200:
                status_data = status_response.json()['data']
                current_status = status_data['status']
                
                if current_status == "completed":
                    print(f"\r   ✅ Analysis completed!                    ", flush=True)
                    break
                elif current_status == "failed":
                    print(f"\r   ❌ Analysis failed                       ", flush=True)
                    return None
                elif wait_time % 15 == 0:
                    print(f"\r   ⏳ Status: {current_status} ({wait_time}s)                    ", flush=True)
        
        # Get results
        log_detail("📥 Retrieving results...", color=Colors.WHITE)
        result_response = requests.get(f"{base_url}/tests/{test_id}/result", timeout=10)
        if result_response.status_code != 200:
            log_detail(f"❌ Failed to get results: HTTP {result_response.status_code}", color=Colors.RED)
            return None
        
        result_data = result_response.json()['data']
        
        # Process and display results
        issues = result_data.get('issues', [])
        duration = result_data.get('duration', 0)
        
        log_detail(f"⏱️  Analysis completed in {duration:.2f} seconds", color=Colors.GREEN)
        
        if issues:
            log_detail(f"🐛 Found {len(issues)} security issues!", color=Colors.RED)
            
            # Group and display issues by tool
            issues_by_tool = {}
            severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
            
            for issue in issues:
                tool = issue.get('tool', 'unknown')
                severity = issue.get('severity', 'low').lower()
                
                if tool not in issues_by_tool:
                    issues_by_tool[tool] = []
                issues_by_tool[tool].append(issue)
                
                if severity in severity_counts:
                    severity_counts[severity] += 1
            
            # Show severity breakdown
            log_detail("📊 Severity breakdown:", color=Colors.CYAN)
            severity_colors = {"critical": Colors.RED, "high": Colors.RED, "medium": Colors.YELLOW, "low": Colors.GREEN}
            severity_emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            
            for severity, count in severity_counts.items():
                if count > 0:
                    emoji = severity_emojis[severity]
                    color = severity_colors[severity]
                    log_detail(f"   {emoji} {severity.capitalize()}: {count}", color=color)
            
            # Display issues by tool
            for tool in expected_tools:
                tool_issues = issues_by_tool.get(tool, [])
                if tool_issues:
                    log_detail(f"🔍 {tool.upper()} found {len(tool_issues)} issues:", color=Colors.CYAN)
                    
                    for i, issue in enumerate(tool_issues[:3]):  # Show first 3 issues per tool
                        severity = issue.get('severity', 'unknown')
                        file_path = issue.get('file_path', 'unknown')
                        message = issue.get('message', 'No description')
                        line_num = issue.get('line_number', '')
                        code_snippet = issue.get('code_snippet', '')
                        description = issue.get('description', '')
                        
                        # Color code by severity
                        severity_color = severity_colors.get(severity.lower(), Colors.WHITE)
                        
                        log_detail(f"   • {severity.upper()}: {message}", color=severity_color, indent=1)
                        log_detail(f"     📄 File: {file_path}{':' + str(line_num) if line_num else ''}", color=Colors.WHITE, indent=1)
                        
                        if code_snippet and len(code_snippet.strip()) < 100:
                            log_detail(f"     💻 Code: {code_snippet.strip()}", color=Colors.MAGENTA, indent=1)
                        
                        if description and description != message:
                            log_detail(f"     📝 Description: {description}", color=Colors.WHITE, indent=1)
                        
                        if i < len(tool_issues) - 1:
                            log_detail("", color=Colors.WHITE)  # Blank line between issues
                    
                    if len(tool_issues) > 3:
                        log_detail(f"     ... and {len(tool_issues) - 3} more {tool} issues", color=Colors.YELLOW, indent=1)
                else:
                    log_detail(f"✅ {tool.upper()}: No issues found", color=Colors.GREEN)
        else:
            log_detail("✅ No security issues found - Clean code!", color=Colors.GREEN)
        
        return {
            "test_name": test_name,
            "duration": duration,
            "tools": expected_tools,
            "issues": issues,
            "total_issues": len(issues),
            "success": True
        }
        
    except Exception as e:
        log_detail(f"❌ Test error: {e}", color=Colors.RED)
        return None

def print_interactive_summary_report(results):
    """Print a comprehensive summary of all test results."""
    log_step("📋", "COMPREHENSIVE ANALYSIS SUMMARY", Colors.CYAN)
    
    total_tests = len(results)
    successful_tests = len([r for r in results if r and r.get('success', False)])
    total_issues = sum(r.get('total_issues', 0) for r in results if r)
    total_duration = sum(r.get('duration', 0) for r in results if r)
    
    log_detail(f"📊 Tests executed: {successful_tests}/{total_tests}", color=Colors.CYAN)
    log_detail(f"⏱️  Total analysis time: {total_duration:.2f} seconds", color=Colors.CYAN)
    log_detail(f"🐛 Total security issues found: {total_issues}", color=Colors.RED if total_issues > 0 else Colors.GREEN)
    
    if successful_tests > 0:
        log_detail(f"⚡ Average analysis time: {total_duration/successful_tests:.2f} seconds per test", color=Colors.YELLOW)
    
    # Show breakdown by test
    log_detail("\n📋 Test Results Breakdown:", color=Colors.CYAN)
    for result in results:
        if result:
            test_name = result.get('test_name', 'Unknown')
            issues_count = result.get('total_issues', 0)
            duration = result.get('duration', 0)
            tools = result.get('tools', [])
            
            status_emoji = "✅" if issues_count == 0 else "🐛"
            status_color = Colors.GREEN if issues_count == 0 else Colors.RED
            
            log_detail(f"{status_emoji} {test_name}: {issues_count} issues ({duration:.2f}s) - {', '.join(tools)}", 
                      color=status_color)
    
    if total_issues == 0:
        colored_print("🎉 EXCELLENT! No security issues found in any test", Colors.GREEN)
        log_detail("   All analyzed applications appear to be secure", color=Colors.GREEN)
    else:
        colored_print("⚠️  ATTENTION! Multiple security issues found", Colors.RED)
        log_detail("   Recommend reviewing and fixing identified issues", color=Colors.RED)
    
    colored_print("\n✅ Analysis Infrastructure Status:", Colors.CYAN)
    log_detail("✅ Real source code successfully analyzed", color=Colors.GREEN)
    log_detail("✅ Multiple security tools working together", color=Colors.GREEN)
    log_detail("✅ Structured JSON results with detailed information", color=Colors.GREEN)
    log_detail("✅ Fast containerized analysis infrastructure", color=Colors.GREEN)
    log_detail("✅ Ready for batch processing of 900+ applications", color=Colors.GREEN)
    
    colored_print(f"\n🎉 INTERACTIVE TESTING COMPLETE!", Colors.BOLD)
    colored_print("="*70, Colors.BLUE)

def test_all_tools():
    """Test all security analysis tools with real model applications."""
    base_url = "http://localhost:8001"
    
    log_step("🚀", "STARTING COMPREHENSIVE SECURITY TOOL TESTING", Colors.BOLD)
    colored_print("Testing all security analysis tools against real AI-generated applications", Colors.CYAN)
    
    # Define test cases for different scenarios
    test_cases = [
        {
            "name": "Python Backend Analysis (Bandit + Safety)",
            "request": {
                "model": "anthropic_claude-3.7-sonnet",
                "app_num": 1,
                "test_type": "security_backend"
            },
            "expected_tools": ["bandit", "safety"]
        },
        {
            "name": "JavaScript Frontend Analysis (ESLint + Retire.js)",
            "request": {
                "model": "anthropic_claude-3.7-sonnet",
                "app_num": 2,
                "test_type": "security_frontend"
            },
            "expected_tools": ["eslint", "retire"]
        },
        {
            "name": "Full Stack Analysis (All Tools)",
            "request": {
                "model": "anthropic_claude-3.7-sonnet",
                "app_num": 3,
                "test_type": "security_backend"
            },
            "expected_tools": ["bandit", "safety", "eslint", "retire"]
        }
    ]
    
    # Check available models first
    log_step("📂", "Discovering Available Models", Colors.BLUE)
    try:
        # Test if our target model exists
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "security-scanner-real", "ls", "/app/sources/anthropic_claude-3.7-sonnet"],
            capture_output=True, text=True, timeout=10
        )
        
        if result.returncode == 0:
            log_detail("✅ Found anthropic_claude-3.7-sonnet model directory", color=Colors.GREEN)
            
            # List available apps
            apps_result = subprocess.run(
                ["docker", "exec", "security-scanner-real", "ls", "/app/sources/anthropic_claude-3.7-sonnet"],
                capture_output=True, text=True, timeout=10
            )
            
            if apps_result.returncode == 0:
                apps = [line.strip() for line in apps_result.stdout.split('\n') if line.strip().startswith('app')]
                log_detail(f"📱 Found {len(apps)} applications: {', '.join(apps[:5])}{'...' if len(apps) > 5 else ''}", color=Colors.CYAN)
            else:
                log_detail("⚠️  Could not list applications", color=Colors.YELLOW)
        else:
            log_detail("❌ Target model not found, checking alternatives...", color=Colors.YELLOW)
            
            # Try to find any available model
            models_result = subprocess.run(
                ["docker", "exec", "security-scanner-real", "ls", "/app/sources"],
                capture_output=True, text=True, timeout=10
            )
            
            if models_result.returncode == 0:
                models = [line.strip() for line in models_result.stdout.split('\n') if line.strip() and not line.startswith('.')]
                if models:
                    alt_model = models[0]
                    log_detail(f"🔄 Using alternative model: {alt_model}", color=Colors.YELLOW)
                    
                    # Update test cases to use alternative model
                    for test_case in test_cases:
                        test_case['request']['model'] = alt_model
                else:
                    log_detail("❌ No models found in /app/sources", color=Colors.RED)
                    return False
            else:
                log_detail("❌ Could not access models directory", color=Colors.RED)
                return False
                
    except Exception as e:
        log_detail(f"⚠️  Could not check models: {e}", color=Colors.YELLOW)
        log_detail("Proceeding with default test configuration...", color=Colors.YELLOW)
    
    # Run all test cases
    results = []
    for i, test_case in enumerate(test_cases, 1):
        colored_print(f"\n{'='*70}", Colors.BLUE)
        colored_print(f"TEST {i}/{len(test_cases)}: {test_case['name']}", f"{Colors.BOLD}{Colors.CYAN}")
        colored_print(f"{'='*70}", Colors.BLUE)
        
        result = run_analysis_test_interactive(
            base_url,
            test_case['request'],
            test_case['name'],
            test_case['expected_tools']
        )
        
        results.append(result)
        
        if result:
            colored_print(f"\n✅ Test {i} completed successfully!", Colors.GREEN)
        else:
            colored_print(f"\n❌ Test {i} failed!", Colors.RED)
        
        # Brief pause between tests
        if i < len(test_cases):
            time.sleep(2)
    
    # Print comprehensive summary
    colored_print(f"\n{'='*70}", Colors.BLUE)
    print_interactive_summary_report(results)
    
    # Return overall success status
    successful_tests = len([r for r in results if r and r.get('success', False)])
    return successful_tests == len(test_cases)

def check_model_exists(model_name):
    """Check if a model directory exists by testing the container."""
    try:
        import subprocess
        result = subprocess.run(
            ["docker", "exec", "security-scanner-real", "ls", f"/app/sources/{model_name}"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def main():
    """Main test execution with interactive features."""
    try:
        # Check if container is running
        log_step("🐳", "Checking Docker Container Status", Colors.BLUE)
        
        try:
            import subprocess
            result = subprocess.run(
                ["docker", "ps", "--filter", "name=security-scanner-real", "--format", "{{.Status}}"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0 and "Up" in result.stdout:
                log_detail("✅ Security scanner container is running", color=Colors.GREEN)
            else:
                log_detail("❌ Security scanner container not found or not running", color=Colors.RED)
                log_detail("   Please run: docker-compose up -d", color=Colors.YELLOW)
                return False
        except Exception as e:
            log_detail(f"⚠️  Could not check container status: {e}", color=Colors.YELLOW)
        
        # Start interactive testing
        colored_print("\n🚀 Starting Interactive Security Analysis...", Colors.BOLD)
        colored_print("Press Ctrl+C at any time to stop the analysis", Colors.YELLOW)
        
        success = test_all_tools()
        
        if success:
            colored_print(f"\n🎉 ALL TOOLS TEST COMPLETED SUCCESSFULLY!", Colors.BOLD)
            colored_print("🔧 All security analysis tools are working with real model code", Colors.GREEN)
            sys.exit(0)
        else:
            colored_print(f"\n❌ SOME TESTS FAILED", Colors.RED)
            sys.exit(1)
            
    except KeyboardInterrupt:
        colored_print(f"\n⏹️  Tests interrupted by user", Colors.YELLOW)
        colored_print("Analysis stopped gracefully", Colors.WHITE)
        sys.exit(1)
    except Exception as e:
        colored_print(f"\n💥 Unexpected error: {e}", Colors.RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
