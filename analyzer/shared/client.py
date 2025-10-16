"""
WebSocket Client Library for Analyzer
=====================================

Simple client library for connecting to the analyzer WebSocket gateway.
Provides high-level interface for requesting analysis and receiving results.
"""
import asyncio
import logging
from typing import Any, Callable, Dict, Optional
import websockets
from websockets.exceptions import ConnectionClosed

from .protocol import (
    WebSocketMessage, MessageType, AnalysisRequest,
    create_analysis_request_message, route_message_to_service
)


logger = logging.getLogger(__name__)


class AnalyzerClient:
    """WebSocket client for analyzer services."""
    
    def __init__(self, uri: str = "ws://localhost:8765", client_id: Optional[str] = None):
        self.uri = uri
        self.client_id = client_id or f"client_{id(self)}"
        self.websocket = None
        self.connected = False
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.pending_requests: Dict[str, asyncio.Future] = {}
        self._listen_task = None
    
    async def connect(self) -> bool:
        """Connect to the WebSocket gateway."""
        try:
            self.websocket = await websockets.connect(
                self.uri,
                ping_interval=None,
                ping_timeout=None,
                close_timeout=10
            )
            self.connected = True
            
            # Send connection acknowledgment
            ack_message = WebSocketMessage(
                type=MessageType.CONNECTION_ACK,
                client_id=self.client_id,
                data={'client_type': 'analyzer_client', 'version': '1.0.0'}
            )
            await self.send_message(ack_message)
            
            # Start listening for messages
            self._listen_task = asyncio.create_task(self._listen_for_messages())
            
            logger.info(f"Connected to analyzer gateway at {self.uri}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.uri}: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from the WebSocket gateway."""
        self.connected = False
        
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        
        if self.websocket:
            await self.websocket.close()
            
        # Cancel any pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        logger.info("Disconnected from analyzer gateway")
    
    async def send_message(self, message: WebSocketMessage):
        """Send a WebSocket message."""
        if not self.connected or not self.websocket:
            raise ConnectionError("Not connected to gateway")
        
        try:
            await self.websocket.send(message.to_json())
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    async def _listen_for_messages(self):
        """Listen for incoming WebSocket messages."""
        try:
            if self.websocket is None:
                return
            async for message_data in self.websocket:
                try:
                    # Handle both str and bytes
                    if isinstance(message_data, bytes):
                        message_data = message_data.decode('utf-8')
                    elif not isinstance(message_data, str):
                        message_data = str(message_data)
                    message = WebSocketMessage.from_json(message_data)
                    await self._handle_message(message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    
        except ConnectionClosed:
            logger.info("WebSocket connection closed")
            self.connected = False
        except Exception as e:
            logger.error(f"Error in message listener: {e}")
            self.connected = False
    
    async def _handle_message(self, message: WebSocketMessage):
        """Handle incoming messages."""
        # Handle responses to pending requests
        if message.correlation_id and message.correlation_id in self.pending_requests:
            future = self.pending_requests.pop(message.correlation_id)
            if not future.done():
                future.set_result(message)
            return
        
        # Handle messages with registered handlers
        if message.type in self.message_handlers:
            try:
                await self.message_handlers[message.type](message)
            except Exception as e:
                logger.error(f"Error in message handler for {message.type}: {e}")
        else:
            logger.debug(f"No handler for message type: {message.type}")
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler."""
        self.message_handlers[message_type] = handler
    
    async def request_analysis(
        self,
        request: AnalysisRequest,
        timeout: float = 300.0
    ) -> WebSocketMessage:
        """Request analysis and wait for result."""
        if not self.connected:
            raise ConnectionError("Not connected to gateway")
        
        # Determine target service
        service = route_message_to_service(WebSocketMessage(
            type=MessageType.ANALYSIS_REQUEST,
            data=request.to_dict()
        ))
        
        # Create request message
        message = create_analysis_request_message(request, self.client_id, service)
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[message.id] = future
        
        try:
            # Send request
            await self.send_message(message)
            
            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            # Clean up pending request
            self.pending_requests.pop(message.id, None)
            raise TimeoutError(f"Analysis request timed out after {timeout} seconds")
        except Exception:
            # Clean up pending request
            self.pending_requests.pop(message.id, None)
            raise
    
    async def request_batch_analysis(
        self,
        requests: list[AnalysisRequest],
        batch_name: str = "Batch Analysis",
        timeout: float = 600.0
    ) -> WebSocketMessage:
        """Request batch analysis and wait for result."""
        if not self.connected:
            raise ConnectionError("Not connected to gateway")
        
        batch_data = {
            'name': batch_name,
            'requests': [req.to_dict() for req in requests],
            'client_id': self.client_id
        }
        
        message = WebSocketMessage(
            type=MessageType.BATCH_REQUEST,
            data=batch_data,
            client_id=self.client_id
        )
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[message.id] = future
        
        try:
            # Send request
            await self.send_message(message)
            
            # Wait for response
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
            
        except asyncio.TimeoutError:
            self.pending_requests.pop(message.id, None)
            raise TimeoutError(f"Batch analysis request timed out after {timeout} seconds")
        except Exception:
            self.pending_requests.pop(message.id, None)
            raise
    
    async def cancel_analysis(self, analysis_id: str):
        """Cancel a running analysis."""
        if not self.connected:
            raise ConnectionError("Not connected to gateway")
        
        message = WebSocketMessage(
            type=MessageType.CANCEL_REQUEST,
            data={'analysis_id': analysis_id},
            client_id=self.client_id
        )
        
        await self.send_message(message)
    
    async def get_status(self, analysis_id: Optional[str] = None) -> WebSocketMessage:
        """Get status of analysis or overall system."""
        if not self.connected:
            raise ConnectionError("Not connected to gateway")
        
        data = {}
        if analysis_id:
            data['analysis_id'] = analysis_id
        
        message = WebSocketMessage(
            type=MessageType.STATUS_REQUEST,
            data=data,
            client_id=self.client_id
        )
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[message.id] = future
        
        try:
            await self.send_message(message)
            result = await asyncio.wait_for(future, timeout=30.0)
            return result
        except asyncio.TimeoutError:
            self.pending_requests.pop(message.id, None)
            raise TimeoutError("Status request timed out")
        except Exception:
            self.pending_requests.pop(message.id, None)
            raise
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.disconnect()


# Convenience functions
async def analyze_code(
    uri: str,
    request: AnalysisRequest,
    progress_handler: Optional[Callable] = None,
    timeout: float = 300.0
) -> Dict[str, Any]:
    """
    Convenience function to analyze code with optional progress updates.
    
    Args:
        uri: WebSocket gateway URI
        request: Analysis request
        progress_handler: Optional callback for progress updates
        timeout: Request timeout in seconds
    
    Returns:
        Analysis result data
    """
    async with AnalyzerClient(uri) as client:
        # Register progress handler if provided
        if progress_handler:
            client.register_handler(MessageType.PROGRESS_UPDATE, progress_handler)
        
        # Request analysis
        result_message = await client.request_analysis(request, timeout)
        
        if result_message.type == MessageType.ERROR:
            raise Exception(f"Analysis failed: {result_message.data}")
        
        return result_message.data


async def batch_analyze(
    uri: str,
    requests: list[AnalysisRequest],
    batch_name: str = "Batch Analysis",
    progress_handler: Optional[Callable] = None,
    timeout: float = 600.0
) -> Dict[str, Any]:
    """
    Convenience function for batch analysis.
    
    Args:
        uri: WebSocket gateway URI
        requests: List of analysis requests
        batch_name: Name for the batch operation
        progress_handler: Optional callback for progress updates
        timeout: Request timeout in seconds
    
    Returns:
        Batch analysis result data
    """
    async with AnalyzerClient(uri) as client:
        # Register progress handler if provided
        if progress_handler:
            client.register_handler(MessageType.PROGRESS_UPDATE, progress_handler)
        
        # Request batch analysis
        result_message = await client.request_batch_analysis(requests, batch_name, timeout)
        
        if result_message.type == MessageType.ERROR:
            raise Exception(f"Batch analysis failed: {result_message.data}")
        
        return result_message.data
