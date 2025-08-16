import asyncio
import json
import sys
import websockets

URI = sys.argv[1] if len(sys.argv) > 1 else 'ws://localhost:8765'

async def main():
    print(f"Connecting to {URI} for event subscription...")
    async with websockets.connect(URI) as ws:
        # Subscribe to events and request a short replay of recent ones
        await ws.send(json.dumps({
            'type':'status_request',
            'id':'sub_cli',
            'timestamp':'2025-01-01T00:00:00',
            'data': {'subscribe': 'events', 'replay': True}
        }))
        i = 0
        while True:
            msg = await ws.recv()
            i += 1
            print(f"[{i}] {msg}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
