import asyncio
import websockets
import json

async def test_dynamic_ws():
    try:
        async with websockets.connect('ws://localhost:2002') as ws:
            await ws.send(json.dumps({'type': 'health_check'}))
            result = await ws.recv()
            print(f"Connection successful: {result}")
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_dynamic_ws())
