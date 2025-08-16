import asyncio
import json
import sys
import uuid

import websockets


URI = sys.argv[1] if len(sys.argv) > 1 else 'ws://localhost:8765'
CORR = sys.argv[2] if len(sys.argv) > 2 else str(uuid.uuid4())


async def main():
    async with websockets.connect(URI) as ws:
        # Compose a minimal protocol-compliant progress_update message
        payload = {
            'type': 'progress_update',
            'id': str(uuid.uuid4()),
            'timestamp': '2025-01-01T00:00:00',
            'correlation_id': CORR,
            'data': {
                'analysis_id': CORR,
                'stage': 'manual_test',
                'progress': 0.1,
                'message': 'Synthetic test progress from publisher',
                'files_processed': 1,
                'total_files': 10
            }
        }
        await ws.send(json.dumps(payload))
        # receive ack/status
        try:
            ack = await asyncio.wait_for(ws.recv(), timeout=3)
            print(ack)
        except Exception:
            pass


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
