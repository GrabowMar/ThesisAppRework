
import asyncio
import json
import websockets

async def test_gateway():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected.")
            # Send a VALID analysis request to trigger routing logs
            msg = {
                "type": "analysis_request",
                "id": "test-routing-1",
                "data": {
                    "analysis_type": "static",
                    "model_slug": "logging_test_v2",
                    "app_number": 999,
                    "options": {}
                }
            }
            print(f"Sending: {json.dumps(msg)}")
            await websocket.send(json.dumps(msg))
            
            # Wait for response
            try:
                while True:
                    response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                    print(f"Received: {response}")
                    data = json.loads(response)
                    if data.get("type") in ["analysis_result", "error"]:
                        break
            except asyncio.TimeoutError:
                print("Timeout (service might be busy, but routing should have happened)")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gateway())
