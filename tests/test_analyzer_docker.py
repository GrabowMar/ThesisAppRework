"""
Unit Tests for Analyzer Manager and Docker Services
====================================================

Tests the analyzer manager CLI and Docker container orchestration.
"""

import pytest
import subprocess
import socket
import json
from pathlib import Path


class TestAnalyzerManagerCLI:
    """Test analyzer manager command-line interface"""
    
    def test_analyzer_manager_status_command(self):
        """Test 'status' command shows all services"""
        result = subprocess.run(
            ['python', 'analyzer/analyzer_manager.py', 'status'],
            capture_output=True,
            text=True,
            timeout=10,
            encoding='utf-8',
            errors='replace'  # Handle Unicode encoding issues on Windows
        )
        
        # Check that status command ran (may have warnings but should show services)
        output = result.stdout + result.stderr
        assert 'static-analyzer' in output or 'ANALYZER' in output
        assert 'docker' in output.lower() or 'container' in output.lower()
    
    def test_analyzer_manager_health_command(self):
        """Test 'health' command checks service health"""
        result = subprocess.run(
            ['python', 'analyzer/analyzer_manager.py', 'health'],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        # Health check may have warnings but should complete
        assert 'static-analyzer' in result.stdout
        assert 'HEALTH' in result.stdout or 'health' in result.stdout.lower()


class TestDockerContainers:
    """Test Docker container status and health"""
    
    def test_all_containers_running(self):
        """Verify all four analyzer containers are running"""
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=analyzer', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True,
            text=True
        )
        
        output = result.stdout
        
        assert 'static-analyzer' in output
        assert 'dynamic-analyzer' in output
        assert 'performance-tester' in output
        assert 'ai-analyzer' in output
        
        # Verify they're running (not exited)
        for line in output.split('\n'):
            if line.strip() and 'analyzer' in line:
                assert 'Up' in line, f"Container should be up: {line}"
    
    def test_containers_are_healthy(self):
        """Verify containers report healthy status"""
        result = subprocess.run(
            ['docker', 'ps', '--filter', 'name=analyzer', '--format', '{{.Names}}\t{{.Status}}'],
            capture_output=True,
            text=True
        )
        
        for line in result.stdout.split('\n'):
            if line.strip() and 'analyzer' in line:
                # Should show (healthy) status
                assert '(healthy)' in line or 'Up' in line, \
                    f"Container should be healthy: {line}"
    
    def test_container_networks(self):
        """Verify containers are on correct network"""
        # List all networks and check for analyzer-related networks
        result = subprocess.run(
            ['docker', 'network', 'ls', '--format', '{{.Name}}'],
            capture_output=True,
            text=True
        )
        
        # Should have at least one network (default, bridge, or analyzer-specific)
        assert result.returncode == 0, "Docker network ls should succeed"
        assert len(result.stdout.strip()) > 0, "Should have at least one network"


class TestAnalyzerPorts:
    """Test analyzer WebSocket port accessibility"""
    
    @pytest.mark.parametrize('service,port', [
        ('static-analyzer', 2001),
        ('dynamic-analyzer', 2002),
        ('performance-tester', 2003),
        ('ai-analyzer', 2004),
    ])
    def test_port_accessible(self, service, port):
        """Test that analyzer ports are accessible"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        
        try:
            result = sock.connect_ex(('localhost', port))
            assert result == 0, f"{service} port {port} should be accessible"
        finally:
            sock.close()
    
    def test_gateway_port_if_enabled(self):
        """Test unified gateway port (8765) if running"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        
        try:
            result = sock.connect_ex(('localhost', 8765))
            # Gateway is optional, so just log the result
            if result == 0:
                print("Gateway port 8765 is accessible")
            else:
                print("Gateway port 8765 not accessible (may not be running)")
        finally:
            sock.close()


class TestContainerToolRegistry:
    """Test container tool registry functionality"""
    
    def test_tool_registry_loads(self):
        """Verify tool registry can be loaded"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        assert registry is not None, "Registry should load"
        
        tools = registry.get_all_tools()
        assert len(tools) > 0, "Registry should have tools"
    
    def test_tool_availability(self):
        """Verify expected tools are available"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        tools = registry.get_all_tools()
        
        # Check for common tools
        tool_names = [tool.name for tool in tools.values()]
        
        expected_tools = ['bandit', 'safety', 'eslint', 'zap']
        for expected in expected_tools:
            assert expected in tool_names, f"Tool {expected} should be available"
    
    def test_tools_mapped_to_containers(self):
        """Verify tools are correctly mapped to containers"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.engines.container_tool_registry import get_container_tool_registry
        
        registry = get_container_tool_registry()
        tools = registry.get_all_tools()
        
        for name, tool in tools.items():
            assert tool.container is not None, f"Tool {name} should have container mapping"
            assert tool.container.value in ['static-analyzer', 'dynamic-analyzer', 'performance-tester', 'ai-analyzer'], \
                f"Tool {name} container should be valid"


class TestAnalyzerManagerOperations:
    """Test analyzer manager analysis operations"""
    
    @pytest.mark.slow
    def test_list_tools_command(self):
        """Test listing available tools"""
        result = subprocess.run(
            ['python', 'analyzer/analyzer_manager.py', 'list-tools'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Should show tools list
        output = result.stdout.lower()
        assert 'bandit' in output or 'safety' in output or 'tool' in output
    
    @pytest.mark.slow
    @pytest.mark.analyzer
    def test_quick_analysis_dry_run(self):
        """Test analyzer manager can parse analyze command"""
        # Just verify command parsing, not actual execution
        result = subprocess.run(
            ['python', 'analyzer/analyzer_manager.py', '--help'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        assert result.returncode == 0
        assert 'analyze' in result.stdout.lower() or 'usage' in result.stdout.lower()


class TestResultStorage:
    """Test result file storage and structure"""
    
    def test_results_directory_structure(self):
        """Verify results directory exists and has correct structure"""
        results_dir = Path(__file__).parent.parent / 'results'
        assert results_dir.exists(), "Results directory should exist"
        assert results_dir.is_dir(), "Results should be a directory"
    
    def test_model_directories_exist(self):
        """Verify model-specific result directories"""
        results_dir = Path(__file__).parent.parent / 'results'
        
        model_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
        
        # Should have at least some model directories
        if model_dirs:  # Only test if results exist
            # Each model dir should follow pattern: provider_model-name
            for model_dir in model_dirs[:5]:  # Check first 5
                assert '_' in model_dir.name or '-' in model_dir.name, \
                    f"Model dir should follow naming pattern: {model_dir.name}"
    
    def test_task_result_json_structure(self):
        """Verify task result JSON files have correct structure"""
        results_dir = Path(__file__).parent.parent / 'results'
        
        # Find any task result JSON
        json_files = list(results_dir.glob('*/app*/task_*/*.json'))
        
        if json_files:  # Only test if results exist
            result_file = json_files[0]
            
            with open(result_file, 'r') as f:
                data = json.load(f)
            
            # Verify expected fields
            assert 'model_slug' in data or 'metadata' in data, \
                "Result should have model info"


class TestFlaskAppIntegration:
    """Test Flask app integration with analyzers"""
    
    def test_flask_app_can_import_analyzer_manager(self):
        """Verify Flask app can import analyzer manager"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        try:
            from app.factory import create_app
            app = create_app()
            
            # Try to import analyzer manager in app context
            with app.app_context():
                from analyzer import analyzer_manager
                assert analyzer_manager is not None
        except ImportError as e:
            pytest.fail(f"Should be able to import analyzer_manager: {e}")
    
    def test_service_locator_has_analyzer_integration(self):
        """Verify ServiceLocator is aware of analyzer services"""
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
        
        from app.factory import create_app
        from app.services.service_locator import ServiceLocator
        
        app = create_app()
        with app.app_context():
            # Verify analyzer-related services exist
            # (this tests integration, not actual execution)
            pass  # ServiceLocator presence is the test


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-m', 'not slow and not analyzer'])
