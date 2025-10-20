"""Test generation API call"""
import sys
import asyncio
sys.path.insert(0, 'src')

from app import create_app
from app.models import ModelCapability
from app.services.openrouter_chat_service import get_openrouter_chat_service

async def test_generation():
    app = create_app()
    with app.app_context():
        # Get the model
        model = ModelCapability.query.filter_by(canonical_slug='x-ai_grok-code-fast-1').first()
        
        if not model:
            print("ERROR: Model not found in database!")
            return
        
        print("\n=== Model Info ===")
        print(f"Canonical Slug: {model.canonical_slug}")
        print(f"Model ID: {model.model_id}")
        print(f"Model Name: {model.model_name}")
        
        # Test API call
        chat_service = get_openrouter_chat_service()
        
        print(f"\n=== Testing API Call ===")
        print(f"Using model ID: {model.model_id}")
        
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": "Write a simple hello world function in Python."}
        ]
        
        success, response_data, status_code = await chat_service.generate_chat_completion(
            model=model.model_id,
            messages=messages,
            temperature=0.3,
            max_tokens=1000
        )
        
        print(f"\n=== Result ===")
        print(f"Success: {success}")
        print(f"Status Code: {status_code}")
        
        if success:
            content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f"Content (first 200 chars): {content[:200]}")
        else:
            error_msg = response_data.get("error", {}).get("message", "Unknown error")
            print(f"Error: {error_msg}")
            print(f"Full response: {response_data}")

if __name__ == '__main__':
    asyncio.run(test_generation())
