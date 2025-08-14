#!/usr/bin/env python3
"""
Test Script for Celery Integration
=================================

Simple test script to verify that Celery integration is working properly.
"""

import sys
from pathlib import Path

# Add src directory to path so 'app' package is importable when running this file directly
src_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(src_root))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        import app.factory as app_factory  # noqa: F401
        print("✓ App factory imports successful")
    except ImportError as e:
        print(f"✗ App factory import failed: {e}")
        assert False
    
    try:
        import app.tasks as tasks_mod
        # Sanity check core task attributes exist
        assert hasattr(tasks_mod, 'security_analysis_task')
        assert hasattr(tasks_mod, 'performance_test_task')
        assert hasattr(tasks_mod, 'static_analysis_task')
        assert hasattr(tasks_mod, 'ai_analysis_task')
        assert hasattr(tasks_mod, 'batch_analysis_task')
        print("✓ Tasks module imported and contains expected tasks")
    except ImportError as e:
        print(f"✗ Task import failed: {e}")
        assert False
    
    try:
        from app.services.task_manager import TaskManager as _TaskManager  # noqa: F401
        print("✓ Task manager import successful")
    except ImportError as e:
        print(f"✗ Task manager import failed: {e}")
        assert False
    
    try:
        from app.services.analyzer_integration import get_analyzer_integration as _get_ai  # noqa: F401
        print("✓ Analyzer integration import successful")
    except ImportError as e:
        print(f"✗ Analyzer integration import failed: {e}")
        assert False
    
    assert True

def test_app_creation():
    """Test Flask app creation."""
    print("\nTesting Flask app creation...")
    
    try:
        from app.factory import create_app
        _app = create_app()
        print("✓ Flask app created successfully")
        assert True
    except Exception as e:
        print(f"✗ Flask app creation failed: {e}")
        assert False

def test_celery_creation():
    """Test Celery app creation."""
    print("\nTesting Celery app creation...")
    
    try:
        from app.factory import get_celery_app
        _celery_app = get_celery_app()
        print("✓ Celery app created successfully")
        assert True
    except Exception as e:
        print(f"✗ Celery app creation failed: {e}")
        assert False

def test_task_manager():
    """Test TaskManager initialization."""
    print("\nTesting TaskManager initialization...")
    
    try:
        from app.services.task_manager import TaskManager
        _ = TaskManager()
        print("✓ TaskManager initialized successfully")
        assert True
    except Exception as e:
        print(f"✗ TaskManager initialization failed: {e}")
        assert False

def test_analyzer_integration():
    """Test AnalyzerIntegration initialization."""
    print("\nTesting AnalyzerIntegration initialization...")
    
    try:
        from app.services.analyzer_integration import get_analyzer_integration
        _ = get_analyzer_integration()
        print("✓ AnalyzerIntegration initialized successfully")
        assert True
    except Exception as e:
        print(f"✗ AnalyzerIntegration initialization failed: {e}")
        assert False

def test_task_definitions():
    """Test that task definitions are working."""
    print("\nTesting task definitions...")
    
    try:
        import app.tasks as t
        expected = [
            'security_analysis_task',
            'performance_test_task',
            'static_analysis_task',
            'ai_analysis_task',
            'batch_analysis_task',
        ]
        for name in expected:
            assert hasattr(t, name), f"Missing task: {name}"
            task_obj = getattr(t, name)
            # Celery wraps functions; ensure a 'name' attribute is present
            assert hasattr(task_obj, 'name')
            print(f"✓ Task app.tasks.{name} defined correctly")

        assert True
    except Exception as e:
        print(f"✗ Task definition test failed: {e}")
        assert False

def test_database_models():
    """Test database models."""
    print("\nTesting database models...")
    
    try:
        import app.models as m
        # Sanity check a few expected models
        for attr in ['ModelCapability', 'GeneratedApplication', 'SecurityAnalysis']:
            assert hasattr(m, attr), f"Missing model: {attr}"
        print("✓ Database models module imported successfully")
        assert True
    except ImportError as e:
        print(f"✗ Database models import failed: {e}")
        assert False

def main():
    """Run all tests."""
    print("="*60)
    print("Celery Integration Test Suite")
    print("="*60)
    
    tests = [
        test_imports,
        test_app_creation,
        test_celery_creation,
        test_task_manager,
        test_analyzer_integration,
        test_task_definitions,
        test_database_models
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            # Consider a test passed if it runs without raising (assertions/errors)
            test()
            passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed or failed: {e}")
            failed += 1
    
    print("\n" + "="*60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("="*60)
    
    if failed == 0:
        print("🎉 All tests passed! Celery integration is ready.")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
