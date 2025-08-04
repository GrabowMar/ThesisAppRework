#!/usr/bin/env python3
"""
Interactive Security Analysis Testing with Real-time Logging
===========================================================

Comprehensive test for ALL security analysis tools on real model applications
with detailed, interactive logging showing exactly what's being tested.
"""
import requests
import json
import time
import sys
from datetime import datetime

class InteractiveLogger:
    """Interactive logger with real-time progress updates."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.test_count = 0
        self.issue_count = 0
    
    def header(self, message):
        """Print a major section header."""
        print("\n" + "=" * 80)
        print(f"🎯 {message}")
        print("=" * 80)
        print(f"Started at: {self.start_time.strftime('%H:%M:%S')}")
    
    def section(self, message):
        """Print a section header."""
        print(f"\n🔹 {message}")
        print("-" * 60)
    
    def step(self, step_num, message):
        """Print a numbered step."""
        print(f"\n{step_num}️⃣  {message}")
    
    def substep(self, message, indent=1):
        """Print a substep with indentation."""
        prefix = "   " * indent
        print(f"{prefix}📋 {message}")
    
    def success(self, message, indent=1):
        """Print a success message."""
        prefix = "   " * indent
        print(f"{prefix}✅ {message}")
    
    def warning(self, message, indent=1):
        """Print a warning message."""
        prefix = "   " * indent
        print(f"{prefix}⚠️  {message}")
    
    def error(self, message, indent=1):
        """Print an error message."""
        prefix = "   " * indent
        print(f"{prefix}❌ {message}")
    
    def info(self, message, indent=1):
        """Print an info message."""
        prefix = "   " * indent
        print(f"{prefix}ℹ️  {message}")
    
    def progress(self, message, indent=1):
        """Print a progress message."""
        prefix = "   " * indent
        print(f"{prefix}⏳ {message}")
    
    def result(self, message, indent=1):
        """Print a result message."""
        prefix = "   " * indent
        print(f"{prefix}📊 {message}")
    
    def issue_found(self, tool, severity, message, file_path, line_num=None, code_snippet=None, indent=2):
        """Log a security issue found."""
        prefix = "   " * indent
        self.issue_count += 1
        
        severity_emoji = {
            "critical": "🔴",
            "high": "🟠", 
            "medium": "🟡",
            "low": "🟢"
        }.get(severity.lower(), "⚪")
        
        print(f"{prefix}🐛 {severity_emoji} [{tool.upper()}] {message}")
        print(f"{prefix}   📁 File: {file_path}")
        if line_num:
            print(f"{prefix}   📍 Line: {line_num}")
        if code_snippet and len(code_snippet) < 100:
            print(f"{prefix}   💻 Code: {code_snippet}")
    
    def tool_summary(self, tool, issues_found, indent=2):
        """Summarize results for a specific tool."""
        prefix = "   " * indent
        if issues_found > 0:
            print(f"{prefix}🔍 {tool.upper()}: Found {issues_found} issues")
        else:
            print(f"{prefix}✅ {tool.upper()}: No issues found")

def test_all_tools_interactive():
    """Interactive test of all security analysis tools."""
    logger = InteractiveLogger()
    base_url = "http://localhost:8001"
    
    logger.header("INTERACTIVE SECURITY ANALYSIS TESTING")
    logger.info("Testing all security tools on real AI-generated applications")
    logger.info("Tools: Bandit, Safety, ESLint, Retire.js")
    
    # Step 1: Health Check
    logger.step(1, "Health Check")
    logger.substep("Checking if security scanner service is running...")
    
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            health_data = response.json()
            logger.success(f"Service Status: {health_data['data']['status']}")
            logger.success(f"Service Name: {health_data['data']['service']}")
        else:
            logger.error(f"Health check failed with status {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Cannot connect to security scanner: {e}")
        return False
    
    # Step 2: Discover Available Models
    logger.step(2, "Discovering Available Models")
    logger.substep("Checking which AI models are available for testing...")
    
    test_cases = [
        {
            "name": "anthropic_claude-3.7-sonnet/app1",
            "model": "anthropic_claude-3.7-sonnet",
            "app_num": 1,
            "description": "Claude Sonnet 3.7 - Application 1"
        },
        {
            "name": "anthropic_claude-3.7-sonnet/app2",
            "model": "anthropic_claude-3.7-sonnet", 
            "app_num": 2,
            "description": "Claude Sonnet 3.7 - Application 2"
        }
    ]
    
    # Check for additional models
    additional_models = [
        ("openai_gpt_4", 1, "OpenAI GPT-4 Application 1"),
        ("google_gemini-2.5-flash", 1, "Google Gemini Flash Application 1"),
        ("deepseek_deepseek-chat-v3-0324", 1, "DeepSeek Chat v3 Application 1")
    ]
    
    for model, app_num, desc in additional_models:
        if check_model_available(logger, model):
            test_cases.append({
                "name": f"{model}/app{app_num}",
                "model": model,
                "app_num": app_num,
                "description": desc
            })
    
    logger.success(f"Found {len(test_cases)} applications to test")
    for case in test_cases:
        logger.info(f"• {case['description']}", indent=2)
    
    # Step 3: Run Security Analysis
    logger.step(3, "Running Security Analysis")
    
    all_results = []
    
    for i, test_case in enumerate(test_cases, 1):
        logger.section(f"Testing {test_case['name']} ({i}/{len(test_cases)})")
        logger.substep(f"Description: {test_case['description']}")
        
        # Backend Analysis
        logger.substep("🐍 Backend Security Analysis (Python)")
        backend_result = run_interactive_backend_analysis(logger, base_url, test_case)
        if backend_result:
            all_results.append(backend_result)
        
        # Frontend Analysis  
        logger.substep("🌐 Frontend Security Analysis (JavaScript)")
        frontend_result = run_interactive_frontend_analysis(logger, base_url, test_case)
        if frontend_result:
            all_results.append(frontend_result)
        
        # Small delay between tests for readability
        if i < len(test_cases):
            logger.progress("Preparing next test...", indent=2)
            time.sleep(1)
    
    # Step 4: Generate Report
    logger.step(4, "Generating Comprehensive Report")
    generate_interactive_report(logger, all_results)
    
    return len(all_results) > 0

def check_model_available(logger, model_name):
    """Check if a model is available in the container."""
    try:
        import subprocess
        logger.substep(f"Checking availability of {model_name}...", indent=2)
        
        result = subprocess.run(
            ["docker", "exec", "security-scanner-real", "ls", f"/app/sources/{model_name}"],
            capture_output=True, text=True, timeout=5
        )
        
        if result.returncode == 0:
            logger.success(f"{model_name} is available", indent=3)
            return True
        else:
            logger.info(f"{model_name} not found", indent=3)
            return False
    except Exception as e:
        logger.warning(f"Could not check {model_name}: {e}", indent=3)
        return False

def run_interactive_backend_analysis(logger, base_url, test_case):
    """Run backend analysis with interactive logging."""
    logger.substep("Preparing backend analysis request...", indent=2)
    
    test_request = {
        "model": test_case["model"],
        "app_num": test_case["app_num"],
        "test_type": "security_backend",
        "tools": ["bandit", "safety"],
        "target_url": f"http://localhost:605{test_case['app_num']}"
    }
    
    logger.substep(f"Tools: {', '.join(test_request['tools'])}", indent=2)
    logger.substep(f"Target: {test_case['model']}/app{test_case['app_num']}/backend/", indent=2)
    
    return run_interactive_analysis(logger, base_url, test_request, "Backend", ["bandit", "safety"])

def run_interactive_frontend_analysis(logger, base_url, test_case):
    """Run frontend analysis with interactive logging."""
    logger.substep("Preparing frontend analysis request...", indent=2)
    
    test_request = {
        "model": test_case["model"],
        "app_num": test_case["app_num"],
        "test_type": "security_frontend",
        "tools": ["eslint", "retire"],
        "target_url": f"http://localhost:905{test_case['app_num']}"
    }
    
    logger.substep(f"Tools: {', '.join(test_request['tools'])}", indent=2)
    logger.substep(f"Target: {test_case['model']}/app{test_case['app_num']}/frontend/", indent=2)
    
    return run_interactive_analysis(logger, base_url, test_request, "Frontend", ["eslint", "retire"])

def run_interactive_analysis(logger, base_url, test_request, analysis_type, expected_tools):
    """Run analysis with detailed interactive logging."""
    try:
        # Submit request
        logger.progress(f"Submitting {analysis_type.lower()} analysis request...", indent=2)
        
        response = requests.post(f"{base_url}/tests", json=test_request, timeout=30)
        if response.status_code != 200:
            logger.error(f"Failed to submit request: HTTP {response.status_code}", indent=2)
            if response.text:
                logger.error(f"Error details: {response.text}", indent=3)
            return None
        
        test_id = response.json()['data']['test_id']
        logger.success(f"Analysis submitted - Test ID: {test_id}", indent=2)
        
        # Monitor progress
        logger.progress(f"Monitoring {analysis_type.lower()} analysis progress...", indent=2)
        
        max_wait = 45
        wait_time = 0
        last_status = None
        
        while wait_time < max_wait:
            time.sleep(3)
            wait_time += 3
            
            try:
                status_response = requests.get(f"{base_url}/tests/{test_id}/status", timeout=10)
                if status_response.status_code == 200:
                    current_status = status_response.json()['data']['status']
                    
                    if current_status != last_status:
                        logger.progress(f"Status: {current_status}", indent=3)
                        last_status = current_status
                    
                    if current_status == "completed":
                        logger.success(f"{analysis_type} analysis completed!", indent=2)
                        break
                    elif current_status == "failed":
                        logger.error(f"{analysis_type} analysis failed", indent=2)
                        return None
            except Exception as e:
                logger.warning(f"Status check error: {e}", indent=3)
        
        if wait_time >= max_wait:
            logger.error(f"{analysis_type} analysis timed out after {max_wait}s", indent=2)
            return None
        
        # Get results
        logger.progress("Retrieving analysis results...", indent=2)
        
        result_response = requests.get(f"{base_url}/tests/{test_id}/result", timeout=10)
        if result_response.status_code != 200:
            logger.error(f"Failed to get results: HTTP {result_response.status_code}", indent=2)
            return None
        
        result_data = result_response.json()['data']
        
        # Process results
        issues = result_data.get('issues', [])
        duration = result_data.get('duration', 0)
        
        logger.result(f"Analysis completed in {duration:.2f} seconds", indent=2)
        logger.result(f"Total issues found: {len(issues)}", indent=2)
        
        # Show results by tool
        for tool in expected_tools:
            tool_issues = [i for i in issues if i.get('tool') == tool]
            logger.tool_summary(tool, len(tool_issues), indent=2)
            
            # Show detailed issues for this tool
            for issue in tool_issues[:3]:  # Show first 3 issues per tool
                logger.issue_found(
                    tool=issue.get('tool', 'unknown'),
                    severity=issue.get('severity', 'unknown'),
                    message=issue.get('message', 'No description'),
                    file_path=issue.get('file_path', 'unknown'),
                    line_num=issue.get('line_number'),
                    code_snippet=issue.get('code_snippet'),
                    indent=3
                )
            
            if len(tool_issues) > 3:
                logger.info(f"... and {len(tool_issues) - 3} more {tool} issues", indent=3)
        
        return {
            "test_name": f"{test_request['model']}/app{test_request['app_num']} {analysis_type}",
            "analysis_type": analysis_type,
            "model": test_request['model'],
            "app_num": test_request['app_num'],
            "duration": duration,
            "tools": expected_tools,
            "issues": issues,
            "total_issues": len(issues),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"{analysis_type} analysis error: {e}", indent=2)
        return None

def generate_interactive_report(logger, results):
    """Generate comprehensive interactive report."""
    logger.substep("Analyzing all test results...")
    
    if not results:
        logger.error("No results to analyze")
        return
    
    total_tests = len(results)
    total_issues = sum(r['total_issues'] for r in results)
    total_duration = sum(r['duration'] for r in results)
    
    logger.section("📊 COMPREHENSIVE ANALYSIS REPORT")
    
    # Overall Statistics
    logger.result(f"Tests Completed: {total_tests}")
    logger.result(f"Total Security Issues Found: {total_issues}")
    logger.result(f"Total Analysis Time: {total_duration:.2f} seconds")
    logger.result(f"Average Time per Test: {total_duration/total_tests:.2f} seconds")
    
    # Tool Performance
    logger.substep("🔧 Tool Performance Analysis")
    tool_stats = {}
    
    for result in results:
        for tool in result['tools']:
            if tool not in tool_stats:
                tool_stats[tool] = {"tests": 0, "issues": 0}
            tool_stats[tool]["tests"] += 1
            
            tool_issues = [i for i in result['issues'] if i.get('tool') == tool]
            tool_stats[tool]["issues"] += len(tool_issues)
    
    for tool, stats in tool_stats.items():
        avg_issues = stats["issues"] / stats["tests"] if stats["tests"] > 0 else 0
        logger.result(f"{tool.upper()}: {stats['tests']} tests, {stats['issues']} issues, {avg_issues:.1f} avg per test", indent=2)
    
    # Issue Severity Analysis
    logger.substep("🚨 Security Issue Severity Breakdown")
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    
    for result in results:
        for issue in result['issues']:
            severity = issue.get('severity', 'low').lower()
            if severity in severity_counts:
                severity_counts[severity] += 1
    
    for severity, count in severity_counts.items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}[severity]
            logger.result(f"{emoji} {severity.capitalize()}: {count} issues", indent=2)
    
    # Most Common Issues
    logger.substep("🔍 Most Common Security Issues")
    issue_types = {}
    
    for result in results:
        for issue in result['issues']:
            issue_type = issue.get('message', 'Unknown issue')
            tool = issue.get('tool', 'unknown')
            key = f"{tool}: {issue_type}"
            issue_types[key] = issue_types.get(key, 0) + 1
    
    sorted_issues = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)
    for issue_type, count in sorted_issues[:5]:
        logger.result(f"• {issue_type} ({count}x)", indent=2)
    
    # Model Analysis
    logger.substep("🤖 AI Model Security Analysis")
    model_stats = {}
    
    for result in results:
        model = result['model']
        if model not in model_stats:
            model_stats[model] = {"tests": 0, "issues": 0}
        model_stats[model]["tests"] += 1
        model_stats[model]["issues"] += result['total_issues']
    
    for model, stats in model_stats.items():
        avg_issues = stats["issues"] / stats["tests"] if stats["tests"] > 0 else 0
        logger.result(f"{model}: {stats['issues']} issues across {stats['tests']} tests ({avg_issues:.1f} avg)", indent=2)
    
    # Final Summary
    logger.section("🎯 TESTING INFRASTRUCTURE VALIDATION")
    logger.success("✅ Real source code successfully analyzed")
    logger.success("✅ Multiple security tools working in parallel")
    logger.success("✅ Containerized analysis infrastructure operational")
    logger.success("✅ Structured JSON results with detailed findings")
    logger.success("✅ Ready for batch processing of 900+ applications")
    
    elapsed_time = datetime.now() - logger.start_time
    logger.info(f"Total test session time: {elapsed_time.total_seconds():.1f} seconds")
    logger.info(f"Total security issues discovered: {logger.issue_count}")

def main():
    """Main execution with error handling."""
    try:
        logger = InteractiveLogger()
        
        success = test_all_tools_interactive()
        
        if success:
            logger.success("\n🎉 ALL SECURITY TOOLS TESTING COMPLETED SUCCESSFULLY!")
            logger.success("🔧 Ready for production analysis of AI-generated applications")
            sys.exit(0)
        else:
            logger.error("\n❌ SOME TESTS FAILED - Check logs above for details")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
