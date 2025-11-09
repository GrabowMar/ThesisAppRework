"""
Compare compact vs standard templates with different models.
"""

import sys
import os
sys.path.insert(0, 'src')

from app.factory import create_app
from app.services.generation import GenerationService
from app.models import GenerationConfig
import json

def test_template_comparison():
    """
    Test both template variants with different models to show the benefit.
    """
    app = create_app()
    
    with app.app_context():
        gen_service = GenerationService()
        
        # Test scenarios:
        # 1. Small model (4K output) - shows truncation even with compact
        # 2. Medium model (8K output) - shows compact templates enable success
        # 3. Large model (16K output) - shows standard templates work fine
        
        test_cases = [
            {
                'name': 'Codex Mini (4K) + Compact',
                'model': 'openai_codex-mini',
                'app_num': 50001,
                'expected': 'Truncated but more complete than standard would be'
            },
            {
                'name': 'GPT-3.5 Turbo (16K) + Standard',
                'model': 'openai_gpt-3.5-turbo',
                'app_num': 50002,
                'expected': 'Complete generation with detailed code'
            },
            {
                'name': 'GPT-4o (16K) + Standard',
                'model': 'openai_gpt-4o-2024-11-20',
                'app_num': 50003,
                'expected': 'Complete generation with advanced features'
            }
        ]
        
        results = []
        
        for test in test_cases:
            print(f"\n{'='*80}")
            print(f"Testing: {test['name']}")
            print(f"{'='*80}")
            
            try:
                # Generate backend
                backend_config = GenerationConfig(
                    model_slug=test['model'],
                    app_number=test['app_num'],
                    component='backend',
                    template_id='crud_todo_list'
                )
                
                backend_result = gen_service.generate_component(backend_config)
                backend_success = backend_result.get('success', False)
                backend_size = len(backend_result.get('generated_code', ''))
                
                # Generate frontend
                frontend_config = GenerationConfig(
                    model_slug=test['model'],
                    app_number=test['app_num'],
                    component='frontend',
                    template_id='crud_todo_list'
                )
                
                frontend_result = gen_service.generate_component(frontend_config)
                frontend_success = frontend_result.get('success', False)
                frontend_size = len(frontend_result.get('generated_code', ''))
                
                result = {
                    'test': test['name'],
                    'model': test['model'],
                    'backend_success': backend_success,
                    'backend_size_bytes': backend_size,
                    'frontend_success': frontend_success,
                    'frontend_size_bytes': frontend_size,
                    'total_bytes': backend_size + frontend_size,
                    'expected': test['expected']
                }
                
                results.append(result)
                
                print(f"✓ Backend: {backend_size} bytes, Success: {backend_success}")
                print(f"✓ Frontend: {frontend_size} bytes, Success: {frontend_success}")
                print(f"✓ Total: {backend_size + frontend_size} bytes")
                
            except Exception as e:
                print(f"✗ Error: {e}")
                results.append({
                    'test': test['name'],
                    'model': test['model'],
                    'error': str(e)
                })
        
        # Summary
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        
        for r in results:
            if 'error' in r:
                print(f"\n{r['test']}: FAILED")
                print(f"  Error: {r['error']}")
            else:
                print(f"\n{r['test']}:")
                print(f"  Backend: {r['backend_size_bytes']:,} bytes")
                print(f"  Frontend: {r['frontend_size_bytes']:,} bytes")
                print(f"  Total: {r['total_bytes']:,} bytes")
                print(f"  Expected: {r['expected']}")
        
        # Save results
        with open('template_comparison_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n✓ Results saved to template_comparison_results.json")

if __name__ == '__main__':
    test_template_comparison()
