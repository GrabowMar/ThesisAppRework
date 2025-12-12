"""Simple WebSocket test to verify graceful close"""
import asyncio
import json
import websockets

async def test_static_analyzer():
    """Test static analyzer WebSocket connection and graceful close"""
    uri = "ws://localhost:2001/ws"
    
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(
            uri,
            max_size=100*1024*1024,  # 100MB
            ping_interval=None,  # Disable ping
            close_timeout=10
        ) as ws:
            # Send a minimal analysis request
            request = {
                "type": "static_analyze",  # Correct type for static analyzer
                "model_slug": "anthropic_claude-3-5-haiku",
                "app_number": 2,
                "tools": ["bandit"]  # Just run bandit for speed
            }
            
            print(f"Sending request: {json.dumps(request, indent=2)}")
            await ws.send(json.dumps(request))
            
            # Collect all frames
            frames = []
            print("\nReceiving frames...")
            
            async for msg in ws:
                data = json.loads(msg)
                frame_type = data.get('type', 'unknown')
                print(f"  Received: {frame_type}")
                frames.append(data)
                
                # Show errors
                if frame_type == 'error':
                    print(f"    Error: {data.get('message', data)}")
                
                # Check for terminal frame
                if frame_type.endswith('_analysis_result'):
                    print(f"\nTerminal frame received!")
                    status = data.get('status', 'unknown')
                    print(f"  Status: {status}")
                    break
            
            print(f"\nTotal frames received: {len(frames)}")
            print("Connection closed gracefully!")
            
    except websockets.exceptions.ConnectionClosed as e:
        print(f"\nConnection closed: code={e.code}, reason={e.reason}")
        if e.code == 1000:
            print("✓ Normal closure (expected)")
        elif e.code == 1006:
            print("✗ Abnormal closure (the bug we're fixing!)")
        else:
            print(f"? Unexpected close code: {e.code}")
    except Exception as e:
        print(f"\nError: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_static_analyzer())
