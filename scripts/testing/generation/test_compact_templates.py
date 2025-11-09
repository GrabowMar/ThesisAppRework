"""Test compact templates with codex-mini."""
import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from app import create_app
from app.services.generation import get_generation_service

app = create_app()

def test_compact_templates():
    """Test generation with compact templates using codex-mini."""
    
    async def _do_gen():
        service = get_generation_service()
        return await service.generate_full_app(
            model_slug='openai_codex-mini',
            app_num=40001,
            template_slug='crud_todo_list',
            generate_frontend=True,
            generate_backend=True
        )
    
    with app.app_context():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_do_gen())
        finally:
            loop.close()
    
    print("\n" + "="*80)
    print("COMPACT TEMPLATE TEST RESULT")
    print("="*80)
    print(f"Model: openai_codex-mini (4K output limit)")
    print(f"Success: {result['success']}")
    print(f"Backend Generated: {result['backend_generated']}")
    print(f"Frontend Generated: {result['frontend_generated']}")
    print(f"App Dir: {result['app_dir']}")
    
    if result.get('errors'):
        print(f"\nErrors:")
        for err in result['errors']:
            print(f"  - {err}")
    
    # Check files
    app_dir = Path(result['app_dir'])
    backend_file = app_dir / 'backend' / 'app.py'
    frontend_file = app_dir / 'frontend' / 'src' / 'App.jsx'
    
    print(f"\n" + "="*80)
    print("FILE CHECK")
    print("="*80)
    
    if backend_file.exists():
        backend_size = backend_file.stat().st_size
        backend_content = backend_file.read_text(encoding='utf-8')
        is_scaffold = 'Minimal Flask scaffold' in backend_content
        print(f"Backend: {backend_size} bytes - {'SCAFFOLD' if is_scaffold else 'GENERATED'}")
        if not is_scaffold:
            has_flask = 'from flask import Flask' in backend_content
            has_cors = 'CORS' in backend_content
            has_main = "if __name__ == '__main__'" in backend_content
            has_todo = 'class Todo' in backend_content or 'class Item' in backend_content
            print(f"  ✓ Flask import: {has_flask}")
            print(f"  ✓ CORS: {has_cors}")
            print(f"  ✓ Main block: {has_main}")
            print(f"  ✓ Model defined: {has_todo}")
    else:
        print("Backend: NOT FOUND")
    
    if frontend_file.exists():
        frontend_size = frontend_file.stat().st_size
        frontend_content = frontend_file.read_text(encoding='utf-8')
        is_scaffold = 'Minimal React scaffold' in frontend_content
        print(f"Frontend: {frontend_size} bytes - {'SCAFFOLD' if is_scaffold else 'GENERATED'}")
        if not is_scaffold:
            has_react = 'import React' in frontend_content
            has_api = 'API_URL' in frontend_content
            has_backend = 'backend:5000' in frontend_content
            print(f"  ✓ React import: {has_react}")
            print(f"  ✓ API_URL constant: {has_api}")
            print(f"  ✓ Docker networking: {has_backend}")
    else:
        print("Frontend: NOT FOUND")
    
    return result['success']

if __name__ == '__main__':
    success = test_compact_templates()
    sys.exit(0 if success else 1)
