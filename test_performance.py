#!/usr/bin/env python3
"""
Test script to verify the new performance tester works end-to-end.
"""
import asyncio
import json
import websockets
from datetime import datetime

async def test_performance_analysis():
    """Test the performance analysis via WebSocket."""
    try:
        # Connect to performance tester
        uri = "ws://localhost:2003"
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to performance tester")
            
            # Send performance analysis request
            request = {
                "type": "performance_analysis",
                "id": "test_001",
                "model_slug": "test_model",
                "app_number": 1,
                "target_urls": ["http://host.docker.internal:5141"],
                "selected_tools": ["locust-performance", "ab-load-test", "aiohttp-load"],
                "config": {
                    "locust": {"users": 10, "spawn_rate": 2, "run_time": "15s"},
                    "apache_bench": {"requests": 50, "concurrency": 5},
                    "aiohttp": {"requests": 20, "concurrency": 3}
                }
            }
            
            print("📤 Sending performance analysis request...")
            await websocket.send(json.dumps(request))
            
            # Listen for responses
            start_time = datetime.now()
            timeout_seconds = 120  # 2 minutes timeout
            
            while True:
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=10)
                    data = json.loads(response)
                    
                    print(f"📨 Received: {data.get('type', 'unknown')}")
                    
                    if data.get('type') == 'analysis_result':
                        result = data.get('result', {})
                        tools_used = result.get('tools_used', [])
                        print(f"🎉 Analysis complete! Tools used: {tools_used}")
                        
                        # Print summary of results
                        results = result.get('results', {})
                        for url, url_results in results.items():
                            print(f"\n📊 Results for {url}:")
                            for tool, tool_result in url_results.items():
                                if isinstance(tool_result, dict):
                                    status = tool_result.get('status', 'unknown')
                                    print(f"  {tool}: {status}")
                                    if status == 'success':
                                        if 'requests_per_second' in tool_result:
                                            print(f"    RPS: {tool_result['requests_per_second']:.2f}")
                                        if 'avg_response_time' in tool_result:
                                            print(f"    Avg Response Time: {tool_result['avg_response_time']:.2f}ms")
                        
                        return True
                    
                    elif data.get('type') == 'progress':
                        stage = data.get('stage', 'unknown')
                        message = data.get('message', '')
                        print(f"⏳ Progress: {stage} - {message}")
                    
                    elif data.get('type') == 'error':
                        error = data.get('error', 'Unknown error')
                        print(f"❌ Error: {error}")
                        return False
                    
                    # Check timeout
                    if (datetime.now() - start_time).total_seconds() > timeout_seconds:
                        print(f"⏰ Test timed out after {timeout_seconds} seconds")
                        return False
                        
                except asyncio.TimeoutError:
                    print("⏳ Waiting for response...")
                    if (datetime.now() - start_time).total_seconds() > timeout_seconds:
                        print(f"⏰ Test timed out after {timeout_seconds} seconds")
                        return False
                    continue
                except Exception as e:
                    print(f"❌ Error receiving response: {e}")
                    return False
    
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Starting performance analysis test...")
    success = asyncio.run(test_performance_analysis())
    if success:
        print("✅ Performance analysis test completed successfully!")
    else:
        print("❌ Performance analysis test failed!")
    print("🏁 Test finished.")