#!/usr/bin/env python3
"""Test AI Analyzer API connectivity and response parsing"""
import asyncio
import os
import aiohttp
import json


async def test_openrouter_api():
    """Test OpenRouter API with the configured key."""
    api_key = os.getenv('OPENROUTER_API_KEY', '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')
    model = 'anthropic/claude-3.5-haiku'
    
    print(f"Testing OpenRouter API...")
    print(f"API Key: {api_key[:15]}...{api_key[-10:]}")
    print(f"Model: {model}")
    
    test_prompt = """Analyze this simple Python code:
```python
def hello():
    print("Hello world")
```

Does this code implement a greeting function?

Respond in this format:
MET: YES
CONFIDENCE: HIGH
EXPLANATION: The code defines a hello() function that prints a greeting message."""

    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:5000",  # Optional
            "X-Title": "AI Analyzer Test"  # Optional
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": test_prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.1
        }
        
        print("\n--- REQUEST ---")
        print(f"URL: https://openrouter.ai/api/v1/chat/completions")
        print(f"Headers: {json.dumps({k: v for k, v in headers.items() if k != 'Authorization'}, indent=2)}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                print(f"\n--- RESPONSE ---")
                print(f"Status: {response.status}")
                print(f"Headers: {dict(response.headers)}")
                
                response_text = await response.text()
                print(f"Body: {response_text}")
                
                if response.status == 200:
                    data = json.loads(response_text)
                    ai_response = data['choices'][0]['message']['content']
                    print(f"\n--- AI RESPONSE ---")
                    print(ai_response)
                    print("\n✅ SUCCESS - API call worked!")
                else:
                    print(f"\n❌ FAILED - API returned error status {response.status}")
                    
        except Exception as e:
            print(f"\n❌ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_openrouter_api())
