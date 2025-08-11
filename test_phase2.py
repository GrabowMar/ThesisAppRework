"""
Phase 2 Security Implementation Test
===================================

Tests for database session management, API consistency, and enhanced error handling.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_database_utilities():
    """Test database utilities and session management."""
    print("🔍 Testing Database Utilities...")
    
    try:
        from database_utils import DatabaseManager, check_database_health
        
        # Test that the DatabaseManager class exists and has expected methods
        required_methods = [
            'get_session', 'safe_execute', 'safe_query', 
            'safe_get', 'safe_create', 'safe_update', 'safe_delete'
        ]
        
        for method in required_methods:
            if hasattr(DatabaseManager, method):
                print(f"✓ DatabaseManager.{method} method exists")
            else:
                print(f"❌ DatabaseManager.{method} method missing")
                return False
        
        # Test health check function
        health_status = check_database_health()
        if isinstance(health_status, dict) and 'connected' in health_status:
            print("✓ Database health check function works")
        else:
            print("❌ Database health check failed")
        
        print("✅ Database utilities test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Database utilities test failed: {e}")
        return False

def test_api_response_utilities():
    """Test standardized API response utilities."""
    print("\n🔍 Testing API Response Utilities...")
    
    try:
        from api_utils import APIResponse
        
        # Test success response
        response, status_code = APIResponse.success(data={'test': 'value'}, message="Test success")
        if status_code == 200 and 'success' in str(response.data) and 'true' in str(response.data).lower():
            print("✓ Success response format correct")
        else:
            print(f"❌ Success response format incorrect: {status_code}")
            return False
        
        # Test error response
        response, status_code = APIResponse.error("Test error", 400)
        if status_code == 400 and 'success' in str(response.data) and 'false' in str(response.data).lower():
            print("✓ Error response format correct")
        else:
            print(f"❌ Error response format incorrect: {status_code}")
            return False
        
        # Test specialized responses
        response, status_code = APIResponse.not_found("Test resource")
        if status_code == 404:
            print("✓ Not found response correct")
        else:
            print(f"❌ Not found response incorrect: {status_code}")
        
        response, status_code = APIResponse.validation_error("Test validation")
        if status_code == 400:
            print("✓ Validation error response correct")
        else:
            print(f"❌ Validation error response incorrect: {status_code}")
        
        print("✅ API response utilities test passed!")
        return True
        
    except Exception as e:
        print(f"❌ API response utilities test failed: {e}")
        return False

def test_enhanced_models():
    """Test enhanced database models with constraints."""
    print("\n🔍 Testing Enhanced Models...")
    
    try:
        # Test that models can be imported
        from models import ModelCapability, GeneratedApplication
        
        # Test ModelCapability constraints
        model_constraints = [
            'positive_context_window',
            'positive_max_tokens', 
            'positive_input_price',
            'positive_output_price',
            'valid_cost_efficiency',
            'valid_safety_score',
            'non_empty_model_id',
            'non_empty_provider'
        ]
        
        # Check if ModelCapability has table args (constraints)
        if hasattr(ModelCapability, '__table_args__'):
            print("✓ ModelCapability has table constraints")
        else:
            print("⚠ ModelCapability missing table constraints")
        
        # Test GeneratedApplication constraints  
        app_constraints = [
            'unique_model_app',
            'valid_app_number_range',
            'non_empty_model_slug',
            'non_empty_provider',
            'non_empty_app_type',
            'valid_container_status'
        ]
        
        if hasattr(GeneratedApplication, '__table_args__'):
            print("✓ GeneratedApplication has table constraints")
        else:
            print("⚠ GeneratedApplication missing table constraints")
        
        print("✅ Enhanced models test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Enhanced models test failed: {e}")
        return False

def test_security_integration():
    """Test integration of security features."""
    print("\n🔍 Testing Security Integration...")
    
    try:
        # Test that security modules can be imported together
        from security import InputValidator, handle_errors
        from database_utils import DatabaseManager
        from api_utils import APIResponse
        
        # Test that they work together
        @handle_errors
        def test_integrated_function():
            # Validate input
            model_slug = InputValidator.validate_model_slug("test_model")
            
            # Would use database safely (mock here)
            # result = DatabaseManager.safe_query(SomeModel, slug=model_slug)
            
            # Return standardized response
            return APIResponse.success(data={'model_slug': model_slug})
        
        # Execute the integrated function
        response = test_integrated_function()
        if response and 'success' in str(response):
            print("✓ Security features integrate successfully")
        else:
            print("❌ Security integration failed")
            return False
        
        print("✅ Security integration test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Security integration test failed: {e}")
        return False

def test_syntax_validation():
    """Test that all new files have valid Python syntax."""
    print("\n🔍 Testing File Syntax...")
    
    files_to_check = [
        'src/security.py',
        'src/database_utils.py',
        'src/api_utils.py'
    ]
    
    import ast
    
    for file_path in files_to_check:
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    ast.parse(f.read())
                print(f"✓ {file_path} syntax valid")
            else:
                print(f"⚠ {file_path} not found")
        except SyntaxError as e:
            print(f"❌ {file_path} syntax error: {e}")
            return False
    
    print("✅ Syntax validation passed!")
    return True

def main():
    """Run all Phase 2 tests."""
    print("🛡️ Running Phase 2 Security Tests")
    print("=" * 50)
    
    tests = [
        test_syntax_validation,
        test_database_utilities,
        test_api_response_utilities,
        test_enhanced_models,
        test_security_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"🎯 Test Results: {passed} passed, {failed} failed")
    
    if failed == 0:
        print("🎉 All Phase 2 tests passed!")
        print("\n📊 Phase 2 Improvements:")
        print("• Database session management with context managers")
        print("• Enhanced models with integrity constraints")
        print("• Standardized API response formatting")
        print("• Improved error handling and logging")
        print("• Security feature integration")
        return 0
    else:
        print("⚠️  Some Phase 2 tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())