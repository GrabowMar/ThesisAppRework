"""
Integration tests for Pipeline Execution and Database Models.

These tests verify:
1. PipelineExecution creation and status tracking
2. GeneratedApplication model operations
3. AnalyzerConfiguration model operations
4. BatchAnalysis model operations
5. AnalysisTask creation and lifecycle

Requirements:
- Database must be configured
"""

import pytest
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

# Mark all tests in this module as integration tests
pytestmark = [pytest.mark.integration]


class TestPipelineExecution:
    """Test PipelineExecution model operations."""
    
    def test_create_pipeline_execution(self, app, db_session):
        """Test creating a new pipeline execution."""
        from app.models import PipelineExecution, PipelineExecutionStatus, User
        
        # Create a user first (required for pipeline)
        user = User(
            username=f'testuser_{uuid.uuid4().hex[:8]}',
            email=f'test_{uuid.uuid4().hex[:8]}@example.com'
        )
        user.set_password('testpass123')
        db_session.add(user)
        db_session.flush()
        
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['test_model'],
                'templates': ['crud_todo_list'],
            },
            'analysis': {
                'enabled': True,
                'tools': ['static'],
            },
        }
        
        pipeline = PipelineExecution(
            user_id=user.id,
            config=config,
            name='Test Pipeline'
        )
        
        db_session.add(pipeline)
        db_session.commit()
        
        assert pipeline.id is not None
        assert pipeline.pipeline_id is not None
        assert pipeline.status == PipelineExecutionStatus.PENDING
        assert pipeline.name == 'Test Pipeline'
        
        # Cleanup
        db_session.delete(pipeline)
        db_session.delete(user)
        db_session.commit()
    
    def test_pipeline_status_transitions(self, app, db_session):
        """Test pipeline status state transitions."""
        from app.models import PipelineExecution, PipelineExecutionStatus, User
        
        user = User(
            username=f'testuser_{uuid.uuid4().hex[:8]}',
            email=f'test_{uuid.uuid4().hex[:8]}@example.com'
        )
        user.set_password('testpass123')
        db_session.add(user)
        db_session.flush()
        
        pipeline = PipelineExecution(
            user_id=user.id,
            config={'generation': {'mode': 'generate', 'models': [], 'templates': []}},
            name='Status Test'
        )
        db_session.add(pipeline)
        db_session.commit()
        
        # PENDING -> RUNNING
        pipeline.start()
        db_session.commit()
        assert pipeline.status == PipelineExecutionStatus.RUNNING
        assert pipeline.started_at is not None
        
        # RUNNING -> COMPLETED
        pipeline.status = PipelineExecutionStatus.COMPLETED
        pipeline.completed_at = datetime.now(timezone.utc)
        db_session.commit()
        assert pipeline.status == PipelineExecutionStatus.COMPLETED
        
        # Cleanup
        db_session.delete(pipeline)
        db_session.delete(user)
        db_session.commit()
    
    def test_pipeline_progress_tracking(self, app, db_session):
        """Test pipeline progress calculation."""
        from app.models import PipelineExecution, User
        
        user = User(
            username=f'testuser_{uuid.uuid4().hex[:8]}',
            email=f'test_{uuid.uuid4().hex[:8]}@example.com'
        )
        user.set_password('testpass123')
        db_session.add(user)
        db_session.flush()
        
        config = {
            'generation': {
                'mode': 'generate',
                'models': ['model1', 'model2'],
                'templates': ['t1', 't2'],  # 4 total jobs
            },
            'analysis': {
                'enabled': True,
            },
        }
        
        pipeline = PipelineExecution(user_id=user.id, config=config)
        db_session.add(pipeline)
        db_session.commit()
        
        # Initial progress should be 0
        assert pipeline.get_overall_progress() == 0.0
        
        # Add 2 generation results (50% of generation = 25% overall)
        pipeline.add_generation_result({'success': True, 'model_slug': 'model1', 'template_slug': 't1', 'job_index': 0})
        pipeline.add_generation_result({'success': True, 'model_slug': 'model1', 'template_slug': 't2', 'job_index': 1})
        db_session.commit()
        
        progress = pipeline.get_overall_progress()
        assert progress == 25.0  # 2/4 generation done = 50% * 0.5 weight = 25%
        
        # Cleanup
        db_session.delete(pipeline)
        db_session.delete(user)
        db_session.commit()


class TestPipelineTaskRelationship:
    """Test relationships between pipelines and tasks."""
    
    def test_pipeline_has_tasks(self, app, db_session):
        """Test that pipeline can have associated tasks."""
        from app.models import PipelineExecution, AnalysisTask, AnalysisStatus, AnalyzerConfiguration, User
        
        # Create user
        user = User(
            username=f'testuser_{uuid.uuid4().hex[:8]}',
            email=f'test_{uuid.uuid4().hex[:8]}@example.com'
        )
        user.set_password('testpass123')
        db_session.add(user)
        db_session.flush()
        
        # Create analyzer config first (required by AnalysisTask)
        config = AnalyzerConfiguration.query.first()
        if not config:
            config = AnalyzerConfiguration(
                name='TestConfig',
                config_data='{}'
            )
            db_session.add(config)
            db_session.flush()
        
        # Create pipeline
        pipeline = PipelineExecution(
            user_id=user.id,
            config={'generation': {'mode': 'generate', 'models': [], 'templates': []}},
        )
        db_session.add(pipeline)
        db_session.flush()
        
        # Create task linked to this pipeline via batch_id
        task = AnalysisTask(
            task_id=f'test_task_{pipeline.pipeline_id}',
            task_name='test',
            status=AnalysisStatus.PENDING,
            target_model='test_model',
            target_app_number=1,
            analyzer_config_id=config.id,
            batch_id=pipeline.pipeline_id  # Link via pipeline_id
        )
        db_session.add(task)
        db_session.commit()
        
        # Verify task was created
        assert task.id is not None
        assert task.batch_id == pipeline.pipeline_id
        
        # Cleanup
        db_session.delete(task)
        db_session.delete(pipeline)
        db_session.delete(user)
        db_session.commit()


class TestGeneratedApplicationModel:
    """Test GeneratedApplication model operations."""
    
    def test_create_generated_application(self, app, db_session):
        """Test creating a generated application record."""
        from app.models import GeneratedApplication, AnalysisStatus
        
        gen_app = GeneratedApplication(
            model_slug='test_model_integration',
            app_number=999,
            app_type='fullstack',
            provider='test',
            template_slug='crud_todo_list',
            generation_status=AnalysisStatus.COMPLETED,
        )
        db_session.add(gen_app)
        db_session.commit()
        
        assert gen_app.id is not None
        assert gen_app.model_slug == 'test_model_integration'
        assert gen_app.generation_status == AnalysisStatus.COMPLETED
        
        # Cleanup
        db_session.delete(gen_app)
        db_session.commit()
    
    def test_generated_app_unique_constraint(self, app, db_session):
        """Test that model_slug + app_number + version is unique."""
        from app.models import GeneratedApplication
        from sqlalchemy.exc import IntegrityError
        
        unique_slug = f'unique_test_{uuid.uuid4().hex[:8]}'
        
        gen_app1 = GeneratedApplication(
            model_slug=unique_slug,
            app_number=1,
            version=1,
            app_type='fullstack',
            provider='test',
            template_slug='test',
        )
        db_session.add(gen_app1)
        db_session.commit()
        
        # Try to create duplicate (same model, app, version)
        gen_app2 = GeneratedApplication(
            model_slug=unique_slug,
            app_number=1,
            version=1,  # Same version
            app_type='fullstack',
            provider='test',
        )
        db_session.add(gen_app2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
        
        db_session.rollback()
        
        # Cleanup
        db_session.delete(gen_app1)
        db_session.commit()
    
    def test_generated_app_to_dict(self, app, db_session):
        """Test serialization to dictionary."""
        from app.models import GeneratedApplication
        
        gen_app = GeneratedApplication(
            model_slug='dict_test_model',
            app_number=100,
            app_type='fullstack',
            provider='test',
            has_backend=True,
            has_frontend=True,
            backend_framework='flask',
        )
        db_session.add(gen_app)
        db_session.commit()
        
        data = gen_app.to_dict()
        
        assert data['model_slug'] == 'dict_test_model'
        assert data['app_number'] == 100
        assert data['has_backend'] is True
        assert data['has_frontend'] is True
        assert data['backend_framework'] == 'flask'
        
        # Cleanup
        db_session.delete(gen_app)
        db_session.commit()


class TestAnalyzerConfiguration:
    """Test AnalyzerConfiguration model."""
    
    def test_create_analyzer_config(self, app, db_session):
        """Test creating analyzer configuration."""
        from app.models import AnalyzerConfiguration
        
        config = AnalyzerConfiguration(
            name=f'Test Config {uuid.uuid4().hex[:8]}',
            config_data='{"tools": ["bandit", "semgrep"]}'
        )
        db_session.add(config)
        db_session.commit()
        
        assert config.id is not None
        assert 'Test Config' in config.name
        
        # Cleanup
        db_session.delete(config)
        db_session.commit()
    
    def test_analyzer_config_default_exists(self, app, db_session):
        """Test that a default analyzer config exists or can be created."""
        from app.models import AnalyzerConfiguration
        
        config = AnalyzerConfiguration.query.first()
        
        if config is None:
            # Create default if not exists
            config = AnalyzerConfiguration(
                name='AutoDefault-Universal',
                config_data='{}'
            )
            db_session.add(config)
            db_session.commit()
        
        assert config is not None


class TestModelCapability:
    """Test ModelCapability model operations."""
    
    def test_create_model_capability(self, app, db_session):
        """Test creating a model capability record."""
        from app.models import ModelCapability
        
        unique_id = f'test/model-{uuid.uuid4().hex[:8]}'
        unique_slug = f'test_model-{uuid.uuid4().hex[:8]}'
        
        model = ModelCapability(
            model_id=unique_id,
            canonical_slug=unique_slug,
            provider='test',
            model_name='Test Model',
            context_window=4096,
            is_free=True,
        )
        db_session.add(model)
        db_session.commit()
        
        assert model.id is not None
        assert model.model_id == unique_id
        assert model.context_window == 4096
        
        # Cleanup
        db_session.delete(model)
        db_session.commit()
    
    def test_model_capability_metadata(self, app, db_session):
        """Test model capability JSON metadata."""
        from app.models import ModelCapability
        
        unique_id = f'test/model-meta-{uuid.uuid4().hex[:8]}'
        unique_slug = f'test_model-meta-{uuid.uuid4().hex[:8]}'
        
        model = ModelCapability(
            model_id=unique_id,
            canonical_slug=unique_slug,
            provider='test',
            model_name='Metadata Test Model',
        )
        
        # Test metadata
        model.set_metadata({'source': 'integration_test', 'version': '1.0'})
        db_session.add(model)
        db_session.commit()
        
        # Refresh and verify
        db_session.refresh(model)
        metadata = model.get_metadata()
        assert metadata['source'] == 'integration_test'
        assert metadata['version'] == '1.0'
        
        # Cleanup
        db_session.delete(model)
        db_session.commit()


class TestBatchAnalysis:
    """Test batch analysis operations."""
    
    def test_create_batch(self, app, db_session):
        """Test creating a batch analysis record."""
        from app.models import BatchAnalysis, JobStatus
        
        batch = BatchAnalysis(
            batch_id=f'test_batch_{uuid.uuid4().hex[:8]}',
            status=JobStatus.PENDING,
            total_tasks=5,
            completed_tasks=0,
        )
        db_session.add(batch)
        db_session.commit()
        
        assert batch.id is not None
        assert batch.status == JobStatus.PENDING
        
        # Cleanup
        db_session.delete(batch)
        db_session.commit()
    
    def test_batch_progress_update(self, app, db_session):
        """Test updating batch progress."""
        from app.models import BatchAnalysis, JobStatus
        
        batch = BatchAnalysis(
            batch_id=f'progress_test_{uuid.uuid4().hex[:8]}',
            status=JobStatus.RUNNING,
            total_tasks=10,
            completed_tasks=0
        )
        db_session.add(batch)
        db_session.commit()
        
        # Update progress
        batch.completed_tasks = 5
        batch.progress_percentage = 50.0
        db_session.commit()
        
        # Refresh and verify
        db_session.refresh(batch)
        assert batch.completed_tasks == 5
        assert batch.progress_percentage == 50.0
        
        # Cleanup
        db_session.delete(batch)
        db_session.commit()
    
    def test_batch_analysis_types(self, app, db_session):
        """Test analysis types JSON field."""
        from app.models import BatchAnalysis, JobStatus
        
        batch = BatchAnalysis(
            batch_id=f'types_test_{uuid.uuid4().hex[:8]}',
            status=JobStatus.PENDING,
            total_tasks=3,
        )
        
        # Set analysis types
        batch.set_analysis_types(['static', 'dynamic', 'performance'])
        db_session.add(batch)
        db_session.commit()
        
        # Retrieve and verify
        db_session.refresh(batch)
        types = batch.get_analysis_types()
        assert 'static' in types
        assert 'dynamic' in types
        assert 'performance' in types
        
        # Cleanup
        db_session.delete(batch)
        db_session.commit()


class TestAnalysisTask:
    """Test AnalysisTask model operations."""
    
    def test_create_analysis_task(self, app, db_session):
        """Test creating an analysis task."""
        from app.models import AnalysisTask, AnalysisStatus, AnalyzerConfiguration
        
        # Ensure config exists
        config = AnalyzerConfiguration.query.first()
        if not config:
            config = AnalyzerConfiguration(name='DefaultTest', config_data='{}')
            db_session.add(config)
            db_session.flush()
        
        task = AnalysisTask(
            task_id=f'task_{uuid.uuid4().hex[:12]}',
            task_name='comprehensive',
            status=AnalysisStatus.PENDING,
            target_model='test_model',
            target_app_number=1,
            analyzer_config_id=config.id,
        )
        db_session.add(task)
        db_session.commit()
        
        assert task.id is not None
        assert task.status == AnalysisStatus.PENDING
        assert task.task_name == 'comprehensive'
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()
    
    def test_task_status_transitions(self, app, db_session):
        """Test analysis task status transitions."""
        from app.models import AnalysisTask, AnalysisStatus, AnalyzerConfiguration
        
        config = AnalyzerConfiguration.query.first()
        if not config:
            config = AnalyzerConfiguration(name='DefaultTest', config_data='{}')
            db_session.add(config)
            db_session.flush()
        
        task = AnalysisTask(
            task_id=f'task_{uuid.uuid4().hex[:12]}',
            task_name='static',
            status=AnalysisStatus.PENDING,
            target_model='test_model',
            target_app_number=1,
            analyzer_config_id=config.id,
        )
        db_session.add(task)
        db_session.commit()
        
        # PENDING -> RUNNING
        task.start_execution()
        db_session.commit()
        assert task.status == AnalysisStatus.RUNNING
        assert task.started_at is not None
        
        # RUNNING -> COMPLETED
        task.complete_execution(success=True)
        task.total_issues = 5  # Set separately
        db_session.commit()
        assert task.status == AnalysisStatus.COMPLETED
        assert task.total_issues == 5
        
        # Cleanup
        db_session.delete(task)
        db_session.commit()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
