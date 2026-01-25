"""
Analyzer Connection Pool & Load Balancer
=========================================

Manages connections to multiple analyzer replicas and distributes
requests using intelligent load balancing.

Architecture:
- Maintains pool of connections to all analyzer replicas
- Round-robin or least-loaded load balancing
- Automatic failover and health checking
- Connection recycling and retry logic

Usage:
    pool = AnalyzerPool()
    await pool.initialize()
    result = await pool.send_analysis_request('static-analyzer', message)
"""

import asyncio
import json
import logging
import os
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any

import websockets
from websockets.exceptions import WebSocketException

logger = logging.getLogger(__name__)


class LoadBalancingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"


@dataclass
class AnalyzerEndpoint:
    """Represents a single analyzer service endpoint."""
    service_name: str
    host: str
    port: int

    # Health tracking
    is_healthy: bool = True
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0

    # Load tracking
    active_requests: int = 0
    total_requests: int = 0
    total_failures: int = 0

    # Performance metrics
    avg_response_time: float = 0.0
    last_request_time: Optional[datetime] = None

    @property
    def url(self) -> str:
        """Get WebSocket URL for this endpoint."""
        return f"ws://{self.host}:{self.port}"

    @property
    def load_score(self) -> float:
        """Calculate load score (lower is better)."""
        # Weighted score: active requests (heavy) + avg response time (light)
        return self.active_requests * 10 + (self.avg_response_time / 10)


@dataclass
class AnalyzerPoolConfig:
    """Configuration for analyzer pool."""
    strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_LOADED
    health_check_interval: int = 30  # seconds
    max_retries: int = 3
    request_timeout: int = 600  # 10 minutes for long analyses
    connection_timeout: int = 10
    max_consecutive_failures: int = 3  # Mark unhealthy after N failures
    cooldown_period: int = 60  # Seconds to wait before retrying unhealthy endpoint


class AnalyzerPool:
    """
    Connection pool and load balancer for analyzer services.

    Manages multiple replicas of each analyzer type and intelligently
    distributes requests for optimal concurrency.
    """

    def __init__(self, config: Optional[AnalyzerPoolConfig] = None):
        """
        Initialize analyzer pool.

        Args:
            config: Pool configuration (uses defaults if not provided)
        """
        self.config = config or AnalyzerPoolConfig()
        self.endpoints: Dict[str, List[AnalyzerEndpoint]] = {}
        self.round_robin_indexes: Dict[str, int] = {}
        self.health_check_task: Optional[asyncio.Task] = None
        self._initialized = False

    def _load_endpoints_from_env(self):
        """
        Load analyzer endpoints from environment variables.

        Supports both single and multi-replica configurations:
        - Single: STATIC_ANALYZER_URL=ws://static-analyzer:2001
        - Multi: STATIC_ANALYZER_URLS=ws://host:2001,ws://host:2002,ws://host:2003
        """
        # Mapping of service names to env var prefixes
        service_configs = {
            'static-analyzer': 'STATIC_ANALYZER',
            'dynamic-analyzer': 'DYNAMIC_ANALYZER',
            'performance-tester': 'PERF_TESTER',
            'ai-analyzer': 'AI_ANALYZER'
        }

        for service_name, env_prefix in service_configs.items():
            endpoints = []

            # Check for multi-replica configuration first
            urls_env = f"{env_prefix}_URLS"
            if urls_env in os.environ:
                urls = os.environ[urls_env].split(',')
                for url in urls:
                    url = url.strip()
                    if url.startswith('ws://'):
                        host_port = url.replace('ws://', '')
                        if ':' in host_port:
                            host, port = host_port.split(':', 1)
                            endpoints.append(AnalyzerEndpoint(
                                service_name=service_name,
                                host=host,
                                port=int(port)
                            ))

            # Fall back to single URL configuration
            if not endpoints:
                url_env = f"{env_prefix}_URL"
                if url_env in os.environ:
                    url = os.environ[url_env]
                    if url.startswith('ws://'):
                        host_port = url.replace('ws://', '')
                        if ':' in host_port:
                            host, port = host_port.split(':', 1)
                            endpoints.append(AnalyzerEndpoint(
                                service_name=service_name,
                                host=host,
                                port=int(port)
                            ))
                else:
                    # Use defaults for docker environment (3 replicas each)
                    default_ports = {
                        'static-analyzer': [2001, 2002, 2003],
                        'dynamic-analyzer': [2011, 2012, 2013],
                        'performance-tester': [2021, 2022, 2023],
                        'ai-analyzer': [2031, 2032, 2033]
                    }

                    host = 'localhost'  # or service name in docker
                    for port in default_ports.get(service_name, []):
                        endpoints.append(AnalyzerEndpoint(
                            service_name=service_name,
                            host=host,
                            port=port
                        ))

            if endpoints:
                self.endpoints[service_name] = endpoints
                logger.info(
                    f"Loaded {len(endpoints)} endpoint(s) for {service_name}: "
                    f"{[e.url for e in endpoints]}"
                )
            else:
                logger.warning(f"No endpoints configured for {service_name}")

    async def initialize(self):
        """Initialize the pool and start background health checking."""
        if self._initialized:
            return

        self._load_endpoints_from_env()

        # Initial health check
        await self._check_all_health()

        # Start background health checker
        self.health_check_task = asyncio.create_task(self._health_check_loop())

        self._initialized = True
        logger.info(
            f"Analyzer pool initialized with {sum(len(eps) for eps in self.endpoints.values())} total endpoints"
        )

    async def shutdown(self):
        """Shutdown the pool and cleanup resources."""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass

        self._initialized = False
        logger.info("Analyzer pool shutdown complete")

    def _select_endpoint(self, service_name: str) -> Optional[AnalyzerEndpoint]:
        """
        Select best endpoint for a request using configured strategy.

        Args:
            service_name: Name of analyzer service

        Returns:
            Selected endpoint or None if none available
        """
        endpoints = self.endpoints.get(service_name, [])
        if not endpoints:
            return None

        # Filter to healthy endpoints
        healthy = [e for e in endpoints if e.is_healthy]

        # If no healthy endpoints, try unhealthy ones that have cooled down
        if not healthy:
            now = datetime.now()
            cooldown = timedelta(seconds=self.config.cooldown_period)
            cooled_down = [
                e for e in endpoints
                if e.last_health_check and (now - e.last_health_check) > cooldown
            ]
            if cooled_down:
                logger.warning(
                    f"No healthy {service_name} endpoints, trying cooled-down endpoints"
                )
                healthy = cooled_down
            else:
                logger.error(f"No available {service_name} endpoints!")
                return None

        # Apply load balancing strategy
        if self.config.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            idx = self.round_robin_indexes.get(service_name, 0)
            endpoint = healthy[idx % len(healthy)]
            self.round_robin_indexes[service_name] = idx + 1
            return endpoint

        elif self.config.strategy == LoadBalancingStrategy.LEAST_LOADED:
            return min(healthy, key=lambda e: e.load_score)

        elif self.config.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(healthy)

        return healthy[0]  # Fallback

    async def _check_endpoint_health(self, endpoint: AnalyzerEndpoint) -> bool:
        """
        Check health of a single endpoint.

        Args:
            endpoint: Endpoint to check

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with websockets.connect(
                endpoint.url,
                open_timeout=5,
                close_timeout=2,
                ping_interval=None
            ) as ws:
                # Send health check
                await ws.send(json.dumps({"type": "health_check"}))

                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(response)

                if data.get('status') == 'healthy':
                    endpoint.is_healthy = True
                    endpoint.consecutive_failures = 0
                    endpoint.last_health_check = datetime.now()
                    return True

        except Exception as e:
            logger.debug(f"Health check failed for {endpoint.url}: {e}")

        endpoint.consecutive_failures += 1
        endpoint.last_health_check = datetime.now()

        if endpoint.consecutive_failures >= self.config.max_consecutive_failures:
            if endpoint.is_healthy:
                logger.warning(
                    f"Marking {endpoint.url} as unhealthy after "
                    f"{endpoint.consecutive_failures} failures"
                )
            endpoint.is_healthy = False

        return False

    async def _check_all_health(self):
        """Check health of all endpoints concurrently."""
        tasks = []
        for endpoints in self.endpoints.values():
            for endpoint in endpoints:
                tasks.append(self._check_endpoint_health(endpoint))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _health_check_loop(self):
        """Background task that periodically checks endpoint health."""
        while True:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._check_all_health()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)

    async def send_analysis_request(
        self,
        service_name: str,
        message: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send analysis request to an analyzer service.

        Args:
            service_name: Name of analyzer service (e.g., 'static-analyzer')
            message: Request message dictionary
            timeout: Optional timeout override

        Returns:
            Response dictionary from analyzer

        Raises:
            RuntimeError: If no endpoints available or all retries failed
        """
        timeout = timeout or self.config.request_timeout
        max_retries = self.config.max_retries

        for attempt in range(max_retries):
            endpoint = self._select_endpoint(service_name)
            if not endpoint:
                raise RuntimeError(f"No available endpoints for {service_name}")

            # Track request
            endpoint.active_requests += 1
            endpoint.total_requests += 1
            request_start = time.time()

            try:
                logger.debug(
                    f"Sending request to {endpoint.url} (attempt {attempt + 1}/{max_retries}, "
                    f"active={endpoint.active_requests}, load={endpoint.load_score:.1f})"
                )

                # Connect and send request
                async with websockets.connect(
                    endpoint.url,
                    open_timeout=self.config.connection_timeout,
                    close_timeout=5,
                    ping_interval=None,
                    max_size=100 * 1024 * 1024  # 100MB for large responses
                ) as ws:
                    await ws.send(json.dumps(message))

                    # Wait for response (handle streaming responses)
                    result = None
                    async for response_msg in ws:
                        data = json.loads(response_msg)
                        msg_type = data.get('type', '')

                        # Handle different message types
                        if msg_type in ('analysis_result', 'error'):
                            result = data
                            break
                        elif msg_type == 'request_queued':
                            logger.debug(f"Request queued at {endpoint.url}: {data}")
                        elif msg_type == 'progress_update':
                            logger.debug(f"Progress from {endpoint.url}: {data.get('stage')}")

                    if not result:
                        raise RuntimeError("No result received from analyzer")

                    # Success - update metrics
                    duration = time.time() - request_start
                    endpoint.last_request_time = datetime.now()
                    endpoint.consecutive_failures = 0

                    # Update rolling average response time
                    if endpoint.avg_response_time == 0:
                        endpoint.avg_response_time = duration
                    else:
                        endpoint.avg_response_time = (
                            endpoint.avg_response_time * 0.8 + duration * 0.2
                        )

                    logger.info(
                        f"Request completed via {endpoint.url} in {duration:.2f}s "
                        f"(avg={endpoint.avg_response_time:.2f}s)"
                    )

                    return result

            except Exception as e:
                logger.warning(
                    f"Request to {endpoint.url} failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                endpoint.total_failures += 1
                endpoint.consecutive_failures += 1

                # Mark as unhealthy if too many failures
                if endpoint.consecutive_failures >= self.config.max_consecutive_failures:
                    endpoint.is_healthy = False
                    logger.warning(f"Marked {endpoint.url} as unhealthy")

                # Retry with different endpoint
                if attempt < max_retries - 1:
                    await asyncio.sleep(1)  # Brief delay between retries

            finally:
                endpoint.active_requests -= 1

        # All retries exhausted
        raise RuntimeError(
            f"Failed to complete request to {service_name} after {max_retries} attempts"
        )

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get statistics about the connection pool."""
        stats = {}

        for service_name, endpoints in self.endpoints.items():
            service_stats = {
                'total_endpoints': len(endpoints),
                'healthy_endpoints': sum(1 for e in endpoints if e.is_healthy),
                'total_active_requests': sum(e.active_requests for e in endpoints),
                'endpoints': [
                    {
                        'url': e.url,
                        'healthy': e.is_healthy,
                        'active_requests': e.active_requests,
                        'total_requests': e.total_requests,
                        'total_failures': e.total_failures,
                        'avg_response_time': round(e.avg_response_time, 2),
                        'load_score': round(e.load_score, 2)
                    }
                    for e in endpoints
                ]
            }
            stats[service_name] = service_stats

        return stats


# Global pool instance
_pool_instance: Optional[AnalyzerPool] = None


async def get_analyzer_pool() -> AnalyzerPool:
    """Get or create the global analyzer pool instance."""
    global _pool_instance

    if _pool_instance is None:
        _pool_instance = AnalyzerPool()
        await _pool_instance.initialize()

    return _pool_instance
