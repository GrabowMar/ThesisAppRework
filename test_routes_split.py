"""
Quick test to verify Flask app can start after routes split
"""
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

try:
    print("=" * 60)
    print("Testing Flask App Initialization")
    print("=" * 60)
    
    # Test importing routes
    print("\n1. Testing route imports...")
    from app.routes import models_bp, jinja_applications_bp
    print("   ✓ models_bp imported")
    print("   ✓ jinja_applications_bp imported")
    
    # Test importing functions from applications
    print("\n2. Testing applications module functions...")
    from app.routes.jinja.applications import (
        _render_applications_page,
        build_applications_context,
        generate_application,
        application_detail,
        _render_application_section,
        application_section_prompts,
        application_file_preview,
        application_generation_metadata
    )
    print("   ✓ All application functions imported")
    
    # Test importing functions from models
    print("\n3. Testing models module functions...")
    from app.routes.jinja.models import (
        _enrich_model,
        models_index,
        models_overview,
        model_actions,
        model_apps,
        models_import_page,
        export_models_csv,
        models_filter,
        models_comparison,
        model_details,
        model_section
    )
    print("   ✓ All model functions imported")
    
    # Test shared utilities
    print("\n4. Testing shared utilities...")
    from app.routes.jinja.shared import SimplePagination
    print("   ✓ SimplePagination imported")
    
    # Verify blueprint names and prefixes
    print("\n5. Verifying blueprint configuration...")
    assert models_bp.name == 'models', f"Expected 'models', got '{models_bp.name}'"
    assert models_bp.url_prefix == '/models', f"Expected '/models', got '{models_bp.url_prefix}'"
    print(f"   ✓ models_bp: name='{models_bp.name}', prefix='{models_bp.url_prefix}'")
    
    assert jinja_applications_bp.name == 'applications', f"Expected 'applications', got '{jinja_applications_bp.name}'"
    assert jinja_applications_bp.url_prefix == '/applications', f"Expected '/applications', got '{jinja_applications_bp.url_prefix}'"
    print(f"   ✓ jinja_applications_bp: name='{jinja_applications_bp.name}', prefix='{jinja_applications_bp.url_prefix}'")
    
    print("\n" + "=" * 60)
    print("✓ All tests passed! Flask app should start correctly.")
    print("=" * 60)
    sys.exit(0)
    
except Exception as e:
    print("\n" + "=" * 60)
    print(f"✗ Test failed: {e}")
    print("=" * 60)
    import traceback
    traceback.print_exc()
    sys.exit(1)
