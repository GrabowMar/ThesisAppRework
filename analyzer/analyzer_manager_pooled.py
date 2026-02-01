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
try:
    from analyzer_manager import AnalyzerManager as BaseAnalyzerManager
except ImportError:
    # Try relative import if direct import fails
    from .analyzer_manager import AnalyzerManager as BaseAnalyzerManager

logger = logging.getLogger(__name__)


class PooledAnalyzerManager(BaseAnalyzerManager):
    """
    Analyzer manager that uses connection pooling for concurrent analysis.

    This is a drop-in replacement for AnalyzerManager that delegates all
    WebSocket communication to the AnalyzerPool for better concurrency.
    """

    def __init__(self):
        """Initialize the pooled analyzer manager."""
        super().__init__()
        self.pool: Optional[AnalyzerPool] = None
        self._initialized = False

        # Service name mapping (overrides/extends what parent might have)
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
        logger.info(f"⚡ Running performance test on {model_slug} app {app_number}")
        
        # Validate app exists and normalize slug
        validation = self._normalize_and_validate_app(model_slug, app_number)
        if isinstance(validation, dict):
            # Validation returned an error dict
            return validation
        normalized_slug, app_path = validation
        
        # Resolve target URLs if not provided
        resolved_urls = []
        if target_urls:
            resolved_urls = list(target_urls)
        else:
            # Check config for target_url override
            conf = config or {}
            if conf.get('target_url'):
                resolved_urls.append(conf.get('target_url'))
            else:
                ports = self._resolve_app_ports(normalized_slug, app_number)
                if not ports:
                    return {
                        'status': 'error',
                        'error': f'No port configuration found for {normalized_slug} app{app_number}',
                        'message': 'Start the app with docker-compose or configure ports in database'
                    }
                
                backend_port, frontend_port = ports
                # Use Docker container names for container-to-container communication
                safe_slug = normalized_slug.replace('_', '-').replace('.', '-')
                
                # Get the build_id of running containers for correct naming
                build_id = self._get_running_build_id(normalized_slug, app_number)
                if build_id:
                    container_prefix = f"{safe_slug}-app{app_number}-{build_id}"
                else:
                    container_prefix = f"{safe_slug}-app{app_number}"
                
                resolved_urls = [
                    f"http://{container_prefix}_backend:{backend_port}",
                    f"http://{container_prefix}_frontend:80"
                ]
                logger.info(f"Target URLs for performance test (build_id={build_id}): {resolved_urls}")

        message = {
            "type": "performance_test",
            "model_slug": normalized_slug,
            "app_number": app_number,
            "target_urls": resolved_urls,
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
            "type": "ai_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            "tools": tools or [],
            "config": config or {},
        }

        return await self.send_websocket_message(
            'ai-analyzer',
            message,
            timeout=int(os.environ.get('AI_ANALYSIS_TIMEOUT', '900'))
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
