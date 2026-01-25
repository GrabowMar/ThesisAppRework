#!/usr/bin/env python3
"""
Concurrent Analyzer Service Base
=================================

Enhanced version of BaseWSService that supports concurrent task processing.

Key improvements:
- Internal task queue (asyncio.Queue)
- Configurable concurrency with Semaphore
- Non-blocking request handling
- Background worker pool
- Request correlation IDs for tracking

Architecture:
- WebSocket handler accepts requests immediately and queues them
- Background workers process tasks from queue concurrently
- Results are sent back via WebSocket when complete
- Supports streaming progress updates
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import websockets
from websockets import serve


def _setup_logging() -> logging.Logger:
    level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, level_str, logging.INFO)
    logging.basicConfig(level=level)
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    # Suppress noisy websockets internals
    try:
        logging.getLogger("websockets.server").setLevel(logging.CRITICAL)
        logging.getLogger("websockets.http").setLevel(logging.CRITICAL)
        logging.getLogger("websockets.http11").setLevel(logging.CRITICAL)
    except Exception:
        pass
    return logger


BASE_LOGGER = _setup_logging()


@dataclass
class AnalysisRequest:
    """Represents a queued analysis request."""
    request_id: str
    message_data: Dict[str, Any]
    websocket: Any  # websockets.WebSocketServerProtocol
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class ServiceInfo:
    name: str
    version: str = "1.0.0"
    started_at: datetime = field(default_factory=datetime.now)
    max_concurrent: int = 2
    queue_size: int = 100


class ConcurrentWSService:
    """
    Concurrent WebSocket service base with internal task queue.

    This replaces BaseWSService with a concurrent architecture that can
    handle multiple analyses simultaneously.
    """

    def __init__(
        self,
        service_name: str,
        default_port: int,
        version: str = "1.0.0",
        max_concurrent: int = None,
        queue_size: int = 100
    ):
        """
        Initialize concurrent analyzer service.

        Args:
            service_name: Name of the service
            default_port: Default WebSocket port
            version: Service version
            max_concurrent: Max concurrent analyses (default: CPU count or 2)
            queue_size: Max size of request queue
        """
        self.log = logging.getLogger(service_name) or BASE_LOGGER

        # Determine max concurrent from env or CPU count
        if max_concurrent is None:
            max_concurrent = int(os.getenv('MAX_CONCURRENT_ANALYSES',
                                          os.cpu_count() or 2))

        self.info = ServiceInfo(
            name=service_name,
            version=version,
            started_at=datetime.now(),
            max_concurrent=max_concurrent,
            queue_size=queue_size
        )

        self.default_port = default_port
        self.available_tools: List[str] = []

        # Concurrent processing components
        self.request_queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self.semaphore: asyncio.Semaphore = asyncio.Semaphore(max_concurrent)
        self.active_requests: Dict[str, AnalysisRequest] = {}
        self.workers: List[asyncio.Task] = []

        # Stats
        self.stats = {
            'total_requests': 0,
            'completed_requests': 0,
            'failed_requests': 0,
            'queue_full_errors': 0
        }

        # Detect available tools
        try:
            self.available_tools = self._detect_available_tools()
        except Exception as e:
            self.log.debug(f"Tool detection failed: {e}")
            self.available_tools = []

    # ---- Hooks to override -------------------------------------------------
    def _detect_available_tools(self) -> List[str]:
        """Detect and return a list of available tool names for this service."""
        return []

    async def handle_analysis(self, request_id: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Service-specific analysis handler. Must be implemented by subclasses.

        Args:
            request_id: Unique request identifier
            message_data: Request message data

        Returns:
            Analysis result dictionary
        """
        raise NotImplementedError("Subclasses must implement handle_analysis()")

    # ---- Utilities ---------------------------------------------------------
    @staticmethod
    def extract_selected_tools(message: Dict[str, Any]) -> Optional[Set[str]]:
        """Extract normalized selected tools set from message."""
        tools = message.get("tools")
        if not tools and isinstance(message.get("config"), dict):
            tools = message["config"].get("tools")
        if tools and isinstance(tools, list):
            try:
                return {str(t).lower() for t in tools}
            except Exception:
                return None
        return None

    async def send_progress(
        self,
        websocket,
        request_id: str,
        stage: str,
        message: str = "",
        **kwargs
    ) -> None:
        """Send progress update to client via WebSocket."""
        try:
            payload = {
                'type': 'progress_update',
                'request_id': request_id,
                'stage': stage,
                'message': message,
                'service': self.info.name,
                'timestamp': datetime.now().isoformat(),
                **kwargs
            }
            await websocket.send(json.dumps(payload))
        except Exception as e:
            self.log.debug(f"Failed to send progress: {e}")

    # ---- Background Worker Pool --------------------------------------------
    async def _worker(self, worker_id: int):
        """
        Background worker that processes requests from the queue.

        Workers run continuously, taking requests from the queue and
        processing them concurrently (limited by semaphore).
        """
        self.log.info(f"Worker {worker_id} started")

        while True:
            try:
                # Get next request from queue
                request: AnalysisRequest = await self.request_queue.get()

                # Acquire semaphore (limits concurrent processing)
                async with self.semaphore:
                    request.started_at = datetime.now()
                    self.log.info(
                        f"Worker {worker_id} processing request {request.request_id} "
                        f"(queued for {(request.started_at - request.created_at).total_seconds():.2f}s)"
                    )

                    try:
                        # Send started notification
                        await self.send_progress(
                            request.websocket,
                            request.request_id,
                            "started",
                            f"Analysis started by worker {worker_id}"
                        )

                        # Execute analysis (subclass implementation)
                        result = await self.handle_analysis(
                            request.request_id,
                            request.message_data
                        )

                        # Send result
                        result['request_id'] = request.request_id
                        result['type'] = result.get('type', 'analysis_result')
                        result['timestamp'] = datetime.now().isoformat()

                        await request.websocket.send(json.dumps(result))

                        request.completed_at = datetime.now()
                        duration = (request.completed_at - request.started_at).total_seconds()

                        self.log.info(
                            f"Worker {worker_id} completed request {request.request_id} "
                            f"in {duration:.2f}s"
                        )

                        self.stats['completed_requests'] += 1

                    except Exception as e:
                        self.log.error(
                            f"Worker {worker_id} error processing {request.request_id}: {e}",
                            exc_info=True
                        )

                        # Send error response
                        try:
                            error_response = {
                                'type': 'error',
                                'request_id': request.request_id,
                                'service': self.info.name,
                                'error': str(e),
                                'timestamp': datetime.now().isoformat()
                            }
                            await request.websocket.send(json.dumps(error_response))
                        except Exception:
                            pass  # WebSocket might be closed

                        self.stats['failed_requests'] += 1

                    finally:
                        # Remove from active requests
                        self.active_requests.pop(request.request_id, None)

                        # Mark task as done
                        self.request_queue.task_done()

            except asyncio.CancelledError:
                self.log.info(f"Worker {worker_id} cancelled")
                break
            except Exception as e:
                self.log.error(f"Worker {worker_id} unexpected error: {e}", exc_info=True)
                await asyncio.sleep(1)  # Prevent tight error loop

    # ---- WebSocket Handlers ------------------------------------------------
    async def _handle_ping(self, websocket):
        """Handle ping request."""
        await websocket.send(json.dumps({
            "type": "pong",
            "timestamp": datetime.now().isoformat(),
            "service": self.info.name,
        }))

    async def _handle_health(self, websocket):
        """Handle health check request."""
        uptime = (datetime.now() - self.info.started_at).total_seconds()
        queue_size = self.request_queue.qsize()
        active_count = len(self.active_requests)

        await websocket.send(json.dumps({
            "type": "health_response",
            "status": "healthy",
            "service": self.info.name,
            "version": self.info.version,
            "uptime": uptime,
            "available_tools": self.available_tools,
            "concurrency": {
                "max_concurrent": self.info.max_concurrent,
                "active_analyses": active_count,
                "queued_analyses": queue_size,
                "queue_capacity": self.info.queue_size
            },
            "stats": self.stats,
            "timestamp": datetime.now().isoformat(),
        }))

    async def _handle_analysis_request(self, websocket, message_data: Dict[str, Any]):
        """
        Handle incoming analysis request.

        Queues the request for background processing and returns immediately.
        """
        request_id = message_data.get('id') or str(uuid.uuid4())

        # Check if queue is full
        if self.request_queue.full():
            self.stats['queue_full_errors'] += 1
            self.log.warning(f"Queue full, rejecting request {request_id}")

            error_response = {
                'type': 'error',
                'request_id': request_id,
                'service': self.info.name,
                'error': 'Service queue is full, try again later',
                'queue_size': self.request_queue.qsize(),
                'max_queue_size': self.info.queue_size,
                'timestamp': datetime.now().isoformat()
            }
            await websocket.send(json.dumps(error_response))
            return

        # Create request object
        request = AnalysisRequest(
            request_id=request_id,
            message_data=message_data,
            websocket=websocket,
            created_at=datetime.now()
        )

        # Queue for processing
        self.active_requests[request_id] = request
        await self.request_queue.put(request)

        self.stats['total_requests'] += 1

        self.log.info(
            f"Queued request {request_id} "
            f"(queue: {self.request_queue.qsize()}/{self.info.queue_size}, "
            f"active: {len(self.active_requests)})"
        )

        # Send acknowledgment
        ack_response = {
            'type': 'request_queued',
            'request_id': request_id,
            'service': self.info.name,
            'queue_position': self.request_queue.qsize(),
            'estimated_wait_seconds': self.request_queue.qsize() * 30,  # Rough estimate
            'timestamp': datetime.now().isoformat()
        }
        await websocket.send(json.dumps(ack_response))

    async def _handle_client(self, websocket):
        """Handle WebSocket client connection."""
        client = f"{getattr(websocket, 'remote_address', ('?', '?'))[0]}:{getattr(websocket, 'remote_address', ('?', '?'))[1]}"
        self.log.debug(f"New client connected: {client}")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format",
                        "service": self.info.name,
                    }))
                    continue

                msg_type = data.get("type", "")

                # Handle different message types
                if msg_type == "ping":
                    await self._handle_ping(websocket)

                elif msg_type == "health_check":
                    await self._handle_health(websocket)

                elif msg_type in ("analysis_request", "static_analyze", "dynamic_analyze",
                                  "performance_test", "ai_analyze"):
                    # Queue analysis request
                    await self._handle_analysis_request(websocket, data)

                else:
                    self.log.warning(f"Unknown message type: {msg_type}")
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}",
                        "service": self.info.name,
                    }))

        except websockets.exceptions.ConnectionClosed:
            self.log.debug(f"Client disconnected: {client}")
        except Exception as e:
            self.log.error(f"Client handler error for {client}: {e}", exc_info=True)

    # ---- Server Lifecycle --------------------------------------------------
    async def run(self):
        """Start the concurrent analyzer service."""
        host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
        port = int(os.getenv('WEBSOCKET_PORT', self.default_port))

        # Start worker pool
        num_workers = self.info.max_concurrent + 1  # +1 for queue processing
        self.log.info(f"Starting {num_workers} background workers")
        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(i))
            self.workers.append(worker)

        self.log.info(
            f"Starting {self.info.name} v{self.info.version} on {host}:{port} "
            f"(max_concurrent={self.info.max_concurrent}, queue_size={self.info.queue_size})"
        )

        try:
            async with serve(
                self._handle_client,
                host,
                port,
                ping_interval=None,
                ping_timeout=None,
                max_size=100 * 1024 * 1024,  # 100 MB for large responses
            ):
                self.log.info(f"{self.info.name} listening on ws://{host}:{port}")
                await asyncio.Future()  # run forever

        except Exception as e:
            self.log.error(f"Failed to start service: {e}")
            raise
        finally:
            # Cleanup workers
            self.log.info("Shutting down workers...")
            for worker in self.workers:
                worker.cancel()
            await asyncio.gather(*self.workers, return_exceptions=True)
