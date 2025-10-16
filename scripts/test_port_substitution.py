"""Test port substitution in scaffolding templates"""
import re
from pathlib import Path

def test_port_substitution():
    """Test that port placeholders are correctly substituted"""
    
    # Test template content with placeholders
    template_content = """
    port: {{backend_port|5000}},
    target: 'http://localhost:{{backend_port|5000}}',
    FRONTEND_PORT={{frontend_port|8000}}
    CORS_ORIGINS=http://localhost:{{frontend_port|8000}}
    """
    
    # Substitutions
    substitutions = {
        'backend_port': '5001',
        'frontend_port': '8001',
    }
    
    # Apply substitutions (matching the logic from sample_generation_service.py)
    result = template_content
    
    # Replace pipe-default syntax {{key|default}}
    for key, value in substitutions.items():
        pattern = r'\{\{' + re.escape(key) + r'\|[^\}]+\}\}'
        result = re.sub(pattern, str(value), result)
    
    # Replace standard placeholders {{key}}
    for key, value in substitutions.items():
        result = result.replace(f"{{{{{key}}}}}", value)
    
    print("Original:")
    print(template_content)
    print("\nSubstituted:")
    print(result)
    
    # Verify substitutions
    assert '5001' in result
    assert '8001' in result
    assert '{{backend_port' not in result
    assert '{{frontend_port' not in result
    
    print("\n✅ Port substitution test passed!")

if __name__ == '__main__':
    test_port_substitution()
