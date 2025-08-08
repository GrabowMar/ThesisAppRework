#!/usr/bin/env python3
"""
Health check for Security Analyzer service
"""

import asyncio
import json
import sys
import websockets

async def health_check():
    """Check if the security analyzer service is healthy."""
    try:
        uri = "ws://localhost:2005"
        
        async with websockets.connect(uri, open_timeout=5) as websocket:
            # Send health check message
            health_msg = {
                "type": "health_check",
                "timestamp": "2025-01-08T12:00:00"
            }
            
            await websocket.send(json.dumps(health_msg))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            
            if data.get("type") == "health_response" and data.get("status") == "healthy":
                print("Service is healthy")
                return True
            else:
                print(f"Service unhealthy: {data}")
                return False
                
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    is_healthy = asyncio.run(health_check())
    sys.exit(0 if is_healthy else 1)
