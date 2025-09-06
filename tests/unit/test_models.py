"""
Model Tests
===========

Unit tests for database models and their methods.
"""

import pytest
from datetime import datetime


@pytest.mark.unit
@pytest.mark.db
class TestModelCapability:
    """Test ModelCapability model."""

    def test_create_model_capability(self, db_session):
        """Test creating a model capability."""
        from tests.conftest import create_test_model_capability
        
        model = create_test_model_capability(
            db_session,
            model_name='test-gpt-4',
            provider='openai',
            model_id='gpt-4'
        )
        
        assert model.id is not None
        assert model.model_name == 'test-gpt-4'
        assert model.provider == 'openai'
        assert model.model_id == 'gpt-4'

    def test_model_capability_repr(self, db_session):
        """Test model capability string representation."""
        from tests.conftest import create_test_model_capability
        
        model = create_test_model_capability(db_session, model_id='gpt-4')
        
        assert 'gpt-4' in repr(model)

    def test_model_capability_capabilities_json(self, db_session):
        """Test model capability JSON capabilities handling."""
        from tests.conftest import create_test_model_capability
        
        model = create_test_model_capability(db_session)
        
        # Test setting capabilities
        capabilities = {'text-generation': True, 'code-completion': True}
        model.set_capabilities(capabilities)
        db_session.commit()
        
        # Test getting capabilities
        retrieved_caps = model.get_capabilities()
        assert retrieved_caps == capabilities


@pytest.mark.unit
@pytest.mark.db
class TestGeneratedApplication:
    """Test GeneratedApplication model."""

    def test_create_generated_application(self, db_session):
        """Test creating a generated application."""
        from tests.conftest import create_test_generated_application
        from app.constants import AnalysisStatus
        
        app = create_test_generated_application(
            db_session,
            model_slug='gpt-4',
            app_number=1,
            app_type='web',
            provider='openai',
            generation_status=AnalysisStatus.COMPLETED
        )
        
        assert app.id is not None
        assert app.model_slug == 'gpt-4'
        assert app.app_number == 1
        assert app.app_type == 'web'
        assert app.generation_status == AnalysisStatus.COMPLETED

    def test_generated_application_timestamps(self, db_session):
        """Test application timestamp handling."""
        from tests.conftest import create_test_generated_application
        
        app = create_test_generated_application(db_session)
        
        assert app.created_at is not None
        assert app.updated_at is not None
        assert isinstance(app.created_at, datetime)
        assert isinstance(app.updated_at, datetime)

    def test_application_metadata_handling(self, db_session):
        """Test application metadata JSON handling."""
        from tests.conftest import create_test_generated_application
        
        app = create_test_generated_application(db_session)
        
        # Test setting metadata
        metadata = {'version': '1.0', 'features': ['auth', 'db']}
        app.set_metadata(metadata)
        db_session.commit()
        
        # Test getting metadata
        retrieved_metadata = app.get_metadata()
        assert retrieved_metadata == metadata


@pytest.mark.unit
@pytest.mark.db
class TestSecurityAnalysis:
    """Test SecurityAnalysis model."""

    def test_create_security_analysis(self, db_session):
        """Test creating a security analysis."""
        from app.models import SecurityAnalysis
        from app.constants import AnalysisStatus
        from tests.conftest import create_test_generated_application
        
        # Create associated application first
        app = create_test_generated_application(db_session)
        
        # Create security analysis using direct field assignment
        analysis = SecurityAnalysis()
        analysis.application_id = app.id
        analysis.status = AnalysisStatus.COMPLETED
        
        db_session.add(analysis)
        db_session.commit()
        
        assert analysis.id is not None
        assert analysis.application_id == app.id
        assert analysis.status == AnalysisStatus.COMPLETED

    def test_security_analysis_bandit_config(self, db_session):
        """Test security analysis bandit configuration."""
        from app.models import SecurityAnalysis
        from tests.conftest import create_test_generated_application
        
        app = create_test_generated_application(db_session)
        analysis = SecurityAnalysis()
        analysis.application_id = app.id
        
        db_session.add(analysis)
        db_session.commit()
        
        # Test bandit config
        bandit_config = {'tests': ['B101'], 'severity': 'high'}
        analysis.set_bandit_config(bandit_config)
        db_session.commit()
        
        retrieved_config = analysis.get_bandit_config()
        assert 'tests' in retrieved_config
        assert retrieved_config['tests'] == ['B101']


@pytest.mark.unit
@pytest.mark.db
class TestPerformanceTest:
    """Test PerformanceTest model."""

    def test_create_performance_test(self, db_session):
        """Test creating a performance test."""
        from app.models import PerformanceTest
        from app.constants import AnalysisStatus
        from tests.conftest import create_test_generated_application
        
        app = create_test_generated_application(db_session)
        
        perf_test = PerformanceTest()
        perf_test.application_id = app.id
        perf_test.status = AnalysisStatus.COMPLETED
        perf_test.test_type = 'load'
        
        db_session.add(perf_test)
        db_session.commit()
        
        assert perf_test.id is not None
        assert perf_test.application_id == app.id
        assert perf_test.test_type == 'load'

    def test_performance_test_results(self, db_session):
        """Test performance test results handling."""
        from app.models import PerformanceTest
        from tests.conftest import create_test_generated_application
        
        app = create_test_generated_application(db_session)
        perf_test = PerformanceTest()
        perf_test.application_id = app.id
        
        db_session.add(perf_test)
        db_session.commit()
        
        # Test results JSON handling
        results = {'rps': 100, 'avg_response': 200}
        perf_test.set_results(results)
        db_session.commit()
        
        retrieved_results = perf_test.get_results()
        assert retrieved_results['rps'] == 100


@pytest.mark.unit
class TestModelUtilities:
    """Test model utility functions."""

    def test_utc_now_function(self):
        """Test UTC now utility function."""
        from app.models import utc_now
        
        now = utc_now()
        
        assert isinstance(now, datetime)
        assert now.tzinfo is not None

    def test_model_imports(self):
        """Test that all models can be imported."""
        from app.models import (
            ModelCapability,
            GeneratedApplication,
            SecurityAnalysis,
            PerformanceTest
        )
        
        # All imports should succeed
        assert ModelCapability is not None
        assert GeneratedApplication is not None
        assert SecurityAnalysis is not None
        assert PerformanceTest is not None