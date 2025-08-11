"""
Basic Security Test
===================

Test script to verify that security features are working correctly.
This does not require external dependencies to run.
"""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_input_validator():
    """Test the InputValidator class."""
    print("🔍 Testing InputValidator...")
    
    try:
        from security import InputValidator, ValidationError
        
        # Test string sanitization
        result = InputValidator.sanitize_string("<script>alert('xss')</script>", 50)
        print(f"✓ XSS sanitization: {result}")
        assert "&lt;script&gt;" in result, "XSS not properly escaped"
        
        # Test model slug validation
        valid_slug = InputValidator.validate_model_slug("anthropic_claude-3")
        print(f"✓ Valid model slug: {valid_slug}")
        
        # Test invalid model slug
        try:
            InputValidator.validate_model_slug("<script>")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            print("✓ Invalid model slug rejected")
        
        # Test app number validation
        valid_app = InputValidator.validate_app_number("15")
        print(f"✓ Valid app number: {valid_app}")
        assert valid_app == 15
        
        # Test invalid app number
        try:
            InputValidator.validate_app_number("50")
            assert False, "Should have raised ValidationError"
        except ValidationError:
            print("✓ Invalid app number rejected")
        
        print("✅ InputValidator tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ InputValidator test failed: {e}")
        return False

def test_error_handlers():
    """Test error handling decorators."""
    print("\n🔍 Testing Error Handlers...")
    
    try:
        from security import handle_errors, ValidationError
        
        @handle_errors
        def test_function_that_raises_validation_error():
            raise ValidationError("Test validation error")
        
        @handle_errors  
        def test_function_that_raises_generic_error():
            raise Exception("Test generic error")
        
        # Test validation error handling
        response, status_code = test_function_that_raises_validation_error()
        assert status_code == 400
        print("✓ ValidationError handled correctly")
        
        # Test generic error handling
        response, status_code = test_function_that_raises_generic_error()
        assert status_code == 500
        print("✓ Generic error handled correctly")
        
        print("✅ Error handler tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Error handler test failed: {e}")
        return False

def test_security_headers():
    """Test that security headers can be applied."""
    print("\n🔍 Testing Security Headers...")
    
    try:
        from security import add_security_headers
        from flask import Flask
        
        app = Flask(__name__)
        add_security_headers(app)
        
        with app.test_client() as client:
            with app.test_request_context('/'):
                # Create a mock response
                from flask import make_response
                response = make_response("test")
                
                # Trigger after_request handlers
                response = app.process_response(response)
                
                # Check security headers
                expected_headers = [
                    'X-Frame-Options',
                    'X-Content-Type-Options', 
                    'X-XSS-Protection',
                    'Content-Security-Policy'
                ]
                
                for header in expected_headers:
                    if header in response.headers:
                        print(f"✓ {header} header present")
                    else:
                        print(f"⚠ {header} header missing")
        
        print("✅ Security headers test completed!")
        return True
        
    except Exception as e:
        print(f"❌ Security headers test failed: {e}")
        return False

def main():
    """Run all security tests."""
    print("🛡️ Running Security Tests")
    print("=" * 50)
    
    tests = [
        test_input_validator,
        test_error_handlers, 
        test_security_headers
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
        print("🎉 All security tests passed!")
        return 0
    else:
        print("⚠️  Some security tests failed!")
        return 1

if __name__ == "__main__":
    exit(main())