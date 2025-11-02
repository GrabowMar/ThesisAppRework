import pytest

pytestmark = [pytest.mark.integration, pytest.mark.websocket]

import asyncio
import websockets
import json

async def test_static_analyzer():
    uri = "ws://localhost:2001"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri, open_timeout=10) as websocket:
            print("Connected!")
            
            message = {
                "type": "static_analyze",
                "model_slug": "openai_gpt-4.1-2025-04-14",
                "app_number": 3,
                "source_path": "/app/sources/openai_gpt-4.1-2025-04-14/app3",
                "tools": ["bandit", "semgrep"],
                "timestamp": "2025-10-31T18:00:00",
                "id": "test123"
            }
            
            print(f"Sending message: {message}")
            await websocket.send(json.dumps(message))
            print("Message sent, waiting for response...")
            
            response = await asyncio.wait_for(websocket.recv(), timeout=60)
            print(f"Received response ({len(response)} bytes)")
            print(f"Response type: {json.loads(response).get('type')}")
            print(f"Response status: {json.loads(response).get('status')}")
            
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_static_analyzer())
