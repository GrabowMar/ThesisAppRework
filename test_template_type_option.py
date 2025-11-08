"""Test template type selection option."""
import sys
sys.path.insert(0, 'src')

from app.services.generation import GenerationConfig, CodeGenerator

def test_template_selection():
    """Test that template_type parameter controls template selection."""
    
    generator = CodeGenerator()
    
    # Test case 1: auto (should use compact for GPT-3.5)
    config_auto = GenerationConfig(
        model_slug='openai_gpt-3.5-turbo',
        app_num=1,
        template_slug='crud_todo_list',
        component='frontend',
        template_type='auto'
    )
    
    # Test case 2: force full (even for GPT-3.5 which normally uses compact)
    config_full = GenerationConfig(
        model_slug='openai_gpt-3.5-turbo',
        app_num=1,
        template_slug='crud_todo_list',
        component='frontend',
        template_type='full'
    )
    
    # Test case 3: force compact (even for GPT-4o which normally uses full)
    config_compact = GenerationConfig(
        model_slug='openai_gpt-4o',
        app_num=1,
        template_slug='crud_todo_list',
        component='frontend',
        template_type='compact'
    )
    
    print("Testing template selection logic...\n")
    
    # Build prompts and check which templates were used
    for config, expected in [
        (config_auto, 'compact'),
        (config_full, 'full'),
        (config_compact, 'compact')
    ]:
        print(f"Building prompt for {config.model_slug} with template_type='{config.template_type}'...")
        prompt = generator._build_prompt(config)
        
        # Check if compact or full template based on content
        # Compact templates have "Rules:" section, full templates have "## Requirements"
        is_compact = 'Rules:' in prompt and 'Example skeleton:' in prompt
        actual = 'compact' if is_compact else 'full'
        
        status = '[OK]' if actual == expected else '[FAIL]'
        print(f"{status} Expected: {expected}, Got: {actual}")
        print(f"   Prompt length: {len(prompt)} chars")
        
        # Show first 200 chars for debugging
        print(f"   Preview: {prompt[:200]}...")
        print()
    
    print("Test complete!")

if __name__ == '__main__':
    test_template_selection()
