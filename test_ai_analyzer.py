#!/usr/bin/env python3
"""
Simple test for ai-analyzer WebSocket service.
"""

import asyncio
import websockets
import json
import sys

async def test_ai_analyzer():
    """Test ai-analyzer with a simple message."""
    
    try:
        print("Connecting to ai-analyzer...")
        async with websockets.connect('ws://localhost:2004') as websocket:
            print("Connected successfully!")
            
            # Test health check first
            health_message = {
                "type": "health_check",
                "timestamp": "2025-09-20T00:00:00.000000"
            }
            
            print("Sending health check...")
            await websocket.send(json.dumps(health_message))
            
            response = await websocket.recv()
            health_data = json.loads(response)
            print(f"Health check response: {health_data}")
            
            # Test AI analysis message
            analysis_message = {
                "type": "ai_analyze",
                "model_slug": "nousresearch_hermes-4-405b",
                "app_number": 2,
                "tools": ["ai-code-review"],
                "id": "test-123"
            }
            
            print("Sending analysis request...")
            await websocket.send(json.dumps(analysis_message))
            
            response = await websocket.recv()
            analysis_data = json.loads(response)
            print(f"Analysis response: {analysis_data}")
            
    except Exception as e:
        print(f"Test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test_ai_analyzer())
    sys.exit(0 if success else 1)