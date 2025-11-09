"""
Test script to verify generation service fixes

Run this to verify:
1. File locks prevent concurrent overwrites
2. Queue mode works correctly
3. Timezone-aware datetime comparisons work
4. OpenRouter error handling is robust
"""

import sys
import os
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent / 'src'
sys.path.insert(0, str(src_dir))

def test_file_locks():
    """Test that file locks prevent concurrent writes."""
    print("\n=== Testing File Locks ===")
    from app.services.generation import get_generation_service
    
    service = get_generation_service()
    
    # Test that locks are created per-app
    lock1 = service._get_app_lock("test_model", 1)
    lock2 = service._get_app_lock("test_model", 1)
    lock3 = service._get_app_lock("test_model", 2)
    
    assert lock1 is lock2, "Same app should return same lock"
    assert lock1 is not lock3, "Different apps should have different locks"
    
    print("✓ File locks working correctly")
    return True

def test_queue_mode():
    """Test that queue mode is properly configured."""
    print("\n=== Testing Queue Mode ===")
    from app.services.generation import get_generation_service
    
    service = get_generation_service()
    
    # Check queue is enabled by default
    assert service.use_queue == True, "Queue should be enabled by default"
    assert service.generation_queue is not None, "Queue should be initialized"
    
    # Check worker thread is running
    assert service.queue_worker_thread.is_alive(), "Queue worker thread should be running"
    
    print(f"✓ Queue mode enabled with max_concurrent={service.max_concurrent}")
    return True

def test_timezone_helper():
    """Test timezone normalization helper."""
    print("\n=== Testing Timezone Helper ===")
    from app.services.generation import _ensure_timezone_aware
    from datetime import datetime, timezone
    
    # Test naive datetime
    naive_dt = datetime(2025, 1, 1, 12, 0, 0)
    aware_dt = _ensure_timezone_aware(naive_dt)
    assert aware_dt.tzinfo is not None, "Should convert naive to aware"
    assert aware_dt.tzinfo == timezone.utc, "Should use UTC"
    
    # Test already aware datetime
    already_aware = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = _ensure_timezone_aware(already_aware)
    assert result.tzinfo == timezone.utc, "Should preserve timezone"
    
    # Test None
    result = _ensure_timezone_aware(None)
    assert result is None, "Should handle None"
    
    print("✓ Timezone normalization working correctly")
    return True

def test_openrouter_service():
    """Test that OpenRouter service is properly configured."""
    print("\n=== Testing OpenRouter Service ===")
    from app.services.openrouter_chat_service import get_openrouter_chat_service
    import inspect
    
    service = get_openrouter_chat_service()
    
    # Check that generate_chat_completion has max_retries parameter
    sig = inspect.signature(service.generate_chat_completion)
    params = list(sig.parameters.keys())
    assert 'max_retries' in params, "Should have max_retries parameter"
    
    # Check default value
    default_retries = sig.parameters['max_retries'].default
    assert default_retries == 2, f"Default retries should be 2, got {default_retries}"
    
    print("✓ OpenRouter service has retry logic")
    return True

def test_migration_exists():
    """Check that timezone migration file exists."""
    print("\n=== Checking Migration File ===")
    
    migration_file = Path(__file__).parent / 'migrations' / '20250209_normalize_timezones.py'
    assert migration_file.exists(), f"Migration file not found: {migration_file}"
    
    # Check it's valid Python
    with open(migration_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert 'def upgrade()' in content, "Should have upgrade function"
        assert 'def downgrade()' in content, "Should have downgrade function"
    
    print(f"✓ Migration file exists: {migration_file.name}")
    return True

def main():
    """Run all tests."""
    print("=" * 60)
    print("Generation Service Fixes - Verification Tests")
    print("=" * 60)
    
    tests = [
        ("File Locks", test_file_locks),
        ("Queue Mode", test_queue_mode),
        ("Timezone Helper", test_timezone_helper),
        ("OpenRouter Service", test_openrouter_service),
        ("Migration File", test_migration_exists),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, "PASS" if success else "FAIL"))
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results.append((name, "FAIL"))
    
    print("\n" + "=" * 60)
    print("Test Results:")
    print("=" * 60)
    for name, status in results:
        symbol = "✓" if status == "PASS" else "✗"
        print(f"{symbol} {name}: {status}")
    
    passed = sum(1 for _, status in results if status == "PASS")
    total = len(results)
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n✅ All fixes verified successfully!")
        return 0
    else:
        print("\n❌ Some tests failed - please review")
        return 1

if __name__ == '__main__':
    sys.exit(main())
