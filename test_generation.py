"""Test generation with cheap models to validate improvements"""
import asyncio
import sys
import os
import logging

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

logging.basicConfig(level=logging.INFO)

async def test_generation():
    """Test generation without full app initialization"""
    from app.factory import create_app
    from app.services.generation import CodeGenerator, GenerationConfig
    
    # Create minimal app context
    app = create_app()
    
    with app.app_context():
        # Test models (cheap but capable)
        test_models = [
            'anthropic_claude-4.5-haiku-20251001',
            'openai_gpt-4o-mini',
        ]
        
        template = 'crud_todo_list'
        
        for model_slug in test_models:
            print(f"\n{'='*80}")
            print(f"Testing generation with: {model_slug}")
            print(f"Template: {template}")
            print(f"{'='*80}\n")
            
            generator = CodeGenerator()
            
            # Test backend generation
            print("\n--- Backend Generation ---")
            config = GenerationConfig(
                model_slug=model_slug,
                app_num=999,  # Test app number
                template_slug=template,
                component='backend',
                temperature=0.3,
                max_tokens=32000  # Using new default
            )
            
            try:
                success, content, error = await generator.generate(config)
                
                if success:
                    print(f"✓ Backend generation successful!")
                    print(f"  Generated code length: {len(content)} characters")
                    print(f"  Contains 'db = SQLAlchemy()': {'db = SQLAlchemy()' in content}")
                    print(f"  Contains 'def setup_app': {'def setup_app' in content}")
                    print(f"  Contains route decorators: {content.count('@app.route')}")
                    print(f"  First 300 chars:\n{content[:300]}...")
                else:
                    print(f"✗ Backend generation failed: {error}")
                    
            except Exception as e:
                print(f"✗ Exception during backend generation: {e}")
                import traceback
                traceback.print_exc()
            
            # Test frontend generation
            print("\n--- Frontend Generation ---")
            config.component = 'frontend'
            
            try:
                success, content, error = await generator.generate(config)
                
                if success:
                    print(f"✓ Frontend generation successful!")
                    print(f"  Generated code length: {len(content)} characters")
                    print(f"  Contains 'import React': {'import React' in content}")
                    print(f"  Contains 'axios': {'axios' in content}")
                    print(f"  Contains 'API_URL': {'API_URL' in content}")
                    print(f"  Contains 'export default': {'export default' in content}")
                    print(f"  First 300 chars:\n{content[:300]}...")
                else:
                    print(f"✗ Frontend generation failed: {error}")
                    
            except Exception as e:
                print(f"✗ Exception during frontend generation: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\n{'='*80}\n")

if __name__ == '__main__':
    asyncio.run(test_generation())
