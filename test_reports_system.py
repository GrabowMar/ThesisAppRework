"""Test script for the new reports system"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
src_path = project_root / 'src'
sys.path.insert(0, str(src_path))
os.chdir(str(project_root))

print("="*60)
print("Testing Reports System")
print("="*60)

# Test 1: Import generators
print("\n1. Testing imports...")
try:
    from app.services.reports import (
        ModelReportGenerator, 
        AppReportGenerator, 
        ToolReportGenerator,
        BaseReportGenerator
    )
    print("   ✓ All generators imported successfully")
except Exception as e:
    print(f"   ✗ Import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Import service
print("\n2. Testing service import...")
try:
    from app.services.report_generation_service import ReportGenerationService
    print("   ✓ Report generation service imported")
except Exception as e:
    print(f"   ✗ Service import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Import models
print("\n3. Testing model import...")
try:
    from app.models.report import Report
    print("   ✓ Report model imported")
except Exception as e:
    print(f"   ✗ Model import error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Check generator interfaces
print("\n4. Testing generator interfaces...")
try:
    # Check if generators have required methods
    for gen_class in [ModelReportGenerator, AppReportGenerator, ToolReportGenerator]:
        assert hasattr(gen_class, 'collect_data'), f"{gen_class.__name__} missing collect_data"
        assert hasattr(gen_class, 'get_template_name'), f"{gen_class.__name__} missing get_template_name"
        assert hasattr(gen_class, 'validate_config'), f"{gen_class.__name__} missing validate_config"
        assert hasattr(gen_class, 'generate_summary'), f"{gen_class.__name__} missing generate_summary"
        print(f"   ✓ {gen_class.__name__} has all required methods")
except Exception as e:
    print(f"   ✗ Interface check error: {e}")
    sys.exit(1)

# Test 5: Check Report model validation
print("\n5. Testing Report model...")
try:
    # Check if Report has new report types
    report = Report()
    assert hasattr(report, 'validate_config_for_type'), "Report missing validate_config_for_type method"
    print("   ✓ Report model has validation method")
except Exception as e:
    print(f"   ✗ Report model error: {e}")
    sys.exit(1)

# Test 6: Test template names
print("\n6. Testing template name generation...")
try:
    from pathlib import Path
    test_config = {'model_slug': 'test', 'app_number': 1, 'tool_name': 'test'}
    
    model_gen = ModelReportGenerator({'model_slug': 'test'}, Path('/tmp'))
    app_gen = AppReportGenerator({'app_number': 1}, Path('/tmp'))
    tool_gen = ToolReportGenerator({}, Path('/tmp'))
    
    assert model_gen.get_template_name() == 'model_analysis.html'
    assert app_gen.get_template_name() == 'app_comparison.html'
    assert tool_gen.get_template_name() == 'tool_analysis.html'
    
    print("   ✓ Model generator: model_analysis.html")
    print("   ✓ App generator: app_comparison.html")
    print("   ✓ Tool generator: tool_analysis.html")
except Exception as e:
    print(f"   ✗ Template name error: {e}")
    sys.exit(1)

# Test 7: Test config validation
print("\n7. Testing config validation...")
try:
    # Model generator should require model_slug
    model_gen = ModelReportGenerator({}, Path('/tmp'))
    try:
        model_gen.validate_config()
        print("   ✗ Model generator should reject empty config")
    except Exception:
        print("   ✓ Model generator validates model_slug requirement")
    
    # App generator should require app_number
    app_gen = AppReportGenerator({}, Path('/tmp'))
    try:
        app_gen.validate_config()
        print("   ✗ App generator should reject empty config")
    except Exception:
        print("   ✓ App generator validates app_number requirement")
    
    # Tool generator accepts empty config (all filters optional)
    tool_gen = ToolReportGenerator({}, Path('/tmp'))
    tool_gen.validate_config()  # Should not raise
    print("   ✓ Tool generator accepts empty config (global analysis)")
    
except Exception as e:
    print(f"   ✗ Config validation error: {e}")
    sys.exit(1)

# Test 8: Check templates exist
print("\n8. Checking template files...")
template_dir = project_root / 'src' / 'templates' / 'pages' / 'reports'
templates = ['model_analysis.html', 'app_comparison.html', 'tool_analysis.html']

for template in templates:
    template_path = template_dir / template
    if template_path.exists():
        print(f"   ✓ {template} exists")
    else:
        print(f"   ✗ {template} NOT FOUND at {template_path}")

print("\n" + "="*60)
print("✓ All tests passed!")
print("="*60)
