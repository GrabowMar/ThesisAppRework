"""
Generate three apps with different models to test compact templates.
"""

import sys
import os
import asyncio
sys.path.insert(0, 'src')

from app.factory import create_app
from pathlib import Path

async def test_three_apps_async():
    """
    Generate three apps:
    1. codex-mini (4K output) - uses compact templates
    2. gpt-3.5-turbo (16K output) - uses standard templates
    3. gpt-4o (16K output) - uses standard templates
    """
    app = create_app()
    
    with app.app_context():
        from app.services.generation import GenerationService
        gen_service = GenerationService()
        
        test_cases = [
            {
                'name': 'Codex Mini (4K) + Compact',
                'model': 'openai_codex-mini',
                'app_num': 60001,
                'template': 'crud_todo_list'
            },
            {
                'name': 'GPT-3.5 Turbo (16K) + Standard',
                'model': 'openai_gpt-3.5-turbo',
                'app_num': 60002,
                'template': 'crud_todo_list'
            },
            {
                'name': 'GPT-4o (16K) + Standard',
                'model': 'openai_gpt-4o-2024-11-20',
                'app_num': 60003,
                'template': 'crud_todo_list'
            }
        ]
        
        results = []
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n{'='*80}")
            print(f"Test {i}/3: {test['name']}")
            print(f"{'='*80}")
            
            try:
                # Generate full app
                print(f"\n🔧 Generating full app for {test['model']}...")
                
                result = await gen_service.generate_full_app(
                    model_slug=test['model'],
                    app_num=test['app_num'],
                    template_slug=test['template'],
                    generate_frontend=True,
                    generate_backend=True
                )
                
                print(f"  ✓ Scaffolded: {result.get('scaffolded', False)}")
                print(f"  ✓ Backend generated: {result.get('backend_generated', False)}")
                print(f"  ✓ Frontend generated: {result.get('frontend_generated', False)}")
                print(f"  ✓ Success: {result.get('success', False)}")
                
                if result.get('errors'):
                    print(f"  ⚠ Errors: {result['errors']}")
                
                # Read generated files to analyze
                app_dir = Path('generated') / 'apps' / test['model'] / f"app{test['app_num']}"
                backend_file = app_dir / 'backend' / 'app.py'
                frontend_file = app_dir / 'frontend' / 'src' / 'App.jsx'
                
                backend_code = ''
                frontend_code = ''
                
                if backend_file.exists():
                    backend_code = backend_file.read_text(encoding='utf-8')
                    backend_size = len(backend_code)
                    backend_lines = backend_code.count('\n') + 1
                    
                    # Check for key backend features
                    has_flask = 'from flask import' in backend_code
                    has_cors = 'CORS' in backend_code
                    has_db = 'SQLAlchemy' in backend_code
                    has_model = 'class Todo' in backend_code
                    has_main = "if __name__ == '__main__':" in backend_code
                    has_get = '@app.route' in backend_code and 'GET' in backend_code
                    has_post = 'POST' in backend_code
                    has_put = 'PUT' in backend_code
                    has_delete = 'DELETE' in backend_code
                    
                    print(f"\n  📄 Backend: {backend_size:,} bytes, {backend_lines} lines")
                    print(f"     Features: Flask={has_flask}, CORS={has_cors}, DB={has_db}, Model={has_model}")
                    print(f"     Endpoints: GET={has_get}, POST={has_post}, PUT={has_put}, DELETE={has_delete}")
                    print(f"     Main block: {has_main}")
                    
                    backend_features = {
                        'flask': has_flask,
                        'cors': has_cors,
                        'db': has_db,
                        'model': has_model,
                        'main': has_main,
                        'get': has_get,
                        'post': has_post,
                        'put': has_put,
                        'delete': has_delete
                    }
                else:
                    backend_size = 0
                    backend_lines = 0
                    backend_features = {}
                    print(f"\n  ✗ Backend file not found")
                
                if frontend_file.exists():
                    frontend_code = frontend_file.read_text(encoding='utf-8')
                    frontend_size = len(frontend_code)
                    frontend_lines = frontend_code.count('\n') + 1
                    
                    # Check for key frontend features
                    has_react = 'import React' in frontend_code
                    has_hooks = 'useState' in frontend_code
                    has_api_url = 'API_URL' in frontend_code
                    has_docker_net = 'backend:5000' in frontend_code
                    has_axios = 'axios' in frontend_code
                    has_bootstrap = 'bootstrap' in frontend_code
                    has_export = 'export default' in frontend_code
                    
                    print(f"\n  📄 Frontend: {frontend_size:,} bytes, {frontend_lines} lines")
                    print(f"     Features: React={has_react}, Hooks={has_hooks}, Axios={has_axios}")
                    print(f"     Config: API_URL={has_api_url}, Docker={has_docker_net}, Bootstrap={has_bootstrap}")
                    print(f"     Export: {has_export}")
                    
                    frontend_features = {
                        'react': has_react,
                        'hooks': has_hooks,
                        'api_url': has_api_url,
                        'docker_net': has_docker_net,
                        'axios': has_axios,
                        'bootstrap': has_bootstrap,
                        'export': has_export
                    }
                else:
                    frontend_size = 0
                    frontend_lines = 0
                    frontend_features = {}
                    print(f"\n  ✗ Frontend file not found")
                
                test_result = {
                    'test': test['name'],
                    'model': test['model'],
                    'app_num': test['app_num'],
                    'generation_result': result,
                    'backend': {
                        'size_bytes': backend_size,
                        'lines': backend_lines,
                        'features': backend_features
                    },
                    'frontend': {
                        'size_bytes': frontend_size,
                        'lines': frontend_lines,
                        'features': frontend_features
                    },
                    'total_bytes': backend_size + frontend_size,
                    'total_lines': backend_lines + frontend_lines
                }
                
                results.append(test_result)
                
            except Exception as e:
                print(f"\n✗ Error: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    'test': test['name'],
                    'model': test['model'],
                    'app_num': test['app_num'],
                    'error': str(e)
                })
        
        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY - COMPACT TEMPLATE VALIDATION")
        print(f"{'='*80}")
        
        for r in results:
            if 'error' in r:
                print(f"\n❌ {r['test']}: FAILED")
                print(f"   Error: {r['error']}")
            else:
                gen_result = r['generation_result']
                print(f"\n✅ {r['test']}:")
                print(f"   App: app{r['app_num']}")
                print(f"   Generation: Success={gen_result.get('success')}, Backend={gen_result.get('backend_generated')}, Frontend={gen_result.get('frontend_generated')}")
                print(f"   Backend: {r['backend']['size_bytes']:,} bytes, {r['backend']['lines']} lines")
                print(f"   Frontend: {r['frontend']['size_bytes']:,} bytes, {r['frontend']['lines']} lines")
                print(f"   Total: {r['total_bytes']:,} bytes, {r['total_lines']} lines")
                
                # Backend completeness
                if r['backend']['features']:
                    backend_score = sum(r['backend']['features'].values())
                    print(f"   Backend completeness: {backend_score}/9 features")
                
                # Frontend completeness
                if r['frontend']['features']:
                    frontend_score = sum(r['frontend']['features'].values())
                    print(f"   Frontend completeness: {frontend_score}/7 features")
        
        print(f"\n{'='*80}")
        print("✓ Test complete! Check generated/apps/ for the apps.")
        print(f"{'='*80}")

def test_three_apps():
    """Wrapper to run async test."""
    asyncio.run(test_three_apps_async())

if __name__ == '__main__':
    test_three_apps()
