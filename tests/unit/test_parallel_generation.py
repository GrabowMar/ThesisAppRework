"""Unit tests for parallel generation execution in pipelines.

These tests verify that the parallel generation execution is correctly
configured and works as expected.
"""

import pytest
from unittest.mock import MagicMock, patch
import json


class TestParallelGenerationConfig:
    """Test parallel generation configuration."""
    
    def test_generation_options_default_parallel_true(self):
        """Verify generation options default to parallel=True."""
        # Default config without explicit options
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model_a'],
                'templates': ['template_a'],
            },
            'analysis': {
                'enabled': True,
                'tools': ['bandit'],
            }
        }
        
        gen_options = config.get('generation', {}).get('options', {})
        parallel = gen_options.get('parallel', True)  # Default is True
        max_concurrent = gen_options.get('maxConcurrentTasks', 2)  # Default is 2
        
        assert parallel is True
        assert max_concurrent == 2
    
    def test_generation_options_explicit_values(self):
        """Verify explicit generation options are respected."""
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model_a', 'model_b'],
                'templates': ['template_a', 'template_b'],
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 3
                }
            },
        }
        
        gen_options = config.get('generation', {}).get('options', {})
        parallel = gen_options.get('parallel', True)
        max_concurrent = gen_options.get('maxConcurrentTasks', 2)
        
        assert parallel is True
        assert max_concurrent == 3
    
    def test_generation_options_sequential_mode(self):
        """Verify sequential mode sets maxConcurrent to 1."""
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model_a'],
                'templates': ['template_a'],
                'options': {
                    'parallel': False,
                    'maxConcurrentTasks': 3  # Should be ignored
                }
            },
        }
        
        gen_options = config.get('generation', {}).get('options', {})
        gen_use_parallel = gen_options.get('parallel', True)
        gen_max_concurrent = gen_options.get('maxConcurrentTasks', 2) if gen_use_parallel else 1
        
        assert gen_use_parallel is False
        assert gen_max_concurrent == 1


class TestPipelineProgressGeneration:
    """Test pipeline progress with generation parallelism tracking."""
    
    def test_progress_includes_generation_parallelism(self):
        """Verify progress includes generation parallelism settings."""
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model_a', 'model_b'],
                'templates': ['template_a'],
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 2
                }
            },
            'analysis': {
                'enabled': True,
                'tools': ['bandit'],
                'options': {
                    'parallel': True,
                    'maxConcurrentTasks': 2  # 2x2 parallelism (matching generation)
                }
            }
        }
        
        # Simulate progress initialization from pipeline model
        gen_config = config.get('generation', {})
        models = gen_config.get('models', [])
        templates = gen_config.get('templates', [])
        total_generation_jobs = len(models) * len(templates)
        
        gen_options = gen_config.get('options', {})
        gen_use_parallel = gen_options.get('parallel', True)
        gen_max_concurrent = gen_options.get('maxConcurrentTasks', 2) if gen_use_parallel else 1
        
        analysis_enabled = config.get('analysis', {}).get('enabled', True)
        analysis_options = config.get('analysis', {}).get('options', {})
        max_concurrent = analysis_options.get('maxConcurrentTasks', 2)  # Now defaults to 2
        use_parallel = analysis_options.get('parallel', True)
        
        progress = {
            'generation': {
                'total': total_generation_jobs,
                'completed': 0,
                'failed': 0,
                'status': 'pending',
                'results': [],
                'max_concurrent': gen_max_concurrent,
                'in_flight': 0,
            },
            'analysis': {
                'total': total_generation_jobs if analysis_enabled else 0,
                'completed': 0,
                'failed': 0,
                'status': 'pending' if analysis_enabled else 'skipped',
                'task_ids': [],
                'max_concurrent': max_concurrent if use_parallel else 1,
                'in_flight': 0,
            },
        }
        
        # Verify generation settings
        assert progress['generation']['total'] == 2  # 2 models * 1 template
        assert progress['generation']['max_concurrent'] == 2
        assert progress['generation']['in_flight'] == 0
        
        # Verify analysis settings
        assert progress['analysis']['total'] == 2
        assert progress['analysis']['max_concurrent'] == 2  # Now 2x2 parallelism


class TestPipelineExecutionService:
    """Test PipelineExecutionService parallel generation methods."""
    
    def test_service_has_generation_executor(self):
        """Verify service initializes with generation executor."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        svc = PipelineExecutionService(poll_interval=1.0)
        
        # Check attributes exist
        assert hasattr(svc, '_generation_executor')
        assert hasattr(svc, '_generation_futures')
        assert hasattr(svc, '_in_flight_generation')
        
        # Initially None until started
        assert svc._generation_executor is None
        assert svc._generation_futures == {}
        assert svc._in_flight_generation == {}
    
    def test_service_starts_generation_executor(self):
        """Verify service starts generation executor when started."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        svc = PipelineExecutionService(poll_interval=1.0)
        svc.start()
        
        try:
            # Executor should be created
            assert svc._generation_executor is not None
            assert svc._analysis_executor is not None
        finally:
            svc.stop()
    
    def test_service_stops_generation_executor(self):
        """Verify service properly shuts down generation executor."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        svc = PipelineExecutionService(poll_interval=1.0)
        svc.start()
        svc.stop()
        
        # Executor should be None after stop
        assert svc._generation_executor is None
        assert svc._analysis_executor is None
    
    def test_cleanup_generation_tracking(self):
        """Verify cleanup_generation_tracking clears tracking state."""
        from app.services.pipeline_execution_service import PipelineExecutionService
        
        svc = PipelineExecutionService(poll_interval=1.0)
        
        # Simulate tracking state
        pipeline_id = 'test_pipeline_123'
        svc._in_flight_generation[pipeline_id] = {'job_key_1', 'job_key_2'}
        svc._generation_futures[pipeline_id] = {}
        
        # Call cleanup
        svc._cleanup_generation_tracking(pipeline_id)
        
        # Verify cleanup
        assert pipeline_id not in svc._in_flight_generation
        assert pipeline_id not in svc._generation_futures
