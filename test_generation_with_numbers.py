"""Test that generation works with numbered requirements."""
import sys
import asyncio
sys.path.insert(0, 'src')

from app.factory import create_app
from app.services.generation import get_generation_service

async def test_generation():
    app = create_app()
    
    with app.app_context():
        service = get_generation_service()
        
        # Just test loading requirements - don't actually generate
        generator = service.generator
        
        # Load a template's requirements
        reqs = generator._load_requirements('crud_todo_list')
        
        if reqs:
            print("OK Successfully loaded crud_todo_list requirements")
            print(f"\nBackend requirements ({len(reqs.get('backend_requirements', []))}):")
            for req in reqs.get('backend_requirements', []):
                print(f"  {req}")
            
            print(f"\nFrontend requirements ({len(reqs.get('frontend_requirements', []))}):")
            for req in reqs.get('frontend_requirements', []):
                print(f"  {req}")
            
            # Test prompt building
            from app.services.generation import GenerationConfig
            config = GenerationConfig(
                model_slug='openai_gpt-4o-mini',
                app_num=999,
                template_slug='crud_todo_list',
                component='backend'
            )
            config.requirements = reqs
            
            prompt = generator._build_prompt(config)
            
            # Check if numbered requirements appear in prompt
            has_numbered = '1. Todo model' in prompt or '2. REST API' in prompt
            
            print(f"\n>>> Prompt generated ({len(prompt)} chars)")
            print(f">>> Contains numbered requirements: {has_numbered}")
            
            if has_numbered:
                print("\nSample from prompt:")
                lines = prompt.split('\n')
                in_req_section = False
                count = 0
                for line in lines:
                    if 'Requirements' in line or '## Requirements' in line:
                        in_req_section = True
                    if in_req_section and ('1. ' in line or '2. ' in line or '3. ' in line):
                        print(f"  {line.strip()}")
                        count += 1
                        if count >= 3:
                            break
        else:
            print("ERROR Failed to load requirements")

if __name__ == '__main__':
    asyncio.run(test_generation())
