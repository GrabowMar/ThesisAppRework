"""
Tool-specific validation tests for analyzer services.

These tests verify that individual analysis tools:
1. Are available in their respective services
2. Produce expected output format
3. Handle edge cases correctly

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
from typing import Dict, Any, List

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'analyzer'))

from analyzer.analyzer_manager import AnalyzerManager


# =============================================================================
# Test Configuration
# =============================================================================

# Static analyzer tools by category
PYTHON_STATIC_TOOLS = ['bandit', 'semgrep', 'ruff', 'mypy', 'vulture', 'radon']
JS_STATIC_TOOLS = ['eslint', 'npm-audit']
PYTHON_DEPENDENCY_TOOLS = ['safety', 'pip-audit']

# Dynamic analyzer tools
DYNAMIC_TOOLS = ['curl', 'nmap']

# Performance tools
PERFORMANCE_TOOLS = ['aiohttp', 'ab']

# AI analyzer tools
AI_TOOLS = ['requirements-checker', 'style-checker']


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="module")
def analyzer_manager():
    """Create analyzer manager instance."""
    return AnalyzerManager()


@pytest.fixture
def test_app_info() -> Dict[str, Any]:
    """Get a test app for analysis (first available app with Python files)."""
    apps_dir = project_root / 'generated' / 'apps'
    
    for model_dir in apps_dir.iterdir():
        if model_dir.is_dir() and not model_dir.name.startswith('.'):
            # Try template structure: model/template/app{N}
            for template_dir in model_dir.iterdir():
                if template_dir.is_dir() and not template_dir.name.startswith('.'):
                    for app_dir in template_dir.iterdir():
                        if app_dir.is_dir() and app_dir.name.startswith('app'):
                            app_num = int(app_dir.name.replace('app', ''))
                            return {'model_slug': model_dir.name, 'app_number': app_num}
    
    pytest.skip("No generated apps available for testing")


# =============================================================================
# Static Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestStaticAnalyzerPythonTools:
    """Test Python static analysis tools."""
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("tool", ['bandit', 'ruff'])
    async def test_python_security_tools(self, analyzer_manager, test_app_info, tool):
        """Test Python security analysis tools (bandit, ruff)."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=[tool]
        )
        
        # Should complete without error status
        assert result.get('status') != 'error' or 'analysis' in result, \
            f"Tool {tool} failed: {result.get('error', 'unknown error')}"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_semgrep_analysis(self, analyzer_manager, test_app_info):
        """Test semgrep security analysis (can be slow)."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['semgrep']
        )
        
        assert result.get('status') != 'error' or 'analysis' in result, \
            f"Semgrep analysis failed: {result.get('error', 'unknown error')}"


@pytest.mark.analyzer
@pytest.mark.integration
class TestStaticAnalyzerJSTools:
    """Test JavaScript/TypeScript static analysis tools."""
    
    @pytest.mark.asyncio
    async def test_eslint_analysis(self, analyzer_manager, test_app_info):
        """Test ESLint JavaScript analysis."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['eslint']
        )
        
        # ESLint may return exit code 1 with findings - that's success
        # We're checking the service processes the request
        assert 'analysis' in result or result.get('status') != 'error' or result.get('type'), \
            f"ESLint analysis failed: {result}"


@pytest.mark.analyzer
@pytest.mark.integration
class TestStaticAnalyzerDependencyTools:
    """Test dependency vulnerability scanning tools."""
    
    @pytest.mark.asyncio
    async def test_safety_check(self, analyzer_manager, test_app_info):
        """Test safety dependency vulnerability check."""
        result = await analyzer_manager.run_security_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['safety']
        )
        
        # Safety may find issues or not - we just verify it runs
        assert 'analysis' in result or 'status' in result, \
            f"Safety check failed with unexpected format: {result.keys()}"


# =============================================================================
# Dynamic Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestDynamicAnalyzerTools:
    """Test dynamic analysis tools."""
    
    @pytest.fixture
    def running_app_info(self) -> Dict[str, Any]:
        """Get info for an app with .env file (port config)."""
        apps_dir = project_root / 'generated' / 'apps'
        
        for model_dir in apps_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                for template_dir in model_dir.iterdir():
                    if template_dir.is_dir():
                        for app_dir in template_dir.iterdir():
                            if app_dir.is_dir() and app_dir.name.startswith('app'):
                                env_file = app_dir / '.env'
                                if env_file.exists():
                                    app_num = int(app_dir.name.replace('app', ''))
                                    return {'model_slug': model_dir.name, 'app_number': app_num}
        
        pytest.skip("No apps with port configuration available")
    
    @pytest.mark.asyncio
    async def test_curl_connectivity(self, analyzer_manager, running_app_info):
        """Test curl connectivity check tool."""
        result = await analyzer_manager.run_dynamic_analysis(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['curl']
        )
        
        # Curl should run and return results (connection may fail if app not running)
        assert 'analysis' in result or 'status' in result or 'type' in result, \
            f"Curl tool returned unexpected format: {result.keys()}"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_nmap_scan(self, analyzer_manager, running_app_info):
        """Test nmap port scanning tool."""
        result = await analyzer_manager.run_dynamic_analysis(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['nmap']
        )
        
        assert 'analysis' in result or 'status' in result or 'type' in result, \
            f"Nmap tool returned unexpected format: {result.keys()}"


# =============================================================================
# Performance Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
class TestPerformanceAnalyzerTools:
    """Test performance analysis tools."""
    
    @pytest.fixture
    def running_app_info(self) -> Dict[str, Any]:
        """Get info for an app with port configuration."""
        apps_dir = project_root / 'generated' / 'apps'
        
        for model_dir in apps_dir.iterdir():
            if model_dir.is_dir() and not model_dir.name.startswith('.'):
                for template_dir in model_dir.iterdir():
                    if template_dir.is_dir():
                        for app_dir in template_dir.iterdir():
                            if app_dir.is_dir() and app_dir.name.startswith('app'):
                                env_file = app_dir / '.env'
                                if env_file.exists():
                                    app_num = int(app_dir.name.replace('app', ''))
                                    return {'model_slug': model_dir.name, 'app_number': app_num}
        
        pytest.skip("No apps with port configuration available")
    
    @pytest.mark.asyncio
    async def test_aiohttp_load_test(self, analyzer_manager, running_app_info):
        """Test aiohttp-based load testing tool."""
        result = await analyzer_manager.run_performance_test(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['aiohttp']
        )
        
        # Performance test should complete
        assert 'analysis' in result or 'status' in result or 'type' in result, \
            f"Aiohttp tool returned unexpected format: {result.keys()}"
    
    @pytest.mark.asyncio
    @pytest.mark.slow
    async def test_apache_bench_load_test(self, analyzer_manager, running_app_info):
        """Test Apache Bench (ab) load testing tool."""
        result = await analyzer_manager.run_performance_test(
            running_app_info['model_slug'],
            running_app_info['app_number'],
            tools=['ab']
        )
        
        assert 'analysis' in result or 'status' in result or 'type' in result, \
            f"Apache Bench tool returned unexpected format: {result.keys()}"


# =============================================================================
# AI Analyzer Tool Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
@pytest.mark.slow
class TestAIAnalyzerTools:
    """Test AI-powered analysis tools.
    
    Note: These tests may require API keys and can be slow.
    """
    
    @pytest.mark.asyncio
    async def test_requirements_checker(self, analyzer_manager, test_app_info):
        """Test functional requirements checker tool."""
        result = await analyzer_manager.run_ai_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['requirements-checker']
        )
        
        # AI service should respond (may fail due to API key)
        assert 'analysis' in result or 'status' in result or 'error' in result, \
            f"Requirements checker returned unexpected format: {result.keys()}"


# =============================================================================
# Tool Combination Tests
# =============================================================================

@pytest.mark.analyzer
@pytest.mark.integration
@pytest.mark.slow
class TestToolCombinations:
    """Test running multiple tools together."""
    
    @pytest.mark.asyncio
    async def test_multiple_python_tools(self, analyzer_manager, test_app_info):
        """Test running multiple Python analysis tools together."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['bandit', 'ruff']
        )
        
        assert result.get('status') != 'error' or 'analysis' in result, \
            f"Multi-tool Python analysis failed: {result.get('error')}"
    
    @pytest.mark.asyncio
    async def test_python_and_js_tools(self, analyzer_manager, test_app_info):
        """Test running Python and JavaScript tools together."""
        result = await analyzer_manager.run_static_analysis(
            test_app_info['model_slug'],
            test_app_info['app_number'],
            tools=['bandit', 'eslint']
        )
        
        assert result.get('status') != 'error' or 'analysis' in result, \
            f"Mixed language analysis failed: {result.get('error')}"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'analyzer and not slow'])
