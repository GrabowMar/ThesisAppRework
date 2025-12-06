"""
Integration tests for analyzer services.

These tests verify that all analyzer services are:
1. Running and healthy
2. Responding to WebSocket connections
3. Processing analysis requests correctly

Requirements:
- Docker must be running
- Analyzer services must be started: python analyzer/analyzer_manager.py start
"""

import asyncio
import pytest
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'analyzer'))

from analyzer.analyzer_manager import AnalyzerManager


# =============================================================================
# Test Configuration
# =============================================================================

# Services and their expected ports
ANALYZER_SERVICES = {
    'static-analyzer': 2001,
    'dynamic-analyzer': 2002,
    'performance-tester': 2003,
    'ai-analyzer': 2004,
}


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def analyzer_manager():
    """Create analyzer manager instance."""
    return AnalyzerManager()


# =============================================================================
# Health Check Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestAnalyzerHealth:
    """Test analyzer service health checks."""
    
    @pytest.mark.asyncio
    async def test_all_services_healthy(self, analyzer_manager):
        """Verify all analyzer services report healthy status."""
        health_results = await analyzer_manager.check_all_services_health()
        
        for service_name, result in health_results.items():
            assert result.get('status') == 'healthy', \
                f"Service {service_name} is not healthy: {result}"
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("service_name", list(ANALYZER_SERVICES.keys()))
    async def test_individual_service_health(self, analyzer_manager, service_name):
        """Test health of individual analyzer services."""
        result = await analyzer_manager.check_service_health(service_name)
        
        assert result.get('status') == 'healthy', \
            f"Service {service_name} health check failed: {result}"
    
    @pytest.mark.asyncio
    async def test_comprehensive_service_tests(self, analyzer_manager):
        """Run comprehensive tests on all services."""
        test_results = await analyzer_manager.test_all_services()
        
        summary = test_results['summary']
        
        # All services should be healthy
        assert summary['healthy_services'] == summary['total_services'], \
            f"Not all services healthy: {summary['healthy_services']}/{summary['total_services']}"
        
        # All pings should succeed
        assert summary['successful_pings'] == summary['total_services'], \
            f"Not all pings successful: {summary['successful_pings']}/{summary['total_services']}"
        
        # Overall health should be healthy
        assert summary['overall_health'] == 'healthy', \
            f"Overall health is not healthy: {summary['overall_health']}"


# =============================================================================
# Service Ping Tests  
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestAnalyzerPing:
    """Test analyzer service ping functionality."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("service_name", list(ANALYZER_SERVICES.keys()))
    async def test_service_ping(self, analyzer_manager, service_name):
        """Test ping response from each service.
        
        Note: Services may not implement ping explicitly, so we use health_check
        as a proxy for ping functionality.
        """
        # Use health check as ping since services handle health_check but may not handle ping
        result = await analyzer_manager.check_service_health(service_name)
        
        assert result.get('status') == 'healthy', \
            f"Service {service_name} not responding: {result}"


# =============================================================================
# Static Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestStaticAnalyzerTools:
    """Test static analyzer tool functionality."""
    
    @pytest.fixture
    def test_app_info(self) -> Dict[str, Any]:
        """Get a test app for analysis (first available app)."""
        apps_dir = project_root / 'generated' / 'apps'
        
        for model_dir in apps_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                # Try flat structure
                for item in model_dir.iterdir():
                    if item.is_dir():
                        if item.name.startswith('app'):
                            # Flat structure: model/app{N}
                            app_num = int(item.name.replace('app', ''))
                            return {'model_slug': model_dir.name, 'app_number': app_num}
                        else:
                            # Template structure: model/template/app{N}
                            for app_dir in item.iterdir():
                                if app_dir.is_dir() and app_dir.name.startswith('app'):
                                    app_num = int(app_dir.name.replace('app', ''))
                                    return {'model_slug': model_dir.name, 'app_number': app_num}
        
        pytest.skip("No generated apps available for testing")
    
    @pytest.mark.asyncio
    async def test_static_analysis_runs(self, analyzer_manager, test_app_info):
        """Verify static analysis executes without errors."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['bandit']  # Single fast tool
        )
        
        # Should not be an error
        assert result.get('status') != 'error', \
            f"Static analysis failed: {result.get('error')}"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_static_analysis_with_multiple_tools(self, analyzer_manager, test_app_info):
        """Test static analysis with multiple tools."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['bandit', 'ruff', 'eslint']
        )
        
        assert result.get('status') != 'error', \
            f"Multi-tool static analysis failed: {result.get('error')}"


# =============================================================================
# Dynamic Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestDynamicAnalyzerTools:
    """Test dynamic analyzer tool functionality."""
    
    @pytest.fixture
    def running_app_info(self) -> Dict[str, Any]:
        """Get info for a running app (with backend/frontend containers up)."""
        # This requires checking which apps have running containers
        # For simplicity, use anthropic model app 3 if it exists
        apps_dir = project_root / 'generated' / 'apps' / 'anthropic_claude-4.5-haiku-20251001'
        
        if apps_dir.exists():
            for template_dir in apps_dir.iterdir():
                if template_dir.is_dir():
                    for app_dir in template_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            env_file = app_dir / '.env'
                            if env_file.exists():
                                app_num = int(app_dir.name.replace('app', ''))
                                return {'model_slug': 'anthropic_claude-4.5-haiku-20251001', 'app_number': app_num}
        
        pytest.skip("No running apps available for dynamic testing")
    
    @pytest.mark.asyncio
    async def test_dynamic_analysis_with_curl(self, analyzer_manager, running_app_info):
        """Test dynamic analysis with curl connectivity check."""
        result = await analyzer_manager.run_dynamic_analysis(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['curl']
        )
        
        # Analysis should complete (may have connection errors if app not running)
        # We're testing that the analyzer service processes the request
        assert 'status' in result or 'analysis' in result, \
            f"Dynamic analysis returned unexpected format: {result.keys()}"


# =============================================================================
# Performance Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestPerformanceAnalyzerTools:
    """Test performance analyzer tool functionality."""
    
    @pytest.fixture
    def running_app_info(self) -> Dict[str, Any]:
        """Get info for a running app."""
        apps_dir = project_root / 'generated' / 'apps' / 'anthropic_claude-4.5-haiku-20251001'
        
        if apps_dir.exists():
            for template_dir in apps_dir.iterdir():
                if template_dir.is_dir():
                    for app_dir in template_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            env_file = app_dir / '.env'
                            if env_file.exists():
                                app_num = int(app_dir.name.replace('app', ''))
                                return {'model_slug': 'anthropic_claude-4.5-haiku-20251001', 'app_number': app_num}
        
        pytest.skip("No running apps available for performance testing")
    
    @pytest.mark.asyncio
    async def test_performance_analysis_with_aiohttp(self, analyzer_manager, running_app_info):
        """Test performance analysis with aiohttp tool."""
        result = await analyzer_manager.run_performance_test(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['aiohttp']
        )
        
        # Check analysis completed
        assert 'status' in result or 'analysis' in result, \
            f"Performance analysis returned unexpected format: {result.keys()}"


# =============================================================================
# AI Analyzer Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
@pytest.mark.slow
class TestAIAnalyzerTools:
    """Test AI analyzer functionality."""
    
    @pytest.fixture
    def test_app_info(self) -> Dict[str, Any]:
        """Get a test app for AI analysis."""
        apps_dir = project_root / 'generated' / 'apps' / 'anthropic_claude-4.5-haiku-20251001'
        
        if apps_dir.exists():
            for template_dir in apps_dir.iterdir():
                if template_dir.is_dir():
                    for app_dir in template_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            app_num = int(app_dir.name.replace('app', ''))
                            return {'model_slug': 'anthropic_claude-4.5-haiku-20251001', 'app_number': app_num}
        
        pytest.skip("No apps available for AI analysis")
    
    @pytest.mark.asyncio
    async def test_ai_analysis_service_responds(self, analyzer_manager, test_app_info):
        """Test that AI analyzer service responds to requests."""
        result = await analyzer_manager.run_ai_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['requirements-checker']  # Lighter weight than full style check
        )
        
        # Service should respond (may fail due to API key, but service should process)
        assert 'status' in result or 'analysis' in result or 'error' in result, \
            f"AI analysis returned unexpected format: {result.keys()}"


# =============================================================================
# Result Storage Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestResultStorage:
    """Test that analysis results are properly stored."""
    
    def test_results_directory_exists(self):
        """Verify results directory exists."""
        results_dir = project_root / 'results'
        assert results_dir.exists(), "Results directory does not exist"
    
    def test_can_find_result_files(self, analyzer_manager):
        """Test that result file search works."""
        # This tests the find_result_files method
        results_dir = project_root / 'results'
        
        if not any(results_dir.iterdir()):
            pytest.skip("No results available to search")
        
        # Try to find any JSON file
        matches = analyzer_manager.find_result_files('*.json')
        # We just verify the method doesn't crash
        assert isinstance(matches, list), "find_result_files should return a list"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'analyzer'])
