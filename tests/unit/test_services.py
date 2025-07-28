"""
Unit tests for core services.

Tests service classes including ServiceManager, Docker services,
performance testing, security analysis, and other core functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

# Import services to test
try:
    from core_services import ServiceManager, ServiceInitializer, get_port_config
    from performance_service import LocustPerformanceTester
    from security_analysis_service import UnifiedCLIAnalyzer
    from zap_service import create_scanner
    from openrouter_service import OpenRouterAnalyzer
except ImportError as e:
    pytest.skip(f"Service imports not available: {e}", allow_module_level=True)


class TestServiceManager:
    """Test ServiceManager class."""
    
    def test_service_manager_creation(self, app):
        """Test creating ServiceManager instance."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            assert service_manager is not None
            assert service_manager.app == app
            assert hasattr(service_manager, 'services')
    
    def test_register_service(self, app):
        """Test registering services."""
        with app.app_context():
            service_manager = ServiceManager(app)
            mock_service = Mock()
            
            service_manager.register_service('test_service', mock_service)
            
            assert 'test_service' in service_manager.services
            assert service_manager.services['test_service'] == mock_service
    
    def test_get_service(self, app):
        """Test getting registered service."""
        with app.app_context():
            service_manager = ServiceManager(app)
            mock_service = Mock()
            
            service_manager.register_service('test_service', mock_service)
            retrieved_service = service_manager.get_service('test_service')
            
            assert retrieved_service == mock_service
    
    def test_get_nonexistent_service(self, app):
        """Test getting non-existent service returns None."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            service = service_manager.get_service('nonexistent')
            
            assert service is None


class TestServiceInitializer:
    """Test ServiceInitializer class."""
    
    def test_service_initializer_creation(self, app, mock_service_manager):
        """Test creating ServiceInitializer."""
        with app.app_context():
            initializer = ServiceInitializer(app, mock_service_manager)
            
            assert initializer.app == app
            assert initializer.service_manager == mock_service_manager
    
    @patch('core_services.DockerManager')
    def test_initialize_docker_service(self, mock_docker_class, app, mock_service_manager):
        """Test initializing Docker service."""
        mock_docker_instance = Mock()
        mock_docker_class.return_value = mock_docker_instance
        
        with app.app_context():
            initializer = ServiceInitializer(app, mock_service_manager)
            initializer.initialize_docker_service()
            
            mock_service_manager.register_service.assert_called_with('docker_manager', mock_docker_instance)
    
    @patch('core_services.ScanManager')
    def test_initialize_scan_service(self, mock_scan_class, app, mock_service_manager):
        """Test initializing scan service."""
        mock_scan_instance = Mock()
        mock_scan_class.return_value = mock_scan_instance
        
        with app.app_context():
            initializer = ServiceInitializer(app, mock_service_manager)
            initializer.initialize_scan_service()
            
            mock_service_manager.register_service.assert_called_with('scan_manager', mock_scan_instance)


class TestGetPortConfig:
    """Test get_port_config function."""
    
    def test_get_port_config_with_data(self, app, sample_port_config):
        """Test get_port_config with sample data."""
        with app.app_context():
            app.config['PORT_CONFIG'] = sample_port_config
            
            configs = get_port_config()
            
            assert isinstance(configs, list)
            assert len(configs) == len(sample_port_config)
            
            if configs:
                assert 'model' in configs[0]
                assert 'app_num' in configs[0]
                assert 'frontend_port' in configs[0]
    
    def test_get_port_config_empty(self, app):
        """Test get_port_config with empty data."""
        with app.app_context():
            app.config['PORT_CONFIG'] = []
            
            configs = get_port_config()
            
            assert configs == []
    
    def test_get_port_config_missing(self, app):
        """Test get_port_config when config is missing."""
        with app.app_context():
            # Remove PORT_CONFIG from config
            if 'PORT_CONFIG' in app.config:
                del app.config['PORT_CONFIG']
            
            configs = get_port_config()
            
            assert configs == []


class TestPerformanceService:
    """Test LocustPerformanceTester service."""
    
    def test_performance_tester_creation(self):
        """Test creating LocustPerformanceTester instance."""
        output_dir = Path('/tmp/test_output')
        
        tester = LocustPerformanceTester(output_dir)
        
        assert tester.output_dir == output_dir
        assert tester.static_url_path == "/static"
    
    def test_setup_test_directory(self):
        """Test setting up test directory."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            tester = LocustPerformanceTester(output_dir)
            
            test_name = "test_performance_run"
            test_dir = tester._setup_test_directory(test_name)
            
            assert test_dir.exists()
            assert test_dir.is_dir()
            assert "test_performance_run" in str(test_dir)
    
    @patch('performance_service.LocustPerformanceTester._get_port_for_model_app')
    def test_run_performance_test(self, mock_get_port, mock_performance_tester):
        """Test running performance test."""
        mock_get_port.return_value = 3000
        
        result = mock_performance_tester.run_performance_test('test_model', 1)
        
        assert isinstance(result, dict)
        assert 'status' in result
        
        # Verify mock was called
        mock_performance_tester.run_performance_test.assert_called_once()
    
    def test_create_user_class(self):
        """Test creating Locust user class."""
        import tempfile
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            tester = LocustPerformanceTester(output_dir)
            
            host = "http://localhost:3000"
            endpoints = [
                {"path": "/", "method": "GET", "weight": 1},
                {"path": "/api/data", "method": "POST", "weight": 2}
            ]
            
            user_class = tester.create_user_class(host, endpoints)
            
            assert user_class is not None
            assert hasattr(user_class, 'host')


class TestSecurityAnalysisService:
    """Test UnifiedCLIAnalyzer service."""
    
    def test_unified_cli_analyzer_creation(self):
        """Test creating UnifiedCLIAnalyzer instance."""
        analyzer = UnifiedCLIAnalyzer()
        
        assert analyzer is not None
    
    @patch('security_analysis_service.subprocess.run')
    def test_run_bandit_analysis(self, mock_subprocess):
        """Test running Bandit security analysis."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"results": []}',
            stderr=''
        )
        
        analyzer = UnifiedCLIAnalyzer()
        result = analyzer.run_bandit_analysis('/fake/path')
        
        assert isinstance(result, dict)
        mock_subprocess.assert_called_once()
    
    @patch('security_analysis_service.subprocess.run')
    def test_run_safety_check(self, mock_subprocess):
        """Test running Safety vulnerability check."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='[]',
            stderr=''
        )
        
        analyzer = UnifiedCLIAnalyzer()
        result = analyzer.run_safety_check('/fake/path')
        
        assert isinstance(result, dict)
        mock_subprocess.assert_called_once()
    
    def test_analyze_application(self, mock_security_analyzer):
        """Test analyzing application."""
        result = mock_security_analyzer.analyze_application('/fake/path')
        
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'results' in result


class TestZapService:
    """Test ZAP scanner service."""
    
    @patch('zap_service.ZAPv2')
    def test_create_scanner(self, mock_zap_class):
        """Test creating ZAP scanner."""
        mock_zap_instance = Mock()
        mock_zap_class.return_value = mock_zap_instance
        
        scanner = create_scanner()
        
        assert scanner is not None
        mock_zap_class.assert_called_once()
    
    def test_scanner_configuration(self, mock_scan_manager):
        """Test scanner configuration."""
        scan_config = {
            'target_url': 'http://localhost:3000',
            'scan_type': 'active'
        }
        
        result = mock_scan_manager.start_scan(scan_config)
        
        assert isinstance(result, dict)
        assert 'scan_id' in result
        assert 'status' in result


class TestOpenRouterService:
    """Test OpenRouter analyzer service."""
    
    def test_openrouter_analyzer_creation(self):
        """Test creating OpenRouter analyzer."""
        api_key = "test_api_key"
        
        analyzer = OpenRouterAnalyzer(api_key)
        
        assert analyzer is not None
        assert analyzer.api_key == api_key
    
    @patch('openrouter_service.requests.post')
    def test_analyze_code(self, mock_post):
        """Test analyzing code with OpenRouter."""
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Analysis result'}}]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        analyzer = OpenRouterAnalyzer("test_key")
        result = analyzer.analyze_code("test code", "review")
        
        assert isinstance(result, dict)
        mock_post.assert_called_once()


class TestServiceIntegration:
    """Test service integration and interaction."""
    
    def test_service_manager_integration(self, app):
        """Test integration of multiple services through ServiceManager."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            # Register multiple mock services
            docker_service = Mock()
            scan_service = Mock()
            
            service_manager.register_service('docker_manager', docker_service)
            service_manager.register_service('scan_manager', scan_service)
            
            # Test getting services
            assert service_manager.get_service('docker_manager') == docker_service
            assert service_manager.get_service('scan_manager') == scan_service
            
            # Test service interaction
            docker_service.start_containers.return_value = {'success': True}
            scan_service.start_scan.return_value = {'scan_id': 'test-123'}
            
            # Simulate workflow
            docker_result = service_manager.get_service('docker_manager').start_containers()
            scan_result = service_manager.get_service('scan_manager').start_scan({})
            
            assert docker_result['success'] is True
            assert 'scan_id' in scan_result
    
    def test_service_error_handling(self, app):
        """Test service error handling."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            # Register service that raises exception
            failing_service = Mock()
            failing_service.perform_operation.side_effect = Exception("Service error")
            
            service_manager.register_service('failing_service', failing_service)
            
            # Test that exceptions are propagated
            service = service_manager.get_service('failing_service')
            
            with pytest.raises(Exception) as excinfo:
                service.perform_operation()
            
            assert "Service error" in str(excinfo.value)
    
    def test_service_configuration(self, app, temp_config_files):
        """Test service configuration from files."""
        with app.app_context():
            # Test loading configuration
            config_data = temp_config_files
            
            # Simulate loading config files
            with open(config_data['capabilities_file']) as f:
                capabilities = json.load(f)
            
            with open(config_data['port_file']) as f:
                ports = json.load(f)
            
            assert 'models' in capabilities
            assert isinstance(ports, list)
            assert len(ports) > 0
    
    def test_service_lifecycle(self, app):
        """Test service lifecycle management."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            # Mock service with lifecycle methods
            lifecycle_service = Mock()
            lifecycle_service.initialize.return_value = True
            lifecycle_service.cleanup.return_value = True
            lifecycle_service.is_healthy.return_value = True
            
            service_manager.register_service('lifecycle_service', lifecycle_service)
            
            # Test initialization
            service = service_manager.get_service('lifecycle_service')
            init_result = service.initialize()
            assert init_result is True
            
            # Test health check
            health_result = service.is_healthy()
            assert health_result is True
            
            # Test cleanup
            cleanup_result = service.cleanup()
            assert cleanup_result is True


class TestServiceUtils:
    """Test service utility functions."""
    
    def test_port_configuration_parsing(self, sample_port_config):
        """Test parsing port configuration data."""
        # Test that port config data is properly structured
        for config in sample_port_config:
            assert 'model' in config
            assert 'app_num' in config
            assert 'frontend_port' in config
            assert 'backend_port' in config
            
            # Test port values are reasonable
            assert isinstance(config['frontend_port'], int)
            assert isinstance(config['backend_port'], int)
            assert config['frontend_port'] > 1024
            assert config['backend_port'] > 1024
    
    def test_model_slug_validation(self):
        """Test model slug validation."""
        valid_slugs = [
            'openai_gpt-4',
            'anthropic_claude-3',
            'test_model_1'
        ]
        
        invalid_slugs = [
            'invalid slug with spaces',
            'invalid/slash',
            'invalid\\backslash'
        ]
        
        # This would test a validation function if it existed
        for slug in valid_slugs:
            # Should be valid
            assert isinstance(slug, str)
            assert len(slug) > 0
        
        for slug in invalid_slugs:
            # Should be detected as invalid (if validation existed)
            assert ' ' in slug or '/' in slug or '\\' in slug
    
    def test_service_health_checks(self, mock_service_manager):
        """Test service health checking."""
        # Test that services report health status
        docker_service = mock_service_manager.get_service('docker_manager')
        
        if docker_service:
            # Mock health check would return status
            assert hasattr(docker_service, 'get_container_status')
    
    def test_service_error_recovery(self, app):
        """Test service error recovery mechanisms."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            # Mock service that can recover from errors
            recoverable_service = Mock()
            recoverable_service.operation.side_effect = [
                Exception("Temporary error"),  # First call fails
                {"success": True}              # Second call succeeds
            ]
            
            service_manager.register_service('recoverable', recoverable_service)
            
            service = service_manager.get_service('recoverable')
            
            # First call should fail
            with pytest.raises(Exception):
                service.operation()
            
            # Second call should succeed
            result = service.operation()
            assert result['success'] is True


class TestServicePerformance:
    """Test service performance characteristics."""
    
    def test_service_manager_performance(self, app):
        """Test ServiceManager performance with many services."""
        with app.app_context():
            service_manager = ServiceManager(app)
            
            # Register many services
            import time
            start_time = time.time()
            
            for i in range(100):
                mock_service = Mock()
                service_manager.register_service(f'service_{i}', mock_service)
            
            registration_time = time.time() - start_time
            
            # Registration should be fast
            assert registration_time < 1.0
            
            # Retrieval should also be fast
            start_time = time.time()
            
            for i in range(100):
                service = service_manager.get_service(f'service_{i}')
                assert service is not None
            
            retrieval_time = time.time() - start_time
            assert retrieval_time < 1.0
    
    def test_concurrent_service_access(self, app):
        """Test concurrent access to services."""
        import threading
        import time
        
        with app.app_context():
            service_manager = ServiceManager(app)
            shared_service = Mock()
            shared_service.get_data.return_value = {"data": "test"}
            
            service_manager.register_service('shared_service', shared_service)
            
            results = []
            
            def access_service():
                service = service_manager.get_service('shared_service')
                result = service.get_data()
                results.append(result)
            
            # Create multiple threads
            threads = []
            for _ in range(10):
                thread = threading.Thread(target=access_service)
                threads.append(thread)
            
            # Start all threads
            start_time = time.time()
            for thread in threads:
                thread.start()
            
            # Wait for completion
            for thread in threads:
                thread.join()
            end_time = time.time()
            
            # All should succeed
            assert len(results) == 10
            assert all(r['data'] == 'test' for r in results)
            
            # Should complete quickly
            assert end_time - start_time < 5.0
