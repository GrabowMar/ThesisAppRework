"""
WebSocket Gateway for Analyzer Infrastructure
============================================

Central hub for all WebSocket communication between clients and analysis services.
Handles message routing, connection management, and service discovery.
"""
import asyncio
import logging
import time
from typing import Dict, Set
import websockets
from websockets.exceptions import ConnectionClosed
from dataclasses import dataclass, field

from shared.protocol import (
    WebSocketMessage, MessageType, ServiceType,
    create_error_message, create_heartbeat_message, validate_message,
    route_message_to_service, create_request_from_dict
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class ConnectedClient:
    """Information about a connected client."""
    websocket: websockets.WebSocketServerProtocol
    client_id: str
    client_type: str = "unknown"
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    message_count: int = 0


@dataclass
class ConnectedService:
    """Information about a connected service."""
    websocket: websockets.WebSocketServerProtocol
    service_id: str
    service_type: ServiceType
    capabilities: list = field(default_factory=list)
    connected_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)
    health_status: str = "unknown"
    active_analyses: int = 0


class AnalyzerGateway:
    """WebSocket gateway for analyzer infrastructure."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.clients: Dict[str, ConnectedClient] = {}
        self.services: Dict[str, ConnectedService] = {}
        self.service_by_type: Dict[ServiceType, Set[str]] = {}
        self.running = False
        self.server = None
        
        # Initialize service type mappings
        for service_type in ServiceType:
            self.service_by_type[service_type] = set()
    
    async def start(self):
        """Start the WebSocket gateway server."""
        logger.info(f"Starting analyzer gateway on {self.host}:{self.port}")
        
        try:
            self.server = await websockets.serve(
                self.handle_connection,
                self.host,
                self.port,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=1024 * 1024,  # 1MB max message size
                max_queue=32
            )
            
            self.running = True
            
            # Start background tasks
            asyncio.create_task(self._cleanup_stale_connections())
            asyncio.create_task(self._send_heartbeats())
            
            logger.info("Analyzer gateway started successfully")
            await self.server.wait_closed()
            
        except Exception as e:
            logger.error(f"Failed to start gateway: {e}")
            raise
    
    async def stop(self):
        """Stop the WebSocket gateway server."""
        logger.info("Stopping analyzer gateway")
        self.running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        
        # Close all client connections
        for client in list(self.clients.values()):
            try:
                await client.websocket.close()
            except Exception:
                pass
        
        # Close all service connections
        for service in list(self.services.values()):
            try:
                await service.websocket.close()
            except Exception:
                pass
        
        logger.info("Analyzer gateway stopped")
    
    async def handle_connection(self, websocket, path):
        """Handle a new WebSocket connection."""
        client_id = None
        try:
            logger.info(f"New connection from {websocket.remote_address}")
            
            # Wait for initial message to identify client/service
            async for message_data in websocket:
                try:
                    message = WebSocketMessage.from_json(message_data)
                    
                    if message.type == MessageType.CONNECTION_ACK:
                        # Client connection
                        client_id = message.client_id or f"client_{id(websocket)}"
                        await self._register_client(websocket, client_id, message.data)
                        break
                    elif message.type == MessageType.SERVICE_REGISTER:
                        # Service connection
                        await self._register_service(websocket, message.data)
                        break
                    else:
                        # Unknown connection type
                        error_msg = create_error_message(
                            "INVALID_HANDSHAKE",
                            "Expected CONNECTION_ACK or SERVICE_REGISTER message",
                            suggestion="Send proper handshake message first"
                        )
                        await websocket.send(error_msg.to_json())
                        return
                        
                except Exception as e:
                    logger.error(f"Error processing handshake: {e}")
                    error_msg = create_error_message(
                        "HANDSHAKE_ERROR",
                        f"Failed to process handshake: {e}"
                    )
                    await websocket.send(error_msg.to_json())
                    return
            
            # Handle messages for registered client/service
            async for message_data in websocket:
                try:
                    message = WebSocketMessage.from_json(message_data)
                    await self._handle_message(websocket, message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    error_msg = create_error_message(
                        "MESSAGE_ERROR",
                        f"Failed to process message: {e}"
                    )
                    await websocket.send(error_msg.to_json())
                    
        except ConnectionClosed:
            logger.info(f"Connection closed for {client_id or 'unknown'}")
        except Exception as e:
            logger.error(f"Connection error: {e}")
        finally:
            await self._cleanup_connection(websocket)
    
    async def _register_client(self, websocket, client_id: str, data: dict):
        """Register a new client connection."""
        client_type = data.get('client_type', 'unknown')
        
        # Remove existing client with same ID
        if client_id in self.clients:
            old_client = self.clients[client_id]
            try:
                await old_client.websocket.close()
            except Exception:
                pass
        
        self.clients[client_id] = ConnectedClient(
            websocket=websocket,
            client_id=client_id,
            client_type=client_type
        )
        
        logger.info(f"Registered client: {client_id} ({client_type})")
        
        # Send acknowledgment
        ack_message = WebSocketMessage(
            type=MessageType.CONNECTION_ACK,
            data={'status': 'connected', 'gateway_version': '1.0.0'}
        )
        await websocket.send(ack_message.to_json())
    
    async def _register_service(self, websocket, data: dict):
        """Register a new service connection."""
        service_type = ServiceType(data['service_type'])
        service_id = data['service_id']
        capabilities = data.get('capabilities', [])
        
        # Remove existing service with same ID
        if service_id in self.services:
            old_service = self.services[service_id]
            try:
                await old_service.websocket.close()
            except Exception:
                pass
            self.service_by_type[old_service.service_type].discard(service_id)
        
        self.services[service_id] = ConnectedService(
            websocket=websocket,
            service_id=service_id,
            service_type=service_type,
            capabilities=capabilities
        )
        
        self.service_by_type[service_type].add(service_id)
        
        logger.info(f"Registered service: {service_id} ({service_type.value})")
        
        # Send acknowledgment
        ack_message = WebSocketMessage(
            type=MessageType.SERVICE_REGISTER,
            data={'status': 'registered', 'gateway_version': '1.0.0'}
        )
        await websocket.send(ack_message.to_json())
    
    async def _handle_message(self, websocket, message: WebSocketMessage):
        """Handle an incoming message."""
        if not validate_message(message.to_dict()):
            error_msg = create_error_message(
                "INVALID_MESSAGE",
                "Message failed validation"
            )
            await websocket.send(error_msg.to_json())
            return
        
        # Update client/service activity
        await self._update_activity(websocket, message)
        
        # Route message based on type
        if message.type == MessageType.HEARTBEAT:
            await self._handle_heartbeat(websocket, message)
        elif message.type == MessageType.ANALYSIS_REQUEST:
            await self._handle_analysis_request(websocket, message)
        elif message.type == MessageType.BATCH_REQUEST:
            await self._handle_batch_request(websocket, message)
        elif message.type == MessageType.STATUS_REQUEST:
            await self._handle_status_request(websocket, message)
        elif message.type == MessageType.CANCEL_REQUEST:
            await self._handle_cancel_request(websocket, message)
        elif message.type in [MessageType.ANALYSIS_RESULT, MessageType.PROGRESS_UPDATE, MessageType.STATUS_UPDATE]:
            await self._route_to_client(message)
        else:
            logger.warning(f"Unhandled message type: {message.type}")
    
    async def _handle_analysis_request(self, websocket, message: WebSocketMessage):
        """Handle analysis request from client."""
        try:
            request_data = message.data.get('request', message.data)
            create_request_from_dict(request_data)  # Validate request format
            
            # Route to appropriate service
            target_service = route_message_to_service(message)
            available_services = self.service_by_type.get(target_service, set())
            
            if not available_services:
                error_msg = create_error_message(
                    "SERVICE_UNAVAILABLE",
                    f"No {target_service.value} services available",
                    correlation_id=message.id,
                    suggestion="Try again later or check service status"
                )
                await websocket.send(error_msg.to_json())
                return
            
            # Select service (simple round-robin for now)
            service_id = next(iter(available_services))
            service = self.services[service_id]
            
            # Forward message to service
            message.correlation_id = message.id  # Set correlation for response routing
            await service.websocket.send(message.to_json())
            
            logger.info(f"Routed analysis request {message.id} to {service_id}")
            
        except Exception as e:
            logger.error(f"Error handling analysis request: {e}")
            error_msg = create_error_message(
                "REQUEST_ERROR",
                f"Failed to process analysis request: {e}",
                correlation_id=message.id
            )
            await websocket.send(error_msg.to_json())
    
    async def _handle_batch_request(self, websocket, message: WebSocketMessage):
        """Handle batch analysis request."""
        try:
            batch_data = message.data
            requests = batch_data.get('requests', [])
            
            if not requests:
                error_msg = create_error_message(
                    "EMPTY_BATCH",
                    "Batch request contains no analysis requests",
                    correlation_id=message.id
                )
                await websocket.send(error_msg.to_json())
                return
            
            # For now, process requests sequentially
            # In a production system, this would be handled by a batch coordinator service
            results = []
            
            for i, request_data in enumerate(requests):
                try:
                    request = create_request_from_dict(request_data)
                    
                    # Create individual request message
                    individual_message = WebSocketMessage(
                        type=MessageType.ANALYSIS_REQUEST,
                        data={'request': request.to_dict()},
                        client_id=message.client_id,
                        correlation_id=f"{message.id}_{i}"
                    )
                    
                    # Route to service
                    await self._handle_analysis_request(websocket, individual_message)
                    
                except Exception as e:
                    logger.error(f"Error processing batch item {i}: {e}")
                    results.append({
                        'status': 'failed',
                        'error': str(e)
                    })
            
            logger.info(f"Started batch analysis {message.id} with {len(requests)} requests")
            
        except Exception as e:
            logger.error(f"Error handling batch request: {e}")
            error_msg = create_error_message(
                "BATCH_ERROR",
                f"Failed to process batch request: {e}",
                correlation_id=message.id
            )
            await websocket.send(error_msg.to_json())
    
    async def _handle_status_request(self, websocket, message: WebSocketMessage):
        """Handle status request."""
        try:
            analysis_id = message.data.get('analysis_id') if message.data else None
            
            if analysis_id:
                # Request status for specific analysis
                # This would typically be forwarded to the appropriate service
                status_data = {'analysis_id': analysis_id, 'status': 'unknown'}
            else:
                # Return gateway status
                status_data = {
                    'gateway_status': 'running',
                    'connected_clients': len(self.clients),
                    'connected_services': len(self.services),
                    'services_by_type': {
                        service_type.value: len(services)
                        for service_type, services in self.service_by_type.items()
                    },
                    'uptime': time.time() - (min(
                        client.connected_at for client in self.clients.values()
                    ) if self.clients else time.time())
                }
            
            response = WebSocketMessage(
                type=MessageType.STATUS_UPDATE,
                data=status_data,
                correlation_id=message.id
            )
            await websocket.send(response.to_json())
            
        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            error_msg = create_error_message(
                "STATUS_ERROR",
                f"Failed to get status: {e}",
                correlation_id=message.id
            )
            await websocket.send(error_msg.to_json())
    
    async def _handle_cancel_request(self, websocket, message: WebSocketMessage):
        """Handle analysis cancellation request."""
        # This would typically be forwarded to the appropriate service
        logger.info(f"Cancel request for analysis {message.data.get('analysis_id')}")
    
    async def _handle_heartbeat(self, websocket, message: WebSocketMessage):
        """Handle heartbeat message."""
        # Update service health if this is from a service
        for service in self.services.values():
            if service.websocket == websocket:
                service.last_heartbeat = time.time()
                if message.data:
                    service.health_status = message.data.get('status', 'healthy')
                    service.active_analyses = message.data.get('active_analyses', 0)
                break
    
    async def _route_to_client(self, message: WebSocketMessage):
        """Route message to appropriate client."""
        if message.client_id and message.client_id in self.clients:
            client = self.clients[message.client_id]
            try:
                await client.websocket.send(message.to_json())
            except Exception as e:
                logger.error(f"Failed to send message to client {message.client_id}: {e}")
        else:
            logger.warning(f"Cannot route message to unknown client: {message.client_id}")
    
    async def _update_activity(self, websocket, message: WebSocketMessage):
        """Update activity timestamp for client/service."""
        # Update client activity
        for client in self.clients.values():
            if client.websocket == websocket:
                client.last_heartbeat = time.time()
                client.message_count += 1
                break
        
        # Update service activity
        for service in self.services.values():
            if service.websocket == websocket:
                service.last_heartbeat = time.time()
                break
    
    async def _cleanup_connection(self, websocket):
        """Clean up a disconnected connection."""
        # Remove client
        client_to_remove = None
        for client_id, client in self.clients.items():
            if client.websocket == websocket:
                client_to_remove = client_id
                break
        
        if client_to_remove:
            del self.clients[client_to_remove]
            logger.info(f"Removed client: {client_to_remove}")
        
        # Remove service
        service_to_remove = None
        for service_id, service in self.services.items():
            if service.websocket == websocket:
                service_to_remove = service_id
                self.service_by_type[service.service_type].discard(service_id)
                break
        
        if service_to_remove:
            del self.services[service_to_remove]
            logger.info(f"Removed service: {service_to_remove}")
    
    async def _cleanup_stale_connections(self):
        """Periodically clean up stale connections."""
        while self.running:
            try:
                current_time = time.time()
                stale_threshold = 120  # 2 minutes
                
                # Check for stale clients
                stale_clients = [
                    client_id for client_id, client in self.clients.items()
                    if current_time - client.last_heartbeat > stale_threshold
                ]
                
                for client_id in stale_clients:
                    client = self.clients[client_id]
                    try:
                        await client.websocket.close()
                    except Exception:
                        pass
                    logger.info(f"Cleaned up stale client: {client_id}")
                
                # Check for stale services
                stale_services = [
                    service_id for service_id, service in self.services.items()
                    if current_time - service.last_heartbeat > stale_threshold
                ]
                
                for service_id in stale_services:
                    service = self.services[service_id]
                    try:
                        await service.websocket.close()
                    except Exception:
                        pass
                    logger.info(f"Cleaned up stale service: {service_id}")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(60)
    
    async def _send_heartbeats(self):
        """Send periodic heartbeats to services."""
        while self.running:
            try:
                heartbeat = create_heartbeat_message(
                    service_id="gateway",
                    status="healthy",
                    uptime=time.time(),
                    connected_clients=len(self.clients),
                    connected_services=len(self.services)
                )
                
                # Send to all services
                for service in list(self.services.values()):
                    try:
                        await service.websocket.send(heartbeat.to_json())
                    except Exception as e:
                        logger.error(f"Failed to send heartbeat to {service.service_id}: {e}")
                
                await asyncio.sleep(30)  # Send every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in heartbeat task: {e}")
                await asyncio.sleep(30)


async def main():
    """Main entry point for the gateway."""
    import signal
    
    gateway = AnalyzerGateway()
    
    # Handle shutdown signals
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(gateway.stop())
    
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    try:
        await gateway.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
