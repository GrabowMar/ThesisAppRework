#!/usr/bin/env python3
"""
Health check for AI Analyzer service.
"""

import asyncio
import websockets
import json
import sys
import os
from datetime import datetime
from typing import Dict, Any

async def check_health() -> Dict[str, Any]:
    """Check if the AI analyzer service is healthy."""
    
    try:
        # Use the correct port from environment or default
        port = int(os.getenv('WEBSOCKET_PORT', 2004))
        uri = f"ws://localhost:{port}"
        
        # Use simple connect without deprecated timeout parameter
        websocket = await websockets.connect(uri)
        
        try:
            # Send simple health check message - use health_check as expected by BaseWSService
            message = {
                "type": "health_check",
                "timestamp": datetime.now().isoformat(),
                "id": "health_check_001"
            }
            
            await websocket.send(json.dumps(message))
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('type') == 'health_check_response' or response_data.get('status') == 'healthy':
                return {
                    "status": "healthy",
                    "service": "ai-analyzer",
                    "details": response_data
                }
            else:
                return {
                    "status": "unhealthy",
                    "service": "ai-analyzer",
                    "error": f"Invalid response: {response_data}"
                }
        finally:
            await websocket.close()
                
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
