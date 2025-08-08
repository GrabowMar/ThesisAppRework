#!/usr/bin/env python3
"""
Static Analyzer Service - Simple WebSocket Server
================================================

A simple static analysis service that responds to health checks and ping messages.
This service listens on port 8001 and can be extended to perform actual static analysis.

Usage:
    python main.py

The service will start on ws://localhost:8001
"""

import asyncio
import json
import logging
import os
from datetime import datetime
import websockets
from websockets.asyncio.server import serve

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StaticAnalyzer:
    """Simple static analyzer service."""
    
    def __init__(self):
        self.service_name = "static-analyzer"
        self.version = "1.0.0"
        self.start_time = datetime.now()
    
    async def handle_message(self, websocket, message_data):
        """Handle incoming messages."""
        try:
            msg_type = message_data.get("type", "unknown")
            
            if msg_type == "ping":
                # Respond to ping with pong
                response = {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                logger.info("Responded to ping")
                
            elif msg_type == "health_check":
                # Health check response
                uptime = (datetime.now() - self.start_time).total_seconds()
                response = {
                    "type": "health_response",
                    "status": "healthy",
                    "service": self.service_name,
                    "version": self.version,
                    "uptime": uptime,
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info("Responded to health check")
                
            elif msg_type == "analyze":
                # Simple analysis response
                model_slug = message_data.get("model_slug", "unknown")
                app_number = message_data.get("app_number", 0)
                
                # Simulate analysis
                await asyncio.sleep(1)  # Simulate processing time
                
                response = {
                    "type": "analysis_result",
                    "status": "success",
                    "model_slug": model_slug,
                    "app_number": app_number,
                    "service": self.service_name,
                    "results": {
                        "total_files": 10,
                        "issues_found": 3,
                        "severity_breakdown": {
                            "high": 1,
                            "medium": 1,
                            "low": 1
                        }
                    },
                    "timestamp": datetime.now().isoformat()
                }
                await websocket.send(json.dumps(response))
                logger.info(f"Completed analysis for {model_slug} app {app_number}")
                
            else:
                # Unknown message type
                response = {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                    "service": self.service_name
                }
                await websocket.send(json.dumps(response))
                logger.warning(f"Unknown message type: {msg_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            error_response = {
                "type": "error",
                "message": f"Internal error: {str(e)}",
                "service": self.service_name
            }
            try:
                await websocket.send(json.dumps(error_response))
            except Exception:
                pass  # Connection might be closed

async def handle_client(websocket):
    """Handle client connections."""
    analyzer = StaticAnalyzer()
    client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
    logger.info(f"New client connected: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                # Parse JSON message
                message_data = json.loads(message)
                logger.debug(f"Received message: {message_data}")
                
                # Handle the message
                await analyzer.handle_message(websocket, message_data)
                
            except json.JSONDecodeError:
                logger.error("Received invalid JSON message")
                error_response = {
                    "type": "error",
                    "message": "Invalid JSON format",
                    "service": analyzer.service_name
                }
                await websocket.send(json.dumps(error_response))
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client disconnected: {client_addr}")
    except Exception as e:
        logger.error(f"Unexpected error with client {client_addr}: {e}")

async def main():
    """Start the static analyzer service."""
    host = os.getenv('WEBSOCKET_HOST', 'localhost')
    port = int(os.getenv('WEBSOCKET_PORT', 2001))
    
    logger.info(f"Starting Static Analyzer service on {host}:{port}")
    
    try:
        async with serve(handle_client, host, port):
            logger.info(f"Static Analyzer listening on ws://{host}:{port}")
            logger.info("Service ready to accept connections")
            await asyncio.Future()  # Run forever
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Service crashed: {e}")
        exit(1)
