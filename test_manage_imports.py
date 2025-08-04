#!/usr/bin/env python3
"""
Test script to verify manage.py import fixes
"""
import sys
from pathlib import Path

# Add testing-infrastructure to path
sys.path.append(str(Path(__file__).parent / "testing-infrastructure"))

def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    
    try:
        from local_testing_models import LocalTestingAPIClient, TestType, TestingStatus, ServiceHealth
        print("✅ Local testing models imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import local testing models: {e}")
        return False
    
    try:
        from manage import TestingInfrastructureManager
        print("✅ TestingInfrastructureManager imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import TestingInfrastructureManager: {e}")
        return False
    
    return True

def test_client_functionality():
    """Test that the client has all required methods."""
    print("\nTesting client functionality...")
    
    try:
        from local_testing_models import LocalTestingAPIClient
        client = LocalTestingAPIClient()
        
        # Test that all required methods exist
        required_methods = ['health_check', 'run_security_analysis', 'run_performance_test', 'run_zap_scan']
        for method_name in required_methods:
            if hasattr(client, method_name):
                print(f"✅ Method {method_name} exists")
            else:
                print(f"❌ Method {method_name} missing")
                return False
        
        # Test a simple method call
        health = client.health_check()
        print(f"✅ Health check returned: {type(health)} with {len(health)} services")
        
        return True
    except Exception as e:
        print(f"❌ Client functionality test failed: {e}")
        return False

def test_manager_initialization():
    """Test that the manager can be initialized."""
    print("\nTesting manager initialization...")
    
    try:
        from manage import TestingInfrastructureManager
        from pathlib import Path
        
        base_path = Path("testing-infrastructure")
        manager = TestingInfrastructureManager(base_path)
        
        print(f"✅ Manager initialized with base_path: {manager.base_path}")
        print(f"✅ Manager has client: {manager.client is not None}")
        
        return True
    except Exception as e:
        print(f"❌ Manager initialization failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing manage.py Import Fixes ===\n")
    
    tests = [
        test_imports,
        test_client_functionality,
        test_manager_initialization
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("🎉 All tests passed! The import fixes are working correctly.")
        sys.exit(0)
    else:
        print("❌ Some tests failed. There may be remaining import issues.")
        sys.exit(1)
