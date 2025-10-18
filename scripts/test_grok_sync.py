"""Test Grok with synchronous requests (debug timeout issue)."""
import requests
import json
import os
import sys
from pathlib import Path

# Load .env
from dotenv import load_dotenv
load_dotenv()

def test_grok_api():
    """Test direct Grok API call with requests library."""
    api_key = os.getenv('OPENROUTER_API_KEY')
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set")
        return False
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    payload = {
        "model": "x-ai/grok-4-fast",
        "messages": [
            {
                "role": "user",
                "content": "Generate a simple Flask API with one route that returns {'message': 'hello'}. Include requirements.txt. Use code blocks."
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("Testing Grok 4 Fast API - Synchronous Request")
    print("=" * 80)
    print(f"URL: {url}")
    print(f"Model: x-ai/grok-4-fast")
    print(f"Timeout: 120 seconds")
    print()
    
    try:
        print("Sending request...")
        response = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=120  # 2 minutes
        )
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            content = data['choices'][0]['message']['content']
            tokens = data.get('usage', {}).get('total_tokens', 0)
            
            print(f"✓ SUCCESS!")
            print(f"Tokens: {tokens}")
            print(f"Content length: {len(content)} chars")
            print()
            print("Content preview:")
            print("-" * 80)
            print(content[:500])
            print("-" * 80)
            return True
        else:
            print(f"✗ ERROR: {response.status_code}")
            print(response.text)
            return False
            
    except requests.Timeout:
        print("✗ TIMEOUT after 120 seconds")
        return False
    except Exception as e:
        print(f"✗ EXCEPTION: {type(e).__name__}: {e}")
        return False


if __name__ == '__main__':
    success = test_grok_api()
    sys.exit(0 if success else 1)
