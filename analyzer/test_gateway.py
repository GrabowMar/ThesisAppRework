import asyncio
import json
import sys

import websockets

# Use the shared protocol if available
from shared.protocol import (
    AnalysisRequest,
    AnalysisType,
    ServiceType,
    create_analysis_request_message,
)


async def main():
    model = sys.argv[1] if len(sys.argv) > 1 else 'anthropic_claude-3.7-sonnet'
    app_number = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    uri = sys.argv[3] if len(sys.argv) > 3 else 'ws://localhost:8765'

    req = AnalysisRequest(
        model=model,
        app_number=app_number,
        analysis_type=AnalysisType.CODE_QUALITY_PYTHON,
        source_path=''
    )
    msg = create_analysis_request_message(req, client_id='cli-test', service=ServiceType.CODE_QUALITY)

    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as ws:
        await ws.send(msg.to_json())
        print("Request sent, awaiting response...")
        resp = await ws.recv()
        try:
            data = json.loads(resp)
        except json.JSONDecodeError:
            print("Non-JSON response:", resp)
            return
        print("Received:")
        # Print a concise summary
        print(json.dumps(
            {
                'type': data.get('type'),
                'correlation_id': data.get('correlation_id'),
                'service_status': data.get('data', {}).get('status'),
                'inner_type': data.get('data', {}).get('type'),
            },
            indent=2
        ))


if __name__ == '__main__':
    asyncio.run(main())
