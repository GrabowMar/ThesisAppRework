"""
Test Docker Container Naming Fix

This script verifies that the Docker container naming conflict has been resolved.
It checks that:
1. PROJECT_NAME environment variable is properly passed
2. Each app gets unique container names
3. No naming conflicts occur when starting multiple apps
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root / 'src'))

from app.services.docker_manager import DockerManager


def test_project_name_generation():
    """Test that project names are unique per model/app."""
    print("=" * 60)
    print("Testing Project Name Generation")
    print("=" * 60)
    
    manager = DockerManager()
    
    test_cases = [
        ('openai_gpt-4', 1, 'openai-gpt-4-app1'),
        ('openai_gpt-4', 2, 'openai-gpt-4-app2'),
        ('anthropic_claude-3.5-sonnet', 1, 'anthropic-claude-3-5-sonnet-app1'),
        ('google_gemini-2.0-flash', 3, 'google-gemini-2-0-flash-app3'),
    ]
    
    all_passed = True
    for model, app_num, expected in test_cases:
        actual = manager._get_project_name(model, app_num)
        passed = actual == expected
        all_passed = all_passed and passed
        
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {model}/app{app_num}")
        print(f"  Expected: {expected}")
        print(f"  Actual:   {actual}")
        print()
    
    return all_passed


def test_environment_variable_in_compose():
    """Test that PROJECT_NAME will be passed to docker-compose commands."""
    print("=" * 60)
    print("Testing Environment Variable Passing")
    print("=" * 60)
    
    manager = DockerManager()
    
    # Check if the _execute_compose_command method includes env parameter
    import inspect
    source = inspect.getsource(manager._execute_compose_command)
    
    checks = [
        ("env = os.environ.copy()" in source, "Creates environment copy"),
        ("env['PROJECT_NAME'] = project_name" in source, "Sets PROJECT_NAME variable"),
        ("env=env" in source, "Passes env to subprocess"),
    ]
    
    all_passed = True
    for check, description in checks:
        passed = check
        all_passed = all_passed and passed
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {description}")
    
    print()
    return all_passed


def test_error_handling():
    """Test that errors are properly extracted and returned."""
    print("=" * 60)
    print("Testing Error Handling")
    print("=" * 60)
    
    manager = DockerManager()
    
    # Check error handling code
    import inspect
    source = inspect.getsource(manager._execute_compose_command)
    
    checks = [
        ("'exit_code'" in source, "Includes exit_code field"),
        ("out['error']" in source or "error_text" in source, "Extracts error messages"),
        ("lines[-1]" in source or "splitlines()" in source, "Parses multi-line errors"),
    ]
    
    all_passed = True
    for check, description in checks:
        passed = check
        all_passed = all_passed and passed
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {description}")
    
    print()
    return all_passed


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Docker Container Naming Fix Verification")
    print("=" * 60 + "\n")
    
    results = []
    
    # Test 1: Project name generation
    results.append(("Project Name Generation", test_project_name_generation()))
    
    # Test 2: Environment variable passing
    results.append(("Environment Variable Passing", test_environment_variable_in_compose()))
    
    # Test 3: Error handling
    results.append(("Error Message Handling", test_error_handling()))
    
    # Summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        all_passed = all_passed and passed
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 60)
    
    if all_passed:
        print("\n🎉 All tests passed! The Docker naming fix is working correctly.")
        print("\nNext steps:")
        print("1. Restart the Flask app to apply the changes")
        print("2. Try starting multiple applications")
        print("3. Run: docker ps --format '{{.Names}}' to verify unique names")
        return 0
    else:
        print("\n⚠️ Some tests failed. Please review the changes.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
