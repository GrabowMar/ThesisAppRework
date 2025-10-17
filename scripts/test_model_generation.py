"""Test Generation Across Multiple Models

Systematically test generation with different models and templates.
Validates results and provides improvement recommendations.

Usage:
    python scripts/test_model_generation.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import asyncio
import json
from datetime import datetime
from app.factory import create_app
from app.models import ModelCapability
from app.services.simple_generation_service import get_simple_generation_service, GenerationRequest


def get_available_models():
    """Get list of available models from database."""
    app = create_app()
    with app.app_context():
        # Get models that are installed
        models = ModelCapability.query.filter_by(installed=True).limit(5).all()
        return [(m.canonical_slug, m.model_id, m.model_name) for m in models]


def get_available_templates():
    """Get list of available templates - using filesystem since no AppTemplate model."""
    from app.paths import MISC_DIR
    template_dir = MISC_DIR / 'templates' / 'two-query'
    
    templates = []
    # We only have the two-query templates
    if (template_dir / 'backend.md.jinja2').exists():
        templates.append((1, "Todo App", "Simple CRUD todo application with Flask backend and React frontend"))
    
    return templates


async def test_generation(model_slug: str, model_id: str, template_id: int, app_num: int):
    """Test generating both backend and frontend for a model/template combo."""
    
    print(f"\n{'='*80}")
    print(f"Testing: {model_slug} / Template {template_id} / App {app_num}")
    print(f"{'='*80}")
    
    service = get_simple_generation_service()
    results = {
        'model_slug': model_slug,
        'template_id': template_id,
        'app_num': app_num,
        'timestamp': datetime.utcnow().isoformat(),
        'backend': {},
        'frontend': {},
        'validation': {}
    }
    
    # Ensure scaffolding exists
    print("\n1. Setting up scaffolding...")
    success = service.scaffold_app(model_slug, app_num, force=False)
    if success:
        print("   [OK] Scaffolding ready")
    else:
        print("   [FAIL] Scaffolding failed")
        return results
    
    # Generate backend
    print("\n2. Generating backend...")
    backend_request = GenerationRequest(
        template_id=template_id,
        model_slug=model_slug,
        component='backend',
        temperature=0.3,
        max_tokens=16000
    )
    
    try:
        backend_result = await service.generate_code(backend_request)
        results['backend'] = {
            'success': backend_result.success,
            'error': backend_result.error,
            'tokens': backend_result.tokens_used,
            'duration': backend_result.duration,
            'content_length': len(backend_result.content) if backend_result.success else 0
        }
        
        if backend_result.success:
            print(f"   [OK] Generated ({backend_result.tokens_used} tokens, {backend_result.duration:.2f}s)")
            
            # Save backend code
            save_result = service.save_generated_code(
                model_slug, app_num, 'backend', backend_result.content
            )
            print(f"   ✓ Saved {len(save_result['saved_files'])} files")
            results['backend']['saved_files'] = save_result['saved_files']
            results['backend']['validation'] = save_result.get('validation', {})
        else:
            print(f"   [FAIL] Generation failed: {backend_result.error}")
    except Exception as e:
        print(f"   [FAIL] Exception: {e}")
        results['backend']['error'] = str(e)
    
    # Generate frontend
    print("\n3. Generating frontend...")
    frontend_request = GenerationRequest(
        template_id=template_id,
        model_slug=model_slug,
        component='frontend',
        temperature=0.3,
        max_tokens=16000
    )
    
    try:
        frontend_result = await service.generate_code(frontend_request)
        results['frontend'] = {
            'success': frontend_result.success,
            'error': frontend_result.error,
            'tokens': frontend_result.tokens_used,
            'duration': frontend_result.duration,
            'content_length': len(frontend_result.content) if frontend_result.success else 0
        }
        
        if frontend_result.success:
            print(f"   [OK] Generated ({frontend_result.tokens_used} tokens, {frontend_result.duration:.2f}s)")
            
            # Save frontend code
            save_result = service.save_generated_code(
                model_slug, app_num, 'frontend', frontend_result.content
            )
            print(f"   [OK] Saved {len(save_result['saved_files'])} files")
            results['frontend']['saved_files'] = save_result['saved_files']
            results['frontend']['validation'] = save_result.get('validation', {})
        else:
            print(f"   [FAIL] Generation failed: {frontend_result.error}")
    except Exception as e:
        print(f"   [FAIL] Exception: {e}")
        results['frontend']['error'] = str(e)
    
    # Overall validation summary
    print("\n4. Validation Summary:")
    backend_val = results['backend'].get('validation', {}).get('backend', {})
    frontend_val = results['frontend'].get('validation', {}).get('frontend', {})
    
    if backend_val:
        if backend_val.get('valid'):
            print("   [OK] Backend validation passed")
        else:
            print("   [FAIL] Backend validation failed")
            for err in backend_val.get('errors', []):
                print(f"      - {err}")
    
    if frontend_val:
        if frontend_val.get('valid'):
            print("   [OK] Frontend validation passed")
        else:
            print("   [FAIL] Frontend validation failed")
            for err in frontend_val.get('errors', []):
                print(f"      - {err}")
    
    results['overall_success'] = (
        results['backend'].get('success', False) and 
        results['frontend'].get('success', False) and
        backend_val.get('valid', False) and
        frontend_val.get('valid', False)
    )
    
    return results


async def run_test_suite():
    """Run comprehensive test suite."""
    
    print("="*80)
    print("MULTI-MODEL GENERATION TEST SUITE")
    print("="*80)
    
    # Get available resources
    print("\nQuerying available models and templates...")
    models = get_available_models()
    templates = get_available_templates()
    
    print(f"\nFound {len(models)} enabled models:")
    for slug, mid, name in models[:5]:
        print(f"  - {name} ({slug})")
    if len(models) > 5:
        print(f"  ... and {len(models) - 5} more")
    
    print(f"\nFound {len(templates)} templates:")
    for tid, name, desc in templates[:5]:
        print(f"  - #{tid}: {name}")
    if len(templates) > 5:
        print(f"  ... and {len(templates) - 5} more")
    
    # Select test cases
    # Test a few different models with a simple template
    test_cases = []
    
    if len(models) > 0 and len(templates) > 0:
        # Use first template for all tests
        template_id = templates[0][0]
        
        # Test first 3 models
        for i, (slug, mid, name) in enumerate(models[:3], start=1):
            test_cases.append((slug, mid, template_id, 900 + i))
    
    if not test_cases:
        print("\n[ERROR] No models or templates available for testing")
        return []
    
    print(f"\n{'='*80}")
    print(f"Running {len(test_cases)} test cases...")
    print(f"{'='*80}")
    
    # Run tests
    all_results = []
    for slug, mid, template_id, app_num in test_cases:
        result = await test_generation(slug, mid, template_id, app_num)
        all_results.append(result)
        
        # Small delay between tests
        await asyncio.sleep(2)
    
    return all_results


def analyze_results(all_results):
    """Analyze test results and provide recommendations."""
    
    print("\n" + "="*80)
    print("TEST RESULTS ANALYSIS")
    print("="*80)
    
    if not all_results:
        print("\nNo results to analyze")
        return
    
    total = len(all_results)
    successful = sum(1 for r in all_results if r.get('overall_success', False))
    
    print(f"\nOverall Success Rate: {successful}/{total} ({successful/total*100:.1f}%)")
    
    # Backend analysis
    backend_success = sum(1 for r in all_results if r['backend'].get('success', False))
    backend_valid = sum(1 for r in all_results if r['backend'].get('validation', {}).get('backend', {}).get('valid', False))
    
    print(f"\nBackend:")
    print(f"  Generation Success: {backend_success}/{total} ({backend_success/total*100:.1f}%)")
    print(f"  Validation Pass: {backend_valid}/{total} ({backend_valid/total*100:.1f}%)")
    
    # Frontend analysis
    frontend_success = sum(1 for r in all_results if r['frontend'].get('success', False))
    frontend_valid = sum(1 for r in all_results if r['frontend'].get('validation', {}).get('frontend', {}).get('valid', False))
    
    print(f"\nFrontend:")
    print(f"  Generation Success: {frontend_success}/{total} ({frontend_success/total*100:.1f}%)")
    print(f"  Validation Pass: {frontend_valid}/{total} ({frontend_valid/total*100:.1f}%)")
    
    # Common errors
    print("\nCommon Issues:")
    
    all_errors = []
    for r in all_results:
        backend_errors = r['backend'].get('validation', {}).get('backend', {}).get('errors', [])
        frontend_errors = r['frontend'].get('validation', {}).get('frontend', {}).get('errors', [])
        all_errors.extend(backend_errors)
        all_errors.extend(frontend_errors)
    
    if all_errors:
        from collections import Counter
        error_counts = Counter(all_errors)
        for error, count in error_counts.most_common(5):
            print(f"  - {error} ({count}x)")
    else:
        print("  No validation errors!")
    
    # Recommendations
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    
    if backend_valid < total:
        print("\n1. Backend Issues:")
        print("   - Review backend template for missing dependency instructions")
        print("   - Check if models are following requirements.txt format")
        print("   - Consider adding more examples to template")
    
    if frontend_valid < total:
        print("\n2. Frontend Issues:")
        print("   - Review frontend template for package.json requirements")
        print("   - Ensure API URL patterns are clear")
        print("   - Check React best practices in template")
    
    if successful == total:
        print("\n[SUCCESS] All tests passed! System is working well.")
        print("  Consider:")
        print("  - Testing with more complex templates")
        print("  - Testing with different model parameters")
        print("  - Adding more validation rules")
    
    # Save results
    results_file = Path(__file__).parent.parent / 'results' / 'test' / f'generation_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    results_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\nDetailed results saved to: {results_file}")


async def main():
    """Main entry point."""
    results = await run_test_suite()
    analyze_results(results)


if __name__ == '__main__':
    asyncio.run(main())
