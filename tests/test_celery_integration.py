"""
Test Celery background task integration.
"""
import pytest
from pathlib import Path
import sys

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def test_celery_app_can_be_imported():
    """Test that Celery app can be imported."""
    try:
        from tasks import celery_app
        assert celery_app is not None
        assert hasattr(celery_app, 'Task')
        print("✓ Celery app imported successfully")
    except Exception as e:
        pytest.fail(f"Failed to import Celery app: {e}")


def test_tasks_can_be_imported():
    """Test that task functions can be imported."""
    try:
        from tasks import test_task, run_security_analysis_task
        
        # Check they are Celery tasks
        assert hasattr(test_task, 'delay'), "test_task missing delay method"
        assert hasattr(test_task, 'apply_async'), "test_task missing apply_async method"
        assert hasattr(run_security_analysis_task, 'delay'), "security task missing delay method"
        assert hasattr(run_security_analysis_task, 'apply_async'), "security task missing apply_async method"
        
        print("✓ All task functions imported with Celery methods")
    except Exception as e:
        pytest.fail(f"Failed to import tasks: {e}")


def test_celery_app_configuration():
    """Test that Celery app is properly configured."""
    try:
        from tasks import celery_app
        
        # Check basic configuration
        assert celery_app.conf.timezone == 'UTC'
        assert celery_app.conf.enable_utc is True
        assert celery_app.conf.task_serializer == 'json'
        assert celery_app.conf.result_serializer == 'json'
        
        print("✓ Celery app properly configured")
    except Exception as e:
        pytest.fail(f"Failed to check Celery configuration: {e}")


def test_task_registration():
    """Test that tasks are registered with Celery."""
    try:
        from tasks import celery_app
        
        # Get registered task names
        registered_tasks = list(celery_app.tasks.keys())
        
        # Check our tasks are registered
        expected_tasks = [
            'src.tasks.test_task',
            'src.tasks.run_security_analysis_task',
            'src.tasks.cleanup_expired_results',
            'src.tasks.health_check_containers'
        ]
        
        for task_name in expected_tasks:
            assert task_name in registered_tasks, f"Task {task_name} not registered"
        
        print(f"✓ All {len(expected_tasks)} tasks registered with Celery")
        print(f"  Registered tasks: {expected_tasks}")
    except Exception as e:
        pytest.fail(f"Failed to check task registration: {e}")


def test_flask_app_integration():
    """Test that tasks can get Flask app context."""
    try:
        from tasks import get_flask_app
        
        # Test that we can get a Flask app instance
        app = get_flask_app()
        assert app is not None
        assert hasattr(app, 'config')
        
        print("✓ Flask app integration works")
    except Exception as e:
        pytest.fail(f"Failed to get Flask app: {e}")


def test_task_progress_function():
    """Test the task progress update function."""
    try:
        from tasks import update_task_progress
        
        # Test that function can be called without errors
        # (This won't actually update anything without a running task)
        update_task_progress("test-id", 50, 100, "Testing progress")
        
        print("✓ Task progress function works")
    except Exception as e:
        pytest.fail(f"Failed to test progress function: {e}")


if __name__ == "__main__":
    test_celery_app_can_be_imported()
    test_tasks_can_be_imported()
    test_celery_app_configuration()
    test_task_registration()
    test_flask_app_integration()
    test_task_progress_function()
    print("All Celery integration tests passed!")
