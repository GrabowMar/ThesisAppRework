import asyncio
import json
import websockets

async def check_health():
    async with websockets.connect('ws://localhost:2001') as ws:
        await ws.send(json.dumps({'type': 'health_check'}))
        response = await ws.recv()
        data = json.loads(response)
        print("Health Response:")
        print(f"  Status: {data['status']}")
        print(f"  Service: {data['service']}")
        print(f"  Available Tools: {data['available_tools']}")
        return data

if __name__ == '__main__':
    result = asyncio.run(check_health())
