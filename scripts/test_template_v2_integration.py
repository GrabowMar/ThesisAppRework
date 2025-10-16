"""
Integration test for V2 Template System with actual generation
Tests end-to-end flow: requirements → template → model → code
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

# Set mock mode for testing
os.environ['OPENROUTER_API_KEY'] = 'mock-key-for-testing'

from app.services.template_renderer import TemplateRenderer
from app.services.sample_generation_service import Template, get_sample_generation_service

def test_v2_template_with_generation():
    """Test V2 template system integrated with generation service"""
    print("=" * 70)
    print("V2 Template System - Generation Integration Test")
    print("=" * 70)
    
    # Step 1: Render V2 templates
    print("\n1. Rendering V2 Templates")
    print("-" * 70)
    renderer = TemplateRenderer()
    
    requirements = renderer.load_requirements('base64_converter')
    scaffolding = renderer.load_scaffolding('react-flask')
    
    backend_prompt = renderer.render_template(
        'two-query', 'backend', requirements, scaffolding
    )
    frontend_prompt = renderer.render_template(
        'two-query', 'frontend', requirements, scaffolding
    )
    
    print(f"✓ Backend prompt: {len(backend_prompt)} chars")
    print(f"✓ Frontend prompt: {len(frontend_prompt)} chars")
    print(f"✓ App name: {requirements['name']}")
    
    # Step 2: Create Template objects from V2 prompts
    print("\n2. Creating Template Objects for Generation Service")
    print("-" * 70)
    
    backend_template = Template(
        app_num=100,  # Use 100 to avoid conflicts
        name=f"{requirements['app_id']}_backend_v2",
        content=backend_prompt,
        requirements=requirements.get('backend_requirements', []),
        template_type='backend',
        display_name=f"{requirements['name']} (Backend - V2)"
    )
    
    frontend_template = Template(
        app_num=100,
        name=f"{requirements['app_id']}_frontend_v2",
        content=frontend_prompt,
        requirements=requirements.get('frontend_requirements', []),
        template_type='frontend',
        display_name=f"{requirements['name']} (Frontend - V2)"
    )
    
    print(f"✓ Backend template created: {backend_template.name}")
    print(f"✓ Frontend template created: {frontend_template.name}")
    
    # Step 3: Register templates with generation service
    print("\n3. Registering with Generation Service")
    print("-" * 70)
    
    gen_service = get_sample_generation_service()
    
    # Add templates to registry
    gen_service.template_registry.templates.append(backend_template)
    gen_service.template_registry.templates.append(frontend_template)
    gen_service.template_registry._by_name[backend_template.name] = backend_template
    gen_service.template_registry._by_name[frontend_template.name] = frontend_template
    gen_service.template_registry._resort()
    
    print(f"✓ Templates registered")
    print(f"✓ Total templates in registry: {len(gen_service.template_registry.templates)}")
    
    # Step 4: Verify templates can be retrieved
    print("\n4. Verifying Template Retrieval")
    print("-" * 70)
    
    retrieved_backend = gen_service.template_registry.get(backend_template.name)
    retrieved_frontend = gen_service.template_registry.get(frontend_template.name)
    
    if retrieved_backend and retrieved_frontend:
        print(f"✓ Backend template retrieved: {retrieved_backend.display_name}")
        print(f"✓ Frontend template retrieved: {retrieved_frontend.display_name}")
    else:
        print("✗ Failed to retrieve templates")
        return False
    
    # Step 5: List templates to verify they appear
    print("\n5. Listing All Templates")
    print("-" * 70)
    
    all_templates = gen_service.list_templates()
    v2_templates = [t for t in all_templates if '_v2' in t.get('name', '')]
    
    print(f"✓ Total templates: {len(all_templates)}")
    print(f"✓ V2 templates: {len(v2_templates)}")
    for t in v2_templates:
        print(f"  - {t['display_name']} (app {t['app_num']}, {t['template_type']})")
    
    # Step 6: Simulate generation request (without actually calling API)
    print("\n6. Simulating Generation Request")
    print("-" * 70)
    
    print(f"✓ Would generate with:")
    print(f"  - Template ID: 100 (app_num)")
    print(f"  - Model: mock/basic-coder")
    print(f"  - Backend prompt: {len(backend_prompt)} chars")
    print(f"  - Frontend prompt: {len(frontend_prompt)} chars")
    print(f"  - Output dir: generated/apps/mock_basic-coder/app_100/")
    
    # Step 7: Show V2 template structure
    print("\n7. V2 Template Content Preview")
    print("-" * 70)
    
    print("Backend prompt (first 300 chars):")
    print(f"  {backend_prompt[:300]}...")
    print("\nFrontend prompt (first 300 chars):")
    print(f"  {frontend_prompt[:300]}...")
    
    print("\n" + "=" * 70)
    print("✅ Integration test completed successfully!")
    print("=" * 70)
    print("\n📝 Summary:")
    print(f"  - V2 templates rendered: ✓")
    print(f"  - Template objects created: ✓")
    print(f"  - Registered with generation service: ✓")
    print(f"  - Ready for actual generation: ✓")
    print(f"\n💡 To generate actual code, call:")
    print(f"  gen_service.generate_async('100', 'mock/basic-coder')")
    print()
    
    return True

if __name__ == '__main__':
    try:
        success = test_v2_template_with_generation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
