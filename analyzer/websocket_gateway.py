#!/usr/bin/env python3
"""
Analyzer WebSocket Gateway
==========================

Bridges external clients using the shared protocol to the individual analyzer
services running on ports 2001-2004. Accepts MessageType-based JSON messages
and routes them to the appropriate service, translating payloads as needed.

Listens on ws://0.0.0.0:8765
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import websockets
from websockets import serve
try:
    from websockets.server import WebSocketServerProtocol  # type: ignore
except Exception:  # pragma: no cover
    WebSocketServerProtocol = object  # fallback for type hints

# Shared protocol utilities
from shared.protocol import (
    WebSocketMessage,
    MessageType,
    ServiceType,
    AnalysisType,
    create_error_message,
    create_progress_update_message,
    route_message_to_service,
)


level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
level = getattr(logging, level_str, logging.INFO)
logging.basicConfig(level=level)
logger = logging.getLogger("analyzer.websocket_gateway")
logger.setLevel(level)
try:
    # Suppress noisy connection/opening handshake logs across websockets internals
    for name in (
        "websockets",
        "websockets.server",
        "websockets.client",
        "websockets.connection",
        "websockets.protocol",
        "websockets.http",
        "websockets.http11",
        "websockets.legacy",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)
except Exception:
    pass


SERVICE_URLS: Dict[ServiceType, str] = {
    ServiceType.CODE_QUALITY: os.getenv("STATIC_ANALYZER_URL", "ws://localhost:2001"),
    ServiceType.SECURITY_ANALYZER: os.getenv("STATIC_ANALYZER_URL", "ws://localhost:2001"),
    ServiceType.PERFORMANCE_TESTER: os.getenv("PERF_TESTER_URL", "ws://localhost:2003"),
    ServiceType.AI_ANALYZER: os.getenv("AI_ANALYZER_URL", "ws://localhost:2004"),
}

# Simple in-memory event bus
CONNECTED_CLIENTS: set = set()
SUBSCRIBERS: set = set()
EVENT_LOG: list[Dict[str, Any]] = []
MAX_EVENT_LOG = 200
# Optional durable JSONL log file for events (set empty to disable)
EVENT_LOG_FILE = os.getenv("GATEWAY_EVENT_LOG", os.path.join(os.path.dirname(__file__), "gateway_events.jsonl"))


def _record_event(event: Dict[str, Any]):
    """Record in-memory and optionally persist to JSONL file (best-effort)."""
    EVENT_LOG.append(event)
    while len(EVENT_LOG) > MAX_EVENT_LOG:
        EVENT_LOG.pop(0)

    # Persist to JSONL if configured
    try:
        if EVENT_LOG_FILE and isinstance(EVENT_LOG_FILE, str) and len(EVENT_LOG_FILE.strip()) > 0:
            # Offload blocking I/O to a thread to avoid blocking the event loop
            async def _persist(ev: Dict[str, Any]):
                import json as _json
                try:
                    os.makedirs(os.path.dirname(EVENT_LOG_FILE), exist_ok=True)
                except Exception:
                    # Directory may already exist or be current dir
                    pass
                try:
                    # Append line-delimited JSON for easy tailing/ingestion
                    with open(EVENT_LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(_json.dumps(ev, ensure_ascii=False) + "\n")
                except Exception:
                    # Swallow persistence errors silently
                    pass

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_persist(dict(event)))
            except RuntimeError:
                # No running loop (unlikely here); fallback to synchronous write
                try:
                    import json as _json
                    with open(EVENT_LOG_FILE, 'a', encoding='utf-8') as f:
                        f.write(_json.dumps(event, ensure_ascii=False) + "\n")
                except Exception:
                    pass
    except Exception:
        # Never propagate persistence errors
        pass


async def broadcast_event(stage: str, message: str = "", *,
                          service: Optional[str] = None,
                          correlation_id: Optional[str] = None,
                          details: Optional[Dict[str, Any]] = None):
    """Broadcast an event and keep a short history.

    If possible, emit a protocol-compliant PROGRESS_UPDATE. If details contain
    extra keys, sanitize them to ProgressUpdate-compatible fields to avoid
    exceptions that could otherwise downgrade the event type.
    """
    payload = {
        'stage': stage,
        'message': message,
        'service': service,
        'timestamp': datetime.utcnow().isoformat(),
    }
    if details:
        payload['details'] = details

    # Log with reduced verbosity to prevent spam
    if stage in {"error", "failed"}:
        logger.warning(f"[{stage}] {message} service={service}")
    elif stage in {"completed"} and "health" not in message.lower():
        # Skip logging routine health check completions
        logger.info(f"[{stage}] {message} service={service}")
    elif stage in {"started", "running"} and any(keyword in message.lower() for keyword in ["health", "monitor", "ping"]):
        # Reduce monitoring/health check log level to debug
        logger.debug(f"[{stage}] {message} service={service}")
    else:
        logger.debug(f"[{stage}] {message} service={service}")
    _record_event({'stage': stage, 'message': message, 'service': service, 'correlation_id': correlation_id, 'timestamp': payload['timestamp']})

    # Wrap using the shared protocol helper with sanitized kwargs
    try:
        progress_kwargs: Dict[str, Any] = {}
        if isinstance(details, dict):
            # Only pass fields supported by ProgressUpdate dataclass
            allowed = {"current_file", "files_processed", "total_files", "issues_found", "progress"}
            for k in allowed:
                if k in details:
                    progress_kwargs[k] = details[k]

        msg = create_progress_update_message(
            analysis_id=correlation_id or "",
            stage=stage,
            progress=float(progress_kwargs.get("progress", 0.0) or 0.0),  # qualitative stage if unknown
            message=message,
            **{k: v for k, v in progress_kwargs.items() if k != "progress"}
        )
    except Exception:
        # Fallback to a generic STATUS_UPDATE if helper fails
        msg = WebSocketMessage(type=MessageType.STATUS_UPDATE, data=payload, correlation_id=correlation_id)

    # Send to all current subscribers
    if SUBSCRIBERS:
        dead: list = []
        for ws in list(SUBSCRIBERS):
            try:
                await ws.send(msg.to_json())
            except Exception:
                dead.append(ws)
        for ws in dead:
            SUBSCRIBERS.discard(ws)


async def send_to_service(service: ServiceType, message: Dict[str, Any], timeout: int = 300) -> Dict[str, Any]:
    """Send a JSON message to a specific analyzer service and stream responses.

    Rebroadcasts any progress_update messages to subscribers. Returns when a
    terminal message (e.g., *_result or error) is received or the timeout expires.
    """
    url = SERVICE_URLS.get(service)
    if not url:
        return {"type": "error", "status": "error", "error": f"No URL configured for {service.value}"}

    try:
        await broadcast_event('routing', f"Routing request to {service.value}", service=service.value, details={'outbound_type': message.get('type')})
        async with websockets.connect(
            url, open_timeout=10, close_timeout=10, ping_interval=None, ping_timeout=None
        ) as ws:
            await broadcast_event('service_connected', f"Connected to {service.value}", service=service.value)
            await ws.send(json.dumps(message))
            await broadcast_event('sent', f"Sent to {service.value}", service=service.value, details={'payload_type': message.get('type')})
            # Stream loop: handle progress messages until a final result is received
            end_time = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = end_time - asyncio.get_event_loop().time()
                if remaining <= 0:
                    raise asyncio.TimeoutError(f"Timeout waiting for {service.value} response")
                raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                try:
                    data = json.loads(raw)
                except Exception:
                    await broadcast_event('error', f"Malformed message from {service.value}", service=service.value)
                    continue

                mtype = str(data.get('type', '')).lower()
                corr = data.get('correlation_id') or message.get('id')

                if mtype == 'progress_update':
                    # Normalize common fields
                    d = data if isinstance(data, dict) else {}
                    stage = d.get('stage') or (d.get('data') or {}).get('stage') or 'progress'
                    msg = d.get('message') or (d.get('data') or {}).get('message') or ''
                    await broadcast_event(stage, msg, service=service.value, correlation_id=corr, details=d)
                    continue

                # Treat status_update as noteworthy but not terminal
                if mtype == 'status_update':
                    await broadcast_event('status', f"Status from {service.value}", service=service.value, correlation_id=corr, details=data)
                    continue

                await broadcast_event('received_response', f"Response from {service.value}", service=service.value)
                return data
    except asyncio.TimeoutError as e:
        # Timeouts are expected under load; keep them low-noise
        await broadcast_event('timeout', f"{service.value} timeout: {e}", service=service.value)
        return {"type": "error", "status": "timeout", "error": str(e)}
    except (ConnectionRefusedError, OSError) as e:
        # Service likely not up yet; do not escalate to error severity
        await broadcast_event('service_unavailable', f"{service.value} unavailable: {e}", service=service.value)
        return {"type": "error", "status": "unavailable", "error": str(e)}
    except Exception as e:
        # For protocol/handshake issues that slip through, keep as a generic error
        try:
            import websockets as _ws
            if isinstance(e, getattr(_ws.exceptions, 'InvalidHandshake', tuple())):
                await broadcast_event('handshake_issue', f"{service.value} handshake: {e}", service=service.value)
                return {"type": "error", "status": "handshake", "error": str(e)}
        except Exception:
            pass
        await broadcast_event('error', f"{service.value} error: {e}", service=service.value)
        return {"type": "error", "status": "error", "error": str(e)}


def map_analysis_request_to_service_message(req_msg: WebSocketMessage) -> Optional[Tuple[ServiceType, Dict[str, Any]]]:
    """Translate a shared-protocol analysis_request into a service-specific message payload."""
    data = req_msg.data or {}
    try:
        _ = AnalysisType(data.get("analysis_type"))
    except Exception:
        _ = None

    # Route based on protocol helper first
    target_service = route_message_to_service(req_msg)

    # Map shared request fields
    model_slug = data.get("model") or data.get("model_slug") or "unknown"
    app_number = int(data.get("app_number", 1))
    options = data.get("options") or {}

    if target_service in (ServiceType.CODE_QUALITY, ServiceType.SECURITY_ANALYZER):
        # Static analyzer expects 'static_analyze'
        payload = {
            "type": "static_analyze",
            "model_slug": model_slug,
            "app_number": app_number,
            # pass configuration when present
            "config": options if options else None,
            "timestamp": datetime.now().isoformat(),
            "id": req_msg.id,
        }
        return ServiceType.SECURITY_ANALYZER, payload

    if target_service is ServiceType.PERFORMANCE_TESTER:
        # Performance tester expects 'performance_test'
        # Pull target_url or target_urls from options if provided
        target_url = options.get("target_url") or data.get("target_url")
        target_urls = options.get("target_urls") or ([target_url] if target_url else [])
        payload = {
            "type": "performance_test",
            "model_slug": model_slug,
            "app_number": app_number,
            "target_urls": target_urls,
            "config": options if options else None,
            "timestamp": datetime.now().isoformat(),
            "id": req_msg.id,
        }
        return ServiceType.PERFORMANCE_TESTER, payload

    if target_service is ServiceType.AI_ANALYZER:
        payload = {
            "type": "ai_analysis",
            "model_slug": model_slug,
            "app_number": app_number,
            "config": options if options else None,
            "timestamp": datetime.now().isoformat(),
            "id": req_msg.id,
        }
        return ServiceType.AI_ANALYZER, payload

    if target_service is ServiceType.DEPENDENCY_SCANNER:
        # Not implemented: return None to yield an error
        return None

    # Fallback: try static analyzer
    payload = {
        "type": "static_analyze",
        "model_slug": model_slug,
        "app_number": app_number,
        "config": options if options else None,
        "timestamp": datetime.now().isoformat(),
        "id": req_msg.id,
    }
    return ServiceType.SECURITY_ANALYZER, payload


async def handle_client(websocket):
    client = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.debug(f"Client connected: {client}")
    CONNECTED_CLIENTS.add(websocket)

    try:
        async for raw in websocket:
            try:
                # Accept both shared-protocol messages and raw dicts
                incoming: Dict[str, Any] = json.loads(raw)
                if not isinstance(incoming, dict):
                    raise ValueError("Invalid message format")

                # Ensure minimal fields exist for the protocol parser
                msg: WebSocketMessage
                try:
                    msg = WebSocketMessage.from_dict(incoming)
                except Exception:
                    # Synthesize a minimal wrapper if needed
                    msg = WebSocketMessage(type=MessageType(incoming.get("type", "error")), data=incoming)

                # Event: message received at gateway
                await broadcast_event('received', f"Message {msg.type}", details={'client': client})

                if msg.type == MessageType.CONNECTION_ACK:
                    ack = WebSocketMessage(
                        type=MessageType.CONNECTION_ACK,
                        data={"status": "acknowledged", "server_time": datetime.utcnow().isoformat()},
                    )
                    await websocket.send(ack.to_json())
                    continue

                if msg.type.name.lower() == "ping" or msg.type == MessageType.HEARTBEAT:
                    hb = WebSocketMessage(type=MessageType.HEARTBEAT, data={"status": "alive"})
                    await websocket.send(hb.to_json())
                    continue

                if msg.type == MessageType.STATUS_REQUEST:
                    # Subscription handling: {'subscribe': 'events'|'none', 'replay': true}
                    d = (msg.data or {}) if hasattr(msg, 'data') else {}
                    subscribe = False
                    if isinstance(d, dict):
                        sub_val = d.get('subscribe')
                        subscribe = (bool(sub_val) or (isinstance(sub_val, str) and sub_val.lower() in ('events','true','yes')))
                    if subscribe:
                        SUBSCRIBERS.add(websocket)
                        await broadcast_event('subscriber_added', f"Subscriber added: {client}", details={'client': client})
                        if isinstance(d, dict) and d.get('replay'):
                            # Replay recent events to the new subscriber
                            for ev in EVENT_LOG[-50:]:
                                replay = WebSocketMessage(type=MessageType.STATUS_UPDATE, data=ev)
                                try:
                                    await websocket.send(replay.to_json())
                                except Exception:
                                    break
                    # Always send a status snapshot
                    data = {
                        "services": {st.value: SERVICE_URLS.get(st) for st in SERVICE_URLS},
                        "timestamp": datetime.utcnow().isoformat(),
                        "subscribed": websocket in SUBSCRIBERS,
                    }
                    status_msg = WebSocketMessage(type=MessageType.STATUS_UPDATE, data=data, correlation_id=msg.id)
                    await websocket.send(status_msg.to_json())
                    continue

                if msg.type == MessageType.ANALYSIS_REQUEST:
                    mapping = map_analysis_request_to_service_message(msg)
                    if not mapping:
                        err = create_error_message(
                            code="unsupported",
                            message="Requested analysis/service not supported",
                            correlation_id=msg.id,
                        )
                        await websocket.send(err.to_json())
                        await broadcast_event('failed', 'Unsupported analysis request', correlation_id=msg.id)
                        continue

                    service, payload = mapping
                    # Send request to target service
                    await broadcast_event('dispatch', f"Dispatch to {service.value}", service=service.value, correlation_id=msg.id)
                    result = await send_to_service(service, payload)

                    # Wrap and forward back to client
                    wrapped = WebSocketMessage(
                        type=MessageType.ANALYSIS_RESULT,
                        data=result,
                        correlation_id=msg.id,
                    )
                    await websocket.send(wrapped.to_json())
                    await broadcast_event('completed', f"Completed {service.value}", service=service.value, correlation_id=msg.id,
                                           details={'result_status': result.get('status')})
                    continue

                # Allow external producers to publish progress updates via gateway
                if msg.type == MessageType.PROGRESS_UPDATE:
                    d = msg.data if isinstance(msg.data, dict) else {}
                    stage = d.get('stage', 'progress')
                    message = d.get('message', '')
                    service = d.get('service')
                    await broadcast_event(stage, message, service=service, correlation_id=msg.correlation_id, details=d)
                    # Ack back so producers can proceed
                    ack = WebSocketMessage(type=MessageType.STATUS_UPDATE, data={'ack': True, 'stage': stage})
                    await websocket.send(ack.to_json())
                    continue

                # Unknown message type - return protocol error
                err = create_error_message(
                    code="unknown_type",
                    message=f"Unknown message type: {msg.type}",
                    correlation_id=msg.id,
                )
                await websocket.send(err.to_json())
                await broadcast_event('failed', f"Unknown message type: {msg.type}")
            except Exception as e:
                logger.error(f"Error handling message from {client}: {e}")
                try:
                    err = create_error_message(code="internal_error", message=str(e))
                    await websocket.send(err.to_json())
                except Exception:
                    pass
    except websockets.exceptions.ConnectionClosed:
        logger.debug(f"Client disconnected: {client}")
    except Exception as e:
        logger.error(f"WebSocket error with {client}: {e}")
    finally:
        SUBSCRIBERS.discard(websocket)
        CONNECTED_CLIENTS.discard(websocket)


async def main():
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8765"))
    logger.info(f"Starting Analyzer Gateway on ws://{host}:{port}")
    async with serve(handle_client, host, port):
        logger.info("Gateway listening and ready")
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Gateway stopped by user")
    except Exception as e:
        logger.error(f"Gateway crashed: {e}")
        raise
