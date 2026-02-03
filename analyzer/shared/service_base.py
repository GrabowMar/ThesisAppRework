#!/usr/bin/env python3
"""
Shared Base for Analyzer Services
=================================

Provides a lightweight, reusable base class for WebSocket-based analyzer
services. Handles:
- Logging setup and websockets noise suppression
- Uniform ping and health_check handling
- Consistent environment-driven host/port configuration
- Progress event emission to an optional gateway
- Normalized selected tools extraction from incoming messages

Each concrete service should subclass BaseWSService and implement:
- available tools detection via _detect_available_tools()
- handle_message() to process service-specific message types

This module intentionally avoids coupling to the shared protocol models to
preserve compatibility with existing simple message schemas used in services.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
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
    except Exception:  # pragma: no cover
        pass
    return logger


BASE_LOGGER = _setup_logging()


@dataclass
class ServiceInfo:
    name: str
    version: str = "1.0.0"
    started_at: datetime = datetime.now()


class BaseWSService:
    """Base class for analyzer WebSocket services."""

    def __init__(self, service_name: str, default_port: int, version: str = "1.0.0"):
        self.log = logging.getLogger(service_name) if logging.getLogger(service_name) else BASE_LOGGER
        self.info = ServiceInfo(service_name, version, datetime.now())
        self.default_port = default_port
        self.available_tools: List[str] = []
        try:
            self.available_tools = self._detect_available_tools()
        except Exception as e:  # pragma: no cover - defensive
            self.log.debug(f"Tool detection failed: {e}")
            self.available_tools = []

    # ---- Hooks to override -------------------------------------------------
    def _detect_available_tools(self) -> List[str]:  # pragma: no cover - abstract
        """Detect and return a list of available tool names for this service."""
        return []

    async def handle_message(self, websocket, message_data: Dict[str, Any]):  # pragma: no cover - abstract
        """Service-specific message handling. Must be implemented by subclasses."""
        raise NotImplementedError

    # ---- Utilities ---------------------------------------------------------
    @staticmethod
    def extract_selected_tools(message: Dict[str, Any]) -> Optional[Set[str]]:
        """Extract normalized selected tools set from message.

        Looks for top-level 'tools' first, then 'config.tools'. Returns a
        lowercase set or None if no selection provided.
        """
        tools = message.get("tools")
        if not tools and isinstance(message.get("config"), dict):
            tools = message["config"].get("tools")
        if tools and isinstance(tools, list):
            try:
                return {str(t).lower() for t in tools}
            except Exception:
                return None
        return None

    async def send_progress(self, stage: str, message: str = "", analysis_id: Optional[str] = None, **kwargs) -> None:
        """Best-effort progress event to gateway via WebSocket.

        Non-blocking and failure-tolerant by design.
        """
        gw = os.getenv('GATEWAY_URL', 'ws://localhost:8765')
        payload = {
            'type': 'progress_update',
            'correlation_id': analysis_id or kwargs.get('analysis_id') or '',
            'stage': stage,
            'message': message,
            'service': self.info.name,
            'data': {
                'stage': stage,
                'message': message,
                **kwargs,
            },
            'timestamp': datetime.now().isoformat(),
        }
        try:
            # Disable keepalive pings when talking to gateway as well
            async with websockets.connect(gw, open_timeout=1, close_timeout=1, ping_interval=None) as ws:
                await ws.send(json.dumps(payload))
        except Exception:
            # Silent by design
            pass

    # ---- Common message helpers -------------------------------------------
    async def _handle_ping(self, websocket):
        await websocket.send(json.dumps({
            "type": "pong",
            "timestamp": datetime.now().isoformat(),
            "service": self.info.name,
        }))

    async def _handle_health(self, websocket):
        uptime = (datetime.now() - self.info.started_at).total_seconds()
        await websocket.send(json.dumps({
            "type": "health_response",
            "status": "healthy",
            "service": self.info.name,
            "version": self.info.version,
            "uptime": uptime,
            "available_tools": self.available_tools,
            "timestamp": datetime.now().isoformat(),
        }))

    # ---- Server lifecycle --------------------------------------------------
    async def _handle_client(self, websocket):
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
                if msg_type == "ping":
                    await self._handle_ping(websocket)
                elif msg_type == "health_check":
                    await self._handle_health(websocket)
                else:
                    await self.handle_message(websocket, data)
                    # Only close for terminal messages (analysis_result, error)
                    # Allow streaming for progress_update and status_update messages
                    if msg_type in ("analysis_request", "static_analyze", "dynamic_analyze", "performance_test", "ai_analyze"):
                        # Analysis requests are terminal - close connection gracefully after response sent
                        self.log.debug(f"Analysis complete for {client}, closing connection")
                        # IMPORTANT: Wait briefly to ensure the response is fully transmitted to client
                        # before initiating close handshake. Large responses (100MB+) need time to flush.
                        await asyncio.sleep(0.5)
                        await websocket.close(code=1000, reason="Analysis complete")
                        break  # Exit the message loop after closing

        except websockets.exceptions.ConnectionClosed:
            self.log.debug(f"Client disconnected: {client}")
        except Exception as e:  # pragma: no cover
            self.log.error(f"Client handler error for {client}: {e}")

    async def run(self):
        host = os.getenv('WEBSOCKET_HOST', '0.0.0.0')
        port = int(os.getenv('WEBSOCKET_PORT', self.default_port))
        self.log.info(f"Starting {self.info.name} on {host}:{port}")
        try:
            # Disable keepalive pings on the server to avoid ping timeouts while
            # long-running subprocess tasks block the event loop.
            # Increase max_size to 100MB to handle large SARIF responses
            async with serve(
                self._handle_client,
                host,
                port,
                ping_interval=None,
                ping_timeout=None,
                max_size=100 * 1024 * 1024,  # 100 MB for large SARIF responses
            ):
                self.log.info(f"{self.info.name} listening on ws://{host}:{port}")
                await asyncio.Future()  # run forever
        except Exception as e:
            self.log.error(f"Failed to start service: {e}")
            raise
