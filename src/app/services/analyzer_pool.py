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
    max_consecutive_failures: int = 5  # Mark unhealthy after N failures (increased from 3 for high-concurrency tolerance)
    cooldown_period: int = 20  # Seconds to wait before retrying unhealthy endpoint (reduced from 60 for faster recovery)
    # DISABLED: ping_interval/ping_timeout cause false-positive connection closures when
    # analyzers are running long synchronous subprocesses (ZAP, bandit, etc.) that block
    # the event loop and prevent timely pong responses. Server already disables pings.
    ping_interval: Optional[int] = None  # Disabled - analyzers can't respond during sync work
    ping_timeout: Optional[int] = None   # Disabled - relies on message_timeout instead
    message_timeout: int = 600  # Timeout for receiving individual messages (progress updates) - increased to 10 min to match request_timeout for long-running static analyses


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
                    # Use defaults for root stack environment (mapped to host ports)
                    default_ports = {
                        'static-analyzer': [2001, 2051, 2052],
                        'dynamic-analyzer': [2002, 2053],
                        'performance-tester': [2003, 2054],
                        'ai-analyzer': [2004, 2055]
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
        """Initialize the pool."""
        if self._initialized:
            return

        self._load_endpoints_from_env()
        
        # Mark all endpoints as healthy initially to assume success until proven otherwise
        # This prevents immediate failures if the pool starts before backend services
        for endpoints in self.endpoints.values():
            for endpoint in endpoints:
                endpoint.is_healthy = True
                endpoint.consecutive_failures = 0
                endpoint.last_health_check = datetime.now()

        self._initialized = True
        logger.info(
            f"Analyzer pool initialized with {sum(len(eps) for eps in self.endpoints.values())} total endpoints"
        )

    async def shutdown(self):
        """Shutdown the pool and cleanup resources."""
        self._initialized = False
        logger.info("Analyzer pool shutdown complete")

    async def select_best_endpoint(self, service_name: str) -> Optional[AnalyzerEndpoint]:
        """
        Select best endpoint for a request using configured strategy.
        Performs on-demand health checks for stale/unhealthy endpoints to ensure recovery.

        Args:
            service_name: Name of analyzer service

        Returns:
            Selected endpoint or None if none available
        """
        endpoints = self.endpoints.get(service_name, [])
        if not endpoints:
            return None

        # 1. Identify healthy candidates
        healthy_candidates = [e for e in endpoints if e.is_healthy]
        
        # 2. Check for stale/unhealthy endpoints that deserve a retry
        # (Those that are marked unhealthy but have passed the cooldown period)
        now = datetime.now()
        cooldown = timedelta(seconds=self.config.cooldown_period)
        
        retry_candidates = []
        for e in endpoints:
            if not e.is_healthy:
                # If never checked or passed cooldown, it's a candidate for resurrection
                if not e.last_health_check or (now - e.last_health_check) > cooldown:
                    retry_candidates.append(e)
        
        # 3. If we have retry candidates, check their health on-demand
        # We limit the number of checks to avoid latency spikes during selection
        if retry_candidates:
            # Sort by last check time (oldest first) to prioritize long-dead endpoints
            retry_candidates.sort(key=lambda x: x.last_health_check or datetime.min)
            
            # Check up to 2 candidates in parallel to try and recover them
            check_tasks = [self._check_endpoint_health(e) for e in retry_candidates[:2]]
            if check_tasks:
                logger.debug(f"Attempting to resurrect {len(check_tasks)} stale endpoints for {service_name}")
                results = await asyncio.gather(*check_tasks, return_exceptions=True)
                
                # If any recovered, add them to healthy candidates
                for i, is_alive in enumerate(results):
                    if is_alive is True:
                        e = retry_candidates[i]
                        logger.info(f"Resurrected endpoint {e.url} for {service_name}")
                        healthy_candidates.append(e)

        # 4. If still no healthy candidates, we're in trouble
        if not healthy_candidates:
            logger.error(f"No healthy endpoints available for {service_name}")
            return None

        # 5. Apply load balancing strategy on healthy candidates
        if self.config.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            idx = self.round_robin_indexes.get(service_name, 0)
            endpoint = healthy_candidates[idx % len(healthy_candidates)]
            self.round_robin_indexes[service_name] = idx + 1
            return endpoint

        elif self.config.strategy == LoadBalancingStrategy.LEAST_LOADED:
            # Find minimum load score
            min_score = min(e.load_score for e in healthy_candidates)
            # Find all endpoints with that score (handle ties)
            best_candidates = [e for e in healthy_candidates if abs(e.load_score - min_score) < 0.001]
            # Randomly select from the best candidates to ensure even distribution
            return random.choice(best_candidates)

        elif self.config.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(healthy_candidates)

        return healthy_candidates[0]  # Fallback

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
                open_timeout=5,   # Increased from 2s for better tolerance during high load
                close_timeout=1,
                ping_interval=None
            ) as ws:
                # Send health check
                await ws.send(json.dumps({"type": "health_check"}))

                # Wait for response
                response = await asyncio.wait_for(ws.recv(), timeout=8)  # Increased from 3s
                data = json.loads(response)

                if data.get('status') == 'healthy':
                    endpoint.is_healthy = True
                    endpoint.consecutive_failures = 0
                    endpoint.last_health_check = datetime.now()
                    return True

        except Exception as e:
            # Don't log full stack trace for health checks, just the error
            pass

        endpoint.consecutive_failures += 1
        endpoint.last_health_check = datetime.now()

        # Mark as unhealthy if it was previously healthy
        # (We don't need max_consecutive_failures logic for on-demand checks, simple state toggle is better)
        if endpoint.is_healthy:
            logger.warning(f"Endpoint {endpoint.url} failed health check, marking unhealthy")
        
        endpoint.is_healthy = False
        return False

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
            # Select endpoint (this now includes on-demand health recovery)
            endpoint = await self.select_best_endpoint(service_name)
            
            if not endpoint:
                raise RuntimeError(f"No reachable endpoints for {service_name}")

            # Track request
            endpoint.active_requests += 1
            endpoint.total_requests += 1
            request_start = time.time()

            try:
                logger.info(
                    f"Sending request to {endpoint.url} (attempt {attempt + 1}/{max_retries}, "
                    f"active={endpoint.active_requests}, load={endpoint.load_score:.1f})"
                )

                # Connect and send request
                # Enable ping/pong to detect dead connections early
                async with websockets.connect(
                    endpoint.url,
                    open_timeout=self.config.connection_timeout,
                    close_timeout=5,
                    ping_interval=self.config.ping_interval,
                    ping_timeout=self.config.ping_timeout,
                    max_size=100 * 1024 * 1024  # 100MB for large responses
                ) as ws:
                    await ws.send(json.dumps(message))

                    # Wait for response with timeout protection
                    # Use per-message timeout to detect stalled connections
                    result = None
                    overall_deadline = time.time() + timeout
                    
                    while time.time() < overall_deadline:
                        remaining = overall_deadline - time.time()
                        # Use smaller of message_timeout or remaining time
                        recv_timeout = min(self.config.message_timeout, remaining)
                        
                        try:
                            response_msg = await asyncio.wait_for(
                                ws.recv(), 
                                timeout=recv_timeout
                            )
                        except asyncio.TimeoutError:
                            if time.time() >= overall_deadline:
                                raise RuntimeError(
                                    f"Request timeout after {timeout}s waiting for response"
                                )
                            # Message timeout but overall deadline not reached - 
                            # this means no progress updates for message_timeout seconds
                            logger.warning(
                                f"No message from {endpoint.url} for {self.config.message_timeout}s, "
                                f"connection may be stalled"
                            )
                            raise RuntimeError(
                                f"Connection stalled: no response for {self.config.message_timeout}s"
                            )
                        except websockets.ConnectionClosed as cc:
                            # Connection closed by server - if code is 1000 (OK), treat as success
                            if cc.code == 1000 and result:
                                logger.debug(f"Connection closed normally (1000) with result")
                                break
                            elif cc.code == 1000:
                                # Closed OK but no result yet - might have been sent before close
                                logger.warning(f"Connection closed (1000) but no result captured from {endpoint.url}")
                                raise RuntimeError(f"Connection closed before result received")
                            else:
                                raise RuntimeError(f"Connection closed with code {cc.code}: {cc.reason}")
                        
                        data = json.loads(response_msg)
                        msg_type = data.get('type', '')

                        # Handle different message types - use lenient detection
                        # to match all analyzer response types (static_analysis_result,
                        # dynamic_analysis_result, performance_analysis_result, etc.)
                        has_analysis = isinstance(data.get('analysis'), dict)
                        is_terminal = (
                            msg_type == 'error' or
                            ('analysis_result' in msg_type) or
                            ('_result' in msg_type and has_analysis) or
                            (msg_type.endswith('_analysis') and has_analysis) or
                            (data.get('status', '').lower() in ('success', 'completed') and has_analysis) or
                            (msg_type == 'result' and has_analysis)
                        )
                        if is_terminal:
                            result = data
                            break
                        elif msg_type == 'request_queued':
                            logger.debug(f"Request queued at {endpoint.url}: {data}")
                        elif msg_type == 'progress_update':
                            logger.debug(f"Progress from {endpoint.url}: {data.get('stage')}")
                    
                    if not result:
                        if time.time() >= overall_deadline:
                            raise RuntimeError(f"Request timeout after {timeout}s")
                        raise RuntimeError("No result received from analyzer (connection closed?)")

                    # Success - update metrics
                    duration = time.time() - request_start
                    endpoint.last_request_time = datetime.now()
                    endpoint.consecutive_failures = 0
                    endpoint.is_healthy = True  # Successful request implies health

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
                endpoint.is_healthy = False # Mark unhealthy on failure to trigger immediate failover

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
