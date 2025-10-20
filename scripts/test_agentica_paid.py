"""Test if paid agentica model works (should work if billing is set up)"""
import asyncio
import sys
import os
from pathlib import Path

# Load .env before importing services
project_root = Path(__file__).parent.parent
env_file = project_root / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key] = value

sys.path.insert(0, str(project_root / 'src'))

from app.services.openrouter_chat_service import OpenRouterChatService

async def test():
    service = OpenRouterChatService()
    
    # Test with exact model ID from OpenRouter
    model_id = "agentica-org/deepcoder-14b-preview"
    
    print(f"Testing model: {model_id}")
    print("=" * 60)
    
    try:
        success, response, status = await service.generate_chat_completion(
            model=model_id,
            messages=[{"role": "user", "content": "Hello, world!"}],
            max_tokens=50
        )
        if success:
            print(f"SUCCESS: Status {status}")
            print(f"Response: {response.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')}")
        else:
            print(f"FAILED: Status {status}, Error: {response}")
    except Exception as e:
        print(f"FAILED: {e}")
    
    # Now test free version
    model_id_free = "agentica-org/deepcoder-14b-preview:free"
    print(f"\nTesting model: {model_id_free}")
    print("=" * 60)
    
    try:
        success, response, status = await service.generate_chat_completion(
            model=model_id_free,
            messages=[{"role": "user", "content": "Hello, world!"}],
            max_tokens=50
        )
        if success:
            print(f"SUCCESS: Status {status}")
            print(f"Response: {response.get('choices', [{}])[0].get('message', {}).get('content', 'N/A')}")
        else:
            print(f"FAILED: Status {status}, Error: {response}")
    except Exception as e:
        print(f"FAILED: {e}")

asyncio.run(test())
