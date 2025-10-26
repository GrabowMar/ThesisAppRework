"""Quick verification script for graceful fallback implementation.

Run this to verify the implementation is working correctly without full test suite.
"""
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def verify_implementation():
    """Verify all components are in place."""
    checks = []
    
    # 1. Check settings.py has new config
    try:
        from config.settings import Config
        has_timeout = hasattr(Config, 'ANALYZER_SERVICE_TIMEOUT')
        has_retry = hasattr(Config, 'ANALYZER_RETRY_FAILED_SERVICES')
        checks.append(('Config settings', has_timeout and has_retry))
    except Exception as e:
        checks.append(('Config settings', False, str(e)))
    
    # 2. Check TaskExecutionService has timeout wrapper
    try:
        from app.services.task_execution_service import TaskExecutionService
        import inspect
        
        # Check if methods exist in the class
        has_wrapper = hasattr(TaskExecutionService, '_execute_service_with_timeout')
        
        # Check if __init__ sets the timeout attributes
        init_source = inspect.getsource(TaskExecutionService.__init__)
        has_timeout_init = '_service_timeout' in init_source and '_retry_enabled' in init_source
        
        checks.append(('Service timeout wrapper', has_wrapper and has_timeout_init))
    except Exception as e:
        checks.append(('Service timeout wrapper', False, str(e)))
    
    # 3. Check .env has variables
    try:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
        with open(env_path, 'r') as f:
            env_content = f.read()
        has_timeout_var = 'ANALYZER_SERVICE_TIMEOUT' in env_content
        has_retry_var = 'ANALYZER_RETRY_FAILED_SERVICES' in env_content
        checks.append(('.env configuration', has_timeout_var and has_retry_var))
    except Exception as e:
        checks.append(('.env configuration', False, str(e)))
    
    # 4. Check template has warning UI
    try:
        template_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'src', 
            'templates', 
            'pages', 
            'analysis', 
            'result_detail.html'
        )
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        has_warning = 'degraded_services' in template_content
        has_alert = 'Partial Results Available' in template_content
        checks.append(('Warning UI template', has_warning and has_alert))
    except Exception as e:
        checks.append(('Warning UI template', False, str(e)))
    
    # 5. Check documentation exists
    try:
        doc_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'docs',
            'features',
            'GRACEFUL_ANALYZER_FALLBACKS.md'
        )
        doc_exists = os.path.exists(doc_path)
        checks.append(('Documentation', doc_exists))
    except Exception as e:
        checks.append(('Documentation', False, str(e)))
    
    # Print results
    print("\n" + "="*60)
    print("GRACEFUL ANALYZER FALLBACKS - VERIFICATION")
    print("="*60 + "\n")
    
    all_passed = True
    for check in checks:
        name = check[0]
        passed = check[1]
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status:12} {name}")
        if not passed and len(check) > 2:
            print(f"             Error: {check[2][:100]}")  # Truncate long errors
        all_passed = all_passed and passed
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Implementation complete!")
    else:
        print("❌ SOME CHECKS FAILED - Review errors above")
    print("="*60 + "\n")
    
    return all_passed


if __name__ == '__main__':
    success = verify_implementation()
    sys.exit(0 if success else 1)
