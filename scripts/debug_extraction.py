"""Debug code extraction"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from dotenv import load_dotenv
load_dotenv()

from app.services.multi_step_generation_service import (
    get_multi_step_service,
    MultiStepRequest
)


async def debug_extraction():
    service = get_multi_step_service()
    
    request = MultiStepRequest(
        requirement_id="todo_api",
        model_slug="openai/gpt-4o-mini",
        app_num=999,  # Use a test app number
        component="backend",
        temperature=0.3,
        max_tokens=16000
    )
    
    # Load requirement
    requirement = service.load_requirement(request.requirement_id)
    
    # Render first prompt
    template_name = "backend_step3_polish.md.jinja2"  # Test the final polish step
    prompt = service.render_prompt(template_name, requirement)
    
    print("=" * 60)
    print("PROMPT:")
    print("=" * 60)
    print(prompt[:1000])  # First 1000 chars
    print("\n...")
    
    # Call API
    success, content, tokens, error = await service.call_api(
        prompt,
        request.model_slug,
        request.temperature,
        request.max_tokens
    )
    
    if not success:
        print(f"\nAPI Error: {error}")
        return
    
    print("\n" + "=" * 60)
    print(f"RESPONSE: {len(content)} chars, {tokens} tokens")
    print("=" * 60)
    
    # Show first part of response
    print(content[:2000])
    print("\n...\n")
    
    # Extract code
    files = service.extract_code_blocks(content)
    
    print("=" * 60)
    print("EXTRACTED FILES:")
    print("=" * 60)
    for filename, code in files.items():
        lines = len(code.split('\n'))
        chars = len(code)
        print(f"\n{filename}: {lines} lines, {chars} chars")
        print(f"First 200 chars: {code[:200]}")


if __name__ == "__main__":
    asyncio.run(debug_extraction())
