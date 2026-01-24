"""
Pooled Analyzer Manager
========================

Drop-in replacement for AnalyzerManager that uses the connection pool
for concurrent request handling across multiple analyzer replicas.

This version maintains API compatibility but routes all requests through
the AnalyzerPool for intelligent load balancing and concurrency.

Usage:
    # Instead of:
    # from analyzer.analyzer_manager import AnalyzerManager

    # Use:
    from analyzer.analyzer_manager_pooled import PooledAnalyzerManager as AnalyzerManager
"""

import asyncio
import logging
import os
from typing import Dict, Any, Optional

# Import the connection pool
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.analyzer_pool import get_analyzer_pool, AnalyzerPool

logger = logging.getLogger(__name__)


class PooledAnalyzerManager:
    """
    Analyzer manager that uses connection pooling for concurrent analysis.

    This is a drop-in replacement for AnalyzerManager that delegates all
    WebSocket communication to the AnalyzerPool for better concurrency.
    """

    def __init__(self):
        """Initialize the pooled analyzer manager."""
        self.pool: Optional[AnalyzerPool] = None
        self._initialized = False

        # Service name mapping
        self.service_names = {
            'static-analyzer': 'static-analyzer',
            'dynamic-analyzer': 'dynamic-analyzer',
            'performance-tester': 'performance-tester',
            'ai-analyzer': 'ai-analyzer'
        }

    async def _ensure_pool(self):
        """Ensure the connection pool is initialized."""
        if not self._initialized:
            self.pool = await get_analyzer_pool()
            self._initialized = True

    async def send_websocket_message(
        self,
        service_name: str,
        message: Dict[str, Any],
        timeout: int = 30
    ) -> Dict[str, Any]:
        """
        Send a message to an analyzer service via the connection pool.

        This method maintains API compatibility with the original
        AnalyzerManager.send_websocket_message() but uses the pool
        for load balancing and concurrent request handling.

        Args:
            service_name: Name of the analyzer service
            message: Request message dictionary
            timeout: Request timeout in seconds

        Returns:
            Response dictionary from the analyzer
        """
        await self._ensure_pool()

        if service_name not in self.service_names:
            return {
                'status': 'error',
                'error': f'Unknown service: {service_name}'
            }

        try:
            # Use the connection pool to send the request
            # The pool handles replica selection, load balancing, and retry logic
            result = await self.pool.send_analysis_request(
                service_name=service_name,
                message=message,
                timeout=timeout
            )

            return result

        except Exception as e:
            logger.error(f"Pooled request to {service_name} failed: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }

    async def run_static_analysis(
        self,
        model_slug: str,
        app_number: int,
        tools: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Run static analysis using the connection pool.

        Args:
            model_slug: Model identifier
            app_number: App number
            tools: Optional list of tools to run

        Returns:
            Analysis results dictionary
        """
        message = {
            "type": "static_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "tools": tools or [],
        }

        return await self.send_websocket_message(
            'static-analyzer',
            message,
            timeout=int(os.environ.get('STATIC_ANALYSIS_TIMEOUT', '480'))
        )

    async def run_dynamic_analysis(
        self,
        model_slug: str,
        app_number: int,
        target_urls: Optional[list] = None,
        tools: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Run dynamic analysis using the connection pool.

        Args:
            model_slug: Model identifier
            app_number: App number
            target_urls: Optional list of URLs to test
            tools: Optional list of tools to run

        Returns:
            Analysis results dictionary
        """
        message = {
            "type": "dynamic_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "target_urls": target_urls or [],
            "tools": tools or [],
        }

        return await self.send_websocket_message(
            'dynamic-analyzer',
            message,
            timeout=int(os.environ.get('DYNAMIC_ANALYSIS_TIMEOUT', '300'))
        )

    async def run_performance_test(
        self,
        model_slug: str,
        app_number: int,
        target_urls: Optional[list] = None,
        tools: Optional[list] = None,
        config: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Run performance testing using the connection pool.

        Args:
            model_slug: Model identifier
            app_number: App number
            target_urls: Optional list of URLs to test
            tools: Optional list of tools to run
            config: Optional configuration dict

        Returns:
            Performance test results dictionary
        """
        message = {
            "type": "performance_test",
            "model_slug": model_slug,
            "app_number": app_number,
            "target_urls": target_urls or [],
            "tools": tools or [],
            "config": config or {},
        }

        return await self.send_websocket_message(
            'performance-tester',
            message,
            timeout=int(os.environ.get('PERFORMANCE_TEST_TIMEOUT', '600'))
        )

    async def run_ai_analysis(
        self,
        model_slug: str,
        app_number: int,
        tools: Optional[list] = None,
        config: Optional[dict] = None
    ) -> Dict[str, Any]:
        """
        Run AI-powered analysis using the connection pool.

        Args:
            model_slug: Model identifier
            app_number: App number
            tools: Optional list of tools to run
            config: Optional configuration dict

        Returns:
            AI analysis results dictionary
        """
        message = {
            "type": "ai_analysis",
            "model_slug": model_slug,
            "app_number": app_number,
            "tools": tools or [],
            "config": config or {},
        }

        return await self.send_websocket_message(
            'ai-analyzer',
            message,
            timeout=int(os.environ.get('AI_ANALYSIS_TIMEOUT', '300'))
        )

    async def check_service_health(self, service_name: str) -> Dict[str, Any]:
        """
        Check health of an analyzer service.

        Args:
            service_name: Name of the service to check

        Returns:
            Health status dictionary
        """
        message = {
            "type": "health_check",
        }

        return await self.send_websocket_message(
            service_name,
            message,
            timeout=10
        )

    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the connection pool.

        Returns:
            Pool statistics dictionary with health and load info
        """
        await self._ensure_pool()

        if not self.pool:
            return {'error': 'Pool not initialized'}

        return self.pool.get_pool_stats()


# Convenience wrapper for backward compatibility
class AnalyzerManager(PooledAnalyzerManager):
    """Backward-compatible alias for PooledAnalyzerManager."""
    pass
