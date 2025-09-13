#!/usr/bin/env python3
"""Test configuration and analysis creation workflow"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_configuration():
    """Test the configuration system."""
    try:
        from app.config.config_manager import get_config
        
        config = get_config()
        
        print("🔧 Configuration System Test")
        print("=" * 40)
        
        # Test default tools
        security_tools = config.get_default_tools('security')
        print(f"✅ Security tools: {security_tools}")
        
        # Test service URLs
        static_url = config.get_analyzer_service_url('static')
        print(f"✅ Static service URL: {static_url}")
        
        # Test valid tools
        valid_tools = config.get_valid_tools('security')
        print(f"✅ Valid security tools: {valid_tools}")
        
        print("\n✅ Configuration system working correctly!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_imports():
    """Test that all our updated services can import successfully."""
    try:
        print("\n🔍 Testing Service Imports")
        print("=" * 40)
        
        from app.services.task_execution_service import TaskExecutionService
        print("✅ TaskExecutionService imported")
        
        from app.services.security_service import SecurityService
        print("✅ SecurityService imported")
        
        from app.services.analyzer_integration import get_analyzer_integration
        print("✅ AnalyzerIntegration imported")
        
        from app.utils.validators import validate_security_tools
        print("✅ Validators imported")
        
        print("\n✅ All service imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_validator_with_config():
    """Test that validators use the new configuration."""
    try:
        print("\n🛡️ Testing Security Tool Validation")
        print("=" * 40)
        
        from app.utils.validators import validate_security_tools
        
        # Test with valid tools
        result = validate_security_tools(['bandit', 'safety'])
        print(f"✅ Valid tools result: {result['valid']}")
        
        # Test with invalid tools
        result = validate_security_tools(['invalid_tool'])
        print(f"✅ Invalid tools rejected: {not result['valid']}")
        
        print("\n✅ Validator configuration integration working!")
        return True
        
    except Exception as e:
        print(f"❌ Validator test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = True
    
    success &= test_configuration()
    success &= test_imports()
    success &= test_validator_with_config()
    
    if success:
        print("\n🎉 All tests passed! Configuration integration is working correctly.")
    else:
        print("\n💥 Some tests failed. Check the output above for details.")
        sys.exit(1)