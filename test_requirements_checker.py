"""Quick test of requirements-checker tool directly via WebSocket"""
import asyncio
import websockets
import json

async def test_requirements_checker():
    uri = "ws://localhost:2004"
    
    message = {
        "action": "analyze",
        "model_slug": "openai_codex-mini",
        "app_number": 1,
        "analysis_id": "test-123",
        "config": {
            "tools": ["requirements-checker"],
            "gemini_model": "openai/gpt-4o-mini"
        }
    }
    
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Sending analysis request...")
        await websocket.send(json.dumps(message))
        
        print("\nWaiting for responses...\n")
        async for response in websocket:
            data = json.loads(response)
            
            if data.get('type') == 'progress':
                print(f"[PROGRESS] {data.get('stage')}: {data.get('message')}")
            
            elif data.get('type') == 'result':
                print(f"\n{'='*60}")
                print(f"[RESULT] Analysis complete!")
                print(f"{'='*60}\n")
                
                result = data.get('result', {})
                
                # Print metadata
                if 'metadata' in result:
                    print("METADATA:")
                    print(json.dumps(result['metadata'], indent=2))
                    print()
                
                # Print summary
                if 'results' in result and 'summary' in result['results']:
                    print("SUMMARY:")
                    print(json.dumps(result['results']['summary'], indent=2))
                    print()
                
                # Print functional requirements (first 2)
                if 'results' in result and 'functional_requirements' in result['results']:
                    reqs = result['results']['functional_requirements']
                    print(f"FUNCTIONAL REQUIREMENTS ({len(reqs)} total):")
                    for i, req in enumerate(reqs[:2], 1):
                        print(f"\n  {i}. {req.get('requirement', '')[:80]}...")
                        print(f"     Met: {req.get('met')}, Confidence: {req.get('confidence')}")
                        print(f"     Explanation: {req.get('explanation', '')[:100]}...")
                    if len(reqs) > 2:
                        print(f"\n  ... and {len(reqs)-2} more")
                    print()
                
                # Print endpoint tests
                if 'results' in result and 'control_endpoint_tests' in result['results']:
                    endpoints = result['results']['control_endpoint_tests']
                    print(f"CONTROL ENDPOINT TESTS ({len(endpoints)} total):")
                    for ep in endpoints:
                        status = "✅ PASS" if ep.get('passed') else "❌ FAIL"
                        print(f"  {status} {ep.get('method')} {ep.get('endpoint')} - {ep.get('actual_status')}")
                    print()
                
                break
            
            elif data.get('type') == 'error':
                print(f"\n[ERROR] {data.get('message')}")
                break

if __name__ == "__main__":
    asyncio.run(test_requirements_checker())
