#!/usr/bin/env python3
"""Test live generation with Claude Haiku 4.5."""

import sys
import asyncio
sys.path.insert(0, 'src')

from dotenv import load_dotenv
load_dotenv(override=True)

from app import create_app
from app.services.generation import CodeGenerator, GenerationConfig

async def test_generation():
    """Test a minimal generation."""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("Testing Live Generation: anthropic_claude-4.5-haiku-20251001")
        print("=" * 80)
        
        config = GenerationConfig(
            model_slug='anthropic_claude-4.5-haiku-20251001',
            app_num=999,
            template_slug='api_url_shortener',  # Just use any template
            component='backend',
            max_tokens=500,
            temperature=0.7
        )
        
        prompt = 'Create a minimal Flask API with one GET endpoint /health that returns JSON {"status": "ok", "message": "API is running"}'
        
        generator = CodeGenerator()
        
        print(f"\n>> Calling OpenRouter API...")
        print(f"   Model: anthropic_claude-4.5-haiku-20251001")
        print(f"   Prompt: {prompt[:80]}...")
        
        # Access the chat service directly
        from app.models import ModelCapability
        model = ModelCapability.query.filter_by(canonical_slug='anthropic_claude-4.5-haiku-20251001').first()
        
        if not model:
            print("[X] Model not found in database")
            return False
        
        openrouter_model = model.hugging_face_id or model.base_model_id or model.model_id
        print(f"   OpenRouter ID: {openrouter_model}")
        
        messages = [
            {"role": "system", "content": "You are a code generator. Generate only code, no explanations."},
            {"role": "user", "content": prompt}
        ]
        
        # Use the code generator's chat_service
        chat_service = generator.chat_service
        
        success, response_data, status_code = await chat_service.generate_chat_completion(
            model=openrouter_model,
            messages=messages,
            temperature=config.temperature,
            max_tokens=config.max_tokens
        )
        
        print(f"\n{'='*80}")
        print("Result")
        print(f"{'='*80}")
        
        if success:
            print(f"[OK] SUCCESS")
            print(f"Status Code: {status_code}")
            
            # Extract generated code from response
            if isinstance(response_data, dict) and 'choices' in response_data:
                code = response_data['choices'][0]['message']['content']
                print(f"\nGenerated Code ({len(code)} chars):")
                print("-" * 80)
                print(code[:500])
                if len(code) > 500:
                    print(f"\n... (truncated, total {len(code)} chars)")
                print("-" * 80)
            else:
                print(f"Response: {response_data}")
        else:
            print(f"[X] FAILED")
            print(f"Status Code: {status_code}")
            print(f"Response: {response_data}")
        
        return success

if __name__ == '__main__':
    result = asyncio.run(test_generation())
    sys.exit(0 if result else 1)
