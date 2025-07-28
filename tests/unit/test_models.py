"""
Unit tests for database models.

Tests all model classes including their JSON field helpers,
validation methods, and database operations.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import patch

from models import (
    ModelCapability, PortConfiguration, GeneratedApplication,
    SecurityAnalysis, PerformanceTest, BatchAnalysis,
    AnalysisStatus, SeverityLevel
)
from extensions import db


class TestModelCapability:
    """Test ModelCapability model."""
    
    def test_create_model_capability(self, init_database):
        """Test creating a model capability."""
        model = ModelCapability(
            model_id='test-model',
            canonical_slug='test_model',
            provider='openai',
            model_name='Test Model',
            is_free=False,
            context_window=4096,
            max_output_tokens=2048,
            supports_function_calling=True,
            input_price_per_token=0.001,
            output_price_per_token=0.002
        )
        
        db.session.add(model)
        db.session.commit()
        
        assert model.id is not None
        assert model.model_id == 'test-model'
        assert model.canonical_slug == 'test_model'
        assert model.provider == 'openai'
        assert model.is_free is False
        assert model.context_window == 4096
        assert model.supports_function_calling is True
    
    def test_capabilities_json_helpers(self, init_database):
        """Test JSON capabilities helper methods."""
        model = ModelCapability(
            model_id='test-model',
            canonical_slug='test_model',
            provider='openai',
            model_name='Test Model'
        )
        
        # Test setting and getting capabilities
        capabilities = {
            'text_generation': True,
            'code_completion': True,
            'image_analysis': False
        }
        
        model.set_capabilities(capabilities)
        retrieved_capabilities = model.get_capabilities()
        
        assert retrieved_capabilities == capabilities
        assert model.capabilities_json is not None
    
    def test_metadata_json_helpers(self, init_database):
        """Test JSON metadata helper methods."""
        model = ModelCapability(
            model_id='test-model',
            canonical_slug='test_model',
            provider='openai',
            model_name='Test Model'
        )
        
        # Test setting and getting metadata
        metadata = {
            'last_updated': '2024-01-01',
            'performance_benchmarks': {
                'latency': 150,
                'throughput': 100
            }
        }
        
        model.set_metadata(metadata)
        retrieved_metadata = model.get_metadata()
        
        assert retrieved_metadata == metadata
        assert model.metadata_json is not None
    
    def test_to_dict_method(self, init_database):
        """Test to_dict method."""
        model = ModelCapability(
            model_id='test-model',
            canonical_slug='test_model',
            provider='openai',
            model_name='Test Model',
            is_free=True,
            context_window=8192
        )
        
        capabilities = {'text': True}
        metadata = {'version': '1.0'}
        
        model.set_capabilities(capabilities)
        model.set_metadata(metadata)
        
        db.session.add(model)
        db.session.commit()
        
        model_dict = model.to_dict()
        
        assert model_dict['model_id'] == 'test-model'
        assert model_dict['canonical_slug'] == 'test_model'
        assert model_dict['provider'] == 'openai'
        assert model_dict['is_free'] is True
        assert model_dict['context_window'] == 8192
        assert model_dict['capabilities'] == capabilities
        assert model_dict['metadata'] == metadata
        assert 'created_at' in model_dict
        assert 'updated_at' in model_dict
    
    def test_invalid_json_handling(self, init_database):
        """Test handling of invalid JSON in capabilities/metadata fields."""
        model = ModelCapability(
            model_id='test-model',
            canonical_slug='test_model',
            provider='openai',
            model_name='Test Model'
        )
        
        # Manually set invalid JSON
        model.capabilities_json = 'invalid json'
        model.metadata_json = 'invalid json'
        
        # Should return empty dict for invalid JSON
        assert model.get_capabilities() == {}
        assert model.get_metadata() == {}


class TestPortConfiguration:
    """Test PortConfiguration model."""
    
    def test_create_port_configuration(self, init_database):
        """Test creating a port configuration."""
        port_config = PortConfiguration(
            frontend_port=3000,
            backend_port=5000,
            is_available=True
        )
        
        db.session.add(port_config)
        db.session.commit()
        
        assert port_config.id is not None
        assert port_config.frontend_port == 3000
        assert port_config.backend_port == 5000
        assert port_config.is_available is True
    
    def test_metadata_json_helpers(self, init_database):
        """Test JSON metadata helper methods."""
        port_config = PortConfiguration(
            frontend_port=3000,
            backend_port=5000
        )
        
        metadata = {
            'docker_compose_path': '/path/to/docker-compose.yml',
            'container_names': ['frontend', 'backend']
        }
        
        port_config.set_metadata(metadata)
        retrieved_metadata = port_config.get_metadata()
        
        assert retrieved_metadata == metadata
    
    def test_to_dict_method(self, init_database):
        """Test to_dict method."""
        port_config = PortConfiguration(
            frontend_port=3000,
            backend_port=5000,
            is_available=False
        )
        
        metadata = {'test': 'value'}
        port_config.set_metadata(metadata)
        
        db.session.add(port_config)
        db.session.commit()
        
        config_dict = port_config.to_dict()
        
        assert config_dict['frontend_port'] == 3000
        assert config_dict['backend_port'] == 5000
        assert config_dict['is_available'] is False
        assert config_dict['metadata'] == metadata
        assert 'created_at' in config_dict
    
    def test_unique_constraints(self, init_database):
        """Test unique constraints on ports."""
        # Create first port config
        port_config1 = PortConfiguration(
            frontend_port=3000,
            backend_port=5000
        )
        db.session.add(port_config1)
        db.session.commit()
        
        # Try to create another with same frontend port
        port_config2 = PortConfiguration(
            frontend_port=3000,  # Same as above
            backend_port=5001
        )
        db.session.add(port_config2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db.session.commit()


class TestGeneratedApplication:
    """Test GeneratedApplication model."""
    
    def test_create_generated_application(self, init_database):
        """Test creating a generated application."""
        app = GeneratedApplication(
            model_slug='test_model',
            app_number=1,
            app_type='chat_application',
            provider='openai',
            generation_status='completed',
            has_backend=True,
            has_frontend=True,
            backend_framework='Flask',
            frontend_framework='React'
        )
        
        db.session.add(app)
        db.session.commit()
        
        assert app.id is not None
        assert app.model_slug == 'test_model'
        assert app.app_number == 1
        assert app.app_type == 'chat_application'
        assert app.has_backend is True
        assert app.has_frontend is True
    
    def test_metadata_helpers(self, init_database):
        """Test metadata helper methods."""
        app = GeneratedApplication(
            model_slug='test_model',
            app_number=1,
            app_type='test_app',
            provider='test'
        )
        
        metadata = {
            'directory_path': 'misc/models/test_model/app1',
            'ports': {'frontend': 3000, 'backend': 5000},
            'docker_info': {'compose_file': 'docker-compose.yml'}
        }
        
        app.set_metadata(metadata)
        retrieved_metadata = app.get_metadata()
        
        assert retrieved_metadata == metadata
    
    def test_get_directory_path(self, init_database):
        """Test get_directory_path method."""
        app = GeneratedApplication(
            model_slug='test_model',
            app_number=5,
            app_type='test_app',
            provider='test'
        )
        
        # Test default path
        default_path = app.get_directory_path()
        assert default_path == 'misc/models/test_model/app5'
        
        # Test custom path from metadata
        custom_metadata = {'directory_path': 'custom/path/to/app'}
        app.set_metadata(custom_metadata)
        custom_path = app.get_directory_path()
        assert custom_path == 'custom/path/to/app'
    
    def test_get_ports(self, init_database):
        """Test get_ports method."""
        app = GeneratedApplication(
            model_slug='test_model',
            app_number=1,
            app_type='test_app',
            provider='test'
        )
        
        # Test default (empty) ports
        default_ports = app.get_ports()
        assert default_ports == {}
        
        # Test custom ports from metadata
        ports_metadata = {'ports': {'frontend': 3000, 'backend': 5000}}
        app.set_metadata(ports_metadata)
        custom_ports = app.get_ports()
        assert custom_ports == {'frontend': 3000, 'backend': 5000}
    
    def test_unique_constraint(self, init_database):
        """Test unique constraint on model_slug + app_number."""
        # Create first app
        app1 = GeneratedApplication(
            model_slug='test_model',
            app_number=1,
            app_type='test_app1',
            provider='test'
        )
        db.session.add(app1)
        db.session.commit()
        
        # Try to create another with same model_slug + app_number
        app2 = GeneratedApplication(
            model_slug='test_model',
            app_number=1,  # Same combination
            app_type='test_app2',
            provider='test'
        )
        db.session.add(app2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db.session.commit()
    
    def test_relationships(self, init_database):
        """Test relationships with other models."""
        app = GeneratedApplication(
            model_slug='test_model',
            app_number=1,
            app_type='test_app',
            provider='test'
        )
        db.session.add(app)
        db.session.commit()
        
        # Create related security analysis
        security_analysis = SecurityAnalysis(
            application_id=app.id,
            status=AnalysisStatus.COMPLETED
        )
        db.session.add(security_analysis)
        
        # Create related performance test
        performance_test = PerformanceTest(
            application_id=app.id,
            status=AnalysisStatus.COMPLETED
        )
        db.session.add(performance_test)
        db.session.commit()
        
        # Test relationships
        assert len(app.security_analyses) == 1
        assert len(app.performance_tests) == 1
        assert app.security_analyses[0].id == security_analysis.id
        assert app.performance_tests[0].id == performance_test.id


class TestSecurityAnalysis:
    """Test SecurityAnalysis model."""
    
    def test_create_security_analysis(self, init_database, sample_generated_application):
        """Test creating a security analysis."""
        db.session.add(sample_generated_application)
        db.session.commit()
        
        analysis = SecurityAnalysis(
            application_id=sample_generated_application.id,
            status=AnalysisStatus.RUNNING,
            bandit_enabled=True,
            safety_enabled=True,
            total_issues=10,
            critical_severity_count=2,
            high_severity_count=3,
            analysis_duration=120.5
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        assert analysis.id is not None
        assert analysis.application_id == sample_generated_application.id
        assert analysis.status == AnalysisStatus.RUNNING
        assert analysis.bandit_enabled is True
        assert analysis.total_issues == 10
        assert analysis.critical_severity_count == 2
    
    def test_enabled_tools_helpers(self, init_database):
        """Test enabled tools helper methods."""
        analysis = SecurityAnalysis()
        
        tools = {
            'bandit': True,
            'safety': False,
            'pylint': True,
            'eslint': False,
            'npm_audit': True,
            'snyk': False
        }
        
        analysis.set_enabled_tools(tools)
        retrieved_tools = analysis.get_enabled_tools()
        
        assert retrieved_tools == tools
        assert analysis.bandit_enabled is True
        assert analysis.safety_enabled is False
        assert analysis.pylint_enabled is True
    
    def test_results_json_helpers(self, init_database):
        """Test results JSON helper methods."""
        analysis = SecurityAnalysis()
        
        results = {
            'bandit': {
                'issues': [
                    {'severity': 'high', 'confidence': 'high', 'test_id': 'B101'}
                ]
            },
            'safety': {
                'vulnerabilities': []
            }
        }
        
        analysis.set_results(results)
        retrieved_results = analysis.get_results()
        
        assert retrieved_results == results
    
    def test_to_dict_method(self, init_database, sample_generated_application):
        """Test to_dict method."""
        db.session.add(sample_generated_application)
        db.session.commit()
        
        analysis = SecurityAnalysis(
            application_id=sample_generated_application.id,
            status=AnalysisStatus.COMPLETED,
            total_issues=5,
            critical_severity_count=1,
            high_severity_count=2,
            medium_severity_count=1,
            low_severity_count=1
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        analysis_dict = analysis.to_dict()
        
        assert analysis_dict['application_id'] == sample_generated_application.id
        assert analysis_dict['status'] == 'completed'
        assert analysis_dict['total_issues'] == 5
        assert 'severity_breakdown' in analysis_dict
        assert analysis_dict['severity_breakdown']['critical'] == 1
        assert analysis_dict['severity_breakdown']['high'] == 2
        assert 'enabled_tools' in analysis_dict


class TestPerformanceTest:
    """Test PerformanceTest model."""
    
    def test_create_performance_test(self, init_database, sample_generated_application):
        """Test creating a performance test."""
        db.session.add(sample_generated_application)
        db.session.commit()
        
        test = PerformanceTest(
            application_id=sample_generated_application.id,
            status=AnalysisStatus.COMPLETED,
            test_type='load_test',
            target_users=50,
            duration_seconds=120,
            requests_per_second=200.5,
            average_response_time=150.3,
            error_rate_percent=0.8
        )
        
        db.session.add(test)
        db.session.commit()
        
        assert test.id is not None
        assert test.application_id == sample_generated_application.id
        assert test.test_type == 'load_test'
        assert test.target_users == 50
        assert test.requests_per_second == 200.5
    
    def test_results_json_helpers(self, init_database):
        """Test results JSON helper methods."""
        test = PerformanceTest()
        
        results = {
            'response_times': {
                'min': 50,
                'max': 500,
                'avg': 150,
                'p95': 300,
                'p99': 450
            },
            'endpoints': [
                {'path': '/', 'avg_response_time': 100},
                {'path': '/api/data', 'avg_response_time': 200}
            ]
        }
        
        test.set_results(results)
        retrieved_results = test.get_results()
        
        assert retrieved_results == results
    
    def test_to_dict_method(self, init_database, sample_generated_application):
        """Test to_dict method."""
        db.session.add(sample_generated_application)
        db.session.commit()
        
        test = PerformanceTest(
            application_id=sample_generated_application.id,
            status=AnalysisStatus.COMPLETED,
            test_type='stress_test',
            target_users=100,
            requests_per_second=300.0,
            error_rate_percent=1.2
        )
        
        db.session.add(test)
        db.session.commit()
        
        test_dict = test.to_dict()
        
        assert test_dict['application_id'] == sample_generated_application.id
        assert test_dict['status'] == 'completed'
        assert test_dict['test_type'] == 'stress_test'
        assert test_dict['target_users'] == 100
        assert test_dict['requests_per_second'] == 300.0
        assert test_dict['error_rate_percent'] == 1.2


class TestBatchAnalysis:
    """Test BatchAnalysis model."""
    
    def test_create_batch_analysis(self, init_database):
        """Test creating a batch analysis."""
        batch = BatchAnalysis(
            name='Security Batch Test',
            analysis_type='security',
            status=AnalysisStatus.RUNNING,
            total_applications=100,
            completed_applications=75,
            failed_applications=5,
            batch_duration=1800.5
        )
        
        db.session.add(batch)
        db.session.commit()
        
        assert batch.id is not None
        assert batch.name == 'Security Batch Test'
        assert batch.analysis_type == 'security'
        assert batch.total_applications == 100
        assert batch.completed_applications == 75
        assert batch.failed_applications == 5
    
    def test_config_json_helpers(self, init_database):
        """Test config JSON helper methods."""
        batch = BatchAnalysis(
            name='Test Batch',
            analysis_type='performance'
        )
        
        config = {
            'models': ['model1', 'model2'],
            'app_numbers': [1, 2, 3],
            'test_duration': 60,
            'parallel_limit': 5
        }
        
        batch.set_config(config)
        retrieved_config = batch.get_config()
        
        assert retrieved_config == config
    
    def test_results_json_helpers(self, init_database):
        """Test results JSON helper methods."""
        batch = BatchAnalysis(
            name='Test Batch',
            analysis_type='security'
        )
        
        results = {
            'summary': {
                'total_vulnerabilities': 150,
                'high_severity': 25,
                'avg_analysis_time': 45.2
            },
            'failed_apps': ['model1/app1', 'model2/app3']
        }
        
        batch.set_results(results)
        retrieved_results = batch.get_results()
        
        assert retrieved_results == results
    
    def test_get_progress_percentage(self, init_database):
        """Test progress percentage calculation."""
        batch = BatchAnalysis(
            name='Test Batch',
            analysis_type='performance',
            total_applications=100,
            completed_applications=60,
            failed_applications=10
        )
        
        progress = batch.get_progress_percentage()
        assert progress == 70.0  # (60 + 10) / 100 * 100
        
        # Test with zero total applications
        batch.total_applications = 0
        progress = batch.get_progress_percentage()
        assert progress == 0
    
    def test_to_dict_method(self, init_database):
        """Test to_dict method."""
        batch = BatchAnalysis(
            name='Performance Batch',
            analysis_type='performance',
            status=AnalysisStatus.COMPLETED,
            total_applications=50,
            completed_applications=45,
            failed_applications=5
        )
        
        config = {'test': 'config'}
        results = {'test': 'results'}
        
        batch.set_config(config)
        batch.set_results(results)
        
        db.session.add(batch)
        db.session.commit()
        
        batch_dict = batch.to_dict()
        
        assert batch_dict['name'] == 'Performance Batch'
        assert batch_dict['analysis_type'] == 'performance'
        assert batch_dict['status'] == 'completed'
        assert batch_dict['total_applications'] == 50
        assert batch_dict['progress_percentage'] == 100.0
        assert batch_dict['config'] == config
        assert batch_dict['results'] == results


class TestAnalysisStatusEnum:
    """Test AnalysisStatus enum values."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        assert AnalysisStatus.PENDING.value == "pending"
        assert AnalysisStatus.RUNNING.value == "running"
        assert AnalysisStatus.COMPLETED.value == "completed"
        assert AnalysisStatus.FAILED.value == "failed"
        assert AnalysisStatus.CANCELLED.value == "cancelled"
    
    def test_enum_in_model(self, init_database):
        """Test using enum in model."""
        # Create required application first
        app = GeneratedApplication(
            model_slug="test-model",
            app_number=1,
            app_type="login",
            provider="test-provider"
        )
        db.session.add(app)
        db.session.flush()  # Get the ID
        
        analysis = SecurityAnalysis(
            application_id=app.id,
            status=AnalysisStatus.RUNNING
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        # Retrieve from database
        retrieved = SecurityAnalysis.query.first()
        assert retrieved.status == AnalysisStatus.RUNNING
        assert retrieved.status.value == "running"


class TestSeverityLevelEnum:
    """Test SeverityLevel enum values."""
    
    def test_enum_values(self):
        """Test that all expected enum values exist."""
        assert SeverityLevel.LOW.value == "low"
        assert SeverityLevel.MEDIUM.value == "medium"
        assert SeverityLevel.HIGH.value == "high"
        assert SeverityLevel.CRITICAL.value == "critical"
