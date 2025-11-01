"""
Quick Test Runner - Web UI and Analyzer Tests
==============================================

Run this to verify all systems are working:
- Authentication (Bearer token + session cookies)
- Analysis creation form
- Docker analyzers
- Database integration

Usage:
    python run_system_tests.py          # Run all fast tests
    python run_system_tests.py --all    # Run all tests including slow ones
"""

import sys
import subprocess
from pathlib import Path


def run_tests(include_slow=False):
    """Run the test suite"""
    
    print("=" * 70)
    print("System Health Tests - ThesisAppRework")
    print("=" * 70)
    print()
    
    # Test categories
    test_suites = [
        {
            'name': 'Web UI Integration Tests',
            'file': 'tests/test_web_ui_integration.py',
            'markers': 'not slow and not analyzer',
            'description': 'Authentication, form submission, HTMX endpoints'
        },
        {
            'name': 'Analyzer & Docker Tests',
            'file': 'tests/test_analyzer_docker.py',
            'markers': 'not slow and not analyzer',
            'description': 'Container status, ports, tool registry'
        }
    ]
    
    if include_slow:
        # Add slow/comprehensive tests
        test_suites.append({
            'name': 'End-to-End Tests (SLOW)',
            'file': 'tests/test_web_ui_integration.py::TestEndToEndAnalysis',
            'markers': 'slow',
            'description': 'Complete analysis workflows'
        })
    
    results = {}
    
    for suite in test_suites:
        print(f"\n{'─' * 70}")
        print(f"Running: {suite['name']}")
        print(f"Description: {suite['description']}")
        print(f"{'─' * 70}\n")
        
        cmd = [
            sys.executable,
            '-m', 'pytest',
            suite['file'],
            '-v',
            '--tb=short',
            '-m', suite['markers']
        ]
        
        result = subprocess.run(cmd, capture_output=False)
        results[suite['name']] = result.returncode == 0
        
        if result.returncode != 0:
            print(f"\n❌ {suite['name']} FAILED")
        else:
            print(f"\n✅ {suite['name']} PASSED")
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:10} {name}")
    
    print(f"\nTotal: {passed}/{total} test suites passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is healthy.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check output above for details.")
        return 1


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run system health tests')
    parser.add_argument('--all', action='store_true', help='Include slow/comprehensive tests')
    
    args = parser.parse_args()
    
    print("\nChecking prerequisites...")
    
    # Check Flask app is running
    try:
        import requests
        response = requests.get('http://localhost:5000', timeout=2)
        print("✅ Flask app is running on localhost:5000")
    except:
        print("⚠️  Flask app may not be running on localhost:5000")
        print("   Start it with: python src/main.py")
    
    # Check Docker containers
    result = subprocess.run(
        ['docker', 'ps', '--filter', 'name=analyzer', '--format', '{{.Names}}'],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0 and result.stdout.strip():
        containers = result.stdout.strip().split('\n')
        print(f"✅ Docker analyzers running: {len(containers)} containers")
    else:
        print("⚠️  Docker analyzers may not be running")
        print("   Start them with: python analyzer/analyzer_manager.py start")
    
    print()
    
    # Run tests
    exit_code = run_tests(include_slow=args.all)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
