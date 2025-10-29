import asyncio
import json
import websockets

async def test_analysis():
    message = {
        'type': 'static_analyze',
        'model_slug': 'openai_gpt-4.1-2025-04-14',
        'app_number': 1,
        'id': 'test-debug',
        'tools': ['bandit', 'safety', 'pylint']
    }
    
    print(f"Sending message: {json.dumps(message, indent=2)}")
    
    async with websockets.connect('ws://localhost:2001', ping_interval=None) as ws:
        await ws.send(json.dumps(message))
        response = await ws.recv()
        data = json.loads(response)
        
        print(f"\nReceived response type: {data['type']}")
        print(f"Status: {data.get('status', 'N/A')}")
        
        if 'analysis' in data:
            analysis = data['analysis']
            print(f"\nTools used: {analysis.get('tools_used', [])}")
            print(f"Total issues: {analysis.get('summary', {}).get('total_issues_found', 0)}")
            
            if 'results' in analysis and 'python' in analysis['results']:
                py_results = analysis['results']['python']
                print(f"\nPython results keys: {list(py_results.keys())}")
                
                if 'bandit' in py_results:
                    print(f"Bandit executed: {py_results['bandit'].get('executed', False)}")
                    print(f"Bandit status: {py_results['bandit'].get('status', 'N/A')}")
                    print(f"Bandit issues: {py_results['bandit'].get('total_issues', 0)}")
        
        return data

if __name__ == '__main__':
    result = asyncio.run(test_analysis())
