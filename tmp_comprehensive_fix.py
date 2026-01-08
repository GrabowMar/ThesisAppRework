#!/usr/bin/env python3
"""
Comprehensive fix script for ThesisApp production deployment.
Fixes:
1. Flask config to include CELERY_BROKER_URL and CELERY_RESULT_BACKEND
2. Add get_celery function to extensions.py
3. Analyzer statuses Docker detection (if not already patched)
"""

import re
import os

BASE_DIR = "/home/ubuntu/ThesisAppRework"

def fix_factory_config():
    """Add Celery/Redis config to Flask factory.py"""
    filepath = os.path.join(BASE_DIR, "src/app/factory.py")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already has CELERY_BROKER_URL config
    if "CELERY_BROKER_URL" in content and "app.config.update" in content:
        # Check if it's in the config.update section
        match = re.search(r"app\.config\.update\([^)]+CELERY_BROKER_URL", content, re.DOTALL)
        if match:
            print("factory.py: CELERY_BROKER_URL already in config.update - skipping")
            return True
    
    # Find the app.config.update section and add Celery config
    # Look for the pattern ending with ANALYZER_AUTO_START
    pattern = r"(ANALYZER_AUTO_START=os\.environ\.get\('ANALYZER_AUTO_START', 'false'\)\.lower\(\) == 'true',\s*\n\s*\))"
    
    replacement = '''ANALYZER_AUTO_START=os.environ.get('ANALYZER_AUTO_START', 'false').lower() == 'true',

        # Redis/Celery configuration
        REDIS_URL=os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')),
        CELERY_BROKER_URL=os.environ.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
        CELERY_RESULT_BACKEND=os.environ.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
        USE_CELERY_ANALYSIS=os.environ.get('USE_CELERY_ANALYSIS', 'false').lower() == 'true',
    )'''
    
    new_content, count = re.subn(pattern, replacement, content)
    
    if count == 0:
        print("factory.py: Could not find ANALYZER_AUTO_START pattern to add Celery config")
        # Try alternative approach - find config.update closing paren
        alt_pattern = r"(ANALYZER_AUTO_START=os\.environ\.get\('ANALYZER_AUTO_START', 'false'\)\.lower\(\) == 'true',)"
        alt_replacement = '''ANALYZER_AUTO_START=os.environ.get('ANALYZER_AUTO_START', 'false').lower() == 'true',

        # Redis/Celery configuration
        REDIS_URL=os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')),
        CELERY_BROKER_URL=os.environ.get('CELERY_BROKER_URL', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
        CELERY_RESULT_BACKEND=os.environ.get('CELERY_RESULT_BACKEND', os.environ.get('REDIS_URL', 'redis://localhost:6379/0')),
        USE_CELERY_ANALYSIS=os.environ.get('USE_CELERY_ANALYSIS', 'false').lower() == 'true','''
        
        new_content, count = re.subn(alt_pattern, alt_replacement, content)
    
    if count > 0:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"factory.py: Added Celery/Redis config successfully!")
        return True
    else:
        print("factory.py: Failed to find insertion point for Celery config")
        return False


def fix_extensions_get_celery():
    """Add get_celery function to extensions.py"""
    filepath = os.path.join(BASE_DIR, "src/app/extensions.py")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Check if already has get_celery
    if "def get_celery(" in content:
        print("extensions.py: get_celery function already exists - skipping")
        return True
    
    # Add get_celery function after get_websocket_service function
    get_celery_code = '''

def get_celery():
    """Get Celery app instance if available.
    
    Returns None if Celery is not configured or not available.
    This is used by dashboard_service to check Celery status.
    """
    try:
        # Check if USE_CELERY_ANALYSIS is enabled
        use_celery = current_app.config.get('USE_CELERY_ANALYSIS', False)
        if not use_celery:
            return None
        
        # Try to get Celery from celery_worker module
        from app.celery_worker import celery
        return celery
    except ImportError:
        return None
    except Exception:
        return None

'''
    
    # Find a good insertion point - after get_websocket_service function
    # Look for the pattern ending get_websocket_service
    pattern = r"(def get_websocket_service\(\).*?return svc\n)"
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        end_pos = match.end()
        new_content = content[:end_pos] + get_celery_code + content[end_pos:]
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        print("extensions.py: Added get_celery function successfully!")
        return True
    else:
        # Alternative: add at end of file before any trailing content
        # Find a suitable location
        if "def init_extensions(" in content:
            # Insert before init_extensions
            pattern = r"(\ndef init_extensions\()"
            new_content = re.sub(pattern, get_celery_code + r"\1", content)
            
            with open(filepath, 'w') as f:
                f.write(new_content)
            print("extensions.py: Added get_celery function before init_extensions!")
            return True
        else:
            print("extensions.py: Could not find insertion point for get_celery")
            return False


def verify_analyzer_patch():
    """Verify the analyzer Docker detection patch was applied"""
    filepath = os.path.join(BASE_DIR, "src/app/services/dashboard_service.py")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    if "/.dockerenv" in content:
        print("dashboard_service.py: Analyzer Docker detection patch is present!")
        return True
    else:
        print("dashboard_service.py: WARNING - Analyzer Docker detection patch NOT found!")
        return False


def main():
    print("=" * 60)
    print("ThesisApp Production Comprehensive Fix")
    print("=" * 60)
    
    results = []
    
    print("\n1. Fixing Flask factory.py config...")
    results.append(("factory.py config", fix_factory_config()))
    
    print("\n2. Adding get_celery to extensions.py...")
    results.append(("extensions.py get_celery", fix_extensions_get_celery()))
    
    print("\n3. Verifying analyzer patch...")
    results.append(("dashboard_service.py analyzer", verify_analyzer_patch()))
    
    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    for name, success in results:
        status = "✓ OK" if success else "✗ FAILED"
        print(f"  {status}: {name}")
    
    all_success = all(r[1] for r in results)
    if all_success:
        print("\n✓ All fixes applied successfully!")
        print("\nNext steps:")
        print("  1. Rebuild containers: docker compose up -d --build")
        print("  2. Check System Status page")
    else:
        print("\n✗ Some fixes failed - check output above")
    
    return 0 if all_success else 1


if __name__ == "__main__":
    exit(main())
