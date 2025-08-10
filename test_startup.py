"""
Test script to verify the application can start properly
"""

import sys
import os
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def test_imports():
    """Test that all major components can be imported."""
    print("Testing imports...")
    
    try:
        from app.factory import create_app, create_celery
        print("✓ Factory imports work")
    except Exception as e:
        print(f"✗ Factory import failed: {e}")
        return False
    
    try:
        from app.models import db
        print("✓ Models import work")
    except Exception as e:
        print(f"✗ Models import failed: {e}")
        return False
    
    try:
        from app.extensions import init_extensions
        print("✓ Extensions import work")
    except Exception as e:
        print(f"✗ Extensions import failed: {e}")
        return False
    
    try:
        from config.celery_config import CeleryConfig
        print("✓ Celery config imports work")
    except Exception as e:
        print(f"✗ Celery config import failed: {e}")
        return False
    
    return True

def test_app_creation():
    """Test that Flask app can be created."""
    print("\nTesting app creation...")
    
    try:
        from app.factory import create_app
        app = create_app()
        print("✓ Flask app created successfully")
        return True
    except Exception as e:
        print(f"✗ App creation failed: {e}")
        return False

def test_celery_creation():
    """Test that Celery app can be created."""
    print("\nTesting Celery creation...")
    
    try:
        from app.factory import create_app, create_celery
        app = create_app()
        celery = create_celery(app)
        print("✓ Celery app created successfully")
        return True
    except Exception as e:
        print(f"✗ Celery creation failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=== Application Startup Test ===\n")
    
    tests = [
        test_imports,
        test_app_creation,
        test_celery_creation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
            results.append(False)
    
    print(f"\n=== Results ===")
    print(f"Tests passed: {sum(results)}/{len(results)}")
    
    if all(results):
        print("🎉 All tests passed! Application should start properly.")
        return True
    else:
        print("❌ Some tests failed. Check the errors above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
