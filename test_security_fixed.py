#!/usr/bin/env python3
"""Test script to verify security analyzer functionality with correct message types."""

import asyncio
import websockets
import json

async def test_security_analyzer():
    """Test the security analyzer service."""
    uri = "ws://localhost:2005/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to security analyzer")
            
            # Test health check
            health_request = {
                "type": "health_check"
            }
            await websocket.send(json.dumps(health_request))
            response = await websocket.recv()
            health_response = json.loads(response)
            print(f"Health check response: {health_response}")
            
            if health_response.get("status") == "healthy":
                print("✅ Security analyzer is healthy")
                print(f"Available tools: {health_response.get('available_tools')}")
            else:
                print("❌ Security analyzer is not healthy")
                return
            
            # Test security analysis with correct message type
            analysis_request = {
                "type": "security_analyze",  # Fixed: was "security_analysis"
                "model_slug": "anthropic_claude-3.7-sonnet",
                "app_number": 1
            }
            
            print(f"\nSending analysis request: {analysis_request}")
            await websocket.send(json.dumps(analysis_request))
            
            # Wait for response
            response = await websocket.recv()
            analysis_response = json.loads(response)
            print(f"\nAnalysis response: {json.dumps(analysis_response, indent=2)}")
            
            if analysis_response.get("status") == "success":
                print("✅ Security analysis completed successfully")
                analysis_results = analysis_response.get("analysis", {})
                if analysis_results:
                    print(f"Found {len(analysis_results)} analysis results")
                    for tool, results in analysis_results.items():
                        if results:
                            print(f"  {tool}: {len(results)} findings")
            else:
                print("❌ Security analysis failed")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_security_analyzer())
