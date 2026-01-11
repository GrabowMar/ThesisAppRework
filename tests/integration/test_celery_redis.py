"""
Integration tests for Celery and Redis task execution.

These tests verify:
1. Redis connectivity and availability
2. Celery worker registration
3. Task dispatch and execution
4. Issue count extraction from analysis results

Requirements:
- Docker must be running
- Redis container must be healthy
- Celery worker container must be healthy
"""

import pytest
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any
from unittest.mock import patch, MagicMock

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]


class TestRedisConnectivity:
    """Test Redis server connectivity."""
    
    def test_redis_connection(self, app):
        """Verify Redis is reachable."""
        try:
            import redis
            redis_url = app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url, socket_timeout=5.0, socket_connect_timeout=5.0)
            result = client.ping()
            assert result is True, "Redis ping should return True"
        except redis.ConnectionError as e:
            pytest.skip(f"Redis not available: {e}")
    
    def test_redis_set_get(self, app):
        """Test basic Redis operations."""
        try:
            import redis
            redis_url = app.config.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
            client = redis.from_url(redis_url, socket_timeout=5.0)
            
            test_key = f"test_key_{int(time.time())}"
            test_value = "test_value"
            
            # Set
            client.set(test_key, test_value)
            
            # Get
            result = client.get(test_key)
            assert result.decode() == test_value
            
            # Cleanup
            client.delete(test_key)
        except redis.ConnectionError as e:
            pytest.skip(f"Redis not available: {e}")


class TestCeleryConfiguration:
    """Test Celery app configuration."""
    
    def test_celery_app_exists(self, app):
        """Verify Celery app is properly configured."""
        from app.celery_worker import celery
        
        assert celery is not None
        assert celery.main == 'app.factory'
    
    def test_celery_tasks_registered(self, app):
        """Verify tasks are registered with Celery."""
        from app.celery_worker import celery
        # Force task discovery by importing tasks module
        import app.tasks  # noqa: F401
        
        registered_tasks = list(celery.tasks.keys())
        
        # Check our custom tasks are registered
        expected_tasks = [
            'app.tasks.execute_analysis',
            'app.tasks.execute_subtask',
            'app.tasks.aggregate_results',
        ]
        
        for task_name in expected_tasks:
            assert task_name in registered_tasks, \
                f"Task {task_name} not registered. Available: {registered_tasks}"
    
    def test_celery_broker_configured(self, app):
        """Verify Celery broker URL is configured."""
        from app.celery_worker import celery
        
        broker_url = celery.conf.broker_url
        assert broker_url is not None
        assert 'redis' in broker_url or 'amqp' in broker_url, \
            f"Invalid broker URL: {broker_url}"


class TestIssueCountExtraction:
    """Test the issue count extraction helper function."""
    
    def test_extract_from_direct_summary(self, app):
        """Test extraction from direct summary format."""
        from app.tasks import _extract_total_issues
        
        payload = {
            'summary': {
                'total_findings': 42
            }
        }
        
        result = _extract_total_issues(payload)
        assert result == 42
    
    def test_extract_from_nested_results(self, app):
        """Test extraction from nested results format."""
        from app.tasks import _extract_total_issues
        
        payload = {
            'results': {
                'summary': {
                    'total_findings': 21
                }
            }
        }
        
        result = _extract_total_issues(payload)
        assert result == 21
    
    def test_extract_from_service_results(self, app):
        """Test extraction from service-specific results."""
        from app.tasks import _extract_total_issues
        
        # This simulates the actual result format from analyzers
        payload = {
            'results': {
                'summary': {
                    'total_findings': 0  # Summary says 0 but services have findings
                },
                'services': {
                    'static': {
                        'analysis': {
                            'results': {
                                'python': {
                                    'bandit': {
                                        'total_issues': 7
                                    },
                                    'semgrep': {
                                        'total_issues': 14
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        
        result = _extract_total_issues(payload)
        assert result == 21, f"Expected 21 (7+14), got {result}"
    
    def test_extract_from_top_level_services(self, app):
        """Test extraction from top-level service format."""
        from app.tasks import _extract_total_issues
        
        payload = {
            'services': {
                'static': {
                    'analysis': {
                        'results': {
                            'python': {
                                'ruff': {'total_issues': 10},
                                'mypy': {'total_issues': 5}
                            }
                        }
                    }
                }
            }
        }
        
        result = _extract_total_issues(payload)
        assert result == 15
    
    def test_extract_handles_empty_payload(self, app):
        """Test extraction handles empty payload gracefully."""
        from app.tasks import _extract_total_issues
        
        result = _extract_total_issues({})
        assert result == 0
    
    def test_extract_handles_malformed_payload(self, app):
        """Test extraction handles malformed payload."""
        from app.tasks import _extract_total_issues
        
        payload = {
            'services': {
                'static': "not a dict"  # Invalid format
            }
        }
        
        result = _extract_total_issues(payload)
        assert result == 0  # Should not crash, return 0


class TestTaskService:
    """Test the TaskService task creation."""
    
    def test_create_task(self, app, db_session):
        """Test creating an analysis task."""
        from app.services.task_service import task_service
        from app.models import AnalysisTask, AnalysisStatus
        
        task = task_service.create_task(
            model_slug='test_model',
            app_number=99,
            tools=['bandit'],
            task_name='test',
            description='Integration test task',
            dispatch=False  # Don't actually dispatch to Celery
        )
        
        assert task is not None
        assert task.task_id.startswith('task_')
        assert task.status == AnalysisStatus.PENDING
        assert task.target_model == 'test_model'
        assert task.target_app_number == 99
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()
    
    def test_create_task_with_custom_options(self, app, db_session):
        """Test creating task with custom options."""
        from app.services.task_service import task_service
        from app.models import AnalysisTask
        
        custom_opts = {
            'tools': ['bandit', 'semgrep'],
            'execution_engine': 'celery'
        }
        
        task = task_service.create_task(
            model_slug='test_model',
            app_number=99,
            tools=['bandit', 'semgrep'],
            task_name='static',
            custom_options=custom_opts,
            dispatch=False
        )
        
        assert task is not None
        
        meta = task.get_metadata()
        assert 'custom_options' in meta
        assert meta['custom_options']['tools'] == ['bandit', 'semgrep']
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()


class TestTaskStatusTransitions:
    """Test task status state machine transitions."""
    
    def test_pending_to_running(self, app, db_session):
        """Test task transition from PENDING to RUNNING."""
        from app.services.task_service import task_service
        from app.models import AnalysisTask, AnalysisStatus
        
        task = task_service.create_task(
            model_slug='test_model',
            app_number=99,
            tools=['bandit'],
            task_name='test',
            dispatch=False
        )
        
        assert task.status == AnalysisStatus.PENDING
        
        # Start the task
        task_service.start_task(task.task_id)
        
        # Refresh from DB
        db_session.refresh(task)
        assert task.status == AnalysisStatus.RUNNING
        assert task.started_at is not None
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()
    
    def test_running_to_completed(self, app, db_session):
        """Test task transition from RUNNING to COMPLETED."""
        from app.services.task_service import task_service
        from app.models import AnalysisTask, AnalysisStatus
        
        task = task_service.create_task(
            model_slug='test_model',
            app_number=99,
            tools=['bandit'],
            task_name='test',
            dispatch=False
        )
        
        # Start and complete
        task_service.start_task(task.task_id)
        task_service.complete_task(task.task_id, results={'issues_found': 10})
        
        db_session.refresh(task)
        assert task.status == AnalysisStatus.COMPLETED
        assert task.completed_at is not None
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()
    
    def test_running_to_failed(self, app, db_session):
        """Test task transition from RUNNING to FAILED."""
        from app.services.task_service import task_service
        from app.models import AnalysisTask, AnalysisStatus
        
        task = task_service.create_task(
            model_slug='test_model',
            app_number=99,
            tools=['bandit'],
            task_name='test',
            dispatch=False
        )
        
        # Start and fail
        task_service.start_task(task.task_id)
        task_service.fail_task(task.task_id, error='Test failure')
        
        db_session.refresh(task)
        assert task.status == AnalysisStatus.FAILED
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()


class TestWebSocketSync:
    """Test the synchronous WebSocket helper."""
    
    def test_run_websocket_sync_import(self, app):
        """Test that _run_websocket_sync is importable."""
        from app.tasks import _run_websocket_sync
        
        assert callable(_run_websocket_sync)
    
    def test_run_websocket_sync_unknown_service(self, app):
        """Test _run_websocket_sync with unknown service."""
        from app.tasks import _run_websocket_sync
        
        result = _run_websocket_sync(
            'unknown-service',
            'test_model',
            1,
            ['tool1'],
            timeout=5
        )
        
        assert result.get('status') == 'error'
        assert 'Unknown service' in result.get('error', '')


class TestDistributedLock:
    """Test the distributed lock mechanism."""
    
    def test_database_write_lock(self, app):
        """Test database write lock context manager."""
        from app.utils.distributed_lock import database_write_lock
        
        with database_write_lock("test_lock_123"):
            # Lock should be acquired
            pass
        # Lock should be released
    
    def test_database_write_lock_concurrent(self, app):
        """Test that locks work with concurrent access."""
        import threading
        from app.utils.distributed_lock import database_write_lock
        
        results = []
        errors = []
        
        def acquire_lock(lock_id: str):
            try:
                with database_write_lock(lock_id):
                    results.append(f"acquired_{lock_id}")
                    time.sleep(0.1)
                    results.append(f"released_{lock_id}")
            except Exception as e:
                errors.append(str(e))
        
        # Start two threads trying to acquire same lock
        t1 = threading.Thread(target=acquire_lock, args=("shared_lock",))
        t2 = threading.Thread(target=acquire_lock, args=("shared_lock",))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Both should complete without errors
        assert len(errors) == 0, f"Lock errors: {errors}"
        assert len(results) == 4, f"Expected 4 results, got {results}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
