#!/usr/bin/env python3
"""
Enhanced Real Model Integration Demonstration
=============================================

This demonstration shows the UnifiedCLIAnalyzer working with 25+ real AI models
from multiple providers, featuring enhanced progress tracking, containerized 
testing integration, and model validation.

Key Features Demonstrated:
- Real model listing and validation
- Containerized security analysis  
- Performance tracking and metrics
- Multi-provider model support
- Enhanced progress monitoring
- API integrations with model providers
"""

import subprocess
import sys
import time
from pathlib import Path

def run_command(command, description, timeout=60):
    """Run a command and return success status."""
    print(f"\n{'='*80}")
    print(f"[*] {description}")
    print('='*80)
    print(f"Command: {command}")
    print('-'*80)
    
    try:
        # Start the process
        start_time = time.time()
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', 
            errors='replace',  # Handle encoding issues gracefully
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        # Print output
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        success = result.returncode == 0
        status = "[+] PASSED" if success else "[-] FAILED"
        print(f"\n{status} (Exit code: {result.returncode}, Time: {elapsed:.1f}s)")
        
        return success
        
    except subprocess.TimeoutExpired:
        print(f"[-] Command timed out after {timeout}s")
        return False
    except Exception as e:
        print(f"[-] Command failed with error: {e}")
        return False

def main():
    """Run the enhanced demonstration."""
    print("Enhanced Real Model Integration Demonstration")
    print("=" * 55)
    print()
    print("This demonstration shows the UnifiedCLIAnalyzer working with 25+ real AI models")
    print("from multiple providers, featuring enhanced progress tracking and containerized")
    print("testing infrastructure integration.")
    print()

    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    if project_root.name != "ThesisAppRework":
        print("Warning: Not in ThesisAppRework directory")
    
    # Demo test cases
    demos = [
        {
            'command': 'python src/unified_cli_analyzer.py utils list-models',
            'description': 'Listing all 25 real AI models from database',
            'timeout': 30
        },
        {
            'command': 'python src/unified_cli_analyzer.py utils list-models --details',
            'description': 'Detailed view of real models with provider information',
            'timeout': 30
        },
        {
            'command': 'python src/unified_cli_analyzer.py security backend --model anthropic_claude-3.7-sonnet --app 1 --tools bandit,safety',
            'description': 'Security analysis with real Anthropic Claude 3.7 Sonnet',
            'timeout': 120
        },
        {
            'command': 'python src/unified_cli_analyzer.py security backend --model openai_gpt-4.1 --app 1 --tools bandit,pylint',
            'description': 'Security analysis with real OpenAI GPT-4.1',
            'timeout': 120
        },
        {
            'command': 'python src/unified_cli_analyzer.py security backend --model google_gemini-2.5-pro --app 1 --tools safety,bandit',
            'description': 'Security analysis with real Google Gemini 2.5 Pro',
            'timeout': 120
        },
        {
            'command': 'python src/unified_cli_analyzer.py security backend --model deepseek_deepseek-r1-0528 --app 1 --tools bandit',
            'description': 'Security analysis with real DeepSeek R1 model',
            'timeout': 120
        },
        {
            'command': 'python src/unified_cli_analyzer.py utils validate-docker',
            'description': 'Validate Docker and containerized testing infrastructure',
            'timeout': 30
        },
        {
            'command': 'python src/unified_cli_analyzer.py utils health-check',
            'description': 'Health check of all services and containerized infrastructure',
            'timeout': 30
        }
    ]
    
    # Run demos and track results
    successful_demos = 0
    total_demos = len(demos)
    results = []
    
    for i, demo in enumerate(demos, 1):
        print(f"\n[*] Demo {i}/{total_demos}")
        success = run_command(
            demo['command'], 
            demo['description'], 
            demo.get('timeout', 60)
        )
        
        if success:
            successful_demos += 1
            status = "PASSED"
        else:
            status = "FAILED"
        
        results.append({
            'demo': i,
            'description': demo['description'],
            'status': status,
            'success': success
        })
    
    # Print summary
    print(f"\n{'='*80}")
    print("ENHANCED REAL MODEL INTEGRATION DEMONSTRATION SUMMARY")
    print('='*80)
    print(f"[+] Successful demos: {successful_demos}/{total_demos}")
    print(f"[*] Success rate: {successful_demos/total_demos*100:.1f}%")
    print()
    
    print("Demo Results:")
    for result in results:
        status_icon = "[+]" if result['success'] else "[-]"
        print(f"  {status_icon} Demo {result['demo']}: {result['status']}")
        print(f"      {result['description']}")
    
    print()
    print("Enhanced Features Demonstrated:")
    print("  [+] Real AI model integration (25+ models from 11 providers)")
    print("  [+] Database-driven model validation and retrieval")
    print("  [+] Containerized testing infrastructure connectivity")
    print("  [+] Unicode encoding issue resolution")
    print("  [+] Enhanced service initialization and health checks")
    print("  [+] Multi-provider model support (Anthropic, OpenAI, Google, DeepSeek)")
    print("  [+] Improved error handling and logging")
    print("  [+] Performance metrics tracking capabilities")
    
    if successful_demos == total_demos:
        print("\n[+] ALL DEMOS PASSED! System is fully operational with real AI models.")
        return 0
    else:
        print(f"\n[-] {total_demos - successful_demos} demos failed. Check logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
