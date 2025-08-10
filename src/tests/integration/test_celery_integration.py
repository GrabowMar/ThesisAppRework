#!/usr/bin/env python3
"""
Test Script for Celery Integration
=================================

Simple test script to verify that Celery integration is working properly.
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    
    try:
        from app.factory import create_app, get_celery_app
        print("✓ App factory imports successful")
    except ImportError as e:
        print(f"✗ App factory import failed: {e}")
        return False
    
    try:
        from app.tasks import security_analysis_task, performance_test_task
        print("✓ Task imports successful")
    except ImportError as e:
        print(f"✗ Task import failed: {e}")
        return False
    
    try:
        from app.services.task_manager import TaskManager
        print("✓ Task manager import successful")
    except ImportError as e:
        print(f"✗ Task manager import failed: {e}")
        return False
    
    try:
        from app.services.analyzer_integration import get_analyzer_integration
        print("✓ Analyzer integration import successful")
    except ImportError as e:
        print(f"✗ Analyzer integration import failed: {e}")
        return False
    
    return True

def test_app_creation():
    """Test Flask app creation."""
    print("\nTesting Flask app creation...")
    
    try:
        from app.factory import create_app
        app = create_app()
        print("✓ Flask app created successfully")
        return True
    except Exception as e:
        print(f"✗ Flask app creation failed: {e}")
        return False

def test_celery_creation():
    """Test Celery app creation."""
    print("\nTesting Celery app creation...")
    
    try:
        from app.factory import get_celery_app
        celery_app = get_celery_app()
        print("✓ Celery app created successfully")
        return True
    except Exception as e:
        print(f"✗ Celery app creation failed: {e}")
        return False

def test_task_manager():
    """Test TaskManager initialization."""
    print("\nTesting TaskManager initialization...")
    
    try:
        from app.services.task_manager import TaskManager
        task_manager = TaskManager()
        print("✓ TaskManager initialized successfully")
        return True
    except Exception as e:
        print(f"✗ TaskManager initialization failed: {e}")
        return False

def test_analyzer_integration():
    """Test AnalyzerIntegration initialization."""
    print("\nTesting AnalyzerIntegration initialization...")
    
    try:
        from app.services.analyzer_integration import get_analyzer_integration
        analyzer = get_analyzer_integration()
        print("✓ AnalyzerIntegration initialized successfully")
        return True
    except Exception as e:
        print(f"✗ AnalyzerIntegration initialization failed: {e}")
        return False

def test_task_definitions():
    """Test that task definitions are working."""
    print("\nTesting task definitions...")
    
    try:
        from app.tasks import (
            security_analysis_task,
            performance_test_task,
            static_analysis_task,
            ai_analysis_task,
            batch_analysis_task
        )
        
        # Check task names
        expected_tasks = [
            'app.tasks.security_analysis_task',
            'app.tasks.performance_test_task',
            'app.tasks.static_analysis_task',
            'app.tasks.ai_analysis_task',
            'app.tasks.batch_analysis_task'
        ]
        
        for task_name in expected_tasks:
            if hasattr(eval(task_name.split('.')[-1]), 'name'):
                print(f"✓ Task {task_name} defined correctly")
            else:
                print(f"✗ Task {task_name} definition issue")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Task definition test failed: {e}")
        return False

def test_database_models():
    """Test database models."""
    print("\nTesting database models...")
    
    try:
        from app.models import (
            ModelCapability,
            PortConfiguration,
            GeneratedApplication,
            SecurityAnalysis,
            PerformanceTest,
            BatchAnalysis,
            ContainerizedTest
        )
        print("✓ Database models imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Database models import failed: {e}")
        return False

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
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} crashed: {e}")
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
