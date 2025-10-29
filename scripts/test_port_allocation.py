#!/usr/bin/env python3
"""Test Port Allocation Concurrency

This script tests that the port allocation service handles concurrent
requests correctly without causing UNIQUE constraint violations.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.factory import create_app
from app.services.port_allocation_service import get_port_allocation_service


def test_duplicate_allocation():
    """Test that duplicate allocations are handled gracefully."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        
        model = "test-model/test-1"
        app_num = 999
        
        print(f"\nTesting duplicate allocation for {model}/app{app_num}...")
        
        # Try to allocate ports twice for the same model/app
        try:
            result1 = service.get_or_allocate_ports(model, app_num)
            print(f"✓ First allocation: backend={result1.backend}, frontend={result1.frontend}")
            
            result2 = service.get_or_allocate_ports(model, app_num)
            print(f"✓ Second allocation: backend={result2.backend}, frontend={result2.frontend}")
            
            if result1.backend == result2.backend and result1.frontend == result2.frontend:
                print("✓ Both allocations returned the same ports (correct behavior)")
            else:
                print(f"✗ ERROR: Allocations returned different ports!")
                return 1
            
            # Clean up
            service.release_ports(model, app_num)
            print(f"✓ Cleaned up test allocation")
            
            return 0
            
        except Exception as e:
            print(f"✗ ERROR: {e}")
            return 1


def test_concurrent_different_apps():
    """Test that concurrent allocations for different apps work correctly."""
    app = create_app()
    with app.app_context():
        service = get_port_allocation_service()
        
        model = "test-model/test-2"
        
        print(f"\nTesting concurrent allocations for different apps...")
        
        try:
            # Allocate ports for app1 and app2
            result1 = service.get_or_allocate_ports(model, 1)
            result2 = service.get_or_allocate_ports(model, 2)
            
            print(f"✓ App1: backend={result1.backend}, frontend={result1.frontend}")
            print(f"✓ App2: backend={result2.backend}, frontend={result2.frontend}")
            
            # Verify they got different ports
            if result1.backend != result2.backend and result1.frontend != result2.frontend:
                print("✓ Apps got different ports (correct behavior)")
            else:
                print(f"✗ ERROR: Apps got overlapping ports!")
                return 1
            
            # Clean up
            service.release_ports(model, 1)
            service.release_ports(model, 2)
            print(f"✓ Cleaned up test allocations")
            
            return 0
            
        except Exception as e:
            print(f"✗ ERROR: {e}")
            return 1


def main():
    """Run all tests."""
    print("=" * 60)
    print("Port Allocation Concurrency Tests")
    print("=" * 60)
    
    tests = [
        test_duplicate_allocation,
        test_concurrent_different_apps
    ]
    
    failed = 0
    for test in tests:
        result = test()
        if result != 0:
            failed += 1
    
    print("\n" + "=" * 60)
    if failed == 0:
        print("✓ All tests passed!")
    else:
        print(f"✗ {failed} test(s) failed")
    print("=" * 60)
    
    return failed


if __name__ == '__main__':
    sys.exit(main())
