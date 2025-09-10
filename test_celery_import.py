#!/usr/bin/env python3
"""
Test import of analysis_engines in Celery worker context
"""

import os
import sys

# Change to src directory first (like worker.py does)
src_dir = os.path.join(os.path.dirname(__file__), 'src')
os.chdir(src_dir)
sys.path.insert(0, src_dir)

print(f"Working directory: {os.getcwd()}")
print(f"Python path includes: {src_dir}")

print("\nTesting import of analysis_engines...")

try:
    from app.services.analysis_engines import get_engine
    print("✅ SUCCESS: get_engine imported successfully")
    print(f"get_engine function: {get_engine}")
    
    # Test getting a security engine
    try:
        security_engine = get_engine('security')
        print(f"✅ SUCCESS: Security engine created: {security_engine}")
        print(f"Engine name: {security_engine.engine_name}")
        print(f"Engine integration: {security_engine._integration}")
    except Exception as e:
        print(f"❌ ERROR: Failed to create security engine: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"❌ ERROR: Failed to import get_engine: {e}")
    import traceback
    traceback.print_exc()

print("\nTesting direct analyzer_integration import...")
try:
    from app.services.analyzer_integration import get_analyzer_integration
    print("✅ SUCCESS: analyzer_integration imported successfully")
    
    # Test getting integration instance
    try:
        integration = get_analyzer_integration()
        print(f"✅ SUCCESS: Integration instance created: {integration}")
    except Exception as e:
        print(f"❌ ERROR: Failed to create integration instance: {e}")
        import traceback
        traceback.print_exc()
        
except Exception as e:
    print(f"❌ ERROR: Failed to import analyzer_integration: {e}")
    import traceback
    traceback.print_exc()
