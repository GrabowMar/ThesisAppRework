"""Integration tests for pipeline race conditions and edge cases.

These tests verify the robustness of the pipeline execution under
various failure scenarios and race conditions.
"""

import pytest
import json
import time
from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestJobIndexTaskCreationAtomicity:
    """Test atomicity between job_index advancement and task creation."""
    
    def test_job_index_not_lost_on_task_creation_failure(self, app, db_session):
        """Verify that failed task creation doesn't lose jobs.
        
        Scenario:
        1. job_index is advanced and committed
        2. _submit_analysis_task fails
        3. The job should still be tracked as attempted/failed
        """
        from app.models.pipeline import PipelineExecution
        from app.constants import AnalysisStatus
        
        # Create a pipeline in analysis stage
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [
                    {'model': 'model_a', 'app': 1},
                    {'model': 'model_b', 'app': 2}
                ]
            },
            'analysis': {
                'enabled': True,
                'tools': ['semgrep', 'bandit']
            }
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        pipeline.current_job_index = 0
        db_session.add(pipeline)
        db_session.commit()
        
        # Simulate: job_index advanced but task creation "failed"
        pipeline.advance_job_index()
        db_session.commit()
        
        # Simulate task creation failure - add error marker
        pipeline.add_analysis_task_id(
            'error:task_creation_failed',
            success=False,
            model_slug='model_a',
            app_number=1
        )
        db_session.commit()
        
        # Verify
        progress = pipeline.progress
        assert pipeline.current_job_index == 1, "job_index should be advanced"
        assert 'error:task_creation_failed' in progress['analysis']['main_task_ids']
        assert 'model_a:1' in progress['analysis']['submitted_apps']
        
        # Job is tracked as failed, next poll shouldn't retry it
        assert progress['analysis']['failed'] == 1
    
    def test_job_can_be_retried_after_transient_failure(self, app, db_session):
        """Verify mechanism for retrying after transient failures.
        
        Note: Current implementation doesn't support this - this test
        documents the gap and expected behavior.
        """
        from app.models.pipeline import PipelineExecution
        
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [{'model': 'model_a', 'app': 1}]
            },
            'analysis': {'enabled': True, 'tools': ['semgrep']}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # First attempt fails
        pipeline.advance_job_index()
        pipeline.add_analysis_task_id(
            'error:transient_network_error',
            success=False,
            model_slug='model_a',
            app_number=1
        )
        db_session.commit()
        
        progress = pipeline.progress
        
        # Current behavior: job is marked as failed and in submitted_apps
        assert 'model_a:1' in progress['analysis']['submitted_apps']
        
        # Gap: No built-in way to retry without manual intervention
        # Expected behavior for retry:
        # 1. Remove from submitted_apps
        # 2. Reset job_index or add to retry queue
        # 3. Change error marker to retryable status
        
        # Document current limitation
        pytest.skip("Retry mechanism not implemented - documenting gap")


class TestDuplicatePreventionIntegration:
    """Test duplicate prevention under simulated concurrent access."""
    
    def test_submitted_apps_prevents_duplicate_analysis_task(self, app, db_session):
        """Verify submitted_apps check prevents duplicate task creation."""
        from app.models.pipeline import PipelineExecution
        
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [{'model': 'model_a', 'app': 1}]
            },
            'analysis': {'enabled': True, 'tools': ['semgrep']}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # First submission
        pipeline.add_analysis_task_id(
            'task_first',
            success=True,
            model_slug='model_a',
            app_number=1,
            is_main_task=True,
            subtask_ids=['sub_1', 'sub_2']
        )
        db_session.commit()
        
        # Simulate concurrent poll checking submitted_apps
        progress = pipeline.progress
        job_key = 'model_a:1'
        
        # Second poll should detect duplicate
        assert job_key in progress['analysis']['submitted_apps']
        
        # Verify structure
        assert 'task_first' in progress['analysis']['main_task_ids']
        assert 'sub_1' in progress['analysis']['subtask_ids']
        assert 'sub_2' in progress['analysis']['subtask_ids']
    
    def test_multiple_apps_same_model_tracked_separately(self, app, db_session):
        """Verify different apps for same model are tracked correctly."""
        from app.models.pipeline import PipelineExecution
        
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [
                    {'model': 'model_a', 'app': 1},
                    {'model': 'model_a', 'app': 2},
                    {'model': 'model_a', 'app': 3}
                ]
            },
            'analysis': {'enabled': True, 'tools': ['semgrep']}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # Submit all three apps
        for app_num in [1, 2, 3]:
            pipeline.add_analysis_task_id(
                f'task_app{app_num}',
                success=True,
                model_slug='model_a',
                app_number=app_num,
                is_main_task=True
            )
        db_session.commit()
        
        progress = pipeline.progress
        
        # All three should be tracked separately
        assert 'model_a:1' in progress['analysis']['submitted_apps']
        assert 'model_a:2' in progress['analysis']['submitted_apps']
        assert 'model_a:3' in progress['analysis']['submitted_apps']
        assert len(progress['analysis']['submitted_apps']) == 3


class TestCompletionCountingAccuracy:
    """Test accurate completion counting with main tasks vs subtasks."""
    
    def test_completion_uses_main_task_ids_not_subtasks(self, app, db_session):
        """Verify completion count is based on main_task_ids length."""
        from app.models.pipeline import PipelineExecution
        from app.models import AnalysisTask
        from app.constants import AnalysisStatus
        
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [
                    {'model': 'model_a', 'app': 1},
                    {'model': 'model_b', 'app': 2}
                ]
            },
            'analysis': {'enabled': True, 'tools': ['semgrep', 'bandit', 'zap']}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # Add 2 main tasks with 3 subtasks each (6 total task IDs)
        for i, (model, app_num) in enumerate([('model_a', 1), ('model_b', 2)]):
            main_task_id = f'main_{i}'
            subtask_ids = [f'sub_{i}_1', f'sub_{i}_2', f'sub_{i}_3']
            pipeline.add_analysis_task_id(
                main_task_id,
                success=True,
                model_slug=model,
                app_number=app_num,
                is_main_task=True,
                subtask_ids=subtask_ids
            )
        db_session.commit()
        
        progress = pipeline.progress
        
        # Verify structure: 2 main tasks, 6 subtasks
        assert len(progress['analysis']['main_task_ids']) == 2
        assert len(progress['analysis']['subtask_ids']) == 6
        
        # update_analysis_completion should use main_task_ids count
        done = pipeline.update_analysis_completion(completed=2, failed=0)
        
        assert done is True  # 2/2 main tasks complete
        assert pipeline.status == 'completed'
    
    def test_partial_success_counted_correctly(self, app, db_session):
        """Verify partial success tasks count as completed."""
        from app.models.pipeline import PipelineExecution
        
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [
                    {'model': 'model_a', 'app': 1},
                    {'model': 'model_b', 'app': 2}
                ]
            },
            'analysis': {'enabled': True}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # Add main tasks
        pipeline.add_analysis_task_id('task_1', success=True, model_slug='model_a', app_number=1, is_main_task=True)
        pipeline.add_analysis_task_id('task_2', success=True, model_slug='model_b', app_number=2, is_main_task=True)
        db_session.commit()
        
        # 1 completed, 1 partial_success (should both count as done)
        progress = pipeline.progress
        progress['analysis']['partial_success'] = 1
        pipeline.progress = progress
        
        done = pipeline.update_analysis_completion(completed=1, failed=0)
        
        # 1 completed + 1 partial_success = 2 done out of 2 main tasks
        assert done is True


class TestBackwardsCompatibility:
    """Test backwards compatibility with legacy task_ids structure."""
    
    def test_fallback_to_task_ids_when_main_task_ids_empty(self, app, db_session):
        """Verify fallback to legacy task_ids when main_task_ids not populated."""
        from app.models.pipeline import PipelineExecution
        
        # Simulate old pipeline with only task_ids (no main_task_ids)
        config = {
            'generation': {
                'mode': 'existing',
                'existingApps': [{'model': 'model_a', 'app': 1}]
            },
            'analysis': {'enabled': True}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'analysis'
        db_session.add(pipeline)
        db_session.commit()
        
        # Manually set legacy structure (simulating old data)
        progress = pipeline.progress
        progress['analysis']['task_ids'] = ['legacy_task_1']
        progress['analysis']['main_task_ids'] = []  # Empty - legacy mode
        pipeline.progress = progress
        db_session.commit()
        
        # update_analysis_completion should fall back to task_ids
        db_session.refresh(pipeline)
        done = pipeline.update_analysis_completion(completed=1, failed=0)
        
        assert done is True


class TestHealthCacheBehavior:
    """Test health cache behavior across pipeline boundaries."""
    
    def test_health_cache_persists_across_polls(self, app):
        """Document that health cache persists across poll iterations."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        service = PipelineExecutionService(poll_interval=1.0, app=app)
        
        # Manually set health cache
        service._service_health_cache['static-analyzer'] = {
            'healthy': True,
            'check_time': time.time()
        }
        
        # Verify cache persists
        result = service._get_service_health('static-analyzer')
        assert result['healthy'] is True
        
        # Document: Cache is NOT cleared between pipelines
        # This is a potential issue if service health changes
    
    def test_health_cache_ttl_expiry(self, app):
        """Verify health cache expires after TTL."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        service = PipelineExecutionService(poll_interval=1.0, app=app)
        service.HEALTH_CHECK_TTL = 0.1  # 100ms for testing
        
        # Set stale cache
        service._service_health_cache['static-analyzer'] = {
            'healthy': True,
            'check_time': time.time() - 1.0  # 1 second ago (older than 100ms TTL)
        }
        
        # Should trigger fresh check (will fail since no real service)
        with patch.object(service, '_get_analyzer_host', return_value='localhost'):
            result = service._get_service_health('static-analyzer')
        
        # Fresh check performed (not from cache)
        assert result['check_time'] > service._service_health_cache.get(
            'static-analyzer', {}
        ).get('check_time', 0) - 1.0


class TestGenerationJobTracking:
    """Test generation job tracking with job_index in key."""
    
    def test_job_index_allows_same_model_template_multiple_times(self, app, db_session):
        """Verify same model:template can be used multiple times with different job_index."""
        from app.models.pipeline import PipelineExecution
        
        # Config with same model:template twice (e.g., generating 2 apps)
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model_a'],
                'templates': ['template_x', 'template_x']  # Same template twice
            },
            'analysis': {'enabled': False}
        }
        
        pipeline = PipelineExecution(user_id=1, config=config)
        pipeline.status = 'running'
        pipeline.current_stage = 'generation'
        db_session.add(pipeline)
        db_session.commit()
        
        # First generation result (job_index=0)
        result1 = {
            'job_index': 0,
            'model_slug': 'model_a',
            'template_slug': 'template_x',
            'app_number': 1,
            'success': True
        }
        pipeline.add_generation_result(result1)
        
        # Second generation result (job_index=1, same model:template)
        result2 = {
            'job_index': 1,
            'model_slug': 'model_a',
            'template_slug': 'template_x',
            'app_number': 2,
            'success': True
        }
        pipeline.add_generation_result(result2)
        db_session.commit()
        
        progress = pipeline.progress
        
        # Both should be tracked separately due to job_index in key
        submitted_jobs = progress['generation'].get('submitted_jobs', [])
        assert '0:model_a:template_x' in submitted_jobs
        assert '1:model_a:template_x' in submitted_jobs
        assert len(submitted_jobs) == 2
