import asyncio
import websockets
import json
import uuid
from datetime import datetime

async def test_dynamic_analysis_ws():
    """Test the exact message format the analyzer manager sends"""
    
    message = {
        "type": "dynamic_analyze",
        "model_slug": "anthropic_claude-4.5-haiku-20251001",
        "app_number": 1,
        "target_urls": [
            "http://host.docker.internal:5001",
            "http://host.docker.internal:8001"
        ],
        "tools": None,
        "timestamp": datetime.now().isoformat(),
        "id": str(uuid.uuid4())
    }
    
    print(f"Connecting to ws://localhost:2002...")
    try:
        async with websockets.connect(
            'ws://localhost:2002',
            open_timeout=10,
            close_timeout=10,
            ping_interval=None,
            ping_timeout=None,
            max_size=100 * 1024 * 1024
        ) as ws:
            print("Connected! Sending message...")
            print(f"Message: {json.dumps(message, indent=2)}")
            
            await ws.send(json.dumps(message))
            print("Message sent. Waiting for responses...")
            
            frame_count = 0
            async for raw_message in ws:
                frame_count += 1
                try:
                    frame = json.loads(raw_message)
                    frame_type = frame.get('type', 'unknown')
                    status = frame.get('status', 'unknown')
                    has_analysis = 'analysis' in frame
                    
                    print(f"\nFrame #{frame_count}:")
                    print(f"  Type: {frame_type}")
                    print(f"  Status: {status}")
                    print(f"  Has 'analysis' key: {has_analysis}")
                    print(f"  Keys: {list(frame.keys())}")
                    
                    # Check if this is a terminal frame
                    if 'analysis_result' in frame_type or (frame_type.endswith('_analysis') and has_analysis):
                        print(f"\n✅ Terminal frame detected!")
                        if has_analysis:
                            print(f"Analysis summary:")
                            analysis = frame['analysis']
                            print(f"  Tools used: {analysis.get('tools_used', [])}")
                            print(f"  Results keys: {list(analysis.get('results', {}).keys())}")
                        break
                        
                except json.JSONDecodeError as e:
                    print(f"Frame #{frame_count}: Invalid JSON - {e}")
                    print(f"Raw: {raw_message[:200]}")
                    
            print(f"\n✅ Test complete - received {frame_count} frames")
            
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_dynamic_analysis_ws())
