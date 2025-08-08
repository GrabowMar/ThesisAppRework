#!/usr/bin/env python3
"""
Health check for AI Analyzer service.
"""

import asyncio
import websockets
import json
import sys
from typing import Dict, Any

async def check_health() -> Dict[str, Any]:
    """Check if the AI analyzer service is healthy."""
    
    try:
        # Connect to the service
        uri = "ws://localhost:8004"
        
        async with websockets.connect(uri, timeout=5) as websocket:
            # Send heartbeat message
            heartbeat_msg = {
                "type": "heartbeat",
                "data": {"check": "health"},
                "id": "health_check_001",
                "timestamp": "2025-01-27T10:00:00Z"
            }
            
            await websocket.send(json.dumps(heartbeat_msg))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            response_data = json.loads(response)
            
            if response_data.get("type") == "heartbeat":
                return {
                    "status": "healthy",
                    "service": "ai-analyzer",
                    "details": response_data.get("data", {})
                }
            else:
                return {
                    "status": "unhealthy",
                    "service": "ai-analyzer",
                    "error": "Invalid response format"
                }
                
    except asyncio.TimeoutError:
        return {
            "status": "unhealthy",
            "service": "ai-analyzer",
            "error": "Connection timeout"
        }
    except ConnectionRefusedError:
        return {
            "status": "unhealthy",
            "service": "ai-analyzer", 
            "error": "Connection refused - service may not be running"
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "service": "ai-analyzer",
            "error": f"Unexpected error: {str(e)}"
        }

def main():
    """Run health check and exit with appropriate code."""
    
    result = asyncio.run(check_health())
    
    if result["status"] == "healthy":
        print("AI Analyzer service is healthy")
        print(f"Details: {result.get('details', {})}")
        sys.exit(0)
    else:
        print(f"AI Analyzer service is unhealthy: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
