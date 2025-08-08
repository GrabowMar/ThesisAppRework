"""Health check for static analyzer service."""
import sys
import asyncio
import websockets
import json
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from shared.protocol import WebSocketMessage, MessageType

async def health_check():
    """Perform health check on the service."""
    try:
        uri = "ws://localhost:8001"
        async with websockets.connect(uri) as websocket:
            # Send heartbeat
            message = WebSocketMessage(
                type=MessageType.HEARTBEAT,
                data={'check': 'health'}
            )
            
            await websocket.send(message.to_json())
            
            # Wait for response
            response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            response_data = json.loads(response)
            
            if response_data.get('type') == MessageType.HEARTBEAT.value:
                print("Health check passed")
                return True
            else:
                print("Health check failed - unexpected response")
                return False
                
    except Exception as e:
        print(f"Health check failed: {str(e)}")
        return False

if __name__ == "__main__":
    result = asyncio.run(health_check())
    sys.exit(0 if result else 1)
