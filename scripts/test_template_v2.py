"""
Quick test script for the V2 Template System
Tests rendering without starting the full Flask app
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from app.services.template_renderer import TemplateRenderer

def test_template_renderer():
    """Test the template renderer service"""
    print("=" * 60)
    print("Testing V2 Template System")
    print("=" * 60)
    
    renderer = TemplateRenderer()
    
    # Test 1: List requirements
    print("\n1. Listing Requirements:")
    print("-" * 60)
    requirements = renderer.list_requirements()
    for req in requirements:
        print(f"  ✓ {req['name']} ({req['id']})")
        print(f"    {req['description']}")
    
    # Test 2: List scaffolding types
    print("\n2. Listing Scaffolding Types:")
    print("-" * 60)
    scaffolding_types = renderer.list_scaffolding_types()
    for stype in scaffolding_types:
        print(f"  ✓ {stype}")
    
    # Test 3: List template types
    print("\n3. Listing Template Types:")
    print("-" * 60)
    template_types = renderer.list_template_types()
    for ttype in template_types:
        print(f"  ✓ {ttype}")
    
    # Test 4: Load requirements
    print("\n4. Loading Requirements (xsd_verifier):")
    print("-" * 60)
    req_data = renderer.load_requirements('xsd_verifier')
    print(f"  Name: {req_data['name']}")
    print(f"  Description: {req_data['description']}")
    print(f"  Backend Requirements: {len(req_data['backend_requirements'])}")
    print(f"  Frontend Requirements: {len(req_data['frontend_requirements'])}")
    
    # Test 5: Load scaffolding
    print("\n5. Loading Scaffolding (react-flask):")
    print("-" * 60)
    scaffolding = renderer.load_scaffolding('react-flask')
    print(f"  Backend files: {list(scaffolding['backend'].keys())}")
    print(f"  Frontend files: {list(scaffolding['frontend'].keys())}")
    
    # Test 6: Render backend template
    print("\n6. Rendering Backend Template:")
    print("-" * 60)
    backend_prompt = renderer.render_template(
        'two-query', 'backend', req_data, scaffolding
    )
    print(f"  Rendered prompt length: {len(backend_prompt)} characters")
    print(f"  First 200 chars:\n  {backend_prompt[:200]}...")
    
    # Test 7: Render frontend template
    print("\n7. Rendering Frontend Template:")
    print("-" * 60)
    frontend_prompt = renderer.render_template(
        'two-query', 'frontend', req_data, scaffolding
    )
    print(f"  Rendered prompt length: {len(frontend_prompt)} characters")
    print(f"  First 200 chars:\n  {frontend_prompt[:200]}...")
    
    # Test 8: Preview both
    print("\n8. Preview Both Templates:")
    print("-" * 60)
    preview = renderer.preview('two-query', 'xsd_verifier', 'react-flask')
    print(f"  Backend prompt: {len(preview['backend'])} chars")
    print(f"  Frontend prompt: {len(preview['frontend'])} chars")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

if __name__ == '__main__':
    try:
        test_template_renderer()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
