"""
Quick validation script for routes split
Checks that the split was successful without requiring full Flask app initialization
"""
import ast
import sys
from pathlib import Path

def validate_python_file(filepath):
    """Validate that a Python file has valid syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        ast.parse(code)
        return True, "Valid syntax"
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def check_blueprint_name(filepath, expected_name):
    """Check that a file defines a blueprint with the expected name."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        if f"{expected_name} = Blueprint(" in content:
            return True, f"Blueprint '{expected_name}' found"
        return False, f"Blueprint '{expected_name}' not found"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    base_path = Path(__file__).parent / "src" / "app" / "routes" / "jinja"
    
    files_to_check = [
        ("applications.py", "applications_bp"),
        ("models.py", "models_bp"),
        ("shared.py", None),  # No blueprint in shared
    ]
    
    print("=" * 60)
    print("Routes Split Validation")
    print("=" * 60)
    
    all_valid = True
    
    for filename, blueprint_name in files_to_check:
        filepath = base_path / filename
        print(f"\nChecking {filename}...")
        
        # Check file exists
        if not filepath.exists():
            print(f"  ✗ File not found: {filepath}")
            all_valid = False
            continue
        print(f"  ✓ File exists")
        
        # Check syntax
        valid, msg = validate_python_file(filepath)
        if valid:
            print(f"  ✓ {msg}")
        else:
            print(f"  ✗ {msg}")
            all_valid = False
            continue
        
        # Check blueprint name (if applicable)
        if blueprint_name:
            valid, msg = check_blueprint_name(filepath, blueprint_name)
            if valid:
                print(f"  ✓ {msg}")
            else:
                print(f"  ✗ {msg}")
                all_valid = False
    
    # Check __init__.py imports
    print(f"\nChecking __init__.py...")
    init_path = base_path.parent / "__init__.py"
    try:
        with open(init_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_imports = [
            "from .jinja.applications import applications_bp as jinja_applications_bp",
            "from .jinja.models import models_bp",
        ]
        
        for imp in required_imports:
            if imp in content:
                print(f"  ✓ Import found: {imp}")
            else:
                print(f"  ✗ Import missing: {imp}")
                all_valid = False
                
        # Check registration
        if "app.register_blueprint(jinja_applications_bp)" in content:
            print(f"  ✓ jinja_applications_bp registered")
        else:
            print(f"  ✗ jinja_applications_bp not registered")
            all_valid = False
            
    except Exception as e:
        print(f"  ✗ Error checking __init__.py: {e}")
        all_valid = False
    
    print("\n" + "=" * 60)
    if all_valid:
        print("✓ All validation checks passed!")
        print("=" * 60)
        return 0
    else:
        print("✗ Some validation checks failed")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
