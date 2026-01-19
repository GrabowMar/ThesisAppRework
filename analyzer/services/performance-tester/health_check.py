#!/usr/bin/env python3
"""
Health Check for Performance Tester Service
==========================================

This script performs a health check on the Performance Tester WebSocket service.

The health check:
- Connects to the Performance Tester service on the configured WebSocket port (default: 2003)
- Sends a health_check message
- Validates the response indicates service health
- Returns appropriate exit codes for monitoring systems

Usage:
    python health_check.py

Exit Codes:
    0: Service is healthy
    1: Service is unhealthy or unreachable

This script is used by Docker health checks, monitoring systems, and deployment
scripts to verify the Performance Tester service is running correctly.
"""

import asyncio
import websockets
import json
import sys
import os
from datetime import datetime

async def health_check():
    """Perform health check on the service."""
    try:
        # Use the correct port from environment or default
        port = int(os.getenv('WEBSOCKET_PORT', 2003))
        uri = f"ws://localhost:{port}"
        
        # Use simple connect without deprecated timeout parameter
        websocket = await websockets.connect(uri)
        
        try:
            # Send simple health check message
            message = {
                "type": "health_check",
                "timestamp": datetime.now().isoformat(),
                "id": "health_check_001"
            }
            
            await websocket.send(json.dumps(message))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('status') == 'healthy':
                print("Health check passed")
                return True
            else:
                print(f"Health check failed - unexpected response: {response_data}")
                return False
        finally:
            await websocket.close()
                
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return False

if __name__ == "__main__":
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
