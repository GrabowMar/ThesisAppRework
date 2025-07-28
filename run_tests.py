"""
Test runner for Thesis Research App.

This script runs the comprehensive test suite and generates reports.
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path


def setup_test_environment():
    """Set up the test environment."""
    # Add src directory to Python path
    src_dir = Path(__file__).parent / "src"
    sys.path.insert(0, str(src_dir))
    
    # Set environment variables for testing
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['TESTING'] = 'true'


def run_tests(test_type='all', verbose=False, coverage=False, report_dir=None):
    """Run tests with specified options."""
    setup_test_environment()
    
    # Base pytest command
    cmd = ['python', '-m', 'pytest']
    
    # Add verbosity
    if verbose:
        cmd.append('-v')
    else:
        cmd.append('-q')
    
    # Add coverage if requested
    if coverage:
        cmd.extend([
            '--cov=src',
            '--cov-report=html',
            '--cov-report=term-missing'
        ])
        
        if report_dir:
            cmd.append(f'--cov-report=html:{report_dir}/coverage')
    
    # Select test type
    if test_type == 'unit':
        cmd.append('tests/unit/')
    elif test_type == 'integration':
        cmd.append('tests/integration/')
    elif test_type == 'models':
        cmd.append('tests/unit/test_models.py')
    elif test_type == 'routes':
        cmd.append('tests/unit/test_routes.py')
    elif test_type == 'services':
        cmd.append('tests/unit/test_services.py')
    elif test_type == 'workflows':
        cmd.append('tests/integration/test_workflows.py')
    else:  # all
        cmd.append('tests/')
    
    # Add report directory for JUnit XML
    if report_dir:
        cmd.extend(['--junitxml', f'{report_dir}/test-results.xml'])
    
    # Run tests
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)
    
    return result.returncode


def check_dependencies():
    """Check if required test dependencies are installed."""
    required_packages = [
        'pytest',
        'pytest-cov',
        'pytest-flask',
        'pytest-mock'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("Missing required test packages:")
        for package in missing_packages:
            print(f"  - {package}")
        print("\nInstall with: pip install " + " ".join(missing_packages))
        return False
    
    return True


def main():
    """Main test runner function."""
    parser = argparse.ArgumentParser(description='Run Thesis Research App tests')
    
    parser.add_argument(
        '--type', '-t',
        choices=['all', 'unit', 'integration', 'models', 'routes', 'services', 'workflows'],
        default='all',
        help='Type of tests to run'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '--coverage', '-c',
        action='store_true',
        help='Generate code coverage report'
    )
    
    parser.add_argument(
        '--report-dir', '-r',
        type=str,
        help='Directory to save test reports'
    )
    
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Check test dependencies and exit'
    )
    
    args = parser.parse_args()
    
    # Check dependencies if requested
    if args.check_deps:
        if check_dependencies():
            print("All test dependencies are installed.")
            return 0
        else:
            return 1
    
    # Create report directory if specified
    if args.report_dir:
        Path(args.report_dir).mkdir(parents=True, exist_ok=True)
    
    # Check dependencies before running tests
    if not check_dependencies():
        print("Please install missing dependencies before running tests.")
        return 1
    
    # Run tests
    print(f"Running {args.type} tests...")
    
    exit_code = run_tests(
        test_type=args.type,
        verbose=args.verbose,
        coverage=args.coverage,
        report_dir=args.report_dir
    )
    
    if exit_code == 0:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed.")
    
    return exit_code


if __name__ == '__main__':
    sys.exit(main())
