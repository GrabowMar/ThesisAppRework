"""Test generation with GPT-4o-mini (higher token limit)"""
import os
os.environ['FLASK_SKIP_SERVER'] = '1'

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app.factory import create_app
from app.services.generation import GenerationService

async def main():
    app = create_app()
    
    with app.app_context():
        service = GenerationService()
        
        print("=" * 80)
        print("TESTING GPT-4o-mini (16K token limit)")
        print("=" * 80)
        print(f"Model: openai_gpt-4o-mini")
        print(f"Template: crud_todo_list")
        print(f"App Number: 4")
        print("-" * 80)
        
        print("\nStarting generation...")
        
        result = await service.generate_full_app(
            model_slug='openai_gpt-4o-mini',
            app_num=4,
            template_slug='crud_todo_list'
        )
        
        if result:
            print("\nGENERATION SUCCESSFUL!")
            
            # Check files
            app_dir = Path('generated/apps/openai_gpt-4o-mini/app4')
            backend = app_dir / 'backend' / 'app.py'
            frontend = app_dir / 'frontend' / 'src' / 'App.jsx'
            
            if backend.exists():
                code = backend.read_text()
                print(f"\nBackend: {len(code)} bytes, {len(code.splitlines())} lines")
                print(f"   Has db instance: {'db = SQLAlchemy()' in code}")
                print(f"   Has setup_app: {'def setup_app' in code}")
                print(f"   Routes: {code.count('@app.route')}")
            
            if frontend.exists():
                code = frontend.read_text()
                print(f"\nFrontend: {len(code)} bytes, {len(code.splitlines())} lines")
                print(f"   React import: {'import React' in code}")
                print(f"   Uses axios: {'axios' in code}")
        else:
            print("\n❌ GENERATION FAILED")

if __name__ == '__main__':
    asyncio.run(main())
