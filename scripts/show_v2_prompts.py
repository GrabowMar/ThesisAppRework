"""Show what prompts are being sent to the model in V2 generation."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.generation_v2 import GenerationConfig, CodeGenerator

def show_prompts():
    """Display the prompts that would be sent to the model."""
    generator = CodeGenerator()
    
    # Test configurations
    configs = [
        GenerationConfig(
            model_slug="anthropic/claude-3.5-sonnet",
            app_num=1,
            template_id=1,
            component="backend"
        ),
        GenerationConfig(
            model_slug="anthropic/claude-3.5-sonnet",
            app_num=1,
            template_id=1,
            component="frontend"
        )
    ]
    
    for config in configs:
        print("=" * 80)
        print(f"COMPONENT: {config.component.upper()}")
        print("=" * 80)
        
        print("\n" + "-" * 80)
        print("SYSTEM PROMPT:")
        print("-" * 80)
        print(generator._get_system_prompt(config.component))
        
        print("\n" + "-" * 80)
        print("USER PROMPT:")
        print("-" * 80)
        print(generator._build_prompt(config))
        
        print("\n")

if __name__ == '__main__':
    show_prompts()
